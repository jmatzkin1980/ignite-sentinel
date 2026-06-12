"""Tests for IMP-043 spec-unit delta reports during regeneration."""
from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from sentinel.cli import main
from sentinel.traceability import load_graph


RAW = """# Client Request: Support Operations Dashboard

Objective: reduce support leads' weekly review preparation time.

Users: support team leads.

In scope: read-only dashboard for ticket volume and SLA breach risk. Out of scope: editing tickets.

Metric: reduce preparation effort by 30 percent in the first release month.
"""


class SpecUnitDeltaTests(unittest.TestCase):
    def setUp(self):
        self.old_cwd = Path.cwd()
        self.temp = Path(tempfile.mkdtemp())
        os.chdir(self.temp)
        self.raw = self.temp / "raw.md"
        self.raw.write_text(RAW, encoding="utf-8")
        self.first_answer = self.temp / "answers-1.md"
        self.first_answer.write_text(
            "### GAP-ACCEPTANCE\n"
            "- Answer: When ticket metrics are available, the system shall flag SLA breach risk queues.\n"
            "- Owner / source: Client workshop\n"
            "- Evidence or reference: Synthetic test response\n"
            "- Decision status: confirmed\n",
            encoding="utf-8",
        )
        self.second_answer = self.temp / "answers-2.md"
        self.second_answer.write_text(
            "### GAP-BUSINESS-RULES\n"
            "- Answer: When a queue has no open tickets, the system shall hide SLA breach risk indicators.\n"
            "- Owner / source: Client workshop\n"
            "- Evidence or reference: Synthetic follow-up response\n"
            "- Decision status: confirmed\n",
            encoding="utf-8",
        )

    def tearDown(self):
        os.chdir(self.old_cwd)
        shutil.rmtree(self.temp, ignore_errors=True)

    def test_regenerated_specs_report_unit_delta_and_stale_readiness(self):
        self.assertEqual(main(["init", "DELTA"]), 0)
        self.assertEqual(main(["ingest", "DELTA", "--source", str(self.raw)]), 0)
        self.assertEqual(main(["resolve-gaps", "DELTA", "--source", str(self.first_answer)]), 0)
        self.assertEqual(main(["brief", "DELTA"]), 0)
        self.assertEqual(main(["specs", "DELTA"]), 0)
        self.assertEqual(main(["backlog", "DELTA"]), 0)

        self.assertEqual(main(["resolve-gaps", "DELTA", "--source", str(self.second_answer)]), 0)
        self.assertEqual(main(["specs", "DELTA"]), 0)

        workspace = self.temp / "workspaces" / "DELTA"
        reports = sorted((workspace / "07_changes" / "04_regeneration").glob("*spec-units-delta.md"))
        self.assertTrue(reports)
        report = reports[-1].read_text(encoding="utf-8")
        self.assertIn("`SPEC-U-002` | ADDED", report)
        self.assertIn("`SPEC-U-001` | UNCHANGED", report)

        readiness = json.loads((workspace / "08_context_packs" / "implementation_readiness.json").read_text(encoding="utf-8"))
        self.assertEqual(readiness["stale_spec_units"][0]["unit_id"], "SPEC-U-002")
        self.assertEqual(readiness["stale_spec_units"][0]["status"], "ADDED")

        state = json.loads((workspace / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(state["stale_spec_units"][0]["unit_id"], "SPEC-U-002")
        self.assertIn("last_spec_unit_delta_id", state)

        graph = load_graph("DELTA")
        delta_node = state["last_spec_unit_delta_id"]
        self.assertTrue(any(node["id"] == delta_node and node["type"] == "regeneration_diff" for node in graph["nodes"]))
        self.assertIn({"from": state["last_change_id"], "to": delta_node, "relation": "triggers_regeneration"}, graph["edges"])


if __name__ == "__main__":
    unittest.main()
