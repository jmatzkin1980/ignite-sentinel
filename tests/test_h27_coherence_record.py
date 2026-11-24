"""IMP-410 (H27 inc 3) task 5: `/self-review --crosses --change` records or waives the semantic crosses of a change."""
from __future__ import annotations

import contextlib
import io
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import run_ok, waive_crosses  # noqa: E402
from test_h26_cross_record import CID, CROSSES, PID, CrossCase  # noqa: E402
from test_mcp_parity import _tools  # noqa: E402

from sentinel.change_coherence import coherence_dir, coherence_state  # noqa: E402
from sentinel.changes import change_gaps_path  # noqa: E402
from sentinel.cli import main  # noqa: E402
from sentinel.core.io import forget_read_snapshots  # noqa: E402
from sentinel.crosses.record import record_cross  # noqa: E402
from sentinel.memory import ContextBroker  # noqa: E402
from sentinel.workspace import workspace_path  # noqa: E402

FIXTURE = CROSSES / "coherencia_pantalla_sin_endpoint.json"
QUESTION = "¿Qué endpoint alimenta la bandeja de aprobaciones?"


def run_err(argv: list[str]) -> tuple[int, str]:
    err = io.StringIO()
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
        code = main(list(argv))
    return code, err.getvalue()


class CoherenceRecord(CrossCase):
    def ready(self) -> None:
        waive_crosses(PID, CID)
        forget_read_snapshots()

    def payload(self, data: dict, name: str = "coh.json") -> Path:
        path = Path.cwd() / name
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return path

    def gaps_text(self) -> str:
        return change_gaps_path(workspace_path(PID), CID).read_text(encoding="utf-8")

    def record_fixture(self) -> dict:
        self.ready()
        return json.loads(run_ok(["self-review", PID, "--crosses", "--change", CID, "--source", str(FIXTURE)]))

    def test_screen_without_endpoint(self):
        result = self.record_fixture()
        self.assertEqual(result["action"], "crosses")
        self.assertEqual(result["counts"], {"conflict": 0, "missing": 1})
        (gap_id,) = result["gaps_opened"]
        self.assertTrue(gap_id.startswith("GAP-XRV-"))
        section = self.gaps_text().split(f"### {gap_id}")[1].split("### ")[0]
        self.assertIn("medium", section)
        self.assertIn("cross-review", section)
        self.assertIn(QUESTION, section)
        self.assertEqual(coherence_state(PID, CID)["state"], "done")
        self.assertEqual(result["state"], "done")
        folder = coherence_dir(workspace_path(PID), CID)
        self.assertIn(gap_id, (folder / "coherence.md").read_text(encoding="utf-8"))
        record = json.loads((folder / "coherence.json").read_text(encoding="utf-8"))
        self.assertEqual(record["status"], "done")
        self.assertEqual(record["gaps"], [gap_id])
        self.assertTrue((workspace_path(PID) / record["submitted"]).is_file())

    def test_rejected_file_writes_nothing(self):
        self.ready()
        data = json.loads(FIXTURE.read_text(encoding="utf-8"))
        data["crosses"][0]["a"]["quote"] = "pantalla — Bandeja inexistente"
        path = self.payload(data)
        before = self.gaps_text()
        code, err = run_err(["self-review", PID, "--crosses", "--change", CID, "--source", str(path)])
        self.assertEqual(code, 3)
        self.assertIn("Cruces rechazados:", err)
        self.assertIn("is not verbatim at §4.1", err)
        self.assertEqual(before, self.gaps_text())
        self.assertFalse((coherence_dir(workspace_path(PID), CID) / "coherence.json").exists())

    def test_empty_list_means_read(self):
        self.ready()
        path = self.payload({"crosses": []})
        result = json.loads(run_ok(["self-review", PID, "--crosses", "--change", CID, "--source", str(path)]))
        self.assertEqual(result["state"], "done")
        self.assertEqual(result["gaps_opened"], [])

    def test_skip(self):
        self.ready()
        code, err = run_err(["self-review", PID, "--crosses", "--change", CID, "--skip"])
        self.assertEqual(code, 3)
        self.assertIn("--skip necesita --reason con el porqué", err)
        forget_read_snapshots()
        result = json.loads(run_ok(["self-review", PID, "--crosses", "--change", CID, "--skip",
                                    "--reason", "sin diseño técnico todavía"]))
        self.assertEqual(result["state"], "waived")
        report = (coherence_dir(workspace_path(PID), CID) / "coherence.md").read_text(encoding="utf-8")
        self.assertIn("sin diseño técnico todavía", report)

    def test_refused_before_crosses(self):
        code, err = run_err(["self-review", PID, "--crosses", "--change", CID, "--source", str(FIXTURE)])
        self.assertEqual(code, 4)  # GateRefusal: a prerequisite stops the command
        self.assertIn("Terminá primero los cruces de CHG-001", err)
        self.assertIn("next step: /sources", err)  # the first missing step of the change (the baseline), as /next names it

    def test_status_only_refreshes(self):
        self.ready()
        result = json.loads(run_ok(["self-review", PID, "--crosses", "--change", CID]))
        self.assertEqual(result["action"], "status")
        self.assertEqual(result["state"], "missing")
        self.assertTrue(Path(result["view_path"]).is_file())

    def test_coherence_gap_already_decided(self):
        crossed = record_cross(PID, CID, "contradicciones", self.write("cruce_contradicciones.md"))
        (con,) = crossed["gaps_opened"]
        ids = self.ids()
        answer = Path.cwd() / "resp-con.md"
        answer.write_text("\n".join([
            f"### {con}", "- Respuesta: Rige la primera: la jefa no aprueba sus propias altas.", "- Opción: A",
            "- Owner / fuente: Jefa de Compras", f"- Evidencia o referencia: {ids['pedido']}:31",
            "- Estado de decisión: confirmado", ""]), encoding="utf-8")
        forget_read_snapshots()
        run_ok(["resolve-gaps", PID, "--source", str(answer), "--change", CID])
        self.ready()
        data = {"crosses": [{
            "rule": "cross_b_business_product", "kind": "conflict",
            "a": {"place": "2.2", "quote": "La jefa de Compras no puede aprobar un alta que cargó ella misma."},
            "b": {"place": "3.2", "quote": "La jefa aprueba o rechaza con un motivo"},
            "finding": "La regla prohíbe aprobar el alta propia y la historia no lo contempla.",
            "question": "¿La jefa puede aprobar un alta que cargó ella misma?"}]}
        path = self.payload(data)
        result = json.loads(run_ok(["self-review", PID, "--crosses", "--change", CID, "--source", str(path)]))
        (xrv,) = result["gaps_opened"]
        self.assertEqual(result["pre_decided"], [xrv])
        self.assertIn("PRE_DECIDED", self.gaps_text().split(f"### {xrv}")[1].split("### ")[0])

    def test_cli_guards(self):
        code, err = run_err(["self-review", PID, "--change", CID])
        self.assertEqual(code, 3)
        self.assertIn("/self-review --change va con --crosses", err)
        code, err = run_err(["self-review", PID])
        self.assertEqual(code, 3)
        self.assertIn("/self-review needs --source PATH", err)
        code, err = run_err(["self-review", PID, "--skip", "--reason", "x"])
        self.assertEqual(code, 3)
        self.assertIn("goes with --crosses --change", err)

    def test_mcp_self_review_change(self):
        self.ready()
        out = _tools()["sentinel_self_review"](project_id=PID, crosses=True, change=CID, skip=True, reason="x")
        self.assertEqual(out["exit_code"], 0, out)
        self.assertEqual(out["output"]["action"], "skip")

    def test_coherence_is_indexed(self):
        self.record_fixture()
        rows = ContextBroker(PID).retrieve("Bandeja", "decision", artifact_type="change_coherence", trace_id=CID)
        self.assertTrue(rows)
        self.assertIn("Bandeja", rows[0]["text"])


if __name__ == "__main__":
    unittest.main()
