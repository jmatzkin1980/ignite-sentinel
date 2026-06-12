"""Tests for the IMP-025 per-section brief readiness and soft /brief gate.

brief_section_readiness classifies the narrative sections 1-6 of the project
brief as populated/pending, scores overall coverage, and names the gaps that feed
each poor section (inverse of the IMP-024 gap→section map). brief_gate_warnings
turns the poor sections into human-readable warnings. The gate is non-blocking by
default and only blocks the advance to READY_FOR_SPECS in opt-in strict mode.
"""
from __future__ import annotations

import unittest

from sentinel.maturity import brief_gate_warnings, brief_section_readiness

# Sections 1-3 evidence-backed (cited), 4-6 explicit [PENDING INPUT].
BRIEF = """# Project Brief - DEMO

## 1. Identidad y Valor

Initiative: Support Dashboard _(source: `00_raw/`)_
- Expected outcome: "reduce prep time" _(source: `00_raw/`)_

## 2. Lente de Negocio: Actores y Necesidades

- The main users are the support team leads. _(source: `00_raw/`)_

## 3. Lente de Producto: Proceso y Journey

- In scope: "read-only dashboard" _(source: `00_raw/`)_

## 4. Lente de Diseno: Flujos y Resiliencia UX

- [PENDING INPUT]: no evidence in client input yet; tracked by `GAP-DESIGN-FLOW`.

## 5. Lente Tecnico: Datos, Conectividad y Arquitectura

- [PENDING INPUT]: no evidence in client input yet; tracked by `GAP-TECH-DATA-SOURCE`.

## 6. Gobernanza y Restricciones

- [PENDING INPUT]: no evidence in client input yet; tracked by `GAP-GOVERNANCE-CONSTRAINTS`.

## 7. Decisiones, Seeds e Inferencias

(not tracked)
"""


class BriefSectionReadinessTests(unittest.TestCase):
    def setUp(self):
        self.r = brief_section_readiness(BRIEF)

    def test_coverage_score_counts_populated_sections(self):
        self.assertEqual(self.r["sections_populated"], 3)
        self.assertEqual(self.r["sections_total"], 6)
        self.assertEqual(self.r["coverage_score"], 0.5)

    def test_per_section_status(self):
        sec = self.r["sections"]
        self.assertEqual(sec["1"]["status"], "populated")
        self.assertEqual(sec["2"]["status"], "populated")
        self.assertEqual(sec["3"]["status"], "populated")
        self.assertEqual(sec["4"]["status"], "pending")
        self.assertEqual(sec["5"]["status"], "pending")
        self.assertEqual(sec["6"]["status"], "pending")

    def test_poor_sections_name_feeding_gaps(self):
        poor = {p["section"]: p["feeding_gaps"] for p in self.r["poor_sections"]}
        self.assertEqual(set(poor), {"4", "5", "6"})
        self.assertIn("GAP-DESIGN-FLOW", poor["4"])
        self.assertIn("GAP-GOVERNANCE-CONSTRAINTS", poor["6"])

    def test_empty_section_is_pending(self):
        r = brief_section_readiness("## 1. Identidad\n\n## 2. Negocio\n\nActors cited _(source: `00_raw/`)_\n")
        self.assertEqual(r["sections"]["1"]["status"], "pending")
        self.assertEqual(r["sections"]["2"]["status"], "populated")


class BriefGateWarningTests(unittest.TestCase):
    def test_warnings_name_sections_and_gaps(self):
        r = brief_section_readiness(BRIEF)
        warnings = brief_gate_warnings(r, "en")
        self.assertEqual(len(warnings), 3)
        self.assertTrue(any("Section 4" in w and "GAP-DESIGN-FLOW" in w for w in warnings))

    def test_spanish_warnings(self):
        r = brief_section_readiness(BRIEF)
        warnings = brief_gate_warnings(r, "es")
        self.assertTrue(any(w.startswith("Sección 4") for w in warnings))

    def test_fully_populated_has_no_warnings(self):
        full = "\n".join(f"## {i}. S{i}\n\nClaim _(source: `00_raw/`)_\n" for i in range(1, 7))
        r = brief_section_readiness(full)
        self.assertEqual(r["coverage_score"], 1.0)
        self.assertEqual(brief_gate_warnings(r), [])


if __name__ == "__main__":
    unittest.main()
