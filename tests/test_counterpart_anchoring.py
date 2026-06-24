"""End of false maturity: counterpart anchoring for surface concepts (IMP-117).

Naming a surface concept (metric/KPI/indicator, auth/login/permission/role)
without its counterpart must NOT count as coverage: the mention anchors a cited,
medium (non-blocking) gap instead of suppressing the question. When the
counterpart is present the gap is suppressed, and when the concept is not named
at all nothing fires (this is what distinguishes the ``mention_requires_counterpart``
rule from the broader ``mention_without_counterpart`` surface checks).
"""
from __future__ import annotations

import unittest

from sentinel.discovery import detect_gaps


def gap_ids(text: str) -> set[str]:
    return {gap["id"] for gap in detect_gaps(text)}


def gap_by_id(text: str, gap_id: str) -> dict | None:
    return next((gap for gap in detect_gaps(text) if gap["id"] == gap_id), None)


class MetricDefinitionTests(unittest.TestCase):
    def test_named_metric_without_counterpart_fires_cited_and_medium(self):
        gap = gap_by_id("We will track key metrics and KPIs for the team.", "GAP-METRIC-DEFINITION")
        self.assertIsNotNone(gap)
        self.assertEqual(gap["severity"], "medium")
        self.assertEqual(gap["lens"], "business")
        self.assertTrue(gap.get("evidence_mention"))

    def test_metric_with_counterpart_is_suppressed(self):
        text = "Track the conversion metric; its source is the CRM and the baseline is last quarter."
        self.assertNotIn("GAP-METRIC-DEFINITION", gap_ids(text))

    def test_metric_concept_absent_does_not_fire(self):
        # The discriminating guard vs. the broad surface rule: no concept, no gap.
        self.assertNotIn("GAP-METRIC-DEFINITION", gap_ids("We want a read-only dashboard for support leads."))


class AuthModelTests(unittest.TestCase):
    def test_named_auth_without_counterpart_fires_cited_and_medium(self):
        gap = gap_by_id("The app needs login and permissions for users.", "GAP-AUTH-MODEL")
        self.assertIsNotNone(gap)
        self.assertEqual(gap["severity"], "medium")
        self.assertEqual(gap["lens"], "technical")
        self.assertTrue(gap.get("evidence_mention"))

    def test_auth_with_counterpart_is_suppressed(self):
        text = "Login uses SSO via OAuth and permissions follow an RBAC model."
        self.assertNotIn("GAP-AUTH-MODEL", gap_ids(text))

    def test_auth_concept_absent_does_not_fire(self):
        self.assertNotIn("GAP-AUTH-MODEL", gap_ids("We want a read-only dashboard for support leads."))

    def test_plain_control_word_does_not_false_trigger_auth(self):
        # "control"/"controles" must not match the role triggers; "in scope" is unrelated.
        self.assertNotIn("GAP-AUTH-MODEL", gap_ids("We need access control reports in scope for the dashboard."))


class NonBlockingTests(unittest.TestCase):
    def test_new_counterpart_gaps_are_medium_only(self):
        text = "We need metrics and login with permissions but no other detail."
        for gap in detect_gaps(text):
            if gap["id"] in {"GAP-METRIC-DEFINITION", "GAP-AUTH-MODEL"}:
                self.assertEqual(gap["severity"], "medium", gap["id"])


if __name__ == "__main__":
    unittest.main()
