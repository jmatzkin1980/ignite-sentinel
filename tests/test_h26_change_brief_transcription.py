"""IMP-398 (H26 inc 1): the change brief transcribes harvest divergences and cross-cutting facts."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from sentinel.compilers.change_brief import render_change_brief  # noqa: E402

CITE_PATH = "`00_raw/02_technology_context/sad.md`"
QUOTE = "Ninguna existe en las 94/99 migraciones"


def _gap(gap_id: str, **extra) -> dict:
    gap = {"id": gap_id, "status": "CLOSED", "closure_reason": "by_baseline", "lens": "technical",
           "severity": "high", "answer": "No hay migraciones previas", "owner": "",
           "evidence": f'{CITE_PATH} "{QUOTE}"', "blocks": False}
    gap.update(extra)
    return gap


def _facts() -> list[dict]:
    return [
        {"kind": "fact", "block": "B1", "text": "Monolito modular con capa de servicios.", "ref": "api:README.md"},
        {"kind": "fact", "block": "B5", "text": "Los logs salen en formato JSON.", "ref": "api:ops.md"},
        {"kind": "fact", "block": "B2", "text": "El envio valida datos fiscales.", "ref": "api:envio.py"},
    ]


def _inputs(gaps: list[dict], border: list[dict], language: str = "es") -> dict:
    return {"project_id": "P", "change_id": "CHG-001", "change": {"source": "n.md", "border": border},
            "language": language, "gaps": gaps, "harvest": {"entries": _facts()}, "note_title": "Nota"}


def _border(*types: str) -> list[dict]:
    return [{"zone": "nuevo", "type": t, "name": f"x-{t}", "cite": "GAP-SCOPE"} for t in types]


class DivergenceClosedByBaseline(unittest.TestCase):
    def test_divergence_shows_answer_and_support_not_ya_existe(self):
        gaps = [_gap("GAP-HRV-ABCD1234", description="⚠ README vs code divergence (a): x", origin="harvest")]
        text, _ = render_change_brief(_inputs(gaps, _border("endpoint")))
        self.assertIn(f"No hay migraciones previas — Respaldo en la línea de base: «{QUOTE}» "
                      "(`00_raw/02_technology_context/sad.md`, GAP-HRV-ABCD1234)", text)
        self.assertNotIn("Ya existe: «", text)

    def test_divergence_in_english(self):
        gaps = [_gap("GAP-HRV-ABCD1234", origin="harvest")]
        text, _ = render_change_brief(_inputs(gaps, _border("endpoint"), "en"))
        self.assertIn(f"No hay migraciones previas — Baseline support: «{QUOTE}»", text)
        self.assertNotIn("Already exists: «", text)

    def test_plain_by_baseline_keeps_ya_existe(self):
        gaps = [_gap("GAP-BUSINESS-RULES")]
        text, _ = render_change_brief(_inputs(gaps, _border("endpoint")))
        self.assertIn(f"Ya existe: «{QUOTE}»", text)
        self.assertNotIn("Respaldo en la línea de base", text)


class CrossCuttingFacts(unittest.TestCase):
    def test_b1_and_b5_enter_with_a_technical_border(self):
        for surface in ("endpoint", "dato", "integracion", "proceso"):
            text, _ = render_change_brief(_inputs([], _border(surface)))
            self.assertIn("Monolito modular con capa de servicios. (api:README.md, B1)", text, surface)
            self.assertIn("Los logs salen en formato JSON. (api:ops.md, B5)", text, surface)

    def test_facts_sit_in_s1_and_technical_lens(self):
        text, _ = render_change_brief(_inputs([], _border("endpoint")))
        s1 = text.split("## 2.")[0]
        s5 = text.split("## 5.")[1].split("## 6.")[0]
        self.assertIn("(api:README.md, B1)", s1)
        self.assertIn("(api:ops.md, B5)", s5)
        self.assertNotIn("(api:ops.md, B5)", s1)
        self.assertNotIn("(api:README.md, B1)", s5)

    def test_without_technical_border_they_do_not_appear(self):
        text, _ = render_change_brief(_inputs([], _border("pantalla", "regla", "rol")))
        self.assertNotIn("B1)", text)
        self.assertNotIn("B5)", text)


if __name__ == "__main__":
    unittest.main()
