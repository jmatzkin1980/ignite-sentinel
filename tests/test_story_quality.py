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

Objective: operations leads review risk queues before the daily meeting.

Users: operations leads.

In scope: read-only risk dashboard for open queues.
"""

EARS = "When queue metrics are available, the system shall display open risk queues."


class StoryQualityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.old_cwd = Path.cwd()
        self.temp = Path(tempfile.mkdtemp())
        os.chdir(self.temp)

    def tearDown(self) -> None:
        os.chdir(self.old_cwd)
        shutil.rmtree(self.temp, ignore_errors=True)

    def test_invest_score_flags_layer_only_story(self) -> None:
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

    def test_parallel_invest_audit_flags_explicit_story_dependency_without_changing_score(self) -> None:
        criteria = [
            {"id": "AC-002-01", "classification": "fail-to-pass", "text": "Happy path"},
            {"id": "AC-002-02", "classification": "pass-to-pass", "text": "Regression"},
            {"id": "AC-002-03", "classification": "evidence", "text": "Evidence"},
        ]
        result = evaluate_story_quality(
            {"id": "US-901", "title": "Review risk dashboard queues"},
            "**Type:** value_story\n**Slicing Pattern:** Workflow Step / Happy Path\nWhen metrics are ready, show open risk queues and let operations leads filter by severity.",
            criteria,
            {
                "story_id": "US-901",
                "type": "value_story",
                "source_unit": "SPEC-U-901",
                "slicing": "Workflow Step / Happy Path",
                "trace": ["SPEC-U-901", "REQ-EARS-901"],
                "dependencies": ["US-099"],
            },
        )

        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["score"], 1.0)
        self.assertFalse(result["invest_audit"]["I"]["passed"])
        self.assertEqual(result["invest_audit"]["I"]["evidence"]["dependencies"], ["US-099"])
        self.assertEqual(result["invest_audit_summary"], {"passed": 5, "total": 6})

    def test_quality_updates_audit_and_story_gate(self) -> None:
        raw = self.temp / "raw.md"
        raw.write_text(RAW, encoding="utf-8")
        self.assertEqual(main(["init", "QUAL"]), 0)
        self.assertEqual(main(["ingest", "QUAL", "--source", str(raw)]), 0)
        answers = self.temp / "answers.md"
        answers.write_text(
            "### GAP-ACCEPTANCE\n"
            f"- Answer: {EARS}\n"
            "- Owner / source: Client workshop\n"
            "- Evidence reference: Synthetic EARS response\n"
            "- Decision status: confirmed\n",
            encoding="utf-8",
        )
        self.assertEqual(main(["resolve-gaps", "QUAL", "--source", str(answers)]), 0)
        self.assertEqual(main(["brief", "QUAL"]), 0)
        self.assertEqual(main(["specs", "QUAL"]), 0)
        ws = self.temp / "workspaces" / "QUAL"
        (ws / "00_raw" / "02_technology_context" / "tech.md").write_text(
            "Execution commands: run pytest. Critical surfaces: risk dashboard module queue metrics API. "
            "Engineering practices: preserve trace IDs and validate queue failures.",
            encoding="utf-8",
        )
        (ws / "00_raw" / "04_quality_context" / "quality.md").write_text(
            "Quality evidence: fail-to-pass, pass-to-pass, and acceptance evidence cover queue metrics.",
            encoding="utf-8",
        )
        self.assertEqual(main(["reindex", "QUAL"]), 0)
        self.assertEqual(main(["backlog", "QUAL"]), 0)
        self.assertEqual(main(["story-status", "QUAL", "--story", "US-001", "--set", "Ready", "--owner", "Delivery Lead"]), 0)
        self.assertEqual(main(["quality", "QUAL"]), 0)

        state = json.loads((ws / "state.json").read_text(encoding="utf-8"))
        self.assertIn("US-001", state["story_quality"])
        self.assertGreaterEqual(state["story_quality"]["US-001"]["score"], 0.8)
        self.assertIn("invest_audit", state["story_quality"]["US-001"])
        self.assertEqual(state["story_quality"]["US-001"]["invest_audit_summary"]["total"], 6)
        dor_keys = {item["key"] for item in state["story_gates"]["US-001"]["dor"]["items"]}
        self.assertIn("story_quality_invest", dor_keys)
        audit = (ws / "05_quality" / "backlog_readiness_audit.md").read_text(encoding="utf-8")
        self.assertIn("INVEST/SPIDR Score", audit)
        self.assertIn("Parallel INVEST Audit", audit)
        self.assertIn("| I | Independent |", audit)
        self.assertIn("story_quality_invest", json.dumps(state["story_gates"]["US-001"], ensure_ascii=False))


if __name__ == "__main__":
    unittest.main()
