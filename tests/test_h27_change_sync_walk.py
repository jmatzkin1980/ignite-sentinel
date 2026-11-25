"""IMP-418 (H27 inc 6a) task 8: the whole walk of a new request version on a change, end to end through the CLI."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import SyncCase, run_ok  # noqa: E402

from sentinel.core.io import forget_read_snapshots  # noqa: E402
from sentinel.readiness_verdict import change_next_step  # noqa: E402
from sentinel.sources import load_source_manifest  # noqa: E402

PID = "TCWK"
CID = "CHG-001"

DIVERGENCE_V2 = "\n".join([
    "# Cruce delta",
    "",
    "- [DIVERGENCIA] El pedido fija el umbral en 3.000.000 y el prototipo muestra 1.000.000.",
    '  - Pedido: F-V2 "mayor a 3.000.000 requiere aprobación de la jefa de Compras"',
    '  - Diseño: F-DIS "Umbral de aprobación: 1.000.000"',
    "",
])
EVIDENCE = "Si el monto supera el umbral, el alta pasa a la bandeja de la jefa de Compras."
BLOCKING = {
    "id": "GAP-APROBACION-AUSENCIA", "lens": "business", "severity": "high", "technique": "pre-mortem",
    "question": "¿Quién aprueba un alta de monto alto cuando la jefa de Compras está ausente?",
    "evidence": EVIDENCE,
}


class Walk(SyncCase):
    PID = PID

    def nxt(self) -> dict:
        forget_read_snapshots()
        return change_next_step(PID, CID)

    def test_new_request_version_to_challenge_and_back(self):
        old = self.ids()["pedido"]
        Path("v2").mkdir(exist_ok=True)
        v2 = self.write_v2("v2/pedido.md")
        out = json.loads(run_ok(["sync", PID, "--change", CID, "--source", str(v2), "--role", "pedido",
                                 "--supersedes", old]))
        forget_read_snapshots()
        new = out["loaded"][0]["source_id"]
        self.assertTrue(out["sync"][0]["report_path"].endswith("sync_report.md"))

        step = self.nxt()
        self.assertEqual(step["key"], "crosses")
        self.assertIn("--kind diseno", step["command"])
        self.assertTrue(step["command"].endswith("--delta"))

        delta = Path.cwd() / "delta.md"
        delta.write_text(DIVERGENCE_V2.replace("F-V2", new).replace("F-DIS", self.ids()["diseno"]), encoding="utf-8")
        run_ok(["cross", PID, "--change", CID, "--kind", "diseno", "--claims", str(delta), "--delta"])
        step = self.nxt()
        self.assertNotIn("--delta", step["command"])
        self.assertNotEqual(step.get("key"), "crosses")

        # the new divergence opened a blocking question: answer it, then challenge the change
        blocks = [f"### {gap}\n- Respuesta: (A) rige el diseño.\n- Owner / fuente: Jefa de Compras\n"
                  "- Estado de decisión: confirmado\n" for gap in self.open_gaps() if gap.startswith("GAP-DIS-")]
        if blocks:
            answer = Path.cwd() / "answer-dis.md"
            answer.write_text("\n".join(blocks), encoding="utf-8")
            run_ok(["resolve-gaps", PID, "--source", str(answer), "--change", CID])
        forget_read_snapshots()

        finding = Path.cwd() / "challenge.json"
        finding.write_text(json.dumps({"gaps": [BLOCKING], "absent": [], "untouched": []}), encoding="utf-8")
        run_ok(["challenge", PID, "--source", str(finding), "--change", CID])
        step = self.nxt()
        self.assertEqual(step["key"], "lenses")
        self.assertIn("GAP-APROBACION-AUSENCIA", self.open_gaps())

        answer = Path.cwd() / "answer-ch.md"
        answer.write_text("### GAP-APROBACION-AUSENCIA\n- Respuesta: (A) La suplente designada aprueba.\n"
                          "- Owner / fuente: Jefa de Compras\n- Estado de decisión: confirmado\n", encoding="utf-8")
        run_ok(["resolve-gaps", PID, "--source", str(answer), "--change", CID])
        self.assertNotEqual(self.nxt()["key"], "lenses")

    def test_no_candidate_row_left_unconfirmed(self):
        old = self.ids()["pedido"]
        Path("v2").mkdir(exist_ok=True)
        v2 = self.write_v2("v2/pedido.md")
        run_ok(["sync", PID, "--change", CID, "--source", str(v2), "--role", "pedido", "--supersedes", old])
        forget_read_snapshots()
        pending = [r for r in load_source_manifest(PID)["registry"] if r.get("pending_version_of")]
        self.assertEqual(pending, [])
        self.assertEqual(self.nxt().get("versions", []), [])


if __name__ == "__main__":
    unittest.main()
