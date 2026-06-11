#!/usr/bin/env sh
set -eu

if [ -n "${SENTINEL_PYTHON:-}" ]; then
  PYTHON_BIN="$SENTINEL_PYTHON"
elif [ -x ".venv/bin/python" ]; then
  PYTHON_BIN=".venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="python3"
elif command -v python >/dev/null 2>&1; then
  PYTHON_BIN="python"
else
  echo "Python 3.10+ was not found. Install Python, create .venv, or set SENTINEL_PYTHON." >&2
  exit 1
fi

if [ "$#" -eq 0 ]; then
  set -- --help
fi

"$PYTHON_BIN" -m sentinel "$@"
