"""IMP-410 (H27 inc 3) task 3: before a question of the change is opened, the earlier decision is looked up."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import run_ok  # noqa: E402
from test_h26_cross_record import CID, PID, CrossCase  # noqa: E402

from sentinel.changes import change_gaps_path, list_changes, regenerate_change_gaps  # noqa: E402
from sentinel.core.io import forget_read_snapshots, write_text  # noqa: E402
from sentinel.crosses.record import RETIRE_NOTE, record_cross  # noqa: E402
from sentinel.gaps import parse_gap_rows, render_gaps  # noqa: E402
from sentinel.harvest import apply_harvest  # noqa: E402
from sentinel.prior_decisions import find_prior_decision, load_priors, pick_memory_match, prior_path  # noqa: E402
from sentinel.workspace import workspace_path  # noqa: E402

DIS_ANSWER = "Rige el pedido: el umbral es 5.000.000 y el prototipo se corrige."


class PriorDecisionCase(CrossCase):
    def blocking(self) -> int:
        return list_changes(PID)[CID]["gap_counts"]["blocking_open"]

    def close(self, gap_id: str, answer: str = DIS_ANSWER, line: int = 31) -> None:
        lines = [f"### {gap_id}", f"- Respuesta: {answer}", "- Opción: B", "- Owner / fuente: Jefa de Compras",
                 f"- Evidencia o referencia: {self.ids()['pedido']}:{line}", "- Estado de decisión: confirmado", ""]
        path = Path.cwd() / f"resp-{len(list(Path.cwd().glob('resp-*')))}.md"
        path.write_text("\n".join(lines), encoding="utf-8")
        forget_read_snapshots()
        run_ok(["resolve-gaps", PID, "--source", str(path), "--change", CID])

    def gap_of(self, result: dict, prefix: str) -> str:
        return next(g for g in result["gaps"] if g.startswith(prefix))

    def close_dis(self) -> str:
        result = record_cross(PID, CID, "diseno", self.write("cruce_diseno.md"))
        gap = self.gap_of(result, "GAP-DIS-")
        self.close(gap)
        return gap

    def section(self, gap_id: str) -> str:
        text = change_gaps_path(workspace_path(PID), CID).read_text(encoding="utf-8")
        return text.split(f"### {gap_id}")[1].split("\n### ")[0]

    def priors(self) -> dict:
        return load_priors(workspace_path(PID), CID)


class LinkedDecision(PriorDecisionCase):
    def test_contradiction_already_decided_by_divergence(self):
        dis = self.close_dis()
        before = self.blocking()
        result = record_cross(PID, CID, "contradicciones", self.write("cruce_contradicciones_umbral.md"))
        con = self.gap_of(result, "GAP-CON-")
        self.assertEqual(self.gaps()[con]["status"].strip("`"), "PRE_DECIDED")
        self.assertIn(con, result["pre_decided"])
        self.assertTrue(self.gaps()[con]["resolution_note"].startswith(f"ya decidido en {dis}"))
        entry = self.priors()[con]
        self.assertEqual((entry["match"], entry["basis"], entry["answer"]), ("linked", "quote", DIS_ANSWER))
        self.assertEqual(self.blocking(), before)

    def test_option_not_carried_across_families(self):
        self.close_dis()
        result = record_cross(PID, CID, "contradicciones", self.write("cruce_contradicciones_umbral.md"))
        con = self.gap_of(result, "GAP-CON-")
        self.assertEqual(self.priors()[con]["option"], "")
        self.assertNotIn("- Opción: B", self.section(con))

    def test_element_link(self):
        result = record_cross(PID, CID, "contradicciones", self.write("cruce_contradicciones.md"))
        con = self.gap_of(result, "GAP-CON-")
        self.close(con, answer="Rige RN-04: dado un alta cargada por la jefa, cuando ella intenta aprobarla, "
                               "el sistema no lo permite; sin otra jefatura aprueba la gerencia.", line=33)
        pedido = self.ids()["pedido"]
        both = {"id": "GAP-CON-0000BBBB", "text": "", "sources": [], "citations": [
            {"side": "pedido", "source_id": pedido, "line": 42,
             "quote": "cuando ella intenta aprobarla, entonces el sistema no lo permite"},
            {"side": "pedido", "source_id": pedido, "line": 47,
             "quote": "la jefa de Compras puede aprobar las altas que cargó ella misma"}]}
        found = find_prior_decision(PID, CID, both)
        self.assertEqual((found.gap_id, found.match, found.basis), (con, "linked", "quote"))
        named = {"id": "GAP-CON-0000CCCC", "text": "RN-04 se contradice con otra regla", "sources": [], "citations": [
            {"side": "pedido", "source_id": pedido, "line": 33, "quote": "no puede aprobar un alta"}]}
        found = find_prior_decision(PID, CID, named)
        self.assertEqual((found.gap_id, found.basis), (con, "element"))

    def test_memory_suggestion(self):
        result = record_cross(PID, CID, "contradicciones", self.write("cruce_contradicciones.md"))
        con = self.gap_of(result, "GAP-CON-")
        self.close(con, answer="Rige RN-04: dado un alta cargada por la jefa, cuando ella intenta aprobarla, "
                               "el sistema no lo permite; sin otra jefatura aprueba la gerencia.", line=33)
        pedido = self.ids()["pedido"]
        candidate = {"id": "GAP-XRV-0000AAAA", "text": "", "sources": [], "citations": [
            {"side": "pedido", "source_id": pedido, "line": 42,
             "quote": "Dado un alta cargada por la jefa, cuando ella intenta aprobarla, entonces el sistema no lo permite."}]}
        found = find_prior_decision(PID, CID, candidate)
        self.assertEqual((found.gap_id, found.match, found.basis), (con, "suggested", "memory"))
        self.assertGreaterEqual(found.score, 0.75)
        self.assertEqual(found.option, "")
        other = {**candidate, "citations": [], "sources": ["F-99"]}
        self.assertIsNone(find_prior_decision(PID, CID, other))

    def test_retired_gap_is_not_a_prior(self):
        record_cross(PID, CID, "diseno", self.write("cruce_diseno.md"))
        text = self.write("cruce_diseno.md").read_text(encoding="utf-8")
        cut = text.index("- [DIVERGENCIA]")
        again = Path.cwd() / "sin-divergencia.md"
        again.write_text(text[:cut], encoding="utf-8")
        record_cross(PID, CID, "diseno", again)
        retired = [g for g in self.gaps().values() if g["id"].startswith("GAP-DIS-")]
        self.assertEqual(retired[0]["resolution_note"].strip(), RETIRE_NOTE["es"])
        result = record_cross(PID, CID, "contradicciones", self.write("cruce_contradicciones_umbral.md"))
        con = self.gap_of(result, "GAP-CON-")
        self.assertEqual(self.gaps()[con]["status"].strip("`"), "OPEN")
        self.assertNotIn(con, self.priors())

    def test_rerecord_keeps_decided_state(self):
        self.close_dis()
        file = self.write("cruce_contradicciones_umbral.md")
        con = self.gap_of(record_cross(PID, CID, "contradicciones", file), "GAP-CON-")
        self.close(con, answer="Rige la configuración por parámetro: el umbral lo fija Compras y arranca en 5.000.000.")
        self.assertEqual(self.gaps()[con]["status"].strip("`"), "CLOSED")
        before = prior_path(workspace_path(PID), CID).read_bytes()
        record_cross(PID, CID, "contradicciones", file)
        self.assertEqual(self.gaps()[con]["status"].strip("`"), "CLOSED")
        self.assertEqual(prior_path(workspace_path(PID), CID).read_bytes(), before)
        self.assertTrue(self.priors()[con].get("overridden"))


class TightLinks(PriorDecisionCase):
    """IMP-410 final fix I1: a link covers the candidate, it does not merely touch it."""

    def cand(self, gap_id, text, *cites):
        pedido = self.ids()["pedido"]
        return {"id": gap_id, "text": text, "sources": [], "citations": [
            {"side": "pedido", "source_id": pedido, "line": line, "quote": quote} for line, quote in cites]}

    def test_fragment_and_other_sentence_stay_open(self):
        self.close_dis()
        probe = self.cand("GAP-CON-00000001", "la notificación a la gerencia no dice quién aprueba",
                          (31, "requiere aprobación de la jefa"), (34, "se notifica a la gerencia de Compras"))
        found = find_prior_decision(PID, CID, probe)
        self.assertTrue(found is None or found.match != "linked", found)

    def test_named_rule_with_another_rule_stays_open(self):
        self.close_dis()
        probe = self.cand("GAP-CON-00000002", "RN-02 y el aviso a los 5 días no dicen quién escala",
                          (34, "se notifica a la gerencia de Compras"))
        found = find_prior_decision(PID, CID, probe)
        self.assertTrue(found is None or found.match != "linked", found)

    def test_true_case_still_links(self):
        dis = self.close_dis()
        probe = self.cand("GAP-CON-00000003", "", (31, "mayor a 5.000.000 requiere aprobación de la jefa de Compras"))
        found = find_prior_decision(PID, CID, probe)
        self.assertEqual((found.gap_id, found.match), (dis, "linked"))

    def test_closure_other_than_answered_is_not_a_prior(self):
        pedido = self.ids()["pedido"]
        quote = "mayor a 5.000.000 requiere aprobación de la jefa de Compras"
        decision = {"id": "GAP-DIS-0000AAAA", "closure": "by_absence", "answer": "no aplica", "option": "", "elements": [],
                    "citations": [{"side": "pedido", "source_id": pedido, "line": 31, "quote": quote}]}
        probe = self.cand("GAP-CON-00000004", "", (31, quote))
        with mock.patch("sentinel.decision_memory.closed_decisions", return_value=[decision]):
            self.assertIsNone(find_prior_decision(PID, CID, probe))
            decision["closure"] = "answered"
            self.assertEqual(find_prior_decision(PID, CID, probe).gap_id, "GAP-DIS-0000AAAA")

    def test_critical_candidate_keeps_blocking(self):
        from sentinel.prior_decisions import PriorDecision, apply_prior_decisions

        gaps = [{"id": "GAP-CON-00000005", "severity": "critical", "status": "OPEN"},
                {"id": "GAP-CON-00000006", "severity": "high", "status": "OPEN"}]
        found = PriorDecision("GAP-DIS-0000AAAA", "linked", "quote", "Rige el pedido.")
        with mock.patch("sentinel.prior_decisions.find_prior_decision", return_value=found):
            apply_prior_decisions(PID, CID, gaps, {g["id"]: {"id": g["id"]} for g in gaps})
        self.assertEqual([g["status"] for g in gaps], ["OPEN", "PRE_DECIDED"])
        self.assertIn("GAP-CON-00000005", self.priors())


class PickMemory(unittest.TestCase):
    ROWS = [{"artifact_id": "DECISION-CHG-001-GAP-B", "artifact_type": "change_decision", "score": 0.9, "trace_ids": ["F-01"]},
            {"artifact_id": "DECISION-CHG-001-GAP-A", "artifact_type": "change_decision", "score": 0.9, "trace_ids": ["F-01"]},
            {"artifact_id": "X", "artifact_type": "change_border", "score": 2.0, "trace_ids": ["F-01"]}]

    def test_pick_memory_match(self):
        self.assertEqual(pick_memory_match(self.ROWS, {"F-01"})["artifact_id"], "DECISION-CHG-001-GAP-A")
        low = [{**r, "score": 0.74} for r in self.ROWS]
        self.assertIsNone(pick_memory_match(low, {"F-01"}))
        other = [{**r, "trace_ids": ["F-02"]} for r in self.ROWS]
        self.assertIsNone(pick_memory_match(other, {"F-01"}))


class DesignRequest(PriorDecisionCase):
    def test_design_request_ref(self):
        before = self.blocking()
        result = record_cross(PID, CID, "diseno", self.write("cruce_diseno_pd.md"))
        dis = self.gap_of(result, "GAP-DIS-")
        row = self.gaps()[dis]
        self.assertEqual((row["status"].strip("`"), row["severity"].strip("`")), ("OPEN", "high"))
        self.assertIn(dis, result["design_requests"])
        self.assertTrue(row["description"].endswith("Ya registrado en el pedido como pedido a Diseño: PD-01."))
        section = self.section(dis)
        self.assertIn("Ya registrado en el pedido como pedido a Diseño (PD-01): Rige el pedido; Diseño ajusta según PD-01: "
                      "«PD-01: El umbral de aprobación se configura por parámetro y arranca en 5.000.000.»", section)
        self.assertIn("- Opción: B", section)
        self.assertEqual(self.blocking(), before + 1)


HARVEST = """# Harvest

## B0 Inventario
- doc: sad-compras — 00_raw/06_baseline/sad-compras.md

## B1 Arquitectura
- [DIVERGENCIA sad-compras:sad-compras.md] El SAD dice v2; el código sirve rutas v1.
"""


class LensAndHarvest(PriorDecisionCase):
    def test_lens_round_and_harvest_go_through_lookup(self):
        path = change_gaps_path(workspace_path(PID), CID)
        rows = [g for g in parse_gap_rows(path.read_text(encoding="utf-8")) if g.get("id") != "NONE"]
        lens = [g for g in rows if g["id"] != "GAP-SCOPE"]
        self.assertEqual(list_changes(PID)[CID]["round"], "lenses")
        write_text(path, render_gaps(PID, [g for g in rows if g is not lens[0]], CID, "es", path.with_name("gap_elicitation.json")))
        with mock.patch("sentinel.prior_decisions.find_prior_decision", return_value=None) as spy:
            regenerate_change_gaps(PID, CID)
            self.assertEqual(spy.call_count, 1)
            self.assertEqual(spy.call_args.args[2]["id"], lens[0]["id"])
            spy.reset_mock()
            Path("harvest.md").write_text(HARVEST, encoding="utf-8")
            forget_read_snapshots()
            apply_harvest(PID, Path("harvest.md"), CID)
            self.assertEqual(spy.call_count, 1)
            self.assertTrue(spy.call_args.args[2]["id"].startswith("GAP-HRV-"))


if __name__ == "__main__":
    unittest.main()
