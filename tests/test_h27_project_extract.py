"""IMP-420 (H27 inc 6b) task 2: the inventory and the proposals of the project's request, and the opt-in by evidence."""
from __future__ import annotations

import shutil
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import ProjectExtractionCase, run_ok  # noqa: E402

from sentinel.changes import project_extraction_offered  # noqa: E402
from sentinel.core.io import forget_read_snapshots  # noqa: E402
from sentinel.extraction import extraction_dir  # noqa: E402
from sentinel.extraction.inventory import build_inventory, inventory_state, load_inventory  # noqa: E402
from sentinel.extraction.proposals import load_proposals, record_proposals  # noqa: E402
from sentinel.workspace import workspace_path  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"
PROJECT = FIXTURES / "project_extraction"
PID = ProjectExtractionCase.PID
TAIL = "el alta queda en estado Observada"


class ProjectInventory(ProjectExtractionCase):
    def inventory(self) -> dict:
        build_inventory(PID, None)
        forget_read_snapshots()
        return load_inventory(workspace_path(PID), None) or {}

    def test_project_inventory_lists_request_elements(self):
        result = build_inventory(PID, None)
        counts = result["by_kind"]
        self.assertEqual((counts["rule"], counts["criterion"], counts["story"], counts["decision"]), (5, 4, 3, 1))
        self.assertEqual(inventory_state(PID, None), "current")
        path = workspace_path(PID) / "02_requirements" / "extraction" / "inventory.json"
        self.assertTrue(path.is_file())
        self.assertEqual(Path(result["inventory_path"]), path)

    def test_long_section_line_end_content_covered(self):
        inventory = self.inventory()
        parts = [e for e in inventory["elements"] if e["id"].startswith("SEC-proceso.p")]
        self.assertGreaterEqual(len(parts), 2)
        lines = (PROJECT / "brief_alta_proveedores.md").read_text(encoding="utf-8").split("\n")
        at = next(n for n, text in enumerate(lines, 1) if TAIL in text)
        self.assertTrue(any(a <= at <= b for e in parts for a, b in e["spans"]), [e["spans"] for e in parts])

    def test_project_worksheet_has_no_change_fields(self):
        build_inventory(PID, None)
        sheet = (extraction_dir(workspace_path(PID), None) / "proposals_template.md").read_text(encoding="utf-8")
        for label in ("Delta:", "Superficie:", "Afecta:", "Surface:", "Affects:"):
            self.assertNotIn(label, sheet)
        self.assertIn("- Tratamiento:", sheet)
        self.assertIn(f"/extract {PID} --proposals", sheet)
        self.assertNotIn("--change", sheet)

    def test_project_proposals_recorded(self):
        build_inventory(PID, None)
        result = record_proposals(PID, None, PROJECT / "propuestas.md")
        self.assertEqual(result["rejected"], {})
        self.assertEqual(sorted(result["recorded"]), ["RN-01", "RN-03", "RN-04", "RN-05"])
        items = load_proposals(workspace_path(PID), None)["items"]
        self.assertEqual(items["RN-01"]["statements"][0]["delta"], "ADDED")
        self.assertEqual(items["RN-01"]["statements"][0]["surfaces"], [])

    def test_change_fields_refused_on_project(self):
        build_inventory(PID, None)
        result = record_proposals(PID, None, PROJECT / "propuestas_cambio.md")
        reasons = " ".join(r for errors in result["rejected"].values() for r in errors)
        self.assertIn("En el proyecto todo enunciado es ADDED: MODIFIED es de un cambio", reasons)
        self.assertIn("Afecta es de un cambio", reasons)
        self.assertEqual({"RN-01", "RN-03", "RN-04"} - set(result["rejected"]), set())
        self.assertFalse({"RN-01", "RN-03", "RN-04"} & set(result["recorded"]))

    def test_project_and_change_inventories_do_not_mix(self):
        shutil.copy(FIXTURES / "change_extraction" / "pedido_ids.md", Path.cwd() / "pedido_ids.md")
        run_ok(["ingest", PID, "--source", "pedido_ids.md", "--change"])
        forget_read_snapshots()
        change = build_inventory(PID, "CHG-001")
        change_sources = {e["source_id"] for e in load_inventory(workspace_path(PID), "CHG-001")["elements"]}
        project = self.inventory()
        self.assertTrue(change_sources)
        self.assertFalse({e["source_id"] for e in project["elements"]} & change_sources)
        self.assertEqual(change["by_kind"], {"rule": 6, "criterion": 5, "story": 3, "decision": 2, "section": 6})


class Offered(ProjectExtractionCase):
    def test_offered_only_with_ids_or_records(self):
        self.assertTrue(project_extraction_offered(PID, False))
        self.assertFalse(project_extraction_offered(PID, True))
        build_inventory(PID, None)
        self.assertTrue(project_extraction_offered(PID, True))

    def test_not_offered_without_ids(self):
        from test_golden_artifacts import RAW_ES

        other = "GLD"
        Path("golden.md").write_text(RAW_ES, encoding="utf-8")
        run_ok(["init", other])
        run_ok(["ingest", other, "--source", "golden.md"])
        self.assertFalse(project_extraction_offered(other, False))
        self.assertFalse(project_extraction_offered(other, True))


if __name__ == "__main__":
    unittest.main()
