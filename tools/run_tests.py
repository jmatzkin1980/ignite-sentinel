"""Run the unit suite by CI tier (IMP-246).

    python tools/run_tests.py --tier fast   # every module except tests/slow_modules.txt
    python tools/run_tests.py --tier full   # the whole suite (same as unittest discover -s tests)

The slow set is an explicit list (``tests/slow_modules.txt``), chosen from measured
durations (``tools/time_tests.py``), so the fast tier is reproducible and reviewable.
Stdlib only. Exit code 0 only when every selected test passes.
"""

from __future__ import annotations

import argparse
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TESTS = ROOT / "tests"
SLOW_LIST = TESTS / "slow_modules.txt"


def slow_modules() -> set[str]:
    if not SLOW_LIST.is_file():
        return set()
    names = set()
    for line in SLOW_LIST.read_text(encoding="utf-8").splitlines():
        name = line.split("#", 1)[0].strip()
        if name:
            names.add(name)
    return names


def selected_modules(tier: str) -> list[str]:
    modules = sorted(path.stem for path in TESTS.glob("test_*.py"))
    if tier == "full":
        return modules
    slow = slow_modules()
    unknown = sorted(slow - set(modules))
    if unknown:
        raise SystemExit(f"tests/slow_modules.txt names modules that do not exist: {', '.join(unknown)}")
    return [name for name in modules if name not in slow]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--tier", choices=("fast", "full"), default="fast")
    args = parser.parse_args(argv)
    sys.path.insert(0, str(TESTS))
    sys.path.insert(0, str(ROOT))
    modules = selected_modules(args.tier)
    suite = unittest.defaultTestLoader.loadTestsFromNames(modules)
    print(f"tier={args.tier}: {len(modules)} modules", flush=True)
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
