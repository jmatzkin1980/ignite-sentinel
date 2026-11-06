"""Faithfulness claim eval wired into the unit suite.

``tests/evals/run_faithfulness_claim_evals.py`` checks the no-invention rule
end to end: a fully supported artifact must score 1.0 and a planted silent
invention must be caught (score below 1.0, the invented claims reported as
unsupported). It used to run only by hand, so a regression in
``sentinel.validation.artifact_faithfulness_report`` could pass ``verify.ps1``.
This test runs the same evaluation (in-process, no report written).
"""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_runner():
    spec = importlib.util.spec_from_file_location(
        "run_faithfulness_claim_evals", REPO_ROOT / "tests" / "evals" / "run_faithfulness_claim_evals.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FaithfulnessClaimEvalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = _load_runner().build_report()
        cls.by_fixture = {r["fixture"]: r for r in cls.report["fixtures"]}

    def test_eval_is_falsable(self):
        scores = {name: r["score"] for name, r in self.by_fixture.items()}
        self.assertTrue(self.report["falsable_ok"], f"faithful must score 1.0 and silent_invention < 1.0: {scores}")

    def test_every_fixture_matches_its_answer_key(self):
        for name, result in self.by_fixture.items():
            with self.subTest(fixture=name):
                self.assertTrue(result["ok"], result["mismatches"])

    def test_both_sides_of_the_trap_are_present(self):
        # Without both fixtures `falsable_ok` would be vacuous.
        self.assertIn("faithful", self.by_fixture)
        self.assertIn("silent_invention", self.by_fixture)
        self.assertGreater(self.by_fixture["silent_invention"]["unsupported_claim_count"], 0)
        self.assertEqual(self.by_fixture["faithful"]["unsupported_claim_count"], 0)


if __name__ == "__main__":
    unittest.main()
