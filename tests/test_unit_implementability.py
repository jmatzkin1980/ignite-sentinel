"""IMP-118: maturity as agent implementability — per-RU matrix + soft gate.

Two layers:

* Pure-function tests over ``build_unit_implementability_matrix`` and helpers,
  which assert the OPEN (non-inferable) vs DEFERRED_TO_CONTEXT (discoverable)
  distinction deterministically without relying on gap-to-unit anchoring.
* An integration test through real ``/ingest`` + ``/maturity`` that asserts the
  per-RU view is wired into ``development_readiness`` / ``/status`` and that the
  pre-existing ``maturity_score`` is preserved.
"""
from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from sentinel.cli import main
from sentinel.development_readiness import (
    build_unit_implementability_matrix,
    classify_unit_gap,
    compute_unit_implementability,
    gap_scope_index,
    summarize_unit_implementability,
)
from sentinel.maturity import generate_project_brief, maturity_metrics
from sentinel.status import project_status


def gap(gap_id: str, lens: str, unit: str, *, status: str = "OPEN", severity: str = "medium") -> dict[str, str]:
    return {"id": gap_id, "lens": lens, "severity": severity, "status": status, "unit": unit}


class UnitImplementabilityLogicTests(unittest.TestCase):
    """Deterministic classification: scope decides OPEN vs DEFERRED."""

    def setUp(self) -> None:
        self.scope = gap_scope_index()
        self.units = [
            {"id": "RU-001", "label": "metrics dashboard", "evidence_mention": "metrics"},
            {"id": "RU-002", "label": "login flow", "evidence_mention": "login"},
            {"id": "RU-003", "label": "export report", "evidence_mention": "export"},
        ]

    def test_source_scope_gap_is_open_non_inferable(self) -> None:
        # GAP-METRIC-SOURCE reads the client's own requirement text (source
        # scope): only the client can supply the missing source/baseline.
        self.assertEqual(self.scope.get("GAP-METRIC-SOURCE"), "source")
        self.assertEqual(classify_unit_gap(gap("GAP-METRIC-SOURCE", "business", "RU-001"), self.scope), "OPEN")

    def test_domain_scope_gap_is_deferred_discoverable(self) -> None:
        # GAP-DESIGN-FLOW is a domain dimension a design context pack deepens.
        self.assertNotEqual(self.scope.get("GAP-DESIGN-FLOW"), "source")
        self.assertEqual(
            classify_unit_gap(gap("GAP-DESIGN-FLOW", "design", "RU-001"), self.scope),
            "DEFERRED_TO_CONTEXT",
        )

    def test_unknown_gap_falls_back_to_lens(self) -> None:
        self.assertEqual(classify_unit_gap(gap("GAP-CUSTOM-X", "business", "RU-001"), self.scope), "OPEN")
        self.assertEqual(
            classify_unit_gap(gap("GAP-CUSTOM-Y", "technical", "RU-001"), self.scope),
            "DEFERRED_TO_CONTEXT",
        )

    def test_unit_with_non_inferable_gap_is_not_implementable(self) -> None:
        gaps = [gap("GAP-METRIC-SOURCE", "business", "RU-001")]
        matrix = build_unit_implementability_matrix(self.units, gaps, self.scope)
        ru1 = next(row for row in matrix if row["unit_id"] == "RU-001")
        self.assertEqual(ru1["readiness"], "NOT_IMPLEMENTABLE")
        self.assertEqual(ru1["open_lenses"], ["business"])
        cell = next(c for c in ru1["lenses"] if c["lens"] == "business")
        self.assertEqual(cell["status"], "OPEN")
        self.assertIn("GAP-METRIC-SOURCE", cell["gaps"])

    def test_unit_with_only_domain_gap_is_deferred_not_blocking(self) -> None:
        # "Solo le faltan columnas": discoverable by domain → does not block.
        gaps = [gap("GAP-DESIGN-FLOW", "design", "RU-002")]
        matrix = build_unit_implementability_matrix(self.units, gaps, self.scope)
        ru2 = next(row for row in matrix if row["unit_id"] == "RU-002")
        self.assertEqual(ru2["readiness"], "DEFERRED_TO_CONTEXT")
        self.assertEqual(ru2["open_lenses"], [])
        self.assertIn("design", ru2["deferred_lenses"])

    def test_unit_with_no_open_gaps_is_implementable(self) -> None:
        matrix = build_unit_implementability_matrix(self.units, [], self.scope)
        self.assertTrue(all(row["readiness"] == "IMPLEMENTABLE" for row in matrix))

    def test_closed_gap_does_not_count(self) -> None:
        gaps = [gap("GAP-METRIC-SOURCE", "business", "RU-001", status="CLOSED")]
        matrix = build_unit_implementability_matrix(self.units, gaps, self.scope)
        ru1 = next(row for row in matrix if row["unit_id"] == "RU-001")
        self.assertEqual(ru1["readiness"], "IMPLEMENTABLE")

    def test_summary_separates_open_from_deferred(self) -> None:
        gaps = [
            gap("GAP-METRIC-SOURCE", "business", "RU-001"),  # OPEN
            gap("GAP-DESIGN-FLOW", "design", "RU-002"),       # DEFERRED
            # RU-003 has nothing -> IMPLEMENTABLE
        ]
        matrix = build_unit_implementability_matrix(self.units, gaps, self.scope)
        summary = summarize_unit_implementability(matrix)
        self.assertEqual(summary["units_total"], 3)
        self.assertEqual(summary["not_implementable"], ["RU-001"])
        self.assertEqual(summary["deferred_to_context"], ["RU-002"])
        self.assertEqual(summary["implementable"], ["RU-003"])
        # Score counts implementable + deferred as advanceable (2 of 3).
        self.assertAlmostEqual(summary["implementability_score"], round(2 / 3, 3))
        self.assertEqual(summary["gate"]["state"], "UNITS_NOT_IMPLEMENTABLE")
        self.assertFalse(summary["gate"]["blocks_by_default"])

    def test_empty_matrix_is_a_noop_gate(self) -> None:
        summary = summarize_unit_implementability([])
        self.assertEqual(summary["units_total"], 0)
        self.assertEqual(summary["implementability_score"], 1.0)
        self.assertEqual(summary["gate"]["state"], "ALL_UNITS_IMPLEMENTABLE")
        self.assertEqual(summary["not_implementable"], [])


RAW = (
    "# Ops Console\n\n"
    "Goal: reduce manual review time for support leads. "
    "The dashboard shows queue metrics that must improve by 30 percent. "
    "Scope includes a read-only dashboard for queue triage."
)


class UnitImplementabilityIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.old_cwd = Path.cwd()
        self.temp = Path(tempfile.mkdtemp())
        os.chdir(self.temp)
        self.source = self.temp / "ops.md"
        self.source.write_text(RAW, encoding="utf-8")
        self.assertEqual(main(["init", "OPS"]), 0)
        self.assertEqual(main(["ingest", "OPS", "--source", str(self.source)]), 0)
        self.ws = self.temp / "workspaces" / "OPS"

    def tearDown(self) -> None:
        os.chdir(self.old_cwd)
        shutil.rmtree(self.temp, ignore_errors=True)

    def test_maturity_persists_unit_implementability(self) -> None:
        self.assertEqual(main(["maturity", "OPS"]), 0)
        payload = json.loads(
            (self.ws / "01_discovery" / "development_readiness.json").read_text(encoding="utf-8")
        )
        impl = payload["unit_implementability"]
        self.assertEqual(impl["statuses"], ["CONFIRMED", "DEFERRED_TO_CONTEXT", "OPEN"])
        self.assertTrue(impl["matrix"])
        # The metrics dashboard unit names a metric with no source/definition:
        # a non-inferable, client-owned gap → not implementable, with the
        # design/frontend dimensions deferred to a domain context pack.
        metric_unit = next(
            row for row in impl["matrix"]
            if any(
                cell["status"] == "OPEN"
                and any(g.startswith("GAP-METRIC") for g in cell["gaps"])
                for cell in row["lenses"]
            )
        )
        self.assertEqual(metric_unit["readiness"], "NOT_IMPLEMENTABLE")
        self.assertIn("business", metric_unit["open_lenses"])
        self.assertTrue(metric_unit["deferred_lenses"])  # design/frontend deferred
        self.assertTrue(impl["summary"]["not_implementable"])

    def test_status_and_maturity_surface_implementability_without_breaking_score(self) -> None:
        self.assertEqual(main(["maturity", "OPS"]), 0)
        metrics = maturity_metrics("OPS")
        self.assertIn("maturity_score", metrics)  # pre-existing dimension preserved
        self.assertIn("unit_implementability", metrics)
        self.assertIn("not_implementable", metrics["unit_implementability"])

        status = project_status("OPS")
        readiness = status["development_readiness"]
        self.assertIn("unit_implementability", readiness)
        self.assertIn("summary", readiness["unit_implementability"])

    def test_soft_gate_warns_without_blocking_by_default(self) -> None:
        result = generate_project_brief("OPS")
        self.assertFalse(result.get("blocked", False))
        self.assertFalse(result["implementability_gate"]["strict"])
        self.assertTrue(result["implementability_gate"]["not_implementable_units"])
        self.assertTrue(any("not implementable" in w.lower() for w in result["warnings"]))

    def test_strict_gate_blocks_advance_to_specs(self) -> None:
        config = self.ws / "sentinel.config.yaml"
        config.write_text(
            config.read_text(encoding="utf-8") + "\nimplementability_gate:\n  strict: true\n",
            encoding="utf-8",
        )
        result = generate_project_brief("OPS")
        self.assertTrue(result["blocked"])
        self.assertTrue(result["implementability_gate"]["strict"])
        state = json.loads((self.ws / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(state["readiness_stage"], "UNITS_NOT_IMPLEMENTABLE")


if __name__ == "__main__":
    unittest.main()
