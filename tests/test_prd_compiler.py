"""Tests for IMP-039 PRD evidence compiler."""
from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from pathlib import Path

from sentinel.cli import main
from sentinel.discovery import prd_section_for_gap
from sentinel.generation import compile_prd_sections
from sentinel.validation import score_artifact_text


RAW = """# Client Request: Support Operations Dashboard

We want a dashboard for our customer support operation. The goal is to reduce the time team leads spend preparing the weekly review meeting.

The main users are the support team leads. They want to see ticket volume, resolution time, and backlog ageing in one screen.

In scope: a read-only dashboard for the current quarter. Out of scope: editing tickets or managing agents from this screen.

We expect this to cut preparation effort by around 30% once the team adopts it.
"""


class PrdSectionCompilerTests(unittest.TestCase):
    def test_target_sections_compile_from_evidence(self):
        gap_answers = {
            "GAP-ACCEPTANCE": {
                "statement": "Given metrics are available, the dashboard shows prioritized queues.",
                "source": "CHG-001",
            },
            "GAP-METRIC-SOURCE": {
                "statement": "Baseline comes from the weekly support operations report.",
                "source": "CHG-001",
            },
        }
        sections = compile_prd_sections("SUP", "Support dashboard", {"gap_answers": gap_answers, "raw_text": RAW}, "en", RAW)

        for section in ("1", "3", "4", "6"):
            self.assertNotIn("[PENDING INPUT]", sections[section], sections[section])
            self.assertNotIn("GAP-PRD-", sections[section], sections[section])

        self.assertIn("support team leads", sections["3"])
        self.assertIn("ticket volume", sections["4"])
        self.assertIn("30%", sections["6"])
        self.assertIn("CHG-001", sections["6"])
        self.assertNotIn("GAP-METRIC-SOURCE", sections["6"])

    def test_prd_section_map_routes_known_gaps(self):
        self.assertEqual(prd_section_for_gap("GAP-ACCEPTANCE"), "4")
        self.assertEqual(prd_section_for_gap("GAP-METRIC-SOURCE"), "6")
        self.assertEqual(prd_section_for_gap("GAP-PRD-PERSONA-DETAIL"), "3")


class PrdLifecycleCompilerTests(unittest.TestCase):
    def setUp(self):
        self.old_cwd = Path.cwd()
        self.temp = Path(tempfile.mkdtemp())
        os.chdir(self.temp)
        self.raw = self.temp / "raw.md"
        self.raw.write_text(RAW, encoding="utf-8")
        self.answers = self.temp / "answers.md"
        self.answers.write_text(
            "### GAP-METRIC-SOURCE\n"
            "- Answer: Baseline comes from the weekly support operations report owned by Support Ops; target is a 30 percent reduction measured during the first release month.\n"
            "- Owner / source: Client workshop\n"
            "- Evidence or reference: Synthetic test response\n"
            "- Decision status: confirmed\n\n"
            "### GAP-ACCEPTANCE\n"
            "- Answer: Given ticket metrics are available, when a support lead opens the dashboard, then it shows prioritized queues for weekly review.\n"
            "- Owner / source: Client workshop\n"
            "- Evidence or reference: Synthetic test response\n"
            "- Decision status: confirmed\n",
            encoding="utf-8",
        )

    def tearDown(self):
        os.chdir(self.old_cwd)
        shutil.rmtree(self.temp, ignore_errors=True)

    def test_generated_prd_is_mixed_not_scaffolding(self):
        self.assertEqual(main(["init", "PRDC"]), 0)
        self.assertEqual(main(["ingest", "PRDC", "--source", str(self.raw)]), 0)
        self.assertEqual(main(["resolve-gaps", "PRDC", "--source", str(self.answers)]), 0)
        self.assertEqual(main(["brief", "PRDC"]), 0)
        self.assertEqual(main(["specs", "PRDC"]), 0)

        prd = (self.temp / "workspaces" / "PRDC" / "03_specs" / "prd.md").read_text(encoding="utf-8")
        score = score_artifact_text(prd)
        self.assertIn(score["classification"], {"mixed", "evidence-backed"})
        self.assertIn("support team leads", prd)
        self.assertIn("REQ-001", prd)


if __name__ == "__main__":
    unittest.main()
