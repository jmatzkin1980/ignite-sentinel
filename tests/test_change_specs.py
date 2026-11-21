"""IMP-388: `/specs --change` builds SPEC-U units from the change's REQ-EARS rows, never a PRD."""
from __future__ import annotations

import io
import json
import shutil
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import SnapshotWorkspaceCase, build_matured_workspace, gap_acceptance_answer, run_cli, run_ok  # noqa: E402
from sentinel.cli import main as cli_main  # noqa: E402
from sentinel import mcp as sentinel_mcp  # noqa: E402
from sentinel.compilers.change_specs import compile_change_specs  # noqa: E402
from sentinel.core.markdown import parse_frontmatter  # noqa: E402
from sentinel.errors import GateRefusal  # noqa: E402
from sentinel.traceability import load_graph  # noqa: E402
from sentinel.id_registry import registry_path  # noqa: E402
from sentinel.workspace import read_json, update_state, workspace_path  # noqa: E402
from test_change_flow import SCOPE_ANSWER  # noqa: E402
from test_mcp_parity import _tools  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"
OBJECTIVE = ("### GAP-OBJECTIVE\n- Respuesta: Cuando el comprador cambia el texto del aviso, el sistema debe mostrar el aviso nuevo.\n"
             "- Owner / fuente: Jefa de Compras\n- Delta: MODIFIED\n- Estado de decisión: confirmado\n")
USERS = ("### GAP-USERS\n- Respuesta: Cuando el comprador sigue enviando el alta completa, el sistema debe continuar validando los datos.\n"
         "- Owner / fuente: Jefa de Compras\n- Delta: UNCHANGED\n- Estado de decisión: confirmado\n")
ACCEPTANCE = ("### GAP-ACCEPTANCE\n- Respuesta: Cuando el comprador guarda el alta incompleta, el sistema debe conservar los datos cargados. "
              "Cuando el comprador abre la lista de pendientes, el sistema debe listar sus altas incompletas.\n"
              "- Owner / fuente: Jefa de Compras\n- Delta: ADDED\n- Estado de decisión: confirmado\n")
EXTRA = ("### GAP-TECH-NFR\n- Respuesta: Cuando el comprador consulta sus altas incompletas, el sistema debe responder en menos de dos segundos.\n"
         "- Owner / fuente: Jefa de Compras\n- Delta: ADDED\n- Estado de decisión: confirmado\n")
ALL_ANSWERS = ACCEPTANCE + "\n" + OBJECTIVE + "\n" + USERS
PROJECT_RAW = """# Operations Risk Dashboard

Objective: let operations leads review risk queues before the daily meeting.

Users: operations leads and analysts.

In scope: read-only risk dashboard for open queues and queue drilldown.
"""
PROJECT_EARS = ("When queue metrics are available, the system shall display open risk queues. "
                "When an operations lead selects a queue, the system shall show the queue detail with current risk indicators.")


def units_dir(project: str, cid: str = "CHG-001") -> Path:
    return workspace_path(project) / "03_specs" / cid / "units"


def unit_files(project: str, cid: str = "CHG-001") -> list[str]:
    return sorted(p.stem for p in units_dir(project, cid).glob("SPEC-U-*.md"))


def open_change(project: str, note: str = "pedido.md") -> str:
    shutil.copy(FIXTURES / "change_borrador.md", Path.cwd() / note)
    (Path.cwd() / "scope.md").write_text(SCOPE_ANSWER, encoding="utf-8")
    cid = json.loads(run_ok(["ingest", project, "--source", note, "--change"]))["change_id"]
    run_ok(["resolve-gaps", project, "--source", "scope.md", "--change", cid])
    return cid


def answer(project: str, cid: str, name: str, text: str) -> dict:
    Path(name).write_text(text, encoding="utf-8")
    return json.loads(run_ok(["resolve-gaps", project, "--source", name, "--change", cid]))


class ChangeSpecs(SnapshotWorkspaceCase):
    cid = "CHG-001"

    @classmethod
    def build_workspace(cls):
        run_ok(["init", "BORR"])
        cid = open_change("BORR")
        answer("BORR", cid, "a.md", ALL_ANSWERS)
        run_ok(["brief", "BORR", "--change", cid])

    def test_builds_units_from_change_rows_without_prd(self):
        res = json.loads(run_ok(["specs", "BORR", "--change", self.cid]))
        self.assertEqual(res["units"], ["SPEC-U-001", "SPEC-U-002", "SPEC-U-003"])
        self.assertEqual(unit_files("BORR"), res["units"])
        base = workspace_path("BORR") / "03_specs"
        self.assertFalse((base / "prd.md").exists())
        self.assertFalse((base / "units").exists())
        self.assertTrue((base / self.cid / "specs.md").is_file())
        self.assertNotIn("prd", res["next_step"].lower())
        self.assertIn("03_specs/CHG-001/specs.md", res["next_step"])
        state = read_json(workspace_path("BORR") / "state.json", {})
        self.assertEqual(state["changes"][self.cid]["specs"]["units"], res["units"])
        report = json.loads((base / self.cid / "change_specs_report.json").read_text(encoding="utf-8"))
        self.assertEqual(report["by_delta"], {"ADDED": 2, "MODIFIED": 1})
        self.assertEqual(report["change_id"], self.cid)

    def test_unit_traces_and_cites_the_change_brief(self):
        run_ok(["specs", "BORR", "--change", self.cid])
        text = (units_dir("BORR") / "SPEC-U-001.md").read_text(encoding="utf-8")
        front = parse_frontmatter(text)
        ears = front["ears"][0]
        self.assertEqual(front["trace_ids"], [self.cid, ears])
        self.assertEqual(front["change"], self.cid)
        self.assertIn(front["delta"], {"ADDED", "MODIFIED", "REMOVED"})
        self.assertIn("02_requirements/CHG-001/project-brief.md", front["sources"])
        self.assertIn("02_requirements/CHG-001/requirements.md#normalized-requirements-ears", front["sources"])
        for banned in ("REQ-001", "PRD-001", "SPEC-001"):
            self.assertNotIn(banned, text)

    def test_unchanged_rows_are_listed_as_preserved_not_units(self):
        res = json.loads(run_ok(["specs", "BORR", "--change", self.cid]))
        self.assertEqual(len(res["preserved"]), 1)
        specs_md = (workspace_path("BORR") / "03_specs" / self.cid / "specs.md").read_text(encoding="utf-8")
        self.assertIn("Comportamiento preservado", specs_md)
        self.assertIn(res["preserved"][0], specs_md)
        self.assertIn("continuar validando", specs_md)

    def test_graph_links_each_unit_to_its_ears_requirement(self):
        res = json.loads(run_ok(["specs", "BORR", "--change", self.cid]))
        graph = load_graph("BORR")
        nodes = {n["id"]: n for n in graph["nodes"]}
        for unit_id in res["units"]:
            self.assertEqual(nodes[unit_id]["type"], "spec_unit")
            targets = [e["to"] for e in graph["edges"] if e["from"] == unit_id and e["relation"] == "traces_to"]
            self.assertEqual(len(targets), 1)
            self.assertEqual(nodes[targets[0]]["type"], "ears_requirement")

    def test_refuses_without_change_brief(self):
        (workspace_path("BORR") / "02_requirements" / self.cid / "project-brief.md").unlink()
        with self.assertRaises(GateRefusal) as caught:
            compile_change_specs("BORR", self.cid)
        self.assertIn("/brief BORR --change CHG-001", caught.exception.next_step)
        self.assertFalse((workspace_path("BORR") / "03_specs" / self.cid).exists())

    def test_refuses_for_unknown_change(self):
        with self.assertRaises(GateRefusal):
            compile_change_specs("BORR", "CHG-009")

    def test_refuses_with_blocking_gaps_open(self):
        changes = read_json(workspace_path("BORR") / "state.json", {})["changes"]
        changes[self.cid]["gap_counts"]["blocking_open"] = 2
        update_state("BORR", changes=changes)
        with self.assertRaises(GateRefusal) as caught:
            compile_change_specs("BORR", self.cid)
        self.assertIn("/resolve-gaps BORR --change CHG-001", caught.exception.next_step)
        self.assertFalse((workspace_path("BORR") / "03_specs" / self.cid).exists())

    def test_refuses_without_unit_rows(self):
        rows = workspace_path("BORR") / "02_requirements" / self.cid / "requirements.md"
        kept = [ln for ln in rows.read_text(encoding="utf-8").splitlines() if "| ADDED |" not in ln and "| MODIFIED |" not in ln]
        rows.write_text("\n".join(kept) + "\n", encoding="utf-8")
        with self.assertRaises(GateRefusal) as caught:
            compile_change_specs("BORR", self.cid)
        self.assertIn("GAP-ACCEPTANCE", caught.exception.next_step)
        self.assertFalse((workspace_path("BORR") / "03_specs" / self.cid).exists())

    def test_rerun_keeps_ids_and_appends_new(self):
        first = json.loads(run_ok(["specs", "BORR", "--change", self.cid]))
        before = {p.stem: p.read_text(encoding="utf-8") for p in units_dir("BORR").glob("*.md")}
        answer("BORR", self.cid, "b.md", EXTRA)
        second = json.loads(run_ok(["specs", "BORR", "--change", self.cid]))
        self.assertEqual(second["units"][:3], first["units"])
        self.assertEqual(second["units"][3], "SPEC-U-004")
        for name, text in before.items():
            self.assertEqual((units_dir("BORR") / f"{name}.md").read_text(encoding="utf-8"), text)
        again = json.loads(run_ok(["specs", "BORR", "--change", self.cid]))
        self.assertEqual(again["units"], second["units"])

    def test_cli_and_mcp_accept_change(self):
        code, out = run_cli(["specs", "BORR", "--change", self.cid])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["change_id"], self.cid)
        code, _ = run_cli(["specs", "BORR", "--change", self.cid, "--release", "r1"])
        self.assertEqual(code, 3)
        captured: list[list[str]] = []
        with patch.object(sentinel_mcp, "run_cli", lambda arguments: captured.append(arguments) or {"exit_code": 0}):
            _tools()["sentinel_specs"](project_id="BORR", change=self.cid)
            _tools()["sentinel_specs"](project_id="BORR")
        self.assertEqual(captured[0], ["specs", "BORR", "--change", self.cid])
        self.assertEqual(captured[1], ["specs", "BORR"])

    def test_plain_specs_in_change_only_workspace_refuses(self):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = cli_main(["specs", "BORR"])
        self.assertEqual(code, 4)
        self.assertIn("--change CHG-001", err.getvalue() + out.getvalue())
        self.assertNotIn("Run /ingest first", err.getvalue() + out.getvalue())
        self.assertFalse((workspace_path("BORR") / "03_specs" / self.cid).exists())

    def test_release_with_change_refused_only_for_specs(self):
        code, _ = run_cli(["specs", "BORR", "--change", self.cid, "--release", "r1"])
        self.assertEqual(code, 3)


class ChangeSpecsWithProject(SnapshotWorkspaceCase):
    @classmethod
    def build_workspace(cls):
        build_matured_workspace("MIX", PROJECT_RAW, gap_acceptance_answer(PROJECT_EARS), backlog=False)
        cid = open_change("MIX")
        cls.cid = cid
        answer("MIX", cid, "a.md", ALL_ANSWERS)
        run_ok(["brief", "MIX", "--change", cid])

    def test_project_units_seeded_before_change_ids_assigned(self):
        project_units = workspace_path("MIX") / "03_specs" / "units"
        before = {p.name: p.read_text(encoding="utf-8") for p in project_units.glob("*.md")}
        self.assertEqual(sorted(before), ["SPEC-U-001.md", "SPEC-U-002.md"])
        self.assertFalse(registry_path("MIX").exists())
        res = json.loads(run_ok(["specs", "MIX", "--change", self.cid]))
        self.assertEqual(res["units"], ["SPEC-U-003", "SPEC-U-004", "SPEC-U-005"])
        issued = json.loads(registry_path("MIX").read_text(encoding="utf-8"))["families"]["SPEC-U"]["issued"]
        self.assertEqual(issued["REQ-EARS-001"], "SPEC-U-001")
        self.assertEqual(issued["REQ-EARS-002"], "SPEC-U-002")
        self.assertEqual({p.name: p.read_text(encoding="utf-8") for p in project_units.glob("*.md")}, before)

    def test_project_specs_after_change_specs_no_collision(self):
        run_ok(["specs", "MIX", "--change", self.cid])
        run_ok(["specs", "MIX"])
        project_units = workspace_path("MIX") / "03_specs" / "units"
        self.assertEqual(sorted(p.stem for p in project_units.glob("*.md")), ["SPEC-U-001", "SPEC-U-002"])
        self.assertEqual(unit_files("MIX", self.cid), ["SPEC-U-003", "SPEC-U-004", "SPEC-U-005"])
        self.assertTrue((workspace_path("MIX") / "03_specs" / "prd.md").is_file())


if __name__ == "__main__":
    unittest.main()
