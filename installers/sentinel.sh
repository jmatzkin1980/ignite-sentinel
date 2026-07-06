#!/usr/bin/env sh
set -eu

# Resolve the repo root from the script location (parent of installers/) and run
# from there, so the launcher works when invoked from any cwd. The CLI anchors
# workspaces/ to its cwd (sentinel/core/paths.py:repo_root).
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPO_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
cd -- "$REPO_ROOT"

if [ -n "${SENTINEL_PYTHON:-}" ]; then
  PYTHON_BIN="$SENTINEL_PYTHON"
elif [ -x ".venv/bin/python" ]; then
  PYTHON_BIN="$REPO_ROOT/.venv/bin/python"
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

exec "$PYTHON_BIN" -m sentinel "$@"
