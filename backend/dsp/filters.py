"""Stateful DSP building blocks shared by all demodulators.

Every stage here keeps its own delay-line/IIR state across calls so a
demodulator can feed it consecutive IQ chunks and get a continuous result
(no clicks/discontinuities at chunk boundaries), as long as `reset()` is
called whenever the upstream signal source changes (e.g. retuning).
"""

from __future__ import annotations

import numpy as np
from scipy import signal as dsp


def design_lowpass(cutoff_hz: float, sample_rate: float, numtaps: int = 63) -> np.ndarray:
    nyquist = sample_rate / 2
    norm_cutoff = min(cutoff_hz / nyquist, 0.999)
    return dsp.firwin(numtaps, norm_cutoff, window="hamming")


class StatefulFIR:
    """FIR filter (e.g. channel low-pass) with delay-line state preserved
    across chunks via `scipy.signal.lfilter`'s `zi`."""

    def __init__(self, taps: np.ndarray):
        self.taps = taps
        self._zi = np.zeros(len(taps) - 1)

    def process(self, x: np.ndarray) -> np.ndarray:
        y, self._zi = dsp.lfilter(self.taps, [1.0], x, zi=self._zi)
        return y

    def reset(self) -> None:
        self._zi = np.zeros(len(self.taps) - 1)


class StatefulResampler:
    """Integer up/down resampler with a persistent FIR delay line and
    decimation phase carried across chunks.

    Replaces calling `scipy.signal.resample_poly()` per chunk, which
    redesigns its filter and resets its internal state on every call —
    that adds both CPU overhead and an audible discontinuity/settling
    transient at every chunk boundary. A compact (63-tap) filter keeps
    group delay in the sub-millisecond range regardless of ratio.
    """

    def __init__(self, up: int, down: int, rate_in: float, numtaps: int = 63):
        self.up = max(1, up)
        self.down = max(1, down)
        rate_up = rate_in * self.up
        cutoff = min(rate_in, rate_up / self.down) / 2.0 * 0.9
        taps = design_lowpass(cutoff, rate_up, numtaps=numtaps)
        self._fir = StatefulFIR(taps * self.up)  # compensate zero-stuffing energy loss
        self._phase = 0

    def process(self, x: np.ndarray) -> np.ndarray:
        if self.up > 1:
            stuffed = np.zeros(len(x) * self.up, dtype=np.float64)
            stuffed[:: self.up] = x
        else:
            stuffed = x
        filtered = self._fir.process(stuffed)
        if self.down > 1:
            start = (-self._phase) % self.down
            out = filtered[start :: self.down]
            self._phase = (self._phase + len(filtered)) % self.down
            return out
        return filtered

    def reset(self) -> None:
        self._fir.reset()
        self._phase = 0


class NCOMixer:
    """Complex mixer (numerically-controlled oscillator) for frequency
    translation: shifts IQ by `-freq_hz` so a carrier that isn't sitting at
    DC (e.g. because the tuner's actual LO doesn't land exactly on the
    requested center frequency) gets re-centered before channel filtering.
    Phase is carried continuously across chunks, and across frequency
    changes via `set_frequency()`, so there's no click when the offset is
    adjusted.
    """

    def __init__(self, freq_hz: float, sample_rate: float):
        self.sample_rate = sample_rate
        self.freq_hz = freq_hz
        self._phase = 0.0

    def set_frequency(self, freq_hz: float) -> None:
        self.freq_hz = freq_hz

    def process(self, iq: np.ndarray) -> np.ndarray:
        if self.freq_hz == 0.0:
            return iq
        n = len(iq)
        phase_inc = -2 * np.pi * self.freq_hz / self.sample_rate
        phases = self._phase + phase_inc * np.arange(n)
        self._phase = (self._phase + phase_inc * n) % (2 * np.pi)
        return iq * np.exp(1j * phases)

    def reset(self) -> None:
        self._phase = 0.0


def estimate_carrier_offset(
    iq: np.ndarray, sample_rate: float, search_half_bw_hz: float = 300_000.0
) -> float | None:
    """Estimate how far the strongest in-band carrier sits from 0Hz (DC) by
    taking the power-weighted spectral centroid within a search window.
    Used to re-center a station that the tuner didn't land exactly on
    (LO error, tuner-specific quirks) before it reaches the channel filter,
    which otherwise silently filters out an off-center carrier.

    Returns None (not 0.0) when there isn't enough signal above the noise
    floor to measure confidently — 0.0 would be indistinguishable from "the
    carrier really is at DC" and could wrongly pull a tracking loop back
    toward zero during a fade.
    """
    nperseg = min(2048, len(iq))
    if nperseg < 16:
        return None
    freqs, psd = dsp.welch(iq, fs=sample_rate, nperseg=nperseg, return_onesided=False)
    freqs = np.fft.fftshift(freqs)
    psd = np.fft.fftshift(psd)
    psd_db = 10 * np.log10(psd + 1e-20)

    in_window = np.abs(freqs) <= search_half_bw_hz
    if not np.any(in_window):
        return None
    noise_floor_db = float(np.percentile(psd_db, 20))
    weights = np.clip(psd_db[in_window] - noise_floor_db, 0, None)
    if weights.sum() <= 0:
        return None
    return float(np.sum(freqs[in_window] * weights) / weights.sum())


class DCBlocker:
    """One-pole IIR DC removal: y[n] = x[n] - x[n-1] + a*y[n-1].

    Implemented via `scipy.signal.lfilter` (C loop, releases the GIL)
    instead of a per-sample Python `for` loop — same exact difference
    equation, but a Python-level loop here was a real, measurable source
    of audio-thread stalls (and GIL contention with the websocket/asyncio
    thread) on slower hardware, independent of chunk size or signal
    quality. State (`zi`) is carried across chunks exactly as before.
    """

    def __init__(self, pole: float = 0.995):
        self.pole = pole
        self._b = np.array([1.0, -1.0])
        self._a = np.array([1.0, -pole])
        self._zi = np.zeros(1)

    def process(self, x: np.ndarray) -> np.ndarray:
        y, self._zi = dsp.lfilter(self._b, self._a, x, zi=self._zi)
        return y

    def reset(self) -> None:
        self._zi = np.zeros(1)


class Deemphasis:
    """One-pole low-pass de-emphasis for broadcast FM (75us US / 50us EU).

    Same note as `DCBlocker`: vectorized via `lfilter` instead of a
    per-sample Python loop, identical math (y[n] = a*x[n] + (1-a)*y[n-1]).
    """

    def __init__(self, sample_rate: float, time_constant: float = 75e-6):
        self.alpha = 1.0 - np.exp(-1.0 / (sample_rate * time_constant))
        self._b = np.array([self.alpha])
        self._a = np.array([1.0, -(1.0 - self.alpha)])
        self._zi = np.zeros(1)

    def process(self, x: np.ndarray) -> np.ndarray:
        y, self._zi = dsp.lfilter(self._b, self._a, x, zi=self._zi)
        return y

    def reset(self) -> None:
        self._zi = np.zeros(1)


class Squelch:
    """Smoothed mute gate for FM audio, driven by an explicit open/closed
    decision from the caller — NOT inferred from per-chunk IQ power.

    A quadrature discriminator has no concept of "no signal": fed pure
    noise it still outputs a value every sample (atan2 of a near-random
    complex number), typically near full scale. Without a gate, a failed
    carrier lock produces loud static indistinguishable from real audio.

    Deriving "is there a real carrier" from the chunk's own IQ power
    doesn't work: a self-referential floor that tracks the signal level
    converges onto whatever level it's first fed (including a strong,
    perfectly stable real carrier) and then never sees enough contrast to
    open — there's no inherent within-channel swing between "noise" and
    "signal" to threshold against once you're already locked onto one
    station. The real decision (was a plausible carrier actually found?)
    is already made once per retune by the carrier-search/plausibility
    check in AudioWorker._hard_lock — this class only smooths *that*
    decision into a click-free gain ramp via `set_open()`/`next_gain()`.
    """

    def __init__(self, attack: float = 0.3, release: float = 0.05):
        self.attack = attack
        self.release = release
        self._open = False
        self._gain = 0.0

    def set_open(self, is_open: bool) -> None:
        self._open = is_open

    def next_gain(self) -> float:
        target = 1.0 if self._open else 0.0
        rate = self.attack if target > self._gain else self.release
        self._gain += rate * (target - self._gain)
        return self._gain

    def reset(self) -> None:
        self._open = False
        self._gain = 0.0


class SimpleAGC:
    """Tracks a moving target amplitude and applies a smoothed gain.

    The gain update is a genuine per-sample feedback loop (each sample's
    output depends on a gain that itself depends on every prior sample's
    decision), so unlike `DCBlocker`/`Deemphasis` it can't be swapped for
    a stateless vectorized filter without changing its attack/decay
    behavior. It's also not on the WFM path that's actually stuttering
    (only AM/SSB/CW use it), so it's left as-is rather than risk a
    regression in those modes for an unrelated perf change.
    """

    def __init__(self, target: float = 0.3, attack: float = 0.01, decay: float = 0.0005):
        self.target = target
        self.attack = attack
        self.decay = decay
        self._gain = 1.0

    def process(self, x: np.ndarray) -> np.ndarray:
        out = np.empty_like(x)
        gain = self._gain
        for i, xi in enumerate(x):
            out[i] = xi * gain
            level = abs(out[i])
            if level > self.target:
                gain *= 1.0 - self.attack
            else:
                gain *= 1.0 + self.decay
            gain = min(gain, 1e4)
        self._gain = gain
        return out

    def reset(self) -> None:
        self._gain = 1.0
