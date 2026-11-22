from __future__ import annotations

import json
import shutil
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import SnapshotWorkspaceCase, run_ok  # noqa: E402

from sentinel.changes import list_changes  # noqa: E402
from sentinel.source_registry import SourceRegistryError, row_role, set_role  # noqa: E402
from sentinel.sources import source_manifest_path, source_log_path  # noqa: E402
from sentinel.workspace import workspace_path  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"


class RowRole(unittest.TestCase):
    def test_row_role_inference(self):
        self.assertIsNone(row_role({"kind": "technology_context", "events": [{"via": "harvested"}]}))
        self.assertEqual(row_role({"kind": "external", "events": [{"via": "change_ingested"}]}), "pedido")
        self.assertEqual(row_role({"kind": "external", "events": [{"via": "initial_ingested"}]}), "pedido")
        self.assertEqual(row_role({"kind": "technology_context", "events": [{"via": "synced"}]}), "linea_de_base")
        self.assertEqual(row_role({"kind": "baseline", "events": []}), "linea_de_base")
        self.assertEqual(row_role({"kind": "prior_plan", "events": []}), "plan_previo")
        self.assertEqual(row_role({"kind": "design_context", "events": [{"via": "synced"}]}), "diseno_nuevo")
        self.assertEqual(row_role({"kind": "new_design", "events": []}), "diseno_nuevo")
        self.assertIsNone(row_role({"kind": "external", "events": [{"via": "synced"}]}))
        self.assertEqual(row_role({"kind": "design_context", "role": "plan_previo", "events": []}), "plan_previo")

    def test_set_role_rejects_unknown(self):
        row: dict = {}
        with self.assertRaises(SourceRegistryError) as ctx:
            set_role(row, "otro")
        self.assertIn("linea_de_base", str(ctx.exception))
        self.assertNotIn("role", row)
        set_role(row, "pedido")
        self.assertEqual(row["role"], "pedido")


class IngestRoles(SnapshotWorkspaceCase):
    @classmethod
    def build_workspace(cls):
        shutil.copy(FIXTURES / "change_borrador.md", Path.cwd() / "pedido.md")
        run_ok(["init", "BORR"])
        run_ok(["ingest", "BORR", "--source", "pedido.md", "--change"])
        run_ok(["init", "PROJ"])
        run_ok(["ingest", "PROJ", "--source", "pedido.md"])

    def test_ingest_change_declares_pedido(self):
        manifest = json.loads(source_manifest_path("BORR").read_text(encoding="utf-8"))
        rows = [r for r in manifest["registry"] if "pedido.md" in " ".join(r["paths"])]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["role"], "pedido")
        self.assertEqual(list_changes("BORR")["CHG-001"]["sources"], [rows[0]["id"]])
        self.assertIn("role: pedido", source_log_path("BORR").read_text(encoding="utf-8").replace("rol:", "role:"))

    def test_project_ingest_rows_have_no_role_key(self):
        manifest = json.loads(source_manifest_path("PROJ").read_text(encoding="utf-8"))
        self.assertTrue(manifest["registry"])
        self.assertTrue(all("role" not in row for row in manifest["registry"]))
        log = source_log_path("PROJ").read_text(encoding="utf-8")
        self.assertNotIn("rol:", log)
        self.assertNotIn("role:", log)


if __name__ == "__main__":
    unittest.main()
