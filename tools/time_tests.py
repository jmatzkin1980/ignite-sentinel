"""Measure test duration per module (IMP-246): picks the slow set for the fast CI tier.

Usage: python tools/time_tests.py [--out timings.json]
Runs every tests/test_*.py module on its own and records wall-clock seconds, sorted
slowest first. Stdlib only; read-only apart from the output file.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="")
    args = parser.parse_args(argv)
    sys.path.insert(0, str(ROOT / "tests"))
    sys.path.insert(0, str(ROOT))
    timings = []
    for path in sorted((ROOT / "tests").glob("test_*.py")):
        suite = unittest.defaultTestLoader.loadTestsFromName(path.stem)
        start = time.perf_counter()
        result = unittest.TextTestRunner(stream=_Null(), verbosity=0).run(suite)
        timings.append({"module": path.stem, "seconds": round(time.perf_counter() - start, 2), "tests": result.testsRun})
    timings.sort(key=lambda item: item["seconds"], reverse=True)
    text = json.dumps(timings, indent=1)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


class _Null:
    def write(self, *_):
        pass

    def flush(self):
        pass


if __name__ == "__main__":
    raise SystemExit(main())
