#!/bin/bash
# Compile the private analyzer modules into native .so extensions (Cython).
#
# FOR THE PROJECT AUTHOR ONLY — end users never run this; they get the
# prebuilt .so files from the repo and just run install.sh + signal_server.py.
#
# Workflow:
#   1. Copy the full backend/ (INCLUDING the private .py sources) to the Pi
#   2. Run this script on the Pi:  ./build_protected.sh
#   3. Copy the generated backend/*.so back into your local repo
#   4. Commit the .so files — the private .py sources are gitignored and
#      must never be committed
#
# The .so is tied to the CPU architecture and Python minor version it was
# built with (e.g. cpython-311-aarch64-linux-gnu). Build on the same OS /
# Python that users will run — ideally current Raspberry Pi OS. To support
# both 32-bit and 64-bit Pi OS, run this once on each and commit both .so.

set -euo pipefail
cd "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# The closed-source modules. Add a filename here to protect another module.
PRIVATE_MODULES=(
    signal_analyzer.py
    channel_id.py
    fingerprint_store.py
)

for f in "${PRIVATE_MODULES[@]}"; do
    [ -f "$f" ] || { echo "ERROR: $f not found — copy the private sources here first."; exit 1; }
done

# Use the project venv so the .so matches the Python users get from install.sh
if [ ! -d venv ]; then
    python3 -m venv venv
fi
source venv/bin/activate
pip install --quiet --upgrade pip cython setuptools

echo "=== Compiling private modules with Cython ==="
cythonize -3 --inplace "${PRIVATE_MODULES[@]}"

# The intermediate .c files also expose the logic — remove them
for f in "${PRIVATE_MODULES[@]}"; do
    rm -f "${f%.py}.c"
done

echo ""
echo "=== Verifying the compiled modules import (without the .py sources) ==="
HIDE_DIR="$(mktemp -d)"
for f in "${PRIVATE_MODULES[@]}"; do
    mv "$f" "$HIDE_DIR/"
done
STATUS=0
for f in "${PRIVATE_MODULES[@]}"; do
    mod="${f%.py}"
    if python -c "import $mod" 2>/dev/null; then
        echo "  OK   $mod  ->  $(ls "$mod".*.so)"
    else
        echo "  FAIL $mod — .so did not import"
        STATUS=1
    fi
done
for f in "${PRIVATE_MODULES[@]}"; do
    mv "$HIDE_DIR/$f" .
done
rmdir "$HIDE_DIR"
[ "$STATUS" -eq 0 ] || exit 1

echo ""
echo "=== Done ==="
echo "Copy these back into your repo and commit them:"
ls -1 ./*.so
echo ""
echo "Reminder: the .py sources of these modules are gitignored — do NOT force-add them."
