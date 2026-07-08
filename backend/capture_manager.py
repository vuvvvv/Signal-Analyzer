"""Captures unknown/anomalous signals to disk for later review.

Not every "Unknown"/anomalous detection is saved — only ones that clear
all of:
  - anomaly_score above ANOMALY_THRESHOLD
  - power above MIN_POWER_DB
  - the same frequency bucket has persisted for at least MIN_PERSIST_SECONDS
    (filters out single-frame noise spikes)
  - that bucket hasn't already been captured within CAPTURE_COOLDOWN_SECONDS
    (dedupe against re-saving the same ongoing signal every frame)

Runs entirely on the asyncio-loop thread (called from a callback, not a
hot path) and does no heavy work: PIL for the spectrum image (never
matplotlib — too slow/heavy to load per-capture on a Pi 3) and the stdlib
`wave` module for audio, both fast one-shot writes.
"""

from __future__ import annotations

import json
import logging
import os
import time
import wave
from datetime import datetime, timezone

import numpy as np
from PIL import Image

log = logging.getLogger(__name__)

CAPTURES_DIR = "captures"
ANOMALY_THRESHOLD = 0.7
MIN_POWER_DB = -60.0
MIN_PERSIST_SECONDS = 3.0
CAPTURE_COOLDOWN_SECONDS = 300.0
FREQ_BUCKET_MHZ = 0.05  # signals within this span count as "the same" signal
AUDIO_SAMPLE_RATE = 48000


def _colormap(value: float) -> tuple[int, int, int]:
    """value in [0,1] -> a blue->green->yellow->red heat color, no deps."""
    v = max(0.0, min(1.0, value))
    if v < 0.33:
        t = v / 0.33
        return (0, int(t * 180), int(255 - t * 100))
    if v < 0.66:
        t = (v - 0.33) / 0.33
        return (int(t * 255), int(180 + t * 75), int(155 - t * 155))
    t = (v - 0.66) / 0.34
    return (255, int(255 - t * 255), 0)


class CaptureManager:
    def __init__(self, base_dir: str = CAPTURES_DIR):
        self.base_dir = base_dir
        os.makedirs(self.base_dir, exist_ok=True)
        self._tracked: dict[int, dict] = {}  # freq_bucket -> {first_seen, last_capture}

    def _bucket(self, freq_mhz: float) -> int:
        return round(freq_mhz / FREQ_BUCKET_MHZ)

    def consider(
        self,
        result: dict,
        powers_db: "np.ndarray | None" = None,
        sample_rate: float | None = None,
        recent_pcm_bytes: bytes | None = None,
    ) -> dict | None:
        """Returns capture metadata dict if a capture was saved, else None."""
        anomaly_score = result.get("anomaly_score", 0.0)
        power = result.get("power", -999.0)
        is_candidate = anomaly_score > ANOMALY_THRESHOLD or result.get("type_label") == "Unknown"
        if not is_candidate or power < MIN_POWER_DB:
            return None

        bucket = self._bucket(result["freq"])
        now = time.monotonic()
        track = self._tracked.get(bucket)
        if track is None or (now - track["last_seen"]) > MIN_PERSIST_SECONDS * 3:
            # First sighting, or a stale/old sighting far enough in the
            # past that this is really a new occurrence.
            self._tracked[bucket] = {"first_seen": now, "last_seen": now, "last_capture": None}
            return None

        track["last_seen"] = now
        persisted_for = now - track["first_seen"]
        if persisted_for < MIN_PERSIST_SECONDS:
            return None

        last_capture = track["last_capture"]
        if last_capture is not None and (now - last_capture) < CAPTURE_COOLDOWN_SECONDS:
            return None

        track["last_capture"] = now
        return self._save(result, powers_db, sample_rate, recent_pcm_bytes, persisted_for)

    def _save(
        self,
        result: dict,
        powers_db,
        sample_rate,
        recent_pcm_bytes: bytes | None,
        persisted_for: float,
    ) -> dict:
        ts = datetime.now(timezone.utc)
        folder_name = f"{ts.strftime('%Y%m%dT%H%M%S')}_{result['freq']:.3f}MHz".replace(".", "-", 1)
        folder = os.path.join(self.base_dir, folder_name)
        try:
            os.makedirs(folder, exist_ok=True)

            png_path = None
            if powers_db is not None:
                png_path = os.path.join(folder, "spectrum.png")
                self._save_spectrum_png(powers_db, png_path)

            wav_path = None
            if recent_pcm_bytes:
                wav_path = os.path.join(folder, "audio.wav")
                self._save_wav(recent_pcm_bytes, wav_path)

            meta = {
                **result,
                "persisted_seconds": round(persisted_for, 1),
                "captured_at": ts.isoformat(),
                "folder": folder_name,
                "has_spectrum_image": png_path is not None,
                "has_audio": wav_path is not None,
                "sample_rate": sample_rate,
            }
            with open(os.path.join(folder, "meta.json"), "w") as f:
                json.dump(meta, f, indent=2)

            log.info(f"CaptureManager: saved capture {folder_name}")
            return meta
        except Exception as e:
            log.error(f"CaptureManager: failed to save capture: {e}")
            return {"folder": folder_name, "error": str(e)}

    def _save_spectrum_png(self, powers_db: np.ndarray, path: str, height: int = 160) -> None:
        n = len(powers_db)
        lo, hi = float(np.min(powers_db)), float(np.max(powers_db))
        span = max(1e-6, hi - lo)
        normalized = (powers_db - lo) / span

        row = np.zeros((n, 3), dtype=np.uint8)
        for i, v in enumerate(normalized):
            row[i] = _colormap(float(v))
        # Repeat the single FFT row into a band so it reads as a
        # spectrum/waterfall-style strip rather than a 1px sliver.
        img_array = np.tile(row, (height, 1, 1))
        Image.fromarray(img_array, mode="RGB").save(path)

    def _save_wav(self, pcm_bytes: bytes, path: str) -> None:
        with wave.open(path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)  # PCM16
            wf.setframerate(AUDIO_SAMPLE_RATE)
            wf.writeframes(pcm_bytes)

    def list_captures(self) -> list[dict]:
        out = []
        if not os.path.isdir(self.base_dir):
            return out
        for name in sorted(os.listdir(self.base_dir), reverse=True):
            meta_path = os.path.join(self.base_dir, name, "meta.json")
            if os.path.exists(meta_path):
                try:
                    with open(meta_path) as f:
                        out.append(json.load(f))
                except Exception:
                    continue
        return out
