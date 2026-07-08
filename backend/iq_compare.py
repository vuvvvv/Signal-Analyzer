#!/usr/bin/env python3
"""Side-by-side IQ diagnostic, round 2.

Round 1 tested offset/edge tuning (rtl_fm avoids the RTL2832U's center-freq
DC spike by tuning off-frequency and shifting back in software). Result:
offset tuning made things WORSE on this hardware, not better — ruling out
the DC spike as the dominant cause (it's real, measured +17dB, but isn't
what's making the audio noisy). cmp_onfreq.wav (on-freq, minimal generic
chain, no carrier lock/AGC/squelch at all) still had "music with noise" —
not the clean result the rtl_fm CLI gave on the same antenna/station.

The other thing rtl_fm's own log revealed and round 1 didn't test:

    Sampling at 1020000 S/s.   (rtl_fm)   vs   2,400,000 S/s   (our app)

2.4 MS/s is close to the RTL2832U/FC0013's practical USB throughput limit;
cheap tuners are commonly noisier and less linear at their top sample rate
than at a more conservative ~1 MS/s. This script isolates SAMPLE RATE as
the only variable (both cases on-frequency, both with a real coarse carrier
center so neither is unfairly handicapped like round 1's offset case was):

  A) 2,400,000 S/s  (what our app uses)
  B) 1,020,000 S/s  (what rtl_fm uses)

Run on the Pi:   python3 iq_compare.py --freq 98.0
Outputs cmp_2400k.wav and cmp_1020k.wav for direct listening.
"""
from __future__ import annotations

import argparse
import wave

import numpy as np
from scipy import signal as dsp
from rtlsdr import RtlSdr

SECONDS = 2.0  # kept short to stay safe on a ~900MB-RAM Pi
CHUNK = 16 * 1024  # libusb chokes on huge single read_samples() calls


def capture(fs: float, center_hz: float, n: int) -> np.ndarray:
    sdr = RtlSdr()
    sdr.sample_rate = fs
    sdr.center_freq = center_hz
    sdr.gain = "auto"  # match rtl_fm's "Tuner gain set to automatic"
    sdr.read_samples(CHUNK)  # flush stale buffer after retune
    chunks = []
    got = 0
    while got < n:
        c = sdr.read_samples(CHUNK)
        chunks.append(c)
        got += len(c)
    sdr.close()
    return np.concatenate(chunks)[:n].astype(np.complex64)


def estimate_coarse_offset(iq: np.ndarray, fs: float, search_hz: float = 150_000.0) -> float:
    """Power-weighted spectral centroid within ±search_hz of center — same
    idea as our real app's carrier lock, kept here so neither test case is
    handicapped by an uncentered carrier like round 1's offset case was."""
    nperseg = min(4096, len(iq))
    f, P = dsp.welch(iq, fs=fs, nperseg=nperseg, return_onesided=False)
    f = np.fft.fftshift(f)
    P = np.fft.fftshift(P)
    mask = np.abs(f) <= search_hz
    Pdb = 10 * np.log10(P + 1e-20)
    floor = np.percentile(Pdb, 20)
    w = np.clip(Pdb[mask] - floor, 0, None)
    if w.sum() <= 0:
        return 0.0
    return float(np.sum(f[mask] * w) / w.sum())


def dc_spike_db(iq: np.ndarray, fs: float) -> float:
    f, P = dsp.welch(iq, fs=fs, nperseg=8192, return_onesided=False)
    f = np.fft.fftshift(f)
    P = np.fft.fftshift(P)
    dc = P[np.abs(f) < 2000].max()
    floor = np.median(P[(np.abs(f) > 20000) & (np.abs(f) < min(80000, fs / 2 - 1000))])
    return 10 * np.log10(dc / floor)


def fm_demod_chain(iq: np.ndarray, fs: float, channel_bw: float = 100_000.0,
                    decim_target: float = 200_000.0) -> np.ndarray:
    """Generic WFM chain: coarse-center -> channel LPF -> decimate ->
    atan2 discriminator -> 15k audio LPF -> 75us de-emphasis -> resample."""
    offset = estimate_coarse_offset(iq, fs)
    t = np.arange(len(iq)) / fs
    centered = iq * np.exp(-1j * 2 * np.pi * offset * t)

    taps = dsp.firwin(127, channel_bw / (fs / 2), window="hamming")
    filt = dsp.lfilter(taps, [1.0], centered)
    decim = max(1, int(fs // decim_target))
    x = filt[::decim]
    ir = fs / decim

    d = np.angle(x[1:] * np.conj(x[:-1]))
    d = dsp.lfilter(dsp.firwin(127, 15000 / (ir / 2)), [1.0], d)  # audio LPF
    a = 1 - np.exp(-1 / (ir * 75e-6))
    d = dsp.lfilter([a], [1, -(1 - a)], d)  # de-emphasis

    g = np.gcd(48000, int(ir))
    audio = dsp.resample_poly(d, 48000 // g, int(ir) // g)
    return audio, offset


def inband_snr(audio: np.ndarray) -> float:
    f, P = dsp.welch(audio, fs=48000, nperseg=4096)
    voice = P[(f > 300) & (f < 3500)].sum()
    hiss = P[(f > 5000) & (f < 20000)].sum()
    return 10 * np.log10(voice / hiss)


def save_wav(path: str, audio: np.ndarray) -> None:
    a = audio / (np.max(np.abs(audio)) + 1e-9) * 0.9
    pcm = np.clip(a * 32767, -32768, 32767).astype(np.int16)
    w = wave.open(path, "wb")
    w.setnchannels(1)
    w.setsampwidth(2)
    w.setframerate(48000)
    w.writeframes(pcm.tobytes())
    w.close()


def process_one(fs: float, center_hz: float, n: int, wav_path: str):
    iq = capture(fs, center_hz, n)
    spike = dc_spike_db(iq, fs)
    audio, offset = fm_demod_chain(iq, fs)
    del iq
    save_wav(wav_path, audio)
    snr = inband_snr(audio)
    del audio
    return spike, snr, offset


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--freq", type=float, default=98.0, help="station MHz")
    args = ap.parse_args()
    station = args.freq * 1e6

    print(f"== Capturing {args.freq} MHz at two sample rates (on-freq both times) ==")
    print("A) 2,400,000 S/s (what our app uses)")
    spike_a, snr_a, off_a = process_one(2_400_000.0, station, int(2_400_000.0 * SECONDS), "cmp_2400k.wav")

    print("B) 1,020,000 S/s (what rtl_fm uses)")
    spike_b, snr_b, off_b = process_one(1_020_000.0, station, int(1_020_000.0 * SECONDS), "cmp_1020k.wav")

    print()
    print("Carrier offset found by coarse search (sanity check — should be small, a few kHz):")
    print(f"  A 2400k: {off_a:+.0f} Hz")
    print(f"  B 1020k: {off_b:+.0f} Hz")
    print()
    print("DC spike at band center:")
    print(f"  A 2400k: {spike_a:+5.1f} dB above floor")
    print(f"  B 1020k: {spike_b:+5.1f} dB above floor")
    print()
    print("Recovered-audio in-band SNR (voice 0.3-3.5k vs hiss 5-20k):")
    print(f"  A 2400k (cmp_2400k.wav): {snr_a:5.1f} dB")
    print(f"  B 1020k (cmp_1020k.wav): {snr_b:5.1f} dB")
    print()
    print("Listen to both WAVs. If cmp_1020k.wav is clearly cleaner, the fix is")
    print("lowering SAMPLE_RATE in signal_server.py (and decim_target_rate scaling")
    print("in dsp/demodulators.py), not anything about offset tuning.")


if __name__ == "__main__":
    main()
