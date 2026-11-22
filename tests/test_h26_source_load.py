"""IMP-400 (H26 inc 2): /sources --load PATH --role ROLE registers a source with its role."""
from __future__ import annotations

import json
import shutil
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import SnapshotWorkspaceCase, run_cli, run_ok  # noqa: E402

from sentinel import mcp as sentinel_mcp  # noqa: E402
from sentinel.changes import list_changes  # noqa: E402
from sentinel.errors import GateRefusal, InputError  # noqa: E402
from sentinel.sources import _language, load_source, source_log_path, source_manifest_path  # noqa: E402
from sentinel.workspace import read_state, workspace_path  # noqa: E402
from tests.test_mcp_parity import _tools  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"
SAD = FIXTURES / "change_baseline" / "sad-compras.md"


def _rows(project_id: str) -> list[dict]:
    return json.loads(source_manifest_path(project_id).read_text(encoding="utf-8"))["registry"]


def load(project_id: str, path: Path, role: str, change: str | None = None) -> dict:
    """One /sources --load command (each CLI run is its own write session)."""
    argv = ["sources", project_id, "--load", str(path), "--role", role] + (["--change", change] if change else [])
    return json.loads(run_ok(argv))


class SourceLoad(SnapshotWorkspaceCase):
    @classmethod
    def build_workspace(cls):
        shutil.copy(FIXTURES / "change_borrador.md", Path.cwd() / "pedido.md")
        run_ok(["init", "BORR"])
        run_ok(["ingest", "BORR", "--source", "pedido.md", "--change"])
        run_ok(["init", "PROJ"])
        run_ok(["ingest", "PROJ", "--source", "pedido.md"])

    def test_load_baseline_copies_registers_and_indexes(self):
        out = run_ok(["sources", "BORR", "--load", str(SAD), "--role", "linea_de_base", "--change", "CHG-001"])
        result = json.loads(out)
        copy = workspace_path("BORR") / "00_raw" / "06_baseline" / "sad-compras.md"
        self.assertTrue(copy.is_file())
        self.assertFalse(result["in_place"])
        self.assertFalse(result["reused"])
        self.assertIn("linea_de_base", result["message"])
        row = next(r for r in _rows("BORR") if r["id"] == result["source_id"])
        self.assertEqual(row["role"], "linea_de_base")
        self.assertEqual(row["authority"], "built")
        self.assertIn(result["source_id"], list_changes("BORR")["CHG-001"]["sources"])
        log = source_log_path("BORR").read_text(encoding="utf-8")  # the log follows the project language
        self.assertIn("rol: linea_de_base" if _language("BORR") == "es" else "role: linea_de_base", log)

    def test_load_in_place_registers_hand_copied_file(self):
        folder = workspace_path("BORR") / "00_raw" / "02_technology_context"
        folder.mkdir(parents=True, exist_ok=True)
        hand = folder / "sad-a-mano.md"
        shutil.copy(SAD, hand)
        before = sorted(p.name for p in (workspace_path("BORR") / "00_raw").rglob("*") if p.is_file())
        result = load("BORR", hand, "linea_de_base", "CHG-001")
        after = sorted(p.name for p in (workspace_path("BORR") / "00_raw").rglob("*") if p.is_file())
        self.assertTrue(result["in_place"])
        self.assertEqual(before, after)
        self.assertFalse((workspace_path("BORR") / "00_raw" / "06_baseline").exists())
        self.assertIn("02_technology_context/sad-a-mano.md", result["path"])

    def test_load_rejects_harvest_copy(self):
        folder = workspace_path("BORR") / "00_raw" / "02_technology_context" / "harvest"
        folder.mkdir(parents=True, exist_ok=True)
        copy = folder / "harvest.md"
        copy.write_text("# Lectura de Sentinel\n\nAlta de proveedores.\n", encoding="utf-8")
        with self.assertRaises(InputError) as ctx:
            load_source("BORR", copy, "linea_de_base", "CHG-001")
        self.assertIn("lectura de Sentinel", str(ctx.exception))
        code, _ = run_cli(["sources", "BORR", "--load", str(copy), "--role", "linea_de_base", "--change", "CHG-001"])
        self.assertNotEqual(code, 0)

    def test_load_same_content_reuses_row(self):
        first = load("BORR", SAD, "linea_de_base", "CHG-001")
        other = Path.cwd() / "otro-nombre.md"
        shutil.copy(SAD, other)
        second = load("BORR", other, "linea_de_base", "CHG-001")
        self.assertTrue(second["reused"])
        self.assertEqual(first["source_id"], second["source_id"])
        sources = list_changes("BORR")["CHG-001"]["sources"]
        self.assertEqual(sources.count(first["source_id"]), 1)
        self.assertFalse((workspace_path("BORR") / "00_raw" / "06_baseline" / "otro-nombre.md").exists())

    def test_load_in_place_reused_content_attaches_path(self):
        first = load("BORR", SAD, "linea_de_base", "CHG-001")
        folder = workspace_path("BORR") / "00_raw" / "02_technology_context"
        folder.mkdir(parents=True, exist_ok=True)
        hand = folder / "sad-a-mano.md"
        shutil.copy(SAD, hand)
        second = load("BORR", hand, "linea_de_base", "CHG-001")
        self.assertTrue(second["reused"])
        self.assertTrue(second["in_place"])
        self.assertEqual(first["source_id"], second["source_id"])
        row = next(r for r in _rows("BORR") if r["id"] == first["source_id"])
        self.assertTrue(any(p.endswith("02_technology_context/sad-a-mano.md") for p in row["paths"] + row["copies"]))

    def test_harvest_rule_is_the_workspace_folder_only(self):
        other = Path.cwd() / "harvest" / "sad.md"
        other.parent.mkdir()
        shutil.copy(SAD, other)
        self.assertFalse(load("BORR", other, "linea_de_base", "CHG-001")["in_place"])

    def test_load_conflicting_declared_role_refused(self):
        first = load("BORR", SAD, "linea_de_base", "CHG-001")
        with self.assertRaises(InputError) as ctx:
            load_source("BORR", SAD, "plan_previo", "CHG-001")
        message = str(ctx.exception)
        self.assertIn(first["source_id"], message)
        self.assertIn("--id", message)
        self.assertIn("--role", message)

    def test_inferred_role_is_overwritten_by_declared(self):
        # PROJ's /ingest registered the request without a declared role (inferred pedido).
        row = _rows("PROJ")[0]
        self.assertNotIn("role", row)
        result = load("PROJ", Path.cwd() / "pedido.md", "plan_previo")
        self.assertEqual(result["source_id"], row["id"])
        self.assertTrue(result["reused"])
        self.assertEqual(next(r for r in _rows("PROJ") if r["id"] == row["id"])["role"], "plan_previo")

    def test_load_pedido_requires_change(self):
        with self.assertRaises(InputError) as ctx:
            load_source("BORR", FIXTURES / "change_request.md", "pedido")
        self.assertIn("/ingest", str(ctx.exception))
        with self.assertRaises(GateRefusal):
            load_source("BORR", FIXTURES / "change_request.md", "pedido", "CHG-099")

    def test_load_unknown_role_lists_roles(self):
        with self.assertRaises(InputError) as ctx:
            load_source("BORR", SAD, "otro", "CHG-001")
        self.assertIn("linea_de_base", str(ctx.exception))

    def test_role_without_load_or_id_is_input_error(self):
        code, _ = run_cli(["sources", "BORR", "--role", "plan_previo"])
        self.assertNotEqual(code, 0)
        code, _ = run_cli(["sources", "BORR", "--load", str(SAD)])
        self.assertNotEqual(code, 0)

    def test_role_fix_with_id(self):
        first = load("BORR", SAD, "linea_de_base", "CHG-001")
        run_ok(["sources", "BORR", "--id", first["source_id"], "--role", "plan_previo"])
        log = source_log_path("BORR").read_text(encoding="utf-8")
        self.assertIn("rol: plan_previo" if _language("BORR") == "es" else "role: plan_previo", log)
        self.assertNotIn("linea_de_base", log)
        row = next(r for r in _rows("BORR") if r["id"] == first["source_id"])
        self.assertEqual(row["role"], "plan_previo")
        code, _ = run_cli(["sources", "BORR", "--id", first["source_id"], "--role", "otro"])
        self.assertNotEqual(code, 0)

    def test_load_without_change_in_project_workspace(self):
        before = read_state("PROJ").get("changes", {})
        result = load("PROJ", SAD, "linea_de_base")
        self.assertIsNone(result["change_id"])
        row = next(r for r in _rows("PROJ") if r["id"] == result["source_id"])
        self.assertEqual(row["role"], "linea_de_base")
        self.assertEqual(read_state("PROJ").get("changes", {}), before)
        self.assertTrue((workspace_path("PROJ") / "00_raw" / "06_baseline" / "sad-compras.md").is_file())

    def test_mcp_sources_load(self):
        captured: list[list[str]] = []
        with patch.object(sentinel_mcp, "run_cli", lambda arguments: captured.append(arguments) or {"exit_code": 0}):
            _tools()["sentinel_sources"](project_id="P", load="sad.md", role="linea_de_base", change="CHG-001")
        self.assertEqual(
            ["sources", "P", "--load", "sad.md", "--role", "linea_de_base", "--change", "CHG-001"], captured[0]
        )


if __name__ == "__main__":
    unittest.main()
