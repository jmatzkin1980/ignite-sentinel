"""IMP-412 (H27 inc 4) task 5: a clash between closed decisions goes back to the BA as GAP-CHQ-* (T2-26)."""
from __future__ import annotations

import hashlib
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import run_ok  # noqa: E402
from test_h26_cross_record import CID, CROSSES, PID, CrossCase  # noqa: E402

from sentinel.changes import list_changes  # noqa: E402
from sentinel.core.io import forget_read_snapshots  # noqa: E402
from sentinel.crosses.record import record_cross  # noqa: E402
from sentinel.decision_conflicts import conflict_gap_id, conflicting_pairs  # noqa: E402
from sentinel.extraction.inventory import build_inventory, element_lines, parse_request_elements  # noqa: E402
from sentinel.extraction.proposals import record_proposals  # noqa: E402

A = {"id": "GAP-DIS-AAAA0001", "lens": "design", "option": "B", "answer": "Rige el pedido.",
     "elements": ["RN-02"], "citations": [{"source_id": "F-01", "line": 31}]}
B = {"id": "GAP-DIS-BBBB0002", "lens": "design", "option": "A", "answer": "Rige el diseño.",
     "elements": ["RN-02"], "citations": [{"source_id": "F-01", "line": 40}]}


class Pure(unittest.TestCase):
    def test_conflicting_pairs(self):
        self.assertEqual(conflicting_pairs([B, A]), [(A, B, "RN-02")])
        self.assertEqual(conflicting_pairs([A, {**B, "option": "B"}]), [])
        self.assertEqual(conflicting_pairs([A, {**B, "id": "GAP-CON-BBBB0002"}]), [])
        only_section = {"elements": ["SEC-objetivo"], "citations": [{"source_id": "F-01", "line": 31}]}
        self.assertEqual(conflicting_pairs([{**A, **only_section}, {**B, **only_section, "citations": A["citations"]}]),
                         [({**A, **only_section}, {**B, **only_section, "citations": A["citations"]}, "F-01:31")])
        self.assertEqual(conflicting_pairs([A, {**B, "option": ""}]), [])

    def test_conflict_gap_id(self):
        expected = "GAP-CHQ-" + hashlib.sha256(b"GAP-DIS-AAAA0001|GAP-DIS-BBBB0002").hexdigest()[:8].upper()
        self.assertEqual(conflict_gap_id("GAP-DIS-BBBB0002", "GAP-DIS-AAAA0001"), expected)


class ClashCase(CrossCase):
    counter = 0

    def blocking(self) -> int:
        return list_changes(PID)[CID]["gap_counts"]["blocking_open"]

    def answer(self, gap_id: str, text: str, option: str, line: int = 31) -> dict:
        lines = [f"### {gap_id}", f"- Respuesta: {text}", f"- Opción: {option}", "- Owner / fuente: Jefa de Compras",
                 f"- Evidencia o referencia: {self.ids()['pedido']}:{line}", "- Estado de decisión: confirmado", ""]
        ClashCase.counter += 1
        path = Path.cwd() / f"clash-resp-{ClashCase.counter}.md"
        path.write_text("\n".join(lines), encoding="utf-8")
        forget_read_snapshots()
        return json.loads(run_ok(["resolve-gaps", PID, "--source", str(path), "--change", CID]))

    def dis_gaps(self) -> tuple[str, str]:
        result = record_cross(PID, CID, "diseno", self.write("cruce_diseno_choque.md"))
        found = {g: self.gaps()[g] for g in result["gaps"] if g.startswith("GAP-DIS-")}
        first = next(g for g, row in found.items() if "1.000.000" in row["description"])
        second = next(g for g in found if g != first)
        return first, second

    def clash(self) -> tuple[str, str, dict]:
        first, second = self.dis_gaps()
        self.answer(first, "Rige el pedido: el umbral es 5.000.000.", "B")
        before = self.blocking()
        result = self.answer(second, "Rige el diseño: se puede delegar la aprobación.", "A")
        return first, second, {**result, "before": before}

    def chq_rows(self) -> list[str]:
        return [g for g in self.gaps() if g.startswith("GAP-CHQ-")]


class Closing(ClashCase):
    def test_closing_opens_conflict(self):
        first, second, result = self.clash()
        expected = conflict_gap_id(first, second)
        self.assertEqual(result["decision_conflicts"], [expected])
        row = self.gaps()[expected]
        self.assertEqual((row["status"].strip("`"), row["severity"].strip("`")), ("OPEN", "high"))
        self.assertIn("contradiction", row["origin"])
        self.assertIn("(A) rige lo que decidió", row["question"])
        self.assertIn(first, row["question"])
        self.assertIn(second, row["question"])
        self.assertEqual(self.blocking(), result["before"] - 1 + 1)  # the second closes (-1) and the clash opens (+1): +1 over a clean close

    def test_closed_conflict_not_reopened(self):
        first, second, result = self.clash()
        chq = result["decision_conflicts"][0]
        closed = self.answer(chq, "Rige lo que decidió la jefa.", "A")
        self.assertIn(chq, closed["closed"])
        self.assertEqual(self.gaps()[chq]["status"].strip("`"), "CLOSED")
        again = self.answer(first, "Rige el pedido: el umbral es 5.000.000.", "B")
        self.assertEqual(again["decision_conflicts"], [])
        self.assertEqual(self.chq_rows(), [chq])


class Proposals(ClashCase):
    def block(self, *cited: str, extra: str = "") -> str:
        text = (CROSSES / "pedido_contradiccion.md").read_text(encoding="utf-8")
        element = next(e for e in parse_request_elements(text, "F-01", "pedido.md") if e["id"] == "RN-02")
        first, last = element_lines(element)
        return "\n".join([
            "### RN-02", "- Tratamiento: descarte", f"- Líneas: {first}-{last}",
            '- Cita: "requiere aprobación de la jefa de Compras"', "- Motivo: Ya está decidido.",
            *([f"- Decisión: {', '.join(cited)}"] if cited else []), *([extra] if extra else []), ""])

    def submit(self, text: str) -> dict:
        path = Path.cwd() / "clash-prop.md"
        path.write_text(text, encoding="utf-8")
        forget_read_snapshots()
        return record_proposals(PID, CID, path)

    def test_proposal_citing_clashing_decisions(self):
        first, second, result = self.clash()
        chq = result["decision_conflicts"][0]
        build_inventory(PID, CID)
        dis1, dis2 = sorted([first, second])
        out = self.submit(self.block(dis1, dis2))
        self.assertEqual(out["recorded"], [])
        self.assertIn(f"cita {dis1} y {dis2}, que chocan: se abrió {chq}", out["rejected"]["RN-02"][0])
        self.assertEqual(out["conflicts"], [chq])

    def test_unknown_decision_rejected(self):
        self.dis_gaps()
        build_inventory(PID, CID)
        out = self.submit(self.block("GAP-DIS-00000000"))
        self.assertEqual(out["recorded"], [])
        self.assertIn("GAP-DIS-00000000 no es una decisión cerrada de CHG-001", out["rejected"]["RN-02"][0])

    def test_choque_flag_opens_conflict(self):
        diseno = record_cross(PID, CID, "diseno", self.write("cruce_diseno.md"))
        contra = record_cross(PID, CID, "contradicciones", self.write("cruce_contradicciones.md"))
        dis = next(g for g in diseno["gaps"] if g.startswith("GAP-DIS-") and "5.000.000" in self.gaps()[g]["description"])
        con = next(g for g in contra["gaps"] if g.startswith("GAP-CON-"))
        self.answer(dis, "Rige el pedido: el umbral es 5.000.000.", "B")
        self.answer(con, "Rige RN-04: la jefa no aprueba sus propias altas.", "A", line=33)
        build_inventory(PID, CID)
        out = self.submit(self.block(dis, con, extra="- Marca: choque — junta el umbral con la autoaprobación"))
        chq = conflict_gap_id(dis, con)
        self.assertEqual(out["recorded"], [])
        self.assertEqual(out["conflicts"], [chq])
        self.assertIn(f"se abrió {chq}", out["rejected"]["RN-02"][0])
        self.assertIn(chq, self.chq_rows())


if __name__ == "__main__":
    unittest.main()
