#!/bin/bash
# Run on Raspberry Pi to install all dependencies

echo "=== Signal Scope Pi Setup ==="

# System packages
sudo apt update
# python3-dev: needed to build RPi.GPIO/spidev from pip
# libopenblas0: runtime BLAS for numpy/scipy wheels
# fonts-dejavu-core: DejaVu fonts used by screen_controller.py
sudo apt install -y rtl-sdr sox python3-pip python3-venv python3-dev libusb-1.0-0 \
    git cmake build-essential libfftw3-dev libsamplerate-dev \
    libopenblas0 fonts-dejavu-core

# Block default kernel driver so RTL-SDR can use it
echo "blacklist dvb_usb_rtl28xxu" | sudo tee /etc/modprobe.d/blacklist-rtl.conf
sudo modprobe -r dvb_usb_rtl28xxu 2>/dev/null || true

# Enable SPI for screen
sudo raspi-config nonint do_spi 0

# csdr: the reference DSP engine (used by OpenWebRX and other mature SDR
# projects) that does CW demodulation here (the one mode real rtl_fm has
# no -M for). Not packaged in apt — build from source. See csdr_chain.py.
if ! command -v csdr >/dev/null 2>&1; then
    echo "=== Building csdr ==="
    git clone https://github.com/jketterl/csdr.git /tmp/csdr-build
    mkdir -p /tmp/csdr-build/build
    (cd /tmp/csdr-build/build && cmake .. && make -j"$(nproc)" && sudo make install)
    sudo ldconfig
    rm -rf /tmp/csdr-build
fi

# rtl_fm_pipe: a patched build of rtl-sdr's own rtl_fm.c that reads raw IQ
# from stdin instead of a USB device, used for WFM/NFM/AM/USB/LSB so audio
# matches the real `rtl_fm` CLI byte-for-byte. See vendor/rtl_fm_pipe.c.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
gcc -O2 -o "$SCRIPT_DIR/vendor/rtl_fm_pipe" "$SCRIPT_DIR/vendor/rtl_fm_pipe.c" -lm -lpthread

# Python environment
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Verify the prebuilt analyzer modules (shipped as compiled .so, no source)
# load on this Pi's architecture + Python version.
echo ""
echo "=== Checking prebuilt analyzer modules ==="
for mod in signal_analyzer channel_id fingerprint_store; do
    if python -c "import $mod" 2>/dev/null; then
        echo "  OK   $mod"
    else
        echo "  FAIL $mod — the prebuilt .so does not match this Pi's architecture"
        echo "         or Python version ($(python -V 2>&1), $(uname -m))."
        echo "         Check the README 'Prebuilt Modules' section for supported builds."
    fi
done

echo ""
echo "=== Setup Complete ==="
echo "Test RTL-SDR:  rtl_test"
echo "Run server:    source venv/bin/activate && python signal_server.py"
