"""Per-unit inquisitive lenses (IMP-116).

Gaps are anchored to the Requirement Unit (RU-*, IMP-115) whose cited evidence
explains them, and a trigger token present in one unit no longer suppresses an
inquisitive gap that belongs to another. Behavior without units is identical to
``detect_gaps`` so existing workspaces are untouched.
"""
from __future__ import annotations

import unittest

from sentinel.discovery import (
    AnnotationError,
    detect_gaps,
    detect_unit_anchored_gaps,
    extract_requirement_units,
    parse_gap_rows,
    render_gaps,
    validate_agent_gaps,
)


# "database"/"persist" (a backend counterpart) appears in the login unit and, at
# the document scope, suppresses GAP-BACKEND-SURFACE for the API integration
# unit that has no contract/persistence/failure detail of its own.
CROSS_SUPPRESSION_TEXT = (
    "The login screen persists sessions in a database. "
    "We also need an API integration with the CRM."
)


class PerUnitDetectionTests(unittest.TestCase):
    def test_token_in_one_unit_does_not_suppress_gap_in_another(self):
        global_gaps = {gap["id"] for gap in detect_gaps(CROSS_SUPPRESSION_TEXT)}
        # Document-level scan is fooled by the counterpart in the login unit.
        self.assertNotIn("GAP-BACKEND-SURFACE", global_gaps)

        units = extract_requirement_units(CROSS_SUPPRESSION_TEXT)
        anchored = detect_unit_anchored_gaps(CROSS_SUPPRESSION_TEXT, {}, units)
        backend = [gap for gap in anchored if gap["id"] == "GAP-BACKEND-SURFACE"]
        # Per-unit scoping resurfaces it, anchored to the unit that explains it.
        self.assertEqual(len(backend), 1)
        self.assertTrue(backend[0]["unit"].startswith("RU-"))

    def test_every_gap_carries_a_unit_field_when_units_exist(self):
        units = extract_requirement_units(CROSS_SUPPRESSION_TEXT)
        anchored = detect_unit_anchored_gaps(CROSS_SUPPRESSION_TEXT, {}, units)
        for gap in anchored:
            self.assertIn("unit", gap)

    def test_no_duplicate_gap_ids_after_anchoring(self):
        units = extract_requirement_units(CROSS_SUPPRESSION_TEXT)
        anchored = detect_unit_anchored_gaps(CROSS_SUPPRESSION_TEXT, {}, units)
        ids = [gap["id"] for gap in anchored]
        self.assertEqual(len(ids), len(set(ids)))

    def test_without_units_behavior_is_identical_to_detect_gaps(self):
        base = detect_gaps(CROSS_SUPPRESSION_TEXT)
        self.assertEqual(detect_unit_anchored_gaps(CROSS_SUPPRESSION_TEXT, {}, None), base)
        self.assertEqual(detect_unit_anchored_gaps(CROSS_SUPPRESSION_TEXT, {}, []), base)


class RenderRoundtripTests(unittest.TestCase):
    def test_unit_column_renders_and_roundtrips(self):
        gaps = [
            {
                "id": "GAP-BACKEND-SURFACE",
                "lens": "technical",
                "severity": "medium",
                "status": "OPEN",
                "description": "Backend surface unclear.",
                "question": "What is the contract?",
                "evidence_mention": "api",
                "origin": "checklist",
                "unit": "RU-002",
            }
        ]
        rendered = render_gaps("ACME", gaps, "REQ-001", "en")
        self.assertIn("| Resolution Note | Unit |", rendered)
        parsed = parse_gap_rows(rendered)
        self.assertEqual(parsed[0]["unit"], "RU-002")

    def test_legacy_rows_without_unit_parse_unchanged(self):
        legacy = (
            "| GAP-001 | product | high | OPEN | REQ-001 | Missing users | Who? | client | quote | agent | pending |\n"
        )
        parsed = parse_gap_rows(legacy)
        self.assertEqual(parsed[0]["resolution_note"], "pending")
        self.assertNotIn("unit", parsed[0])


class AgentUnitTests(unittest.TestCase):
    RAW = "We need an API integration with the CRM and a login with roles."

    def _payload(self, unit_value):
        return {
            "gaps": [
                {
                    "id": "GAP-BACKEND-SURFACE",
                    "lens": "technical",
                    "severity": "medium",
                    "question": "What is the integration contract?",
                    "evidence": "API integration with the CRM",
                    "unit": unit_value,
                }
            ]
        }

    def test_optional_unit_is_accepted_and_normalized(self):
        validated = validate_agent_gaps(self._payload("ru-003"), self.RAW)
        self.assertEqual(validated[0]["unit"], "RU-003")

    def test_missing_unit_is_allowed(self):
        payload = self._payload("ru-003")
        del payload["gaps"][0]["unit"]
        validated = validate_agent_gaps(payload, self.RAW)
        self.assertNotIn("unit", validated[0])

    def test_malformed_unit_is_rejected(self):
        with self.assertRaises(AnnotationError):
            validate_agent_gaps(self._payload("RU-3"), self.RAW)


if __name__ == "__main__":
    unittest.main()
