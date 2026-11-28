"""IMP-384: /harvest --change opens the harvest's gaps in the change, never in the project."""
from __future__ import annotations

import io
import json
import shutil
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import SnapshotWorkspaceCase, place_harvest_docs, run_ok  # noqa: E402

from sentinel.changes import change_gaps_path, list_changes  # noqa: E402
from sentinel.cli import main  # noqa: E402
from sentinel.gaps import parse_gap_rows  # noqa: E402
from sentinel.workspace import workspace_path  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"

HARVEST = """# Harvest

## B0 Inventory
- repo: compras-api \u2014 services/compras
- doc: manual-compras \u2014 00_raw/01_business_context/manual-compras.md

## B1 Architecture
- [HECHO compras-api:src/app.py] La API es una app Flask.
- [DIVERGENCIA compras-api:README.md] El README dice v2; el codigo sirve rutas v1.

## B6 Pantallas
- [HECHO manual-compras:manual-compras.md] El alta de proveedores tiene cuatro pasos.
"""

BAD = HARVEST + "\n- [HECHO fantasma:x.py] Un repo que no existe.\n"


def run_err(argv: list[str]) -> tuple[int, str]:
    err = io.StringIO()
    with redirect_stdout(io.StringIO()), redirect_stderr(err):
        code = main(list(argv))
    return code, err.getvalue()


class ChangeHarvest(SnapshotWorkspaceCase):
    change_id = "CHG-001"

    @classmethod
    def build_workspace(cls):
        shutil.copy(FIXTURES / "change_borrador.md", Path.cwd() / "pedido.md")
        run_ok(["init", "BORR"])
        run_ok(["ingest", "BORR", "--source", "pedido.md", "--change"])

    @property
    def base(self) -> Path:
        return workspace_path("BORR")

    def write(self, name: str, text: str) -> str:
        place_harvest_docs("BORR", text)  # B-37: the documents a harvest lists are in the workspace
        Path(name).write_text(text, encoding="utf-8")
        return name

    def test_harvest_gaps_go_to_the_change(self):
        out = json.loads(run_ok(["harvest", "BORR", "--source", self.write("h.md", HARVEST), "--change", self.change_id]))
        self.assertEqual(out["change_id"], self.change_id)
        self.assertEqual(len(out["gaps_opened"]), 1)
        rows = parse_gap_rows(change_gaps_path(self.base, self.change_id).read_text(encoding="utf-8"))
        self.assertIn(out["gaps_opened"][0], {row["id"] for row in rows})
        self.assertTrue(out["gaps_opened"][0].startswith("GAP-HRV-"))
        self.assertFalse((self.base / "01_discovery" / "gaps.md").exists())
        self.assertTrue((self.base / "01_discovery" / self.change_id / "gap_elicitation.json").exists())
        self.assertIn("gap_counts", list_changes("BORR")[self.change_id])
        record = json.loads((self.base / "01_discovery" / "harvest.json").read_text(encoding="utf-8"))
        self.assertEqual(record["docs"], ["manual-compras"])

    def test_change_harvest_does_not_duplicate_gaps_on_rerun(self):
        src = self.write("h.md", HARVEST)
        run_ok(["harvest", "BORR", "--source", src, "--change", self.change_id])
        out = json.loads(run_ok(["harvest", "BORR", "--source", src, "--change", self.change_id]))
        self.assertEqual(out["gaps_opened"], [])

    def test_change_only_workspace_refuses_plain_harvest(self):
        code, err = run_err(["harvest", "BORR", "--source", self.write("h.md", HARVEST)])
        self.assertNotEqual(code, 0)
        self.assertIn(f"--change {self.change_id}", err)
        self.assertFalse((self.base / "01_discovery" / "harvest.json").exists())
        self.assertFalse((self.base / "00_raw" / "02_technology_context" / "harvest").exists())

    def test_change_only_refusal_follows_the_project_language(self):
        state_file = self.base / "state.json"
        original = state_file.read_text(encoding="utf-8")
        try:
            for language, expected in (("es", "sólo tiene cambios: los gaps del harvest necesitan un cambio"),
                                       ("en", "only has changes: the harvest gaps need a change")):
                state = json.loads(original)
                state["project_language"] = language
                state_file.write_text(json.dumps(state), encoding="utf-8")
                code, err = run_err(["harvest", "BORR", "--source", self.write("h.md", HARVEST)])
                self.assertNotEqual(code, 0)
                self.assertIn(expected, err)
        finally:
            state_file.write_text(original, encoding="utf-8")

    def test_harvest_gaps_use_the_change_language_not_the_project_language(self):
        state_file = self.base / "state.json"
        original = state_file.read_text(encoding="utf-8")
        try:
            state = json.loads(original)
            state["project_language"] = "en"
            state_file.write_text(json.dumps(state), encoding="utf-8")
            self.assertEqual(list_changes("BORR")[self.change_id].get("language"), "es")
            text = HARVEST + "\n## B2 Datos\n- [FUERA DEL CÓDIGO owners] Quién es dueño de la integración de pagos.\n"
            out = json.loads(run_ok(["harvest", "BORR", "--source", self.write("h.md", text), "--change", self.change_id]))
            self.assertIn("docs", out)
            gaps = change_gaps_path(self.base, self.change_id).read_text(encoding="utf-8")
            self.assertIn("¿Quién confirma: ", gaps)
            self.assertNotIn("Who confirms:", gaps)
        finally:
            state_file.write_text(original, encoding="utf-8")

    def test_repo_only_harvest_writes_no_docs_key(self):
        text = "## B0 Inventory\n- repo: compras-api — services/compras\n\n## B1 A\n- [HECHO compras-api:src/app.py] Flask.\n"
        run_ok(["harvest", "BORR", "--source", self.write("h.md", text), "--change", self.change_id])
        record = json.loads((self.base / "01_discovery" / "harvest.json").read_text(encoding="utf-8"))
        self.assertNotIn("docs", record)

    def test_invalid_block_with_change_writes_nothing(self):
        before = (self.base / "state.json").read_text(encoding="utf-8")
        gaps_before = change_gaps_path(self.base, self.change_id).read_text(encoding="utf-8")
        code, err = run_err(["harvest", "BORR", "--source", self.write("h.md", BAD), "--change", self.change_id])
        self.assertNotEqual(code, 0)
        self.assertIn("fantasma", err)
        self.assertFalse((self.base / "01_discovery" / "harvest.json").exists())
        self.assertFalse((self.base / "00_raw" / "02_technology_context" / "harvest").exists())
        self.assertEqual((self.base / "state.json").read_text(encoding="utf-8"), before)
        self.assertEqual(change_gaps_path(self.base, self.change_id).read_text(encoding="utf-8"), gaps_before)

    def test_unknown_change_is_refused(self):
        code, err = run_err(["harvest", "BORR", "--source", self.write("h.md", HARVEST), "--change", "CHG-999"])
        self.assertNotEqual(code, 0)
        self.assertIn("CHG-999 no es un cambio abierto de BORR", err)
        self.assertFalse((self.base / "01_discovery" / "harvest.json").exists())


class McpHarvestChange(unittest.TestCase):
    def _argv(self, **kwargs):
        from unittest.mock import patch

        from sentinel import mcp as sentinel_mcp
        from tests.test_mcp_parity import _tools

        captured: list[list[str]] = []
        with patch.object(sentinel_mcp, "run_cli", lambda arguments: captured.append(arguments) or {"exit_code": 0}):
            _tools()["sentinel_harvest"](project_id="P", source="h.md", **kwargs)
        return captured[0]

    def test_change_is_forwarded(self):
        self.assertEqual(["harvest", "P", "--source", "h.md", "--change", "CHG-001"], self._argv(change="CHG-001"))

    def test_without_change_no_flag(self):
        self.assertEqual(["harvest", "P", "--source", "h.md"], self._argv())


if __name__ == "__main__":
    unittest.main()
