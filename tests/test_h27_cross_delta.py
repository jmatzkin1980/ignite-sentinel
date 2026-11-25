"""H27 inc 6a task 3: /cross --delta replaces only the touched claims and keeps the rest with their gaps and answers."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import SyncCase, run_cli, run_ok  # noqa: E402

from unittest.mock import patch  # noqa: E402

from sentinel import mcp as sentinel_mcp  # noqa: E402
from tests.test_mcp_parity import _tools  # noqa: E402
from sentinel.change_sync import apply_touched_set  # noqa: E402
from sentinel.core.io import forget_read_snapshots, read_json  # noqa: E402
from sentinel.crosses import cross_path  # noqa: E402
from sentinel.crosses.record import CrossError, record_cross  # noqa: E402
from sentinel.crosses.state import cross_status  # noqa: E402
from sentinel.workspace import workspace_path  # noqa: E402

PID = "TCDL"
CID = "CHG-001"

DIVERGENCE_V2 = "\n".join([
    "# Cruce delta",
    "",
    "- [DIVERGENCIA] El pedido fija el umbral en 3.000.000 y el prototipo muestra 1.000.000.",
    '  - Pedido: F-V2 "mayor a 3.000.000 requiere aprobación de la jefa de Compras"',
    '  - Diseño: F-DIS "Umbral de aprobación: 1.000.000"',
    "",
])
CONTRADICTION = "\n".join([
    "# Contradicciones",
    "",
    "- [CONTRADICCIÓN] RN-04 prohíbe que la jefa apruebe sus propias altas y PD-03 lo permite cuando no hay otra jefatura.",
    '  - Pedido: F-V2 "La jefa de Compras no puede aprobar un alta que cargó ella misma."',
    '  - Pedido: F-V2 "la jefa de Compras puede aprobar las altas que cargó ella misma"',
    "",
])


class DeltaCase(SyncCase):
    PID = PID

    def load_v2(self) -> tuple[str, str]:
        Path("v2").mkdir(exist_ok=True)
        source = self.write_v2("v2/pedido.md")
        old = self.ids()["pedido"]
        new = json.loads(run_ok(["sources", PID, "--load", str(source), "--role", "pedido", "--change", CID]))["source_id"]
        run_ok(["sources", PID, "--id", old, "--superseded-by", new, "--reason", "version nueva"])
        forget_read_snapshots()
        apply_touched_set(PID, CID, previous_id=old, new_id=new)
        forget_read_snapshots()
        return old, new

    def delta_file(self, text: str, new: str, name: str = "delta.md") -> Path:
        path = Path.cwd() / name
        path.write_text(text.replace("F-V2", new).replace("F-DIS", self.ids()["diseno"]), encoding="utf-8")
        return path

    def record(self, kind: str) -> dict:
        return read_json(cross_path(workspace_path(PID), CID, kind), {})


class StepAndMerge(DeltaCase):
    def test_step_asks_for_delta(self):
        self.load_v2()
        step = self.step()
        self.assertEqual(step["key"], "crosses")
        self.assertEqual(step["command"], f"/cross {PID} --change {CID} --kind diseno --claims PATH --delta")
        self.assertIn("releer sólo: afirmaciones 5", step["text"])

    def test_delta_keeps_untouched_gaps_and_answers(self):
        old, new = self.load_v2()
        before = self.record("diseno")
        divergence_gap = next(c["gap"] for c in before["claims"] if c["tag"] == "divergencia")
        unbacked_gap = next(c["gap"] for c in before["claims"] if c["tag"] == "sin_respaldo")
        result = record_cross(PID, CID, "diseno", self.delta_file(DIVERGENCE_V2, new), delta=True)
        self.assertEqual(result["retired_gaps"], [])  # answered: replaced, not withdrawn
        self.assertEqual(result["replaced_gaps"], [divergence_gap])
        record = self.record("diseno")
        self.assertIn(unbacked_gap, record["gaps"])
        self.assertNotIn(divergence_gap, record["gaps"])
        self.assertIn(unbacked_gap, self.open_gaps())
        # the contradiction is read again, unchanged: its answered question stays closed and is not retired
        con_gap = next(g["id"] for g in self._gap_rows() if g["id"].startswith("GAP-CON-"))
        row_before = next(g for g in self._gap_rows() if g["id"] == con_gap)
        forget_read_snapshots()
        again = record_cross(PID, CID, "contradicciones", self.delta_file(CONTRADICTION, new, "con.md"), delta=True)
        self.assertNotIn(con_gap, again["retired_gaps"])
        self.assertEqual(again["gaps_opened"], [])
        row_after = next(g for g in self._gap_rows() if g["id"] == con_gap)
        self.assertEqual(row_after, row_before)
        self.assertEqual(str(row_after.get("closure_reason")).strip("`"), "answered")
        self.assertIn(con_gap, self.record("contradicciones")["gaps"])

    def test_delta_merges_and_renumbers(self):
        old, new = self.load_v2()
        result = record_cross(PID, CID, "diseno", self.delta_file(DIVERGENCE_V2, new), delta=True)
        self.assertEqual(result["mode"], "delta")
        self.assertEqual(result["kept"], [1, 2, 3, 4])
        record = self.record("diseno")
        self.assertEqual([c["n"] for c in record["claims"]], [1, 2, 3, 4, 5])
        last = record["claims"][-1]
        self.assertEqual(last["tag"], "divergencia")
        self.assertIn(new, {c["source_id"] for c in last["citations"]})
        self.assertNotIn("pending_delta", record)
        forget_read_snapshots()
        self.assertEqual(cross_status(PID, CID)["kinds"]["diseno"]["state"], "done")

    def test_delta_without_record_refused(self):
        old, new = self.load_v2()
        path = cross_path(workspace_path(PID), CID, "contradicciones")
        path.unlink()
        forget_read_snapshots()
        with self.assertRaises(CrossError) as ctx:
            record_cross(PID, CID, "contradicciones", self.delta_file(CONTRADICTION, new), delta=True)
        self.assertIn("registrá el cruce completo sin --delta", str(ctx.exception))

    def test_full_record_unchanged(self):
        old, new = self.load_v2()
        self.assertIn("pending_delta", self.record("diseno"))
        forget_read_snapshots()
        text = (self.FIXTURES / "change_crosses" / "cruce_diseno.md").read_text(encoding="utf-8")
        text = text.replace("F-PED", new).replace("F-DIS", self.ids()["diseno"]).replace("mayor a 5.000.000", "mayor a 3.000.000")
        path = Path.cwd() / "full.md"
        path.write_text(text, encoding="utf-8")
        result = record_cross(PID, CID, "diseno", path)
        self.assertNotIn("mode", result)
        self.assertNotIn("kept", result)
        record = self.record("diseno")
        self.assertEqual(set(record), {"schema_version", "change_id", "kind", "status", "recorded_at", "source_id", "submitted",
                                       "claims", "counts", "gaps", "basis", "claims_hash", "dropped_gaps", "retired_gaps"}
                         - ({"retired_gaps"} if "retired_gaps" not in record else set())
                         - ({"dropped_gaps"} if "dropped_gaps" not in record else set()))


class Surfaces(DeltaCase):
    def test_cli_and_mcp_delta(self):
        old, new = self.load_v2()
        path = self.delta_file(DIVERGENCE_V2, new)
        out = json.loads(run_ok(["cross", PID, "--change", CID, "--kind", "diseno", "--claims", str(path), "--delta"]))
        self.assertEqual(out["mode"], "delta")
        code, _ = run_cli(["cross", PID, "--change", CID, "--delta"])
        self.assertNotEqual(code, 0)
        from sentinel.crosses import run_cross

        with self.assertRaises(ValueError) as ctx:
            run_cross(PID, CID, delta=True)
        self.assertIn("--delta va con --claims", str(ctx.exception))  # the change is Spanish
        captured: list = []
        with patch.object(sentinel_mcp, "run_cli", lambda arguments: captured.append(arguments) or {"exit_code": 0}):
            _tools()["sentinel_cross"](project_id="P", change="CHG-001", kind="diseno", claims="c.md", delta=True)
        self.assertEqual(captured[0], ["cross", "P", "--change", "CHG-001", "--kind", "diseno", "--claims", "c.md", "--delta"])


if __name__ == "__main__":
    unittest.main()
