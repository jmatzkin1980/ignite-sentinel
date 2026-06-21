#!/usr/bin/env sh
set -eu

TARGET="${1:-dist/sentinel.pyz}"

test_python() {
  "$1" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)' >/dev/null 2>&1
}

resolve_python() {
  if [ -n "${SENTINEL_PYTHON:-}" ] && [ -x "$SENTINEL_PYTHON" ] && test_python "$SENTINEL_PYTHON"; then
    printf '%s\n' "$SENTINEL_PYTHON"
    return 0
  fi
  if [ -x ".venv/bin/python" ] && test_python ".venv/bin/python"; then
    printf '%s\n' ".venv/bin/python"
    return 0
  fi
  if command -v python3 >/dev/null 2>&1 && test_python "$(command -v python3)"; then
    command -v python3
    return 0
  fi
  if command -v python >/dev/null 2>&1 && test_python "$(command -v python)"; then
    command -v python
    return 0
  fi
  return 1
}

PYTHON="$(resolve_python)" || {
  echo "Python 3.10+ was not found. Install Python, create .venv, or set SENTINEL_PYTHON." >&2
  exit 1
}

"$PYTHON" -m sentinel.build --target "$TARGET"
