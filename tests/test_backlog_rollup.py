from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from sentinel.cli import main
from sentinel.status import project_status
from sentinel.workspace import ensure_workspace, state_path, write_json


class BacklogRollupTests(unittest.TestCase):
    def setUp(self):
        self.old_cwd = Path.cwd()
        self.temp = Path(tempfile.mkdtemp())
        os.chdir(self.temp)
        self.ws = ensure_workspace("ROLL")
        (self.ws / "04_backlog").mkdir(parents=True, exist_ok=True)
        for story_id, epic_id, title in [
            ("US-001", "EPIC-001", "First value slice"),
            ("US-002", "EPIC-001", "Second value slice"),
            ("US-003", "EPIC-002", "Shared enabler"),
        ]:
            (self.ws / "04_backlog" / f"{story_id}.md").write_text(
                f"---\nid: {story_id}\nparent_epic: {epic_id}\nstatus: Draft\nowner: \"\"\n---\n\n# {story_id} - {title}\n",
                encoding="utf-8",
            )
        write_json(
            state_path("ROLL"),
            {
                "phase": "backlog_completed",
                "health": "CLEAN",
                "story_lifecycle": {
                    "US-001": {"status": "Ready", "owner": "BA"},
                    "US-002": {"status": "Done", "owner": "QA"},
                    "US-003": {"status": "Blocked", "owner": ""},
                },
                "story_gates": {
                    "US-001": {"dor": {"passed": True, "missing": []}, "dod": {"passed": False, "missing": ["Attach traced downstream acceptance evidence before treating the story as Done."]}},
                    "US-002": {"dor": {"passed": True, "missing": []}, "dod": {"passed": True, "missing": []}},
                    "US-003": {"dor": {"passed": False, "missing": ["Assign a human owner with /story-status --owner before treating the story as Ready."]}, "dod": {"passed": False, "missing": []}},
                },
            },
        )
        write_json(
            self.ws / "08_context_packs" / "implementation_readiness.json",
            {
                "stories": [
                    {"story_id": "US-001", "readiness_score": 1.0, "pending": [], "dependencies": [], "source_unit": "SPEC-U-001"},
                    {"story_id": "US-002", "readiness_score": 0.8, "pending": [], "dependencies": ["US-001"], "source_unit": "SPEC-U-002"},
                    {"story_id": "US-003", "readiness_score": 0.4, "pending": ["Pending domain context: Technology"], "dependencies": [], "source_unit": "SPEC-U-003"},
                ]
            },
        )

    def tearDown(self):
        os.chdir(self.old_cwd)
        shutil.rmtree(self.temp, ignore_errors=True)

    def test_backlog_status_writes_board_and_status_rollup(self):
        self.assertEqual(main(["backlog-status", "ROLL"]), 0)

        board = (self.ws / "04_backlog" / "BACKLOG.md").read_text(encoding="utf-8")
        self.assertIn("# Backlog Board - ROLL", board)
        self.assertIn("| EPIC-001 | 2 | 50.0% | 50.0%", board)
        self.assertIn("| EPIC-002 | 1 | 0.0% | 0.0%", board)
        self.assertIn("Pending domain context: Technology", board)
        self.assertIn("BA, QA", board)

        state = json.loads((self.ws / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(state["backlog_rollup"]["stories_total"], 3)
        self.assertEqual(state["backlog_rollup"]["status_counts"]["Ready"], 1)
        self.assertEqual(state["backlog_rollup"]["status_counts"]["Done"], 1)

        status = project_status("ROLL")
        self.assertEqual(status["backlog_rollup"]["stories_total"], 3)
        self.assertEqual(status["backlog_rollup"]["blocker_count"], 1)


if __name__ == "__main__":
    unittest.main()
