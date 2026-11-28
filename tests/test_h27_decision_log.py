"""IMP-414 (H27 inc 5a) task 5: the decisions annex (A.decisions) of the final change export."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import run_ok  # noqa: E402
from test_h26_cross_record import CID, PID, set_language  # noqa: E402
from test_h27_consolidated_export import FinalCase  # noqa: E402
from test_h27_consolidation import ANSWER  # noqa: E402
from test_h27_decision_conflicts import ClashCase  # noqa: E402

from sentinel.compilers.brief_v2 import BriefInputs, render_brief_v2  # noqa: E402
from sentinel.core.io import forget_read_snapshots  # noqa: E402
from sentinel.crosses.record import record_cross  # noqa: E402


def annex(text: str) -> str:
    return text.split("## A.decisions", 1)[1]


class Pure(unittest.TestCase):
    def inputs(self, **extra) -> BriefInputs:
        return BriefInputs(project_id="BRGD", language="es", profiles=["UI"], genesis="greenfield", **extra)

    def test_project_brief_unchanged(self):
        self.assertEqual(render_brief_v2(self.inputs(extra_annexes=[]))[0], render_brief_v2(self.inputs())[0])

    def test_extra_annex_rendered_last(self):
        text = render_brief_v2(self.inputs(
            extra_annexes=[{"id": "A.decisions", "title": "Registro de decisiones", "lines": ["x"]}]))[0]
        self.assertTrue(text.endswith("## A.decisions Registro de decisiones\n\nx\n"), text[-200:])
        self.assertLess(text.index("## A.provenance"), text.index("## A.decisions"))


class Log(FinalCase):
    def test_log_row(self):
        self.apply()
        text = self.final()
        self.assertIn("## A.decisions Registro de decisiones", text)
        self.assertIn(f"| {self.dis} | 2.2 | {ANSWER} | A | Jefa de Compras |", text)
        self.assertNotIn("A.decisions", self.working())

    def test_assumption_not_in_log(self):
        srd = next(i for i in self.gaps() if i.startswith("GAP-SRD-"))
        path = Path.cwd() / "resp-srd.md"
        path.write_text("\n".join([
            f"### {srd}", "- Respuesta: El historial del auditor se muestra como una pestaña del detalle del alta.",
            "- Owner / fuente: BA de Compras", '- Evidencia o referencia: "quiero consultar quién aprobó cada alta y cuándo"',
            "- Estado de decisión: supuesto", "- Valida: Diseño", ""]), encoding="utf-8")
        forget_read_snapshots()
        out = json.loads(run_ok(["resolve-gaps", PID, "--source", str(path), "--change", CID]))
        self.assertEqual(out["assumed"], [srd])
        text = self.final()
        self.assertNotIn(srd, annex(text))
        self.assertIn("ASM-" + srd[4:], text.split("### 8.1", 1)[1].split("## A.", 1)[0])

    def test_delegated_row(self):
        other = next(g for g in self.gaps() if g.startswith("GAP-SED-"))
        path = Path.cwd() / "resp-del.md"
        path.write_text("\n".join([
            f"### {other}", "- Respuesta: Rige el pedido del área de Compras.", "- Opción: B",
            "- Owner / fuente: Jefa de Compras", f"- Evidencia o referencia: {self.ids()['pedido']}:1",
            "- Estado de decisión: confirmado", "- Confirmado por: delegación del BA", ""]), encoding="utf-8")
        forget_read_snapshots()
        run_ok(["resolve-gaps", PID, "--source", str(path), "--change", CID])
        row = next(line for line in annex(self.final()).splitlines() if line.startswith(f"| {other} |"))
        self.assertTrue(row.endswith("| B | delegado |"), row)

    def test_english_log(self):
        self.apply()
        set_language(PID, "en")
        text = self.final()
        self.assertIn("## A.decisions Decision log", text)
        self.assertIn("| GAP | Section | What was decided | Option | Decided by |", text)


class Clash(ClashCase):
    def test_superseded_row(self):
        first, _second, result = self.clash()
        chq = result["decision_conflicts"][0]
        self.answer(chq, "Rige lo que decidió la jefa.", "A")
        build = __import__("sentinel.extraction.inventory", fromlist=["build_inventory"]).build_inventory
        build(PID, CID)
        forget_read_snapshots()
        from sentinel.compilers.change_deliverable import render_change_deliverable
        text = render_change_deliverable(PID, CID, True)
        rows = [line for line in annex(text).splitlines() if line.startswith("| GAP-")]
        loser = next(r for r in rows if "reemplazada por" in r)
        self.assertIn(f"reemplazada por {first} según {chq}", loser)
        self.assertTrue(loser.endswith("| sin opción | sin responsable |"), loser)
        self.assertTrue(any(r.startswith(f"| {chq} |") and "| A |" in r for r in rows), rows)


if __name__ == "__main__":
    unittest.main()
