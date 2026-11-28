"""IMP-416 task 6: new surfaces of a change become enablers and the change has its own slice plan."""
from __future__ import annotations

import json
import shutil
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import SnapshotWorkspaceCase, build_matured_workspace, gap_acceptance_answer, place_harvest_docs, run_ok  # noqa: E402
from sentinel.compilers.change_backlog import read_change_units  # noqa: E402
from sentinel.core.markdown import parse_frontmatter  # noqa: E402
from sentinel.crosses.surfaces import accept_new_surface, new_surface_candidates  # noqa: E402
from sentinel.readiness_verdict import _backlog_behind, change_next_step  # noqa: E402
from sentinel.slice_plan import build_phases, build_story_rows  # noqa: E402
from sentinel.change_validation import validate_change  # noqa: E402
from sentinel.workspace import workspace_path  # noqa: E402
from test_change_specs import PROJECT_EARS, PROJECT_RAW, open_change  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"
PID = "MIX"
NEW = "Bandeja de aprobación"
TABLE = "Tabla de proveedores"


def _answer(gap: str, text: str, delta: str, surface: str, affects: str = "") -> str:
    return (f"### {gap}\n- Respuesta: {text}\n- Owner / fuente: Jefa de Compras\n- Delta: {delta}\n"
            f"- Superficie: {surface}\n{affects}- Estado de decisión: confirmado\n")


ANSWERS = "\n".join([
    _answer("GAP-ACCEPTANCE",
            "Cuando el comprador guarda el alta incompleta, el sistema debe conservar los datos cargados.",
            "ADDED", NEW),
    _answer("GAP-OBJECTIVE",
            "Cuando el comprador cambia el texto del aviso, el sistema debe mostrar el aviso nuevo.",
            "MODIFIED", TABLE, "- Afecta: US-001\n"),
    _answer("GAP-TECH-NFR",
            "Cuando el comprador consulta sus altas incompletas, el sistema debe responder en menos de dos segundos.",
            "ADDED", TABLE),
    _answer("GAP-USERS",
            "Cuando el comprador sigue enviando el alta completa, el sistema debe continuar validando los datos.",
            "UNCHANGED", TABLE),
])


def ws() -> Path:
    return workspace_path(PID)


def front(story_id: str) -> dict:
    return parse_frontmatter((ws() / "04_backlog" / f"{story_id}.md").read_text(encoding="utf-8"))


class ChangeEnablersPlan(SnapshotWorkspaceCase):
    cid = "CHG-001"

    @classmethod
    def build_workspace(cls):
        build_matured_workspace(PID, PROJECT_RAW, gap_acceptance_answer(PROJECT_EARS))
        cid = cls.cid = open_change(PID)
        shutil.copy(FIXTURES / "change_crosses" / "harvest_compras.md", "harvest_compras.md")
        Path("a.md").write_text(ANSWERS, encoding="utf-8")
        place_harvest_docs(PID, Path("harvest_compras.md").read_text(encoding="utf-8"))  # IMP-435 (B-37)
        run_ok(["harvest", PID, "--source", "harvest_compras.md", "--change", cid])
        accept_new_surface(PID, cid, new_surface_candidates(PID, cid)[0]["id"], "pantalla", NEW)
        run_ok(["resolve-gaps", PID, "--source", "a.md", "--change", cid])
        run_ok(["brief", PID, "--change", cid])
        run_ok(["specs", PID, "--change", cid])

    def backlog(self) -> dict:
        return json.loads(run_ok(["backlog", PID, "--change", self.cid]))

    def test_new_surface_becomes_enabler(self):
        res = self.backlog()
        enablers = [s for s in res["stories"] if front(s)["type"] == "cross_cutting_enabler"]
        self.assertEqual(len(enablers), 1)
        text = (ws() / "04_backlog" / f"{enablers[0]}.md").read_text(encoding="utf-8")
        meta = parse_frontmatter(text)
        self.assertIn("Construir pantalla «Bandeja de aprobación» para las historias que la usan", text)
        self.assertEqual(meta["surfaces"], [NEW])
        rationale = next(l for l in text.splitlines() if l.startswith("- Slicing rationale:"))
        self.assertNotIn("[PENDING INPUT]", rationale)
        self.assertIn("Cross-Cutting Enabler".lower(), rationale.lower().replace("habilitador transversal", "cross-cutting enabler"))
        self.assertIn(NEW, rationale)
        value = next(s for s in res["stories"] if s != enablers[0] and front(s).get("surfaces") == [NEW])
        self.assertIn(value, text)  # enables
        self.assertIn(value, rationale)
        self.assertIn("REQ-EARS-004", text)  # the UNCHANGED row, preserved
        self.assertEqual(text.count("| pass-to-pass |"), 2)  # the enabler's own plus the preserved row
        checks = {c["id"]: c["status"] for c in validate_change(PID, self.cid)["checks"]}
        self.assertEqual(checks["preserved_pass_to_pass"], "PASS")
        self.assertEqual(checks["stories_inside_border"], "PASS")

    def test_project_enablers_unchanged(self):
        from unittest.mock import patch
        import sentinel.compilers.slicing as slicing

        word = slicing.ENABLER_CANDIDATES[0]["tokens"][0]
        with patch.object(slicing, "cross_cutting_enabler_evidence", lambda project_id: word):
            specs = slicing.build_cross_cutting_enabler_specs(PID, [{"id": "US-010", "type": "change_request"}], {})
        self.assertTrue(specs)
        self.assertEqual(specs[0]["enables"], ["US-010"])
        self.assertNotIn("change", specs[0])

    def test_change_slice_plan_does_not_touch_project(self):
        project_md = ws() / "04_backlog" / "SLICE-PLAN.md"
        project_json = ws() / "08_context_packs" / "slice_plan.json"
        before = (project_md.read_bytes(), project_json.read_bytes())
        res = self.backlog()
        self.assertEqual((project_md.read_bytes(), project_json.read_bytes()), before)
        self.assertEqual(res["slice_plan"], f"04_backlog/{self.cid}/SLICE-PLAN.md")
        plan_md = (ws() / "04_backlog" / self.cid / "SLICE-PLAN.md").read_text(encoding="utf-8")
        self.assertIn("## Phase 0 - Enablers", plan_md)
        plan = json.loads((ws() / "08_context_packs" / self.cid / "slice_plan.json").read_text(encoding="utf-8"))
        enabler = next(s for s in res["stories"] if front(s)["type"] == "cross_cutting_enabler")
        position = plan["phases"]["positions"][enabler]
        self.assertEqual((position["wave"], position["parallel_group"]), (0, f"EPIC-{self.cid}"))
        self.assertEqual(sorted(plan["handoff_packs"]), sorted(res["stories"]))
        epic = (ws() / "04_backlog" / f"EPIC-{self.cid}.md").read_text(encoding="utf-8")
        self.assertIn(f"04_backlog/{self.cid}/SLICE-PLAN.md", epic)

    def test_enabler_does_not_block_next(self):
        self.backlog()
        units = read_change_units(PID, self.cid)
        self.assertTrue(units)
        self.assertFalse(_backlog_behind(ws(), self.cid, units, []))
        self.assertNotEqual(change_next_step(PID, self.cid)["key"], "backlog")
        (ws() / "04_backlog" / self.cid / "SLICE-PLAN.md").unlink()
        self.assertTrue(_backlog_behind(ws(), self.cid, units, []))

    def test_project_slice_plan_defaults(self):
        stories = [{"id": "US-001", "type": "cross_cutting_enabler", "title": "e", "enables": ["US-002"]},
                   {"id": "US-002", "type": "value_story", "title": "v"}]
        phases = build_phases(build_story_rows(stories, {"stories": []}))
        self.assertEqual(phases["positions"]["US-001"]["parallel_group"], "EPIC-002")
        phases = build_phases(build_story_rows(stories, {"stories": []}), "EPIC-CHG-009")
        self.assertEqual(phases["positions"]["US-001"]["parallel_group"], "EPIC-CHG-009")


if __name__ == "__main__":
    unittest.main()
