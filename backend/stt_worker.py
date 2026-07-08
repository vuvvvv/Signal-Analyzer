"""Speech-to-text — strictly on-demand, never runs during normal operation.

Only starts when the client explicitly sends `start_stt` (the "Speech To
Text" button in the Flutter AI tab) and stops on `stop_stt` or
disconnect. Uses Vosk's small model (~40MB, CPU-only, no GPU needed) —
NOT Whisper, which is too heavy for a Pi 3.

The model is not bundled with this repo (too large); if it isn't present
under VOSK_MODEL_DIR, `start()` reports unavailable instead of crashing,
so this feature degrades gracefully rather than blocking anything else.
"""

from __future__ import annotations

import json
import logging
import os
import threading
from typing import Callable

log = logging.getLogger(__name__)

VOSK_MODEL_DIR = os.path.join(os.path.dirname(__file__), "models", "vosk-model-small")
SAMPLE_RATE = 48000


class SttWorker:
    def __init__(self, on_text: Callable[[str], None]):
        self._on_text = on_text
        self._active = False
        self._lock = threading.Lock()
        self._recognizer = None

    @property
    def available(self) -> bool:
        return os.path.isdir(VOSK_MODEL_DIR)

    def start(self) -> bool:
        with self._lock:
            if self._active:
                return True
            if not self.available:
                log.warning(f"SttWorker: no Vosk model at {VOSK_MODEL_DIR}; STT unavailable")
                return False
            try:
                from vosk import KaldiRecognizer, Model  # optional dep, imported lazily

                model = Model(VOSK_MODEL_DIR)
                self._recognizer = KaldiRecognizer(model, SAMPLE_RATE)
                self._active = True
                return True
            except Exception as e:
                log.error(f"SttWorker: failed to start ({e})")
                self._recognizer = None
                return False

    def stop(self) -> None:
        with self._lock:
            self._active = False
            self._recognizer = None

    @property
    def active(self) -> bool:
        return self._active

    def feed(self, pcm_bytes: bytes) -> None:
        """Call with small PCM16/48kHz chunks while active; partial/final
        results are pushed to `on_text` as they become available."""
        with self._lock:
            if not self._active or self._recognizer is None:
                return
            recognizer = self._recognizer
        try:
            if recognizer.AcceptWaveform(pcm_bytes):
                text = json.loads(recognizer.Result()).get("text", "")
                if text:
                    self._on_text(text)
        except Exception as e:
            log.error(f"SttWorker: feed error ({e})")
