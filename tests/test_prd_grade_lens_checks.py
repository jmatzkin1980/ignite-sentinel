"""Regression tests for IMP-046 PRD-grade lens checks."""
from __future__ import annotations

import unittest

from sentinel.discovery import detect_gaps, expected_format_for_gap, question_for_gap, unblocks_for_gap


class PrdGradeLensChecksTests(unittest.TestCase):
    def test_persona_detail_not_suppressed_by_business_objective(self):
        text = (
            "The objective is to reduce manual work. Users are finance analysts. "
            "Scope is the review dashboard."
        )
        gaps = {gap["id"] for gap in detect_gaps(text)}
        self.assertIn("GAP-PRD-PERSONA-DETAIL", gaps)

    def test_nfr_kpi_not_suppressed_by_metric_target_without_measurement_detail(self):
        text = (
            "We expect this dashboard to reduce preparation effort by around 30%. "
            "The main users are support team leads and the scope is read-only."
        )
        gaps = {gap["id"] for gap in detect_gaps(text)}
        self.assertIn("GAP-PRD-NFR-KPI", gaps)
        self.assertIn("GAP-METRIC-SOURCE", gaps)

    def test_rollout_environment_check_has_elicitation_mapping(self):
        text = "We need a portal for customers. The objective, users, and scope are clear."
        gaps = {gap["id"]: gap for gap in detect_gaps(text)}
        self.assertIn("GAP-PRD-ROLLOUT-ENVIRONMENTS", gaps)
        self.assertIn("rollout", question_for_gap("GAP-PRD-ROLLOUT-ENVIRONMENTS").lower())
        self.assertNotIn("currently has no confirmed evidence", unblocks_for_gap("GAP-PRD-ROLLOUT-ENVIRONMENTS"))
        self.assertIn("rollout", expected_format_for_gap("GAP-PRD-ROLLOUT-ENVIRONMENTS").lower())


if __name__ == "__main__":
    unittest.main()
