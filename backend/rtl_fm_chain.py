"""WFM/NFM/AM/USB/LSB demodulation via rtl_fm_pipe — a patched build of
rtl-sdr's own rtl_fm.c (see vendor/rtl_fm_pipe.c) that reads raw IQ bytes
from stdin instead of opening a USB device. Every DSP function in that
binary is byte-for-byte the same code the real `rtl_fm` CLI runs; this
module only feeds it bytes and reads PCM back.

`-s` is rtl_fm's *only* channel-bandwidth/decimation control — it has no
separate "bandwidth" flag. rtl_fm derives its boxcar decimation factor as
`downsample = (1_000_000 // rate_in) + 1` and then low-passes/decimates
the incoming IQ by that factor before demodulating, so `-s` must be set
per-mode, the same way a real `rtl_fm` user would pick it — a wide value
for WFM, much narrower for NFM/AM/SSB — not a single value reused for
every mode. (An earlier version of this file passed the same ~1.02MS/s
true capture rate for every mode; for WFM that happens to make rtl_fm's
own downsample formula come out to exactly 6, matching this project's
SAMPLE_RATE constant by design — see signal_server.py's comment on
SAMPLE_RATE. For every other mode it made downsample=1, i.e. *no* channel
filtering at all, which is the bug this fixes.)

SAMPLE_RATE_HZ below (1,020,000) is the *true* IQ byte rate SdrReader
always captures at, fixed by spectrum's needs — never changes per mode.
MODE_MAP's `-s` value is the per-mode rate_in passed to rtl_fm_pipe;
rtl_fm's own downsample formula turns that into the actual boxcar
decimation factor applied to the true 1.02MS/s stream. For WFM (170k)
this divides evenly (1,020,000 / 170,000 = 6, matching rtl_fm's own
computed downsample exactly — zero approximation, same as the reference
command). For the narrower modes the chosen `-s` doesn't divide it as
cleanly, so the post-decimation rate is within ~1% of the nominal value
— the same kind of rounding rtl_fm has always had for any `-s` that
doesn't evenly divide the real device's true capture rate, not something
introduced here.

IMPORTANT constraint verified directly against rtl_fm.c: its final
resample stage, `low_pass_real()`, only decimates — its own source
comment says so ("add support for upsampling?"), and feeding it a target
rate (`-r`) *higher* than the working rate (`-s`) divides by zero in its
`fast/slow` integer division, silently producing empty output. Since
LocalAudioSink always plays at 48kHz, every mode's `-s` here is therefore
kept >= 48000 (verified by actually running each mode's pipeline against
synthetic IQ before picking these numbers, not just assumed). The boxcar
decimation factor itself (computed from `-s`) is still what gives each
mode its distinct channel width — WFM's is 6, NFM/AM/USB/LSB's is 21 —
exactly the mechanism real rtl_fm always uses for -M fm vs -M wbfm.

CW has no -M mode in rtl_fm at all (no built-in narrow-CW demod), so it's
not handled here — see csdr_chain.py, used only for that one mode.
"""

from __future__ import annotations

import logging
import os
import subprocess
import threading
from typing import Optional

log = logging.getLogger(__name__)

_HERE = os.path.dirname(os.path.abspath(__file__))
RTL_FM_PIPE_BIN = os.path.join(_HERE, "vendor", "rtl_fm_pipe")

SAMPLE_RATE_HZ = 1_020_000  # true IQ capture rate fed in, fixed by spectrum
AUDIO_SAMPLE_RATE = 48_000

# rtl_fm's own -M mode names, paired with the `-s` (rate_in) value for
# that mode:
#   WFM (broadcast FM): 170k, matches the tested reference command exactly
#     (divides the true 1.02MS/s capture evenly: downsample=6).
#   NFM/AM/USB/LSB: 48k — the narrowest rate_in that still keeps `-s` >=
#     `-r` (48k) as required (see module docstring); this gives a boxcar
#     downsample of 21 against the true 1.02MS/s stream, a properly
#     narrower channel than WFM's 6, which is what actually distinguishes
#     these modes' bandwidth in rtl_fm's own design.
MODE_MAP = {
    "WFM": ("wbfm", 170_000),
    "NFM": ("fm", 48_000),
    "AM": ("am", 48_000),
    "USB": ("usb", 48_000),
    "LSB": ("lsb", 48_000),
}


class RtlFmChain:
    """Owns a persistent rtl_fm_pipe subprocess for one mode. `feed()`
    writes raw uint8 interleaved I,Q bytes (exactly pyrtlsdr's
    read_bytes() format, unconverted) to its stdin; `.stdout` is its
    PCM16 output."""

    def __init__(self) -> None:
        self.demodulator: Optional[str] = None
        self._proc: Optional[subprocess.Popen] = None

    @property
    def stdout(self):
        return self._proc.stdout if self._proc else None

    @property
    def running(self) -> bool:
        return self._proc is not None

    def start(self, demodulator: str) -> None:
        self.stop()
        name = demodulator.upper()
        entry = MODE_MAP.get(name)
        if entry is None:
            raise ValueError(f"RtlFmChain does not handle {demodulator!r}")
        mode, rate_in = entry

        args = [
            RTL_FM_PIPE_BIN,
            "-M", mode,
            "-s", str(rate_in),
            "-r", str(AUDIO_SAMPLE_RATE),
        ]
        # NOTE: `-E dc` (rtl_fm's built-in dc_block_filter) was tried here
        # and reverted — it audibly degraded WFM quality on real broadcast
        # audio (its per-buffer mean isn't a true high-pass; it can read
        # legitimate low-frequency program content as "DC" and distort it).
        # Do not re-add without verifying on real audio first, not just
        # synthetic test tones.
        try:
            self._proc = subprocess.Popen(
                args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
        except FileNotFoundError as e:
            log.error(
                f"RtlFmChain: missing '{RTL_FM_PIPE_BIN}' ({e}). "
                f"Build it: see vendor/rtl_fm_pipe.c / install.sh."
            )
            self._proc = None
            return
        self.demodulator = name
        threading.Thread(target=self._log_stderr, args=(self._proc,), daemon=True).start()
        log.info(f"RtlFmChain: started {name} (rtl_fm -M {mode} -s {rate_in} -r {AUDIO_SAMPLE_RATE}, true input {SAMPLE_RATE_HZ}Hz)")

    @staticmethod
    def _log_stderr(proc: subprocess.Popen) -> None:
        if proc.stderr is None:
            return
        for line in iter(proc.stderr.readline, b""):
            text = line.decode(errors="replace").rstrip()
            if text:
                log.info(f"RtlFmChain: [rtl_fm_pipe] {text}")

    def stop(self) -> None:
        if self._proc is None:
            return
        try:
            if self._proc.stdin:
                self._proc.stdin.close()
            self._proc.terminate()
            self._proc.wait(timeout=2.0)
        except Exception:
            try:
                self._proc.kill()
                self._proc.wait(timeout=2.0)
            except Exception:
                pass
        self._proc = None
        self.demodulator = None

    def feed(self, raw_iq_bytes: bytes) -> None:
        if self._proc is None or self._proc.stdin is None:
            return
        try:
            self._proc.stdin.write(raw_iq_bytes)
        except (BrokenPipeError, OSError) as e:
            log.error(f"RtlFmChain: feed failed, stopping ({e})")
            self.stop()
