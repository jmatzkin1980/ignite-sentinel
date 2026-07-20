"""IMP-218 (H11): automated guard that the eval runner gates the four agentic
commands H10 verified by hand — /self-review, /compose, /context-request, and
/scrutinize --mode implementability-probe — including the cite-or-silence
invariant (a fabricated citation is rejected). These convert that manual
verification into a guard that fails ``python -m unittest`` on regression.

Mirrors the run_fixture guard pattern in test_evals_prd.py: load the runner as
a module and assert its deterministic gate helpers report green.
"""
from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_runner():
    spec = importlib.util.spec_from_file_location(
        "run_discovery_evals", REPO_ROOT / "tests" / "evals" / "run_discovery_evals.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class AgenticCommandEvalGuards(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runner = _load_runner()

    def test_self_review_gate_is_green(self):
        result = self.runner.self_review_eval()
        self.assertTrue(result["ok"], result["mismatches"])

    def test_compose_gate_is_green(self):
        result = self.runner.compose_eval()
        self.assertTrue(result["ok"], result["mismatches"])

    def test_context_request_gate_is_green(self):
        result = self.runner.context_request_eval()
        self.assertTrue(result["ok"], result["mismatches"])

    def test_implementability_probe_gate_is_green(self):
        result = self.runner.implementability_probe_eval()
        self.assertTrue(result["ok"], result["mismatches"])


if __name__ == "__main__":
    unittest.main()
