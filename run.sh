#!/bin/bash
set -euo pipefail

if [[ "${EUID:-0}" -ne 0 ]]; then
  echo "❌ Запускай через sudo: sudo bravelgo"
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="/opt/bravelgo/venv"

if [[ -x "$VENV/bin/python3" ]]; then
  exec "$VENV/bin/python3" "$SCRIPT_DIR/bravelgo/app.py"
fi

exec python3 "$SCRIPT_DIR/bravelgo/app.py"
