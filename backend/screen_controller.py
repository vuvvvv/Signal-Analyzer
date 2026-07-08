"""
ST7735 Screen Controller — PORTRAIT mode (128x160)
Wiring: VCC=3.3V, GND, CLK=GPIO11, MOSI=GPIO10, CS=GPIO8, DC=GPIO24, RST=GPIO25

Layout (top to bottom):
  - Header bar: app name + clock
  - Big frequency readout (large font) + "MHz"
  - Signal-strength bars (phone-style, from spectrum SNR) + dB value
  - Mini spectrum strip
  - Info lines: peak power, clients connected, anomaly count
"""

import logging
import time
from datetime import datetime

log = logging.getLogger(__name__)

try:
    from luma.core.interface.serial import spi
    from luma.lcd.device import st7735
    from PIL import Image, ImageDraw, ImageFont
    _HAS_LCD = True
except ImportError:
    _HAS_LCD = False
    log.warning("luma.lcd not available")

_FONT_PATHS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]


def _load_font(size: int):
    for path in _FONT_PATHS:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    return ImageFont.load_default()


class ScreenController:
    # Portrait: panel's native 128x160 orientation
    WIDTH = 128
    HEIGHT = 160

    DASHBOARD_INTERVAL = 1.0  # seconds between dashboard redraws
    ALERT_HOLD = 4.0          # keep an alert on screen this long before dashboard resumes

    def __init__(self):
        self.device = None
        self._last_dashboard = 0.0
        self._alert_until = 0.0
        self._anomaly_count = 0
        if _HAS_LCD:
            try:
                serial = spi(port=0, device=0, gpio_DC=24, gpio_RST=25)
                # Panel native geometry is 160x128 (proven working config).
                # rotate=1 turns it 90° so the framebuffer becomes 128x160
                # portrait — do NOT swap width/height here, luma does that.
                self.device = st7735(
                    serial, width=self.HEIGHT, height=self.WIDTH, rotate=1, bgr=True
                )
                log.info("ST7735 screen initialized (portrait 128x160)")
            except Exception as e:
                log.error(f"Screen init failed: {e}")
        if _HAS_LCD:
            self._font_big = _load_font(26)
            self._font_med = _load_font(14)
            self._font_small = _load_font(10)

    def _make_image(self) -> tuple:
        img = Image.new("RGB", (self.WIDTH, self.HEIGHT), "black")
        draw = ImageDraw.Draw(img)
        return img, draw

    def _display(self, img):
        if self.device:
            self.device.display(img)

    def _center_x(self, draw, text: str, font) -> int:
        w = draw.textlength(text, font=font)
        return int((self.WIDTH - w) / 2)

    def show_boot(self):
        if not _HAS_LCD:
            return
        img, draw = self._make_image()
        draw.text((self._center_x(draw, "SIGNAL", self._font_big), 40),
                  "SIGNAL", font=self._font_big, fill="green")
        draw.text((self._center_x(draw, "ANALYZER", self._font_big), 70),
                  "ANALYZER", font=self._font_big, fill="green")
        draw.text((self._center_x(draw, "Ready", self._font_small), 110),
                  "Ready", font=self._font_small, fill=(0, 180, 0))
        now = datetime.now().strftime("%H:%M:%S")
        draw.text((self._center_x(draw, now, self._font_small), 125),
                  now, font=self._font_small, fill="gray")
        self._display(img)

    # ---- main live view -------------------------------------------------

    def show_dashboard(self, powers: list, center_mhz: float, clients: int = 0):
        """Portrait dashboard. Throttled internally — safe to call at spectrum rate."""
        if not _HAS_LCD:
            return
        now = time.monotonic()
        if now < self._alert_until or now - self._last_dashboard < self.DASHBOARD_INTERVAL:
            return
        self._last_dashboard = now

        img, draw = self._make_image()

        # Header bar
        draw.rectangle([(0, 0), (self.WIDTH - 1, 13)], fill=(0, 40, 0))
        draw.text((3, 2), "SIGNAL ANALYZER", font=self._font_small, fill="green")
        clock = datetime.now().strftime("%H:%M")
        draw.text((self.WIDTH - draw.textlength(clock, font=self._font_small) - 3, 2),
                  clock, font=self._font_small, fill="white")

        # Big frequency readout
        freq_txt = f"{center_mhz:.1f}"
        draw.text((self._center_x(draw, freq_txt, self._font_big), 20),
                  freq_txt, font=self._font_big, fill="white")
        draw.text((self._center_x(draw, "MHz", self._font_med), 50),
                  "MHz", font=self._font_med, fill=(0, 200, 255))

        # Signal strength: SNR = peak above median noise floor
        peak_db = snr = 0.0
        bars = 0
        if powers:
            sorted_p = sorted(powers)
            noise = sorted_p[len(sorted_p) // 2]
            peak_db = max(powers)
            snr = peak_db - noise
            for th in (3, 8, 15, 22, 30):
                if snr >= th:
                    bars += 1

        # Phone-style bars (5 bars, increasing height)
        bx, base_y = 32, 106
        for i in range(5):
            h = 8 + i * 7
            x0 = bx + i * 14
            box = [(x0, base_y - h), (x0 + 10, base_y)]
            if i < bars:
                color = "red" if bars <= 1 else ("yellow" if bars <= 2 else "lime")
                draw.rectangle(box, fill=color)
            else:
                draw.rectangle(box, outline=(60, 60, 60))
        snr_txt = f"SNR {snr:.0f} dB"
        draw.text((self._center_x(draw, snr_txt, self._font_small), 109),
                  snr_txt, font=self._font_small, fill="white")

        # Mini spectrum strip
        strip_top, strip_h = 122, 20
        if powers:
            n = len(powers)
            min_p = min(powers)
            rng = max(max(powers) - min_p, 1)
            for x in range(self.WIDTH):
                idx = int(x * n / self.WIDTH)
                norm = (powers[idx] - min_p) / rng
                bar = int(norm * strip_h)
                draw.line([(x, strip_top + strip_h - bar), (x, strip_top + strip_h)],
                          fill=(0, 255, 0) if norm < 0.7 else (255, 60, 60))

        # Bottom info line
        draw.text((3, 147), f"P:{peak_db:.0f}dB", font=self._font_small, fill="cyan")
        draw.text((66, 147), f"C:{clients}", font=self._font_small, fill="white")
        draw.text((94, 147), f"A:{self._anomaly_count}", font=self._font_small,
                  fill="red" if self._anomaly_count else "gray")

        self._display(img)

    # Backwards-compatible name: old callers passed only spectrum + freq
    def show_spectrum(self, powers: list, center_mhz: float):
        self.show_dashboard(powers, center_mhz)

    def show_alert(self, signal: dict):
        if not _HAS_LCD:
            return
        self._anomaly_count += 1
        self._alert_until = time.monotonic() + self.ALERT_HOLD
        img, draw = self._make_image()
        draw.rectangle([(0, 0), (self.WIDTH - 1, self.HEIGHT - 1)], outline="red", width=2)
        draw.text((self._center_x(draw, "ANOMALY", self._font_med), 12),
                  "ANOMALY", font=self._font_med, fill="red")
        freq_txt = f"{signal['freq']:.2f}"
        draw.text((self._center_x(draw, freq_txt, self._font_big), 40),
                  freq_txt, font=self._font_big, fill="white")
        draw.text((self._center_x(draw, "MHz", self._font_small), 70),
                  "MHz", font=self._font_small, fill="white")
        draw.text((self._center_x(draw, f"{signal['power']:.1f} dBm", self._font_med), 90),
                  f"{signal['power']:.1f} dBm", font=self._font_med, fill="yellow")
        sig_type = signal.get("type", "Unknown")
        draw.text((self._center_x(draw, sig_type, self._font_small), 115),
                  sig_type, font=self._font_small, fill="cyan")
        now = datetime.now().strftime("%H:%M:%S")
        draw.text((self._center_x(draw, now, self._font_small), 140),
                  now, font=self._font_small, fill="gray")
        self._display(img)

    def show_status(self, text: str):
        if not _HAS_LCD:
            return
        img, draw = self._make_image()
        draw.text((self._center_x(draw, text, self._font_small), 75),
                  text, font=self._font_small, fill="green")
        self._display(img)
