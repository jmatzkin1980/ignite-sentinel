"""IMP-410 (H27 inc 3) task 7: a decision of the change is never asked twice, and the lenses are read before the extraction.

End to end through the CLI: the design cross-read opens a divergence, the BA decides it; the contradictions cross-read
finds the same contradiction from the other side and the question is born PRE_DECIDED; the lens coherence then opens a
question of its own; the BA confirms the earlier decision with `--accept-prior`; the memory finds the decision.
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import run_ok  # noqa: E402
from test_h26_cross_next import CID, CROSSES, PID, NextCase  # noqa: E402

from sentinel.changes import change_gaps_path, list_changes  # noqa: E402
from sentinel.core.io import forget_read_snapshots  # noqa: E402
from sentinel.crosses.surfaces import new_surface_candidates  # noqa: E402
from sentinel.gaps import parse_gap_rows  # noqa: E402
from sentinel.workspace import workspace_path  # noqa: E402

DIVERGENCE = "Rige el pedido: el umbral es 5.000.000 y el prototipo se corrige."
FIXTURE = CROSSES / "coherencia_pantalla_sin_endpoint.json"


class NeverTwice(NextCase):
    def gap_rows(self) -> dict[str, dict]:
        forget_read_snapshots()
        path = change_gaps_path(workspace_path(PID), CID)
        return {g["id"]: g for g in parse_gap_rows(path.read_text(encoding="utf-8")) if g["id"] != "NONE"}

    def status_of(self, gap_id: str) -> str:
        return self.gap_rows()[gap_id]["status"].strip("`")

    def blocking(self) -> int:
        forget_read_snapshots()
        return list_changes(PID)[CID]["gap_counts"]["blocking_open"]

    def answer(self, gap_ids: list[str], text: str, option: str = "") -> None:
        pedido = self.ids()["pedido"]
        blocks = []
        for gap_id in gap_ids:
            is_divergence = gap_id.startswith("GAP-DIS-")
            lines = [f"### {gap_id}", f"- Respuesta: {text if is_divergence else 'Se acepta como está en el pedido.'}"]
            if option and is_divergence:
                lines.append(f"- Opción: {option}")
            lines += ["- Owner / fuente: Jefa de Compras", f"- Evidencia o referencia: {pedido}:31",
                      "- Estado de decisión: confirmado", ""]
            blocks.append("\n".join(lines))
        path = Path.cwd() / f"resp-{len(list(Path.cwd().glob('resp-*')))}.md"
        path.write_text("\n".join(blocks), encoding="utf-8")
        forget_read_snapshots()
        run_ok(["resolve-gaps", PID, "--source", str(path), "--change", CID])

    def cli(self, *argv: str) -> dict:
        forget_read_snapshots()
        return json.loads(run_ok(list(argv)))

    def test_never_twice(self):
        self.load_design()
        ids = self.ids()

        # 1. the design cross-read opens a divergence; the BA decides it (option B) and answers the other questions
        result = self.cli("cross", PID, "--change", CID, "--kind", "diseno", "--claims",
                          str(self.claims("cruce_diseno.md", ids)))
        opened = [g for g in result["gaps_opened"] if g.startswith(("GAP-DIS-", "GAP-SRD-", "GAP-SED-"))]
        divergence = next(g for g in opened if g.startswith("GAP-DIS-"))
        self.answer(opened, DIVERGENCE, option="B")
        self.assertEqual(self.status_of(divergence), "CLOSED")

        # 2. the harvest closes the baseline cross-read; its candidate surfaces are decided (declined)
        self.cli("harvest", PID, "--source", "harvest_compras.md", "--change", CID)
        forget_read_snapshots()
        for item in new_surface_candidates(PID, CID):
            run_ok(["cross", PID, "--change", CID, "--decline-new", item["id"], "--reason", "no se construye en este cambio"])
        open_blocking = [g for g, row in self.gap_rows().items()
                         if row["severity"].strip("`") in ("critical", "high") and self.status_of(g) == "OPEN"]
        if open_blocking:
            self.answer(open_blocking, "Se resuelve como indica el pedido.")
        self.assertEqual(self.blocking(), 0)

        # 3. the contradictions cross-read finds the threshold question again: it is born decided, and does not block
        claims = Path.cwd() / "con.md"
        claims.write_text((CROSSES / "cruce_contradicciones_umbral.md").read_text(encoding="utf-8")
                          .replace("F-PED", ids["pedido"]), encoding="utf-8")
        result = self.cli("cross", PID, "--change", CID, "--kind", "contradicciones", "--claims", str(claims))
        (con,) = [g for g in result["gaps_opened"] if g.startswith("GAP-CON-")]
        self.assertIn(con, result["pre_decided"])
        self.assertEqual(self.status_of(con), "PRE_DECIDED")
        self.assertEqual(self.blocking(), 0)

        # 4. the lens coherence is the next step, before the extraction
        step = self.cli("next", PID, "--change", CID)
        self.assertEqual(step["key"], "coherence")
        self.assertEqual(step["skill"], "sentinel-self-review §Change coherence")

        # 5. the BA's reading of the lenses opens a question of its own
        result = self.cli("self-review", PID, "--crosses", "--change", CID, "--source", str(FIXTURE))
        (xrv,) = result["gaps_opened"]
        self.assertTrue(xrv.startswith("GAP-XRV-"))
        self.assertEqual(self.status_of(xrv), "OPEN")

        # 6. the BA confirms the earlier decision for the contradiction
        self.cli("gaps", PID, "--change", CID, "--id", con, "--accept-prior")
        self.assertEqual(self.status_of(con), "CLOSED")

        # 7. the decision of the divergence is found in the memory of the change
        found = self.cli("retrieve", PID, "--query", "umbral", "--workflow", "decision", "--artifact-type", "change_decision", "--trace-id", CID)
        rows = found if isinstance(found, list) else found.get("results") or found.get("chunks") or []
        self.assertTrue(rows)
        self.assertTrue(any(DIVERGENCE in row["text"] for row in rows))


if __name__ == "__main__":
    unittest.main()
