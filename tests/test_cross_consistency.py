"""Tests for IMP-045 cross-artifact consistency warnings in /validate."""
from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from pathlib import Path

from sentinel.cli import main
from sentinel.validation import validate_project


RAW = """# Client Request: Support Operations Dashboard

Objective: reduce support leads' weekly review preparation time.

Users: support team leads.

In scope: read-only dashboard for ticket volume and SLA breach risk. Out of scope: editing tickets.

Metric: reduce preparation effort by 30 percent in the first release month.
"""


class CrossArtifactConsistencyTests(unittest.TestCase):
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

    def prepare_project(self, project_id: str = "CONSISTENT") -> Path:
        self.assertEqual(main(["init", project_id]), 0)
        self.assertEqual(main(["ingest", project_id, "--source", str(self.raw)]), 0)
        self.assertEqual(main(["resolve-gaps", project_id, "--source", str(self.answers)]), 0)
        self.assertEqual(main(["brief", project_id]), 0)
        self.assertEqual(main(["specs", project_id]), 0)
        return self.temp / "workspaces" / project_id

    def test_validate_reports_clean_cross_artifact_consistency_for_complete_fixture(self):
        self.prepare_project()

        result = validate_project("CONSISTENT")

        self.assertEqual(result["verdict"], "VALID")
        consistency = result["cross_artifact_consistency"]
        self.assertEqual(consistency["verdict"], "CLEAN")
        self.assertEqual(consistency["warnings_count"], 0)

    def test_synthetic_spec_unit_pointer_inconsistency_warns_without_blocking(self):
        workspace = self.prepare_project("BROKEN_POINTER")
        unit_path = workspace / "03_specs" / "units" / "SPEC-U-001.md"
        unit_text = unit_path.read_text(encoding="utf-8")
        unit_path.write_text(unit_text.replace("03_specs/prd.md#4-functional-requirements", "03_specs/missing.md#4-functional-requirements"), encoding="utf-8")

        result = validate_project("BROKEN_POINTER")

        self.assertEqual(result["verdict"], "VALID")
        consistency = result["cross_artifact_consistency"]
        self.assertEqual(consistency["verdict"], "WARN")
        messages = "\n".join(warning["message"] for warning in consistency["warnings"])
        self.assertIn("SPEC-U-001 has a dangling source pointer", messages)
        self.assertIn("spec_unit->source", {warning["layer"] for warning in consistency["warnings"]})
        self.assertIn("python -m sentinel /specs BROKEN_POINTER", {warning["suggested_command"] for warning in consistency["warnings"]})


if __name__ == "__main__":
    unittest.main()
