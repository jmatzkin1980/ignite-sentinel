"""H27 inc 6a task 1: Sentinel's own re-runs (cross, harvest) close their version chain; a baseline loaded late is stale."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import SyncCase, run_ok  # noqa: E402

from sentinel.changes import list_changes  # noqa: E402
from sentinel.core.io import forget_read_snapshots  # noqa: E402
from sentinel.crosses.record import record_cross  # noqa: E402
from sentinel.crosses.state import cross_status  # noqa: E402
from sentinel.source_registry import registry_summary  # noqa: E402
from sentinel.sources import load_source_manifest, settle_rerun  # noqa: E402
from sentinel.workspace import update_state  # noqa: E402

PID = "VCHAIN"
CID = "CHG-001"
FIXTURES = Path(__file__).resolve().parent / "fixtures"
SAD_V2 = FIXTURES / "change_versions" / "sad-compras-v2.md"


class Chain(SyncCase):
    PID = PID

    def row(self, source_id: str) -> dict:
        forget_read_snapshots()
        return next(r for r in load_source_manifest(PID)["registry"] if r["id"] == source_id)

    def record(self, kind: str, path: Path) -> str:
        forget_read_snapshots()
        return record_cross(PID, CID, kind, path)["source_id"]

    def first_row_of(self, kind: str) -> str:
        forget_read_snapshots()
        from sentinel.crosses import cross_path
        from sentinel.workspace import workspace_path

        data = json.loads(cross_path(workspace_path(PID), CID, kind).read_text(encoding="utf-8"))
        return str(data["source_id"])

    def test_recross_same_file_is_a_rerun(self):
        first = self.first_row_of("contradicciones")
        path = self.claims("cruce_contradicciones.md", self.ids())
        text = path.read_text(encoding="utf-8")
        self.assertIn("RN-04 prohíbe", text)
        path.write_text(text.replace("RN-04 prohíbe", "La regla RN-04 prohíbe"), encoding="utf-8")
        new = self.record("contradicciones", path)
        self.assertNotEqual(new, first)
        row = self.row(new)
        self.assertEqual(row.get("rerun_of"), first)
        self.assertIsNone(row.get("pending_version_of"))
        forget_read_snapshots()
        self.assertEqual(registry_summary(load_source_manifest(PID))["unconfirmed_versions"], [])

    def test_same_name_in_other_kind_stays_candidate(self):
        diseno = self.first_row_of("diseno")
        design_file = Path.cwd() / "sub-cruce_diseno.md"
        self.assertTrue(design_file.is_file())
        other = self.claims("cruce_contradicciones.md", self.ids()).read_text(encoding="utf-8")
        design_file.write_text(other.replace("RN-04 prohíbe", "La regla RN-04 prohíbe"), encoding="utf-8")
        new = self.record("contradicciones", design_file)
        row = self.row(new)
        self.assertEqual(row.get("pending_version_of"), diseno)
        self.assertIsNone(row.get("rerun_of"))

    def test_reharvest_is_a_rerun(self):
        first = list_changes(PID)[CID]["harvests"][0]
        path = Path.cwd() / "harvest_compras.md"
        text = path.read_text(encoding="utf-8")
        self.assertIn("tres ambientes", text)
        path.write_text(text.replace("tres ambientes", "cuatro ambientes"), encoding="utf-8")
        forget_read_snapshots()
        out = json.loads(run_ok(["harvest", PID, "--source", "harvest_compras.md", "--change", CID]))
        new = out["source_id"]
        self.assertNotEqual(new, first)
        row = self.row(new)
        self.assertEqual(row.get("rerun_of"), first)
        self.assertIsNone(row.get("pending_version_of"))

    def test_rerun_needs_the_previous_run_of_the_same_scope(self):
        first = self.first_row_of("contradicciones")
        path = self.claims("cruce_contradicciones.md", self.ids())
        path.write_text(path.read_text(encoding="utf-8").replace("RN-04 prohíbe", "La regla RN-04 prohíbe"), encoding="utf-8")
        new = self.record("contradicciones", path)
        forget_read_snapshots()
        manifest = load_source_manifest(PID)
        for r in manifest["registry"]:
            if r["id"] == new:
                r["rerun_of"] = None
                r["pending_version_of"] = first
        from sentinel.sources import save_source_manifest

        save_source_manifest(PID, manifest)
        self.assertIsNone(settle_rerun(PID, new, "crossed", ["F-99"]))
        self.assertEqual(settle_rerun(PID, new, "crossed", [first]), first)
        with self.assertRaises(ValueError):
            settle_rerun(PID, new, "loaded")

    def test_baseline_loaded_after_harvest_is_stale(self):
        forget_read_snapshots()
        self.assertEqual(cross_status(PID, CID)["kinds"]["linea_de_base"]["state"], "done")
        new = json.loads(run_ok(["sources", PID, "--load", str(SAD_V2), "--role", "linea_de_base", "--change", CID]))["source_id"]
        forget_read_snapshots()
        info = cross_status(PID, CID)["kinds"]["linea_de_base"]
        self.assertEqual(info["state"], "stale")
        self.assertEqual(info["new_sources"], [new])
        step = self.step()
        self.assertEqual(step["key"], "crosses")
        self.assertEqual(step["command"], f"/harvest {PID} --source PATH --change {CID}")
        self.assertIn(f"fuentes vigentes que el cruce no leyó: {new}", step["text"])
        run_ok(["harvest", PID, "--source", "harvest_compras.md", "--change", CID])
        forget_read_snapshots()
        self.assertEqual(cross_status(PID, CID)["kinds"]["linea_de_base"]["state"], "done")

    def test_old_change_without_basis_reads_done(self):
        run_ok(["sources", PID, "--load", str(SAD_V2), "--role", "linea_de_base", "--change", CID])
        forget_read_snapshots()
        changes = {key: dict(value) for key, value in list_changes(PID).items()}
        self.assertIn("harvest_basis", changes[CID])
        changes[CID].pop("harvest_basis")
        update_state(PID, changes=changes)
        forget_read_snapshots()
        self.assertEqual(cross_status(PID, CID)["kinds"]["linea_de_base"]["state"], "done")


if __name__ == "__main__":
    unittest.main()
