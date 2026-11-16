"""IMP-320: a second /ingest must not silently reset a project.

Before this item, /ingest on a workspace that already had its primary requirement rewrote
requirements.md, gaps.md, decisions.md and the identity seeds from the new file: every
closed gap went back to open, the verdict fell back, and the command exited 0. The guide
told users to load each further file that way. Now /ingest refuses (exit 4) and points to
/sync --source, which adds a file without resetting; --replace replaces the primary
requirement on purpose and says how many answered gaps are reopened and how to re-apply
the saved answers.
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import SnapshotWorkspaceCase, run_cli, run_ok  # noqa: E402

PROJECT = "REING"

RAW = """# Operations Risk Dashboard

Objective: let operations leads review risk queues before the daily meeting.

Users: operations leads.

Scope: a read-only dashboard for the current quarter.
"""

CONTEXT = """# Business context

The operations team works in two shifts and reviews queues at 9:00 and 15:00.
"""

ANSWERS = """# Answers

### GAP-ACCEPTANCE
- Answer: When a queue has cases above the SLA threshold, the dashboard shall mark the queue as high risk.
- Owner / source: Client workshop
- Evidence or reference: Synthetic workshop notes
- Decision status: confirmed
"""


class ReingestGuardTests(SnapshotWorkspaceCase):
    @classmethod
    def build_workspace(cls) -> None:
        root = Path.cwd()
        (root / "raw.md").write_text(RAW, encoding="utf-8")
        (root / "context.md").write_text(CONTEXT, encoding="utf-8")
        (root / "answers.md").write_text(ANSWERS, encoding="utf-8")
        run_ok(["init", PROJECT, "--brief-version", "1"])
        run_ok(["ingest", PROJECT, "--source", str(root / "raw.md")])
        run_ok(["resolve-gaps", PROJECT, "--source", str(root / "answers.md")])

    def gaps_text(self) -> str:
        return (self.temp / "workspaces" / PROJECT / "01_discovery" / "gaps.md").read_text(encoding="utf-8")

    def test_second_ingest_is_refused_and_changes_nothing(self):
        before = self.gaps_text()
        requirements = self.temp / "workspaces" / PROJECT / "02_requirements" / "requirements.md"
        req_before = requirements.read_text(encoding="utf-8")
        code, _ = run_cli(["ingest", PROJECT, "--source", str(self.temp / "context.md")])
        self.assertEqual(code, 4)
        self.assertEqual(self.gaps_text(), before)
        self.assertEqual(requirements.read_text(encoding="utf-8"), req_before)

    def test_refusal_points_to_sync_and_to_replace(self):
        import io
        from contextlib import redirect_stderr, redirect_stdout

        from sentinel.cli import main

        err = io.StringIO()
        with redirect_stdout(io.StringIO()), redirect_stderr(err):
            main(["ingest", PROJECT, "--source", str(self.temp / "context.md")])
        message = err.getvalue()
        self.assertIn(f"/sync {PROJECT} --source", message)
        self.assertIn("--replace", message)

    def test_sync_adds_the_file_and_keeps_the_answer(self):
        self.assertIn("GAP-ACCEPTANCE", self.gaps_text())
        run_ok(["sync", PROJECT, "--source", str(self.temp / "context.md")])
        text = self.gaps_text()
        block = text.split("### GAP-ACCEPTANCE", 1)[1].split("### ", 1)[0]
        self.assertNotIn("Status: `OPEN`", block)

    def test_replace_reports_reopened_answers_and_how_to_reapply(self):
        out = run_ok(["ingest", PROJECT, "--source", str(self.temp / "context.md"), "--replace"])
        result = json.loads(out)
        replaced = result["replaced"]
        self.assertGreaterEqual(replaced["answered_gaps_reopened"], 1)
        self.assertTrue(any("answers.md" in path for path in replaced["saved_answers"]))
        self.assertIn("/resolve-gaps", replaced["next_step"])


if __name__ == "__main__":
    unittest.main()
