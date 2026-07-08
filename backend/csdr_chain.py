"""Reference DSP demodulation via csdr (https://github.com/jketterl/csdr) —
the same DSP engine used by OpenWebRX and other mature browser-SDR
projects. No demodulator math is implemented in this codebase: every stage
below is a documented csdr subcommand, verified against the exact build
installed by install.sh (`csdr <subcommand> --help`, jketterl/csdr's
modular CLI — `csdr fmdemod`, `csdr deemphasis`, etc., not the older
monolithic `fmdemod_quadri_cf`-style names from the original libcsdr).
This file only wires already-captured IQ samples into the right csdr
pipeline per mode and reads PCM back out.

csdr is a pure stream processor — it never opens an SDR device. We feed it
IQ samples already captured by SdrReader's single pyrtlsdr handle (as raw
interleaved complex64 = float32 I,Q, the "complex" format csdr's `fmdemod`/
`amdemod`/`shift`/`bandpass`/`realpart` stages expect) via stdin, and read
s16 PCM back from stdout. This is what lets audio demodulation run
continuously alongside spectrum capture without ever touching the RTL-SDR
device a second time.

Pipelines:
  WFM: fmdemod -> fractionaldecimator -> deemphasis --wfm -> agc -> convert
  NFM: fmdemod -> fractionaldecimator -> deemphasis --nfm -> agc -> convert
  AM:  amdemod -> fractionaldecimator -> dcblock -> agc -> convert
  USB/LSB/CW: shift -> bandpass -> realpart -> fractionaldecimator -> agc -> convert
    (csdr's own documented SSB recipe: shift to baseband, bandpass-isolate
    one sideband, take the real part; USB uses a positive passband, LSB
    the mirrored negative one, CW a narrow band around the conventional
    ~600Hz pitch)
"""

from __future__ import annotations

import logging
import subprocess
import threading
from typing import Optional

log = logging.getLogger(__name__)

IQ_SAMPLE_RATE = 1_020_000
AUDIO_SAMPLE_RATE = 48_000
# 1,020,000 / 48,000 = 21.25 exactly — csdr's `fractionaldecimator` takes
# this directly as a floating-point ratio (Lagrange-interpolated), so no
# integer up/down pair or approximation is needed.
DECIMATION_RATE = IQ_SAMPLE_RATE / AUDIO_SAMPLE_RATE

WFM_DEEMPHASIS_TAU_S = 75e-6  # US broadcast FM standard (use 50e-6 for Europe)
VOICE_LOW_HZ = 300.0
VOICE_HIGH_HZ = 3000.0
CW_LOW_HZ = 400.0
CW_HIGH_HZ = 900.0

SUPPORTED_MODES = {"WFM", "NFM", "AM", "USB", "LSB", "CW"}

# csdr decimates/converts in one go via this shared tail: anti-alias
# prefilter (-p) before the fractional decimation, then convert float -> s16.
_DECIMATE = f"csdr fractionaldecimator {DECIMATION_RATE} -f float -p"
_TO_PCM = "csdr convert -i float -o s16"


def _norm(freq_hz: float) -> str:
    """csdr's `bandpass --low/--high` take cutoffs as a fraction of the
    sample rate (cycles/sample), not Hz."""
    return f"{freq_hz / IQ_SAMPLE_RATE:.8f}"


def _pipeline_for(demodulator: str) -> list[str]:
    name = demodulator.upper()
    if name not in SUPPORTED_MODES:
        raise ValueError(f"unknown demodulator: {demodulator!r}, available: {sorted(SUPPORTED_MODES)}")

    if name == "WFM":
        return [
            "csdr fmdemod",
            _DECIMATE,
            f"csdr deemphasis {AUDIO_SAMPLE_RATE} {WFM_DEEMPHASIS_TAU_S:.8f} --wfm",
            "csdr agc",
            _TO_PCM,
        ]
    if name == "NFM":
        return [
            "csdr fmdemod",
            _DECIMATE,
            f"csdr deemphasis {AUDIO_SAMPLE_RATE} --nfm",
            "csdr agc",
            _TO_PCM,
        ]
    if name == "AM":
        return [
            "csdr amdemod",
            _DECIMATE,
            "csdr dcblock",
            "csdr agc",
            _TO_PCM,
        ]

    # USB / LSB / CW: csdr's documented phasing-method SSB recipe.
    if name == "USB":
        low, high = VOICE_LOW_HZ, VOICE_HIGH_HZ
    elif name == "LSB":
        low, high = -VOICE_HIGH_HZ, -VOICE_LOW_HZ
    else:  # CW
        low, high = CW_LOW_HZ, CW_HIGH_HZ
    return [
        "csdr shift 0",
        f"csdr bandpass 0.05 --low {_norm(low)} --high {_norm(high)}",
        "csdr realpart",
        _DECIMATE,
        "csdr agc",
        _TO_PCM,
    ]


class CsdrChain:
    """Owns a persistent csdr subprocess pipeline for one demodulator
    mode. `feed()` writes raw IQ bytes to the first stage's stdin; the
    caller reads finished PCM16 from `.stdout` (the last stage's)."""

    def __init__(self) -> None:
        self.demodulator: Optional[str] = None
        self._procs: list[subprocess.Popen] = []

    @property
    def stdout(self):
        return self._procs[-1].stdout if self._procs else None

    @property
    def running(self) -> bool:
        return bool(self._procs)

    def start(self, demodulator: str) -> None:
        self.stop()
        stages = _pipeline_for(demodulator)
        procs: list[subprocess.Popen] = []
        prev_stdout = None
        try:
            for stage in stages:
                args = stage.split()
                proc = subprocess.Popen(
                    args,
                    stdin=prev_stdout if prev_stdout is not None else subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
                if prev_stdout is not None:
                    prev_stdout.close()  # upstream proc gets SIGPIPE if this stage exits
                prev_stdout = proc.stdout
                procs.append(proc)
                # Every stage's stderr is logged with the exact command that
                # produced it — a stage that exits immediately (bad args,
                # missing module name, etc.) is otherwise silent and shows
                # up only as a generic "broken pipe" two stages downstream.
                threading.Thread(
                    target=self._log_stderr, args=(stage, proc), daemon=True
                ).start()
        except FileNotFoundError as e:
            log.error(f"CsdrChain: missing 'csdr' binary ({e}). Build/install csdr (see install.sh).")
            for p in procs:
                p.kill()
            return
        self._procs = procs
        self.demodulator = demodulator.upper()
        log.info(f"CsdrChain: started {self.demodulator} pipeline: " + " | ".join(stages))

    @staticmethod
    def _log_stderr(stage: str, proc: subprocess.Popen) -> None:
        if proc.stderr is None:
            return
        for line in iter(proc.stderr.readline, b""):
            text = line.decode(errors="replace").rstrip()
            if text:
                log.error(f"CsdrChain: [{stage}] {text}")

    def stop(self) -> None:
        for proc in self._procs:
            try:
                if proc.stdin:
                    proc.stdin.close()
                proc.terminate()
            except Exception:
                pass
        for proc in self._procs:
            try:
                proc.wait(timeout=2.0)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=2.0)
        self._procs = []
        self.demodulator = None

    def feed(self, iq_bytes: bytes) -> None:
        if not self._procs:
            return
        try:
            self._procs[0].stdin.write(iq_bytes)
        except (BrokenPipeError, OSError) as e:
            log.error(f"CsdrChain: feed failed, stopping pipeline ({e})")
            self.stop()
