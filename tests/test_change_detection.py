"""IMP-382: detect_gaps scoped by work kind and border surfaces."""
from __future__ import annotations

import unittest
from pathlib import Path

from sentinel.discovery import detect_gaps

NOTE = (Path(__file__).parent / "fixtures" / "change_borrador.md").read_text(encoding="utf-8")
PROJECT_ONLY = {"GAP-PRD-PERSONA-DETAIL", "GAP-PRD-FR-AC", "GAP-PRD-NFR-KPI", "GAP-PRD-GOVERNANCE",
                "GAP-PRD-DEPENDENCIES-ROADMAP", "GAP-DESIGN-PROTOTYPE-INPUT", "GAP-BACKLOG-ENABLERS"}


class ChangeDetection(unittest.TestCase):
    def test_project_default_is_unchanged(self):
        ids = [g["id"] for g in detect_gaps(NOTE)]
        self.assertEqual(len(ids), 27)

    def test_change_never_raises_project_only_checks(self):
        project = {g["id"] for g in detect_gaps(NOTE)}
        change = {g["id"] for g in detect_gaps(NOTE, work="change")}
        self.assertFalse(change & PROJECT_ONLY)
        self.assertEqual(change, project - PROJECT_ONLY)
        self.assertEqual(len(change), 20)

    def test_border_without_screen_drops_design_and_frontend(self):
        ids = {g["id"] for g in detect_gaps(NOTE, work="change", border_types=frozenset({"endpoint", "dato"}))}
        self.assertFalse(ids & {"GAP-DESIGN-FLOW", "GAP-DESIGN-STATES", "GAP-FRONTEND-SURFACE"})


if __name__ == "__main__":
    unittest.main()
