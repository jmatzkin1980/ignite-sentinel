"""Run the unit suite by CI tier (IMP-246).

    python tools/run_tests.py --tier fast   # every module except tests/slow_modules.txt
    python tools/run_tests.py --tier full   # the whole suite (same as unittest discover -s tests)
    python tools/run_tests.py --tier full --slowest 10   # ...then the 10 slowest modules (verify.ps1)

The slow set is an explicit list (``tests/slow_modules.txt``), chosen from measured
durations (``tools/time_tests.py``), so the fast tier is reproducible and reviewable.
Stdlib only. Exit code 0 only when every selected test passes.
"""

from __future__ import annotations

import argparse
import sys
import time
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


class TimedResult(unittest.TextTestResult):
    """Attributes the time between two finished tests (fixtures included) to the later test's module."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.module_seconds: dict[str, float] = {}
        self.module_tests: dict[str, int] = {}
        self._mark = time.perf_counter()

    def stopTest(self, test):
        super().stopTest(test)
        now = time.perf_counter()
        module = type(test).__module__
        self.module_seconds[module] = self.module_seconds.get(module, 0.0) + (now - self._mark)
        self.module_tests[module] = self.module_tests.get(module, 0) + 1
        self._mark = now


def slowest_report(result: TimedResult, top: int) -> str:
    """IMP-305: where the suite's time goes, so a jump shows in the PR that causes it."""
    total = sum(result.module_seconds.values()) or 1.0
    slowest = sorted(result.module_seconds.items(), key=lambda item: -item[1])[:top]
    lines = [f"Slowest {len(slowest)} test modules (of {len(result.module_seconds)}):"]
    for module, seconds in slowest:
        lines.append(f"  {seconds:7.1f}s  {100 * seconds / total:4.1f}%  {result.module_tests[module]:4d} tests  {module}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--tier", choices=("fast", "full"), default="fast")
    parser.add_argument("--slowest", type=int, default=0, metavar="N", help="list the N slowest test modules at the end")
    args = parser.parse_args(argv)
    sys.path.insert(0, str(TESTS))
    sys.path.insert(0, str(ROOT))
    modules = selected_modules(args.tier)
    suite = unittest.defaultTestLoader.loadTestsFromNames(modules)
    print(f"tier={args.tier}: {len(modules)} modules", flush=True)
    result = unittest.TextTestRunner(verbosity=1, resultclass=TimedResult).run(suite)
    if args.slowest:
        print("\n" + slowest_report(result, args.slowest), flush=True)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
