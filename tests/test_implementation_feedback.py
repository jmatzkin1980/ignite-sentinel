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


class ImplementationFeedbackTests(unittest.TestCase):
    def setUp(self) -> None:
        self.old_cwd = Path.cwd()
        self.temp = Path(tempfile.mkdtemp())
        os.chdir(self.temp)
        raw = self.temp / "raw.md"
        raw.write_text(RAW, encoding="utf-8")
        self.assertEqual(main(["init", "IFB"]), 0)
        self.assertEqual(main(["ingest", "IFB", "--source", str(raw)]), 0)
        answers = self.temp / "answers.md"
        answers.write_text(
            "### GAP-ACCEPTANCE\n"
            f"- Answer: {EARS}\n"
            "- Owner / source: Client workshop\n"
            "- Evidence or reference: Synthetic EARS response\n"
            "- Decision status: confirmed\n",
            encoding="utf-8",
        )
        self.assertEqual(main(["resolve-gaps", "IFB", "--source", str(answers)]), 0)
        self.assertEqual(main(["brief", "IFB"]), 0)
        self.assertEqual(main(["specs", "IFB"]), 0)
        self.ws = self.temp / "workspaces" / "IFB"
        (self.ws / "00_raw" / "02_technology_context" / "tech.md").write_text(
            "Execution commands: run pytest. Critical surfaces: risk dashboard module and queue metrics API. "
            "Engineering practices: preserve trace IDs and validate queue failures.",
            encoding="utf-8",
        )
        (self.ws / "00_raw" / "04_quality_context" / "quality.md").write_text(
            "Quality evidence: fail-to-pass, pass-to-pass and acceptance evidence must cover queue metrics.",
            encoding="utf-8",
        )
        self.assertEqual(main(["reindex", "IFB"]), 0)
        self.assertEqual(main(["backlog", "IFB"]), 0)

    def tearDown(self) -> None:
        os.chdir(self.old_cwd)
        shutil.rmtree(self.temp, ignore_errors=True)

    def _source(self, payload: dict) -> Path:
        path = self.temp / "implementation-feedback.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def test_feedback_opens_gap_marks_story_stale_and_blocks_dod(self) -> None:
        source = self._source(
            {
                "findings": [
                    {
                        "id": "IFB-001",
                        "type": "gap",
                        "gap_id": "GAP-FEEDBACK-QUEUE-DETAIL",
                        "story": "US-001",
                        "acceptance_criteria": "AC-001-01",
                        "source_units": ["SPEC-U-001"],
                        "summary": "Implementation found that the queue detail dependency is not covered by the story contract.",
                        "evidence": "Queue detail test fails because the risk indicator source is not in the handoff contract.",
                        "source": "implementation test run",
                        "mark_stale": True,
                    }
                ]
            }
        )

        self.assertEqual(main(["implementation-feedback", "IFB", "--source", str(source)]), 0)

        state = json.loads((self.ws / "state.json").read_text(encoding="utf-8"))
        finding = state["implementation_feedback"]["findings"]["IFB-001"]
        self.assertEqual(finding["story_id"], "US-001")
        self.assertEqual(finding["gap_id"], "GAP-FEEDBACK-QUEUE-DETAIL")
        self.assertEqual(state["story_lifecycle"]["US-001"]["status"], "Stale")
        self.assertEqual(state["implementation_feedback"]["open_by_story"]["US-001"], ["IFB-001"])
        report = (self.ws / "07_changes" / "05_implementation_feedback" / "feedback_report.md").read_text(encoding="utf-8")
        self.assertIn("IFB-001", report)
        gap_report = (self.ws / "01_discovery" / "implementation_feedback_gaps.md").read_text(encoding="utf-8")
        self.assertIn("GAP-FEEDBACK-QUEUE-DETAIL", gap_report)
        graph = (self.ws / "06_traceability" / "traceability_graph.json").read_text(encoding="utf-8")
        self.assertIn('"type": "implementation_feedback"', graph)
        self.assertIn('"type": "implementation_feedback_gap"', graph)
        self.assertIn('"relation": "feedback_from_implementation"', graph)

        evidence = self.temp / "evidence.md"
        evidence.write_text("Downstream acceptance evidence is present but feedback remains open.", encoding="utf-8")
        self.assertEqual(main(["story-status", "IFB", "--story", "US-001", "--set", "Draft"]), 0)
        self.assertEqual(main(["story-status", "IFB", "--story", "US-001", "--set", "Ready", "--owner", "Delivery Lead"]), 0)
        self.assertEqual(main(["story-status", "IFB", "--story", "US-001", "--set", "In Progress"]), 0)
        self.assertEqual(main(["story-status", "IFB", "--story", "US-001", "--set", "In Review"]), 0)
        config = self.ws / "sentinel.config.yaml"
        config.write_text(
            config.read_text(encoding="utf-8") + "\nbacklog_gate:\n  threshold: 1.0\n  strict: true\n",
            encoding="utf-8",
        )
        self.assertEqual(
            main(["story-status", "IFB", "--story", "US-001", "--set", "Done", "--evidence", str(evidence)]),
            1,
        )

    def test_feedback_rejects_unknown_story_without_rewriting_backlog(self) -> None:
        source = self._source(
            {
                "findings": [
                    {
                        "type": "new-dependency",
                        "story": "US-999",
                        "summary": "Unknown story should be rejected.",
                        "evidence": "Downstream note names a story outside the backlog.",
                    }
                ]
            }
        )

        self.assertEqual(main(["implementation-feedback", "IFB", "--source", str(source)]), 1)
        report = (self.ws / "07_changes" / "05_implementation_feedback" / "feedback_report.md").read_text(encoding="utf-8")
        self.assertIn("story does not exist", report)
        self.assertFalse((self.ws / "04_backlog" / "US-999.md").exists())


if __name__ == "__main__":
    unittest.main()
