"""Tests for IMP-041 PRD section readiness and soft /specs gate."""
from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from sentinel.cli import main
from sentinel.maturity import prd_gate_warnings, prd_section_readiness
from sentinel.status import project_status


RAW = """# Client Request: Support Operations Dashboard

Objective: reduce support leads' weekly review preparation time.

Users: support team leads.

In scope: read-only dashboard for ticket volume and SLA breach risk. Out of scope: editing tickets.

Metric: reduce preparation effort by 30 percent in the first release month.

Acceptance: support leads can identify SLA breach risk queues before the weekly review.
"""


PRD = """# PRD - DEMO

## 1. Executive Summary

Outcome is supported _(source: `00_raw/`)_.

## 2. Scope

- `[PENDING INPUT]` - resolve `GAP-SCOPE`.

## 3. Users

| ID | Persona | Source |
| --- | --- | --- |
| P-01 | Support lead | `REQ-001`, `00_raw/` |

## 4. Functional Requirements

- `[PENDING INPUT]` - resolve `GAP-PRD-FR-AC`.

## 5. Non-Functional Requirements

- `[PENDING INPUT]` - resolve `GAP-PRD-NFR-KPI`.

## 6. KPIs

| KPI | Target | Source |
| --- | --- | --- |
| KPI-01 | 30 percent | `REQ-001`, `00_raw/` |

## 7. Jobs

JTBD-01 backed by `REQ-001`.

## 8. Dependencies

Owner backed by `GAP-PRD-DEPENDENCIES-ROADMAP`.

## 9. Risks

Risk backed by `PRD-001`.

## 10. Roadmap

- `[PENDING INPUT]` - resolve `GAP-PRD-ROLLOUT-ENVIRONMENTS`.

## 11. Constraints

Constraint backed by `GAP-GOVERNANCE-CONSTRAINTS`.

## 12. Team

Team backed by `CTX-QUALITY`.

## 13. Glossary

- `[PENDING INPUT]` - resolve `GAP-PRD-GLOSSARY-GOVERNANCE`.
"""


class PrdSectionReadinessTests(unittest.TestCase):
    def test_readiness_scores_numbered_prd_sections_and_feeding_gaps(self):
        readiness = prd_section_readiness(PRD)

        self.assertEqual(readiness["sections_total"], 13)
        self.assertEqual(readiness["sections"]["1"]["status"], "populated")
        self.assertEqual(readiness["sections"]["2"]["status"], "pending")
        self.assertIn("GAP-SCOPE", readiness["sections"]["2"]["feeding_gaps"])
        self.assertIn("GAP-PRD-FR-AC", readiness["sections"]["4"]["feeding_gaps"])
        self.assertLess(readiness["coverage_score"], 1.0)

    def test_prd_warnings_name_section_and_gaps(self):
        warnings = prd_gate_warnings(prd_section_readiness(PRD), "en")

        self.assertTrue(any("PRD section 4" in warning and "GAP-PRD-FR-AC" in warning for warning in warnings))


class SpecsGateLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.old_cwd = Path.cwd()
        self.temp = Path(tempfile.mkdtemp())
        os.chdir(self.temp)
        self.raw = self.temp / "raw.md"
        self.raw.write_text(RAW, encoding="utf-8")
        self.assertEqual(main(["init", "SPEC41"]), 0)
        self.assertEqual(main(["ingest", "SPEC41", "--source", str(self.raw)]), 0)
        self.assertEqual(main(["brief", "SPEC41"]), 0)
        self.ws = self.temp / "workspaces" / "SPEC41"

    def tearDown(self):
        os.chdir(self.old_cwd)
        shutil.rmtree(self.temp, ignore_errors=True)

    def test_default_specs_gate_warns_without_blocking(self):
        self.assertEqual(main(["specs", "SPEC41"]), 0)

        state = json.loads((self.ws / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(state["phase"], "specs_completed")
        self.assertEqual(state["specs_gate"]["strict"], False)
        self.assertIn("prd_section_readiness", state)
        self.assertIn("prd_section_readiness", project_status("SPEC41")["maturity_metrics"])

    def test_strict_specs_gate_blocks_when_below_threshold(self):
        config = self.ws / "sentinel.config.yaml"
        config.write_text(
            config.read_text(encoding="utf-8") + "\nspecs_gate:\n  threshold: 0.99\n  strict: true\n",
            encoding="utf-8",
        )

        self.assertEqual(main(["specs", "SPEC41"]), 1)

        state = json.loads((self.ws / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(state["readiness_stage"], "SPECS_BELOW_THRESHOLD")
        self.assertTrue(state["specs_gate"]["strict"])
        self.assertTrue(state["specs_gate"]["below_threshold"])


if __name__ == "__main__":
    unittest.main()
