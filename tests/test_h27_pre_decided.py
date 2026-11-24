"""IMP-410 (H27 inc 3) task 2: a question an earlier decision already answers is PRE_DECIDED, prefilled and confirmable."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import SnapshotWorkspaceCase, run_cli, run_ok  # noqa: E402
from test_h26_cross_record import CID, PID, CrossCase  # noqa: E402

from sentinel.changes import accept_prior_decision, change_gaps_path, list_changes  # noqa: E402
from sentinel.errors import InputError  # noqa: E402
from sentinel.compilers.change_brief import collect_change_brief_inputs  # noqa: E402
from sentinel.core.io import forget_read_snapshots  # noqa: E402
from sentinel.crosses.record import _save_change_gaps, record_cross  # noqa: E402
from sentinel.gaps import count_gaps, parse_gap_rows  # noqa: E402
from sentinel.prior_decisions import load_priors, prior_note, save_priors  # noqa: E402
from sentinel.readiness_verdict import build_change_verdict  # noqa: E402
from sentinel.workspace import read_state, workspace_path  # noqa: E402

PRIOR = "GAP-DIS-0A1B2C3D"
ANSWER = "Rige el pedido."


class Counting(unittest.TestCase):
    def test_counts_and_not_blocking(self):
        self.assertEqual(
            count_gaps([{"id": "G", "severity": "high", "status": "PRE_DECIDED"}]),
            {"open": 0, "answered": 0, "partially_closed": 0, "closed": 0, "blocking_open": 0, "total": 1, "pre_decided": 1})
        self.assertNotIn("pre_decided", count_gaps([]))


class PreDecided(CrossCase):
    def setUp(self):
        super().setUp()
        record_cross(PID, CID, "diseno", self.write("cruce_diseno.md"))
        forget_read_snapshots()

    def gap_id(self, prefix: str) -> str:
        return next(i for i in self.gaps() if i.startswith(prefix))

    def rows(self) -> list[dict]:
        path = change_gaps_path(workspace_path(PID), CID)
        return [g for g in parse_gap_rows(path.read_text(encoding="utf-8")) if g.get("id") != "NONE"]

    def seed(self, gap_id: str, prior: str = PRIOR, answer: str = ANSWER) -> None:
        base = workspace_path(PID)
        entry = {"match": "linked", "prior": prior, "basis": "quote", "answer": answer, "option": "",
                 "score": 1.0, "at": "2026-11-24T00:00:00+00:00"}
        priors = load_priors(base, CID)
        priors[gap_id] = entry
        save_priors(base, CID, priors)
        rows = self.rows()
        for row in rows:
            if row["id"] == gap_id:
                row["status"] = "PRE_DECIDED"
                row["resolution_note"] = prior_note(entry, "es")
        _save_change_gaps(PID, CID, change_gaps_path(base, CID), rows)
        forget_read_snapshots()

    def section(self, gap_id: str) -> str:
        text = change_gaps_path(workspace_path(PID), CID).read_text(encoding="utf-8")
        return text.split(f"### {gap_id}")[1].split("\n### ")[0].split("\n## ")[0]

    def blocking(self) -> int:
        return list_changes(PID)[CID]["gap_counts"]["blocking_open"]

    def test_section_is_prefilled(self):
        srd = self.gap_id("GAP-SRD-")
        self.seed(srd)
        section = self.section(srd)
        for expected in (f"Ya decidido en {PRIOR}: {ANSWER}", f"- Respuesta: {ANSWER}",
                         f"- Evidencia o referencia: {PRIOR}", "--accept-prior", "- Estado: `PRE_DECIDED`"):
            self.assertIn(expected, section)
        self.assertIn("- Estado de decisión:\n", section)
        text = change_gaps_path(workspace_path(PID), CID).read_text(encoding="utf-8")
        self.assertIn(f"ya decidido en {PRIOR}: {ANSWER}", text.split("Tabla de trazabilidad")[1])

    def test_accept_prior_closes(self):
        srd = self.gap_id("GAP-SRD-")
        self.seed(srd)
        out = json.loads(run_ok(["gaps", PID, "--change", CID, "--id", srd, "--accept-prior"]))
        self.assertEqual(out["action"], "accept_prior")
        self.assertEqual(out["prior"], PRIOR)
        forget_read_snapshots()
        row = next(g for g in self.rows() if g["id"] == srd)
        self.assertEqual(row["status"], "CLOSED")
        self.assertEqual(row["resolution_note"], f"confirmado por el BA: rige lo decidido en {PRIOR}")
        self.assertIn("accepted_at", load_priors(workspace_path(PID), CID)[srd])
        gap = next(g for g in collect_change_brief_inputs(PID, CID)["gaps"] if g["id"] == srd)
        self.assertEqual(gap["answer"], ANSWER)
        self.assertNotIn("Ya decidido en", self.section(srd))

    def test_accept_prior_refusals(self):
        srd, sed = self.gap_id("GAP-SRD-"), self.gap_id("GAP-SED-")
        self.seed(srd)
        code, _out = run_cli(["gaps", PID, "--change", CID, "--id", sed, "--accept-prior"])
        self.assertEqual(code, 3)
        with self.assertRaises(InputError) as raised:
            accept_prior_decision(PID, CID, sed)
        self.assertIn("no tiene una decisión previa para aceptar", str(raised.exception))
        run_ok(["gaps", PID, "--change", CID, "--id", srd, "--accept-prior"])
        forget_read_snapshots()
        code, _out = run_cli(["gaps", PID, "--change", CID, "--id", srd, "--accept-prior"])
        self.assertEqual(code, 3)
        with self.assertRaises(InputError) as raised:
            accept_prior_decision(PID, CID, srd)
        self.assertIn("ya está cerrada", str(raised.exception))
        code, _out = run_cli(["gaps", PID, "--accept-prior"])
        self.assertNotEqual(code, 0)

    def answers(self, gap_id: str, answer: str, status: str) -> Path:
        ids = self.ids()
        lines = [f"### {gap_id}", f"- Respuesta: {answer}", "- Owner / fuente: Jefa de Compras",
                 f"- Evidencia o referencia: {ids['pedido']}:31", f"- Estado de decisión: {status}", ""]
        path = Path.cwd() / f"resp-{len(list(Path.cwd().glob('resp-*')))}.md"
        path.write_text("\n".join(lines), encoding="utf-8")
        return path

    def test_different_answer_overrides(self):
        srd = self.gap_id("GAP-SRD-")
        self.seed(srd)
        path = self.answers(srd, "Rige el diseño: la bandeja muestra el historial.", "confirmado")
        out = json.loads(run_ok(["resolve-gaps", PID, "--source", str(path), "--change", CID]))
        self.assertIn(srd, out["closed"])
        self.assertEqual(out["prior_overridden"], [srd])
        self.assertTrue(load_priors(workspace_path(PID), CID)[srd]["overridden"])

    def test_pending_answer_blocks_again(self):
        dis = self.gap_id("GAP-DIS-")
        before = self.blocking()
        self.seed(dis, prior="GAP-DIS-FFFFFFFF")
        self.assertEqual(self.blocking(), before - 1)
        path = self.answers(dis, "Rige el pedido, a confirmar con la jefa.", "pendiente")
        out = json.loads(run_ok(["resolve-gaps", PID, "--source", str(path), "--change", CID]))
        self.assertIn(dis, out["answered"])
        self.assertNotIn(dis, out["pre_decided"])
        self.assertEqual(self.blocking(), before)

    def test_status_next_and_verdict_list_it(self):
        srd = self.gap_id("GAP-SRD-")
        self.seed(srd)
        expected = [{"id": srd, "prior": PRIOR}]
        self.assertEqual(json.loads(run_ok(["next", PID, "--change", CID]))["pre_decided"], expected)
        status = json.loads(run_ok(["status", PID, "--change", CID]))
        self.assertEqual(status["pre_decided"], expected)
        self.assertIn(f"1 pregunta(s) ya decidida(s) a confirmar: {srd}", build_change_verdict(PID, CID)["warnings"])
        self.assertNotIn("pre_decided", json.loads(run_ok(["next", PID])))


class ProjectPath(SnapshotWorkspaceCase):
    @classmethod
    def build_workspace(cls):
        run_ok(["init", "PDEC"])
        run_ok(["ingest", "PDEC", "--source", str(Path(__file__).resolve().parent / "fixtures" / "incomplete_requirement.md")])

    def test_project_gaps_unchanged(self):
        path = workspace_path("PDEC") / "01_discovery" / "gaps.md"
        before = path.read_bytes()
        run_ok(["gaps", "PDEC"])
        self.assertEqual(path.read_bytes(), before)
        self.assertNotIn("pre_decided", read_state("PDEC")["gap_counts"])


if __name__ == "__main__":
    unittest.main()
