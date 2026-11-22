"""IMP-396: a confirmed EARS answer of a change names the border surface(s) it touches (`Superficie`)."""
from __future__ import annotations

import json
import shutil
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import SnapshotWorkspaceCase, run_ok  # noqa: E402
from sentinel.change_requirements import (  # noqa: E402
    change_requirements_path, load_change_ears, parse_surfaces, propose_surfaces,
)
from sentinel.changes import get_change  # noqa: E402
from sentinel.core.markdown import parse_frontmatter  # noqa: E402
from sentinel.gaps import parse_gap_responses  # noqa: E402
from sentinel.workspace import workspace_path  # noqa: E402
from test_change_flow import SCOPE_ANSWER  # noqa: E402
from test_change_requirements import gap_status  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"
ONE = "Cuando el comprador guarda el alta incompleta, el sistema debe conservar los datos cargados."
LISTADO = 'Listado "Mis borradores"'
BOTON = 'Botón "Guardar borrador" en el alta de proveedores'
V021_TABLE = """# Requisitos del cambio CHG-001

## Normalized Requirements (EARS)

| ID | Pattern | Delta | Statement | Source | Afecta |
| --- | --- | --- | --- | --- | --- |
| REQ-EARS-001 | event | ADDED | Cuando A, el sistema debe B. | `GAP-ACCEPTANCE` / `CHG-001` | US-001, US-002 |
"""


def answer(surface: str | None, delta: str = "ADDED", text: str = ONE, label: str = "Superficie") -> str:
    lines = ["### GAP-ACCEPTANCE", f"- Respuesta: {text}", "- Owner / fuente: Jefa de Compras", f"- Delta: {delta}"]
    if surface is not None:
        lines.append(f"- {label}: {surface}")
    lines.append("- Estado de decisión: confirmado")
    return "\n".join(lines) + "\n"


class ChangeSurfaces(SnapshotWorkspaceCase):
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

    def border(self) -> list[dict]:
        return get_change("BORR", self.cid)["border"]

    def test_parse_and_propose_surfaces(self):
        border = self.border()
        valid, unknown = parse_surfaces(f"  {LISTADO.upper()} ; Pantalla Inexistente ; ", border)
        self.assertEqual(valid, [LISTADO])
        self.assertEqual(unknown, ["Pantalla Inexistente"])
        self.assertEqual(parse_surfaces('botón "guardar BORRADOR" en el alta de proveedores', border)[0], [BOTON])
        self.assertEqual(parse_surfaces("BOTON \"guardar borrador\" en el alta de proveedores", border)[0], [BOTON])
        self.assertEqual(parse_surfaces("", border), ([], []))
        self.assertEqual(
            propose_surfaces('Cuando el analista abre el listado "mis borradores", el sistema debe listarlos.', border), [LISTADO])
        self.assertEqual(propose_surfaces("Nada que ver", border), [])
        self.assertEqual(parse_gap_responses(answer("A; B"))["GAP-ACCEPTANCE"]["surface"], "A; B")
        self.assertEqual(parse_gap_responses(answer("A", label="Surface"))["GAP-ACCEPTANCE"]["surface"], "A")

    def test_ears_answer_without_surface_stays_open(self):
        res = self.resolve("a.md", answer(None, text=f"Cuando el analista abre el {LISTADO}, el sistema debe listar sus altas."))
        self.assertNotIn("GAP-ACCEPTANCE", res["closed"])
        self.assertNotEqual(gap_status("BORR", self.cid, "GAP-ACCEPTANCE"), "CLOSED")
        finding = res["surface_findings"][0]
        self.assertEqual(finding["gap"], "GAP-ACCEPTANCE")
        self.assertEqual(finding["proposed"], [LISTADO])
        self.assertIn(BOTON, finding["border"])
        self.assertTrue(finding["note"])
        self.assertFalse(change_requirements_path(workspace_path("BORR"), self.cid).exists())

    def test_unknown_surface_stays_open_and_lists_border(self):
        res = self.resolve("a.md", answer("Pantalla Fantasma"))
        self.assertNotIn("GAP-ACCEPTANCE", res["closed"])
        finding = res["surface_findings"][0]
        self.assertEqual(len(finding["border"]), 5)
        self.assertIn("Pantalla Fantasma", finding["note"])
        res = self.resolve("b.md", answer(f"{LISTADO}; Otra"))
        self.assertNotIn("GAP-ACCEPTANCE", res["closed"])

    def test_unchanged_also_needs_a_surface(self):
        res = self.resolve("a.md", answer(None, delta="UNCHANGED"))
        self.assertNotIn("GAP-ACCEPTANCE", res["closed"])
        self.assertEqual(res["surface_findings"][0]["gap"], "GAP-ACCEPTANCE")

    def test_surface_written_and_loaded(self):
        res = self.resolve("a.md", answer(f"{LISTADO.lower()}; {BOTON}"))
        self.assertIn("GAP-ACCEPTANCE", res["closed"])
        self.assertEqual(res["surface_findings"], [])
        text = change_requirements_path(workspace_path("BORR"), self.cid).read_text(encoding="utf-8")
        self.assertIn("| ID | Pattern | Delta | Statement | Source | Afecta | Superficie |", text)
        rows = load_change_ears("BORR", self.cid)
        self.assertEqual(rows[0]["surfaces"], [LISTADO, BOTON])
        before = rows[0]["id"]
        self.resolve("b.md", answer(BOTON))
        again = load_change_ears("BORR", self.cid)
        self.assertEqual([r["id"] for r in again], [before])
        self.assertEqual(again[0]["surfaces"], [BOTON])

    def test_v021_table_loads_with_empty_surfaces(self):
        path = change_requirements_path(workspace_path("BORR"), self.cid)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(V021_TABLE, encoding="utf-8")
        rows = load_change_ears("BORR", self.cid)
        self.assertEqual(rows[0]["surfaces"], [])
        self.assertEqual(rows[0]["affects"], ["US-001", "US-002"])
        old5 = V021_TABLE.replace(" | Afecta |", " |").replace("| --- | --- | --- | --- | --- | --- |", "| --- | --- | --- | --- | --- |")
        old5 = old5.replace(" | US-001, US-002 |", " |")
        path.write_text(old5, encoding="utf-8")
        self.assertEqual(load_change_ears("BORR", self.cid)[0]["surfaces"], [])
        # a later closing upgrades the table to 7 columns without losing the old row
        path.write_text(V021_TABLE, encoding="utf-8")
        self.resolve("a.md", answer(LISTADO, text="Cuando el analista abre el listado, el sistema debe mostrarlo."))
        text = path.read_text(encoding="utf-8")
        self.assertIn("Superficie |", text)
        self.assertIn("REQ-EARS-001", text)
        widths = {len(line.split(" | ")) for line in text.splitlines() if line.startswith("| REQ-EARS")}
        self.assertEqual(widths, {7})


class ChangeSurfacesOpenBorder(SnapshotWorkspaceCase):
    @classmethod
    def build_workspace(cls):
        root = Path.cwd()
        shutil.copy(FIXTURES / "change_borrador.md", root / "pedido.md")
        run_ok(["init", "BORR"])
        run_ok(["ingest", "BORR", "--source", "pedido.md", "--change"])

    def test_unconfirmed_border_skips_the_check(self):
        Path("a.md").write_text(answer(None), encoding="utf-8")
        res = json.loads(run_ok(["resolve-gaps", "BORR", "--source", "a.md", "--change", "CHG-001"]))
        self.assertEqual(res["surface_findings"], [])


class ChangeSurfacesFlow(SnapshotWorkspaceCase):
    @classmethod
    def build_workspace(cls):
        from test_change_specs import ALL_ANSWERS, open_change

        run_ok(["init", "BORR"])
        cid = open_change("BORR")
        Path("all.md").write_text(ALL_ANSWERS, encoding="utf-8")
        run_ok(["resolve-gaps", "BORR", "--source", "all.md", "--change", cid])
        run_ok(["brief", "BORR", "--change", cid])

    def test_surfaces_flow_to_unit_and_story(self):
        cid = "CHG-001"
        rows = load_change_ears("BORR", cid)
        self.assertTrue(rows and all(r["surfaces"] for r in rows))
        run_ok(["specs", "BORR", "--change", cid])
        base = workspace_path("BORR")
        units = sorted((base / "03_specs" / cid / "units").glob("SPEC-U-*.md"))
        self.assertTrue(units)
        by_unit = {}
        for unit in units:
            front = parse_frontmatter(unit.read_text(encoding="utf-8"))
            self.assertTrue(front.get("surfaces"), unit.name)
            by_unit[front["id"]] = front["surfaces"]
        run_ok(["backlog", "BORR", "--change", cid])
        stories = sorted((base / "04_backlog").glob("US-*.md"))
        self.assertTrue(stories)
        for story in stories:
            front = parse_frontmatter(story.read_text(encoding="utf-8"))
            self.assertEqual(front["surfaces"], by_unit[front["source_unit"]])


class ProjectPathIgnoresSurface(SnapshotWorkspaceCase):
    @classmethod
    def build_workspace(cls):
        (Path.cwd() / "raw.md").write_text("# Panel\n\nObjective: let operations leads review risk queues.\n", encoding="utf-8")
        run_ok(["init", "PLAIN"])
        run_ok(["ingest", "PLAIN", "--source", "raw.md"])

    def test_project_path_ignores_surface_field(self):
        Path("r.md").write_text(
            "### GAP-OBJECTIVE\n- Respuesta: Que el equipo vea el estado.\n- Owner / fuente: Jefa\n- Superficie: X\n"
            "- Estado de decisión: confirmado\n", encoding="utf-8")
        out = json.loads(run_ok(["resolve-gaps", "PLAIN", "--source", "r.md"]))
        self.assertNotIn("surface_findings", out)


if __name__ == "__main__":
    unittest.main()
