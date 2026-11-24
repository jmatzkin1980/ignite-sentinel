"""IMP-410 (H27 inc 3) final fix wave: priors follow their decision (I2), untouched PRE_DECIDED sections (I4), accept-prior scope (I5)."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import run_cli, run_ok, waive_crosses  # noqa: E402
from test_h27_prior_decision import CID, PID, DIS_ANSWER, PriorDecisionCase  # noqa: E402

import sentinel.change_coherence as coh  # noqa: E402
from sentinel.changes import accept_prior_decision  # noqa: E402
from sentinel.core.io import forget_read_snapshots  # noqa: E402
from sentinel.crosses.record import record_cross  # noqa: E402
from sentinel.decision_memory import closed_decisions  # noqa: E402
from sentinel.errors import InputError  # noqa: E402
from sentinel.extraction.inventory import _row_path, pedido_rows  # noqa: E402
from sentinel.readiness_verdict import build_change_verdict  # noqa: E402
from sentinel.prior_decisions import save_priors  # noqa: E402
from sentinel.workspace import workspace_path  # noqa: E402


class FinalWave(PriorDecisionCase):
    def decided_pair(self) -> tuple[str, str]:
        dis = self.close_dis()
        result = record_cross(PID, CID, "contradicciones", self.write("cruce_contradicciones_umbral.md"))
        con = self.gap_of(result, "GAP-CON-")
        self.assertEqual(self.gaps()[con]["status"].strip("`"), "PRE_DECIDED")
        return dis, con

    def respond(self, text: str) -> dict:
        path = Path.cwd() / f"resp-{len(list(Path.cwd().glob('resp-*')))}.md"
        path.write_text(text, encoding="utf-8")
        forget_read_snapshots()
        return json.loads(run_ok(["resolve-gaps", PID, "--source", str(path), "--change", CID]))

    def reanswer(self, gap_id: str, answer: str, closure: str = "") -> dict:
        lines = [f"### {gap_id}", f"- Respuesta: {answer}", "- Owner / fuente: Jefa de Compras",
                 f"- Evidencia o referencia: {self.ids()['pedido']}:31", "- Estado de decisión: confirmado"]
        if closure:
            lines.insert(2, f"- Motivo de cierre: {closure}")
        return self.respond("\n".join(lines) + "\n")

    # I2
    def test_reopened_prior_drops_its_dependents_to_open(self):
        dis, con = self.decided_pair()
        severity = self.gaps()[con]["severity"]
        out = self.reanswer(dis, "La premisa era falsa y se reabre la pregunta.", closure="reopened_false_premise")
        row = self.gaps()[con]
        self.assertEqual((row["status"].strip("`"), row["severity"]), ("OPEN", severity))
        self.assertNotIn(con, self.priors())
        self.assertEqual(out["prior_reopened"], [con])
        self.assertNotIn("Ya decidido en", self.section(con))

    def test_reanswered_prior_refreshes_the_snapshot(self):
        dis, con = self.decided_pair()
        new = "Rige el prototipo: el umbral es 1.000.000 y el pedido se corrige."
        out = self.reanswer(dis, new)
        self.assertEqual(out["prior_changed"], [con])
        entry = self.priors()[con]
        self.assertEqual((entry["answer"], entry["changed"]), (new, True))
        self.assertEqual(self.gaps()[con]["status"].strip("`"), "PRE_DECIDED")
        self.assertIn("la decisión previa cambió", self.gaps()[con]["resolution_note"])
        self.assertIn(new, self.section(con))

    def test_accept_prior_uses_the_live_answer(self):
        dis, con = self.decided_pair()
        entry = self.priors()[con]
        save_priors(workspace_path(PID), CID, {**self.priors(), con: {**entry, "answer": "una respuesta vieja"}})
        out = json.loads(run_ok(["gaps", PID, "--change", CID, "--id", con, "--accept-prior"]))
        self.assertTrue(out["warnings"])
        self.assertEqual(self.priors()[con]["answer"], DIS_ANSWER)

    def test_accept_prior_refuses_a_prior_that_is_gone(self):
        dis, con = self.decided_pair()
        save_priors(workspace_path(PID), CID, {**self.priors(), con: {**self.priors()[con], "prior": "GAP-DIS-FFFFFFFF"}})
        with self.assertRaises(InputError) as raised:
            accept_prior_decision(PID, CID, con)
        self.assertIn("ya no está vigente", str(raised.exception))

    # I4
    def test_untouched_section_stays_pending_and_says_how_to_confirm(self):
        dis, con = self.decided_pair()
        before = self.blocking()
        section = self.section(con)
        out = self.respond(f"### {con}{section}")
        self.assertNotIn(con, out["partially_closed"])
        self.assertIn(con, out["pre_decided"])
        self.assertEqual(self.gaps()[con]["status"].strip("`"), "PRE_DECIDED")
        self.assertEqual(self.blocking(), before)
        self.assertTrue(any(con in f and "--accept-prior" in f and "confirmado" in f for f in out["closure_findings"]))

    def test_section_with_confirmed_status_accepts_the_prior_answer(self):
        dis, con = self.decided_pair()
        section = self.section(con).replace("- Estado de decisión:\n", "- Estado de decisión: confirmado\n")
        out = self.respond(f"### {con}{section}")
        self.assertIn(con, out["closed"])
        self.assertEqual(self.gaps()[con]["status"].strip("`"), "CLOSED")
        self.assertFalse(self.priors()[con].get("overridden"))

    # M1
    def test_decision_document_takes_the_lens_as_domain(self):
        from sentinel.memory import ContextBroker

        dis = self.close_dis()
        lens = self.gaps()[dis]["lens"].strip("`")
        doc = next(a for a in ContextBroker(PID).data["artifacts"] if a["artifact_id"] == f"DECISION-{CID}-{dis}")
        self.assertEqual(doc["domain"], lens)

    # I5
    def test_design_request_and_suggestion_are_not_accepted_as_is(self):
        result = record_cross(PID, CID, "diseno", self.write("cruce_diseno_pd.md"))
        dis = self.gap_of(result, "GAP-DIS-")
        self.assertEqual(self.priors()[dis]["match"], "design_request")
        code, _out = run_cli(["gaps", PID, "--change", CID, "--id", dis, "--accept-prior"])
        self.assertEqual(code, 3)
        with self.assertRaises(InputError) as raised:
            accept_prior_decision(PID, CID, dis)
        self.assertIn("no se aceptan solos", str(raised.exception))

    def test_accepting_keeps_the_option_of_the_prior(self):
        dis, con = self.decided_pair()
        save_priors(workspace_path(PID), CID, {**self.priors(), con: {**self.priors()[con], "option": "B"}})
        run_ok(["gaps", PID, "--change", CID, "--id", con, "--accept-prior"])
        forget_read_snapshots()
        self.assertEqual({d["id"]: d["option"] for d in closed_decisions(PID, CID)}[con], "B")


class CoherenceCache(PriorDecisionCase):
    """IMP-410 final fix I3: the lens view is rendered again only when its inputs moved."""

    def renders(self):
        return mock.patch.object(coh, "coherence_view", wraps=coh.coherence_view)

    def test_not_ready_renders_nothing(self):
        coh._FINGERPRINTS.clear()
        with self.renders() as spy:
            self.assertEqual(coh.coherence_state(PID, CID)["state"], "missing")
            build_change_verdict(PID, CID)
        self.assertEqual(spy.call_count, 0)

    def test_state_is_rendered_once_per_input_state(self):
        waive_crosses(PID, CID)
        coh.refresh_coherence(PID, CID)
        coh._FINGERPRINTS.clear()
        with self.renders() as spy:
            first = coh.coherence_state(PID, CID)
            for _ in range(3):
                self.assertEqual(coh.coherence_state(PID, CID)["fingerprint"], first["fingerprint"])
            self.assertLessEqual(spy.call_count, 1)
            coh._FINGERPRINTS.clear()  # another process: the stamp stored next to the view answers
            coh.coherence_state(PID, CID)
            self.assertLessEqual(spy.call_count, 1)

    def test_a_moved_input_renders_again(self):
        waive_crosses(PID, CID)
        coh.refresh_coherence(PID, CID)
        before = coh.coherence_state(PID, CID)["fingerprint"]
        row = pedido_rows(PID, CID)[0]
        path = Path(_row_path(row))
        path = path if path.is_absolute() else Path.cwd() / path
        extra = "\n- PD-09: Otro parámetro de la aprobación.\n"
        path.write_text(path.read_text(encoding="utf-8") + extra, encoding="utf-8")
        forget_read_snapshots()
        with self.renders() as spy:
            after = coh.coherence_state(PID, CID)["fingerprint"]
        self.assertEqual(spy.call_count, 1)
        self.assertNotEqual(before, after)


if __name__ == "__main__":
    unittest.main()
