import os
import shutil
import tempfile
import unittest
from pathlib import Path

from sentinel.cli import main
from sentinel.discovery.workflow import (
    ingest,
    render_requirement_unit_delta,
    requirement_unit_delta_entries,
    requirement_unit_snapshot,
    write_requirement_unit_delta,
)
from sentinel.workspace import workspace_path


class RequirementUnitDeltaLogicTests(unittest.TestCase):
    def _status(self, entries, label):
        for entry in entries:
            if entry["label"] == label:
                return entry["status"]
        return None

    def test_added_modified_removed_are_classified_by_label(self):
        previous = {
            "queue export": {"id": "RU-001", "label": "Queue export", "evidence": "export queues"},
            "stale banner": {"id": "RU-002", "label": "Stale banner", "evidence": "banner when stale"},
        }
        units = [
            {"id": "RU-001", "label": "Queue export", "evidence_mention": "export queues"},
            {"id": "RU-002", "label": "Stale banner", "evidence_mention": "banner colour changed"},
            {"id": "RU-003", "label": "Risk score", "evidence_mention": "compute risk score"},
        ]
        entries = requirement_unit_delta_entries(previous, units)
        self.assertEqual(self._status(entries, "Queue export"), "UNCHANGED")
        self.assertEqual(self._status(entries, "Stale banner"), "MODIFIED")
        self.assertEqual(self._status(entries, "Risk score"), "ADDED")
        # "Removed" only exists in previous under a label absent from units.
        previous["dropped cap"] = {"id": "RU-009", "label": "Dropped cap", "evidence": "old"}
        entries = requirement_unit_delta_entries(previous, units)
        self.assertEqual(self._status(entries, "Dropped cap"), "REMOVED")

    def test_render_cites_ru_id_and_evidence_and_is_read_only_language(self):
        entries = [{"status": "ADDED", "id": "RU-003", "label": "Risk score", "evidence": "compute risk score"}]
        rendered = render_requirement_unit_delta("P", entries)
        self.assertIn("`RU-003`", rendered)
        self.assertIn("compute risk score", rendered)
        self.assertIn("never opens, closes, or rewrites", rendered)


class RequirementUnitDeltaFlowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.old_cwd = Path.cwd()
        self.temp = Path(tempfile.mkdtemp())
        os.chdir(self.temp)
        self.assertEqual(main(["init", "RUD"]), 0)
        self.base = workspace_path("RUD")
        self.delta = self.base / "01_discovery" / "requirement_unit_deltas.md"

    def tearDown(self) -> None:
        os.chdir(self.old_cwd)
        shutil.rmtree(self.temp, ignore_errors=True)

    def _write_units(self, rows: str) -> None:
        (self.base / "01_discovery").mkdir(parents=True, exist_ok=True)
        (self.base / "01_discovery" / "requirement_units.md").write_text(
            "# Requirement Units\n\n"
            "| RU ID | Label | Evidence Mention | Raw Source | Trace ID |\n"
            "| --- | --- | --- | --- | --- |\n" + rows + "\n",
            encoding="utf-8",
        )

    def test_snapshot_parses_the_units_table_by_label(self):
        self._write_units("| `RU-001` | Queue export | `export queues` | `RAW-001` | `RU-001` |")
        snap = requirement_unit_snapshot(self.base)
        self.assertIn("queue export", snap)
        self.assertEqual(snap["queue export"]["id"], "RU-001")
        self.assertEqual(snap["queue export"]["evidence"], "export queues")

    def test_first_ingest_writes_no_delta(self):
        source = self.temp / "a.md"
        source.write_text("Support leads need to export the risk queue before standup.", encoding="utf-8")
        result = ingest("RUD", source)
        self.assertIsNone(result["requirement_unit_deltas"])
        self.assertFalse(self.delta.exists())

    def test_reingest_with_changed_units_writes_a_cited_delta(self):
        # Seed a previous units table, then ingest a source: the snapshot taken
        # before overwrite is non-empty, so a delta view is written.
        self._write_units("| `RU-001` | Legacy capability | `old evidence` | `RAW-001` | `RU-001` |")
        source = self.temp / "b.md"
        source.write_text("Support leads must filter stale queues and export the risk report.", encoding="utf-8")
        result = ingest("RUD", source)
        self.assertIsNotNone(result["requirement_unit_deltas"])
        self.assertTrue(self.delta.exists())
        text = self.delta.read_text(encoding="utf-8")
        self.assertIn("## Added", text)
        self.assertIn("## Removed", text)
        # The removed legacy capability is surfaced (it was not in the new source).
        self.assertIn("Legacy capability", text)


if __name__ == "__main__":
    unittest.main()
