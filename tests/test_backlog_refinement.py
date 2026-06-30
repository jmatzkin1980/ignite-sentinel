"""Tests for IMP-059 sanctioned backlog refinement."""
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

In scope: read-only risk dashboard for open queues. Out of scope: editing cases.

Metric: reduce manual preparation by 30 percent in the first release month.
"""

EARS = "When queue metrics are available, the system shall display open risk queues."


class BacklogRefinementTests(unittest.TestCase):
    def setUp(self):
        self.old_cwd = Path.cwd()
        self.temp = Path(tempfile.mkdtemp())
        os.chdir(self.temp)
        self.raw = self.temp / "raw.md"
        self.raw.write_text(RAW, encoding="utf-8")
        self.assertEqual(main(["init", "BREF"]), 0)
        self.assertEqual(main(["ingest", "BREF", "--source", str(self.raw)]), 0)
        answer = self.temp / "answers.md"
        answer.write_text(
            "### GAP-ACCEPTANCE\n"
            f"- Answer: {EARS}\n"
            "- Owner / source: Client workshop\n"
            "- Evidence or reference: Synthetic EARS response\n"
            "- Decision status: confirmed\n",
            encoding="utf-8",
        )
        self.assertEqual(main(["resolve-gaps", "BREF", "--source", str(answer)]), 0)
        self.assertEqual(main(["brief", "BREF"]), 0)
        self.assertEqual(main(["specs", "BREF"]), 0)
        self.assertEqual(main(["backlog", "BREF"]), 0)
        self.ws = self.temp / "workspaces" / "BREF"

    def tearDown(self):
        os.chdir(self.old_cwd)
        shutil.rmtree(self.temp, ignore_errors=True)

    def _draft(self, payload: dict) -> Path:
        path = self.temp / "refine.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def test_valid_refinement_merges_origin_agent_proposal(self):
        draft = {
            "proposals": [
                {
                    "id": "BREF-001",
                    "kind": "reslice",
                    "target_stories": ["US-001"],
                    "source_units": ["SPEC-U-001"],
                    "slicing_pattern": "Data / External Dependency",
                    "recommendation": "Keep this story focused on the confirmed queue metrics dependency.",
                    "rationale": "The Spec Unit names queue metrics as the observable trigger and response.",
                    "citations": [EARS],
                }
            ]
        }

        self.assertEqual(main(["refine-backlog", "BREF", "--source", str(self._draft(draft))]), 0)

        epic = (self.ws / "04_backlog" / "EPIC-001.md").read_text(encoding="utf-8")
        story = (self.ws / "04_backlog" / "US-001.md").read_text(encoding="utf-8")
        self.assertIn("## Agent Backlog Refinements", epic)
        self.assertIn("Origin: agent", epic)
        self.assertIn("BREF-001", story)
        report = (self.ws / "04_backlog" / "refinements" / "refinement_report.md").read_text(encoding="utf-8")
        self.assertIn("BREF-001", report)
        accepted = json.loads((self.ws / "04_backlog" / "refinements" / "accepted_refinements.json").read_text(encoding="utf-8"))
        self.assertEqual(accepted[0]["origin"], "agent")
        graph = (self.ws / "06_traceability" / "traceability_graph.json").read_text(encoding="utf-8")
        self.assertIn('"type": "backlog_refinement"', graph)
        self.assertIn('"relation": "refined_by"', graph)
        self.assertIn('"relation": "proposes_refinement_for"', graph)

    def test_refinement_rejects_fabricated_citation(self):
        draft = {
            "proposals": [
                {
                    "kind": "reslice",
                    "target_stories": ["US-001"],
                    "source_units": ["SPEC-U-001"],
                    "recommendation": "Unsupported recommendation.",
                    "rationale": "Unsupported rationale.",
                    "citations": ["not present in local evidence"],
                }
            ]
        }

        self.assertEqual(main(["refine-backlog", "BREF", "--source", str(self._draft(draft))]), 1)
        report = (self.ws / "04_backlog" / "refinements" / "refinement_report.md").read_text(encoding="utf-8")
        self.assertIn("citation not found verbatim", report)

    def test_refinement_accepts_measurable_enabler_candidate(self):
        draft = {
            "proposals": [
                {
                    "id": "BREF-EN-001",
                    "kind": "enabler-candidate",
                    "target_stories": ["US-001"],
                    "source_units": ["SPEC-U-001"],
                    "enables_stories": ["US-001"],
                    "supports_boundary": "Risk dashboard open-queue rendering depends on confirmed queue metrics freshness.",
                    "enabled_capability": "Risk dashboard can render open queues only when queue metrics freshness is confirmed.",
                    "verification_method": "Run a backlog acceptance fixture with current queue metrics and stale queue metrics.",
                    "risk_reduced": "Prevents implementing queue views without a measurable freshness contract.",
                    "objective_evidence": "Acceptance evidence includes current and stale queue metric fixture results.",
                    "recommendation": "Add a cross-cutting queue metrics freshness enabler.",
                    "rationale": "The Spec Unit names queue metrics as the observable trigger for the dashboard.",
                    "citations": [EARS],
                }
            ]
        }

        self.assertEqual(main(["refine-backlog", "BREF", "--source", str(self._draft(draft))]), 0)

        accepted = json.loads(
            (self.ws / "04_backlog" / "refinements" / "accepted_refinements.json").read_text(encoding="utf-8")
        )
        self.assertEqual(accepted[0]["enabled_capability"], draft["proposals"][0]["enabled_capability"])
        self.assertEqual(accepted[0]["verification_method"], draft["proposals"][0]["verification_method"])
        epic = (self.ws / "04_backlog" / "EPIC-001.md").read_text(encoding="utf-8")
        self.assertIn("Enabled capability / Capacidad habilitada", epic)
        self.assertIn("Verification / Verificacion", epic)

    def test_refinement_rejects_enabler_without_verification_method(self):
        draft = {
            "proposals": [
                {
                    "kind": "enabler-candidate",
                    "target_stories": ["US-001"],
                    "source_units": ["SPEC-U-001"],
                    "enables_stories": ["US-001"],
                    "supports_boundary": "Risk dashboard open-queue rendering depends on confirmed queue metrics freshness.",
                    "enabled_capability": "Risk dashboard can render open queues only when queue metrics freshness is confirmed.",
                    "risk_reduced": "Prevents implementing queue views without a measurable freshness contract.",
                    "objective_evidence": "Acceptance evidence includes current and stale queue metric fixture results.",
                    "recommendation": "Add a cross-cutting queue metrics freshness enabler.",
                    "rationale": "The Spec Unit names queue metrics as the observable trigger for the dashboard.",
                    "citations": [EARS],
                }
            ]
        }

        self.assertEqual(main(["refine-backlog", "BREF", "--source", str(self._draft(draft))]), 1)
        report = (self.ws / "04_backlog" / "refinements" / "refinement_report.md").read_text(encoding="utf-8")
        self.assertIn("requires verification_method", report)

    def test_refinement_rejects_loose_enabler_boundary(self):
        draft = {
            "proposals": [
                {
                    "kind": "enabler-candidate",
                    "target_stories": ["US-001"],
                    "source_units": ["SPEC-U-001"],
                    "enables_stories": ["US-001"],
                    "supports_boundary": "Generic setup so the internal tool accessible precondition is met.",
                    "enabled_capability": "Risk dashboard can render open queues only when queue metrics freshness is confirmed.",
                    "verification_method": "Run a backlog acceptance fixture with current queue metrics and stale queue metrics.",
                    "risk_reduced": "Generic environment availability.",
                    "objective_evidence": "Environment available.",
                    "recommendation": "Create a broad setup enabler.",
                    "rationale": "This is only a loose precondition.",
                    "citations": [EARS],
                }
            ]
        }

        self.assertEqual(main(["refine-backlog", "BREF", "--source", str(self._draft(draft))]), 1)
        report = (self.ws / "04_backlog" / "refinements" / "refinement_report.md").read_text(encoding="utf-8")
        self.assertIn("loose precondition", report)


if __name__ == "__main__":
    unittest.main()
