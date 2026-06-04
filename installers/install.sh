#!/usr/bin/env sh
set -eu

echo "Ignite Sentinel portable setup"

PYTHON_BIN="${PYTHON:-python3}"

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  if command -v python >/dev/null 2>&1; then
    PYTHON_BIN="python"
  else
    echo "Python 3.10+ was not found. Install or expose Python in PATH, then rerun." >&2
    exit 1
  fi
fi

if [ "${1:-}" = "--venv" ]; then
  "$PYTHON_BIN" -m venv .venv
  . .venv/bin/activate
  python -m pip install -e .
  python -m sentinel /doctor
else
  "$PYTHON_BIN" -m sentinel /doctor
fi

echo "Ignite Sentinel is ready for repo-local VS Code usage."
