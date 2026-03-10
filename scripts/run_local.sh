#!/usr/bin/env bash
set -euo pipefail

if [[ ! -f requirements.txt || ! -f app.py ]]; then
  echo "Run this script from the repository root (where app.py and requirements.txt exist)."
  exit 1
fi

if ! python3 -m venv .venv >/dev/null 2>&1; then
  echo "Could not create virtualenv. On Linux Mint/Ubuntu, install: sudo apt install python3-venv"
  exit 1
fi
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt

# Start the app (db init + seed happen in app.py on startup)
python app.py
