#!/usr/bin/env bash
set -euo pipefail

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

echo "Setup complete."
echo "Run: source venv/bin/activate"
echo "Then: python src/main.py api"
