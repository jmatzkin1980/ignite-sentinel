from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from sentinel.cli import main
from sentinel.quality import evaluate_story_quality


RAW = """# Operations Risk Dashboard

Objective: let operations leads review risk queues before the daily meeting.

Users: operations leads.

In scope: read-only risk dashboard for open queues.
"""

EARS = "When queue metrics are available, the system shall display open risk queues."


class StoryQualityTests(unittest.TestCase):
    def setUp(self):
        self.old_cwd = Path.cwd()
        self.temp = Path(tempfile.mkdtemp())
        os.chdir(self.temp)

    def tearDown(self):
        os.chdir(self.old_cwd)
        shutil.rmtree(self.temp, ignore_errors=True)

    def test_invest_score_flags_layer_only_story(self):
        criteria = [
            {"id": "AC-001-01", "classification": "fail-to-pass", "text": "Given/When/Then"},
            {"id": "AC-001-02", "classification": "pass-to-pass", "text": "Regression"},
            {"id": "AC-001-03", "classification": "evidence", "text": "Evidence"},
        ]
        result = evaluate_story_quality(
            {"id": "US-900", "title": "Create database table"},
            "**Type:** value_story\n**Slicing Pattern:** Workflow Step / Happy Path\nCreate database table and repository.",
            criteria,
            {
                "story_id": "US-900",
                "type": "value_story",
                "source_unit": "SPEC-U-900",
                "slicing": "Workflow Step / Happy Path",
                "trace": ["SPEC-U-900", "REQ-EARS-900"],
                "dependencies": [],
            },
        )

        self.assertLess(result["score"], result["threshold"])
        self.assertEqual(result["status"], "FAIL")
        failed = {item["key"] for item in result["checks"] if not item["passed"]}
        self.assertIn("vertical_slice", failed)

    def test_quality_updates_audit_and_story_gate(self):
        raw = self.temp / "raw.md"
        raw.write_text(RAW, encoding="utf-8")
        self.assertEqual(main(["init", "QUAL"]), 0)
        self.assertEqual(main(["ingest", "QUAL", "--source", str(raw)]), 0)
        answers = self.temp / "answers.md"
        answers.write_text(
            "### GAP-ACCEPTANCE\n"
            f"- Answer: {EARS}\n"
            "- Owner / source: Client workshop\n"
            "- Evidence or reference: Synthetic EARS response\n"
            "- Decision status: confirmed\n",
            encoding="utf-8",
        )
        self.assertEqual(main(["resolve-gaps", "QUAL", "--source", str(answers)]), 0)
        self.assertEqual(main(["brief", "QUAL"]), 0)
        self.assertEqual(main(["specs", "QUAL"]), 0)
        ws = self.temp / "workspaces" / "QUAL"
        (ws / "00_raw" / "02_technology_context" / "tech.md").write_text(
            "Execution commands: run pytest. Critical surfaces: risk dashboard module and queue metrics API. "
            "Engineering practices: preserve trace IDs and validate queue failures.",
            encoding="utf-8",
        )
        (ws / "00_raw" / "04_quality_context" / "quality.md").write_text(
            "Quality evidence: fail-to-pass, pass-to-pass and acceptance evidence must cover queue metrics.",
            encoding="utf-8",
        )
        self.assertEqual(main(["reindex", "QUAL"]), 0)
        self.assertEqual(main(["backlog", "QUAL"]), 0)
        self.assertEqual(main(["story-status", "QUAL", "--story", "US-001", "--set", "Ready", "--owner", "Delivery Lead"]), 0)
        self.assertEqual(main(["quality", "QUAL"]), 0)

        state = json.loads((ws / "state.json").read_text(encoding="utf-8"))
        self.assertIn("US-001", state["story_quality"])
        self.assertGreaterEqual(state["story_quality"]["US-001"]["score"], 0.8)
        dor_keys = {item["key"] for item in state["story_gates"]["US-001"]["dor"]["items"]}
        self.assertIn("story_quality_invest", dor_keys)
        audit = (ws / "05_quality" / "backlog_readiness_audit.md").read_text(encoding="utf-8")
        self.assertIn("INVEST/SPIDR Score", audit)
        self.assertIn("story_quality_invest", json.dumps(state["story_gates"]["US-001"], ensure_ascii=False))


if __name__ == "__main__":
    unittest.main()
