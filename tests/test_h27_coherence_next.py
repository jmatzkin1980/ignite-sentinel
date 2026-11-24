"""IMP-410 (H27 inc 3) task 6: the `coherence` step of /next --change, its gate in the verdict and /status."""
from __future__ import annotations

import shutil
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import run_ok, waive_coherence  # noqa: E402
from test_h26_cross_next import CID, CROSSES, PID, NextCase  # noqa: E402

from sentinel.change_coherence import coherence_state  # noqa: E402
from sentinel.core.io import forget_read_snapshots  # noqa: E402
from sentinel.crosses.record import skip_cross  # noqa: E402
from sentinel.readiness_verdict import build_change_verdict  # noqa: E402
from sentinel.status import change_status  # noqa: E402
from sentinel.workspace import workspace_path  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
KINDS = ("linea_de_base", "diseno", "contradicciones")


class CoherenceNext(NextCase):
    def skip_crosses_by_cli(self) -> None:
        for kind in KINDS:
            run_ok(["cross", PID, "--change", CID, "--kind", kind, "--skip", "--reason", "fuera de esta prueba"])
        forget_read_snapshots()

    def gate(self) -> dict:
        forget_read_snapshots()
        return next(g for g in build_change_verdict(PID, CID)["gate_matrix"] if g["gate"] == "coherence")

    def record_empty(self) -> None:
        path = Path.cwd() / "vacia.json"
        path.write_text('{"crosses": []}', encoding="utf-8")
        run_ok(["self-review", PID, "--crosses", "--change", CID, "--source", str(path)])

    def test_step_after_crosses(self):
        self.skip_crosses_by_cli()
        step = self.step()
        self.assertEqual(step["key"], "coherence")
        self.assertEqual(step["command"], f"/self-review {PID} --crosses --change {CID} --source PATH")
        self.assertEqual(step["skill"], "sentinel-self-review §Change coherence")
        self.assertIn("01_discovery/CHG-001/coherence/view.md", step["text"])
        self.assertIn("advertencia(s)", step["text"])

    def test_view_missing_text(self):
        self.skip_crosses_by_cli()
        shutil.rmtree(workspace_path(PID) / "01_discovery" / CID / "coherence")
        step = self.step()
        self.assertEqual(step["key"], "coherence")
        self.assertEqual(step["command"], f"/self-review {PID} --crosses --change {CID}")
        self.assertEqual(step["title"], "Prepará la coherencia entre lentes")

    def test_done_moves_on_and_stale_comes_back(self):
        self.skip_crosses_by_cli()
        self.record_empty()
        self.assertEqual(self.step()["key"], "extract_inventory")
        run_ok(["harvest", PID, "--source", "harvest_compras.md", "--change", CID])
        from sentinel.status import change_sources

        pedido = change_sources(PID, CID)["by_role"]["pedido"][0]
        claims = Path.cwd() / "cruce_con.md"
        claims.write_text((CROSSES / "cruce_contradicciones.md").read_text(encoding="utf-8").replace("F-PED", pedido),
                          encoding="utf-8")
        run_ok(["cross", PID, "--change", CID, "--kind", "contradicciones", "--claims", str(claims)])
        forget_read_snapshots()
        self.assertEqual(coherence_state(PID, CID)["state"], "stale")
        self.assertEqual(self.gate()["state"], "STALE")

    def test_verdict_gate(self):
        self.skip_crosses_by_cli()
        found = build_change_verdict(PID, CID)
        self.assertIn("falta la coherencia entre lentes", found["blockers"])
        self.assertEqual(self.gate(), {"gate": "coherence", "state": "MISSING", "blocks": True})
        waive_coherence(PID, CID)
        gate = self.gate()
        self.assertEqual((gate["state"], gate["blocks"]), ("WAIVED", False))

    def test_old_workspace_reaches_coherence(self):
        for kind in KINDS:
            skip_cross(PID, CID, kind, "fuera de esta prueba")
        forget_read_snapshots()
        shutil.rmtree(workspace_path(PID) / "01_discovery" / CID / "coherence", ignore_errors=True)
        step = self.step()
        self.assertEqual(step["key"], "coherence")
        self.assertNotIn("--source", step["command"])
        self.assertEqual(change_status(PID, CID)["coherence"]["state"], "missing")

    def test_flow_matrix_rows(self):
        text = (ROOT / "user_guide" / "22-flow-step-matrix.md").read_text(encoding="utf-8")
        self.assertIn("| `coherence_view` | ", text)
        self.assertIn("| `coherence` | ", text)


if __name__ == "__main__":
    unittest.main()
