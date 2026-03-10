#!/usr/bin/env bash
set -euo pipefail

echo "== Linux Mint setup for The 19th Hole Inventory =="

if ! command -v sudo >/dev/null 2>&1; then
  echo "This script expects sudo to be available."
  exit 1
fi

sudo apt update
sudo apt install -y \
  python3 \
  python3-venv \
  python3-pip \
  sqlite3 \
  curl \
  ca-certificates

echo
echo "[OK] Base packages installed."
echo "Next step: run ./scripts/run_local.sh"
