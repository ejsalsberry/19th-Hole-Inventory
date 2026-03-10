#!/usr/bin/env bash
set -euo pipefail

echo "== The 19th Hole Doctor =="
echo "pwd: $(pwd)"
echo "python: $(command -v python3 || true)"
python3 --version || true

echo
if [[ ! -f requirements.txt ]]; then
  echo "[FAIL] requirements.txt missing"
  exit 1
fi

echo "[OK] requirements.txt present"

echo
python3 - <<'PY'
import importlib.util
spec = importlib.util.find_spec('flask')
if spec is None:
    print('[WARN] Flask not importable in current interpreter')
else:
    import flask
    print(f'[OK] Flask importable: {flask.__version__}')
PY

echo
if [[ -f inventory.db ]]; then
  echo "[OK] inventory.db exists"
  python3 - <<'PY'
import sqlite3
con=sqlite3.connect('inventory.db')
rows=con.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
print('[OK] tables:', ', '.join(r[0] for r in rows))
PY
else
  echo "[WARN] inventory.db not found yet (will be created on first run)"
fi

echo
if command -v curl >/dev/null 2>&1; then
  code=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:5000/ || true)
  if [[ "$code" == "200" || "$code" == "302" ]]; then
    echo "[OK] app appears reachable on :5000 (HTTP $code)"
  else
    echo "[INFO] app not reachable on :5000 right now (HTTP $code)"
  fi
fi

echo "== Doctor check complete =="
