"""IMP-382: the change path end to end, and the workspace it leaves passes /doctor and /status."""
from __future__ import annotations

import json
import shutil
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import SnapshotWorkspaceCase, run_ok  # noqa: E402
from sentinel.changes import get_change  # noqa: E402
from sentinel.workspace import read_state  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"
SCOPE_ANSWER = "\n".join([
    "### GAP-SCOPE",
    "- Respuesta: Sólo el formulario de alta de proveedores.",
    "- Borde:",
    '  - nuevo | pantalla | Botón "Guardar borrador" en el alta de proveedores',
    '  - nuevo | pantalla | Listado "Mis borradores"',
    "  - adyacente | endpoint | Envío actual del alta de proveedores",
    "  - adyacente | dato | Tabla de proveedores",
    "  - preservado | proceso | Envío completo del alta",
    "- Owner / fuente: Jefa de Compras",
    "- Estado de decisión: confirmado",
    "",
])


SCOPE_TOTAL, LENS_TOTAL, BLOCKING = 4, 18, 3


class ChangeFlow(SnapshotWorkspaceCase):
    @classmethod
    def build_workspace(cls):
        root = Path.cwd()
        shutil.copy(FIXTURES / "change_borrador.md", root / "pedido.md")
        (root / "scope.md").write_text(SCOPE_ANSWER, encoding="utf-8")
        run_ok(["init", "BORR"])

    def test_borrador_end_to_end(self):
        out = json.loads(run_ok(["ingest", "BORR", "--source", "pedido.md", "--change"]))
        cid = out["change_id"]
        self.assertEqual(out["round"], "scope")
        self.assertEqual(out["gap_counts"]["total"], SCOPE_TOTAL)
        run_ok(["resolve-gaps", "BORR", "--source", "scope.md", "--change", cid])
        change = get_change("BORR", cid)
        self.assertEqual(change["round"], "lenses")
        counts = change["gap_counts"]
        self.assertEqual(counts["total"], LENS_TOTAL)
        self.assertEqual(counts["blocking_open"], BLOCKING)
        # The same note on the project path asks more.
        shutil.copy(FIXTURES / "change_borrador.md", Path.cwd() / "proyecto.md")
        run_ok(["init", "PROJ"])
        run_ok(["ingest", "PROJ", "--source", "proyecto.md"])
        project_total = read_state("PROJ")["gap_counts"]["total"]
        self.assertEqual(project_total, 27)
        self.assertGreater(project_total, counts["total"])
        self.assertIn(json.loads(run_ok(["doctor"]))["verdict"], {"PASS", "WARN"})
        status = json.loads(run_ok(["status", "BORR"]))
        self.assertEqual(status["project_id"], "BORR")


if __name__ == "__main__":
    unittest.main()
