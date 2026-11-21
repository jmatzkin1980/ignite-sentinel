"""IMP-388: confirmed EARS answers of a change carry a BA-declared Delta and become REQ-EARS rows of the change."""
from __future__ import annotations

import json
import shutil
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import SnapshotWorkspaceCase, run_ok  # noqa: E402
from sentinel.change_requirements import (  # noqa: E402
    change_requirements_path, load_change_ears, next_ears_index, parse_delta, propose_delta,
)
from sentinel.changes import change_gaps_path  # noqa: E402
from sentinel.gaps import parse_gap_rows  # noqa: E402
from sentinel.workspace import workspace_path  # noqa: E402
from test_change_flow import SCOPE_ANSWER  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"
EARS_TWO = ("Cuando el comprador guarda el alta incompleta, el sistema debe conservar los datos cargados. "
            "Cuando el comprador abre la lista de pendientes, el sistema debe listar sus altas incompletas.")


def acceptance(answer: str, delta: str | None) -> str:
    lines = ["### GAP-ACCEPTANCE", f"- Respuesta: {answer}", "- Owner / fuente: Jefa de Compras"]
    if delta is not None:
        lines.append(f"- Delta: {delta}")
    lines.append("- Estado de decisión: confirmado")
    return "\n".join(lines) + "\n"


def gap_status(project: str, cid: str, gap_id: str) -> str:
    rows = parse_gap_rows(change_gaps_path(workspace_path(project), cid).read_text(encoding="utf-8"))
    return next(r["status"].strip("`").upper() for r in rows if r["id"] == gap_id)


class ChangeRequirements(SnapshotWorkspaceCase):
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
        self.cid = next(iter(json.loads(run_ok(["status", "BORR"])).get("changes", {"CHG-001": 0})), "CHG-001")

    def resolve(self, name: str, text: str) -> dict:
        Path(name).write_text(text, encoding="utf-8")
        return json.loads(run_ok(["resolve-gaps", "BORR", "--source", name, "--change", self.cid]))

    def rows_path(self) -> Path:
        return change_requirements_path(workspace_path("BORR"), self.cid)

    def test_parse_delta_accepts_the_four_values_case_insensitive(self):
        self.assertEqual(parse_delta("added"), "ADDED")
        self.assertEqual(parse_delta(" Modified "), "MODIFIED")
        self.assertEqual(parse_delta("removed"), "REMOVED")
        self.assertEqual(parse_delta("unchanged"), "UNCHANGED")
        for bad in ("changed", "CAMBIA", "", None):
            self.assertIsNone(parse_delta(bad))

    def test_propose_delta(self):
        self.assertEqual(propose_delta("Cuando falla el envío, el sistema debe continuar validando el alta."), "UNCHANGED")
        self.assertEqual(propose_delta("Cuando el comprador guarda, el sistema debe guardar el borrador."), "ADDED")

    def test_confirmed_ears_answer_with_delta_writes_change_rows(self):
        res = self.resolve("a.md", acceptance(EARS_TWO, "added"))
        self.assertIn("GAP-ACCEPTANCE", res["closed"])
        self.assertEqual(gap_status("BORR", self.cid, "GAP-ACCEPTANCE"), "CLOSED")
        rows = load_change_ears("BORR", self.cid)
        self.assertEqual(len(rows), 2)
        self.assertEqual({r["delta"] for r in rows}, {"ADDED"})
        self.assertEqual({r["source"] for r in rows}, {f"`GAP-ACCEPTANCE` / `{self.cid}`"})
        self.assertEqual(res["ears_rows"], [r["id"] for r in rows])
        self.assertEqual(res["delta_findings"], [])
        self.assertTrue(self.rows_path().read_text(encoding="utf-8").startswith(f"# Requisitos del cambio {self.cid}"))

    def test_ears_answer_without_delta_stays_open_with_proposal(self):
        res = self.resolve("a.md", acceptance(EARS_TWO, None))
        self.assertNotIn("GAP-ACCEPTANCE", res["closed"])
        self.assertNotEqual(gap_status("BORR", self.cid, "GAP-ACCEPTANCE"), "CLOSED")
        self.assertFalse(self.rows_path().exists())
        self.assertEqual(res["ears_rows"], [])
        self.assertEqual(res["delta_findings"][0]["gap"], "GAP-ACCEPTANCE")
        self.assertEqual(res["delta_findings"][0]["proposed"], "ADDED")

    def test_invalid_delta_is_treated_as_missing(self):
        res = self.resolve("a.md", acceptance(EARS_TWO, "changed"))
        self.assertNotIn("GAP-ACCEPTANCE", res["closed"])
        self.assertFalse(self.rows_path().exists())
        note = res["delta_findings"][0]["note"]
        for value in ("ADDED", "MODIFIED", "REMOVED", "UNCHANGED"):
            self.assertIn(value, note)

    def test_reapplying_the_same_answers_adds_no_rows(self):
        self.resolve("a.md", acceptance(EARS_TWO, "ADDED"))
        res = self.resolve("b.md", acceptance(EARS_TWO, "ADDED"))
        self.assertEqual(res["ears_rows"], [])
        self.assertEqual(len(load_change_ears("BORR", self.cid)), 2)

    def test_prose_answer_closes_without_rows_or_delta(self):
        prose = ("### GAP-OBJECTIVE\n- Respuesta: Permitir que Compras guarde el alta incompleta y la retome después.\n"
                 "- Owner / fuente: Jefa de Compras\n- Estado de decisión: confirmado\n")
        res = self.resolve("a.md", prose)
        self.assertIn("GAP-OBJECTIVE", res["closed"])
        self.assertEqual(res["delta_findings"], [])
        self.assertEqual(res["ears_rows"], [])
        self.assertFalse(self.rows_path().exists())

    def test_ears_ids_continue_after_the_project_rows(self):
        req = workspace_path("BORR") / "02_requirements" / "requirements.md"
        req.parent.mkdir(parents=True, exist_ok=True)
        with req.open("a", encoding="utf-8") as handle:
            handle.write("\n| REQ-EARS-001 | event | x | `GAP-A` / `CHG-X` |\n| REQ-EARS-002 | event | y | `GAP-B` / `CHG-X` |\n")
        self.assertEqual(next_ears_index(workspace_path("BORR")), 3)
        res = self.resolve("a.md", acceptance(EARS_TWO, "ADDED"))
        self.assertEqual(res["ears_rows"], ["REQ-EARS-003", "REQ-EARS-004"])

    def test_project_path_ignores_delta_field(self):
        run_ok(["init", "PROJ"])
        shutil.copy(FIXTURES / "change_borrador.md", Path("proyecto.md"))
        run_ok(["ingest", "PROJ", "--source", "proyecto.md"])
        Path("p.md").write_text(acceptance(EARS_TWO, "changed"), encoding="utf-8")
        res = json.loads(run_ok(["resolve-gaps", "PROJ", "--source", "p.md"]))
        self.assertIn("GAP-ACCEPTANCE", res["closed"])
        self.assertNotIn("delta_findings", res)
        folder = workspace_path("PROJ") / "02_requirements"
        self.assertFalse(list(folder.glob("CHG-*")))
        text = (folder / "requirements.md").read_text(encoding="utf-8")
        self.assertIn("| ID | Pattern | Statement | Source |", text)
        self.assertNotIn("Delta", text)


if __name__ == "__main__":
    unittest.main()
