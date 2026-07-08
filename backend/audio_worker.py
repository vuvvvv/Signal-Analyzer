"""Audio worker — feeds IQ into reference DSP engines and plays the PCM
they produce. No demodulator is implemented here or anywhere else in this
codebase:

  - WFM/NFM/AM/USB/LSB are demodulated by rtl_fm_pipe (rtl_fm_chain.py), a
    patched build of rtl-sdr's own rtl_fm.c — byte-for-byte the same DSP
    code the real `rtl_fm` CLI runs, just reading already-captured IQ from
    stdin instead of a second USB device.
  - CW has no -M mode in real rtl_fm, so it uses csdr (csdr_chain.py)
    instead — a separate, mature reference DSP engine (used by OpenWebRX),
    not anything written for this project.

This file's only jobs are:
  - feed thread (`run`): pull IQ chunks off `audio_queue` (the same queue
    SdrReader already fills for every chunk, from its single pyrtlsdr
    handle) and write them to whichever chain handles the current mode,
    but only while a client has asked for audio (`enabled`) — otherwise
    chunks are simply dropped so spectrum/AI keep full throughput without
    paying for demod work nobody asked for.
  - reader thread (`_reader_loop`): drain finished PCM16 off the active
    chain's stdout, apply the linear volume/mute gain (not a demodulator —
    just an amplitude scale), and hand it to LocalAudioSink for playback.
"""

from __future__ import annotations

import logging
import queue
import threading
import time

import numpy as np

from csdr_chain import CsdrChain
from droppable_queue import put_dropping_oldest
from local_audio import LocalAudioSink
from rtl_fm_chain import MODE_MAP as RTL_FM_MODES
from rtl_fm_chain import RtlFmChain

log = logging.getLogger(__name__)


class AudioWorker(threading.Thread):
    def __init__(
        self,
        sample_rate: float,
        audio_queue: "queue.Queue[tuple[int, float, bytes]]",
        sink: LocalAudioSink,
        demodulator: str = "WFM",
        ai_tap_queue: "queue.Queue[dict] | None" = None,
    ):
        super().__init__(name="audio-worker", daemon=True)
        self.sample_rate = sample_rate
        self.audio_queue = audio_queue
        self.sink = sink
        # Optional tap for AI/AI-adjacent consumers (audio classifier,
        # capture manager, STT) — a copy of finished PCM, never the real
        # playback path. Drop-oldest and best-effort: if nobody is
        # consuming it (queue full), we just skip pushing this chunk
        # rather than block real playback for it.
        self.ai_tap_queue = ai_tap_queue
        self._tap_buffer = bytearray()
        self._tap_chunk_bytes = int(48000 * 1.0) * 2  # ~1s of PCM16 mono @48kHz
        self.rtl_fm_chain = RtlFmChain()
        self.csdr_chain = CsdrChain()
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self.enabled = False
        self.muted = False
        self.volume = 1.0
        self.demodulator_name = demodulator.upper()
        self._reader_thread = threading.Thread(
            target=self._reader_loop, name="audio-reader", daemon=True
        )

    def start(self) -> None:
        self._reader_thread.start()
        super().start()

    def stop(self) -> None:
        self._stop.set()
        self.rtl_fm_chain.stop()
        self.csdr_chain.stop()

    def _uses_rtl_fm(self, name: str) -> bool:
        return name in RTL_FM_MODES

    def _active_chain(self):
        return self.rtl_fm_chain if self._uses_rtl_fm(self.demodulator_name) else self.csdr_chain

    def enable(self) -> None:
        with self._lock:
            self.enabled = True
            self._start_chain_locked()

    def disable(self) -> None:
        with self._lock:
            self.enabled = False
            self.rtl_fm_chain.stop()
            self.csdr_chain.stop()

    def set_demodulator(self, name: str) -> None:
        name = name.upper()
        with self._lock:
            self.demodulator_name = name
            if self.enabled:
                self._start_chain_locked()  # fresh process for the new mode

    def restart_chain(self) -> None:
        """Force a fresh demod process so no carried-over filter/
        discriminator state (fm_demod's pre_r/pre_j, deemph_filter's
        static avg, etc.) bleeds from the previous station into the new
        one after a retune. No-op if audio isn't currently enabled."""
        with self._lock:
            if self.enabled:
                self._start_chain_locked()

    def _start_chain_locked(self) -> None:
        self.rtl_fm_chain.stop()
        self.csdr_chain.stop()
        if self._uses_rtl_fm(self.demodulator_name):
            self.rtl_fm_chain.start(self.demodulator_name)
        else:
            self.csdr_chain.start(self.demodulator_name)

    def set_volume(self, volume: float) -> None:
        self.volume = max(0.0, min(volume, 4.0))

    def mute(self) -> None:
        self.muted = True

    def unmute(self) -> None:
        self.muted = False

    def run(self) -> None:
        while not self._stop.is_set():
            try:
                _generation, _capture_time, raw_bytes = self.audio_queue.get(timeout=0.2)
            except queue.Empty:
                continue

            if not self.enabled:
                continue  # drop — spectrum/AI already got their own copy upstream

            with self._lock:
                if self._uses_rtl_fm(self.demodulator_name):
                    if self.rtl_fm_chain.running:
                        self.rtl_fm_chain.feed(raw_bytes)
                else:
                    if self.csdr_chain.running:
                        # csdr's "cf" stages want normalized complex64, not
                        # raw uint8 — derive it from the same raw bytes
                        # (pyrtlsdr's own formula), only when csdr is the
                        # active chain (CW only).
                        iq = np.frombuffer(raw_bytes, dtype=np.uint8).astype(np.float32).view(np.complex64)
                        iq = iq / 127.5 - (1 + 1j)
                        self.csdr_chain.feed(iq.tobytes())

    def _reader_loop(self) -> None:
        while not self._stop.is_set():
            stdout = self._active_chain().stdout
            if stdout is None:
                time.sleep(0.05)
                continue
            try:
                chunk = stdout.read(4096)
            except Exception:
                chunk = b""
            if not chunk:
                time.sleep(0.02)
                continue
            if self.muted:
                continue  # still drained above, so the chain never blocks on a full pipe
            pcm = np.frombuffer(chunk, dtype=np.int16)
            if self.volume != 1.0:
                pcm = np.clip(pcm.astype(np.float64) * self.volume, -32768, 32767).astype(np.int16)
            pcm_bytes = pcm.tobytes()
            self.sink.write(pcm_bytes)
            self._feed_tap(pcm_bytes)

    def _feed_tap(self, pcm_bytes: bytes) -> None:
        """Accumulate ~1s of PCM before handing it to the AI tap queue —
        the classifier needs enough samples for a stable spectral
        estimate, and this keeps the queue traffic low. Never blocks:
        drop-oldest, and simply skipped if there's no tap configured."""
        if self.ai_tap_queue is None:
            return
        self._tap_buffer.extend(pcm_bytes)
        if len(self._tap_buffer) >= self._tap_chunk_bytes:
            payload = bytes(self._tap_buffer[: self._tap_chunk_bytes])
            del self._tap_buffer[: self._tap_chunk_bytes]
            put_dropping_oldest(self.ai_tap_queue, {
                "pcm_bytes": payload,
                "time": time.time(),
            })
