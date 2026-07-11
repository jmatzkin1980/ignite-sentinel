from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from sentinel.discovery import gap_question_warnings
from sentinel.discovery.momtest import (
    hypothetical_trigger,
    momtest_warning_line,
    scan_questions,
)
from sentinel.validation import momtest_gap_warnings


class MomTestTriggerTest(unittest.TestCase):
    """IMP-180: the declarative bilingual Mom-Test heuristic."""

    def test_english_hypothetical_flagged(self) -> None:
        # "would you" is the earliest matching trigger; either phrasing flags it.
        self.assertEqual(
            hypothetical_trigger("Would you like a dashboard for delivery status?"),
            "would you",
        )

    def test_spanish_hypothetical_flagged(self) -> None:
        self.assertEqual(
            hypothetical_trigger("¿Le gustaría recibir una notificación por email?"),
            "le gustaría",
        )

    def test_spanish_hypothetical_without_accents_flagged(self) -> None:
        # Detection survives input that drops diacritics.
        self.assertEqual(
            hypothetical_trigger("Estaria dispuesto a pagar por el servicio?"),
            "estaria dispuesto",
        )

    def test_past_event_question_is_silent_english(self) -> None:
        self.assertIsNone(
            hypothetical_trigger("Walk me through the last time an order shipped late.")
        )

    def test_past_event_question_is_silent_spanish(self) -> None:
        self.assertIsNone(
            hypothetical_trigger("¿Qué pasó la última vez que un pedido se demoró?")
        )

    def test_concrete_current_process_question_is_silent(self) -> None:
        self.assertIsNone(
            hypothetical_trigger("How do you currently notify a customer when an order ships?")
        )

    def test_system_capacity_allowlist_is_silent(self) -> None:
        # Adversarial seed doc 39 §4.1: legitimately hypothetical future *system*
        # capability is not a personal-opinion hypothetical.
        self.assertIsNone(
            hypothetical_trigger("What if the system faces peak load at 10x volume?")
        )

    def test_empty_question_is_silent(self) -> None:
        self.assertIsNone(hypothetical_trigger(""))
        self.assertIsNone(hypothetical_trigger("   "))


class MomTestScanTest(unittest.TestCase):
    def test_scan_cites_question_verbatim(self) -> None:
        findings = scan_questions(
            [
                ("GAP-A", "Would you want weekly reports?"),
                ("GAP-B", "What did you do the last time this failed?"),
            ]
        )
        self.assertEqual(len(findings), 1)
        finding = findings[0]
        self.assertEqual(finding["gap_id"], "GAP-A")
        self.assertEqual(finding["question"], "Would you want weekly reports?")
        self.assertEqual(finding["severity"], "warning")
        line = momtest_warning_line(finding)
        self.assertIn("GAP-A", line)
        self.assertIn("Would you want weekly reports?", line)
        self.assertIn("Mom-Test", line)


class MomTestGapHelperTest(unittest.TestCase):
    def test_agent_question_hypothetical_flagged(self) -> None:
        gaps = [
            {"id": "GAP-OPINION", "question": "¿Le gustaría un panel de soporte?"},
            {"id": "GAP-FACT", "question": "¿Cómo hacen hoy para avisar al cliente?"},
        ]
        warnings = gap_question_warnings(gaps, "es")
        self.assertEqual([w["gap_id"] for w in warnings], ["GAP-OPINION"])

    def test_builtin_checklist_questions_are_not_hypothetical(self) -> None:
        # The curated checklist questions ask about scope/rules/acceptance, never
        # about a hypothetical future preference — no false positives.
        gaps = [
            {"id": "GAP-OBJECTIVE"},
            {"id": "GAP-SCOPE"},
            {"id": "GAP-ACCEPTANCE"},
            {"id": "GAP-BUSINESS-RULES"},
        ]
        self.assertEqual(gap_question_warnings(gaps, "es"), [])
        self.assertEqual(gap_question_warnings(gaps, "en"), [])


class MomTestValidationTest(unittest.TestCase):
    HEADER = (
        "| Gap ID | Lens | Severity | Status | Parent | Description | Question | Source |\n"
        "|---|---|---|---|---|---|---|---|\n"
    )

    def _write_gaps(self, question: str) -> Path:
        tmp = Path(tempfile.mkdtemp())
        discovery = tmp / "01_discovery"
        discovery.mkdir(parents=True)
        row = f"| GAP-X | product | high | OPEN | `REQ-001` | Desc | {question} | Source input. |\n"
        (discovery / "gaps.md").write_text(self.HEADER + row, encoding="utf-8")
        return tmp

    def test_hypothetical_question_in_gaps_md_warns_with_citation(self) -> None:
        base = self._write_gaps("Would you like an opt-out toggle?")
        warnings = momtest_gap_warnings(base)
        self.assertEqual(len(warnings), 1)
        self.assertIn("GAP-X", warnings[0])
        self.assertIn("Would you like an opt-out toggle?", warnings[0])

    def test_past_event_question_in_gaps_md_is_silent(self) -> None:
        base = self._write_gaps("What happened the last time an order shipped?")
        self.assertEqual(momtest_gap_warnings(base), [])

    def test_missing_gaps_md_is_silent(self) -> None:
        self.assertEqual(momtest_gap_warnings(Path(tempfile.mkdtemp())), [])


if __name__ == "__main__":
    unittest.main()
