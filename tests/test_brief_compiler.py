"""Tests for the IMP-024 project-brief compiler.

The brief's narrative sections (1-6) must be compiled from real evidence with a
citation instead of generic TBD: section 1 (objective/metrics), 2 (actors) and 3
(as-is/to-be/scope) populate from the raw client input; sections with no anchor
evidence render an explicit [PENDING INPUT] pointing to the tracking gap; and
confirmed answers of closed gaps route to the section they feed (synergy with the
IMP-022 gap→section map). No invented text.
"""
from __future__ import annotations

import unittest

from sentinel.discovery import brief_section_for_gap
from sentinel.maturity import compile_brief_sections, parse_gap_answers

# Markers the eval harness treats as "section still pending".
PENDING_MARKERS = ("TBD", "[PENDING INPUT]", "PENDING DOMAIN", "No structured evidence", "Documentar el", "Documentar la")

RAW_EN = """# Client Request: Support Operations Dashboard

We want a dashboard for our customer support operation. The goal is to reduce the time team leads spend preparing the weekly review meeting.

The main users are the support team leads. They want to see ticket volume, resolution time, and backlog ageing in one screen.

In scope: a read-only dashboard for the current quarter. Out of scope: editing tickets or managing agents from this screen.

We expect this to cut preparation effort by around 30% once the team adopts it.
"""

RAW_ES = """# Pedido del cliente: Portal de autogestion de reclamos

Queremos un portal web para que nuestros clientes finales carguen y consulten sus reclamos sin llamar al call center. El objetivo es bajar el volumen de llamadas.

Los usuarios son los clientes finales de la compania. Tambien el equipo de atencion, que hoy carga los reclamos a mano.

El alcance de la primera version: alta de reclamo, consulta de estado y adjuntar fotos. Fuera de alcance: chat en vivo y notificaciones push.

Hoy el proceso actual es telefonico y queremos pasar a un proceso digital con seguimiento.
"""


def _is_pending(block: str) -> bool:
    return any(marker in block for marker in PENDING_MARKERS)


class EvidenceSectionTests(unittest.TestCase):
    def test_english_sections_1_to_3_populate_with_citation(self):
        sec = compile_brief_sections(RAW_EN, {}, "We want a dashboard.", "en")
        for s in ("1", "2", "3"):
            self.assertFalse(_is_pending(sec[s]), f"section {s} should be populated:\n{sec[s]}")
        # Citations and concrete evidence are present.
        self.assertIn("00_raw/", sec["1"])
        self.assertIn("30%", sec["1"])
        self.assertIn("support team leads", sec["2"])
        self.assertIn("read-only dashboard", sec["3"])

    def test_sections_4_to_6_pending_without_evidence(self):
        sec = compile_brief_sections(RAW_EN, {}, "We want a dashboard.", "en")
        for s in ("4", "5", "6"):
            self.assertIn("[PENDING INPUT]", sec[s], f"section {s} should be pending")

    def test_spanish_sections_populate(self):
        sec = compile_brief_sections(RAW_ES, {}, "Queremos un portal.", "es")
        for s in ("1", "2", "3"):
            self.assertFalse(_is_pending(sec[s]), f"section {s} should be populated:\n{sec[s]}")
        self.assertIn("clientes finales", sec["2"])
        # Spanish as-is cue ("hoy ... a mano") is detected.
        self.assertIn("as-is", sec["3"].lower())


class GapAnswerRoutingTests(unittest.TestCase):
    def test_closed_gap_answer_populates_its_section(self):
        # A confirmed design-flow answer must populate section 4 instead of PENDING.
        gap_answers = {
            "GAP-DESIGN-FLOW": {
                "statement": "Users reach the dashboard from Home > Operations > Daily queues.",
                "source": "CHG-001",
            }
        }
        sec = compile_brief_sections(RAW_EN, gap_answers, "We want a dashboard.", "en")
        self.assertNotIn("[PENDING INPUT]", sec["4"])
        self.assertIn("Home > Operations", sec["4"])
        self.assertIn("GAP-DESIGN-FLOW", sec["4"])

    def test_parse_gap_answers_reads_resolution_tables(self):
        seeds = (
            "## Gap Resolution Seeds\n\n"
            "| Seed ID | Gap ID | Status | Statement | Source | Brief Section |\n"
            "| --- | --- | --- | --- | --- | --- |\n"
            "| AUTO-SEED-CHG-001 | `GAP-GOVERNANCE-CONSTRAINTS` | CONFIRMED | No PII in dashboard logs. | `CHG-001` | 6 |\n"
        )
        answers = parse_gap_answers(seeds)
        self.assertIn("GAP-GOVERNANCE-CONSTRAINTS", answers)
        self.assertEqual(answers["GAP-GOVERNANCE-CONSTRAINTS"]["statement"], "No PII in dashboard logs.")
        # And it routes to section 6.
        self.assertEqual(brief_section_for_gap("GAP-GOVERNANCE-CONSTRAINTS"), "6")


if __name__ == "__main__":
    unittest.main()
