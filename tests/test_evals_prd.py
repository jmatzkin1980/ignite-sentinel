"""Regression guards for PRD/specs eval baselines.

The eval runner reaches phase 2 (`/specs`) and records PRD target-section
coverage plus fixed specs scaffolding. IMP-039 lifted PRD coverage and IMP-042
keeps specs scaffolding at zero.
"""
from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "evals"


def _load_runner():
    spec = importlib.util.spec_from_file_location(
        "run_discovery_evals", REPO_ROOT / "tests" / "evals" / "run_discovery_evals.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PrdAndSpecsEvalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        runner = _load_runner()
        cls.runner = runner
        cls.result = runner.run_fixture(FIXTURES / "support-dashboard")

    def test_prd_section_status_detects_pending_markers(self):
        status = self.runner.prd_section_status(
            "## 1. Executive\n\n[PENDING INPUT]\n\n## 2. Scope\n\nConfirmed scope [REQ-001].\n"
        )
        self.assertEqual(status["1"], "pending")
        self.assertEqual(status["2"], "populated")

    def test_specs_scaffolding_ids_are_counted(self):
        scaffold = self.runner.specs_scaffolding("JTBD-001 CAP-001 CAP-002 US-001 ASM-001")
        self.assertEqual(scaffold["count"], 5)
        self.assertIn("CAP-001", scaffold["ids"])

    def test_phase_two_baseline_is_recorded(self):
        self.assertTrue(self.result["baseline_ok"])
        self.assertEqual(self.result["prd_target_sections"], ["1", "3", "4", "6"])
        self.assertEqual(self.result["prd_target_coverage"], 1.0)
        self.assertEqual(self.result["specs_scaffolding_count"], 0)
        self.assertNotIn("CAP-001", self.result["specs_scaffolding_ids"])


if __name__ == "__main__":
    unittest.main()
