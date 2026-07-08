"""AI signal-detection worker — runs in its own OS process.

IsolationForest retraining is real CPU-bound work (every 20th detection it
refits 100 estimators) and the stdlib GIL means that, on a thread, it would
periodically steal CPU time from the audio/spectrum/network threads no
matter how the rest of the pipeline is structured. Running it as a separate
process gives it its own GIL and lets the Pi's other cores actually absorb
the spike instead of stalling real-time work.

Only the *latest* spectrum is ever queued in (drop-old, by the caller),
since detection doesn't need every frame. Detections out are never dropped.
"""

import logging
import multiprocessing as mp
import queue
import threading
from typing import Callable

log = logging.getLogger(__name__)


def _process_main(in_queue: mp.Queue, out_queue: mp.Queue, stop_event):
    from signal_analyzer import SignalAnalyzer  # imported in-process

    analyzer = SignalAnalyzer()
    while not stop_event.is_set():
        try:
            job = in_queue.get(timeout=0.2)
        except queue.Empty:
            continue
        try:
            detected = analyzer.detect(job["powers_db"], job["center_freq"], job["sample_rate"])
            for sig in detected:
                out_queue.put(sig)
        except Exception as e:
            log.error(f"AI detect error: {e}")


class AiWorker:
    def __init__(self, on_detection: Callable[[dict], None]):
        self.in_queue: mp.Queue = mp.Queue(maxsize=1)
        self.out_queue: mp.Queue = mp.Queue()
        self._stop_event = mp.Event()
        self._process = mp.Process(
            target=_process_main,
            args=(self.in_queue, self.out_queue, self._stop_event),
            daemon=True,
        )
        self._on_detection = on_detection
        self._bridge_thread = threading.Thread(
            target=self._bridge_loop, name="ai-bridge", daemon=True
        )
        self._bridge_stop = threading.Event()

    def start(self) -> None:
        self._process.start()
        self._bridge_thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        self._bridge_stop.set()
        if self._process.is_alive():
            self._process.join(timeout=2)

    def _bridge_loop(self) -> None:
        while not self._bridge_stop.is_set():
            try:
                sig = self.out_queue.get(timeout=0.2)
            except queue.Empty:
                continue
            self._on_detection(sig)
