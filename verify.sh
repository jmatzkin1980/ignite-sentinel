#!/usr/bin/env bash
# Ignite Sentinel mandatory verification (IMP-246): the POSIX twin of verify.ps1.
#
# Resolves a Python 3.10+ interpreter (SENTINEL_PYTHON, then .venv/bin/python,
# then python3, then python) and runs, stopping at the first failure:
#   1. unittest discover -s tests
#   2. python -m sentinel doctor
#   3. tests/evals/run_discovery_evals.py and
#      tests/evals/run_faithfulness_claim_evals.py   (skipped with --skip-evals)
#
# Usage: ./verify.sh [--skip-evals]
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
skip_evals=0
for arg in "$@"; do
  case "$arg" in
    --skip-evals) skip_evals=1 ;;
    -h|--help) sed -n '2,12p' "$0"; exit 0 ;;
    *) echo "unknown argument: $arg" >&2; exit 2 ;;
  esac
done

is_python310() {
  "$1" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)' >/dev/null 2>&1
}

resolve_python() {
  local candidate
  for candidate in "${SENTINEL_PYTHON:-}" "$repo_root/.venv/bin/python" "$(command -v python3 || true)" "$(command -v python || true)"; do
    if [ -n "$candidate" ] && [ -x "$candidate" ] && is_python310 "$candidate"; then
      echo "$candidate"
      return 0
    fi
  done
  return 1
}

if ! python="$(resolve_python)"; then
  echo "No Python 3.10+ found. Create a venv: python3 -m venv .venv && .venv/bin/python -m pip install -e ." >&2
  echo "Or export SENTINEL_PYTHON pointing to a valid interpreter." >&2
  exit 1
fi

echo "==> Interpreter: $python"
cd "$repo_root"

echo
echo "==> [1/3] unittest discover -s tests"
"$python" -m unittest discover -s tests

echo
echo "==> [2/3] sentinel doctor"
"$python" -m sentinel doctor

if [ "$skip_evals" -eq 1 ]; then
  echo
  echo "==> [3/3] evals SKIPPED (--skip-evals)"
else
  echo
  echo "==> [3/3] discovery evals"
  "$python" tests/evals/run_discovery_evals.py
  echo
  echo "==> [3/3] faithfulness claim evals"
  "$python" tests/evals/run_faithfulness_claim_evals.py
fi

echo
echo "==> Verification OK"
