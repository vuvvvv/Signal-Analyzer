"""Spectrum/waveform worker — runs in its own thread.

Always consumes the *newest* IQ chunk (the reader drops older ones for us),
so this thread is never more than one chunk behind regardless of how long
an FFT or a send takes. Its output also feeds the AI worker, but only the
latest spectrum is forwarded (drop-old) — detection doesn't need every
frame, just a reasonably fresh one.
"""

import logging
import queue
import threading
from typing import Callable

import numpy as np

from droppable_queue import put_dropping_oldest

log = logging.getLogger(__name__)


class SpectrumWorker(threading.Thread):
    def __init__(
        self,
        spectrum_slot: "queue.Queue[np.ndarray]",
        ai_in_queue: "queue.Queue[dict]",
        on_spectrum: Callable[[np.ndarray, float, float], None],
        on_waveform: Callable[[list], None],
        fft_size: int = 1024,
        waveform_len: int = 512,
    ):
        super().__init__(name="spectrum-worker", daemon=True)
        self.spectrum_slot = spectrum_slot
        self.ai_in_queue = ai_in_queue
        self.on_spectrum = on_spectrum
        self.on_waveform = on_waveform
        self.fft_size = fft_size
        self.waveform_len = waveform_len
        self.center_freq = 100e6
        self.sample_rate = 2.4e6
        self._stop = threading.Event()

    def stop(self) -> None:
        self._stop.set()

    def run(self) -> None:
        while not self._stop.is_set():
            try:
                samples = self.spectrum_slot.get(timeout=0.2)
            except queue.Empty:
                continue

            try:
                fft = np.fft.fftshift(np.fft.fft(samples, n=self.fft_size))
                powers_db = 20 * np.log10(np.abs(fft) + 1e-12)

                self.on_spectrum(powers_db, self.center_freq, self.sample_rate)
                self.on_waveform(np.real(samples[: self.waveform_len]).tolist())

                put_dropping_oldest(self.ai_in_queue, {
                    "powers_db": powers_db,
                    "center_freq": self.center_freq,
                    "sample_rate": self.sample_rate,
                })
            except Exception as e:
                log.error(f"Spectrum compute error: {e}")
