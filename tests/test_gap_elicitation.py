"""Tests for gaps-as-elicitation enrichment (IMP-022).

Each gap must expose three elicitation factors in both gaps.md response sections
and the domain context-request packs: why it matters (risk if left open), what it
unblocks (the downstream brief/PRD/spec section that consumes the answer), and the
expected response format. The framework trace table is unchanged, so
render_gaps -> parse_gap_rows must remain a clean roundtrip and /resolve-gaps keeps
parsing answers with no change for the user.
"""
from __future__ import annotations

import unittest

from sentinel.context_requests import lens_checks_section
from sentinel.discovery import (
    expected_format_for_gap,
    parse_gap_rows,
    render_gaps,
    unblocks_for_gap,
)


SAMPLE_GAPS = [
    {
        "id": "GAP-ACCEPTANCE",
        "lens": "quality",
        "severity": "critical",
        "status": "OPEN",
        "description": "Acceptance criteria or success conditions are missing.",
        "question": "What observable condition tells us the requirement is done?",
        "evidence_mention": "N/A",
        "origin": "checklist",
    },
    {
        "id": "GAP-METRIC-SOURCE",
        "lens": "business",
        "severity": "medium",
        "status": "OPEN",
        "description": "A metric appears without a source.",
        "question": "Where does the baseline for this metric come from?",
        "evidence_mention": "reduce review time",
        "origin": "checklist",
    },
]


class ResponseSectionFactorTests(unittest.TestCase):
    def test_english_sections_expose_three_factors(self):
        out = render_gaps("demo", SAMPLE_GAPS, "REQ-001", "en")
        for label in (
            "Why it matters (risk if left open):",
            "What answering this unblocks:",
            "Expected response format:",
        ):
            self.assertIn(label, out, label)
        # And the actual content is the gap-specific mapping, not a placeholder.
        self.assertIn(unblocks_for_gap("GAP-ACCEPTANCE"), out)
        self.assertIn(expected_format_for_gap("GAP-METRIC-SOURCE"), out)

    def test_spanish_sections_expose_three_factors(self):
        out = render_gaps("demo", SAMPLE_GAPS, "REQ-001", "es")
        for label in (
            "Por qué importa (riesgo si queda abierto):",
            "Qué desbloquea esta respuesta:",
            "Formato de respuesta esperado:",
        ):
            self.assertIn(label, out, label)
        self.assertIn(unblocks_for_gap("GAP-ACCEPTANCE", "es"), out)


class RoundtripTests(unittest.TestCase):
    """The enrichment must not disturb the positional trace-table parser."""

    def _assert_roundtrip(self, language: str):
        rendered = render_gaps("demo", SAMPLE_GAPS, "REQ-001", language)
        parsed = parse_gap_rows(rendered)
        self.assertEqual([g["id"] for g in parsed], [g["id"] for g in SAMPLE_GAPS])
        for original, got in zip(SAMPLE_GAPS, parsed):
            self.assertEqual(got["id"], original["id"])
            self.assertEqual(got["lens"], original["lens"])
            self.assertEqual(got["severity"], original["severity"])
            self.assertEqual(got["status"], original["status"])
            self.assertEqual(got["question"], original["question"])
            self.assertEqual(got.get("origin"), original["origin"])

    def test_roundtrip_en(self):
        self._assert_roundtrip("en")

    def test_roundtrip_es(self):
        self._assert_roundtrip("es")


class MappingTests(unittest.TestCase):
    def test_known_gap_has_specific_mapping(self):
        # A known gap returns gap-specific text, not the generic default.
        default_unblocks = unblocks_for_gap("GAP-DOES-NOT-EXIST")
        self.assertNotEqual(unblocks_for_gap("GAP-ACCEPTANCE"), default_unblocks)
        default_format = expected_format_for_gap("GAP-DOES-NOT-EXIST")
        self.assertNotEqual(expected_format_for_gap("GAP-ACCEPTANCE"), default_format)

    def test_unknown_gap_falls_back_to_default(self):
        self.assertTrue(unblocks_for_gap("GAP-UNKNOWN-XYZ"))
        self.assertTrue(expected_format_for_gap("GAP-UNKNOWN-XYZ", "es"))


class ContextRequestFactorTests(unittest.TestCase):
    def test_context_request_exposes_unblocks_and_format(self):
        section = lens_checks_section("quality", "en")
        self.assertIn("Unblocks:", section)
        self.assertIn("Expected format:", section)
        # The quality lens carries GAP-ACCEPTANCE; its mapping must appear.
        self.assertIn("GAP-ACCEPTANCE", section)
        self.assertIn(expected_format_for_gap("GAP-ACCEPTANCE"), section)

    def test_context_request_spanish_labels(self):
        section = lens_checks_section("quality", "es")
        self.assertIn("Desbloquea:", section)
        self.assertIn("Formato esperado:", section)


if __name__ == "__main__":
    unittest.main()
