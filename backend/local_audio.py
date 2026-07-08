"""Local PCM playback sink for the Pi's own audio output.

This is a dumb pipe: it owns no SDR state and never touches the RTL-SDR
device. AudioWorker hands it finished 48kHz mono PCM16 bytes (demodulated
in-process from the *same* IQ stream SdrReader already uses for spectrum)
and this just feeds them to a persistent `play` subprocess writing to the
Pi's local audio output. No PCM ever crosses the WebSocket.
"""

from __future__ import annotations

import logging
import subprocess
from typing import Optional

log = logging.getLogger(__name__)

SAMPLE_RATE = 48000


class LocalAudioSink:
    def __init__(self) -> None:
        self.running = False
        self._proc: Optional[subprocess.Popen] = None

    def start(self) -> None:
        if self.running:
            return
        cmd = [
            "play", "-q", "-t", "raw", "-r", str(SAMPLE_RATE), "-e", "signed",
            "-b", "16", "-c", "1", "-",
            # Applied to rtl_fm's finished PCM, not the IQ/demod pipeline:
            # highpass removes residual hum/rumble below speech/music range,
            # lowpass matches WFM mono's actual ~15kHz audio bandwidth and
            # cuts noise above it. Both are sox's own built-in effects.
            "highpass", "100", "lowpass", "15000",
        ]
        try:
            self._proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)
            self.running = True
            log.info("LocalAudioSink: started 'play' subprocess")
        except FileNotFoundError as e:
            log.error(f"LocalAudioSink: missing 'play' binary ({e}). Install sox.")

    def stop(self) -> None:
        if self._proc is not None:
            try:
                if self._proc.stdin:
                    self._proc.stdin.close()
                self._proc.terminate()
                self._proc.wait(timeout=2.0)
            except Exception:
                self._proc.kill()
            self._proc = None
        self.running = False

    def write(self, pcm_bytes: bytes) -> None:
        if not self.running or self._proc is None or self._proc.stdin is None:
            return
        try:
            self._proc.stdin.write(pcm_bytes)
        except (BrokenPipeError, OSError, ValueError) as e:
            # ValueError: "write to closed file" — the reader thread can
            # race a stop() that already closed stdin; harmless, just stop.
            log.error(f"LocalAudioSink: write failed, stopping ({e})")
            self.stop()
