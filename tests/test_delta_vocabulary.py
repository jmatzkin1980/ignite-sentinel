"""IMP-187: closed ADDED/MODIFIED/REMOVED delta vocabulary across delta reports.

Every "what changed" report marks each affected section/unit with a single
closed enum so a downstream coding agent can act on the delta without diffing
whole documents. An invalid marker is impossible by construction: the enum is
the only source of the tokens and `delta_status` raises on anything else.
"""
from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from pathlib import Path

from sentinel.cli import main
from sentinel.deltas import DeltaStatus, delta_marker, delta_status
from sentinel.generation import section_delta_entries, sections_by_heading
from sentinel.discovery.workflow import requirement_unit_delta_entries


class DeltaEnumTests(unittest.TestCase):
    def test_vocabulary_is_closed(self):
        self.assertEqual(
            {m.value for m in DeltaStatus},
            {"ADDED", "MODIFIED", "REMOVED", "UNCHANGED"},
        )

    def test_canonical_and_member_passthrough(self):
        self.assertIs(delta_status("ADDED"), DeltaStatus.ADDED)
        self.assertIs(delta_status(DeltaStatus.REMOVED), DeltaStatus.REMOVED)
        self.assertEqual(delta_marker("modified"), "MODIFIED")

    def test_surface_aliases_map_onto_the_enum(self):
        # Acceptance-criteria vocabulary folds into the canonical markers.
        self.assertEqual(delta_marker("added_after_freeze"), "ADDED")
        self.assertEqual(delta_marker("changed"), "MODIFIED")
        self.assertEqual(delta_marker("removed"), "REMOVED")

    def test_unknown_status_is_impossible_by_construction(self):
        for bad in ("DELETED", "renamed", "", "add"):
            with self.assertRaises(ValueError):
                delta_marker(bad)


class SectionDeltaTests(unittest.TestCase):
    def test_added_modified_removed_and_unchanged_omitted(self):
        old = "# A\n\nalpha\n\n# B\n\nbeta\n\n# C\n\ngamma\n"
        new = "# A\n\nalpha\n\n# B\n\nBETA CHANGED\n\n# D\n\ndelta\n"
        entries = section_delta_entries(old, new)
        by_heading = {e["heading"]: e["status"] for e in entries}
        self.assertEqual(by_heading["# D"], "ADDED")
        self.assertEqual(by_heading["# B"], "MODIFIED")
        self.assertEqual(by_heading["# C"], "REMOVED")
        # Unchanged section A is omitted from the delta view.
        self.assertNotIn("# A", by_heading)
        # Every emitted status is a valid closed-enum token.
        for status in by_heading.values():
            self.assertEqual(delta_marker(status), status)

    def test_sections_by_heading_captures_bodies(self):
        sections = sections_by_heading("# One\n\nbody one\n\n## Two\n\nbody two\n")
        self.assertEqual(sections["# One"], "body one")
        self.assertEqual(sections["## Two"], "body two")


class RequirementUnitDeltaTests(unittest.TestCase):
    def test_statuses_are_within_the_closed_set(self):
        previous = {
            "gone": {"id": "RU-001", "label": "Gone", "evidence": "x"},
            "kept": {"id": "RU-002", "label": "Kept", "evidence": "same"},
            "shift": {"id": "RU-003", "label": "Shift", "evidence": "old"},
        }
        units = [
            {"id": "RU-002", "label": "Kept", "evidence_mention": "same"},
            {"id": "RU-003", "label": "Shift", "evidence_mention": "new"},
            {"id": "RU-004", "label": "Fresh", "evidence_mention": "z"},
        ]
        entries = requirement_unit_delta_entries(previous, units)
        statuses = {e["label"]: e["status"] for e in entries}
        self.assertEqual(statuses["Fresh"], "ADDED")
        self.assertEqual(statuses["Shift"], "MODIFIED")
        self.assertEqual(statuses["Gone"], "REMOVED")
        self.assertEqual(statuses["Kept"], "UNCHANGED")
        for status in statuses.values():
            self.assertIn(status, {m.value for m in DeltaStatus})


class AcceptanceDeltaColumnTests(unittest.TestCase):
    def setUp(self):
        self.old_cwd = Path.cwd()
        self.temp = Path(tempfile.mkdtemp())
        os.chdir(self.temp)
        self.assertEqual(main(["init", "DEMO"]), 0)
        self.ws = self.temp / "workspaces" / "DEMO"

    def tearDown(self):
        os.chdir(self.old_cwd)
        shutil.rmtree(self.temp, ignore_errors=True)

    def test_report_adds_canonical_delta_column(self):
        from sentinel.backlog.status import write_acceptance_criteria_delta_report

        deltas = [
            {"story_id": "US-001", "ac_id": "AC-1", "change_type": "removed",
             "frozen": {"criterion": "Old rule."}, "current": {}},
            {"story_id": "US-001", "ac_id": "AC-2", "change_type": "changed",
             "frozen": {"criterion": "Was."}, "current": {"criterion": "Now."}},
            {"story_id": "US-002", "ac_id": "AC-9", "change_type": "added_after_freeze",
             "frozen": {}, "current": {"criterion": "New rule."}},
        ]
        path = write_acceptance_criteria_delta_report("DEMO", deltas)
        report = path.read_text(encoding="utf-8")
        self.assertIn("| Story | AC | Delta | Change | Frozen Criterion | Current Criterion |", report)
        # Canonical marker AND the nuanced surface change_type both present.
        self.assertIn("| US-001 | `AC-1` | REMOVED | removed |", report)
        self.assertIn("| US-001 | `AC-2` | MODIFIED | changed |", report)
        self.assertIn("| US-002 | `AC-9` | ADDED | added_after_freeze |", report)


if __name__ == "__main__":
    unittest.main()
