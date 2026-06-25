#!/bin/bash
# TaxFlow Pro v3.10 — Linux setup helper
# Run from inside the extracted tarball directory:
#   ./setup_linux.sh

set -euo pipefail

echo "[TaxFlow Pro] Installing system dependencies..."
if command -v apt-get >/dev/null 2>&1; then
    sudo apt-get update
    sudo apt-get install -y tesseract-ocr poppler-utils python3-pip python3-venv
elif command -v dnf >/dev/null 2>&1; then
    sudo dnf install -y tesseract poppler-utils python3-pip
elif command -v pacman >/dev/null 2>&1; then
    sudo pacman -Sy --noconfirm tesseract poppler python-pip
else
    echo "WARNING: Could not detect package manager. Please install tesseract and poppler-utils manually."
fi

echo "[TaxFlow Pro] Creating Python virtual environment..."
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

echo "[TaxFlow Pro] Setup complete. Run the app with:"
echo "  ./TaxFlowPro.sh"
