"""IMP-404 (H26 inc 4) task 5: /next --change asks for the cross-reads and the new surfaces; /status --change shows them."""
from __future__ import annotations

import json
import shutil
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import IDS_SCOPE_ANSWER, SnapshotWorkspaceCase, run_cli, run_ok, waive_coherence  # noqa: E402

from sentinel.changes import list_changes  # noqa: E402
from sentinel.core.io import forget_read_snapshots  # noqa: E402
from sentinel.crosses.record import record_cross, skip_cross  # noqa: E402
from sentinel.crosses.state import cross_status  # noqa: E402
from sentinel.crosses.surfaces import accept_new_surface, decline_new_surface, new_surface_candidates  # noqa: E402
from sentinel.readiness_verdict import change_next_step  # noqa: E402
from sentinel.status import change_status, project_status  # noqa: E402
from sentinel.workspace import update_state  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"
CROSSES = FIXTURES / "change_crosses"
SAD = FIXTURES / "change_baseline" / "sad-compras.md"
PID = "CRXN"
CID = "CHG-001"


def set_language(project: str, language: str) -> None:
    changes = {key: dict(value) for key, value in list_changes(project).items()}
    changes[CID]["language"] = language
    update_state(project, changes=changes)


class NextCase(SnapshotWorkspaceCase):
    @classmethod
    def build_workspace(cls):
        root = Path.cwd()
        shutil.copy(CROSSES / "pedido_contradiccion.md", root / "pedido.md")
        shutil.copy(CROSSES / "harvest_compras.md", root / "harvest_compras.md")
        (root / "scope.md").write_text(IDS_SCOPE_ANSWER, encoding="utf-8")
        run_ok(["init", PID])
        run_ok(["ingest", PID, "--source", "pedido.md", "--change"])
        run_ok(["resolve-gaps", PID, "--source", "scope.md", "--change", CID])
        run_ok(["sources", PID, "--load", str(SAD), "--role", "linea_de_base", "--change", CID])

    def setUp(self):
        super().setUp()
        forget_read_snapshots()

    def step(self) -> dict:
        forget_read_snapshots()
        return change_next_step(PID, CID)

    def load_design(self) -> str:
        return json.loads(run_ok(["sources", PID, "--load", str(CROSSES / "prototipo-aprobaciones.html"),
                                  "--role", "diseno_nuevo", "--change", CID]))["source_id"]

    def claims(self, name: str, ids: dict[str, str]) -> Path:
        text = (CROSSES / name).read_text(encoding="utf-8")
        text = text.replace("F-PED", ids["pedido"]).replace("F-DIS", ids["diseno"])
        path = Path.cwd() / f"sub-{name}"
        path.write_text(text, encoding="utf-8")
        return path

    def answer_design_gap(self) -> None:
        gap = next(g for g in self.open_gaps() if g.startswith("GAP-DIS-"))
        answer = Path.cwd() / "dis.md"
        answer.write_text("\n".join([f"### {gap}", "- Respuesta: (A) rige el diseño.", "- Owner / fuente: Jefa de Compras",
                                     "- Estado de decisión: confirmado", ""]), encoding="utf-8")
        run_ok(["resolve-gaps", PID, "--source", str(answer), "--change", CID])

    def open_gaps(self) -> list[str]:
        from sentinel.changes import change_gaps_path
        from sentinel.gaps import parse_gap_rows
        from sentinel.workspace import workspace_path

        path = change_gaps_path(workspace_path(PID), CID)
        rows = parse_gap_rows(path.read_text(encoding="utf-8"))
        return [g["id"] for g in rows if str(g.get("status", "OPEN")).strip("`").upper() != "CLOSED"]

    def ids(self) -> dict[str, str]:
        from sentinel.status import change_sources

        found = change_sources(PID, CID)["by_role"]
        return {"pedido": found["pedido"][0], "diseno": found["diseno_nuevo"][0]}


class Crosses(NextCase):
    def test_crosses_step_lists_the_three(self):
        step = self.step()
        self.assertEqual(step["key"], "crosses")
        for text in ("/harvest", "--kind contradicciones"):
            self.assertIn(text, step["text"])
        # I6: with no prototype loaded the design cross-read does not apply, so it is not asked for
        self.assertNotIn("--kind diseno", step["text"])
        self.assertNotIn("diseño nuevo", step["text"])
        self.assertTrue(step["text"].startswith("Faltan 2 cruce(s) de CHG-001:"))
        self.assertEqual(cross_status(PID, CID)["kinds"]["diseno"]["state"], "no_aplica")
        self.assertEqual(step["command"], f"/harvest {PID} --source PATH --change {CID}")

    def test_design_source_changes_the_hint(self):
        self.load_design()
        step = self.step()
        self.assertEqual(step["key"], "crosses")
        self.assertIn("--kind diseno", step["text"])
        self.assertTrue(step["text"].startswith("Faltan 3 cruce(s) de CHG-001:"))

    def test_command_of_the_design_cross(self):
        run_ok(["harvest", PID, "--source", "harvest_compras.md", "--change", CID])
        self.assertEqual(self.step()["command"], f"/cross {PID} --change {CID} --kind contradicciones --claims PATH")
        self.load_design()
        self.assertEqual(self.step()["command"], f"/cross {PID} --change {CID} --kind diseno --claims PATH")

    def test_blocking_cross_gap_goes_back_to_lenses(self):
        run_ok(["harvest", PID, "--source", "harvest_compras.md", "--change", CID])
        self.load_design()
        record_cross(PID, CID, "diseno", self.claims("cruce_diseno.md", self.ids()))
        step = self.step()
        self.assertEqual(step["key"], "lenses")
        self.assertEqual(list_changes(PID)[CID]["gap_counts"]["blocking_open"], 1)

    def test_stale_cross_is_asked_again(self):
        run_ok(["harvest", PID, "--source", "harvest_compras.md", "--change", CID])
        self.load_design()
        ids = self.ids()
        record_cross(PID, CID, "diseno", self.claims("cruce_diseno.md", ids))
        self.answer_design_gap()
        copy = Path.cwd() / "prototipo-v2.html"
        html = (CROSSES / "prototipo-aprobaciones.html").read_text(encoding="utf-8")
        copy.write_text(html.replace("</body>", "<p>Pantalla nueva de reportes de altas</p>\n</body>"), encoding="utf-8")
        loaded = json.loads(run_ok(["sources", PID, "--load", str(copy), "--role", "diseno_nuevo", "--change", CID]))
        run_ok(["sources", PID, "--id", ids["diseno"], "--superseded-by", loaded["source_id"], "--reason", "x"])
        forget_read_snapshots()
        info = cross_status(PID, CID)["kinds"]["diseno"]
        self.assertEqual(info["state"], "stale")
        # the claims were rebased onto the new version: what is stale is the pending delta, not a cited source
        self.assertEqual(info["stale_sources"], [])
        self.assertEqual(info["delta"]["design"], loaded["source_id"])
        step = self.step()
        self.assertEqual(step["key"], "crosses")
        self.assertIn("--kind diseno --claims ARCHIVO --delta", step["text"])
        self.assertIn(f"la fuente nueva {loaded['source_id']}", step["text"])

    def test_waived_baseline_needs_no_harvest(self):
        shutil.copy(CROSSES / "pedido_contradiccion.md", Path.cwd() / "otro.md")
        run_ok(["init", "CRXW"])
        run_ok(["ingest", "CRXW", "--source", "otro.md", "--change"])
        run_ok(["resolve-gaps", "CRXW", "--source", "scope.md", "--change", CID])
        run_ok(["sources", "CRXW", "--change", CID, "--no-baseline", "--reason", "sistema nuevo"])
        forget_read_snapshots()
        status = cross_status("CRXW", CID)
        self.assertNotIn("linea_de_base", status["missing"])
        self.assertEqual(status["kinds"]["linea_de_base"]["state"], "waived")
        self.assertEqual(change_next_step("CRXW", CID)["key"], "crosses")
        self.assertNotIn("/harvest", change_next_step("CRXW", CID)["text"])

    def test_english_texts(self):
        set_language(PID, "en")
        self.load_design()
        step = self.step()
        self.assertEqual(step["key"], "crosses")
        self.assertTrue(step["text"].startswith("3 cross-read(s) of CHG-001 are missing:"))
        for text in ("baseline (/harvest", "new design (/cross", "internal contradictions of the request (/cross"):
            self.assertIn(text, step["text"])
        self.assertNotIn("Faltan", step["text"])
        self.assertNotIn("diseño", step["text"])


class NewSurfaces(NextCase):
    def test_new_surfaces_step(self):
        run_ok(["harvest", PID, "--source", "harvest_compras.md", "--change", CID])
        self.load_design()
        ids = self.ids()
        record_cross(PID, CID, "diseno", self.claims("cruce_diseno.md", ids))
        skip_cross(PID, CID, "contradicciones", "no aplica")
        answer = Path.cwd() / "dis.md"
        gap = next(g for g in self.open_gaps() if g.startswith("GAP-DIS-"))
        answer.write_text(f"### {gap}\n- Respuesta: (A) rige el diseño.\n- Owner / fuente: Jefa de Compras\n"
                          "- Estado de decisión: confirmado\n", encoding="utf-8")
        run_ok(["resolve-gaps", PID, "--source", str(answer), "--change", CID])
        step = self.step()
        self.assertEqual(step["key"], "cross_new_surfaces")
        found = new_surface_candidates(PID, CID)
        self.assertEqual(len(found), 2)
        for item in found:
            self.assertIn(item["id"], step["text"])
        self.assertIn("--accept-new", step["command"])
        accept_new_surface(PID, CID, found[0]["id"], "pantalla", "Historial de aprobaciones")
        decline_new_surface(PID, CID, found[1]["id"], "ya existe")
        self.assertEqual(self.step()["key"], "coherence")  # IMP-410: the lens coherence comes before the extraction
        waive_coherence(PID, CID)
        self.assertEqual(self.step()["key"], "extract_inventory")


class Status(NextCase):
    def test_status_block(self):
        run_ok(["harvest", PID, "--source", "harvest_compras.md", "--change", CID])
        forget_read_snapshots()
        status = change_status(PID, CID)
        self.assertEqual(list(status["crosses"]["kinds"]), ["linea_de_base", "diseno", "contradicciones"])
        self.assertEqual(len(status["new_surface_candidates"]), 2)
        triggers = {w["trigger"]: w["message"] for w in status["warnings"]}
        self.assertIn("crosses_missing", triggers)
        self.assertIn("contradicciones internas", triggers["crosses_missing"])
        self.assertNotIn("diseño nuevo", triggers["crosses_missing"])
        self.assertIn("new_surfaces_pending", triggers)
        self.assertIn("2 candidata(s)", triggers["new_surfaces_pending"])
        code, out = run_cli(["status", PID])
        self.assertEqual(code, 0)
        self.assertNotIn("crosses", json.loads(out))
        self.assertNotIn("crosses", project_status(PID))


if __name__ == "__main__":
    unittest.main()
