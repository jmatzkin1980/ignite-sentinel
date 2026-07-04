from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from sentinel.cli import main
from sentinel.knowledge.ledger import current_units


class LedgerBitemporalUnitTests(unittest.TestCase):
    def test_current_units_filters_by_invalid_at(self):
        units = [
            {"id": "KLU-001", "invalid_at": None},
            {"id": "KLU-002", "invalid_at": "2026-07-03T00:00:00Z"},
            {"id": "KLU-003"},  # missing key defaults to current
        ]
        current = current_units(units)
        ids = {u["id"] for u in current}
        self.assertEqual(ids, {"KLU-001", "KLU-003"})


class LedgerBitemporalFlowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.old_cwd = Path.cwd()
        self.temp = Path(tempfile.mkdtemp())
        os.chdir(self.temp)
        source = self.temp / "input" / "demo.md"
        source.parent.mkdir(parents=True)
        source.write_text(
            "Goal: reduce manual review time for support leads.\n"
            "Users include support leads and operations managers.\n"
            "Scope includes a dashboard for queue triage.\n",
            encoding="utf-8",
        )
        self.assertEqual(main(["init", "BT"]), 0)
        self.assertEqual(main(["ingest", "BT", "--source", str(source)]), 0)
        self.payload = json.loads(
            (self.temp / "workspaces" / "BT" / "01_discovery" / "knowledge_state.json").read_text(encoding="utf-8")
        )

    def tearDown(self) -> None:
        os.chdir(self.old_cwd)
        shutil.rmtree(self.temp, ignore_errors=True)

    def test_payload_records_materialized_at(self):
        self.assertIn("materialized_at", self.payload)
        self.assertTrue(self.payload["materialized_at"])

    def test_every_unit_is_stamped_current(self):
        units = self.payload["units"]
        self.assertGreater(len(units), 0)
        for unit in units:
            self.assertIn("valid_at", unit)
            self.assertTrue(unit["valid_at"])
            self.assertIsNone(unit["invalid_at"])
        # All materialized units are current in the projection (IMP-152).
        self.assertEqual(len(current_units(units)), len(units))

    def test_valid_at_matches_materialization(self):
        for unit in self.payload["units"]:
            self.assertEqual(unit["valid_at"], self.payload["materialized_at"])


if __name__ == "__main__":
    unittest.main()
