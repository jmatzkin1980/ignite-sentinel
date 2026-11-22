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
    lines.append("- Superficie: Tabla de proveedores")
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

    def test_delta_correction_updates_rows_in_place_with_the_same_ids(self):
        self.resolve("a.md", acceptance(EARS_TWO, "ADDED"))
        before = [r["id"] for r in load_change_ears("BORR", self.cid)]
        res = self.resolve("b.md", acceptance(EARS_TWO, "MODIFIED"))
        rows = load_change_ears("BORR", self.cid)
        self.assertEqual([r["id"] for r in rows], before)
        self.assertEqual({r["delta"] for r in rows}, {"MODIFIED"})
        self.assertEqual(res["delta_updated"], before)
        self.assertEqual(res["ears_rows"], [])
        self.assertEqual(res["superseded_rows"], [])

    def test_rewording_supersedes_the_old_row_and_never_reuses_its_id(self):
        self.resolve("a.md", acceptance(EARS_TWO, "ADDED"))
        first, second = load_change_ears("BORR", self.cid)
        reworded = EARS_TWO.replace("conservar los datos cargados", "conservar los datos ingresados")
        res = self.resolve("b.md", acceptance(reworded, "ADDED"))
        self.assertEqual(res["superseded_rows"], [first["id"]])
        self.assertEqual(res["ears_rows"], ["REQ-EARS-003"])
        rows = load_change_ears("BORR", self.cid)
        self.assertEqual([r["id"] for r in rows], [second["id"], "REQ-EARS-003"])
        text = self.rows_path().read_text(encoding="utf-8")
        self.assertIn("## Requisitos reemplazados", text)
        head, _, tail = text.partition("## Requisitos reemplazados")
        self.assertNotIn(first["id"], head)
        self.assertIn(first["id"], tail)
        self.assertEqual(next_ears_index(workspace_path("BORR")), 4)
        later = self.resolve("c.md", acceptance(reworded + " Cuando el comprador cierra sesión, el sistema debe liberar el alta.", "ADDED"))
        self.assertEqual(later["ears_rows"], ["REQ-EARS-004"])
        self.assertEqual(len(load_change_ears("BORR", self.cid)), 3)

    def test_scope_answer_with_ears_wording_needs_no_delta_and_makes_no_row(self):
        from sentinel.gap_resolution import ears_statements

        scope = SCOPE_ANSWER.replace(
            "Respuesta: ", "Respuesta: Cuando Compras abre el alta, el sistema debe limitarse al formulario de proveedores. ", 1)
        self.assertTrue(ears_statements("Cuando Compras abre el alta, el sistema debe limitarse al formulario de proveedores."))
        res = self.resolve("s.md", scope)
        self.assertIn("GAP-SCOPE", res["closed"])
        self.assertEqual(res["delta_findings"], [])
        self.assertEqual(res["ears_rows"], [])
        self.assertFalse(self.rows_path().exists())

    def test_propose_delta_unchanged_for_keep_still_and_mantener(self):
        for text in ("the system shall keep validating the data", "the system shall still validate", "el sistema debe mantener la validación",
                     "el sistema debe mantiene la validación"):
            self.assertEqual(propose_delta(text), "UNCHANGED", text)

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

    def test_project_ears_ids_skip_change_ids(self):
        run_ok(["init", "PROJ"])
        shutil.copy(FIXTURES / "change_borrador.md", Path("proyecto.md"))
        run_ok(["ingest", "PROJ", "--source", "proyecto.md"])
        folder = workspace_path("PROJ") / "02_requirements"
        with (folder / "requirements.md").open("a", encoding="utf-8") as handle:
            handle.write("\n| REQ-EARS-001 | event | x | `GAP-A` / `CHG-X` |\n")
        change_file = folder / "CHG-001" / "requirements.md"
        change_file.parent.mkdir(parents=True)
        change_file.write_text("| REQ-EARS-002 | event | y | `GAP-B` |\n| REQ-EARS-003 | event | z | `GAP-C` |\n", encoding="utf-8")
        one = ("Cuando el comprador guarda el alta incompleta, el sistema debe conservar los datos cargados.")
        Path("p.md").write_text(acceptance(one, None), encoding="utf-8")
        res = json.loads(run_ok(["resolve-gaps", "PROJ", "--source", "p.md"]))
        self.assertIn("GAP-ACCEPTANCE", res["closed"])
        text = (folder / "requirements.md").read_text(encoding="utf-8")
        self.assertIn("| REQ-EARS-004 |", text)
        self.assertNotIn("| REQ-EARS-002 |", text)


if __name__ == "__main__":
    unittest.main()
