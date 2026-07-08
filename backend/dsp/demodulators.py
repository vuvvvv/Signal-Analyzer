"""Generic, extensible demodulator pipeline.

Every mode shares the same skeleton (channel filter -> decimate -> DC
removal -> AGC -> mode-specific demod -> mode-specific audio shaping ->
resample to the output audio rate), but each mode owns its own filter
widths, decimation ratio and post-processing so adding a new mode never
requires touching another mode or the worker/threading code around it.
"""

from __future__ import annotations

import time
from typing import Callable

import numpy as np

from dsp.filters import (
    DCBlocker,
    Deemphasis,
    NCOMixer,
    SimpleAGC,
    Squelch,
    StatefulFIR,
    StatefulResampler,
    design_lowpass,
)


class Demodulator:
    """Base class. Subclasses set channel_bw_hz / decim_target_rate and
    implement `_demodulate(iq) -> np.ndarray` (real-valued, at the
    intermediate decimated rate)."""

    name = "base"
    channel_bw_hz = 100_000.0
    decim_target_rate = 240_000.0
    audio_rate = 48_000
    IS_FM = False  # discriminator-DC-bias fine lock only applies to FM modes
    # Post-demod audio bandlimit, applied at the intermediate rate right
    # after the demodulator and before resampling to audio_rate. None = no
    # extra audio lowpass (modes whose channel filter already bandlimits
    # tightly enough). FM modes MUST set this: a quadrature discriminator
    # run at a high intermediate rate outputs the FULL FM baseband — not
    # just the 0-15kHz program audio, but the 19kHz stereo pilot, the
    # ~38kHz L-R stereo subcarrier, 57kHz RDS, and FM's triangular (rising
    # with frequency) noise. Without bandlimiting to ~15kHz first, the
    # 400k->48k resampler folds all of that down into the audio band
    # (38k->10k, 57k->9k, pilot stays at 19k) as constant noise/whine on
    # top of the otherwise-correct voice. This is exactly the missing stage
    # that makes our output noisy where rtl_fm (which bandlimits its mono
    # output) is clean.
    audio_cutoff_hz: float | None = None

    def __init__(self):
        self._sample_rate: float | None = None
        self._mixer: NCOMixer | None = None
        self._channel_filter: StatefulFIR | None = None
        self._decim_factor: int = 1
        self._decim_phase: int = 0  # carries the decimation start index across chunks
        self._audio_lpf: StatefulFIR | None = None
        self._resampler: StatefulResampler | None = None
        self._dc_blocker = DCBlocker()
        self._prev_sample = None  # IQ phase continuity for discriminator-style modes
        self._squelch: Squelch | None = Squelch() if self.IS_FM else None
        self._build_state(None)

    def _build_state(self, sample_rate: float | None) -> None:
        self._sample_rate = sample_rate
        if sample_rate is None:
            self._mixer = None
            self._channel_filter = None
            self._decim_factor = 1
            self._audio_lpf = None
            self._resampler = None
            return
        prev_offset = self._mixer.freq_hz if self._mixer is not None else 0.0
        self._mixer = NCOMixer(prev_offset, sample_rate)
        taps = design_lowpass(self.channel_bw_hz, sample_rate)
        self._channel_filter = StatefulFIR(taps)
        self._decim_factor = max(1, int(sample_rate // self.decim_target_rate))
        self._decim_phase = 0
        intermediate_rate = sample_rate / self._decim_factor
        if self.audio_cutoff_hz is not None:
            self._audio_lpf = StatefulFIR(design_lowpass(self.audio_cutoff_hz, intermediate_rate))
        else:
            self._audio_lpf = None
        up, down = self._resample_ratio(intermediate_rate)
        self._resampler = StatefulResampler(up, down, intermediate_rate)

    def set_squelch_open(self, is_open: bool) -> None:
        """Called once per hard-relock by AudioWorker with the outcome of
        its own carrier-search plausibility check — the only place that
        actually knows whether a real carrier was found. No-op for modes
        without a squelch (AM/SSB/CW already have their own AGC)."""
        if self._squelch is not None:
            self._squelch.set_open(is_open)

    def set_freq_offset(self, offset_hz: float) -> None:
        """Re-center a carrier that isn't sitting at DC (tuner LO error or
        quirk) before it reaches the channel filter, which would otherwise
        silently attenuate/drop an off-center signal."""
        if self._mixer is not None:
            self._mixer.set_frequency(offset_hz)

    def reset(self) -> None:
        """Clear all filter/phase state. Must be called whenever the IQ
        source changes meaning (e.g. retuning) to avoid bleeding the
        previous signal's state into the new one. Does NOT reset the
        frequency-offset correction — that's re-estimated by the caller
        right after a retune, not assumed to go back to zero."""
        if self._mixer is not None:
            self._mixer.reset()
        if self._channel_filter is not None:
            self._channel_filter.reset()
        if self._audio_lpf is not None:
            self._audio_lpf.reset()
        if self._resampler is not None:
            self._resampler.reset()
        self._dc_blocker.reset()
        self._prev_sample = None
        self._decim_phase = 0
        if self._squelch is not None:
            self._squelch.reset()

    def process(
        self,
        iq: np.ndarray,
        sample_rate: float,
        profile: dict | None = None,
        signal_stats: dict | None = None,
    ) -> np.ndarray:
        if self._sample_rate != sample_rate:
            self._build_state(sample_rate)

        def rms(x: np.ndarray) -> float:
            return float(np.sqrt(np.mean(np.abs(x) ** 2))) if len(x) else 0.0

        t = time.perf_counter
        t0 = t()
        centered = self._mixer.process(iq)
        t1 = t()
        filtered = self._channel_filter.process(centered)
        t2 = t()
        # `filtered` is continuous sample-for-sample across chunks (lfilter's
        # zi carries the filter state), but chunk length isn't a multiple of
        # decim_factor — slicing from index 0 every call (instead of tracking
        # where the previous chunk's stride left off) reintroduces a phase
        # jump at every chunk boundary, corrupting the discriminator with a
        # periodic glitch independent of signal strength or frequency.
        start = (-self._decim_phase) % self._decim_factor
        decimated = filtered[start :: self._decim_factor]
        self._decim_phase = (self._decim_phase + len(filtered)) % self._decim_factor
        intermediate_rate = sample_rate / self._decim_factor
        t3 = t()

        # Stay in float for every stage (demod, de-emphasis/DC/AGC, resample)
        # and only quantize to int16 once, right at the end — quantizing
        # earlier and re-processing in int16 doubles rounding noise.
        demod = self._demodulate(decimated, intermediate_rate)
        t4 = t()
        if self._squelch is not None:
            demod = demod * self._squelch.next_gain()
        # Bandlimit to the program audio (~15kHz for WFM) BEFORE resampling,
        # to strip the 19/38/57kHz stereo-pilot/subcarrier/RDS and the
        # high-frequency FM noise that would otherwise alias into the audio
        # band at the 400k->48k downsample. See `audio_cutoff_hz`.
        if self._audio_lpf is not None:
            demod = self._audio_lpf.process(demod)
        audio = self._post_process(demod, intermediate_rate)
        t5 = t()
        audio = self._resampler.process(audio)
        t6 = t()
        pcm = np.clip(audio * 32767, -32768, 32767).astype(np.int16)
        t7 = t()

        if profile is not None:
            profile["mixer"] = profile.get("mixer", 0.0) + (t1 - t0)
            profile["channel_filter"] = profile.get("channel_filter", 0.0) + (t2 - t1)
            profile["decimation"] = profile.get("decimation", 0.0) + (t3 - t2)
            profile["demodulator"] = profile.get("demodulator", 0.0) + (t4 - t3)
            profile["audio_processing"] = profile.get("audio_processing", 0.0) + (t5 - t4)
            profile["resampler"] = profile.get("resampler", 0.0) + (t6 - t5)
            profile["quantize"] = profile.get("quantize", 0.0) + (t7 - t6)

        if signal_stats is not None:
            # Where does the signal go bad? Read top-to-bottom: clean IQ
            # but garbage after "channel_filter" => carrier lock/mixer is
            # wrong. Clean "channel_filter" but garbage after "demodulator"
            # => the discriminator/demod algorithm itself. Etc.
            signal_stats["rms_iq_in"] = rms(iq)
            signal_stats["rms_post_mixer"] = rms(centered)
            signal_stats["rms_post_channel_filter"] = rms(decimated)
            signal_stats["rms_post_demodulator"] = rms(demod)
            signal_stats["rms_post_audio_processing"] = rms(audio)
            signal_stats["rms_audio_out"] = float(np.sqrt(np.mean((pcm.astype(np.float64) / 32767.0) ** 2)))

        return pcm

    def estimate_fine_offset(self, iq: np.ndarray, sample_rate: float) -> float | None:
        """Refine a coarse carrier-offset estimate. Default: not supported
        (only meaningful for modes that produce a direct frequency-error
        readout, like FM's discriminator — see `_DiscriminatorMixin`)."""
        return None

    def _resample_ratio(self, intermediate_rate: float) -> tuple[int, int]:
        g = np.gcd(int(self.audio_rate), int(intermediate_rate))
        return int(self.audio_rate // g), int(intermediate_rate // g)

    def _demodulate(self, iq: np.ndarray, intermediate_rate: float) -> np.ndarray:
        raise NotImplementedError

    def _post_process(self, audio: np.ndarray, intermediate_rate: float) -> np.ndarray:
        return audio


class _DiscriminatorMixin:
    """Quadrature FM discriminator, shared by WFM and NFM."""

    IS_FM = True

    def _demodulate(self, iq: np.ndarray, intermediate_rate: float) -> np.ndarray:
        if len(iq) == 0:
            return iq.real.astype(np.float64)
        if self._prev_sample is None:
            self._prev_sample = iq[0]
        chain = np.concatenate(([self._prev_sample], iq))
        self._prev_sample = iq[-1]
        angle = np.angle(chain[1:] * np.conj(chain[:-1]))
        return angle / np.pi

    def estimate_fine_offset(self, iq: np.ndarray, sample_rate: float) -> float | None:
        """A spectral-centroid coarse estimate gets close, but for FM the
        discriminator itself gives a direct, much more accurate read on
        any *residual* frequency error: an off-center carrier shows up as
        a constant DC bias in the discriminator output (the modulating
        audio is AC and averages to ~0; only a true carrier offset doesn't).
        Run on a throwaway filter/mixer copy so it never disturbs the real
        pipeline's continuous state."""
        if self._mixer is None or self._channel_filter is None:
            return None
        temp_mixer = NCOMixer(self._mixer.freq_hz, sample_rate)
        temp_filter = StatefulFIR(self._channel_filter.taps)
        centered = temp_mixer.process(iq)
        filtered = temp_filter.process(centered)
        decimated = filtered[:: self._decim_factor]
        if len(decimated) < 2:
            return None
        intermediate_rate = sample_rate / self._decim_factor
        angle = np.angle(decimated[1:] * np.conj(decimated[:-1]))
        mean_norm = float(np.mean(angle)) / np.pi  # normalized to +-1 over +-Nyquist
        return mean_norm * (intermediate_rate / 2.0)

    def _post_process(self, audio: np.ndarray, intermediate_rate: float) -> np.ndarray:
        # The discriminator's raw output is "instantaneous frequency", which
        # is exactly the modulating audio (AC, averages to ~0) PLUS a
        # constant bias from any residual carrier offset (used deliberately
        # by estimate_fine_offset/AFC above — see their docstrings). That
        # bias is never zero in practice (a few Hz of residual error after
        # locking is normal) and a one-pole de-emphasis lowpass passes DC
        # straight through unchanged, so it reached the final PCM as a
        # constant offset — confirmed via a 15s raw-PCM capture: the DC bin
        # measured ~10dB louder than any other content in the spectrum, with
        # the next-loudest energy clustered at implausibly low audio
        # frequencies (1-50Hz) rather than normal voice/music content.
        # Removing it here (post-discriminator, pre-de-emphasis) fixes that
        # without touching the bias the lock/AFC logic deliberately reads.
        return self._dc_blocker.process(audio)


class WFMDemodulator(_DiscriminatorMixin, Demodulator):
    """Broadcast FM (WFM): ~200kHz channel, quadrature discriminator,
    75us de-emphasis."""

    name = "WFM"
    channel_bw_hz = 100_000.0
    # 240kHz (old value) put the post-decimation Nyquist at 120kHz, where
    # the 63-tap channel filter only achieves -12.5dB attenuation —
    # adjacent-channel/out-of-band energy aliased almost unattenuated into
    # the decimated band and corrupted the discriminator (measured via
    # scipy.signal.freqz). 400kHz puts Nyquist at 200kHz, where the same
    # filter measures -54dB — a proper anti-alias margin.
    decim_target_rate = 400_000.0
    # Mono broadcast program audio is 0-15kHz. Everything above (19kHz pilot,
    # 38kHz stereo subcarrier, 57kHz RDS, triangular FM noise) must be cut
    # here or it folds into the audio band at the resample. See base class.
    audio_cutoff_hz = 15_000.0

    def __init__(self):
        super().__init__()
        self._deemphasis: Deemphasis | None = None
        # WFM had no level control at all (unlike AM/SSB's SimpleAGC) —
        # final loudness was whatever the discriminator's raw deviation
        # happened to produce, which tracks RF gain/antenna conditions
        # directly. A weak/under-driven station (e.g. a tuner gain that's
        # adequate to avoid clipping but low for this particular signal)
        # then plays back near-silent, with the noise floor underneath it
        # unchanged — sounding like "noise drowning out a faint voice"
        # even once the signal itself is clean (no DC bias, no glitches).
        #
        # target is much lower than AM/SSB's 0.3: those are envelope/voice
        # signals with a modest peak-to-average ratio, but FM program
        # audio (music especially) has a much higher crest factor — driving
        # its *average* up to 0.3 pushed transient peaks past 1.0, i.e.
        # straight into hard digital clipping (confirmed via a captured
        # debug WAV: peak measured >1.0 after this stage). That clipping
        # itself is a harsh, audible distortion — worse than the quiet
        # original, and indistinguishable by ear from the static this was
        # meant to fix. 0.12 keeps real-world FM peaks under headroom.
        self._agc = SimpleAGC(target=0.12)

    def _build_state(self, sample_rate: float | None) -> None:
        super()._build_state(sample_rate)
        if sample_rate is None:
            self._deemphasis = None
            return
        intermediate_rate = sample_rate / self._decim_factor
        self._deemphasis = Deemphasis(intermediate_rate, time_constant=75e-6)

    def reset(self) -> None:
        super().reset()
        if self._deemphasis is not None:
            self._deemphasis.reset()
        self._agc.reset()

    def _post_process(self, audio: np.ndarray, intermediate_rate: float) -> np.ndarray:
        # DC removal (see _DiscriminatorMixin._post_process) must happen
        # before de-emphasis, not after — de-emphasis is itself a lowpass
        # and would otherwise pass a remaining bias straight through.
        audio = super()._post_process(audio, intermediate_rate)
        # de-emphasis runs here, in float, at the (pre-resample) intermediate
        # rate — before the single final int16 quantization in process().
        audio = self._deemphasis.process(audio)
        # AGC last, after de-emphasis: it should normalize the final
        # listening level, not fight the de-emphasis filter's own gain
        # shaping. Skip it entirely while the squelch is (mostly) closed —
        # SimpleAGC's decay constantly ramps gain up whenever level is
        # below target, with no upper bound tied to "is there real signal
        # here"; left running on squelch-muted near-silence during a long
        # dead patch it would climb toward its 1e4 cap and then slam the
        # very next real chunk into hard clipping the instant the squelch
        # reopens. `reset()` keeps it at a sane unity gain instead.
        if self._squelch is not None and self._squelch._gain < 0.5:
            self._agc.reset()
            return audio
        return self._agc.process(audio)


class NFMDemodulator(_DiscriminatorMixin, Demodulator):
    """Narrowband FM (e.g. analog voice radios): ~12.5kHz channel,
    quadrature discriminator, no de-emphasis."""

    name = "NFM"
    channel_bw_hz = 6_250.0
    # Same anti-aliasing fix as WFM (see its comment): 24kHz put Nyquist at
    # 12kHz, where the channel filter is nowhere near settled (this mode's
    # narrow cutoff doesn't help — the 63-tap filter's absolute transition
    # width in Hz is roughly fixed by sample_rate/numtaps, not by cutoff).
    # 200kHz puts Nyquist at 100kHz, measured -58dB attenuation there.
    decim_target_rate = 200_000.0
    # NFM voice is ~3kHz; bandlimit before resampling so the discriminator's
    # high-frequency noise (run here at the 200kHz intermediate rate) doesn't
    # fold into the audio band. See base class `audio_cutoff_hz`.
    audio_cutoff_hz = 3_500.0


class AMDemodulator(Demodulator):
    """Amplitude modulation: envelope detector + DC removal + AGC."""

    name = "AM"
    channel_bw_hz = 5_000.0
    # Same anti-aliasing fix as WFM/NFM: 200kHz puts Nyquist at 100kHz,
    # measured -59dB attenuation there (was -way under at the old 12kHz).
    decim_target_rate = 200_000.0

    def __init__(self):
        super().__init__()
        self._agc = SimpleAGC(target=0.3)

    def reset(self) -> None:
        super().reset()
        self._agc.reset()

    def _demodulate(self, iq: np.ndarray, intermediate_rate: float) -> np.ndarray:
        envelope = np.abs(iq)
        envelope = self._dc_blocker.process(envelope)
        return self._agc.process(envelope)


class SSBDemodulator(Demodulator):
    """Single-sideband (USB/LSB): complex bandpass to isolate one
    sideband, then take the real part (phasing/filter method)."""

    channel_bw_hz = 3_000.0
    # Same anti-aliasing fix as WFM/NFM/AM: 160kHz puts Nyquist at 80kHz,
    # measured -61dB attenuation there (was -way under at the old 6kHz).
    decim_target_rate = 160_000.0
    voice_low_hz = 300.0
    voice_high_hz = 3_000.0

    def __init__(self, mode: str = "usb"):
        super().__init__()
        if mode not in ("usb", "lsb"):
            raise ValueError(f"unknown SSB mode: {mode}")
        self.mode = mode
        self.name = "USB" if mode == "usb" else "LSB"
        self._agc = SimpleAGC(target=0.3)
        self._sideband_filter: StatefulFIR | None = None

    def _build_state(self, sample_rate: float | None) -> None:
        super()._build_state(sample_rate)
        if sample_rate is None:
            self._sideband_filter = None
            return
        intermediate_rate = sample_rate / self._decim_factor
        taps = design_lowpass(self.voice_high_hz, intermediate_rate)
        center = (self.voice_low_hz + self.voice_high_hz) / 2.0
        sign = 1.0 if self.mode == "usb" else -1.0
        n = np.arange(len(taps))
        shift = np.exp(1j * 2 * np.pi * sign * center * n / intermediate_rate)
        self._sideband_filter = StatefulFIR(taps * shift)

    def reset(self) -> None:
        super().reset()
        self._agc.reset()
        if self._sideband_filter is not None:
            self._sideband_filter.reset()

    def _demodulate(self, iq: np.ndarray, intermediate_rate: float) -> np.ndarray:
        sideband = self._sideband_filter.process(iq)
        audio = np.real(sideband)
        audio = self._dc_blocker.process(audio)
        return self._agc.process(audio)


class CWDemodulator(SSBDemodulator):
    """Morse/CW: narrow bandpass centered on the usual ~600Hz pitch,
    reusing the SSB phasing method."""

    name = "CW"
    channel_bw_hz = 500.0
    # Same anti-aliasing fix as WFM/NFM/AM/SSB: 160kHz puts Nyquist at
    # 80kHz, measured -58dB attenuation there (was -way under at the old
    # 4kHz, off by more than an order of magnitude).
    decim_target_rate = 160_000.0
    voice_low_hz = 400.0
    voice_high_hz = 900.0

    def __init__(self):
        super().__init__(mode="usb")
        self.name = "CW"


DEMODULATORS: dict[str, Callable[[], Demodulator]] = {
    "WFM": WFMDemodulator,
    "NFM": NFMDemodulator,
    "AM": AMDemodulator,
    "USB": lambda: SSBDemodulator(mode="usb"),
    "LSB": lambda: SSBDemodulator(mode="lsb"),
    "CW": CWDemodulator,
}


def get_demodulator(name: str) -> Demodulator:
    try:
        return DEMODULATORS[name.upper()]()
    except KeyError:
        raise ValueError(f"unknown demodulator: {name!r}, available: {list(DEMODULATORS)}")
