"""IMP-323: a refused command leaves nothing behind, and bad input is exit 3, not 1.

The independent review found that /compose, /refine-backlog and /implementation-feedback
archived the payload, wrote reports and state, and added graph nodes before refusing
("none accepted"); that a refused /resolve-gaps with a UTF-16 file left a copy that made
/health, /reindex and /sync fail until it was removed by hand; and that a payload with the
wrong shape or a folder passed as --source ended with exit 1 and a traceback.
"""
from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from sentinel.cli import main

RAW = """# Operations Risk Dashboard

Objective: let operations leads review risk queues before the daily meeting.

Users: operations leads.
"""


def quiet_main(argv: list[str]) -> int:
    import io
    from contextlib import redirect_stderr, redirect_stdout

    with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
        return main(argv)


class ValidateBeforeWriteTests(unittest.TestCase):
    def setUp(self):
        self.old_cwd = Path.cwd()
        self.temp = Path(tempfile.mkdtemp())
        os.chdir(self.temp)
        (self.temp / "raw.md").write_text(RAW, encoding="utf-8")
        self.assertEqual(quiet_main(["init", "VBW", "--brief-version", "1"]), 0)
        self.assertEqual(quiet_main(["ingest", "VBW", "--source", str(self.temp / "raw.md")]), 0)
        self.ws = self.temp / "workspaces" / "VBW"

    def tearDown(self):
        os.chdir(self.old_cwd)
        shutil.rmtree(self.temp, ignore_errors=True)

    def payload(self, name: str, data) -> Path:
        path = self.temp / name
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    def test_folder_as_source_is_invalid_input(self):
        folder = self.temp / "answers"
        folder.mkdir()
        self.assertEqual(quiet_main(["resolve-gaps", "VBW", "--source", str(folder)]), 3)

    def test_utf16_answers_are_refused_and_leave_nothing(self):
        path = self.temp / "answers.md"
        path.write_text("### GAP-ACCEPTANCE\n- Answer: yes\n", encoding="utf-16")
        self.assertEqual(quiet_main(["resolve-gaps", "VBW", "--source", str(path)]), 3)
        responses = self.ws / "07_changes" / "00_client_responses"
        self.assertEqual(list(responses.glob("*")) if responses.exists() else [], [])
        self.assertIn(quiet_main(["health", "VBW"]), (0, 5))

    def test_compose_with_a_list_root_is_invalid_input(self):
        prd = self.ws / "03_specs" / "prd.md"
        prd.parent.mkdir(parents=True, exist_ok=True)
        prd.write_text("# PRD\n\n## 1. Overview\n\nText.\n", encoding="utf-8")
        self.assertEqual(quiet_main(["compose", "VBW", "--source", str(self.payload("c.json", ["x"]))]), 3)

    def test_compose_with_nothing_accepted_writes_nothing(self):
        prd = self.ws / "03_specs" / "prd.md"
        prd.parent.mkdir(parents=True, exist_ok=True)
        prd.write_text("# PRD\n\n## 1. Overview\n\nText.\n", encoding="utf-8")
        before = prd.read_text(encoding="utf-8")
        bad = self.payload("c.json", {"blocks": [{"id": "COMP-1", "section": "99", "paragraphs": []}, "not a block"]})
        state_before = (self.ws / "state.json").read_text(encoding="utf-8")
        self.assertEqual(quiet_main(["compose", "VBW", "--source", str(bad)]), 3)
        compositions = self.ws / "03_specs" / "compositions"
        # Only the report of why each block was refused: no payload copy, no accepted blocks.
        self.assertEqual(sorted(p.name for p in compositions.iterdir()), ["composition_report.md"])
        self.assertIn("block must be an object", (compositions / "composition_report.md").read_text(encoding="utf-8"))
        self.assertEqual(prd.read_text(encoding="utf-8"), before)
        self.assertEqual((self.ws / "state.json").read_text(encoding="utf-8"), state_before)

    def test_refinement_with_nothing_accepted_writes_nothing(self):
        # Called directly: on this fake project the CLI's health gate refuses first (exit 4).
        from sentinel.backlog.refinement import BacklogRefinementError, apply_backlog_refinement

        epic = self.ws / "04_backlog" / "EPIC-001.md"
        epic.parent.mkdir(parents=True, exist_ok=True)
        epic.write_text("# EPIC-001\n", encoding="utf-8")
        bad = self.payload("r.json", {"proposals": [{"id": "BREF-1", "kind": "nonsense"}, 7]})
        with self.assertRaises(BacklogRefinementError):
            apply_backlog_refinement("VBW", bad)
        refinements = self.ws / "04_backlog" / "refinements"
        self.assertEqual(sorted(p.name for p in refinements.iterdir()), ["refinement_report.md"])
        self.assertEqual(epic.read_text(encoding="utf-8"), "# EPIC-001\n")

    def test_feedback_with_nothing_accepted_writes_nothing(self):
        epic = self.ws / "04_backlog" / "EPIC-001.md"
        epic.parent.mkdir(parents=True, exist_ok=True)
        epic.write_text("# EPIC-001\n", encoding="utf-8")
        bad = self.payload("f.json", {"findings": [{"id": "IFB-1"}]})
        self.assertEqual(quiet_main(["implementation-feedback", "VBW", "--source", str(bad)]), 3)
        feedback = self.ws / "07_changes" / "05_implementation_feedback"
        self.assertEqual(sorted(p.name for p in feedback.iterdir()), ["feedback_report.md"])
        self.assertFalse((self.ws / "01_discovery" / "implementation_feedback_gaps.md").exists())


if __name__ == "__main__":
    unittest.main()
