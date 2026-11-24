"""IMP-408 (H27 inc 2) task 2: rejection messages that say how to fix, and drafted-by vs decided-by."""
from __future__ import annotations

import json
import shutil
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import IDS_SCOPE_ANSWER, SnapshotWorkspaceCase, run_ok  # noqa: E402

from sentinel.gap_resolution import apply_gap_responses, render_resolution_rows  # noqa: E402
from sentinel.gaps import parse_gap_responses  # noqa: E402
from sentinel.source_conflicts import declares_unvalidated, unvalidated_trigger  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"
PID = "H27M"
SCOPE = {"id": "GAP-SCOPE", "lens": "product", "severity": "high", "status": "OPEN", "question": "¿Alcance?", "description": "x"}
NOTE_BORDER_ES = ("el bloque Borde va debajo de Respuesta, no de Estado de decisión: movelo (con sus líneas) "
                  "debajo de `- Respuesta:` y volvé a correr /resolve-gaps")
NOTE_BORDER_EN = ("the Border block goes under Answer, not under Decision status: move it (with its lines) "
                  "under `- Answer:` and run /resolve-gaps again")


def apply(text: str, language: str = "es") -> dict:
    return apply_gap_responses([dict(SCOPE)], parse_gap_responses(text), language=language)


class Misplaced(unittest.TestCase):
    def test_border_under_decision_status(self):
        text = ("### GAP-SCOPE\n- Respuesta: El alta con aprobación por monto.\n- Estado de decisión: confirmado\n"
                "  - Borde:\n    - nuevo | pantalla | Bandeja de aprobaciones\n")
        result = apply(text)
        gap = result["gaps"][0]
        self.assertEqual(gap["status"], "PARTIALLY_CLOSED")
        self.assertEqual(gap["resolution_note"], NOTE_BORDER_ES)
        self.assertEqual(result["findings"][0], f"GAP-SCOPE: {NOTE_BORDER_ES}")
        self.assertTrue(result["findings"][0].startswith("GAP-SCOPE: el bloque Borde va debajo de Respuesta, no de Estado de decisión"))
        text_en = ("### GAP-SCOPE\n- Answer: Supplier registration with approval by amount.\n- Decision status: confirmed\n"
                   "  - Border:\n    - nuevo | pantalla | Bandeja de aprobaciones\n")
        self.assertEqual(apply(text_en, "en")["gaps"][0]["resolution_note"], NOTE_BORDER_EN)

    def test_other_field_under_decision_status(self):
        text = ("### GAP-SCOPE\n- Respuesta: El alta con aprobación por monto.\n- Estado de decisión: confirmado\n"
                "  - Delta: ADDED\n")
        gap = apply(text)["gaps"][0]
        self.assertEqual(gap["resolution_note"],
                         "el campo Delta va al mismo nivel que los demás campos, no debajo de Estado de decisión")
        text_en = text.replace("Respuesta", "Answer").replace("Estado de decisión", "Decision status").replace("confirmado", "confirmed")
        self.assertEqual(apply(text_en, "en")["gaps"][0]["resolution_note"],
                         "the Delta field goes at the same level as the other fields, not under Decision status")

    def test_plain_ambiguous_unchanged(self):
        text = "### GAP-SCOPE\n- Respuesta: El alta con aprobación por monto.\n- Estado de decisión: quizás\n"
        self.assertEqual(apply(text)["gaps"][0]["resolution_note"],
                         "ambiguous: answer present but no recognizable decision status")


class Trigger(unittest.TestCase):
    def test_unvalidated_trigger_names_the_word(self):
        self.assertEqual(unvalidated_trigger("# Respuestas al alcance — BORRADOR\n\n### GAP-SCOPE\n"),
                         {"line": 1, "text": "# Respuestas al alcance — BORRADOR", "term": "BORRADOR"})
        found = unvalidated_trigger("# Respuestas\n\nEstado: no validado\n")
        self.assertEqual((found["line"], found["term"]), (3, "no validado"))
        self.assertIsNone(unvalidated_trigger("# Respuestas al alcance\n\n### GAP-SCOPE\n"))
        for text in ("# Respuestas — BORRADOR\n", "Estado: no validado\n", "# Respuestas\n",
                     "Este documento es un borrador\n", "El botón Guardar borrador\n"):
            self.assertEqual(declares_unvalidated(text), unvalidated_trigger(text) is not None)


class Drafted(unittest.TestCase):
    def block(self, owner: str = "", drafted: str = "- Redactado por: Agente Sentinel\n") -> str:
        return ("### GAP-SCOPE\n- Respuesta: El alta con aprobación por monto.\n" + drafted
                + (f"- Owner / fuente: {owner}\n" if owner else "") + "- Estado de decisión: confirmado\n")

    def test_drafted_by_agent_without_owner(self):
        result = apply(self.block())
        gap = result["gaps"][0]
        self.assertEqual(gap["status"], "CLOSED")
        self.assertEqual(gap["decided_by"], "BA (sin nombre)")
        self.assertEqual(gap["drafted_by"], "Agente Sentinel")
        self.assertTrue(any("lo redactó Agente Sentinel y nadie lo firmó como decisión" in f for f in result["findings"]))
        self.assertIn("_(decided by: BA (sin nombre); drafted by: Agente Sentinel)_", render_resolution_rows([gap]))
        english = apply(self.block().replace("Redactado por", "Drafted by"), "en")
        self.assertTrue(any("drafted by Agente Sentinel and nobody signed it as a decision" in f for f in english["findings"]))
        self.assertEqual(english["gaps"][0]["decided_by"], "BA (unnamed)")

    def test_drafted_by_with_named_owner(self):
        result = apply(self.block("Jefa de Compras"))
        self.assertEqual(result["gaps"][0]["decided_by"], "Jefa de Compras")
        self.assertFalse(any("nadie lo firmó" in f for f in result["findings"]))
        self.assertEqual(apply(self.block("Agente"))["gaps"][0]["decided_by"], "BA (sin nombre)")

    def test_no_drafted_by_no_change(self):
        gap = apply(self.block("Jefa de Compras", drafted=""))["gaps"][0]
        self.assertNotIn("decided_by", gap)
        self.assertNotIn("drafted_by", gap)
        self.assertNotIn("drafted by", render_resolution_rows([gap]))


class ChangeFlow(SnapshotWorkspaceCase):
    @classmethod
    def build_workspace(cls):
        shutil.copy(FIXTURES / "change_extraction" / "pedido_ids.md", Path.cwd() / "pedido.md")
        run_ok(["init", PID])
        run_ok(["ingest", PID, "--source", "pedido.md", "--change"])

    def resolve(self, text: str) -> dict:
        (Path.cwd() / "respuestas.md").write_text(text, encoding="utf-8")
        return json.loads(run_ok(["resolve-gaps", PID, "--source", "respuestas.md", "--change", "CHG-001"]))

    def test_resolve_reports_the_line(self):
        out = self.resolve("# Respuestas al alcance — BORRADOR\n\n" + IDS_SCOPE_ANSWER)
        self.assertIn("GAP-SCOPE", out["answered"])
        self.assertTrue(out["closure_findings"][0].startswith(
            "el archivo se declara no validado por la línea 1 («# Respuestas al alcance — BORRADOR», palabra «BORRADOR»)"))
        self.assertEqual(out["unvalidated_trigger"]["line"], 1)

    def test_border_surface_with_draft_word_triggers_nothing(self):
        text = IDS_SCOPE_ANSWER.replace("Bandeja de aprobaciones", 'Botón "Guardar borrador"')
        out = self.resolve(text)
        self.assertIsNone(out["unvalidated_trigger"])
        self.assertIn("GAP-SCOPE", out["closed"])

    def test_owners_in_change_result(self):
        text = IDS_SCOPE_ANSWER.replace("- Owner / fuente: Jefa de Compras", "- Redactado por: agente")
        out = self.resolve(text)
        self.assertEqual(out["owners"], {"GAP-SCOPE": {"decided_by": "BA (sin nombre)", "drafted_by": "agente"}})
        self.assertIn("GAP-SCOPE", out["closed"])


if __name__ == "__main__":
    unittest.main()
