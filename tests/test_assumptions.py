"""Tests for governed assumptions /assume (IMP-067)."""
from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from sentinel.assumptions import (
    AssumptionError,
    apply_assumptions,
    assumption_projection_rows,
    assumptions_projection,
    validate_assumptions,
)
from sentinel.cli import main
from sentinel.discovery import parse_gap_rows
from sentinel.health import run_health
from sentinel.maturity import generate_project_brief, maturity_metrics
from sentinel.status import project_status


RAW = (
    "# Risk Dashboard\n\n"
    "We need a dashboard for operations leads to see queue risk before standup. "
    "The dashboard reads queue metrics from the existing support metrics service."
)


def _assumption(**over):
    base = {
        "id": "ASM-TECH-METRICS-SOURCE",
        "lens": "technical",
        "statement": "The dashboard will provisionally use the existing support metrics service as the source for queue risk.",
        "owner": "Technology Lead",
        "risk": "med",
        "justification": "The dashboard reads queue metrics from the existing support metrics service.",
        "closes_gap": "GAP-TECH-DATA-SOURCE",
    }
    base.update(over)
    return base


class AssumptionValidationTests(unittest.TestCase):
    def test_valid_assumption_requires_owner_risk_and_citation(self):
        rows = validate_assumptions({"assumptions": [_assumption()]}, RAW)
        self.assertEqual(rows[0]["status"], "ASSUMED")
        self.assertEqual(rows[0]["owner"], "Technology Lead")
        self.assertEqual(rows[0]["risk"], "med")
        self.assertEqual(rows[0]["uncertainty"], "med")
        self.assertEqual(rows[0]["priority_signal"], "monitor")

    def test_missing_owner_rejected(self):
        with self.assertRaises(AssumptionError):
            validate_assumptions({"assumptions": [_assumption(owner="")]}, RAW)

    def test_fabricated_justification_rejected(self):
        with self.assertRaises(AssumptionError):
            validate_assumptions({"assumptions": [_assumption(justification="Not in local evidence")]}, RAW)

    def test_invalid_lens_rejected(self):
        with self.assertRaises(AssumptionError):
            validate_assumptions({"assumptions": [_assumption(lens="finance")]}, RAW)

    def test_invalid_uncertainty_rejected(self):
        with self.assertRaises(AssumptionError):
            validate_assumptions({"assumptions": [_assumption(uncertainty="certain")]}, RAW)

    def test_risk_category_is_optional_and_normalized(self):
        rows = validate_assumptions({"assumptions": [_assumption()]}, RAW)
        self.assertEqual(rows[0]["risk_category"], "")

    def test_valid_risk_category_accepted(self):
        rows = validate_assumptions({"assumptions": [_assumption(risk_category="Feasibility")]}, RAW)
        self.assertEqual(rows[0]["risk_category"], "feasibility")

    def test_invalid_risk_category_rejected_with_exact_enum(self):
        with self.assertRaises(AssumptionError) as ctx:
            validate_assumptions({"assumptions": [_assumption(risk_category="go-to-market")]}, RAW)
        message = str(ctx.exception)
        self.assertIn("feasibility, usability, value, viability", message)

    def test_projection_rows_include_only_assumed_rows_riskiest_first(self):
        rows = [
            {
                "id": "ASM-001",
                "statement": "First",
                "risk": "high",
                "uncertainty": "low",
                "owner": "BA",
                "closes_gap": "GAP-001",
                "status": "ASSUMED",
                "justification": "Quote one",
            },
            {
                "id": "ASM-003",
                "statement": "Third",
                "risk": "high",
                "uncertainty": "high",
                "owner": "BA",
                "closes_gap": "GAP-003",
                "status": "ASSUMED",
                "justification": "Quote three",
            },
            {
                "id": "ASM-002",
                "statement": "Second",
                "risk": "low",
                "owner": "BA",
                "closes_gap": "",
                "status": "CONFIRMED",
                "justification": "Quote two",
            },
        ]

        projection = assumption_projection_rows(rows)

        self.assertEqual(
            projection,
            [
                {
                    "id": "ASM-003",
                    "statement": "Third",
                    "risk": "high",
                    "uncertainty": "high",
                    "priority_signal": "test before advancing",
                    "owner": "BA",
                    "closes_gap": "GAP-003",
                    "status": "ASSUMED",
                    "basis_quote": "Quote three",
                },
                {
                    "id": "ASM-001",
                    "statement": "First",
                    "risk": "high",
                    "uncertainty": "low",
                    "priority_signal": "watch closely",
                    "owner": "BA",
                    "closes_gap": "GAP-001",
                    "status": "ASSUMED",
                    "basis_quote": "Quote one",
                }
            ],
        )


class AssumptionLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.old_cwd = Path.cwd()
        self.temp = Path(tempfile.mkdtemp())
        os.chdir(self.temp)
        self.raw = self.temp / "raw.md"
        self.raw.write_text(RAW, encoding="utf-8")
        self.assertEqual(main(["init", "ASM"]), 0)
        self.assertEqual(main(["ingest", "ASM", "--source", str(self.raw)]), 0)
        self.ws = self.temp / "workspaces" / "ASM"

    def tearDown(self):
        os.chdir(self.old_cwd)
        shutil.rmtree(self.temp, ignore_errors=True)

    def _write(self, payload) -> Path:
        path = self.temp / "assumptions.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def _resolve_blocking_gaps(self) -> None:
        gaps = parse_gap_rows((self.ws / "01_discovery" / "gaps.md").read_text(encoding="utf-8"))
        blocks = []
        for gap in gaps:
            if gap.get("severity") not in {"critical", "high"}:
                continue
            blocks.append(
                f"### {gap['id']}\n"
                "- Answer: The BA confirmed enough discovery evidence to proceed with this blocking concern for the synthetic test.\n"
                "- Owner / source: Product Owner\n"
                "- Evidence or reference: Test workshop\n"
                "- Decision status: confirmed\n"
            )
        if blocks:
            path = self.temp / "blocking-answers.md"
            path.write_text("\n".join(blocks), encoding="utf-8")
            self.assertEqual(main(["resolve-gaps", "ASM", "--source", str(path)]), 0)

    def test_assume_writes_register_trace_and_assumed_ledger_unit(self):
        result = apply_assumptions("ASM", self._write({"assumptions": [_assumption()]}))
        self.assertEqual(result["accepted"], ["ASM-TECH-METRICS-SOURCE"])
        self.assertIn("knowledge_state", result)

        assumptions_md = (self.ws / "01_discovery" / "assumptions.md").read_text(encoding="utf-8")
        self.assertIn("ASM-TECH-METRICS-SOURCE", assumptions_md)
        self.assertIn("Technology Lead", assumptions_md)

        projection = assumptions_projection("ASM")
        self.assertEqual(projection["summary"]["assumed"], 1)
        self.assertEqual(projection["assumptions"][0]["id"], "ASM-TECH-METRICS-SOURCE")
        self.assertEqual(
            projection["assumptions"][0]["basis_quote"],
            "The dashboard reads queue metrics from the existing support metrics service.",
        )
        projection_path = self.ws / "08_context_packs" / "assumptions_projection.json"
        persisted = json.loads(projection_path.read_text(encoding="utf-8"))
        self.assertEqual(persisted["assumptions"], projection["assumptions"])
        self.assertEqual(project_status("ASM")["assumptions_projection"]["assumed"], 1)
        self.assertEqual(run_health("ASM")["assumptions_projection"]["assumed"], 1)

        graph = (self.ws / "06_traceability" / "traceability_graph.json").read_text(encoding="utf-8")
        self.assertIn('"type": "assumption_register"', graph)
        self.assertIn('"relation": "basis_for_assumption"', graph)

        ledger = json.loads((self.ws / "01_discovery" / "knowledge_state.json").read_text(encoding="utf-8"))
        unit = next(unit for unit in ledger["units"] if unit["statement"].startswith("The dashboard will provisionally"))
        self.assertEqual(unit["status"], "ASSUMED")
        self.assertEqual(unit["evidence"]["quote"], "The dashboard reads queue metrics from the existing support metrics service.")
        self.assertIn("ASSUMED", ledger["summary"]["by_status"])

        metrics = maturity_metrics("ASM")
        self.assertEqual(metrics["assumptions"]["total"], 1)
        self.assertEqual(metrics["assumptions"]["by_risk"]["med"], 1)

    def test_brief_and_prd_cite_governed_assumption_instead_of_pending_section(self):
        self.assertEqual(main(["assume", "ASM", "--source", str(self._write({"assumptions": [_assumption()]}))]), 0)
        brief = generate_project_brief("ASM")
        self.assertFalse(brief["blocked"])
        brief_text = (self.ws / "02_requirements" / "project-brief.md").read_text(encoding="utf-8")
        self.assertIn("governed assumption: `ASM-TECH-METRICS-SOURCE`", brief_text)
        self.assertIn("Supuestos Gobernados", brief_text)

        self._resolve_blocking_gaps()
        self.assertEqual(main(["maturity", "ASM"]), 0)
        self.assertEqual(main(["specs", "ASM"]), 0)
        prd_text = (self.ws / "03_specs" / "prd.md").read_text(encoding="utf-8")
        self.assertIn("ASM-TECH-METRICS-SOURCE", prd_text)
        self.assertIn("Technology Lead", prd_text)
        self.assertIn("GAP-TECH-DATA-SOURCE", prd_text)

    def test_cli_assume_rejects_invalid_citation(self):
        bad = self._write({"assumptions": [_assumption(justification="fabricated quote")]})
        self.assertEqual(main(["assume", "ASM", "--source", str(bad)]), 1)

    def test_register_groups_by_risk_category_and_readiness_reports_coverage(self):
        result = apply_assumptions(
            "ASM",
            self._write({"assumptions": [_assumption(risk_category="feasibility")]}),
        )
        self.assertEqual(result["assumption_summary"]["by_risk_category"], {"feasibility": 1})

        assumptions_md = (self.ws / "01_discovery" / "assumptions.md").read_text(encoding="utf-8")
        self.assertIn("## Feasibility", assumptions_md)
        self.assertIn("Risk Category", assumptions_md)

        from sentinel.development_readiness import compute_development_readiness

        readiness = compute_development_readiness("ASM")
        self.assertIn("feasibility", readiness["summary"]["by_risk_category"])
        self.assertEqual(readiness["summary"]["by_risk_category"]["feasibility"]["ASSUMED"], 1)

    def test_cli_assume_rejects_invalid_risk_category(self):
        bad = self._write({"assumptions": [_assumption(risk_category="strategy")]})
        self.assertEqual(main(["assume", "ASM", "--source", str(bad)]), 1)


if __name__ == "__main__":
    unittest.main()
