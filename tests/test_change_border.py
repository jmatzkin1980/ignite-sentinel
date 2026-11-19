"""IMP-382: /resolve-gaps --change confirms the border from a BA answer and opens the lens round."""
from __future__ import annotations

import json
import shutil
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import SnapshotWorkspaceCase, run_cli, run_ok  # noqa: E402
from test_change_gaps import run_err  # noqa: E402

from sentinel.changes import change_gaps_path, confirm_border, get_change, parse_border  # noqa: E402
from sentinel.errors import InputError  # noqa: E402
from sentinel.gaps import parse_gap_rows  # noqa: E402
from sentinel.workspace import read_state, workspace_path  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"
PROJECT_ONLY = {
    "GAP-PRD-PERSONA-DETAIL", "GAP-PRD-FR-AC", "GAP-PRD-NFR-KPI", "GAP-PRD-GOVERNANCE",
    "GAP-PRD-DEPENDENCIES-ROADMAP", "GAP-DESIGN-PROTOTYPE-INPUT", "GAP-BACKLOG-ENABLERS",
}


def scope_answer(border_lines: list[str] | None, status: str = "confirmado") -> str:
    lines = [
        "### GAP-SCOPE",
        "- Respuesta: Sólo el formulario de alta de proveedores.",
    ]
    if border_lines is not None:
        lines.append("- Borde:")
        lines += [f"  - {line}" for line in border_lines]
    lines += ["- Owner / fuente: Jefa de Compras", f"- Estado de decisión: {status}", ""]
    return "\n".join(lines)


GOOD_BORDER = [
    'nuevo | pantalla | Botón "Guardar borrador" en el alta de proveedores',
    'nuevo | pantalla | Listado "Mis borradores"',
    "adyacente | endpoint | Envío actual del alta de proveedores",
    "adyacente | dato | Tabla de proveedores",
    "preservado | proceso | Envío completo del alta",
]
CITE = "07_changes/00_client_responses/scope.md#GAP-SCOPE"


class ParseBorder(unittest.TestCase):
    def test_parses_the_five_lines(self):
        border = parse_border(scope_answer(GOOD_BORDER), CITE)
        self.assertEqual([b["zone"] for b in border], ["nuevo", "nuevo", "adyacente", "adyacente", "preservado"])
        self.assertEqual(
            border[0],
            {"zone": "nuevo", "type": "pantalla", "name": 'Botón "Guardar borrador" en el alta de proveedores', "cite": CITE},
        )

    def test_accented_integration_is_normalized(self):
        border = parse_border(scope_answer(["adyacente | integración | Padrón fiscal"]), CITE)
        self.assertEqual(border[0]["type"], "integracion")

    def test_bad_type_names_the_line_and_valid_values(self):
        with self.assertRaises(InputError) as caught:
            parse_border(scope_answer(["nuevo | screen | X"]), CITE)
        message = str(caught.exception)
        self.assertIn("nuevo | screen | X", message)
        self.assertIn("pantalla", message)
        self.assertIn("integracion", message)

    def test_bad_zone_and_malformed_line(self):
        with self.assertRaises(InputError) as caught:
            parse_border(scope_answer(["viejo | pantalla | X"]), CITE)
        self.assertIn("viejo", str(caught.exception))
        self.assertIn("preservado", str(caught.exception))
        with self.assertRaises(InputError):
            parse_border(scope_answer(["nuevo | pantalla"]), CITE)

    def test_missing_or_empty_border_is_refused(self):
        with self.assertRaises(InputError):
            parse_border(scope_answer(None), CITE)
        with self.assertRaises(InputError):
            parse_border(scope_answer([]), CITE)


class ChangeBorder(SnapshotWorkspaceCase):
    change_id = "CHG-001"

    @classmethod
    def build_workspace(cls):
        root = Path.cwd()
        shutil.copy(FIXTURES / "change_borrador.md", root / "pedido.md")
        (root / "scope.md").write_text(scope_answer(GOOD_BORDER), encoding="utf-8")
        (root / "scope_backend.md").write_text(
            scope_answer(["nuevo | endpoint | Alta de borrador", "adyacente | dato | Tabla de proveedores"]), encoding="utf-8"
        )
        (root / "scope_bad.md").write_text(scope_answer(["nuevo | screen | X"]), encoding="utf-8")
        (root / "scope_noborder.md").write_text(scope_answer(None), encoding="utf-8")
        (root / "scope_pending.md").write_text(scope_answer(GOOD_BORDER, "pendiente"), encoding="utf-8")
        (root / "project_answers.md").write_text(
            "### GAP-ACCEPTANCE\n- Answer: When the analyst saves a draft, the system shall keep it.\n"
            "- Owner / source: Compras\n- Evidence or reference: nota\n- Decision status: confirmed\n",
            encoding="utf-8",
        )
        run_ok(["init", "BORR"])
        run_ok(["ingest", "BORR", "--source", "pedido.md", "--change"])

    @property
    def base(self) -> Path:
        return workspace_path("BORR")

    def change_gaps_text(self) -> str:
        return change_gaps_path(self.base, self.change_id).read_text(encoding="utf-8")

    def change_rows(self):
        return parse_gap_rows(self.change_gaps_text())

    def resolve(self, name: str) -> dict:
        return json.loads(run_ok(["resolve-gaps", "BORR", "--source", name, "--change", self.change_id]))

    def workspace_files(self) -> list[str]:
        return sorted(p.relative_to(self.base).as_posix() for p in self.base.rglob("*") if p.is_file())

    def test_confirmed_border_opens_the_lens_round(self):
        out = self.resolve("scope.md")
        self.assertEqual(out["round"], "lenses")
        self.assertEqual(out["change_id"], self.change_id)
        self.assertEqual([b["zone"] for b in out["border"]], ["nuevo", "nuevo", "adyacente", "adyacente", "preservado"])
        ids = {r["id"] for r in self.change_rows()}
        self.assertIn("GAP-DESIGN-FLOW", ids)
        self.assertFalse(ids & PROJECT_ONLY)
        change = get_change("BORR", self.change_id)
        self.assertEqual(change["round"], "lenses")
        self.assertTrue(change["border_confirmed_at"])
        self.assertEqual(change["responses"], ["07_changes/00_client_responses/scope.md"])
        self.assertEqual(change["border"][0]["cite"], CITE)

    def test_existing_rows_keep_their_status_after_the_lens_round_opens(self):
        before = {r["id"]: r["status"] for r in self.change_rows()}
        self.resolve("scope.md")
        after = {r["id"]: r["status"] for r in self.change_rows()}
        self.assertEqual(after["GAP-SCOPE"], "CLOSED")
        for gap_id, status in before.items():
            if gap_id != "GAP-SCOPE":
                self.assertEqual(after[gap_id], status)

    def test_backend_only_border_skips_design(self):
        self.resolve("scope_backend.md")
        ids = {r["id"] for r in self.change_rows()}
        self.assertFalse(ids & {"GAP-DESIGN-FLOW", "GAP-DESIGN-STATES", "GAP-FRONTEND-SURFACE"})

    def assert_rejected(self, name: str, expected: tuple[str, ...]):
        state_before = json.dumps(read_state("BORR"), sort_keys=True)
        gaps_before = self.change_gaps_text()
        files_before = self.workspace_files()
        code, err = run_err(["resolve-gaps", "BORR", "--source", name, "--change", self.change_id])
        self.assertNotEqual(code, 0)
        for text in expected:
            self.assertIn(text, err)
        self.assertEqual(gaps_before, self.change_gaps_text())
        self.assertEqual(get_change("BORR", self.change_id)["round"], "scope")
        self.assertEqual(state_before, json.dumps(read_state("BORR"), sort_keys=True))
        self.assertEqual(files_before, self.workspace_files())

    def test_bad_border_line_rejects_everything(self):
        self.assert_rejected("scope_bad.md", ("screen", "pantalla"))

    def test_missing_border_rejects_everything(self):
        self.assert_rejected("scope_noborder.md", ("Borde",))

    def test_pending_scope_answer_needs_no_border(self):
        out = self.resolve("scope_pending.md")
        self.assertEqual(out["round"], "scope")
        self.assertEqual(out["border"], [])

    def test_project_gap_ids_are_not_applied(self):
        out = self.resolve("project_answers.md")
        self.assertTrue(any("GAP-ACCEPTANCE" in f for f in out["closure_findings"]))
        self.assertEqual(out["round"], "scope")

    def test_project_state_and_files_are_untouched(self):
        self.resolve("scope.md")
        state = read_state("BORR")
        self.assertFalse(state.get("gap_counts"))
        self.assertNotIn("last_gap_resolution_id", state)
        self.assertFalse((self.base / "01_discovery" / "gaps.md").exists())
        self.assertFalse((self.base / "01_discovery" / "gap_elicitation.json").exists())
        self.assertFalse((self.base / "01_discovery" / "decisions.md").exists())
        self.assertTrue((self.base / "01_discovery" / self.change_id / "gap_elicitation.json").exists())

    def test_change_guide_shows_the_border_format_without_an_example_answer(self):
        text = self.change_gaps_text()
        self.assertIn("zona | tipo | nombre", text)
        self.assertEqual(text.count("### GAP-SCOPE"), 1)

    def test_confirm_border_sets_round_and_timestamp(self):
        confirm_border("BORR", self.change_id, [{"zone": "nuevo", "type": "dato", "name": "X", "cite": CITE}])
        change = get_change("BORR", self.change_id)
        self.assertEqual(change["round"], "lenses")
        self.assertEqual(change["border"][0]["type"], "dato")
        self.assertTrue(change["border_confirmed_at"])

    def test_unknown_change_is_refused_before_writing(self):
        files_before = self.workspace_files()
        code, _ = run_cli(["resolve-gaps", "BORR", "--source", "scope.md", "--change", "CHG-999"])
        self.assertNotEqual(code, 0)
        self.assertEqual(files_before, self.workspace_files())


if __name__ == "__main__":
    unittest.main()
