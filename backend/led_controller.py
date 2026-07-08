"""LED Controller - GPIO18 (Pin 12)

Aircraft-beacon style: brightness ramps up and down smoothly using PWM,
like a plane's beacon light. If software PWM is unavailable (some Pi 5 /
rpi-lgpio setups), falls back to plain on/off blinking so the LED always
works. Pulsing runs on a background thread so callers never block.
"""

import math
import threading
import time
import logging

log = logging.getLogger(__name__)

try:
    import RPi.GPIO as GPIO
    _HAS_GPIO = True
except ImportError:
    _HAS_GPIO = False
    log.warning("RPi.GPIO not available (not on Pi?)")


class LedController:
    PWM_FREQ = 200        # Hz, flicker-free
    FADE_STEPS = 80       # brightness steps per fade in/out (more = smoother)

    def __init__(self, gpio_pin: int = 18):
        self.pin = gpio_pin
        self._pwm = None
        self._lock = threading.Lock()
        self._pulses_pending = 0
        self._beacon = False
        self._pulse_interval = 0.5
        self._stop = threading.Event()
        self._wake = threading.Event()
        if _HAS_GPIO:
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(self.pin, GPIO.OUT, initial=GPIO.LOW)
            try:
                self._pwm = GPIO.PWM(self.pin, self.PWM_FREQ)
                self._pwm.start(0)
                # Verify PWM actually accepts duty changes; some backends
                # only fail here, not at construction.
                self._pwm.ChangeDutyCycle(0)
                log.info("LED: software PWM active (smooth beacon mode)")
            except Exception as e:
                log.warning(f"LED: PWM unavailable ({e}), using on/off fallback")
                self._pwm = None
        self._thread = threading.Thread(target=self._run, name="led-pulse", daemon=True)
        self._thread.start()
        # Startup self-test: one visible pulse confirms wiring/config
        self.blink(times=1, interval=0.3)

    def _set_brightness(self, percent: float):
        if not _HAS_GPIO:
            return
        try:
            if self._pwm:
                self._pwm.ChangeDutyCycle(max(0.0, min(100.0, percent)))
            else:
                GPIO.output(self.pin, GPIO.HIGH if percent >= 50 else GPIO.LOW)
        except Exception as e:
            log.error(f"LED: set brightness failed: {e}")

    def on(self):
        self._set_brightness(100)

    def off(self):
        self._set_brightness(0)

    def blink(self, times: int = 1, interval: float = 0.2):
        """Queue smooth beacon pulses; returns immediately."""
        with self._lock:
            self._pulses_pending += times
            self._pulse_interval = interval
        self._wake.set()

    def start_beacon(self, interval: float = 1.2):
        """Pulse continuously (aircraft beacon) until stop_beacon()."""
        with self._lock:
            self._beacon = True
            self._pulse_interval = interval
        self._wake.set()

    def stop_beacon(self):
        with self._lock:
            self._beacon = False
        self.off()

    def _run(self):
        while not self._stop.is_set():
            self._wake.wait()
            if self._stop.is_set():
                break
            with self._lock:
                beacon = self._beacon
                if not beacon and self._pulses_pending <= 0:
                    self._wake.clear()
                    continue
                if not beacon:
                    self._pulses_pending -= 1
                interval = self._pulse_interval
            try:
                self._pulse(fade_time=max(interval, 0.15))
            except Exception as e:
                log.error(f"LED: pulse failed: {e}")

    def _pulse(self, fade_time: float):
        """One smooth breath: sine ramp 0 -> 100 -> 0 over 2*fade_time.
        In fallback (no PWM) mode this degrades to a clean on/off blink."""
        if self._pwm is None:
            self._set_brightness(100)
            time.sleep(fade_time)
            self._set_brightness(0)
            time.sleep(fade_time)
            return
        step_delay = fade_time / self.FADE_STEPS
        # Full breath as one cosine cycle: eased at both the dark and
        # bright ends, then squared (gamma) so the fade looks linear to
        # the eye — LEDs otherwise appear to snap on early in the ramp.
        total = self.FADE_STEPS * 2
        for i in range(total + 1):
            if self._stop.is_set():
                return
            level = (1 - math.cos(math.pi * i / self.FADE_STEPS)) / 2  # 0->1->0
            self._set_brightness(100 * level * level)
            time.sleep(step_delay)
        # Clear dark gap so the LED visibly rests fully off between breaths
        time.sleep(fade_time * 0.5)

    def cleanup(self):
        self._stop.set()
        self._wake.set()
        self._thread.join(timeout=2)
        if _HAS_GPIO:
            try:
                if self._pwm:
                    self._pwm.stop()
            finally:
                GPIO.cleanup(self.pin)