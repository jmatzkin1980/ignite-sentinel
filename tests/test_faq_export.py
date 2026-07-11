"""Tests for the traceable resolved-questions FAQ export (IMP-186).

The FAQ is a governed export from the gap ledger: each question is an elicited
gap and each answer is its CONFIRMED closure, quoted verbatim from the
seed/decision tables and cited to the gap + source. Only confirmed gaps appear;
open gaps are never shown as answered (cita-o-silencio, never invented).
"""
from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from pathlib import Path

from sentinel.cli import main
from sentinel.discovery import build_faq, render_faq
from sentinel.export import export_faq


RAW = (
    "# Risk Dashboard\n\n"
    "We need a dashboard for operations leads to see queue risk before standup. "
    "The dashboard reads queue metrics from the existing support metrics service. "
    "Success means reducing missed SLAs."
)

DECISIONS_WITH_CONFIRMED = (
    "# Decision Log\n\n"
    "## Gap Resolution Decisions\n\n"
    "| Decision ID | Gap ID | Status | Decision | Source |\n"
    "| --- | --- | --- | --- | --- |\n"
    "| AUTO-DEC-CHG-001-001 | `GAP-OBJECTIVE` | CONFIRMED | Cut missed SLAs by 20% this quarter. | `CHG-001` |\n"
    "| AUTO-DEC-CHG-001-002 | `GAP-USERS` | PENDING | Operations leads, maybe others. | `CHG-001` |\n"
)


class FaqRenderTests(unittest.TestCase):
    def test_render_cites_each_resolved_question(self):
        answers = {"GAP-OBJECTIVE": {"statement": "Cut missed SLAs by 20%.", "source": "CHG-001"}}
        faq = render_faq("DEMO", answers, "en")
        self.assertIn("Resolved Questions (FAQ) - DEMO", faq)
        self.assertIn("Expected Outcome", faq)  # human title for GAP-OBJECTIVE
        self.assertIn("Cut missed SLAs by 20%.", faq)  # verbatim answer
        self.assertIn("`GAP-OBJECTIVE`", faq)  # trace to gap
        self.assertIn("`CHG-001`", faq)  # trace to source
        self.assertIn("does NOT replace", faq)

    def test_empty_marker_is_bilingual_and_never_invents(self):
        self.assertIn("FAQ is empty", render_faq("DEMO", {}, "en"))
        self.assertIn("never invented", render_faq("DEMO", {}, "en"))
        self.assertIn("FAQ esta vacia", render_faq("DEMO", {}, "es"))
        self.assertIn("no se inventan", render_faq("DEMO", {}, "es"))

    def test_render_is_ordered_and_numbered(self):
        answers = {
            "GAP-OBJECTIVE": {"statement": "A.", "source": "CHG-001"},
            "GAP-USERS": {"statement": "B.", "source": "CHG-001"},
        }
        faq = render_faq("DEMO", answers, "en")
        self.assertLess(faq.index("Q1."), faq.index("Q2."))
        self.assertLess(faq.index("GAP-OBJECTIVE"), faq.index("GAP-USERS"))

    def test_answer_without_source_still_cites_the_gap(self):
        faq = render_faq("DEMO", {"GAP-OBJECTIVE": {"statement": "A.", "source": ""}}, "en")
        self.assertIn("`GAP-OBJECTIVE`", faq)


class FaqExportLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.old_cwd = Path.cwd()
        self.temp = Path(tempfile.mkdtemp())
        os.chdir(self.temp)
        self.raw = self.temp / "raw.md"
        self.raw.write_text(RAW, encoding="utf-8")
        self.assertEqual(main(["init", "DEMO"]), 0)
        self.assertEqual(main(["ingest", "DEMO", "--source", str(self.raw)]), 0)
        self.ws = self.temp / "workspaces" / "DEMO"

    def tearDown(self):
        os.chdir(self.old_cwd)
        shutil.rmtree(self.temp, ignore_errors=True)

    def test_export_projects_only_confirmed_gaps(self):
        decisions = self.ws / "01_discovery" / "decisions.md"
        decisions.write_text(DECISIONS_WITH_CONFIRMED, encoding="utf-8")
        gaps_path = self.ws / "01_discovery" / "gaps.md"
        before = gaps_path.read_text(encoding="utf-8")
        self.assertEqual(main(["export", "DEMO", "--artifact", "gaps", "--format", "faq"]), 0)
        faq_path = self.ws / "08_context_packs" / "exports" / "gaps-faq.md"
        self.assertTrue(faq_path.exists())
        faq = faq_path.read_text(encoding="utf-8")
        # Confirmed gap appears with its verbatim closure + citation.
        self.assertIn("Cut missed SLAs by 20% this quarter.", faq)
        self.assertIn("`GAP-OBJECTIVE`", faq)
        # The PENDING (open) gap must NEVER appear as answered.
        self.assertNotIn("GAP-USERS", faq)
        self.assertNotIn("Operations leads, maybe others.", faq)
        # The canonical source of truth is untouched by the derived export.
        self.assertEqual(gaps_path.read_text(encoding="utf-8"), before)

    def test_build_faq_matches_export(self):
        (self.ws / "01_discovery" / "decisions.md").write_text(DECISIONS_WITH_CONFIRMED, encoding="utf-8")
        self.assertEqual(main(["export", "DEMO", "--artifact", "gaps", "--format", "faq"]), 0)
        faq_path = self.ws / "08_context_packs" / "exports" / "gaps-faq.md"
        self.assertEqual(build_faq("DEMO"), faq_path.read_text(encoding="utf-8"))

    def test_faq_format_rejected_for_non_gaps_artifact(self):
        with self.assertRaises(RuntimeError) as ctx:
            export_faq("DEMO", "prd")
        self.assertIn("gaps", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
