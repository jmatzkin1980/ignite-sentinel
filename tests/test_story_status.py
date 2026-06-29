from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from hashlib import sha256
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
        freeze = state["acceptance_criteria_freezes"]["US-001"]
        self.assertEqual(freeze["version"], 1)
        self.assertEqual(freeze["trigger"], "/story-status --set Ready")
        self.assertTrue(freeze["items"][0]["criterion"].startswith("Given "))
        story = (self.ws / "04_backlog" / "US-001.md").read_text(encoding="utf-8")
        self.assertIn("status: Ready", story)
        self.assertIn('owner: "Delivery Lead"', story)
        self.assertIn("## Lifecycle", story)
        graph = (self.ws / "06_traceability" / "traceability_graph.json").read_text(encoding="utf-8")
        self.assertIn('"type": "story_status_change"', graph)
        self.assertIn('"relation": "updates_story_status"', graph)
        board = (self.ws / "04_backlog" / "BACKLOG.md").read_text(encoding="utf-8")
        self.assertIn("# Backlog Board - STATUS", board)
        self.assertIn("| 1 | 1 | 100.0% | 0.0%", board)
        log = (self.ws / "06_traceability" / "command_protocol_log.md").read_text(encoding="utf-8")
        self.assertIn("`story-status`", log)
        self.assertFalse(state["story_gates"]["US-001"]["dor"]["passed"])
        self.assertTrue(state["story_gates"]["US-001"]["dor"]["missing"])

    def test_strict_backlog_gate_blocks_ready_when_dor_missing(self):
        config = self.ws / "sentinel.config.yaml"
        config.write_text(
            config.read_text(encoding="utf-8") + "\nbacklog_gate:\n  threshold: 1.0\n  strict: true\n",
            encoding="utf-8",
        )

        self.assertEqual(
            main(["story-status", "STATUS", "--story", "US-001", "--set", "Ready", "--owner", "Delivery Lead"]),
            1,
        )
        state = json.loads((self.ws / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(state["story_lifecycle"]["US-001"]["status"], "Draft")

    def test_dod_evidence_is_registered_and_traced(self):
        self.assertEqual(
            main(["story-status", "STATUS", "--story", "US-001", "--set", "Ready", "--owner", "Delivery Lead"]),
            0,
        )
        self.assertEqual(main(["story-status", "STATUS", "--story", "US-001", "--set", "In Progress"]), 0)
        self.assertEqual(main(["story-status", "STATUS", "--story", "US-001", "--set", "In Review"]), 0)
        evidence = self.temp / "acceptance.md"
        evidence.write_text("Fail-to-pass and pass-to-pass evidence for US-001 is green.", encoding="utf-8")

        self.assertEqual(
            main(["story-status", "STATUS", "--story", "US-001", "--set", "Done", "--evidence", str(evidence)]),
            0,
        )

        state = json.loads((self.ws / "state.json").read_text(encoding="utf-8"))
        entries = state["story_acceptance_evidence"]["US-001"]
        self.assertTrue(entries[0]["path"].startswith("04_backlog/acceptance_evidence/US-001-"))
        graph = (self.ws / "06_traceability" / "traceability_graph.json").read_text(encoding="utf-8")
        self.assertIn('"type": "story_acceptance_evidence"', graph)
        self.assertIn('"relation": "acceptance_evidence_for"', graph)

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

    def test_backlog_regeneration_records_acceptance_delta_after_freeze(self):
        self.assertEqual(
            main(["story-status", "STATUS", "--story", "US-001", "--set", "Ready", "--owner", "Delivery Lead"]),
            0,
        )
        state_path = self.ws / "state.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        frozen = state["acceptance_criteria_freezes"]["US-001"]["items"][0]
        frozen["criterion"] = "Given previous approved behavior, When backlog regenerates, Then the delta is explicit."
        fingerprint = f"{frozen['id']}\n{frozen['classification']}\n{frozen['criterion']}"
        frozen["hash"] = sha256(fingerprint.encode("utf-8")).hexdigest()
        state_path.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")

        self.assertEqual(main(["backlog", "STATUS"]), 0)

        report = (self.ws / "04_backlog" / "acceptance_criteria_deltas.md").read_text(encoding="utf-8")
        self.assertIn("changed", report)
        self.assertIn("previous approved behavior", report)
        self.assertIn("queue metrics", report)
        state = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertEqual(state["acceptance_criteria_deltas"][-1]["delta_count"], 1)
        graph = (self.ws / "06_traceability" / "traceability_graph.json").read_text(encoding="utf-8")
        self.assertIn('"type": "acceptance_criteria_delta"', graph)

    def test_story_with_domain_context_passes_dor(self):
        (self.ws / "00_raw" / "02_technology_context" / "tech.md").write_text(
            "Execution commands: run pytest. Critical surfaces: risk dashboard module and queue metrics API. "
            "Engineering practices: preserve trace IDs and validate queue failures.",
            encoding="utf-8",
        )
        (self.ws / "00_raw" / "04_quality_context" / "quality.md").write_text(
            "Quality evidence: fail-to-pass, pass-to-pass and acceptance evidence must cover queue metrics.",
            encoding="utf-8",
        )
        self.assertEqual(main(["reindex", "STATUS"]), 0)
        self.assertEqual(main(["backlog", "STATUS"]), 0)
        self.assertEqual(
            main(["story-status", "STATUS", "--story", "US-001", "--set", "Ready", "--owner", "Delivery Lead"]),
            0,
        )

        state = json.loads((self.ws / "state.json").read_text(encoding="utf-8"))
        self.assertTrue(state["story_gates"]["US-001"]["dor"]["passed"])
        story = (self.ws / "04_backlog" / "US-001.md").read_text(encoding="utf-8")
        self.assertIn("**DoR Gate:** Passed.", story)


if __name__ == "__main__":
    unittest.main()
