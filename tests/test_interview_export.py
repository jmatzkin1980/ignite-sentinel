"""Tests for the read-only interview-script export from open gaps (IMP-183)."""
from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from pathlib import Path

from sentinel.cli import main
from sentinel.discovery import (
    candidate_options_for_gap,
    build_interview_script,
    interview_probing_for_gap,
    render_interview_script,
)
from sentinel.export import export_interview


RAW = (
    "# Risk Dashboard\n\n"
    "We need a dashboard for operations leads to see queue risk before standup. "
    "The dashboard reads queue metrics from the existing support metrics service. "
    "Success means reducing missed SLAs."
)


def _gap(**over):
    base = {
        "id": "GAP-SCOPE",
        "lens": "product",
        "severity": "critical",
        "status": "OPEN",
        "question": "What is explicitly in scope and out of scope?",
    }
    base.update(over)
    return base


class InterviewScriptRenderTests(unittest.TestCase):
    def test_blocking_gaps_render_before_follow_up(self):
        gaps = [
            _gap(id="GAP-QUALITY", lens="quality", severity="medium", question="Quality?"),
            _gap(id="GAP-SCOPE", lens="product", severity="critical"),
            _gap(id="GAP-USERS", lens="business", severity="high", status="CLOSED"),
        ]
        script = render_interview_script("DEMO", gaps)
        self.assertIn("## Blocking questions", script)
        self.assertIn("## Follow-up questions", script)
        self.assertLess(script.index("## Blocking questions"), script.index("## Follow-up questions"))
        # Blocking GAP-SCOPE appears before the medium follow-up GAP-QUALITY.
        self.assertLess(script.index("GAP-SCOPE"), script.index("GAP-QUALITY"))
        # Closed gaps are excluded from the script.
        self.assertNotIn("GAP-USERS", script)

    def test_probing_questions_only_when_local_evidence(self):
        with_evidence = _gap(id="GAP-METRIC-SOURCE", lens="business", severity="high", evidence_mention="signups")
        without_evidence = _gap(id="GAP-QUALITY", lens="quality", severity="medium")
        script = render_interview_script("DEMO", [with_evidence, without_evidence])
        # Cited gap gets probing questions citing its local mention.
        self.assertIn("Probing questions:", script)
        self.assertIn("Local citation: `signups`", script)
        # The un-cited gap gets no probing block (silence, never invents).
        quality_slice = script[script.index("GAP-QUALITY"):]
        self.assertNotIn("Probing questions:", quality_slice)

    def test_empty_when_no_open_gaps(self):
        self.assertIn("No open gaps", render_interview_script("DEMO", []))
        all_closed = [_gap(status="CLOSED")]
        self.assertIn("No open gaps", render_interview_script("DEMO", all_closed))

    def test_probing_is_derived_from_candidate_options_not_invented(self):
        gap = _gap(id="GAP-METRIC-SOURCE", lens="business", severity="high", evidence_mention="signups")
        probing = interview_probing_for_gap(gap)
        options = candidate_options_for_gap(gap)
        self.assertTrue(probing)
        self.assertEqual([p["text"] for p in probing], [o["text"] for o in options])
        self.assertEqual([p["citation"] for p in probing], [o["citation"] for o in options])
        # No local evidence => no probing (silence).
        self.assertEqual(interview_probing_for_gap(_gap(id="GAP-QUALITY")), [])


class InterviewExportLifecycleTests(unittest.TestCase):
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

    def test_export_writes_script_without_mutating_gaps(self):
        gaps_path = self.ws / "01_discovery" / "gaps.md"
        before = gaps_path.read_text(encoding="utf-8")
        self.assertEqual(main(["export", "DEMO", "--artifact", "gaps", "--format", "interview"]), 0)
        script_path = self.ws / "08_context_packs" / "exports" / "gaps-interview.md"
        self.assertTrue(script_path.exists())
        script = script_path.read_text(encoding="utf-8")
        self.assertIn("Interview Script - DEMO", script)
        self.assertLess(script.index("## Blocking questions"), script.index("## Follow-up questions"))
        self.assertIn("does NOT replace", script)
        # The canonical source of truth is untouched by the derived export.
        self.assertEqual(gaps_path.read_text(encoding="utf-8"), before)

    def test_build_interview_script_matches_export(self):
        self.assertEqual(main(["export", "DEMO", "--artifact", "gaps", "--format", "interview"]), 0)
        script_path = self.ws / "08_context_packs" / "exports" / "gaps-interview.md"
        self.assertEqual(build_interview_script("DEMO"), script_path.read_text(encoding="utf-8"))

    def test_interview_format_rejected_for_non_gaps_artifact(self):
        with self.assertRaises(RuntimeError) as ctx:
            export_interview("DEMO", "prd")
        self.assertIn("gaps", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
