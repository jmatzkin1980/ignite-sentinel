"""IMP-119: agentic implementability probe (pre-flight) as a /scrutinize sub-mode.

The probe reuses the scrutiny machinery but: anchors every finding to a
Requirement Unit (IMP-115), uses a probe finding-type vocabulary, tags
``origin: implementability-probe``, and writes a per-RU report. It is the
pre-flight mirror of the downstream ``/implementation-feedback``. Findings
without a verbatim local citation — or without a real RU anchor — are rejected,
and nothing is auto-resolved.
"""
from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from sentinel.cli import main
from sentinel.discovery import (
    AnnotationError,
    apply_scrutiny,
    known_requirement_unit_ids,
    parse_gap_rows,
    validate_scrutiny_gaps,
)

RAW = (
    "# Ops Console\n\n"
    "The dashboard shows queue metrics for support leads. "
    "The login flow uses single sign-on for agents."
)


class ProbeValidationTests(unittest.TestCase):
    """Mode-aware validation, exercised as pure functions over grounding text."""

    def _finding(self, **over):
        base = {
            "id": "GAP-PROBE-METRIC-SOURCE",
            "lens": "business",
            "severity": "high",
            "finding_type": "non-inferable-gap",
            "unit": "RU-001",
            "question": "What data source feeds the queue metrics shown on the dashboard?",
            "evidence": "The dashboard shows queue metrics",
        }
        base.update(over)
        return base

    def test_probe_finding_with_unit_and_citation_passes(self):
        gaps = validate_scrutiny_gaps(
            {"gaps": [self._finding()]}, RAW, mode="implementability-probe", known_units={"RU-001"}
        )
        self.assertEqual(gaps[0]["origin"], "implementability-probe")
        self.assertEqual(gaps[0]["unit"], "RU-001")

    def test_probe_requires_unit_anchor(self):
        finding = self._finding()
        finding.pop("unit")
        with self.assertRaises(AnnotationError):
            validate_scrutiny_gaps({"gaps": [finding]}, RAW, mode="implementability-probe")

    def test_probe_rejects_unknown_unit(self):
        with self.assertRaises(AnnotationError):
            validate_scrutiny_gaps(
                {"gaps": [self._finding(unit="RU-099")]},
                RAW,
                mode="implementability-probe",
                known_units={"RU-001"},
            )

    def test_probe_rejects_scrutiny_finding_type(self):
        with self.assertRaises(AnnotationError):
            validate_scrutiny_gaps(
                {"gaps": [self._finding(finding_type="domain-conflict")]},
                RAW,
                mode="implementability-probe",
                known_units={"RU-001"},
            )

    def test_probe_rejects_fabricated_citation(self):
        with self.assertRaises(AnnotationError):
            validate_scrutiny_gaps(
                {"gaps": [self._finding(evidence="a baseline that is not in the text")]},
                RAW,
                mode="implementability-probe",
                known_units={"RU-001"},
            )

    def test_scrutiny_mode_does_not_require_unit(self):
        # Back-compat: default scrutiny mode is unchanged by the probe sub-mode.
        scrutiny_finding = {
            "id": "GAP-SCRUTINY-X",
            "lens": "technical",
            "severity": "medium",
            "finding_type": "unstated-assumption",
            "question": "Which SSO provider backs the login flow?",
            "evidence": "single sign-on for agents",
        }
        gaps = validate_scrutiny_gaps({"gaps": [scrutiny_finding]}, RAW)
        self.assertEqual(gaps[0]["origin"], "scrutiny")
        self.assertNotIn("unit", gaps[0])


class ProbeLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.old_cwd = Path.cwd()
        self.temp = Path(tempfile.mkdtemp())
        os.chdir(self.temp)
        self.src = self.temp / "raw.md"
        self.src.write_text(RAW, encoding="utf-8")
        self.assertEqual(main(["init", "PRB"]), 0)
        self.assertEqual(main(["ingest", "PRB", "--source", str(self.src)]), 0)
        self.ws = self.temp / "workspaces" / "PRB"
        units = sorted(known_requirement_unit_ids(self.ws))
        self.assertTrue(units, "ingest should extract at least one Requirement Unit")
        self.unit = units[0]

    def tearDown(self):
        os.chdir(self.old_cwd)
        shutil.rmtree(self.temp, ignore_errors=True)

    def _probe(self, **over) -> Path:
        finding = {
            "id": "GAP-PROBE-METRIC-SOURCE",
            "lens": "business",
            "severity": "high",
            "finding_type": "non-inferable-gap",
            "unit": self.unit,
            "question": "What data source feeds the queue metrics shown on the dashboard?",
            "evidence": "The dashboard shows queue metrics",
        }
        finding.update(over)
        path = self.temp / "probe.json"
        path.write_text(json.dumps({"gaps": [finding]}), encoding="utf-8")
        return path

    def test_probe_merges_per_unit_report_and_anchors_gap(self):
        result = apply_scrutiny("PRB", self._probe(), mode="implementability-probe")
        self.assertEqual(result["mode"], "implementability-probe")
        self.assertIn("GAP-PROBE-METRIC-SOURCE", result["merged"])
        self.assertIn("probe_id", result)

        gaps_md = (self.ws / "01_discovery" / "gaps.md").read_text(encoding="utf-8")
        row = next(line for line in gaps_md.splitlines() if line.startswith("| GAP-PROBE-METRIC-SOURCE"))
        parsed = parse_gap_rows(row)[0]
        self.assertEqual(parsed.get("origin"), "implementability-probe", row)
        self.assertEqual(parsed.get("unit"), self.unit, row)

        report = (self.ws / "01_discovery" / "implementability_probe_report.md").read_text(encoding="utf-8")
        self.assertIn("Implementability Probe Report", report)
        self.assertIn(f"Unit: `{self.unit}`", report)
        self.assertIn("non-inferable-gap", report)

        graph = (self.ws / "06_traceability" / "traceability_graph.json").read_text(encoding="utf-8")
        self.assertIn('"type": "implementability_probe"', graph)
        self.assertIn('"relation": "probed_by"', graph)

        state = json.loads((self.ws / "state.json").read_text(encoding="utf-8"))
        self.assertIn("last_probe_id", state)
        self.assertGreaterEqual(state["gap_counts"].get("implementability_probe_origin", 0), 1)

    def test_cli_probe_runs_and_rejects_uncited_finding(self):
        self.assertEqual(
            main(["scrutinize", "PRB", "--mode", "implementability-probe", "--source", str(self._probe())]),
            0,
        )
        bad = self._probe(id="GAP-PROBE-FAKE", evidence="not present in the raw input")
        self.assertEqual(
            main(["scrutinize", "PRB", "--mode", "implementability-probe", "--source", str(bad)]),
            1,
        )

    def test_default_scrutiny_mode_unaffected(self):
        scrutiny = {
            "gaps": [
                {
                    "id": "GAP-SCRUTINY-SSO",
                    "lens": "technical",
                    "severity": "medium",
                    "finding_type": "unstated-assumption",
                    "question": "Which SSO provider backs the login flow?",
                    "evidence": "single sign-on for agents",
                }
            ]
        }
        path = self.temp / "scrutiny.json"
        path.write_text(json.dumps(scrutiny), encoding="utf-8")
        result = apply_scrutiny("PRB", path)
        self.assertEqual(result["mode"], "scrutiny")
        self.assertIn("scrutiny_id", result)
        self.assertTrue((self.ws / "01_discovery" / "scrutiny_report.md").exists())


if __name__ == "__main__":
    unittest.main()
