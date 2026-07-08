"""Shared rolling-window stage-timing profiler.

Every pipeline stage (RTL-SDR read, queue wait, each DSP step, msgpack
serialization, WebSocket send, ...) records its duration here instead of
hand-rolled sum/count accumulators, so every stage reports the same
Average / Min / Max / p99 instead of just an average — p99 in particular
is what reveals an occasional long stall that an average hides.
"""

from __future__ import annotations

import logging
import time
from collections import deque

import numpy as np


class StageProfiler:
    def __init__(self, window: int = 500):
        self.window = window
        self._stages: dict[str, deque] = {}
        self._counts: dict[str, int] = {}
        self._drops: dict[str, int] = {}
        self._rate_events: dict[str, deque] = {}

    def record(self, stage: str, duration_s: float) -> None:
        dq = self._stages.setdefault(stage, deque(maxlen=self.window))
        dq.append(duration_s)
        self._counts[stage] = self._counts.get(stage, 0) + 1

    def record_drop(self, stage: str, n: int = 1) -> None:
        self._drops[stage] = self._drops.get(stage, 0) + n

    def record_event(self, stage: str, now: float | None = None) -> None:
        """Track a throughput-style event (e.g. one audio chunk produced)
        so a rate-per-second can be derived from event timestamps."""
        now = now if now is not None else time.perf_counter()
        dq = self._rate_events.setdefault(stage, deque(maxlen=self.window))
        dq.append(now)

    def rate_per_sec(self, stage: str) -> float:
        dq = self._rate_events.get(stage)
        if not dq or len(dq) < 2:
            return 0.0
        span = dq[-1] - dq[0]
        return (len(dq) - 1) / span if span > 0 else 0.0

    def stats(self, stage: str) -> dict | None:
        dq = self._stages.get(stage)
        if not dq:
            return None
        arr = np.array(dq)
        return {
            "avg_ms": float(np.mean(arr)) * 1000,
            "min_ms": float(np.min(arr)) * 1000,
            "max_ms": float(np.max(arr)) * 1000,
            "p99_ms": float(np.percentile(arr, 99)) * 1000,
            "count": self._counts.get(stage, 0),
            "drops": self._drops.get(stage, 0),
        }

    def all_stats(self) -> dict[str, dict]:
        return {stage: self.stats(stage) for stage in self._stages}

    def format_report(self, extra: dict | None = None) -> str:
        parts = []
        for stage, s in self.all_stats().items():
            if s is None:
                continue
            parts.append(
                f"{stage}[avg={s['avg_ms']:.3f} min={s['min_ms']:.3f} "
                f"max={s['max_ms']:.3f} p99={s['p99_ms']:.3f} drops={s['drops']}]"
            )
        for stage, dq in self._rate_events.items():
            parts.append(f"{stage}_rate={self.rate_per_sec(stage):.1f}/s")
        if extra:
            for k, v in extra.items():
                parts.append(f"{k}={v}")
        return " ".join(parts)

    def log_report(self, log: logging.Logger, prefix: str = "", extra: dict | None = None) -> None:
        log.info(f"{prefix}{self.format_report(extra)}")
