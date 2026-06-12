"""Tests for IMP-040 sanctioned PRD composition."""
from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from sentinel.cli import main
from sentinel.prd import render_prd_compositions


RAW = """# Client Request: Support Operations Dashboard

Objective: reduce support leads' weekly review preparation time.

Users: support team leads.

In scope: read-only dashboard for ticket volume and SLA breach risk. Out of scope: editing tickets.

Metric: reduce preparation effort by 30 percent in the first release month.

Acceptance: support leads can identify SLA breach risk queues before the weekly review.
"""


class ComposeLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.old_cwd = Path.cwd()
        self.temp = Path(tempfile.mkdtemp())
        os.chdir(self.temp)
        self.raw = self.temp / "raw.md"
        self.raw.write_text(RAW, encoding="utf-8")
        self.assertEqual(main(["init", "COMP"]), 0)
        self.assertEqual(main(["ingest", "COMP", "--source", str(self.raw)]), 0)
        self.assertEqual(main(["brief", "COMP"]), 0)
        self.assertEqual(main(["specs", "COMP"]), 0)
        self.ws = self.temp / "workspaces" / "COMP"

    def tearDown(self):
        os.chdir(self.old_cwd)
        shutil.rmtree(self.temp, ignore_errors=True)

    def _draft(self, payload: dict) -> Path:
        path = self.temp / "compose.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def test_valid_compose_merges_origin_agent_block(self):
        draft = {
            "blocks": [
                {
                    "section": "1",
                    "paragraphs": [
                        {
                            "text": "The PRD narrative can say the dashboard is meant to reduce weekly review preparation effort.",
                            "citations": ["Objective: reduce support leads' weekly review preparation time."],
                        }
                    ],
                }
            ]
        }

        self.assertEqual(main(["compose", "COMP", "--source", str(self._draft(draft))]), 0)

        prd = (self.ws / "03_specs" / "prd.md").read_text(encoding="utf-8")
        self.assertIn("### Agent Composition", prd)
        self.assertIn("Origin: agent", prd)
        self.assertIn("reduce weekly review preparation effort", prd)
        report = (self.ws / "03_specs" / "compositions" / "composition_report.md").read_text(encoding="utf-8")
        self.assertIn("COMP-001", report)
        status = json.loads((self.ws / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(status["prd_composition_count"], 1)
        graph = (self.ws / "06_traceability" / "traceability_graph.json").read_text(encoding="utf-8")
        self.assertIn('"type": "prd_composition"', graph)
        self.assertIn('"relation": "composed_by"', graph)

    def test_compose_rejects_fabricated_citation(self):
        draft = {
            "blocks": [
                {
                    "section": "1",
                    "paragraphs": [
                        {"text": "Unsupported narrative.", "citations": ["not present in any local evidence"]}
                    ],
                }
            ]
        }
        self.assertEqual(main(["compose", "COMP", "--source", str(self._draft(draft))]), 1)
        report = (self.ws / "03_specs" / "compositions" / "composition_report.md").read_text(encoding="utf-8")
        self.assertIn("citation not found verbatim", report)

    def test_compose_rejects_pending_section(self):
        draft = {
            "blocks": [
                {
                    "section": "5",
                    "paragraphs": [
                        {
                            "text": "Quality is fully understood.",
                            "citations": ["Metric: reduce preparation effort by 30 percent in the first release month."],
                        }
                    ],
                }
            ]
        }
        self.assertEqual(main(["compose", "COMP", "--source", str(self._draft(draft))]), 1)
        report = (self.ws / "03_specs" / "compositions" / "composition_report.md").read_text(encoding="utf-8")
        self.assertIn("pending input", report)

    def test_regeneration_discards_block_when_citation_is_no_longer_valid(self):
        comp_dir = self.ws / "03_specs" / "compositions"
        comp_dir.mkdir(parents=True, exist_ok=True)
        accepted = [
            {
                "id": "COMP-001",
                "section": "1",
                "origin": "agent",
                "paragraphs": [{"text": "Now stale.", "citations": ["removed evidence"]}],
            }
        ]
        (comp_dir / "accepted_blocks.json").write_text(json.dumps(accepted), encoding="utf-8")
        prd_path = self.ws / "03_specs" / "prd.md"
        prd = prd_path.read_text(encoding="utf-8")

        rendered = render_prd_compositions("COMP", prd)

        self.assertNotIn("Now stale.", rendered)
        report = (comp_dir / "regeneration_report.md").read_text(encoding="utf-8")
        self.assertIn("discarded", report.lower())
        self.assertIn("citation not found verbatim", report)


if __name__ == "__main__":
    unittest.main()
