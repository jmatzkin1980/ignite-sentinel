"""IMP-416 task 7: INVEST Small judges a change story by its units against the slicing model size."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import SnapshotWorkspaceCase, run_ok  # noqa: E402
from sentinel.core.io import forget_read_snapshots  # noqa: E402
from sentinel.quality import generate_quality, invest_audit  # noqa: E402
from test_change_backlog import state  # noqa: E402
from test_change_specs import ALL_ANSWERS, answer, open_change  # noqa: E402

CRITERIA = [{"id": "AC-001", "classification": "fail-to-pass"}]
AC_CLASSES = {"fail-to-pass", "pass-to-pass", "evidence"}


def audit(units=None, max_units=None, trace=None):
    extra = {} if units is None else {"source_units": units, "max_units": max_units}
    return invest_audit(
        {"id": "US-001"},
        {"type": "value_story"},
        criteria=CRITERIA,
        ac_classes=AC_CLASSES,
        trace=trace if trace is not None else ["SPEC-U-001"],
        dependencies=[],
        enables=[],
        source_unit="SPEC-U-001",
        **extra,
    )["S"]


class GroupedInvest(unittest.TestCase):
    def test_grouped_story_is_small(self):
        ok = audit([f"SPEC-U-00{i}" for i in range(1, 5)], 5)
        self.assertTrue(ok["passed"])
        self.assertIn("4 unit(s) of one functionality, within the slicing model size (5)", ok["finding"])
        bad = audit([f"SPEC-U-00{i}" for i in range(1, 7)], 5)
        self.assertFalse(bad["passed"])
        self.assertIn("above the slicing model size (5)", bad["finding"])

    def test_project_invest_unchanged(self):
        signal = audit(trace=["SPEC-U-001", "SPEC-U-002", "SPEC-U-003"])
        self.assertFalse(signal["passed"])
        self.assertEqual(
            signal["finding"],
            "The slice looks broad because upstream scope or prerequisite coupling is not tightly bounded.",
        )


class ChangeQuality(SnapshotWorkspaceCase):
    cid = "CHG-001"

    @classmethod
    def build_workspace(cls):
        run_ok(["init", "BORR"])
        cid = open_change("BORR")
        answer("BORR", cid, "a.md", ALL_ANSWERS)
        run_ok(["brief", "BORR", "--change", cid])
        run_ok(["specs", "BORR", "--change", cid])

    def test_change_quality_passes_small(self):
        run_ok(["backlog", "BORR", "--change", self.cid])
        forget_read_snapshots()
        generate_quality("BORR", change_id=self.cid)  # IMP-431: the project audit no longer takes the stories of a change
        quality = state("BORR")["story_quality"]
        added = [q for q in quality.values() if "unit(s) of one functionality" in q["invest_audit"]["S"]["finding"]]
        self.assertTrue(added)
        for result in added:
            self.assertTrue(result["invest_audit"]["S"]["passed"])
        self.assertTrue(any(len(q["invest_audit"]["S"]["evidence"]["source_units"]) == 2 for q in added))


if __name__ == "__main__":
    unittest.main()
