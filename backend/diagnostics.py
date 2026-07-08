#!/usr/bin/env python3
"""Standalone diagnostic tool for the FM receive chain (RF -> SDR config ->
IQ samples -> DSP -> audio).

This is intentionally separate from the live server: it opens the RTL-SDR
directly (same device, same settings as `sdr_reader.py`, but no threads,
no queues, no WebSocket) and measures real numbers at every stage so a fix
can be based on measurement instead of guesswork. Run it while the server
(signal_server.py) is stopped, since only one process can hold the dongle.

Usage:
    python3 diagnostics.py --freq 94.0
    python3 diagnostics.py --freq 94.0 --gains auto,20.7,40.2 --ppm 0 --demod WFM
    python3 diagnostics.py --freq 94.0 --out report.json
"""

import argparse
import json
import sys
import time

import numpy as np
from scipy import signal as dsp_signal

from dsp import get_demodulator
from dsp.filters import estimate_carrier_offset
from stage_profiler import StageProfiler

DEFAULT_GAINS = ["auto", 0, 8.7, 19.7, 28.0, 33.8, 40.2, 49.6]
CHANNEL_HALF_BW_HZ = 100_000.0  # matches WFMDemodulator.channel_bw_hz
OFFSET_SEARCH_HALF_BW_HZ = 300_000.0  # wider window: tuner LO error can be hundreds of kHz


def open_sdr(freq_hz: float, sample_rate: float, gain, ppm: int):
    from rtlsdr import RtlSdr

    sdr = RtlSdr()
    sdr.sample_rate = sample_rate
    sdr.center_freq = freq_hz
    if ppm:
        sdr.freq_correction = ppm
    try:
        sdr.gain = gain
    except Exception as e:
        print(f"  ! gain {gain!r} rejected ({e}), falling back to auto")
        sdr.gain = "auto"

    actual = {
        "requested": {"sample_rate": sample_rate, "center_freq": freq_hz, "gain": gain, "ppm": ppm},
        "actual": {
            "sample_rate": sdr.sample_rate,
            "center_freq": sdr.center_freq,
            "gain": sdr.gain,
            "freq_correction": sdr.freq_correction,
        },
    }
    return sdr, actual


def analyze_iq(iq: np.ndarray) -> dict:
    i, q = iq.real, iq.imag
    clip_thresh = 0.98
    clipping_pct = 100.0 * np.mean((np.abs(i) >= clip_thresh) | (np.abs(q) >= clip_thresh))
    dc_i, dc_q = float(np.mean(i)), float(np.mean(q))
    rms_i, rms_q = float(np.sqrt(np.mean(i ** 2))), float(np.sqrt(np.mean(q ** 2)))
    imbalance_db = 20 * np.log10(rms_i / rms_q) if rms_q > 0 else float("inf")
    corr = float(np.corrcoef(i, q)[0, 1]) if np.std(i) > 0 and np.std(q) > 0 else 0.0
    return {
        "clipping_pct": round(clipping_pct, 3),
        "dc_offset_i": round(dc_i, 5),
        "dc_offset_q": round(dc_q, 5),
        "rms_i": round(rms_i, 5),
        "rms_q": round(rms_q, 5),
        "iq_imbalance_db": round(imbalance_db, 2),
        "iq_correlation": round(corr, 4),
    }


def analyze_spectrum(iq: np.ndarray, sample_rate: float, freq_hz: float) -> dict:
    freqs, psd = dsp_signal.welch(iq, fs=sample_rate, nperseg=4096, return_onesided=False)
    freqs = np.fft.fftshift(freqs)
    psd_db = 10 * np.log10(np.fft.fftshift(psd) + 1e-20)

    noise_floor_db = float(np.percentile(psd_db, 20))
    peak_idx = int(np.argmax(psd_db))
    peak_db = float(psd_db[peak_idx])
    peak_freq_offset_hz = float(freqs[peak_idx])
    snr_db = peak_db - noise_floor_db

    in_channel = np.abs(freqs) <= CHANNEL_HALF_BW_HZ
    weights = np.clip(psd_db[in_channel] - noise_floor_db, 0, None)
    if weights.sum() > 0:
        centroid_offset_hz = float(np.sum(freqs[in_channel] * weights) / weights.sum())
    else:
        centroid_offset_hz = 0.0
    suggested_ppm = centroid_offset_hz / freq_hz * 1e6

    # wider search: the strongest carrier may sit hundreds of kHz from the
    # requested center (tuner LO error / quirk), well outside one channel
    wide_offset_hz = estimate_carrier_offset(iq, sample_rate, OFFSET_SEARCH_HALF_BW_HZ) or 0.0

    return {
        "noise_floor_db": round(noise_floor_db, 2),
        "peak_power_db": round(peak_db, 2),
        "wide_search_carrier_offset_hz": round(wide_offset_hz, 1),
        "snr_db": round(snr_db, 2),
        "peak_offset_from_center_hz": round(peak_freq_offset_hz, 1),
        "channel_centroid_offset_hz": round(centroid_offset_hz, 1),
        "suggested_ppm_correction": round(suggested_ppm, 2),
    }


def gain_sweep(freq_hz: float, sample_rate: float, ppm: int, candidate_gains: list) -> list:
    results = []
    for gain in candidate_gains:
        try:
            sdr, _ = open_sdr(freq_hz, sample_rate, gain, ppm)
            iq = sdr.read_samples(64 * 1024)
            sdr.close()
        except Exception as e:
            results.append({"gain": gain, "error": str(e)})
            continue

        power_dbfs = 10 * np.log10(np.mean(np.abs(iq) ** 2) + 1e-20)
        iq_stats = analyze_iq(iq)
        spec_stats = analyze_spectrum(iq, sample_rate, freq_hz)
        results.append({
            "gain": gain,
            "power_dbfs": round(float(power_dbfs), 2),
            "clipping_pct": iq_stats["clipping_pct"],
            "snr_db": spec_stats["snr_db"],
        })
        time.sleep(0.05)
    return results


def audio_diagnostics(sdr, sample_rate: float, demod_name: str, n_chunks: int = 40, chunk_size: int = 8192) -> dict:
    demod = get_demodulator(demod_name)
    demod._build_state(sample_rate)
    warmup = max(5, n_chunks // 4)

    # mirror AudioWorker's one-shot lock: estimate once up front from a real
    # capture, then hold it fixed for the rest of the run (no per-chunk re-lock)
    first_iq = sdr.read_samples(chunk_size)
    offset = estimate_carrier_offset(first_iq, sample_rate, OFFSET_SEARCH_HALF_BW_HZ) or 0.0
    demod.set_freq_offset(offset)
    print(f"  locked carrier offset: {offset:+.0f} Hz")

    discriminator_samples = []
    post_process_samples = []
    pcm_samples = []

    for chunk_idx in range(n_chunks):
        iq = first_iq if chunk_idx == 0 else sdr.read_samples(chunk_size)
        centered = demod._mixer.process(iq)
        filtered = demod._channel_filter.process(centered)
        decimated = filtered[:: demod._decim_factor]
        intermediate_rate = sample_rate / demod._decim_factor

        raw_demod = demod._demodulate(decimated, intermediate_rate)
        post = demod._post_process(raw_demod, intermediate_rate)
        resampled = demod._resampler.process(post)
        pcm = np.clip(resampled * 32767, -32768, 32767).astype(np.int16)

        if chunk_idx >= warmup:
            discriminator_samples.append(raw_demod)
            post_process_samples.append(post)
            pcm_samples.append(pcm)

    disc = np.concatenate(discriminator_samples) if discriminator_samples else np.array([0.0])
    post_all = np.concatenate(post_process_samples) if post_process_samples else np.array([0.0])
    pcm_all = np.concatenate(pcm_samples) if pcm_samples else np.array([0], dtype=np.int16)
    pcm_f = pcm_all.astype(np.float64) / 32767.0

    silence_thresh = 0.01
    clip_thresh = 32760

    return {
        "demodulator": demod.name,
        "discriminator_rms": round(float(np.sqrt(np.mean(disc ** 2))), 5),
        "discriminator_peak": round(float(np.max(np.abs(disc))), 5),
        "post_process_rms": round(float(np.sqrt(np.mean(post_all ** 2))), 5),
        "post_process_peak": round(float(np.max(np.abs(post_all))), 5),
        "audio_rms": round(float(np.sqrt(np.mean(pcm_f ** 2))), 5),
        "audio_peak": int(np.max(np.abs(pcm_all))),
        "clipping_pct": round(100.0 * np.mean(np.abs(pcm_all) >= clip_thresh), 3),
        "silence_pct": round(100.0 * np.mean(np.abs(pcm_f) < silence_thresh), 2),
    }


def chunk_size_sweep(
    freq_hz: float,
    sample_rate: float,
    demod_name: str = "WFM",
    gain=40.2,
    ppm: int = 0,
    sizes: tuple = (2048, 4096, 8192),
    duration_s: float = 3.0,
    queue_depth: int = 3,
) -> list:
    """Measures, not guesses: for each candidate IQ chunk size, runs the
    real demodulator on real captures for `duration_s` seconds and reports
    per-chunk DSP latency (Avg/Max/p99), CPU usage (DSP-time / chunk
    duration — over 1.0 means the chunk can't be processed in real time),
    and how many chunks a drop-oldest queue of depth `queue_depth` would
    have to drop if AudioWorker fell behind by that amount."""
    results = []
    for chunk_size in sizes:
        sdr, _ = open_sdr(freq_hz, sample_rate, gain, ppm)
        demod = get_demodulator(demod_name)
        demod._build_state(sample_rate)

        first_iq = sdr.read_samples(chunk_size)
        offset = estimate_carrier_offset(first_iq, sample_rate, OFFSET_SEARCH_HALF_BW_HZ) or 0.0
        demod.set_freq_offset(offset)

        chunk_duration_s = chunk_size / sample_rate
        profiler = StageProfiler(window=10_000)
        n_chunks = max(1, int(duration_s / chunk_duration_s))
        max_clip = 0
        total_samples = 0

        for i in range(n_chunks):
            iq = first_iq if i == 0 else sdr.read_samples(chunk_size)
            t0 = time.perf_counter()
            pcm = demod.process(iq, sample_rate)
            profiler.record("dsp", time.perf_counter() - t0)
            max_clip += int(np.sum(np.abs(pcm) >= 32760))
            total_samples += len(pcm)

        sdr.close()
        stats = profiler.stats("dsp") or {}
        cpu_ratio = stats.get("avg_ms", 0) / 1000.0 / chunk_duration_s if chunk_duration_s else 0.0
        # simulate how often a queue of this depth would have to drop a
        # chunk if processing fell behind by p99 instead of average
        behind_chunks = max(0, int((stats.get("p99_ms", 0) / 1000.0) // chunk_duration_s))
        simulated_drops = max(0, behind_chunks - queue_depth)

        results.append({
            "chunk_size": chunk_size,
            "chunk_duration_ms": round(chunk_duration_s * 1000, 3),
            "dsp_avg_ms": round(stats.get("avg_ms", 0), 4),
            "dsp_max_ms": round(stats.get("max_ms", 0), 4),
            "dsp_p99_ms": round(stats.get("p99_ms", 0), 4),
            "cpu_ratio": round(cpu_ratio, 3),  # >1.0 means it can't keep up in real time
            "simulated_drops_per_run": simulated_drops,
            "clipping_samples": max_clip,
            "total_audio_samples": total_samples,
            "n_chunks_tested": n_chunks,
        })
        print(f"  chunk_size={chunk_size}: {results[-1]}")
    return results


def print_report(report: dict) -> None:
    print("\n== RTL-SDR Config (requested vs actual) ==")
    print(json.dumps(report["sdr_config"], indent=2))

    print("\n== IQ Sample Health ==")
    print(json.dumps(report["iq_health"], indent=2))

    print("\n== Spectrum / Frequency Offset ==")
    print(json.dumps(report["spectrum"], indent=2))

    print("\n== Gain Sweep ==")
    for row in report["gain_sweep"]:
        print(f"  {row}")

    print("\n== Audio Pipeline Diagnostics ==")
    print(json.dumps(report["audio"], indent=2))


def main() -> int:
    parser = argparse.ArgumentParser(description="FM receive chain diagnostics")
    parser.add_argument("--freq", type=float, required=True, help="frequency in MHz")
    parser.add_argument("--sample-rate", type=float, default=2.4e6)
    parser.add_argument("--gain", default=40.2, help="gain for the main capture ('auto' or a dB value)")
    parser.add_argument("--gains", default=None, help="comma-separated gain list for the sweep")
    parser.add_argument("--ppm", type=int, default=0)
    parser.add_argument("--demod", default="WFM")
    parser.add_argument("--out", default=None, help="optional path to save the report as JSON")
    parser.add_argument(
        "--chunk-sweep", action="store_true",
        help="measure DSP latency/CPU/clipping across IQ chunk sizes 2048/4096/8192 and exit",
    )
    args = parser.parse_args()

    freq_hz = args.freq * 1e6
    gain = args.gain
    if isinstance(gain, str) and gain != "auto":
        gain = float(gain)

    if args.chunk_sweep:
        print(f"Running chunk-size sweep at {args.freq} MHz (2048/4096/8192)...")
        try:
            sweep = chunk_size_sweep(freq_hz, args.sample_rate, args.demod, gain, args.ppm)
        except Exception as e:
            print(f"Failed to run chunk-size sweep: {e}", file=sys.stderr)
            return 1
        print("\n== Chunk Size Sweep ==")
        print(json.dumps(sweep, indent=2))
        if args.out:
            with open(args.out, "w") as f:
                json.dump({"chunk_sweep": sweep}, f, indent=2)
            print(f"\nSaved report to {args.out}")
        return 0

    print(f"Opening RTL-SDR at {args.freq} MHz, sample_rate={args.sample_rate:.0f}, gain={gain}, ppm={args.ppm}...")
    try:
        sdr, sdr_config = open_sdr(freq_hz, args.sample_rate, gain, args.ppm)
    except Exception as e:
        print(f"Failed to open RTL-SDR: {e}", file=sys.stderr)
        return 1

    print("Capturing IQ block for spectrum/IQ-health analysis...")
    iq_block = sdr.read_samples(2 ** 18)
    iq_health = analyze_iq(iq_block)
    spectrum = analyze_spectrum(iq_block, args.sample_rate, freq_hz)

    if args.gains:
        candidate_gains = [g if g == "auto" else float(g) for g in args.gains.split(",")]
    else:
        candidate_gains = DEFAULT_GAINS
    print(f"Running gain sweep over {candidate_gains}...")
    sweep = gain_sweep(freq_hz, args.sample_rate, args.ppm, candidate_gains)

    print(f"Running audio pipeline diagnostics with demodulator={args.demod}...")
    audio = audio_diagnostics(sdr, args.sample_rate, args.demod)

    sdr.close()

    report = {
        "sdr_config": sdr_config,
        "iq_health": iq_health,
        "spectrum": spectrum,
        "gain_sweep": sweep,
        "audio": audio,
    }
    print_report(report)

    if args.out:
        with open(args.out, "w") as f:
            json.dump(report, f, indent=2)
        print(f"\nSaved report to {args.out}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
