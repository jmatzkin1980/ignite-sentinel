"""IMP-402 (H26 inc 3) task 5: extraction coverage and preserved surfaces in /status --change."""
from __future__ import annotations

import json
import shutil
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import run_ok  # noqa: E402
from test_h26_extract_proposals import CID, EXAMPLE, FIXTURES, PID, ProposalsCase, block  # noqa: E402

from sentinel.changes import list_changes  # noqa: E402
from sentinel.core.io import forget_read_snapshots  # noqa: E402
from sentinel.extraction.confirm import confirm_item, confirm_proposals  # noqa: E402
from sentinel.extraction.coverage import extraction_coverage, extraction_fingerprint, preserved_coverage  # noqa: E402
from sentinel.extraction.inventory import build_inventory, load_inventory  # noqa: E402
from sentinel.extraction.proposals import record_proposals  # noqa: E402
from sentinel.workspace import update_state, workspace_path  # noqa: E402

PRESERVED_QUOTE = '- Cita: "sigue habilitándose en el acto, como hoy"'
PRESERVED_STATEMENT = (
    "- Enunciado: Cuando el analista guarda un alta con monto menor o igual al umbral, "
    "el sistema debe habilitarla en el acto."
)


class Coverage(ProposalsCase):
    def setUp(self):
        super().setUp()
        forget_read_snapshots()
        record_proposals(PID, CID, EXAMPLE)

    def status(self, project: str = PID) -> dict:
        return json.loads(run_ok(["status", project, "--change", CID]))

    def test_coverage_counts_by_kind(self):
        confirm_proposals(PID, CID, "all")
        cov = extraction_coverage(PID, CID)
        self.assertEqual(
            (cov["state"], cov["total"], cov["covered"], cov["proposed"], cov["flagged"], cov["pending"]),
            ("current", 22, 4, 1, 1, 17),
        )
        self.assertEqual(cov["by_kind"]["rule"], {"total": 6, "covered": 2})
        self.assertTrue(cov["text"].startswith("4 de 22 (Reglas 2 de 6"), cov["text"])
        self.assertFalse(cov["complete"])
        self.assertEqual(cov["stale_items"], [])

    def test_stale_item_stops_counting(self):
        confirm_proposals(PID, CID, "all")
        base = workspace_path(PID)
        inventory = load_inventory(base, CID)
        path = Path(inventory["sources"][0]["path"])
        path = path if path.is_absolute() else Path.cwd() / path
        text = path.read_text(encoding="utf-8")
        self.assertIn("requiere aprobación de la jefa de Compras", text)
        path.write_text(text.replace("requiere aprobación de la jefa de Compras", "exige la aprobación de la jefa de Compras"),
                        encoding="utf-8")
        build_inventory(PID, CID)
        cov = extraction_coverage(PID, CID)
        self.assertIn("RN-02", cov["stale_items"])
        self.assertEqual(cov["covered"], 3)

    def test_english_text(self):
        confirm_proposals(PID, CID, "all")
        changes = {key: dict(value) for key, value in list_changes(PID).items()}
        changes[CID]["language"] = "en"
        update_state(PID, changes=changes)
        cov = extraction_coverage(PID, CID)
        self.assertTrue(cov["text"].startswith("4 of 22 (Rules 2 of 6"), cov["text"])

    def test_preserved_missing_then_covered(self):
        self.assertEqual(preserved_coverage(PID, CID)["missing"], ["Alta de monto bajo", "Validación de CUIT"])
        self.assertEqual(preserved_coverage(PID, CID)["surfaces"], ["Alta de monto bajo", "Validación de CUIT"])
        path = Path.cwd() / "preserved.md"
        path.write_text(block(
            "SEC-se-preserva", "- Tratamiento: requisito", PRESERVED_QUOTE, PRESERVED_STATEMENT,
            "  - Delta: UNCHANGED", "  - Superficie: Alta de monto bajo",
        ), encoding="utf-8")
        result = record_proposals(PID, CID, path)
        self.assertEqual(result["recorded"], ["SEC-se-preserva"], result)
        self.assertEqual(confirm_item(PID, CID, "SEC-se-preserva")["confirmed"], ["SEC-se-preserva"])
        cov = preserved_coverage(PID, CID)
        self.assertEqual(cov["missing"], ["Validación de CUIT"])
        self.assertEqual(len(cov["rows"]["Alta de monto bajo"]), 1)
        self.assertFalse(cov["complete"])

    def test_status_change_shows_blocks_and_warnings(self):
        confirm_proposals(PID, CID, "all")
        data = self.status()
        self.assertEqual(data["extraction"]["covered"], 4)
        self.assertEqual(data["preserved"]["missing"], ["Alta de monto bajo", "Validación de CUIT"])
        triggers = {w["trigger"]: w["message"] for w in data["warnings"]}
        self.assertIn("extraction_incomplete", triggers)
        self.assertIn("4 de 22", triggers["extraction_incomplete"])
        self.assertIn("preserved_missing", triggers)
        self.assertIn("Alta de monto bajo, Validación de CUIT", triggers["preserved_missing"])
        self.assertNotIn("extraction_missing", triggers)

    def test_fingerprint_moves_with_confirmation(self):
        base = workspace_path(PID)
        before = extraction_fingerprint(base, CID)
        self.assertEqual(len(before), 12)
        path = Path.cwd() / "more.md"
        path.write_text(block("RN-06", "- Tratamiento: descarte", "- Motivo: x",
                              '- Cita: "Los proveedores del exterior quedan fuera"'), encoding="utf-8")
        record_proposals(PID, CID, path)
        self.assertEqual(extraction_fingerprint(base, CID), before)
        confirm_proposals(PID, CID, "all")
        self.assertNotEqual(extraction_fingerprint(base, CID), before)


class NoInventory(ProposalsCase):
    @classmethod
    def build_workspace(cls):
        super().build_workspace()
        root = Path.cwd()
        shutil.copy(FIXTURES / "pedido_ids.md", root / "otro.md")
        run_ok(["init", "SIN"])
        run_ok(["ingest", "SIN", "--source", "otro.md", "--change"])
        run_ok(["resolve-gaps", "SIN", "--source", "scope.md", "--change", CID])
        run_ok(["init", "PRJ"])
        run_ok(["ingest", "PRJ", "--source", "otro.md"])

    def test_missing_inventory_warns_in_lenses(self):
        data = json.loads(run_ok(["status", "SIN", "--change", CID]))
        self.assertEqual(data["round"], "lenses")
        self.assertEqual(data["extraction"]["state"], "missing")
        self.assertEqual(data["extraction"]["text"], "sin inventario")
        self.assertIn("extraction_missing", [w["trigger"] for w in data["warnings"]])
        message = next(w["message"] for w in data["warnings"] if w["trigger"] == "extraction_missing")
        self.assertIn(f"/extract SIN --change {CID}", message)
        self.assertEqual(extraction_fingerprint(workspace_path("SIN"), CID), "")

    def test_project_status_unchanged(self):
        data = json.loads(run_ok(["status", "PRJ"]))
        self.assertNotIn("extraction", data)
        self.assertNotIn("preserved", data)
        full = json.loads(run_ok(["status", "PRJ", "--full"]))
        self.assertNotIn("extraction", full)
        self.assertNotIn("preserved", full)


if __name__ == "__main__":
    unittest.main()
