"""IMP-384: the lens round reads the answer text of a response file, never its form labels."""
from __future__ import annotations

import json
import shutil
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import SnapshotWorkspaceCase, run_ok  # noqa: E402
from sentinel.changes import _lens_evidence, get_change  # noqa: E402
from sentinel.workspace import workspace_path  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"
SCOPE = "\n".join([
    "### GAP-SCOPE",
    "- Respuesta: Sólo el formulario de alta de proveedores.",
    "- Borde:",
    '  - nuevo | pantalla | Botón "Guardar borrador" en el alta de proveedores',
    "  - preservado | proceso | Envío completo del alta",
    "- Owner / fuente: Jefa de Compras",
    "- Evidencia o referencia: Acta de la reunión",
    "- Estado de decisión: confirmado",
    "",
])


class LensEvidence(SnapshotWorkspaceCase):
    @classmethod
    def build_workspace(cls):
        root = Path.cwd()
        shutil.copy(FIXTURES / "change_borrador.md", root / "pedido.md")
        (root / "scope.md").write_text(SCOPE, encoding="utf-8")
        run_ok(["init", "LEV"])
        run_ok(["ingest", "LEV", "--source", "pedido.md", "--change"])
        run_ok(["resolve-gaps", "LEV", "--source", "scope.md", "--change", "CHG-001"])

    def test_labels_are_not_evidence(self):
        text = _lens_evidence(workspace_path("LEV"), get_change("LEV", "CHG-001")).lower()
        for label in ("owner", "fuente", "evidencia", "estado de decisión"):
            self.assertNotIn(label, text)
        self.assertIn("sólo el formulario de alta", text)

    def test_labels_do_not_suppress_delivery_checks(self):
        rows = Path(workspace_path("LEV") / "01_discovery" / "CHG-001" / "gaps.md").read_text(encoding="utf-8")
        for gap in ("GAP-DELIVERY-READINESS", "GAP-QUALITY-HANDOFF"):
            self.assertIn(gap, rows)


if __name__ == "__main__":
    unittest.main()
