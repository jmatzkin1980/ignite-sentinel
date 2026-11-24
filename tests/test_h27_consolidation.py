"""IMP-414 (H27 inc 5a) task 2: the BA writes the text of an element with the decision applied, and confirms it one by one."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import run_cli, run_ok  # noqa: E402
from test_h26_cross_record import CID, CROSSES, PID  # noqa: E402
from test_h27_decision_conflicts import ClashCase  # noqa: E402

from sentinel.core.io import forget_read_snapshots  # noqa: E402
from sentinel.crosses.record import record_cross  # noqa: E402
from sentinel.errors import InputError  # noqa: E402
from sentinel.extraction import extraction_dir  # noqa: E402
from sentinel.extraction.consolidation import (  # noqa: E402
    anchored, confirm_replacement, consolidation_path, load_consolidation, unanchored_sentences,
)
from sentinel.extraction.inventory import build_inventory, element_lines, parse_request_elements  # noqa: E402
from sentinel.workspace import workspace_path  # noqa: E402

ANSWER = "Rige el diseño: el umbral de aprobación es 1.000.000."
RN02_NEW = "| RN-02 | Un alta con monto anual estimado mayor a 1.000.000 requiere aprobación de la jefa de Compras. |"
RN02_OLD = "| RN-02 | Un alta con monto anual estimado mayor a 5.000.000 requiere aprobación de la jefa de Compras. |"
RN02_STATEMENT = ("Cuando un alta tiene un monto anual estimado mayor a 1.000.000, "
                  "el sistema debe pedir la aprobación de la jefa de Compras.")
RN04_OLD = "| RN-04 | La jefa de Compras no puede aprobar un alta que cargó ella misma. |"


class Pure(unittest.TestCase):
    def test_guard_numbers(self):
        # the amount is neither in the element nor in the answer: refused, though every word is
        self.assertFalse(anchored("Un alta con monto anual estimado mayor a 7.000.000 requiere aprobación", RN02_OLD, [ANSWER]))
        self.assertFalse(anchored("Un alta con monto anual estimado mayor a 1.000 requiere aprobación", RN02_OLD, [ANSWER]))
        # a date and a percentage are tokens too
        self.assertFalse(anchored("Un alta con monto anual estimado mayor a 5 requiere aprobación", RN02_OLD, [ANSWER]))
        self.assertTrue(anchored("Un alta con monto anual estimado mayor a 5.000.000 requiere aprobación", RN02_OLD, [ANSWER]))
        self.assertFalse(unanchored_sentences("La jefa de Compras no puede aprobar el 20% de las altas.", RN04_OLD, []) == [])
        self.assertFalse(unanchored_sentences("Un alta rechazada requiere aprobación RN-09 de la jefa de Compras.", RN02_OLD, []) == [])

    def test_guard_negation(self):
        lost = "La jefa de Compras puede aprobar un alta que cargó ella misma"
        self.assertFalse(anchored(lost, RN04_OLD, []))
        self.assertTrue(anchored("La jefa de Compras no puede aprobar un alta que cargó ella misma", RN04_OLD, []))
        # the answer says it: the negation may go
        self.assertTrue(anchored(lost, RN04_OLD, ["Rige el diseño: no se exige, la jefa puede aprobar sus altas."]))

    def test_short_sentence_and_leading_digit_are_checked(self):
        self.assertEqual(unanchored_sentences("Sin SMS. Un alta con monto anual estimado mayor a 5.000.000.", RN02_OLD, []),
                         ["Sin SMS"])
        # `split_evidence_sentences` strips the digits a sentence starts with: the whole piece is checked as well
        self.assertEqual(unanchored_sentences("5 alta con monto anual estimado mayor requiere aprobación de la jefa de Compras", RN02_OLD, []),
                         ["5 alta con monto anual estimado mayor requiere aprobación de la jefa de Compras"])


class ConsolidationCase(ClashCase):
    def setUp(self):
        super().setUp()
        result = record_cross(PID, CID, "diseno", self.write("cruce_diseno.md"))
        found = [g for g in result["gaps"] if g.startswith("GAP-DIS-")]
        self.dis = next(g for g in found if "1.000.000" in self.gaps()[g]["description"])
        self.answer(self.dis, ANSWER, "A")
        build_inventory(PID, CID)
        text = (CROSSES / "pedido_contradiccion.md").read_text(encoding="utf-8")
        found = {e["id"]: e for e in parse_request_elements(text, "F-01", "pedido.md")}
        rn02, rn06 = (element_lines(found["RN-02"]), element_lines(found["RN-06"]))
        proposals = "\n".join([
            "### RN-02", "- Tratamiento: requisito", f"- Líneas: {rn02[0]}-{rn02[1]}",
            '- Cita: "requiere aprobación de la jefa de Compras"',
            f"- Enunciado: {RN02_STATEMENT}", "  - Delta: MODIFIED", "  - Superficie: Aprobación por monto", "",
            "### RN-06", "- Tratamiento: descarte", f"- Líneas: {rn06[0]}-{rn06[1]}",
            '- Cita: "Los proveedores del exterior quedan fuera"',
            "- Motivo: Los proveedores del exterior quedan fuera de este cambio.", "",
        ])
        path = Path.cwd() / "cons-prop.md"
        path.write_text(proposals, encoding="utf-8")
        forget_read_snapshots()
        run_ok(["extract", PID, "--change", CID, "--proposals", str(path)])
        for element in ("RN-02", "RN-06"):
            forget_read_snapshots()
            run_ok(["extract", PID, "--change", CID, "--confirm-item", element])
        self.rn02 = rn02

    # --- helpers --------------------------------------------------------------------------

    def rep(self, **over) -> str:
        fields = {"id": "RN-02", "Decisión": self.dis, "Líneas": "31-31", "Texto": RN02_NEW}
        fields.update(over)
        head = [f"### {fields.pop('id')}"]
        body = [f"- {k}: {v}" for k, v in fields.items() if v is not None]
        return "\n".join([*head, *body, ""])

    def submit_text(self, text: str, name: str = "cons.md") -> dict:
        path = Path.cwd() / name
        path.write_text(text, encoding="utf-8")
        forget_read_snapshots()
        return json.loads(run_ok(["extract", PID, "--change", CID, "--consolidate", str(path)]))

    def stored(self) -> dict:
        return load_consolidation(workspace_path(PID), CID)

    def refused(self, text: str) -> list[str]:
        result = self.submit_text(text)
        self.assertEqual(result["recorded"], [], result)
        return [reason for reasons in result["rejected"].values() for reason in reasons]


class Recording(ConsolidationCase):
    def test_anchored(self):
        rn02 = RN02_OLD
        self.assertTrue(anchored(
            "Un alta con monto anual estimado mayor a 1.000.000 requiere aprobación de la jefa de Compras", rn02, [ANSWER]))
        self.assertFalse(anchored("Además se avisa por SMS al proveedor", rn02, [ANSWER]))

    def test_record_and_confirm(self):
        result = self.submit_text(self.rep())
        self.assertEqual(result["action"], "consolidate")
        self.assertEqual(result["recorded"], ["RN-02"], result)
        self.assertIn("1 reemplazo(s) registrado(s), 0 sin cambios, 0 rechazado(s)", result["message"])
        self.assertTrue(result["submitted"].endswith("cons.md"))
        data = json.loads(consolidation_path(workspace_path(PID), CID).read_text(encoding="utf-8"))
        item = data["replacements"]["RN-02"]
        self.assertEqual((item["id"], item["status"], item["decisions"], item["lines"]),
                         ("REP-RN-02", "proposed", [self.dis], [[31, 31]]))
        self.assertEqual(item["text"], RN02_NEW)
        forget_read_snapshots()
        done = json.loads(run_ok(["extract", PID, "--change", CID, "--confirm-replacement", "RN-02"]))
        self.assertEqual(done["action"], "confirm_replacement")
        self.assertEqual(self.stored()["replacements"]["RN-02"]["status"], "confirmed")

    def test_invented_sentence_rejected(self):
        invented = RN02_NEW[:-2] + " Además se avisa por SMS al proveedor. |"
        reasons = self.refused(self.rep(Texto=invented))
        self.assertTrue(any("«Además se avisa por SMS al proveedor» no está en el elemento ni en la respuesta de" in r
                            for r in reasons), reasons)
        result = self.submit_text(self.rep(Texto=invented, Tipo="extension"))
        self.assertEqual((result["recorded"], result["flagged"]), (["RN-02"], ["RN-02"]), result)
        flags = self.stored()["replacements"]["RN-02"]["flags"]
        self.assertEqual([f["kind"] for f in flags], ["extension"])

    def test_guard_number_rejected_and_extension_escape(self):
        wrong = RN02_NEW.replace("1.000.000", "7.000.000")
        reasons = self.refused(self.rep(Texto=wrong))
        self.assertTrue(any("no está en el elemento ni en la respuesta de" in r for r in reasons), reasons)
        result = self.submit_text(self.rep(Texto=wrong, Tipo="extension"))
        self.assertEqual(result["recorded"], ["RN-02"], result)

    def test_rerun_is_idempotent(self):
        self.submit_text(self.rep())
        forget_read_snapshots()
        run_ok(["extract", PID, "--change", CID, "--confirm-replacement", "RN-02"])
        path = consolidation_path(workspace_path(PID), CID)
        before = path.read_bytes()
        again = self.submit_text(self.rep())
        self.assertEqual(again["unchanged"], ["RN-02"], again)
        self.assertEqual(again["recorded"], [])
        self.assertEqual(self.stored()["replacements"]["RN-02"]["status"], "confirmed")
        self.assertEqual(path.read_bytes(), before)

    def test_changed_text_goes_back_to_proposed(self):
        self.submit_text(self.rep())
        forget_read_snapshots()
        run_ok(["extract", PID, "--change", CID, "--confirm-replacement", "RN-02"])
        changed = self.submit_text(self.rep(Texto=RN02_NEW.replace("requiere", "exige")), name="cons2.md")
        self.assertEqual(changed["rejected"].keys(), {"RN-02"})  # "exige" is in neither: refused, the confirmed one stays
        self.assertEqual(self.stored()["replacements"]["RN-02"]["status"], "confirmed")

    def test_multiline_text_keeps_its_lines(self):
        text = "\n".join(["### RN-02", f"- Decisión: {self.dis}", "- Líneas: 31-31", "- Texto: | RN-02 | Un alta con monto anual",
                          "  estimado mayor a 1.000.000 requiere aprobación de la jefa de Compras. |", ""])
        self.assertEqual(self.submit_text(text)["recorded"], ["RN-02"])
        self.assertEqual(self.stored()["replacements"]["RN-02"]["text"].count("\n"), 1)

    def test_refusals(self):
        self.assertIn("no es una decisión cerrada de CHG-001", " ".join(self.refused(self.rep(**{"Decisión": "GAP-DIS-00000000"}))))
        self.assertIn("necesita Decisión:", " ".join(self.refused(self.rep(**{"Decisión": None}))))
        self.assertIn("Reemplaza dice RN-03", " ".join(self.refused(self.rep(Reemplaza="RN-03"))))
        self.assertIn("Ubicación debe ser un lugar del brief v2", " ".join(self.refused(self.rep(**{"Ubicación": "9.9"}))))
        self.assertIn("falta Texto:", " ".join(self.refused(self.rep(Texto=None))))
        self.assertIn("no está vinculada a RN-01", " ".join(self.refused(self.rep(id="RN-01"))))
        self.assertIn("confirmá primero su extracción", " ".join(self.refused(self.rep(id="HU-01"))))
        self.assertIn("está fuera del elemento", " ".join(self.refused(self.rep(**{"Líneas": "30-31"}))))
        self.assertIn("falta Líneas", " ".join(self.refused(self.rep(**{"Líneas": None}))))
        self.assertIn("no está en el inventario", " ".join(self.refused(self.rep(id="RN-99"))))
        self.assertEqual(self.stored()["replacements"], {})
        self.assertTrue(self.stored()["rejections"])

    def test_location_and_replaces_accepted(self):
        result = self.submit_text(self.rep(Reemplaza="RN-02", **{"Ubicación": "3.6"}))
        self.assertEqual(result["recorded"], ["RN-02"], result)
        self.assertEqual(self.stored()["replacements"]["RN-02"]["location"], "3.6")

    def test_english_change(self):
        from test_h26_cross_record import set_language

        set_language(PID, "en")
        forget_read_snapshots()
        reasons = self.refused(self.rep(**{"Decisión": None}))
        self.assertIn("a replacement needs Decision:", " ".join(reasons))

    def test_blank_block_is_skipped(self):
        result = self.submit_text("### RN-05\n- Texto:\n\n" + self.rep())
        self.assertEqual(result["skipped"], ["RN-05"])
        self.assertEqual(result["recorded"], ["RN-02"])


class NegationGuard(ConsolidationCase):
    """RN-04 says `no puede`; a decision that changes its content (GAP-CON, none of the two kept) links it."""

    def setUp(self):
        super().setUp()
        result = record_cross(PID, CID, "contradicciones", self.write("cruce_contradicciones.md"))
        self.con = next(g for g in result["gaps"] if g.startswith("GAP-CON-"))
        self.answer(self.con, "Se redacta de nuevo la regla con la jefatura de turno.", "C", line=33)
        build_inventory(PID, CID)
        proposal = "\n".join([
            "### RN-04", "- Tratamiento: requisito", "- Líneas: 33-33",
            '- Cita: "no puede aprobar un alta que cargó ella misma"',
            "- Enunciado: Si la jefa de Compras cargó el alta, el sistema debe impedir que la apruebe.",
            "  - Delta: MODIFIED", "  - Superficie: Aprobación por monto", "",
        ])
        path = Path.cwd() / "cons-rn04.md"
        path.write_text(proposal, encoding="utf-8")
        forget_read_snapshots()
        run_ok(["extract", PID, "--change", CID, "--proposals", str(path)])
        forget_read_snapshots()
        run_ok(["extract", PID, "--change", CID, "--confirm-item", "RN-04"])

    def rn04(self, text: str, **over) -> str:
        return self.rep(id="RN-04", **{"Decisión": self.con, "Líneas": "33-33", "Texto": text, **over})

    def test_negation_lost_rejected_and_extension_escape(self):
        lost = "| RN-04 | La jefa de Compras puede aprobar un alta que cargó ella misma. |"
        reasons = self.refused(self.rn04(lost))
        self.assertTrue(any("no está en el elemento ni en la respuesta de" in r for r in reasons), reasons)
        self.assertEqual(self.submit_text(self.rn04(lost, Tipo="extension"))["recorded"], ["RN-04"])

    def test_negation_kept_is_accepted(self):
        kept = "| RN-04 | La jefa de Compras no puede aprobar un alta que cargó ella misma con la jefatura de turno. |"
        self.assertEqual(self.submit_text(self.rn04(kept))["recorded"], ["RN-04"])


class Confirming(ConsolidationCase):
    def test_delegated_and_ratified(self):
        self.submit_text(self.rep())
        forget_read_snapshots()
        run_ok(["extract", PID, "--change", CID, "--confirm-replacement", "RN-02", "--delegated", "--note", "el BA delegó"])
        item = self.stored()["replacements"]["RN-02"]
        self.assertEqual((item["status"], item["confirmed_by"], item["delegated_note"]), ("confirmed", "delegated", "el BA delegó"))
        forget_read_snapshots()
        result = confirm_replacement(PID, CID, "RN-02")
        self.assertEqual(result["ratified"], ["RN-02"])
        self.assertNotIn("confirmed_by", self.stored()["replacements"]["RN-02"])
        forget_read_snapshots()
        with self.assertRaises(InputError) as caught:
            confirm_replacement(PID, CID, "RN-02")
        self.assertIn("no tiene un reemplazo pendiente de confirmar", str(caught.exception))

    def test_nothing_to_confirm(self):
        with self.assertRaises(InputError) as caught:
            confirm_replacement(PID, CID, "RN-02")
        self.assertIn("RN-02 no tiene un reemplazo pendiente de confirmar", str(caught.exception))

    def test_stale_decision_refuses_confirm(self):
        self.submit_text(self.rep())
        self.answer(self.dis, "Rige el pedido: el umbral es 5.000.000.", "B")
        forget_read_snapshots()
        with self.assertRaises(InputError) as caught:
            confirm_replacement(PID, CID, "RN-02")
        self.assertIn("conserva el texto del pedido", str(caught.exception))
        self.assertEqual(self.stored()["replacements"]["RN-02"]["status"], "proposed")

    def test_keeping_option_refuses_record(self):
        self.answer(self.dis, "Rige el pedido: el umbral es 5.000.000.", "B")
        reasons = self.refused(self.rep())
        self.assertIn("conserva el texto del pedido", " ".join(reasons))

    def test_extraction_changed_since(self):
        self.submit_text(self.rep())
        forget_read_snapshots()
        run_ok(["extract", PID, "--change", CID, "--reject-item", "RN-02", "--reason", "se rehace"])
        forget_read_snapshots()
        with self.assertRaises(InputError) as caught:
            confirm_replacement(PID, CID, "RN-02")
        self.assertIn("confirmá primero su extracción", str(caught.exception))


class Guards(ConsolidationCase):
    def test_guards(self):
        path = Path.cwd() / "p.md"
        path.write_text(self.rep(), encoding="utf-8")
        forget_read_snapshots()
        code, _ = run_cli(["extract", PID, "--change", CID, "--consolidate", str(path), "--confirm", "all"])
        self.assertNotEqual(code, 0)
        code, _ = run_cli(["extract", PID, "--change", CID, "--confirm-replacement", "RN-02", "--note", "x"])
        self.assertNotEqual(code, 0)
        code, _ = run_cli(["extract", PID, "--change", CID, "--consolidate", str(path), "--confirm-replacement", "RN-02"])
        self.assertNotEqual(code, 0)
        code, _ = run_cli(["extract", PID, "--change", CID, "--consolidate", str(path), "--delegated"])
        self.assertNotEqual(code, 0)


if __name__ == "__main__":
    unittest.main()
