"""Tests for IMP-042 spec units."""
from __future__ import annotations

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


class SpecUnitGenerationTests(unittest.TestCase):
    def setUp(self):
        self.old_cwd = Path.cwd()
        self.temp = Path(tempfile.mkdtemp())
        os.chdir(self.temp)
        self.raw = self.temp / "raw.md"
        self.raw.write_text(RAW, encoding="utf-8")
        self.answers = self.temp / "answers.md"
        self.answers.write_text(
            "### GAP-ACCEPTANCE\n"
            "- Answer: When ticket metrics are available, the system shall flag SLA breach risk queues.\n"
            "- Owner / source: Client workshop\n"
            "- Evidence or reference: Synthetic test response\n"
            "- Decision status: confirmed\n",
            encoding="utf-8",
        )

    def tearDown(self):
        os.chdir(self.old_cwd)
        shutil.rmtree(self.temp, ignore_errors=True)

    def test_specs_decompose_confirmed_ears_into_stable_units(self):
        self.assertEqual(main(["init", "UNITS"]), 0)
        self.assertEqual(main(["ingest", "UNITS", "--source", str(self.raw)]), 0)
        self.assertEqual(main(["resolve-gaps", "UNITS", "--source", str(self.answers)]), 0)
        self.assertEqual(main(["brief", "UNITS"]), 0)
        self.assertEqual(main(["specs", "UNITS"]), 0)
        self.assertEqual(main(["specs", "UNITS"]), 0)

        workspace = self.temp / "workspaces" / "UNITS"
        specs = (workspace / "03_specs" / "specs.md").read_text(encoding="utf-8")
        unit_path = workspace / "03_specs" / "units" / "SPEC-U-001.md"
        unit = unit_path.read_text(encoding="utf-8")

        self.assertIn("## Spec Units", specs)
        self.assertIn("`SPEC-U-001`", specs)
        for scaffold_id in ("JTBD-001", "CAP-001", "US-001", "ASM-001"):
            self.assertNotIn(scaffold_id, specs)

        self.assertIn("id: SPEC-U-001", unit)
        self.assertIn("status: evidence-backed", unit)
        self.assertIn("  - REQ-EARS-001", unit)
        self.assertIn("02_requirements/requirements.md#normalized-requirements-ears", unit)
        self.assertIn("02_requirements/project-brief.md", unit)
        self.assertIn("When ticket metrics are available", unit)

        graph = load_graph("UNITS")
        nodes = {node["id"]: node for node in graph["nodes"]}
        self.assertEqual(nodes["SPEC-U-001"]["type"], "spec_unit")
        self.assertEqual(nodes["REQ-EARS-001"]["type"], "ears_requirement")
        self.assertIn({"from": "PRD-001", "to": "SPEC-U-001", "relation": "decomposes"}, graph["edges"])
        self.assertIn({"from": "SPEC-U-001", "to": "REQ-EARS-001", "relation": "traces_to"}, graph["edges"])


if __name__ == "__main__":
    unittest.main()
