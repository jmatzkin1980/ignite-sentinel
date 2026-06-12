"""Tests for IMP-047 EARS-oriented elicitation."""
from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from pathlib import Path

from sentinel.cli import main
from sentinel.discovery import expected_format_for_gap, parse_gap_rows
from sentinel.gap_resolution import resolve_gaps
from sentinel.status import project_status


RAW = "# Ops Dashboard\n\nWe need a dashboard for the operations team to see queue risk.\n"


class EarsElicitationFormatTests(unittest.TestCase):
    def test_expected_formats_point_functional_gaps_to_ears(self):
        self.assertIn("EARS", expected_format_for_gap("GAP-ACCEPTANCE"))
        self.assertIn("When <trigger>", expected_format_for_gap("GAP-ACCEPTANCE"))
        self.assertIn("If <condition/rule>", expected_format_for_gap("GAP-BUSINESS-RULES"))
        self.assertIn("statement", expected_format_for_gap("GAP-PRD-FR-AC"))

    def test_spanish_expected_formats_point_functional_gaps_to_ears(self):
        self.assertIn("EARS", expected_format_for_gap("GAP-ACCEPTANCE", "es"))
        self.assertIn("Cuando ocurre", expected_format_for_gap("GAP-ACCEPTANCE", "es"))
        self.assertIn("Si <condición/regla>", expected_format_for_gap("GAP-BUSINESS-RULES", "es"))
        self.assertIn("statement EARS", expected_format_for_gap("GAP-PRD-FR-AC", "es"))


class EarsEligibleResolutionTests(unittest.TestCase):
    def setUp(self):
        self.old_cwd = Path.cwd()
        self.temp = Path(tempfile.mkdtemp())
        os.chdir(self.temp)
        src = self.temp / "raw.md"
        src.write_text(RAW, encoding="utf-8")
        self.assertEqual(main(["init", "EARS47"]), 0)
        self.assertEqual(main(["ingest", "EARS47", "--source", str(src)]), 0)
        self.ws = self.temp / "workspaces" / "EARS47"

    def tearDown(self):
        os.chdir(self.old_cwd)
        shutil.rmtree(self.temp, ignore_errors=True)

    def test_ears_answer_normalizes_but_confirmed_prose_is_marked_and_counted(self):
        gaps = parse_gap_rows((self.ws / "01_discovery" / "gaps.md").read_text(encoding="utf-8"))
        ids = {gap["id"] for gap in gaps}
        self.assertIn("GAP-ACCEPTANCE", ids)
        self.assertIn("GAP-BUSINESS-RULES", ids)

        ears_stmt = "When a case breaches SLA, the system shall flag the queue as high risk."
        prose_rule = "Queues above ten cases near SLA are high risk and exceptions are reviewed by supervisors."
        answered = self.temp / "answers.md"
        answered.write_text(
            "### GAP-ACCEPTANCE - acceptance\n"
            f"- Answer: {ears_stmt}\n"
            "- Owner / source: Ops\n"
            "- Evidence or reference: Workshop\n"
            "- Decision status: confirmed\n\n"
            "### GAP-BUSINESS-RULES - rules\n"
            f"- Answer: {prose_rule}\n"
            "- Owner / source: Ops\n"
            "- Evidence or reference: Workshop\n"
            "- Decision status: confirmed\n",
            encoding="utf-8",
        )

        resolve_gaps("EARS47", answered)

        req = (self.ws / "02_requirements" / "requirements.md").read_text(encoding="utf-8")
        self.assertIn("REQ-EARS-001", req)
        self.assertIn(ears_stmt, req)
        self.assertNotIn(prose_rule, req)

        updated = parse_gap_rows((self.ws / "01_discovery" / "gaps.md").read_text(encoding="utf-8"))
        rules_gap = next(gap for gap in updated if gap["id"] == "GAP-BUSINESS-RULES")
        self.assertEqual(rules_gap["status"], "CLOSED")
        self.assertIn("EARS-eligible", rules_gap["resolution_note"])

        telemetry = project_status("EARS47")["maturity_metrics"]["maturation_telemetry"]
        self.assertEqual(telemetry["ears_eligible_not_normalized_total"], 1)
        self.assertEqual(telemetry["ears_eligible_not_normalized_gap_ids"], ["GAP-BUSINESS-RULES"])


if __name__ == "__main__":
    unittest.main()
