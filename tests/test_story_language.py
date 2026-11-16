"""IMP-324: the generated stories speak the project's language.

The independent review found an English project whose story read "As a target user, I want
when a patient confirms ... so that la capacidad confirmada se puede planificar..." and whose
acceptance criteria carried Spanish text with a doubled "When When". compilers/slicing.py had
no language at all, and used the EARS statement (which starts with "When") as the goal and as
the criterion's "when".
"""
from __future__ import annotations

import unittest

from sentinel.compilers.slicing import (
    acceptance_criteria_for_enabler,
    acceptance_criteria_for_pending_story,
    acceptance_criteria_for_spec_unit_story,
    goal_for_spec_unit,
    strip_ears_lead,
)

UNIT = {"id": "SPEC-U-001", "statement": "When a patient confirms a booking, the system shall reserve the slot.",
        "ears": ["REQ-EARS-001"]}
SPANISH_MARKERS = ("esta confirmado", "el sistema produce", "la falla", "enabler fue propuesto", "no existe una Spec Unit")


class StoryLanguageTests(unittest.TestCase):
    def test_english_criteria_have_no_spanish(self):
        criteria = acceptance_criteria_for_spec_unit_story("US-001", UNIT, UNIT["statement"], "en")
        criteria += acceptance_criteria_for_enabler("US-002", {}, "en")
        criteria += acceptance_criteria_for_pending_story("US-003", "en")
        text = " ".join(f"{c['given']} {c['when']} {c['then']}" for c in criteria)
        for marker in SPANISH_MARKERS:
            self.assertNotIn(marker, text)

    def test_spanish_criteria_keep_their_text(self):
        criteria = acceptance_criteria_for_spec_unit_story("US-001", UNIT, UNIT["statement"], "es")
        self.assertIn("esta confirmado", criteria[0]["given"])

    def test_no_doubled_when_and_no_i_want_when(self):
        criteria = acceptance_criteria_for_spec_unit_story("US-001", UNIT, UNIT["statement"], "en")
        self.assertFalse(criteria[0]["when"].lower().startswith("when "))
        self.assertFalse(goal_for_spec_unit(UNIT, "en").lower().startswith("when "))
        self.assertEqual(strip_ears_lead("Cuando el paciente confirma, el sistema reserva."), "el paciente confirma, el sistema reserva.")

    def test_criteria_ids_and_names_are_unchanged(self):
        criteria = acceptance_criteria_for_spec_unit_story("US-001", UNIT, UNIT["statement"], "en")
        self.assertEqual([c["id"] for c in criteria], [f"AC-001-0{i}" for i in range(1, 6)])
        self.assertEqual(criteria[0]["name"], "Spec Unit Happy Path")
        self.assertEqual(criteria[3]["classification"], "pass-to-pass")


if __name__ == "__main__":
    unittest.main()
