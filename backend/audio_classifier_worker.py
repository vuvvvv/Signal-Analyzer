"""Audio classification worker V3 — multi-layer temporal multi-label analysis.

Runs in its own OS process (same pattern as ai_worker.py) so it can never
steal GIL time from AudioWorker's real-time feed/reader threads.

V3 redesign (no more single-winner softmax):

  Layer 1 — frame analysis. Incoming PCM is split into ~170 ms sub-frames
  and each is scored INDEPENDENTLY against every label (true multi-label:
  each score is 0..1 on its own evidence, never normalized against the
  others — Speech 0.83 and Noise 0.41 can both be true).

  Layer 2 — temporal aggregation. A sliding window keeps the last
  WINDOW_SECONDS of frame scores. Old frames are never re-analyzed; the
  window only aggregates already-computed scores (cheap, Pi-3-friendly).
  The report says how many seconds of the window contained speech / tone /
  music / noise / silence, and the per-label component percentages are
  window means, so mixed content (speech, then a tone, over hiss) shows
  every element.

  Layer 3 — pattern analysis. The window's frame-state sequence is
  segmented and matched against temporal signatures:
      tone/silence repeating on a regular period  -> Periodic Tone
                                                     (+period, duration, count)
      bimodal short/long tone bursts              -> Morse-like keying
      speech/silence alternation                  -> Push-To-Talk Voice
      data/silence alternation                    -> Burst Digital Signal

  Tone taxonomy: Tone is NOT Music. Frame evidence separates Continuous
  Tone, Beep (pattern-level: short isolated tone), DTMF (row+column dual
  tones), CTCSS sub-audible squelch tones, 19 kHz FM stereo pilot, alert
  tones (1050 Hz aviation / EAS 853+960 Hz pair), Whistle (drifting
  narrow tone), and Music (harmonic stack + temporal variation) — each
  scored independently with its own reasons.

  FM verification support: the 19 kHz stereo pilot score is exported as
  `stereo_pilot`, extra broadcast evidence beyond "it's in the FM band".
  (RDS at 57 kHz is above the 24 kHz Nyquist of the 48 kHz PCM tap, so it
  is *not* claimed — decoding it would need the pre-decimation baseband.)

Every emitted result still carries `label`/`confidence` (top component)
for backward compatibility, plus `reason` per decision, so classification
stays explainable. If a quantized TFLite model exists at AUDIO_MODEL_PATH
its per-class probabilities are fed into the same temporal aggregator.
"""

from __future__ import annotations

import logging
import multiprocessing as mp
import os
import queue
import threading
import time
from collections import deque
from typing import Callable

import numpy as np

log = logging.getLogger(__name__)

AUDIO_MODEL_PATH = os.path.join(os.path.dirname(__file__), "models", "audio_classifier.tflite")
SAMPLE_RATE = 48000

FRAME_SAMPLES = 4096          # ~85 ms per analysis frame (resolves Morse dots)
WINDOW_SECONDS = 10.0         # temporal aggregation window
PRESENT_THRESHOLD = 0.5       # a label "occupies" a frame above this score

# All labels are scored independently per frame (multi-label).
LABELS = [
    "Speech", "Music", "Noise", "Silence", "Digital/Data",
    "Continuous Tone", "Whistle", "DTMF", "CTCSS Subtone",
    "Pilot Tone 19k", "Alert Tone",
]

# Kept for the optional TFLite path (coarse model classes map onto the
# fine-grained label set above).
TFLITE_LABELS = ["Speech", "Music", "Noise", "Continuous Tone", "Digital/Data"]

_DTMF_ROWS = (697.0, 770.0, 852.0, 941.0)
_DTMF_COLS = (1209.0, 1336.0, 1477.0, 1633.0)
_CTCSS_LO, _CTCSS_HI = 67.0, 254.1
_ALERT_FREQS = ((1050.0, 30.0), (853.0, 15.0), (960.0, 15.0))  # aviation, EAS pair


# ---------------------------------------------------------------------------
# Layer 1 — independent per-frame feature extraction and label scoring
# ---------------------------------------------------------------------------

def _tonal_peaks(spectrum: np.ndarray, freqs: np.ndarray, max_peaks: int = 6) -> list[tuple[float, float]]:
    """Dominant narrow spectral peaks as (freq_hz, prominence_db) —
    the raw evidence for every tone-family label."""
    mag_db = 20.0 * np.log10(spectrum + 1e-12)
    median_db = float(np.median(mag_db))
    out: list[tuple[float, float]] = []
    order = np.argsort(mag_db)[::-1]
    for idx in order[:200]:
        f = float(freqs[idx])
        if f < 40.0:
            continue
        prominence = float(mag_db[idx]) - median_db
        if prominence < 15.0:
            break
        if all(abs(f - pf) > 40.0 for pf, _ in out):
            out.append((f, prominence))
            if len(out) >= max_peaks:
                break
    return out


def _frame_features(x: np.ndarray) -> dict:
    n = len(x)
    rms = float(np.sqrt(np.mean(x ** 2))) if n else 0.0

    signs = np.sign(x)
    signs[signs == 0] = 1
    zcr = float(np.mean(signs[:-1] != signs[1:])) if n > 1 else 0.0

    spectrum = np.abs(np.fft.rfft(x * np.hanning(n)))
    spectrum = spectrum + 1e-12
    freqs = np.fft.rfftfreq(n, d=1.0 / SAMPLE_RATE)

    centroid = float(np.sum(freqs * spectrum) / np.sum(spectrum))
    flatness = float(np.exp(np.mean(np.log(spectrum))) / np.mean(spectrum))

    peaks = _tonal_peaks(spectrum, freqs)

    # How concentrated is the frame's energy in the top peak? A pure tone
    # puts nearly everything within a few bins; speech/music/noise don't.
    energy = spectrum ** 2
    total_energy = float(np.sum(energy))
    peak_energy_ratio = 0.0
    if peaks and total_energy > 0:
        top_idx = int(np.argmin(np.abs(freqs - peaks[0][0])))
        lo, hi = max(0, top_idx - 10), min(len(energy), top_idx + 11)
        peak_energy_ratio = float(np.sum(energy[lo:hi]) / total_energy)

    # Peaks that rival the top one (>60% of its prominence): a single
    # strong peak = tone; several = dual tones, harmonics, music.
    strong_peak_count = sum(1 for _, p in peaks if peaks and p > 0.6 * peaks[0][1])

    # Harmonicity: how many peaks sit on integer multiples of the lowest
    # peak (music/voiced speech have harmonic stacks; a pure tone doesn't).
    harmonic_count = 0
    if peaks:
        f0 = min(pf for pf, _ in peaks)
        if f0 > 50:
            for pf, _ in peaks:
                ratio = pf / f0
                if abs(ratio - round(ratio)) < 0.06 and round(ratio) > 1:
                    harmonic_count += 1

    def _band_prominence(target: float, tol: float) -> float:
        sel = (freqs >= target - tol) & (freqs <= target + tol)
        if not np.any(sel):
            return 0.0
        band_db = 20.0 * np.log10(float(np.max(spectrum[sel])) + 1e-12)
        return band_db - 20.0 * np.log10(float(np.median(spectrum)) + 1e-12)

    pilot_db = _band_prominence(19000.0, 150.0)

    # CTCSS: compare the strongest 67-254 Hz bin against the *local*
    # low-frequency band median — speech/noise energy down there would
    # otherwise make the whole-spectrum comparison fire constantly.
    ctcss_db = 0.0
    ctcss_freq = 0.0
    local_sel = (freqs >= 50.0) & (freqs <= 350.0)
    ctcss_sel = (freqs >= _CTCSS_LO) & (freqs <= _CTCSS_HI)
    if np.any(ctcss_sel) and np.any(local_sel):
        i = int(np.argmax(spectrum[ctcss_sel]))
        ctcss_freq = float(freqs[ctcss_sel][i])
        ctcss_db = 20.0 * np.log10(float(spectrum[ctcss_sel][i]) + 1e-12) \
            - 20.0 * np.log10(float(np.median(spectrum[local_sel])) + 1e-12)

    # DTMF: BOTH members of the pair must be strong (rival) peaks, not a
    # random harmonic grazing a row/col frequency.
    strong = [pf for pf, p in peaks if peaks and p > 0.6 * peaks[0][1]]
    dtmf_pair = None
    row_hits = [r for pf in strong for r in _DTMF_ROWS if abs(pf - r) < 25.0]
    col_hits = [c for pf in strong for c in _DTMF_COLS if abs(pf - c) < 30.0]
    if row_hits and col_hits:
        dtmf_pair = (row_hits[0], col_hits[0])

    # Alert tones are pure carriers: the TOP peak must sit on the alert
    # frequency (sidelobes/harmonics near it don't count).
    alert_hits = []
    if peaks:
        alert_hits = [t for t, tol in _ALERT_FREQS if abs(peaks[0][0] - t) < tol]
        if dtmf_pair is None and len(strong) == 2:  # EAS 853+960 pair
            if any(abs(pf - 853.0) < 15 for pf in strong) and any(abs(pf - 960.0) < 15 for pf in strong):
                alert_hits = [853.0, 960.0]

    return {
        "rms": rms, "zcr": zcr, "centroid": centroid, "flatness": flatness,
        "peaks": peaks, "harmonic_count": harmonic_count,
        "peak_energy_ratio": peak_energy_ratio, "strong_peak_count": strong_peak_count,
        "pilot_db": pilot_db, "ctcss_db": ctcss_db, "ctcss_freq": ctcss_freq,
        "dtmf_pair": dtmf_pair, "alert_hits": alert_hits,
    }


def _frame_scores(f: dict) -> tuple[dict[str, float], dict[str, list[str]]]:
    """Independent 0..1 score per label. No normalization across labels —
    several labels being high simultaneously is the intended behavior."""
    s: dict[str, float] = {label: 0.0 for label in LABELS}
    why: dict[str, list[str]] = {}

    def add(label: str, amount: float, reason: str):
        s[label] = min(1.0, s[label] + amount)
        why.setdefault(label, []).append(reason)

    if f["rms"] < 0.006:
        add("Silence", 1.0, "Frame energy below silence threshold")
        return s, why

    peaks = f["peaks"]
    top_prom = peaks[0][1] if peaks else 0.0
    tone_freq = peaks[0][0] if peaks else 0.0

    # --- Noise: flat spectrum, no tonal structure (independent of others) ---
    if f["flatness"] > 0.35:
        add("Noise", min(1.0, (f["flatness"] - 0.35) * 2.5 + 0.4),
            f"High spectral flatness ({f['flatness']:.2f})")
    elif f["flatness"] > 0.18:
        add("Noise", 0.3, f"Moderate broadband component (flatness {f['flatness']:.2f})")
    if f["zcr"] > 0.4:
        add("Noise", 0.2, "Very high zero-crossing rate (broadband)")

    # --- Tone family: energy concentrated in ONE narrow peak, NOT music ---
    if (peaks and top_prom > 20.0 and f["peak_energy_ratio"] > 0.45
            and f["strong_peak_count"] == 1 and f["harmonic_count"] <= 1):
        add("Continuous Tone", min(1.0, 0.4 + f["peak_energy_ratio"] * 0.6),
            f"Energy concentrated in a single {tone_freq:.0f} Hz peak "
            f"({f['peak_energy_ratio']*100:.0f}% of frame energy), no harmonic stack")
    if f["dtmf_pair"]:
        add("DTMF", 0.9,
            f"Simultaneous DTMF row+column pair {f['dtmf_pair'][0]:.0f}+{f['dtmf_pair'][1]:.0f} Hz")
    # CTCSS must not fire on voiced speech F0 (which also lives at
    # 80-250 Hz but always carries a harmonic stack above it).
    if (f["ctcss_db"] > 15.0 and f["rms"] > 0.01
            and _CTCSS_LO <= f["ctcss_freq"] <= _CTCSS_HI
            and (f["harmonic_count"] == 0 or f["ctcss_freq"] < 115.0)):
        add("CTCSS Subtone", min(1.0, f["ctcss_db"] / 30.0),
            f"Sub-audible tone at {f['ctcss_freq']:.1f} Hz above the local low-band floor")
    if f["pilot_db"] > 18.0:
        add("Pilot Tone 19k", min(1.0, f["pilot_db"] / 30.0),
            f"19 kHz stereo pilot present ({f['pilot_db']:.0f} dB above median)")
    if f["alert_hits"]:
        add("Alert Tone", 0.6 + 0.2 * (len(f["alert_hits"]) > 1),
            f"Standard alert frequency detected ({'+'.join(f'{a:.0f}' for a in f['alert_hits'])} Hz)")

    # --- Speech: mid centroid, syllabic energy, voiced harmonics but few.
    # Never fires on single-tone frames (energy concentrated in one peak). ---
    if 300 <= f["centroid"] <= 3400 and f["flatness"] < 0.5 and f["peak_energy_ratio"] < 0.5:
        add("Speech", 0.35, f"Spectral centroid {f['centroid']:.0f} Hz within speech band")
    if 0.05 <= f["zcr"] <= 0.28:
        add("Speech", 0.2, "Zero-crossing rate typical of voiced/unvoiced speech mix")
    if 2 <= f["harmonic_count"] <= 4 and 80 <= (peaks[0][0] if peaks else 0) <= 400:
        add("Speech", 0.25, "Low-pitched harmonic stack (voiced speech F0 range)")

    # --- Music: rich harmonic stack + wide spectrum. A bare tone must NOT
    # score here: music requires MULTIPLE harmonics/peaks and never a
    # single-peak energy concentration. ---
    if f["harmonic_count"] >= 3 and len(peaks) >= 4 and f["peak_energy_ratio"] < 0.75:
        add("Music", 0.55,
            f"Rich harmonic stack ({f['harmonic_count']} harmonics, {len(peaks)} tonal peaks)")
    if (f["centroid"] > 600 and 0.05 <= f["flatness"] <= 0.35 and len(peaks) >= 3
            and f["peak_energy_ratio"] < 0.5):
        add("Music", 0.25, "Wideband tonal-plus-percussive balance")

    # --- Whistle: narrow high-pitched tone; drift is confirmed at the
    # temporal layer (frame layer only flags the candidate) ---
    if (peaks and top_prom > 20.0 and 500 <= tone_freq <= 5000
            and f["harmonic_count"] == 0 and f["strong_peak_count"] == 1
            and f["peak_energy_ratio"] > 0.4):
        add("Whistle", 0.35, f"Narrow high-pitched tone at {tone_freq:.0f} Hz (whistle candidate)")

    # --- Digital/Data: high ZCR + high centroid, non-harmonic ---
    if f["zcr"] > 0.3 and f["centroid"] > 2000 and f["harmonic_count"] <= 1:
        add("Digital/Data", 0.5, "High zero-crossing rate + high centroid (keying-like)")
    if 0.2 <= f["flatness"] <= 0.5 and f["zcr"] > 0.25:
        add("Digital/Data", 0.2, "Noise-like but structured spectrum (modem-like)")

    return s, why


def _frame_state(scores: dict[str, float]) -> str:
    """Single dominant state per frame — used ONLY for the pattern layer
    (the multi-label scores are reported independently regardless)."""
    if scores["Silence"] > 0.5:
        return "silence"
    tone = max(scores["Continuous Tone"], scores["DTMF"], scores["Whistle"], scores["Alert Tone"])
    best = max(
        ("tone", tone), ("speech", scores["Speech"]), ("data", scores["Digital/Data"]),
        ("music", scores["Music"]), ("noise", scores["Noise"]),
        key=lambda kv: kv[1],
    )
    return best[0] if best[1] > 0.3 else "noise"


# ---------------------------------------------------------------------------
# Layer 2 + 3 — sliding-window aggregation and temporal pattern detection
# ---------------------------------------------------------------------------

class TemporalAggregator:
    """Keeps the last WINDOW_SECONDS of per-frame scores. Frames are
    analyzed exactly once; the window only re-aggregates stored numbers."""

    def __init__(self, window_s: float = WINDOW_SECONDS):
        self.window_s = window_s
        self._frames: deque = deque()  # (t, scores, why, state, tone_freq)

    def add(self, scores: dict, why: dict, state: str, tone_freq: float) -> None:
        now = time.monotonic()
        self._frames.append((now, scores, why, state, tone_freq))
        cutoff = now - self.window_s
        while self._frames and self._frames[0][0] < cutoff:
            self._frames.popleft()

    def report(self, frame_s: float) -> dict:
        if not self._frames:
            return {}
        n = len(self._frames)

        # ---- independent multi-label components (window means) ----
        components = []
        reasons: list[str] = []
        for label in LABELS:
            mean_score = float(np.mean([fr[1][label] for fr in self._frames]))
            present_frames = sum(1 for fr in self._frames if fr[1][label] >= PRESENT_THRESHOLD)
            if mean_score >= 0.05 or present_frames:
                components.append({
                    "label": label,
                    "confidence": round(mean_score, 2),
                    "seconds": round(present_frames * frame_s, 1),
                })
        components.sort(key=lambda c: -c["confidence"])

        # Representative reasons: newest frame evidence per reported label
        for c in components[:5]:
            for _, _, why, _, _ in reversed(self._frames):
                if c["label"] in why:
                    reasons.append(f"{c['label']}: {why[c['label']][0]}")
                    break

        # ---- activity timeline (seconds per state over the window) ----
        states = [fr[3] for fr in self._frames]
        timeline = {st: round(states.count(st) * frame_s, 1)
                    for st in ("speech", "music", "tone", "data", "noise", "silence")
                    if states.count(st)}

        # ---- temporal patterns ----
        patterns = self._detect_patterns(states, frame_s)

        # Whistle confirmation: tone frequency drifting over time
        tone_freqs = [fr[4] for fr in self._frames if fr[3] == "tone" and fr[4] > 0]
        if len(tone_freqs) >= 4 and float(np.std(tone_freqs)) > 80.0:
            patterns.append({"name": "Whistle (drifting tone)",
                             "detail": f"Tone frequency drifting ±{np.std(tone_freqs):.0f} Hz"})

        return {"components": components, "timeline": timeline,
                "patterns": patterns, "reasons": reasons, "frames_in_window": n}

    def _detect_patterns(self, states: list[str], frame_s: float) -> list[dict]:
        """Segment the state sequence and match alternation signatures."""
        segments: list[tuple[str, int]] = []
        for st in states:
            if segments and segments[-1][0] == st:
                segments[-1] = (st, segments[-1][1] + 1)
            else:
                segments.append((st, 1))

        patterns: list[dict] = []

        def _alternation(active: str) -> list[float] | None:
            """Durations (s) of `active` segments if they alternate with silence."""
            runs = [cnt * frame_s for st, cnt in segments if st == active]
            gaps = [cnt * frame_s for st, cnt in segments if st == "silence"]
            if len(runs) >= 2 and gaps:
                return runs
            return None

        tone_runs = _alternation("tone")
        if tone_runs:
            onsets, t = [], 0.0
            for st, cnt in segments:
                if st == "tone":
                    onsets.append(t)
                t += cnt * frame_s
            if len(onsets) >= 3:
                periods = np.diff(onsets)
                if float(np.std(periods)) < 0.3 * max(1e-6, float(np.mean(periods))):
                    # Bimodal short/long durations => Morse-like keying
                    runs = np.array(tone_runs)
                    # 1.8 not the ideal 3.0 dot:dash ratio — frame
                    # quantization (~170 ms) compresses measured durations.
                    if len(runs) >= 5 and runs.max() >= 1.8 * runs.min() and runs.min() < 0.4:
                        patterns.append({
                            "name": "Morse-like keying",
                            "detail": f"Short/long tone bursts (~{runs.min():.2f}/{runs.max():.2f} s)"})
                    else:
                        patterns.append({
                            "name": "Periodic Tone",
                            "detail": f"every {np.mean(periods):.1f} s, "
                                      f"~{np.mean(runs):.1f} s each, ×{len(onsets)}",
                            "period_s": round(float(np.mean(periods)), 2),
                            "tone_s": round(float(np.mean(tone_runs)), 2),
                            "count": len(onsets)})
            if not any(p["name"].startswith(("Periodic", "Morse")) for p in patterns):
                if len(tone_runs) == 1 or (tone_runs and max(tone_runs) < 0.5):
                    patterns.append({"name": "Beep",
                                     "detail": f"Short isolated tone burst (~{max(tone_runs):.2f} s)"})

        if _alternation("speech"):
            patterns.append({"name": "Push-To-Talk Voice",
                             "detail": "Speech segments alternating with silence"})
        if _alternation("data"):
            patterns.append({"name": "Burst Digital Signal",
                             "detail": "Data bursts alternating with silence"})
        return patterns


# ---------------------------------------------------------------------------
# Quality report (unchanged idea from V2, driven by window aggregates)
# ---------------------------------------------------------------------------

def _quality_report(components: list[dict], timeline: dict, frame_s: float) -> dict:
    noise_share = next((c["confidence"] for c in components if c["label"] == "Noise"), 0.0)
    window_total = sum(timeline.values()) or 1.0
    silence_ratio = timeline.get("silence", 0.0) / window_total
    choppy = 0.3 < silence_ratio < 0.9 and timeline.get("silence", 0.0) > 1.0
    clarity = max(0.0, min(1.0, (1.0 - noise_share) * (1.0 - 0.5 * silence_ratio)))

    noise_cause = None
    if noise_share > 0.25:
        if choppy:
            noise_cause = "Intermittent reception (signal dropping in and out)"
        else:
            noise_cause = "Weak signal or interference (persistent broadband noise)"
    return {"clarity": round(clarity, 2), "choppy": choppy,
            "noise_share": round(noise_share, 2), "noise_cause": noise_cause}


# ---------------------------------------------------------------------------
# Classifiers
# ---------------------------------------------------------------------------

class _RuleBasedClassifier:
    """V3: per-frame independent scoring + temporal aggregation window."""

    def __init__(self):
        self._agg = TemporalAggregator()
        self._frame_s = FRAME_SAMPLES / SAMPLE_RATE

    def classify(self, pcm_i16: np.ndarray) -> dict:
        x = pcm_i16.astype(np.float64) / 32768.0
        stereo_pilot = 0.0

        # Layer 1: analyze each new sub-frame exactly once
        for start in range(0, max(1, len(x) - FRAME_SAMPLES + 1), FRAME_SAMPLES):
            frame = x[start:start + FRAME_SAMPLES]
            if len(frame) < FRAME_SAMPLES // 2:
                break
            f = _frame_features(frame)
            scores, why = _frame_scores(f)
            state = _frame_state(scores)
            tone_freq = f["peaks"][0][0] if f["peaks"] else 0.0
            self._agg.add(scores, why, state, tone_freq)
            stereo_pilot = max(stereo_pilot, scores["Pilot Tone 19k"])

        # Layers 2+3: aggregate the window
        rep = self._agg.report(self._frame_s)
        if not rep:
            return {"label": "Silence", "confidence": 0.5,
                    "components": [{"label": "Silence", "confidence": 1.0, "seconds": 0.0}],
                    "timeline": {}, "patterns": [],
                    "quality": {"clarity": 0.0, "choppy": False, "noise_share": 1.0,
                                "noise_cause": None},
                    "stereo_pilot": 0.0, "reason": ["No audio yet"]}

        components = rep["components"]
        # Final label: strongest non-silence component unless everything
        # really is silence.
        non_silent = [c for c in components if c["label"] != "Silence"]
        top = (non_silent or components)[0]

        pattern_reasons = [f"Pattern: {p['name']} — {p['detail']}" for p in rep["patterns"]]

        return {
            "label": top["label"],
            "confidence": top["confidence"],
            "components": components,
            "timeline": rep["timeline"],
            "patterns": rep["patterns"],
            "quality": _quality_report(components, rep["timeline"], self._frame_s),
            "stereo_pilot": round(stereo_pilot, 2),
            "reason": rep["reasons"] + pattern_reasons,
        }


class _TFLiteClassifier:
    """Optional model path: the model's per-class probabilities are fed
    into the SAME temporal aggregator, so the timeline/pattern layers work
    identically. Uses tflite-runtime (never full TensorFlow); import
    failure falls back to the rule-based path in `build_classifier`."""

    def __init__(self, model_path: str):
        from tflite_runtime.interpreter import Interpreter  # optional dep

        self._interpreter = Interpreter(model_path=model_path)
        self._interpreter.allocate_tensors()
        self._input = self._interpreter.get_input_details()[0]
        self._output = self._interpreter.get_output_details()[0]
        self._rule = _RuleBasedClassifier()  # provides frames/window/patterns

    def classify(self, pcm_i16: np.ndarray) -> dict:
        # Rule-based V3 does the temporal work; the model refines the
        # coarse labels it knows about by averaging its probabilities in.
        result = self._rule.classify(pcm_i16)

        x = pcm_i16.astype(np.float32) / 32768.0
        target_len = self._input["shape"][-1]
        x = np.pad(x, (0, max(0, target_len - len(x))))[:target_len]
        self._interpreter.set_tensor(self._input["index"], x.reshape(self._input["shape"]))
        self._interpreter.invoke()
        probs = self._interpreter.get_tensor(self._output["index"]).flatten()

        by_label = {c["label"]: c for c in result["components"]}
        for i, p in enumerate(probs[:len(TFLITE_LABELS)]):
            label = TFLITE_LABELS[i]
            if label in by_label:
                merged = 0.5 * by_label[label]["confidence"] + 0.5 * float(p)
                by_label[label]["confidence"] = round(merged, 2)
        result["components"].sort(key=lambda c: -c["confidence"])
        result["reason"].append("TFLite model probabilities merged into window scores")
        return result


def build_classifier():
    if os.path.exists(AUDIO_MODEL_PATH):
        try:
            return _TFLiteClassifier(AUDIO_MODEL_PATH)
        except Exception as e:
            log.warning(f"AudioClassifier: TFLite model present but unusable ({e}); using rule-based classifier")
    return _RuleBasedClassifier()


# ---------------------------------------------------------------------------
# Worker process plumbing (unchanged)
# ---------------------------------------------------------------------------

def _process_main(in_queue: mp.Queue, out_queue: mp.Queue, stop_event):
    classifier = build_classifier()
    while not stop_event.is_set():
        try:
            job = in_queue.get(timeout=0.2)
        except queue.Empty:
            continue
        try:
            pcm = np.frombuffer(job["pcm_bytes"], dtype=np.int16)
            result = classifier.classify(pcm)
            result["type"] = "audio_classification"
            result["time"] = job.get("time")
            out_queue.put(result)
        except Exception as e:
            log.error(f"Audio classify error: {e}")


class AudioClassifierWorker:
    def __init__(self, on_classification: Callable[[dict], None]):
        self.in_queue: mp.Queue = mp.Queue(maxsize=1)
        self.out_queue: mp.Queue = mp.Queue()
        self._stop_event = mp.Event()
        self._process = mp.Process(
            target=_process_main,
            args=(self.in_queue, self.out_queue, self._stop_event),
            daemon=True,
        )
        self._on_classification = on_classification
        self._bridge_thread = threading.Thread(
            target=self._bridge_loop, name="audio-ai-bridge", daemon=True
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
                result = self.out_queue.get(timeout=0.2)
            except queue.Empty:
                continue
            self._on_classification(result)
