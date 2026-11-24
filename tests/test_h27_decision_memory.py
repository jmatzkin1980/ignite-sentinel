"""IMP-410 (H27 inc 3) task 1: the decisions of a change are indexed in memory and retrievable."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import run_ok  # noqa: E402
from test_h26_cross_record import CID, PID, CrossCase  # noqa: E402

from sentinel.core.io import forget_read_snapshots  # noqa: E402
from sentinel.crosses.record import record_cross  # noqa: E402
from sentinel.decision_memory import index_change_decisions  # noqa: E402
from sentinel.memory import ContextBroker  # noqa: E402
from sentinel.workspace import memory_path  # noqa: E402


class DecisionMemory(CrossCase):
    def artifacts(self) -> dict[str, dict]:
        return {a["artifact_id"]: a for a in ContextBroker(PID).data["artifacts"]}

    def open_cross_gap(self) -> str:
        result = record_cross(PID, CID, "diseno", self.write("cruce_diseno.md"))
        index_change_decisions(PID, CID)
        return next(g for g in result["gaps"] if g.startswith("GAP-DIS-"))

    def close(self, gap_id: str, closure: str | None = None, answer: str | None = None) -> None:
        ids = self.ids()
        lines = [f"### {gap_id}",
                 f"- Respuesta: {answer or 'Rige el pedido: el umbral es 5.000.000 y el prototipo se corrige.'}"]
        if closure:
            lines.append(f"- Motivo de cierre: {closure}")
        else:
            lines.append("- Opción: B")
        lines += ["- Owner / fuente: Jefa de Compras",
                  f"- Evidencia o referencia: {ids['pedido']}:31",
                  "- Estado de decisión: confirmado", ""]
        path = Path.cwd() / f"resp-{len(list(Path.cwd().glob('resp-*')))}.md"
        path.write_text("\n".join(lines), encoding="utf-8")
        forget_read_snapshots()
        run_ok(["resolve-gaps", PID, "--source", str(path), "--change", CID])

    def test_scope_answer_is_retrievable(self):
        out = json.loads(run_ok(["retrieve", PID, "--query", "aprobación por monto", "--workflow", "decision",
                                 "--artifact-type", "change_decision", "--trace-id", "GAP-SCOPE"]))
        rows = out if isinstance(out, list) else out.get("results") or out.get("chunks") or []
        self.assertTrue(rows)
        self.assertIn("El alta de proveedores con aprobación por monto.", rows[0]["text"])
        self.assertIn("CHG-001", rows[0]["trace_ids"])
        self.assertIn("GAP-SCOPE", rows[0]["trace_ids"])

    def test_border_is_indexed(self):
        rows = ContextBroker(PID).retrieve("Bandeja", "decision", artifact_type="change_border", trace_id=CID)
        self.assertIn("nuevo | pantalla | Bandeja de aprobaciones", rows[0]["text"])

    def test_cross_record_is_indexed(self):
        gap = self.open_cross_gap()
        rows = ContextBroker(PID).retrieve("Umbral de aprobación", "decision", artifact_type="change_cross")
        self.assertTrue(rows)
        self.assertIn("Umbral de aprobación: 1.000.000", rows[0]["text"])
        self.assertIn(gap, rows[0]["trace_ids"])

    def test_closed_cross_gap_carries_sources_and_elements(self):
        gap = self.open_cross_gap()
        self.close(gap)
        artifact = self.artifacts()[f"DECISION-{CID}-{gap}"]
        self.assertEqual(artifact["artifact_type"], "change_decision")
        self.assertIn(self.ids()["pedido"], artifact["trace_ids"])
        self.assertIn("RN-02", artifact["trace_ids"])
        text = " ".join(c["text"] for c in ContextBroker(PID).data["chunks"] if c["artifact_id"] == artifact["artifact_id"])
        self.assertIn("- Opción: B", text)

    def test_reopened_decision_is_forgotten(self):
        gap = self.open_cross_gap()
        self.close(gap)
        self.assertIn(f"DECISION-{CID}-{gap}", self.artifacts())
        self.close(gap, closure="reopened_false_premise", answer="La premisa era falsa y se reabre la pregunta.")
        self.assertNotIn(f"DECISION-{CID}-{gap}", self.artifacts())

    def test_reindex_rebuilds_and_is_idempotent(self):
        memory_path(PID).unlink()
        run_ok(["reindex", PID, "--full"])
        self.assertTrue([a for a in self.artifacts() if a.startswith("DECISION-")])
        out = json.loads(run_ok(["reindex", PID]))
        self.assertFalse([a for a in out["indexed"] if str(a).startswith("DECISION-")])
        self.assertTrue([a for a in out["skipped"] if str(a).startswith("DECISION-")])


class ProjectWorkspace(unittest.TestCase):
    def test_project_workspace_unchanged(self):
        import os
        import tempfile

        old = Path.cwd()
        with tempfile.TemporaryDirectory() as tmp:
            os.chdir(tmp)
            try:
                run_ok(["init", "PRJX"])
                run_ok(["ingest", "PRJX", "--source", str(Path(old) / "tests" / "fixtures" / "incomplete_requirement.md")])
                run_ok(["reindex", "PRJX"])
                ids = [a["artifact_id"] for a in ContextBroker("PRJX").data["artifacts"]]
                self.assertTrue(ids)
                self.assertFalse([i for i in ids if i.startswith("DECISION-")])
            finally:
                os.chdir(old)


if __name__ == "__main__":
    unittest.main()
