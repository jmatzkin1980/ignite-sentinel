"""IMP-325: one verdict of "ready", and a /next that never sends the BA in circles.

The independent review found /next repeating /quality forever (the stage never moves after
/quality), sending a DIRTY project to /backlog or /quality (which refuse it), ignoring a
deleted brief past /brief, and saying "Waiting for client answers" when the BA had assumed
the answer, with no word on how to move on. It also found /status saying READY_WITH_WARNINGS
while the brief v2 said "Ready to build: no".
"""
from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from pathlib import Path

from sentinel.cli import main
from sentinel.readiness_verdict import brief_ready_to_build, next_step

RAW = """# Operations Risk Dashboard

Objective: let operations leads review risk queues before the daily meeting.
"""


def quiet(argv):
    import io
    from contextlib import redirect_stderr, redirect_stdout

    with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
        return main(argv)


class NextStepTests(unittest.TestCase):
    def setUp(self):
        self.old_cwd = Path.cwd()
        self.temp = Path(tempfile.mkdtemp())
        os.chdir(self.temp)
        (self.temp / "raw.md").write_text(RAW, encoding="utf-8")
        self.assertEqual(quiet(["init", "NXT", "--brief-version", "1"]), 0)
        self.assertEqual(quiet(["ingest", "NXT", "--source", str(self.temp / "raw.md")]), 0)
        self.verdict = {"counts": {"total": 3, "open": 0}, "blocking_open": []}

    def tearDown(self):
        os.chdir(self.old_cwd)
        shutil.rmtree(self.temp, ignore_errors=True)

    def key(self, state, **kwargs):
        options = {"has_stories": True, "has_brief": True}
        options.update(kwargs)
        return next_step("NXT", state, self.verdict, **options)

    def test_after_quality_the_next_step_is_handoff(self):
        state = {"readiness_stage": "READY_FOR_BACKLOG", "phase": "quality_completed", "health": "CLEAN"}
        self.assertEqual(self.key(state)["key"], "handoff")

    def test_before_quality_it_is_still_quality(self):
        state = {"readiness_stage": "READY_FOR_BACKLOG", "phase": "backlog_completed", "health": "CLEAN"}
        self.assertEqual(self.key(state)["key"], "quality")

    def test_dirty_project_is_sent_to_health(self):
        state = {"readiness_stage": "READY_FOR_BACKLOG", "phase": "specs_completed", "health": "DIRTY"}
        self.assertEqual(self.key(state, has_stories=False)["key"], "health")

    def test_deleted_brief_past_brief_is_named(self):
        state = {"readiness_stage": "READY_FOR_SPECS", "phase": "brief_completed", "health": "CLEAN"}
        self.assertEqual(self.key(state, has_brief=False)["key"], "brief_missing")

    def test_assumed_blocking_gap_explains_the_exit(self):
        self.verdict["blocking_open"] = ["GAP-SCOPE"]
        state = {"readiness_stage": "CLIENT_RESPONSE_NEEDED", "phase": "discovery_completed"}
        step = self.key(state, assumed_blocking=["GAP-SCOPE"])
        self.assertEqual(step["key"], "resolve_blocking")
        self.assertIn("never unblocks", step["text"])
        self.assertIn("/resolve-gaps", step["text"])

    def test_non_blocking_gaps_name_specs(self):
        self.verdict["counts"] = {"total": 3, "open": 2}
        state = {"readiness_stage": "READY_FOR_PROJECT_BRIEF", "phase": "gaps_resolved"}
        self.assertIn("/specs", self.key(state)["text"])


class ReadyToBuildTests(unittest.TestCase):
    def setUp(self):
        self.temp = Path(tempfile.mkdtemp())
        (self.temp / "02_requirements").mkdir()

    def tearDown(self):
        shutil.rmtree(self.temp, ignore_errors=True)

    def brief(self, text):
        (self.temp / "02_requirements" / "project-brief.md").write_text(text, encoding="utf-8")
        return brief_ready_to_build(self.temp)

    def test_english_no(self):
        result = self.brief("# Brief\n\n> Ready to build: no. 15 pending marks block (§7).\n")
        self.assertIs(result["ready"], False)
        self.assertIn("15 pending marks", result["line"])

    def test_spanish_yes(self):
        self.assertIs(self.brief("Listo para construir: sí. Ninguna marca pendiente bloquea.\n")["ready"], True)

    def test_v1_brief_has_no_line(self):
        self.assertIsNone(self.brief("# Project Brief\n\nNo such line.\n"))


if __name__ == "__main__":
    unittest.main()
