"""Tests for maturation-cycle telemetry (IMP-028).

After two /resolve-gaps rounds, /status (and /maturity) expose: number of
resolve iterations, closed-gap split by provenance, count of open blocking gaps,
and the age (in rounds) of the oldest surviving blocking gap. Fields are additive
and optional.
"""
from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from pathlib import Path

from sentinel.cli import main
from sentinel.discovery import parse_gap_rows
from sentinel.gap_resolution import resolve_gaps
from sentinel.maturity import maturation_telemetry
from sentinel.status import project_status
from sentinel.sync import sync_change

RAW = "# Ops Dashboard\n\nWe need a dashboard for the operations team to see queue risk.\n"


class TelemetryTests(unittest.TestCase):
    def setUp(self):
        self.old_cwd = Path.cwd()
        self.temp = Path(tempfile.mkdtemp())
        os.chdir(self.temp)
        src = self.temp / "raw.md"
        src.write_text(RAW, encoding="utf-8")
        self.assertEqual(main(["init", "TEL"]), 0)
        self.assertEqual(main(["ingest", "TEL", "--source", str(src)]), 0)
        self.ws = self.temp / "workspaces" / "TEL"

    def tearDown(self):
        os.chdir(self.old_cwd)
        shutil.rmtree(self.temp, ignore_errors=True)

    def _gap_ids(self):
        gaps = parse_gap_rows((self.ws / "01_discovery" / "gaps.md").read_text(encoding="utf-8"))
        return [g["id"] for g in gaps if g["id"] != "NONE"]

    def _answer(self, gap_id, name, owner="Ops"):
        path = self.temp / f"{name}.md"
        path.write_text(
            f"### {gap_id} - x\n"
            f"- Answer: The operations lead confirmed this scope and ownership in the workshop.\n"
            f"- Owner / source: {owner}\n- Evidence or reference: Workshop\n- Decision status: confirmed\n",
            encoding="utf-8",
        )
        return path

    def test_two_rounds_telemetry(self):
        ids = self._gap_ids()
        self.assertGreaterEqual(len(ids), 2)
        resolve_gaps("TEL", self._answer(ids[0], "r1"))
        resolve_gaps("TEL", self._answer(ids[1], "r2"))

        tel = maturation_telemetry("TEL")
        self.assertEqual(tel["resolve_iterations"], 2)
        self.assertGreaterEqual(tel["closed_total"], 1)
        self.assertIn("checklist", tel["closed_by_origin"])
        # Some blocking gaps remain unanswered, so the age proxy equals the rounds run.
        if tel["open_blocking_gaps"]:
            self.assertEqual(tel["oldest_blocking_age_rounds"], 2)

    def test_status_surfaces_telemetry(self):
        resolve_gaps("TEL", self._answer(self._gap_ids()[0], "r1"))
        status = project_status("TEL")
        self.assertIn("maturation_telemetry", status["maturity_metrics"])
        self.assertEqual(status["maturity_metrics"]["maturation_telemetry"]["resolve_iterations"], 1)

    def test_closed_split_by_client_domain_and_inference_source(self):
        ids = self._gap_ids()
        self.assertGreaterEqual(len(ids), 3)
        resolve_gaps("TEL", self._answer(ids[0], "client", owner="Client product owner"))
        resolve_gaps("TEL", self._answer(ids[1], "domain", owner="Technology architect"))
        resolve_gaps("TEL", self._answer(ids[2], "inference", owner="Sentinel inference"))

        tel = maturation_telemetry("TEL")
        self.assertEqual(tel["closed_by_response_source"]["client"], 1)
        self.assertEqual(tel["closed_by_response_source"]["domain"], 1)
        self.assertEqual(tel["closed_by_response_source"]["inference"], 1)
        self.assertEqual(tel["closed_by_response_source_pct"]["client"], 0.333)

    def test_sync_reports_reopened_closed_gaps(self):
        ids = self._gap_ids()
        self.assertIn("GAP-USERS", ids)
        resolve_gaps("TEL", self._answer("GAP-USERS", "users", owner="Client product owner"))

        change = self.temp / "late-change.md"
        change.write_text("We need a dashboard for queue risk. Acceptance remains undefined.", encoding="utf-8")
        result = sync_change("TEL", change, "late clarification")
        self.assertIn("GAP-USERS", result["reopened_gaps"])

        tel = maturation_telemetry("TEL")
        self.assertEqual(tel["reopened_by_sync_total"], 1)
        self.assertIn("GAP-USERS", tel["reopened_by_sync_gap_ids"])


if __name__ == "__main__":
    unittest.main()
