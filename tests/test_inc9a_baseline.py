"""IMP-435 (H27 inc 9a): what the project, the change and the series write is the same bytes as before inc 9a,
except for what a task lists under "Cambia bytes". Machine- and backend-independent (see tests/inc9a_baseline.py)."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from inc9a_baseline import BASELINE_PATH, snapshot  # noqa: E402


class Inc9aBytesUnchanged(unittest.TestCase):
    def test_outputs_match_the_snapshot_taken_before_inc9a(self):
        before = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as tmp:
            now = snapshot(Path(tmp))
        self.assertEqual(sorted(now), sorted(before))
        for scenario in before:
            self.assertEqual(now[scenario], before[scenario], scenario)


if __name__ == "__main__":
    unittest.main()
