"""IMP-393: a MODIFIED/REMOVED requirement of a change names the existing stories it affects (`Afecta`)."""
from __future__ import annotations

import json
import shutil
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import SnapshotWorkspaceCase, run_ok  # noqa: E402
from sentinel.change_requirements import (  # noqa: E402
    change_requirements_path, load_change_ears, parse_affects, story_candidates,
)
from sentinel.workspace import workspace_path  # noqa: E402
from test_change_flow import SCOPE_ANSWER  # noqa: E402
from test_change_requirements import EARS_TWO, gap_status  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"
ONE = "Cuando el comprador guarda el alta incompleta, el sistema debe conservar los datos cargados."


def answer(delta: str | None, affects: str | None, evidence: str | None = None, text: str = ONE) -> str:
    lines = ["### GAP-ACCEPTANCE", f"- Respuesta: {text}", "- Owner / fuente: Jefa de Compras"]
    if delta is not None:
        lines.append(f"- Delta: {delta}")
    if affects is not None:
        lines.append(f"- Afecta: {affects}")
    lines.append("- Superficie: Tabla de proveedores")
    if evidence is not None:
        lines.append(f"- Evidencia o referencia: {evidence}")
    lines.append("- Estado de decisión: confirmado")
    return "\n".join(lines) + "\n"


def write_story(project: str, number: int, trace: list[str] | None = None, change: str | None = None) -> None:
    folder = workspace_path(project) / "04_backlog"
    folder.mkdir(parents=True, exist_ok=True)
    lines = ["---", f"id: US-{number:03d}", f"project: {project}", "parent_epic: EPIC-001", "status: draft"]
    if change:
        lines.append(f"change: {change}")
    lines += ["trace:", *[f"  - {item}" for item in trace or []], "---", "", f"# US-{number:03d} - Alta de proveedores", ""]
    (folder / f"US-{number:03d}.md").write_text("\n".join(lines), encoding="utf-8")


class ChangeAffects(SnapshotWorkspaceCase):
    @classmethod
    def build_workspace(cls):
        root = Path.cwd()
        shutil.copy(FIXTURES / "change_borrador.md", root / "pedido.md")
        (root / "scope.md").write_text(SCOPE_ANSWER, encoding="utf-8")
        run_ok(["init", "BORR"])
        out = json.loads(run_ok(["ingest", "BORR", "--source", "pedido.md", "--change"]))
        run_ok(["resolve-gaps", "BORR", "--source", "scope.md", "--change", out["change_id"]])

    def setUp(self):
        super().setUp()
        # IMP-396: /status now lists the changes (a list of per-change dicts); the id is the first one's.
        listed = json.loads(run_ok(["status", "BORR"])).get("changes") or [{"change_id": "CHG-001"}]
        self.cid = listed[0]["change_id"]

    def resolve(self, name: str, text: str) -> dict:
        Path(name).write_text(text, encoding="utf-8")
        return json.loads(run_ok(["resolve-gaps", "BORR", "--source", name, "--change", self.cid]))

    def rows_path(self) -> Path:
        return change_requirements_path(workspace_path("BORR"), self.cid)

    def test_parse_affects(self):
        self.assertEqual(parse_affects("US-003, US-007"), ["US-003", "US-007"])
        self.assertEqual(parse_affects("US-003 US-007"), ["US-003", "US-007"])
        self.assertEqual(parse_affects("us-003"), ["US-003"])
        for none in ("ninguna", "Ninguno", "none", " NONE "):
            self.assertEqual(parse_affects(none), [])
        for bad in ("", "x", None, "US-3"):
            self.assertIsNone(parse_affects(bad))

    def test_case_b_modified_without_affects_closes(self):
        res = self.resolve("a.md", answer("MODIFIED", None))
        self.assertIn("GAP-ACCEPTANCE", res["closed"])
        self.assertEqual(res["affects_findings"], [])
        rows = load_change_ears("BORR", self.cid)
        self.assertEqual([r["affects"] for r in rows], [[]])

    def test_modified_without_affects_with_stories_stays_open(self):
        write_story("BORR", 1)
        write_story("BORR", 2)
        res = self.resolve("a.md", answer("MODIFIED", None, evidence="US-002 describe el alta"))
        self.assertNotIn("GAP-ACCEPTANCE", res["closed"])
        self.assertNotEqual(gap_status("BORR", self.cid, "GAP-ACCEPTANCE"), "CLOSED")
        self.assertFalse(self.rows_path().exists())
        finding = res["affects_findings"][0]
        self.assertEqual(finding["gap"], "GAP-ACCEPTANCE")
        self.assertEqual(finding["candidates"], ["US-002"])
        self.assertIn("US-002", finding["note"])

    def test_only_the_changes_own_stories_do_not_make_affects_mandatory(self):
        write_story("BORR", 1, change=self.cid)
        res = self.resolve("a.md", answer("MODIFIED", None))
        self.assertIn("GAP-ACCEPTANCE", res["closed"])
        self.assertEqual(res["affects_findings"], [])

    def test_unknown_story_in_affects_stays_open(self):
        write_story("BORR", 1)
        res = self.resolve("a.md", answer("REMOVED", "US-099"))
        self.assertNotIn("GAP-ACCEPTANCE", res["closed"])
        self.assertIn("US-099", res["affects_findings"][0]["note"])
        self.assertFalse(self.rows_path().exists())

    def test_none_is_a_valid_affects_with_stories(self):
        write_story("BORR", 1)
        res = self.resolve("a.md", answer("MODIFIED", "ninguna"))
        self.assertIn("GAP-ACCEPTANCE", res["closed"])
        self.assertEqual(res["affects_findings"], [])
        self.assertEqual(load_change_ears("BORR", self.cid)[0]["affects"], [])

    def test_affects_written_and_loaded(self):
        write_story("BORR", 1)
        write_story("BORR", 2)
        res = self.resolve("a.md", answer("MODIFIED", "US-002"))
        self.assertIn("GAP-ACCEPTANCE", res["closed"])
        text = self.rows_path().read_text(encoding="utf-8")
        self.assertIn("| ID | Pattern | Delta | Statement | Source | Afecta | Superficie |", text)
        rows = load_change_ears("BORR", self.cid)
        self.assertEqual(rows[0]["affects"], ["US-002"])
        again = self.resolve("b.md", answer("MODIFIED", "US-001, US-002"))
        self.assertEqual(again["ears_rows"], [])
        self.assertEqual(again["delta_updated"], [rows[0]["id"]])
        self.assertEqual(load_change_ears("BORR", self.cid)[0]["affects"], ["US-001", "US-002"])

    def test_affects_on_added_is_ignored_with_a_note(self):
        write_story("BORR", 1)
        res = self.resolve("a.md", answer("ADDED", "US-001"))
        self.assertIn("GAP-ACCEPTANCE", res["closed"])
        self.assertEqual(load_change_ears("BORR", self.cid)[0]["affects"], [])
        self.assertEqual(res["affects_findings"][0]["gap"], "GAP-ACCEPTANCE")
        self.assertEqual(res["affects_findings"][0]["candidates"], [])

    def test_candidates_from_border_citation(self):
        write_story("BORR", 1, trace=["REQ-001"])
        write_story("BORR", 2, trace=["REQ-001", "SPEC-U-001"])
        write_story("BORR", 3, trace=["SPEC-U-001"], change=self.cid)
        scope = SCOPE_ANSWER.replace("Envío actual del alta de proveedores", "Envío actual del alta (SPEC-U-001)")
        self.resolve("s.md", scope)
        self.assertEqual(story_candidates("BORR", self.cid, ""), ["US-002"])
        self.assertEqual(story_candidates("BORR", self.cid, "ver US-001"), ["US-001", "US-002"])

    def test_candidates_from_readiness_source_unit(self):
        write_story("BORR", 1)
        pack = workspace_path("BORR") / "08_context_packs" / "implementation_readiness.json"
        pack.parent.mkdir(parents=True, exist_ok=True)
        pack.write_text(json.dumps({"stories": [{"story_id": "US-001", "source_unit": "SPEC-U-004", "trace": []}]}), encoding="utf-8")
        self.assertEqual(story_candidates("BORR", self.cid, "regla SPEC-U-004"), ["US-001"])
        self.assertEqual(story_candidates("BORR", self.cid, "regla SPEC-U-005"), [])

    def test_v0200_table_without_affects_column_loads(self):
        path = self.rows_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "# Requisitos del cambio X\n\n## Normalized Requirements (EARS)\n\n"
            "| ID | Pattern | Delta | Statement | Source |\n| --- | --- | --- | --- | --- |\n"
            f"| REQ-EARS-001 | event | MODIFIED | {ONE} | `GAP-ACCEPTANCE` / `{self.cid}` |\n",
            encoding="utf-8",
        )
        rows = load_change_ears("BORR", self.cid)
        self.assertEqual([(r["id"], r["delta"], r["affects"]) for r in rows], [("REQ-EARS-001", "MODIFIED", [])])
        # a later reconcile upgrades the table to six columns and keeps the id
        write_story("BORR", 1)
        self.resolve("a.md", answer("MODIFIED", "US-001"))
        rows = load_change_ears("BORR", self.cid)
        self.assertEqual([(r["id"], r["affects"]) for r in rows], [("REQ-EARS-001", ["US-001"])])
        self.assertIn("Afecta", path.read_text(encoding="utf-8"))

    def test_project_path_ignores_affects_field(self):
        run_ok(["init", "PROJ"])
        shutil.copy(FIXTURES / "change_borrador.md", Path("proyecto.md"))
        run_ok(["ingest", "PROJ", "--source", "proyecto.md"])
        Path("p.md").write_text(answer("MODIFIED", "US-099", text=EARS_TWO), encoding="utf-8")
        res = json.loads(run_ok(["resolve-gaps", "PROJ", "--source", "p.md"]))
        self.assertIn("GAP-ACCEPTANCE", res["closed"])
        self.assertNotIn("affects_findings", res)


if __name__ == "__main__":
    unittest.main()
