#!/usr/bin/env python3
"""
Signal Scope Backend - Raspberry Pi WebSocket Server

Architecture (real-time pipeline, see README in this directory for the
full writeup):

    SdrReader (thread)          -- blocking RTL-SDR reads, nothing else
        |-- audio_queue   (drop-oldest, depth N) --> AudioWorker (thread) --> LocalAudioSink
        |-- spectrum_slot (drop-oldest, depth 1) --> SpectrumWorker (thread)
                                                          |-- ai_in_queue (drop-oldest, depth 1) --> AiWorker (PROCESS)

    There is exactly one RTL-SDR handle, owned by SdrReader, open for as
    long as scanning is active. Audio and spectrum/AI both read off that
    same IQ stream, so spectrum/search and audio always run together —
    starting/stopping audio never touches the device.

    AudioWorker also taps its finished PCM (only while audio is actually
    enabled) into ai_audio_queue (drop-oldest, depth 1) which feeds
    AudioClassifierWorker (a second, separate PROCESS) and, only when a
    client explicitly asked for it, SttWorker.

    Every worker hands its finished output to this module via a plain
    callback, which bridges it onto the asyncio event loop
    (`loop.call_soon_threadsafe`). The event loop owns a single prioritized
    sender: AI detections are sent as soon as they arrive and are never
    dropped; spectrum/waveform are throttled and always reflect only the
    newest frame, since stale visuals aren't worth the bandwidth. Audio
    classification results and captures are lower priority still — see
    `_sender_loop`.

No stage can block another: the reader never waits on a queue (drop-oldest
everywhere upstream of it), and CPU-heavy AI work (RF anomaly retraining,
audio classification, speech-to-text) all run in separate processes/
threads so none of it can steal GIL time from the SDR/spectrum/audio/
network real-time path. Every AI-adjacent stage is a pure consumer: if it
falls behind, its queue just drops old data — it can never block or slow
down the pipeline feeding it.

Audio is *not* streamed to clients. AudioWorker (audio_worker.py) feeds IQ
into rtl_fm_pipe (rtl_fm_chain.py — a patched, otherwise-unmodified build
of rtl-sdr's own rtl_fm.c) for WFM/NFM/AM/USB/LSB, and into csdr
(csdr_chain.py) for CW (the one mode real rtl_fm has no -M for). No
demodulator is written for this project; PCM is written straight to
LocalAudioSink, which plays it on the Pi's own audio output via a local
`play` subprocess. Flutter only ever sends control commands (start_audio/
stop_audio/set_freq/set_demodulator/set_volume/mute/unmute) — no PCM
crosses the WebSocket.
"""

from __future__ import annotations

import asyncio
import logging
import os
import queue
import threading
import time
from datetime import datetime

import msgpack
import numpy as np
import websockets

from ai_worker import AiWorker
from audio_classifier_worker import AudioClassifierWorker
from audio_worker import AudioWorker
from capture_manager import CaptureManager
from captures_http import CapturesHttpServer
from droppable_queue import drain_queue, put_dropping_oldest
from led_controller import LedController
from local_audio import LocalAudioSink
from screen_controller import ScreenController
from sdr_reader import SdrReader
from spectrum_worker import SpectrumWorker
from stt_worker import SttWorker

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

HOST = "0.0.0.0"
PORT = 8765
# 2.4 MS/s (old value) sits near the FC0013's practical USB/ADC limit —
# confirmed via a side-by-side IQ capture (iq_compare.py) on this exact
# hardware/antenna/station: same carrier-lock accuracy, same DC-spike
# size, but measurably (and audibly) noisier than capturing at 1.02 MS/s —
# the rate rtl_fm itself uses on this dongle ("Sampling at 1020000 S/s" in
# its own log).
SAMPLE_RATE = 1_020_000.0
# Hard tuner limits for THIS dongle's FC0013: asking librtlsdr for a
# frequency the PLL can't lock (e.g. 949 MHz) doesn't just fail — it
# leaves the device in a bad state and the process segfaults. Reject
# out-of-range requests before they ever reach the hardware.
# Override via SIGNAL_SCOPE_TUNER_RANGE="14:948" (MHz) for other tuners.
_range = os.environ.get("SIGNAL_SCOPE_TUNER_RANGE", "14:948").split(":")
TUNER_MIN_MHZ, TUNER_MAX_MHZ = float(_range[0]), float(_range[1])
NUM_SAMPLES = 8 * 1024  # ~8.0ms/chunk at this rate — matches rtl_fm's own "Buffer size: 8.03ms"
AUDIO_QUEUE_DEPTH = 3  # ~25ms of look-ahead before the reader drops audio chunks
VIZ_SEND_INTERVAL = 1 / 12  # spectrum/waveform refresh rate sent to clients


class SdrServer:
    def __init__(self):
        self.led = LedController(gpio_pin=18)
        self.screen = ScreenController()
        self.clients: set = set()
        self.loop: asyncio.AbstractEventLoop | None = None

        # Cross-thread hand-off queues
        self.audio_in_queue: "queue.Queue" = queue.Queue(maxsize=AUDIO_QUEUE_DEPTH)
        self.spectrum_slot: "queue.Queue" = queue.Queue(maxsize=1)
        self.ai_audio_queue: "queue.Queue" = queue.Queue(maxsize=1)  # AudioWorker -> audio tap bridge

        # Outbound (asyncio-side) state
        self.signal_out: asyncio.Queue = asyncio.Queue()
        self.status_out: asyncio.Queue = asyncio.Queue()
        self.audio_ai_out: asyncio.Queue = asyncio.Queue()  # lowest priority: audio class. + captures
        self._latest_spectrum: dict | None = None
        self._latest_waveform: dict | None = None
        self._latest_audio_pcm: bytes | None = None
        self._wake_event: asyncio.Event | None = None

        _gain_override = os.environ.get("SIGNAL_SCOPE_GAIN")
        _gain = _gain_override if _gain_override == "auto" else (float(_gain_override) if _gain_override else 40.2)
        self.reader = SdrReader(
            SAMPLE_RATE, NUM_SAMPLES, self.audio_in_queue, self.spectrum_slot, gain=_gain
        )
        self.audio_sink = LocalAudioSink()
        self.audio_worker = AudioWorker(
            SAMPLE_RATE, self.audio_in_queue, self.audio_sink, ai_tap_queue=self.ai_audio_queue
        )
        self.ai_worker = AiWorker(self._on_detection)
        # SpectrumWorker feeds the AI process directly: its mp.Queue
        # (maxsize=1, drop-oldest via put_dropping_oldest) IS the ai_in
        # slot. There is no intermediate plain Queue — a previous refactor
        # left one in between with nothing consuming it, which silently
        # starved the RF analyzer of every frame.
        self.ai_in_queue = self.ai_worker.in_queue
        self.spectrum_worker = SpectrumWorker(
            self.spectrum_slot, self.ai_in_queue, self._on_spectrum, self._on_waveform
        )
        self.audio_classifier_worker = AudioClassifierWorker(self._on_audio_classification)
        self.capture_manager = CaptureManager()
        self.stt_worker = SttWorker(self._on_stt_text)
        self.captures_http = CapturesHttpServer(self.capture_manager.base_dir)

        self._audio_tap_stop = threading.Event()
        self._audio_tap_thread = threading.Thread(
            target=self._audio_tap_bridge_loop, name="audio-tap-bridge", daemon=True
        )

    # ---- worker callbacks (run on worker threads/process, must hop to the loop) ----

    def _on_spectrum(self, powers_db, center_freq: float, sample_rate: float) -> None:
        self.loop.call_soon_threadsafe(self._handle_spectrum, powers_db, center_freq, sample_rate)

    def _handle_spectrum(self, powers_db, center_freq: float, sample_rate: float) -> None:
        self._latest_spectrum = {
            "type": "spectrum",
            "powers": powers_db.tolist(),
            "center_freq": center_freq,
            "sample_rate": sample_rate,
            "time": datetime.utcnow().isoformat(),
        }
        # Live LCD dashboard — throttled internally to ~1 Hz, no-op mid-alert
        self.screen.show_dashboard(
            self._latest_spectrum["powers"], center_freq / 1e6, clients=len(self.clients)
        )

    def _on_waveform(self, samples: list) -> None:
        self.loop.call_soon_threadsafe(self._handle_waveform, samples)

    def _handle_waveform(self, samples: list) -> None:
        self._latest_waveform = {"type": "waveform", "samples": samples}

    def _on_detection(self, sig: dict) -> None:
        self.loop.call_soon_threadsafe(self._handle_detection, sig)

    def _handle_detection(self, sig: dict) -> None:
        self.signal_out.put_nowait(sig)  # never dropped
        self._wake_event.set()
        if sig.get("anomaly_score", 0) > 0.7:
            self.led.blink(times=3, interval=0.1)
            self.screen.show_alert(sig)

        # Capture consideration is cheap (dict/int bookkeeping) and only
        # does real work (PNG/WAV/JSON write) on the rare frames that
        # clear every threshold in CaptureManager.consider — never on the
        # SDR/spectrum/audio real-time path, only here on the already-
        # off-thread detection callback.
        powers = None
        spectrum_sample_rate = None
        if self._latest_spectrum is not None:
            powers = np.array(self._latest_spectrum["powers"])
            spectrum_sample_rate = self._latest_spectrum["sample_rate"]
        capture = self.capture_manager.consider(
            sig, powers_db=powers, sample_rate=spectrum_sample_rate, recent_pcm_bytes=self._latest_audio_pcm
        )
        if capture:
            self.audio_ai_out.put_nowait({"type": "capture", **capture})
            self._wake_event.set()

    # ---- audio-tap-derived AI (classifier / STT / capture audio) ----

    def _audio_tap_bridge_loop(self) -> None:
        """Bridges AudioWorker's plain queue.Queue tap to the audio
        classifier's multiprocessing.Queue and to STT — runs on its own
        thread so neither ever touches the audio playback thread."""
        while not self._audio_tap_stop.is_set():
            try:
                job = self.ai_audio_queue.get(timeout=0.2)
            except queue.Empty:
                continue
            self._latest_audio_pcm = job["pcm_bytes"]
            put_dropping_oldest(self.audio_classifier_worker.in_queue, job)
            if self.stt_worker.active:
                self.stt_worker.feed(job["pcm_bytes"])

    def _on_audio_classification(self, result: dict) -> None:
        self.loop.call_soon_threadsafe(self._handle_audio_classification, result)

    def _handle_audio_classification(self, result: dict) -> None:
        self.audio_ai_out.put_nowait(result)
        self._wake_event.set()

    def _on_stt_text(self, text: str) -> None:
        self.loop.call_soon_threadsafe(self._handle_stt_text, text)

    def _handle_stt_text(self, text: str) -> None:
        self.audio_ai_out.put_nowait({"type": "stt_text", "text": text})
        self._wake_event.set()

    # ---- networking ----

    async def broadcast(self, data: dict) -> None:
        if not self.clients:
            return
        packed = msgpack.packb(data, use_bin_type=True)
        await asyncio.gather(
            *(ws.send(packed) for ws in self.clients),
            return_exceptions=True,
        )

    async def _drain(self, q: asyncio.Queue) -> None:
        while not q.empty():
            await self.broadcast(q.get_nowait())

    async def _sender_loop(self) -> None:
        """Single prioritized sender: detections go out as soon as they
        exist; spectrum/waveform are throttled and always the latest.
        Audio classification/capture/STT events are lowest priority —
        drained last, after the real-time-relevant traffic above."""
        last_viz = 0.0
        while True:
            await self._drain(self.signal_out)
            await self._drain(self.status_out)

            now = time.monotonic()
            if now - last_viz >= VIZ_SEND_INTERVAL:
                last_viz = now
                if self._latest_spectrum is not None:
                    await self.broadcast(self._latest_spectrum)
                    self._latest_spectrum = None
                if self._latest_waveform is not None:
                    await self.broadcast(self._latest_waveform)
                    self._latest_waveform = None

            await self._drain(self.audio_ai_out)

            try:
                await asyncio.wait_for(self._wake_event.wait(), timeout=VIZ_SEND_INTERVAL)
            except asyncio.TimeoutError:
                pass
            self._wake_event.clear()

    async def handle_client(self, websocket) -> None:
        self.clients.add(websocket)
        log.info(f"Client connected: {websocket.remote_address}")
        await websocket.send(msgpack.packb({
            "type": "status",
            "message": "Connected to Signal Scope Pi",
        }, use_bin_type=True))

        client_id = str(websocket.remote_address)
        try:
            async for raw in websocket:
                try:
                    cmd = msgpack.unpackb(raw, raw=False) if isinstance(raw, bytes) else None
                    if cmd:
                        await self._handle_command(cmd, client_id)
                except (msgpack.exceptions.UnpackException, ValueError):
                    pass
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            self.clients.discard(websocket)
            log.info(f"Client disconnected: {websocket.remote_address}")

    @staticmethod
    def _range_error(freq_mhz: float) -> str:
        return (f"Rejected {freq_mhz:.1f} MHz — tuner supports "
                f"{TUNER_MIN_MHZ:.0f}-{TUNER_MAX_MHZ:.0f} MHz only")

    async def _status(self, message: str) -> None:
        self.status_out.put_nowait({"type": "status", "message": message})
        self._wake_event.set()

    async def _handle_command(self, cmd: dict, client: str = "?") -> None:
        command = cmd.get("command")
        log.info(f"Command from {client}: {cmd}")

        if command == "start_scan":
            freq = cmd.get("center_freq_mhz", 100.0)
            freq_hz = freq * 1e6
            if not self._retune(freq_hz, cmd.get("demodulator")):
                await self._status(self._range_error(freq))
                return
            self.reader.scanning.set()
            self.led.start_beacon()
            await self._status(f"Scanning {freq:.1f} MHz")

        elif command == "stop_scan":
            self.reader.scanning.clear()
            self.led.stop_beacon()
            await self._status("Scan stopped")

        elif command == "set_freq":
            freq = cmd.get("freq_mhz", 100.0)
            freq_hz = freq * 1e6
            if not self._retune(freq_hz, cmd.get("demodulator")):
                await self._status(self._range_error(freq))
                return
            await self._status(f"Frequency: {freq:.1f} MHz")

        elif command == "set_demodulator":
            name = cmd.get("demodulator", "WFM")
            self.audio_worker.set_demodulator(name)
            await self._status(f"Demodulator: {name}")

        elif command == "start_audio":
            # Audio rides the same IQ stream as spectrum (one RTL-SDR
            # handle), so this just retunes (if asked) and enables the
            # demod worker — it never touches the device itself.
            freq = cmd.get("freq_mhz")
            if freq is not None:
                if not self._retune(freq * 1e6, cmd.get("demodulator")):
                    await self._status(self._range_error(freq))
                    return
            elif cmd.get("demodulator"):
                self.audio_worker.set_demodulator(cmd["demodulator"])
            self.reader.scanning.set()
            self.audio_sink.start()
            self.audio_worker.enable()
            self.led.start_beacon()
            await self._status(f"Audio playing: {self.reader.center_freq / 1e6:.1f} MHz")

        elif command == "stop_audio":
            self.audio_worker.disable()
            self.audio_sink.stop()
            self.led.stop_beacon()
            await self._status("Audio stopped")

        elif command == "set_volume":
            volume = float(cmd.get("volume", 1.0))
            self.audio_worker.set_volume(volume)
            await self._status(f"Volume: {volume:.2f}")

        elif command == "mute":
            self.audio_worker.mute()
            await self._status("Muted")

        elif command == "unmute":
            self.audio_worker.unmute()
            await self._status("Unmuted")

        elif command == "start_stt":
            # Explicit, on-demand only — never runs on its own. Feeds off
            # the same audio tap as the classifier, so it only works
            # while audio is actually enabled.
            ok = self.stt_worker.start()
            await self._status("Speech-to-text started" if ok else "Speech-to-text unavailable (no model installed)")

        elif command == "stop_stt":
            self.stt_worker.stop()
            await self._status("Speech-to-text stopped")

    def _retune(self, freq_hz: float, demodulator: str | None) -> bool:
        """Switch frequency/demodulator for both spectrum and audio at
        once — they share the same tuner and the same IQ stream. A
        duplicate set_freq/start_scan command for the same frequency
        (e.g. resent by the client) is a no-op. Returns False when the
        frequency is outside the tuner's lockable range (request is
        dropped entirely — the hardware is never touched)."""
        if freq_hz <= 0:
            log.error(f"_retune: rejecting nonsensical freq_hz={freq_hz}")
            return False
        if not (TUNER_MIN_MHZ * 1e6 <= freq_hz <= TUNER_MAX_MHZ * 1e6):
            log.error(
                f"_retune: {freq_hz/1e6:.3f} MHz outside tuner range "
                f"{TUNER_MIN_MHZ:.0f}-{TUNER_MAX_MHZ:.0f} MHz — rejected before touching the device"
            )
            return False
        freq_changed = abs(freq_hz - self.reader.center_freq) >= 1.0
        log.info(
            f"_retune(freq={freq_hz/1e6:.4f}MHz, demodulator={demodulator!r}): "
            f"current_center={self.reader.center_freq/1e6:.4f}MHz freq_changed={freq_changed}"
        )

        if freq_changed:
            self.reader.set_center_freq(freq_hz)
            self.spectrum_worker.center_freq = freq_hz

        if demodulator:
            self.audio_worker.set_demodulator(demodulator)  # already restarts the chain
        elif freq_changed:
            # EXPERIMENT (see conversation): restart the demod chain on a
            # pure frequency change too, so fm_demod's pre_r/pre_j and
            # deemph_filter's static avg never carry the old station's
            # state into the new one. A/B-measured to cause a real,
            # measurable transient (~tens of ms) right after a retune.
            self.audio_worker.restart_chain()

        if not freq_changed:
            log.info("_retune: no-op (frequency unchanged)")
            return True

        drain_queue(self.audio_in_queue)
        drain_queue(self.spectrum_slot)
        drain_queue(self.ai_in_queue)
        return True

    async def run(self) -> None:
        self.loop = asyncio.get_running_loop()
        self._wake_event = asyncio.Event()

        self.screen.show_boot()
        self.reader.start()
        self.audio_worker.start()
        self.spectrum_worker.start()
        self.ai_worker.start()
        self.audio_classifier_worker.start()
        self._audio_tap_thread.start()
        self.captures_http.start()

        asyncio.create_task(self._sender_loop())
        log.info(f"Starting WebSocket server on {HOST}:{PORT}")
        async with websockets.serve(self.handle_client, HOST, PORT):
            log.info("Server ready. Waiting for connections...")
            await asyncio.Future()

    def cleanup(self) -> None:
        self.reader.stop()
        self.audio_worker.stop()
        self.audio_sink.stop()
        self.spectrum_worker.stop()
        self.ai_worker.stop()
        self.audio_classifier_worker.stop()
        self.stt_worker.stop()
        self._audio_tap_stop.set()
        self.captures_http.stop()
        self.led.off()
        self.led.cleanup()


if __name__ == "__main__":
    server = SdrServer()
    try:
        asyncio.run(server.run())
    except KeyboardInterrupt:
        server.cleanup()
        log.info("Server stopped")
