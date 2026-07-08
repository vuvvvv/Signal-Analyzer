"""Dedicated RTL-SDR reader thread.

This thread does exactly one thing: call the blocking `read_samples()` and
fan each chunk out to the workers. It never runs FFT, demodulation, AI, or
serialization, so a slow downstream consumer can never stall the actual
hardware read and starve the SDR's internal USB buffer.

The pyrtlsdr handle is opened exactly once and stays open for as long as
scanning is active — spectrum and local audio playback (see audio_worker.py)
both run off the same IQ stream from this single reader, never a second
device handle.

Fan-out:
- `audio_queue`: every chunk, in order (bounded, drop-oldest on overload —
  the reader itself must never block, even if that means losing audio).
  Carries the *raw* uint8 IQ bytes (pyrtlsdr's read_bytes(), unconverted)
  alongside the normalized complex128 — rtl_fm_chain.py feeds the raw
  bytes straight into rtl_fm_pipe, byte-for-byte what the real RTL-SDR
  USB transfer would have carried, since `rtl_fm` itself operates on
  that exact raw format.
- `spectrum_slot`: only the newest chunk (maxsize=1, drop-oldest), since
  spectrum/AI only ever care about "what does it look like right now".
"""

from __future__ import annotations

import logging
import queue
import threading
import time

import numpy as np
from rtlsdr import RtlSdr

from droppable_queue import put_dropping_oldest
from stage_profiler import StageProfiler

log = logging.getLogger(__name__)

PROFILE_LOG_EVERY = 100


class SdrReader(threading.Thread):
    def __init__(
        self,
        sample_rate: float,
        num_samples: int,
        audio_queue: "queue.Queue[tuple[int, float, np.ndarray]]",
        spectrum_slot: "queue.Queue[np.ndarray]",
        freq_correction_ppm: int = 0,
        gain: float | str = 40.2,
    ):
        super().__init__(name="sdr-reader", daemon=True)
        self.sample_rate = sample_rate
        self.num_samples = num_samples
        self.audio_queue = audio_queue
        self.spectrum_slot = spectrum_slot
        self.freq_correction_ppm = freq_correction_ppm
        self.gain = gain

        self.sdr: RtlSdr | None = None
        self.center_freq = 100e6
        self.scanning = threading.Event()
        self._stop = threading.Event()
        self._freq_lock = threading.Lock()
        self._pending_freq: float | None = None
        self._generation = 0
        self.profiler = StageProfiler()
        self._read_count = 0

    def init_sdr(self) -> bool:
        try:
            self.sdr = RtlSdr()
            self.sdr.sample_rate = self.sample_rate
            self.sdr.center_freq = self.center_freq
            if self.gain != "auto":
                self._apply_nearest_gain(self.gain)
            else:
                self.sdr.gain = "auto"
            log.info(f"Gain requested={self.gain!r} actual={self.sdr.gain!r}")
            if self.freq_correction_ppm:
                self.sdr.freq_correction = self.freq_correction_ppm
            log.info("RTL-SDR initialized")
            return True
        except Exception as e:
            log.error(f"SDR init failed: {e}")
            self.sdr = None
            return False

    def _apply_nearest_gain(self, requested_gain: float) -> None:
        """Different tuner chips (e.g. FC0013 vs R820T) expose different
        discrete gain steps. Asking for a value that isn't one of them
        gets silently snapped to *something* by the driver — pick the
        nearest valid step ourselves so the chosen value is deterministic
        and logged, instead of finding out only by measuring afterwards."""
        try:
            valid_gains = self.sdr.valid_gains_db
            if valid_gains:
                nearest = min(valid_gains, key=lambda g: abs(g - requested_gain))
                self.sdr.gain = nearest
                return
        except Exception as e:
            log.error(f"Could not read valid_gains_db: {e}")
        try:
            self.sdr.gain = requested_gain
        except Exception as e:
            log.error(f"Gain {requested_gain!r} rejected, falling back to auto: {e}")
            self.sdr.gain = "auto"

    def set_center_freq(self, freq_hz: float) -> int:
        """Only a *real* frequency change bumps `generation`; calling this
        again with the same frequency (e.g. a duplicate command from the
        client) is a no-op. Returns the current generation, which
        AudioWorker uses to know when to drop stale-frequency IQ."""
        with self._freq_lock:
            if abs(freq_hz - self.center_freq) < 1.0:
                log.info(
                    f"set_center_freq({freq_hz:.0f}) is a no-op: already at "
                    f"{self.center_freq:.0f}Hz (generation stays {self._generation})"
                )
                return self._generation
            previous = self.center_freq
            self.center_freq = freq_hz
            self._pending_freq = freq_hz
            self._generation += 1
            log.info(
                f"set_center_freq: {previous:.0f}Hz -> {freq_hz:.0f}Hz, "
                f"generation {self._generation - 1} -> {self._generation}"
            )
            return self._generation

    def stop(self) -> None:
        self._stop.set()
        self.scanning.clear()

    def run(self) -> None:
        while not self._stop.is_set():
            if not self.scanning.wait(timeout=0.2):
                continue
            if self.sdr is None and not self.init_sdr():
                self.scanning.clear()
                continue

            with self._freq_lock:
                pending, self._pending_freq = self._pending_freq, None
            if pending is not None:
                try:
                    self.sdr.center_freq = pending
                except Exception as e:
                    # e.g. LIBUSB_ERROR_IO: tuner (FC0013/R820T/...) has no
                    # valid PLL combination for this frequency, out of the
                    # tuner's tunable range. The driver leaves the hardware
                    # at its last-good frequency, so resync our tracked
                    # center_freq to that instead of the rejected `pending`
                    # (which set_center_freq had already optimistically
                    # applied) — otherwise a retry of the same bad
                    # frequency would look like a no-op change and never
                    # reach the tuner again. Skip the flush read; the
                    # tuner never actually retuned.
                    log.error(f"SDR rejected center_freq={pending:.0f}Hz: {e}")
                    try:
                        with self._freq_lock:
                            self.center_freq = self.sdr.get_center_freq()
                    except Exception as e2:
                        log.error(f"Could not read back center_freq after rejection: {e2}")
                    continue
                try:
                    # flush stale IQ buffered by the driver/tuner before retune took effect
                    self.sdr.read_samples(self.num_samples)
                except Exception as e:
                    log.error(f"SDR flush read error: {e}")

            try:
                with self._freq_lock:
                    generation = self._generation
                t0 = time.perf_counter()
                # read_bytes(), not read_samples(): we need the raw uint8
                # I,Q bytes (the same layout the real USB transfer carries)
                # to feed rtl_fm_pipe unmodified. The complex IQ used for
                # spectrum is derived from those same bytes below via
                # pyrtlsdr's own read_samples()/packed_bytes_to_iq() formula,
                # so spectrum output is unaffected by this change.
                raw = self.sdr.read_bytes(self.num_samples * 2)
                capture_time = time.perf_counter()
                self.profiler.record("rtl_read", capture_time - t0)

                raw_bytes = bytes(raw)
                samples = np.frombuffer(raw, dtype=np.uint8).astype(np.float64).view(np.complex128)
                samples /= 127.5
                samples -= (1 + 1j)

                if put_dropping_oldest(self.audio_queue, (generation, capture_time, raw_bytes)):
                    self.profiler.record_drop("audio_queue")
                if put_dropping_oldest(self.spectrum_slot, samples):
                    self.profiler.record_drop("spectrum_slot")

                self._read_count += 1
                if self._read_count >= PROFILE_LOG_EVERY:
                    self._read_count = 0
                    self.profiler.log_report(log, prefix="SdrReader: ")
                    # Diagnostic only — measurement, no correction/filtering
                    # applied to raw_bytes itself. Ideal unbiased center for
                    # an 8-bit unsigned I/Q sample is 127.5.
                    raw_u8 = np.frombuffer(raw, dtype=np.uint8)
                    log.info(
                        f"SdrReader: IQ DC bias (raw uint8, diagnostic only): "
                        f"I_avg={raw_u8[0::2].mean():.3f} Q_avg={raw_u8[1::2].mean():.3f} "
                        f"(ideal=127.500)"
                    )
            except Exception as e:
                log.error(f"SDR read error: {e}")
                self.scanning.clear()
                self.sdr = None
