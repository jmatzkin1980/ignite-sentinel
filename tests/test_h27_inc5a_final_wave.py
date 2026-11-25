"""IMP-414 (H27 inc 5a) final review wave: anchoring guards, re-answered decisions, retired clashes, change PRD placeholders."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import run_cli, run_ok  # noqa: E402
from test_h26_cross_record import CID, PID  # noqa: E402
from test_h27_consolidation import ConsolidationCase  # noqa: E402
from test_h27_decision_conflicts import ClashCase  # noqa: E402

from sentinel.compilers.prd import render_prd_full  # noqa: E402
from sentinel.consolidation_control import consolidation_control, consolidation_sha  # noqa: E402
from sentinel.core.io import forget_read_snapshots  # noqa: E402
from sentinel.extraction.consolidation import anchored, consolidation_path, unanchored_sentences  # noqa: E402
from sentinel.workspace import workspace_path  # noqa: E402

TOPE = "El tope de reintegro es 5000 pesos por mes. El cliente no puede cancelar la suscripcion."


class AnchoringGuards(unittest.TestCase):
    def test_c1_substring_cannot_cut_a_number(self):
        self.assertNotEqual(unanchored_sentences("El tope de reintegro es 500.", TOPE, []), [])
        self.assertFalse(anchored("La tasa es 12", "La tasa es 12,5% anual", []))
        self.assertFalse(anchored("La tasa es 12,5", "La tasa es 12,5% anual", []))

    def test_c1_substring_cannot_drop_a_leading_no(self):
        self.assertFalse(anchored("puede cancelar la suscripcion", TOPE, []))
        self.assertFalse(anchored("se permite superar el tope", "x", ["No se permite superar el tope"]))
        # the whole sentence is still fine
        self.assertTrue(anchored("El cliente no puede cancelar la suscripcion", TOPE, []))
        self.assertTrue(anchored("El tope de reintegro es 5000 pesos por mes", TOPE, []))

    def test_m2_element_id_is_not_a_number_source(self):
        from hashlib import sha256

        from sentinel.changes import _squash
        from sentinel.extraction.consolidation import validate_replacement

        text = "El plazo de respuesta es de 10 dias"
        element = {"id": "RN-30", "sha": sha256(_squash(text).encode("utf-8")).hexdigest()[:16], "lines": [1, 1]}
        decisions = {"GAP-DIS-AAAA": {"id": "GAP-DIS-AAAA", "option": "A", "elements": ["RN-30"], "answer": "Rige el diseno."}}
        for body, ok in (("| RN-30 | El plazo de respuesta es de 30 dias |", False),
                         ("| RN-30 | El plazo de respuesta es de 10 dias |", True)):
            raw = {"decisions": ["GAP-DIS-AAAA"], "summary": body, "summary_lines": [body]}
            item, errors = validate_replacement(element, text, raw, decisions, "es", None, "CHG-001")
            self.assertEqual(item is not None, ok, errors)

    def test_m3_added_negation_is_rejected(self):
        element = "El plazo de respuesta es de 10 dias. No aplica a las altas urgentes."
        self.assertFalse(anchored("El plazo de respuesta no es de 10 dias", element, []))
        self.assertTrue(anchored("El plazo de respuesta no es de 10 dias", element, ["No rige el plazo de 10 dias"]))
        self.assertTrue(anchored("El plazo de respuesta es de 10 dias", element, []))


RN02_REP = "| RN-02 | Un alta con monto anual estimado mayor a 1.000.000 requiere aprobación de la jefa de Compras. |"


class Reanswer(ConsolidationCase):
    def test_i1_reanswered_decision_unconfirms_the_replacement(self):
        self.submit_text(self.rep())
        forget_read_snapshots()
        run_ok(["extract", PID, "--change", CID, "--confirm-replacement", "RN-02"])
        forget_read_snapshots()
        row = next(r for r in consolidation_control(PID, CID)["rows"] if r["element"] == "RN-02")
        self.assertEqual(row["status"], "modificado")
        sha = consolidation_sha(PID, CID)
        self.answer(self.dis, "Rige el diseño: el umbral de aprobación es 2.000.000.", "A")
        forget_read_snapshots()
        control = consolidation_control(PID, CID)
        row = next(r for r in control["rows"] if r["element"] == "RN-02")
        self.assertEqual(row["status"], "pendiente", row)
        self.assertIn("RN-02", control["unconfirmed"])
        self.assertNotEqual(consolidation_sha(PID, CID), sha)
        # confirming the old text again is refused: 1.000.000 is not in the new answer
        forget_read_snapshots()
        code, _ = run_cli(["extract", PID, "--change", CID, "--confirm-replacement", "RN-02"])
        self.assertNotEqual(code, 0)
        # the BA writes it again with the new answer and confirms
        self.submit_text(self.rep(Texto=RN02_REP.replace("1.000.000", "2.000.000")))
        forget_read_snapshots()
        run_ok(["extract", PID, "--change", CID, "--confirm-replacement", "RN-02"])
        forget_read_snapshots()
        row = next(r for r in consolidation_control(PID, CID)["rows"] if r["element"] == "RN-02")
        self.assertEqual(row["status"], "modificado")


class RetiredClash(ClashCase):
    def test_i2_retired_conflict_reopens_when_the_pair_clashes_again(self):
        first, second, result = self.clash()
        chq = result["decision_conflicts"][0]
        self.answer(second, "Rige el pedido: el umbral es 5.000.000.", "B")
        self.assertEqual(self.gaps()[chq]["status"].strip("`"), "CLOSED")
        again = self.answer(second, "Rige el diseño: se puede delegar la aprobación.", "A")
        self.assertEqual(self.gaps()[chq]["status"].strip("`"), "OPEN", again)
        self.assertEqual(self.chq_rows(), [chq])


class ChangePrd(unittest.TestCase):
    RAW = "Queremos agilizar el alta de proveedores en Compras."

    def test_i3_change_prd_has_no_project_placeholders(self):
        text = render_prd_full(PID, self.RAW, {"raw_text": self.RAW}, "CHG-001/project-brief.md", "es", self.RAW,
                               pending="sin dato registrado", assumption_rows="", source_path="02_requirements/CHG-001/")
        for forbidden in ("ASM-01", "ASM-02", "Sentinel guardrail", "GAP-PRD-PERSONA-DETAIL", "GAP-TECH-DATA-SOURCE",
                          "GAP-METRIC-SOURCE", "| FR-01 | Primary end-to-end capability", "| OK |"):
            self.assertNotIn(forbidden, text, forbidden)
        section = text.split("### 9a. Assumption Register")[1].split("### 9b.")[0]
        self.assertIn("sin dato registrado", section)

    def test_i3_project_prd_keeps_its_rows(self):
        text = render_prd_full(PID, self.RAW, {"raw_text": self.RAW}, "project-brief.md", "es", self.RAW)
        self.assertIn("ASM-01", text)
        self.assertIn("| FR-01 | Primary end-to-end capability", text)


class Rerun(ConsolidationCase):
    def test_m1_rerun_with_a_bad_block_is_byte_identical(self):
        bad = self.rep() + "\n" + self.rep(id="RN-06", Texto="| RN-06 | Algo inventado por completo. |")
        self.submit_text(bad)
        path = consolidation_path(workspace_path(PID), CID)
        before = path.read_bytes()
        self.submit_text(bad)
        self.assertEqual(path.read_bytes(), before)
        stored = self.stored()
        keys = [(r["id"], r["reason"]) for r in stored["rejections"]]
        self.assertEqual(len(keys), len(set(keys)))
        self.assertEqual(stored["replacements"]["RN-02"]["status"], "proposed")


if __name__ == "__main__":
    unittest.main()
