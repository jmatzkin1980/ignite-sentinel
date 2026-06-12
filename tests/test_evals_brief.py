"""Regression guards for the IMP-027 eval extensions.

Locks two falsifiable baselines so future work (IMP-021 /annotate, IMP-024
brief compiler) can be measured against them and cannot regress silently:

- The `expense-approval` fixture demonstrates the lexical ceiling: five gaps
  that are genuinely unaddressed stay suppressed because a single keyword is
  present, so its semantic target_recall is 0.00 today.
- The narrative brief sections (1-3) are compiled from cited evidence by the
  IMP-024 brief compiler, so brief_target_coverage is 1.00 for expense-approval.

Deterministic and local-first: runs the real lifecycle in a temp dir, no
network. Importing the eval runner here also smoke-tests its new code paths.
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


class BriefSectionStatusTests(unittest.TestCase):
    def test_marker_makes_section_pending(self):
        runner = _load_runner()
        brief = "## 1. Identidad\n\nTBD from confirmed client language.\n\n## 2. Negocio\n\nFinance approvers own the flow [REQ-001].\n"
        status = runner.brief_section_status(brief)
        self.assertEqual(status["1"], "pending")
        self.assertEqual(status["2"], "populated")


class ExpenseApprovalCeilingTests(unittest.TestCase):
    """Lock the lexical ceiling and the brief baseline for the new fixture."""

    @classmethod
    def setUpClass(cls):
        runner = _load_runner()
        cls.result = runner.run_fixture(FIXTURES / "expense-approval")

    def test_baseline_ok(self):
        # must_fire detected, no new false positives.
        self.assertTrue(self.result["baseline_ok"], self.result["missing_must_fire"])
        self.assertEqual(self.result["new_false_positives"], [])

    def test_lexical_ceiling_suppresses_semantic_gaps(self):
        # The five buzzword-suppressed gaps must NOT fire under the keyword
        # engine; this is the metric IMP-021 must move above 0.
        self.assertEqual(self.result["target_fire_total"], 5)
        self.assertEqual(self.result["target_fire_detected"], [])
        self.assertEqual(self.result["target_recall"], 0.0)

    def test_brief_compiler_populates_evidence_sections(self):
        # IMP-024: the brief compiler now populates sections 1-3 from cited
        # evidence (objective, actors, scope), moving coverage from 0.0 to 1.0.
        self.assertEqual(self.result["brief_target_sections"], ["1", "2", "3"])
        self.assertEqual(self.result["brief_target_populated"], ["1", "2", "3"])
        self.assertEqual(self.result["brief_target_coverage"], 1.0)

    def test_brief_keeps_unsupported_sections_pending(self):
        # The eval should protect both sides of "evidence or silence":
        # confirmed sections populate, unsupported sections remain pending.
        self.assertEqual(self.result["brief_expected_pending_sections"], ["4", "5", "6"])
        self.assertEqual(self.result["brief_expected_pending_matched"], ["4", "5", "6"])
        self.assertEqual(self.result["brief_expected_pending_coverage"], 1.0)

    def test_detected_language_and_gap_metadata_match_answer_key(self):
        self.assertEqual(self.result["detected_language"], "en")
        self.assertEqual(self.result["gap_detail_mismatches"], [])
        self.assertGreaterEqual(self.result["origin_counts"].get("checklist", 0), 1)


class AnnotatedDiscoveryEvalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        runner = _load_runner()
        cls.result = runner.run_fixture(FIXTURES / "expense-approval", apply_annotation=True)

    def test_annotation_closes_semantic_target_recall_with_agent_origin(self):
        self.assertEqual(self.result["target_fire_total"], 5)
        self.assertEqual(len(self.result["target_fire_detected"]), 5)
        self.assertEqual(self.result["target_recall"], 1.0)
        self.assertEqual(self.result["gap_detail_mismatches"], [])
        self.assertGreaterEqual(self.result["origin_counts"].get("agent", 0), 5)


if __name__ == "__main__":
    unittest.main()
