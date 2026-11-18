from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

from sentinel.cli import main

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import SnapshotWorkspaceCase, build_matured_workspace, gap_acceptance_answer, run_ok  # noqa: E402


RAW = """# Operations Risk Dashboard

Objective: let operations leads review risk queues before the daily meeting.

Users: operations leads.

In scope: read-only risk dashboard for open queues.
"""

EARS = "When queue metrics are available, the system shall display open risk queues."


class ImplementationFeedbackTests(SnapshotWorkspaceCase):
    @classmethod
    def build_workspace(cls) -> None:
        ws = build_matured_workspace("IFB", RAW, gap_acceptance_answer(EARS), backlog=False)
        (ws / "00_raw" / "02_technology_context" / "tech.md").write_text(
            "Execution commands: run pytest. Critical surfaces: risk dashboard module and queue metrics API. "
            "Engineering practices: preserve trace IDs and validate queue failures.",
            encoding="utf-8",
        )
        (ws / "00_raw" / "04_quality_context" / "quality.md").write_text(
            "Quality evidence: fail-to-pass, pass-to-pass and acceptance evidence must cover queue metrics.",
            encoding="utf-8",
        )
        run_ok(["reindex", "IFB"])
        run_ok(["backlog", "IFB"])

    def setUp(self) -> None:
        super().setUp()
        self.ws = self.temp / "workspaces" / "IFB"

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
            4,  # IMP-302: gate refusal
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

        self.assertEqual(main(["implementation-feedback", "IFB", "--source", str(source)]), 3)  # IMP-302: invalid input
        report = (self.ws / "07_changes" / "05_implementation_feedback" / "feedback_report.md").read_text(encoding="utf-8")
        self.assertIn("story does not exist", report)
        self.assertFalse((self.ws / "04_backlog" / "US-999.md").exists())

    def _state(self) -> dict:
        return json.loads((self.ws / "state.json").read_text(encoding="utf-8"))

    @staticmethod
    def _gap_finding(summary: str, **extra: object) -> dict:
        return {
            "type": "gap",
            "story": "US-001",
            "summary": summary,
            "evidence": "Downstream test run: " + summary,
            **extra,
        }

    def test_default_ids_continue_after_earlier_runs_and_gaps_accumulate(self) -> None:
        # IMP-367: positional defaults made a second run reuse IFB-001 / GAP-FEEDBACK-001
        # and overwrite the first finding; write_text dropped the earlier gap row.
        first = self._source({"findings": [self._gap_finding("Queue detail source is missing.")]})
        self.assertEqual(main(["implementation-feedback", "IFB", "--source", str(first)]), 0)
        second = self._source({"findings": [self._gap_finding("Queue export format is undefined.")]})
        self.assertEqual(main(["implementation-feedback", "IFB", "--source", str(second)]), 0)

        findings = self._state()["implementation_feedback"]["findings"]
        self.assertEqual(sorted(findings), ["IFB-001", "IFB-002"])
        self.assertEqual(findings["IFB-001"]["gap_id"], "GAP-FEEDBACK-001")
        self.assertEqual(findings["IFB-002"]["gap_id"], "GAP-FEEDBACK-002")
        self.assertIn("Queue detail source", findings["IFB-001"]["summary"])
        gaps = (self.ws / "01_discovery" / "implementation_feedback_gaps.md").read_text(encoding="utf-8")
        self.assertIn("`GAP-FEEDBACK-001`", gaps)
        self.assertIn("`GAP-FEEDBACK-002`", gaps)

    def test_explicit_ids_kept_and_resolved_gap_row_is_marked_not_deleted(self) -> None:
        opened = self._source({"findings": [
            self._gap_finding("Queue detail source is missing.", id="IFB-QUEUE", gap_id="GAP-FEEDBACK-QUEUE"),
            self._gap_finding("Queue export format is undefined."),
        ]})
        self.assertEqual(main(["implementation-feedback", "IFB", "--source", str(opened)]), 0)
        self.assertEqual(sorted(self._state()["implementation_feedback"]["findings"]), ["IFB-001", "IFB-QUEUE"])

        resolved = self._source({"findings": [
            self._gap_finding("Queue detail source added to the contract.", id="IFB-QUEUE",
                              gap_id="GAP-FEEDBACK-QUEUE", status="resolved"),
        ]})
        self.assertEqual(main(["implementation-feedback", "IFB", "--source", str(resolved)]), 0)
        gaps = (self.ws / "01_discovery" / "implementation_feedback_gaps.md").read_text(encoding="utf-8")
        rows = {line.split("|")[1].strip(): line for line in gaps.splitlines() if line.startswith("| `GAP-")}
        self.assertEqual(sorted(rows), ["`GAP-FEEDBACK-001`", "`GAP-FEEDBACK-QUEUE`"])
        self.assertIn("| RESOLVED |", rows["`GAP-FEEDBACK-QUEUE`"])
        self.assertIn("added to the contract", rows["`GAP-FEEDBACK-QUEUE`"])
        self.assertIn("| OPEN |", rows["`GAP-FEEDBACK-001`"])

    def test_resolving_by_finding_id_alone_resolves_its_gap(self) -> None:
        # IMP-370: without repeating gap_id, the resolution opened GAP-FEEDBACK-002 as RESOLVED
        # and left GAP-FEEDBACK-001 OPEN.
        opened = self._source({"findings": [self._gap_finding("Queue detail source is missing.")]})
        self.assertEqual(main(["implementation-feedback", "IFB", "--source", str(opened)]), 0)
        resolved = self._source({"findings": [
            self._gap_finding("Queue detail source added to the contract.", id="IFB-001", status="resolved"),
        ]})
        self.assertEqual(main(["implementation-feedback", "IFB", "--source", str(resolved)]), 0)
        findings = self._state()["implementation_feedback"]["findings"]
        self.assertEqual(findings["IFB-001"]["gap_id"], "GAP-FEEDBACK-001")
        gaps = (self.ws / "01_discovery" / "implementation_feedback_gaps.md").read_text(encoding="utf-8")
        rows = {line.split("|")[1].strip(): line for line in gaps.splitlines() if line.startswith("| `GAP-")}
        self.assertEqual(sorted(rows), ["`GAP-FEEDBACK-001`"])
        self.assertIn("| RESOLVED |", rows["`GAP-FEEDBACK-001`"])

    def test_health_is_recomputed_once_no_feedback_stays_open(self) -> None:
        # IMP-367: resolving every finding left health DIRTY until /health ran.
        from sentinel.health import run_health

        baseline = run_health("IFB")["verdict"]
        opened = self._source({"findings": [self._gap_finding("Queue detail source is missing.", id="IFB-QUEUE")]})
        self.assertEqual(main(["implementation-feedback", "IFB", "--source", str(opened)]), 0)
        self.assertEqual(self._state()["health"], "DIRTY")

        resolved = self._source({"findings": [
            self._gap_finding("Queue detail source added to the contract.", id="IFB-QUEUE", status="resolved"),
        ]})
        self.assertEqual(main(["implementation-feedback", "IFB", "--source", str(resolved)]), 0)
        state = self._state()
        self.assertEqual(state["implementation_feedback"]["open_by_story"], {})
        self.assertEqual(state["health"], baseline)
        self.assertEqual(state["health"], run_health("IFB")["verdict"])

    def test_health_stays_dirty_when_another_cause_remains(self) -> None:
        opened = self._source({"findings": [self._gap_finding("Queue detail source is missing.", id="IFB-QUEUE")]})
        self.assertEqual(main(["implementation-feedback", "IFB", "--source", str(opened)]), 0)
        # a Stale story is a separate DIRTY cause that resolving the feedback does not clear
        state_file = self.ws / "state.json"
        state = self._state()
        state.setdefault("story_lifecycle", {}).setdefault("US-001", {})["status"] = "Stale"
        state_file.write_text(json.dumps(state), encoding="utf-8")
        resolved = self._source({"findings": [
            self._gap_finding("Queue detail source added to the contract.", id="IFB-QUEUE", status="resolved"),
        ]})
        self.assertEqual(main(["implementation-feedback", "IFB", "--source", str(resolved)]), 0)
        self.assertEqual(self._state()["health"], "DIRTY")


if __name__ == "__main__":
    unittest.main()
