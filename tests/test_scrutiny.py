"""Tests for systematic multi-lens scrutiny /scrutinize (IMP-066)."""
from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from sentinel.cli import main
from sentinel.discovery import AnnotationError, apply_scrutiny, parse_gap_rows, scrutiny_grounding_text, validate_scrutiny_gaps

RAW = (
    "# Billing Sync\n\n"
    "We need near real-time billing status in CRM for account managers. "
    "The dashboard must show failed syncs."
)

TECH_CONTEXT = "The billing platform only exports invoice status in a nightly batch file."


def _finding(**over):
    base = {
        "id": "GAP-SCRUTINY-BILLING-LATENCY",
        "lens": "technical",
        "severity": "high",
        "finding_type": "domain-conflict",
        "question": "Which latency target is authoritative for CRM billing status: near real-time or nightly batch?",
        "evidence": "only exports invoice status in a nightly batch file",
        "description": "Domain context conflicts with the raw requirement's near real-time expectation.",
    }
    base.update(over)
    return base


class ScrutinyValidationTests(unittest.TestCase):
    def test_valid_context_citation_passes(self):
        gaps = validate_scrutiny_gaps({"gaps": [_finding()]}, RAW + "\n" + TECH_CONTEXT, lens="technical")
        self.assertEqual(gaps[0]["origin"], "scrutiny")
        self.assertEqual(gaps[0]["lens"], "technical")

    def test_fabricated_context_citation_rejected(self):
        with self.assertRaises(AnnotationError):
            validate_scrutiny_gaps({"gaps": [_finding(evidence="not actually stated")]}, RAW + "\n" + TECH_CONTEXT)

    def test_invalid_finding_type_rejected(self):
        with self.assertRaises(AnnotationError):
            validate_scrutiny_gaps({"gaps": [_finding(finding_type="persona-role-play")]}, RAW + "\n" + TECH_CONTEXT)

    def test_lens_filter_rejects_mismatched_lens(self):
        with self.assertRaises(AnnotationError):
            validate_scrutiny_gaps({"gaps": [_finding()]}, RAW + "\n" + TECH_CONTEXT, lens="design")


class ScrutinyLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.old_cwd = Path.cwd()
        self.temp = Path(tempfile.mkdtemp())
        os.chdir(self.temp)
        self.src = self.temp / "raw.md"
        self.src.write_text(RAW, encoding="utf-8")
        self.assertEqual(main(["init", "SCR"]), 0)
        self.ws = self.temp / "workspaces" / "SCR"
        tech_dir = self.ws / "00_raw" / "02_technology_context"
        tech_dir.mkdir(parents=True, exist_ok=True)
        (tech_dir / "billing.md").write_text(TECH_CONTEXT, encoding="utf-8")
        self.assertEqual(main(["ingest", "SCR", "--source", str(self.src)]), 0)

    def tearDown(self):
        os.chdir(self.old_cwd)
        shutil.rmtree(self.temp, ignore_errors=True)

    def _write(self, payload) -> Path:
        path = self.temp / "scrutiny.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def test_grounding_includes_domain_context(self):
        self.assertIn(TECH_CONTEXT, scrutiny_grounding_text(self.ws))

    def test_scrutiny_merges_gap_report_and_ledger(self):
        result = apply_scrutiny("SCR", self._write({"gaps": [_finding()]}), lens="technical")
        self.assertIn("GAP-SCRUTINY-BILLING-LATENCY", result["merged"])
        self.assertIn("knowledge_state", result)

        gaps_md = (self.ws / "01_discovery" / "gaps.md").read_text(encoding="utf-8")
        row = next(line for line in gaps_md.splitlines() if line.startswith("| GAP-SCRUTINY-BILLING-LATENCY"))
        self.assertEqual(parse_gap_rows(row)[0].get("origin"), "scrutiny", row)

        report = (self.ws / "01_discovery" / "scrutiny_report.md").read_text(encoding="utf-8")
        self.assertIn("Scrutiny Report", report)
        self.assertIn("Lens: `technical`", report)
        self.assertIn("domain-conflict", report)

        graph = (self.ws / "06_traceability" / "traceability_graph.json").read_text(encoding="utf-8")
        self.assertIn('"type": "scrutiny_report"', graph)
        self.assertIn('"relation": "scrutinized_by"', graph)
        self.assertIn('"type": "knowledge_ledger"', graph)

        state = json.loads((self.ws / "state.json").read_text(encoding="utf-8"))
        self.assertGreaterEqual(state["gap_counts"].get("scrutiny_origin", 0), 1)

        ledger = json.loads((self.ws / "01_discovery" / "knowledge_state.json").read_text(encoding="utf-8"))
        unit = next(unit for unit in ledger["units"] if unit["statement"].startswith("Domain context conflicts"))
        self.assertEqual(unit["status"], "OPEN")
        self.assertEqual(unit["evidence"]["quote"], "only exports invoice status in a nightly batch file")

    def test_cli_scrutinize_runs_and_rejects_bad_lens(self):
        self.assertEqual(
            main(["scrutinize", "SCR", "--lens", "technical", "--source", str(self._write({"gaps": [_finding()]}))]),
            0,
        )
        bad = self._write({"gaps": [_finding(id="GAP-SCRUTINY-DESIGN", lens="design")]})
        self.assertEqual(main(["scrutinize", "SCR", "--lens", "technical", "--source", str(bad)]), 1)


if __name__ == "__main__":
    unittest.main()
