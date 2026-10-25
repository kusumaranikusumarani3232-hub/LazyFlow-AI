#!/usr/bin/env bash
# Exit on error
set -o errexit

echo "==> Updating apt packages and installing Tesseract OCR..."
apt-get update
apt-get install -y tesseract-ocr tesseract-ocr-eng

echo "==> Upgrading pip and installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

echo "==> Tesseract version verification:"
tesseract --version || echo "Warning: tesseract binary check returned non-zero"

echo "==> Render build completed successfully!"
