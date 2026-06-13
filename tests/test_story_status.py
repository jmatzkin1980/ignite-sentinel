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

In scope: read-only risk dashboard for open queues.
"""

EARS = "When queue metrics are available, the system shall display open risk queues."


class StoryStatusTests(unittest.TestCase):
    def setUp(self):
        self.old_cwd = Path.cwd()
        self.temp = Path(tempfile.mkdtemp())
        os.chdir(self.temp)
        raw = self.temp / "raw.md"
        raw.write_text(RAW, encoding="utf-8")
        self.assertEqual(main(["init", "STATUS"]), 0)
        self.assertEqual(main(["ingest", "STATUS", "--source", str(raw)]), 0)
        answers = self.temp / "answers.md"
        answers.write_text(
            "### GAP-ACCEPTANCE\n"
            f"- Answer: {EARS}\n"
            "- Owner / source: Client workshop\n"
            "- Evidence or reference: Synthetic EARS response\n"
            "- Decision status: confirmed\n",
            encoding="utf-8",
        )
        self.assertEqual(main(["resolve-gaps", "STATUS", "--source", str(answers)]), 0)
        self.assertEqual(main(["brief", "STATUS"]), 0)
        self.assertEqual(main(["specs", "STATUS"]), 0)
        self.assertEqual(main(["backlog", "STATUS"]), 0)
        self.ws = self.temp / "workspaces" / "STATUS"

    def tearDown(self):
        os.chdir(self.old_cwd)
        shutil.rmtree(self.temp, ignore_errors=True)

    def test_story_status_updates_state_frontmatter_and_trace(self):
        self.assertEqual(
            main(["story-status", "STATUS", "--story", "US-001", "--set", "Ready", "--owner", "Delivery Lead"]),
            0,
        )

        state = json.loads((self.ws / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(state["story_lifecycle"]["US-001"]["status"], "Ready")
        self.assertEqual(state["story_lifecycle"]["US-001"]["owner"], "Delivery Lead")
        story = (self.ws / "04_backlog" / "US-001.md").read_text(encoding="utf-8")
        self.assertIn("status: Ready", story)
        self.assertIn('owner: "Delivery Lead"', story)
        self.assertIn("## Lifecycle", story)
        graph = (self.ws / "06_traceability" / "traceability_graph.json").read_text(encoding="utf-8")
        self.assertIn('"type": "story_status_change"', graph)
        self.assertIn('"relation": "updates_story_status"', graph)
        log = (self.ws / "06_traceability" / "command_protocol_log.md").read_text(encoding="utf-8")
        self.assertIn("`story-status`", log)

    def test_story_status_rejects_illegal_transition(self):
        self.assertEqual(main(["story-status", "STATUS", "--story", "US-001", "--set", "Done"]), 1)
        state = json.loads((self.ws / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(state["story_lifecycle"]["US-001"]["status"], "Draft")

    def test_backlog_regeneration_preserves_story_lifecycle(self):
        self.assertEqual(
            main(["story-status", "STATUS", "--story", "US-001", "--set", "Ready", "--owner", "Delivery Lead"]),
            0,
        )
        self.assertEqual(main(["backlog", "STATUS"]), 0)

        state = json.loads((self.ws / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(state["story_lifecycle"]["US-001"]["status"], "Ready")
        self.assertEqual(state["story_lifecycle"]["US-001"]["owner"], "Delivery Lead")
        story = (self.ws / "04_backlog" / "US-001.md").read_text(encoding="utf-8")
        self.assertIn("status: Ready", story)
        self.assertIn('owner: "Delivery Lead"', story)
        readiness = json.loads((self.ws / "08_context_packs" / "implementation_readiness.json").read_text(encoding="utf-8"))
        self.assertEqual(readiness["stories"][0]["story_status"], "Ready")
        self.assertEqual(readiness["stories"][0]["owner"], "Delivery Lead")


if __name__ == "__main__":
    unittest.main()
