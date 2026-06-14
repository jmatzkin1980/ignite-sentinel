"""Tests for IMP-044 declarative retrieval plans."""
from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from sentinel.cli import main
from sentinel.generation import build_specs_generation_context


RAW = """# Client Request: Support Operations Dashboard

Objective: reduce support leads' weekly review preparation time.

Users: support team leads.

In scope: read-only dashboard for ticket volume and SLA breach risk. Out of scope: editing tickets.

Metric: reduce preparation effort by 30 percent in the first release month.
"""


class RetrievalPlanTests(unittest.TestCase):
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
            "- Decision status: confirmed\n"
            "### GAP-METRIC-SOURCE\n"
            "- Answer: Baseline comes from the weekly support operations report owned by Support Ops; target is a 30 percent reduction in preparation effort measured during the first release month.\n"
            "- Owner / source: Client workshop\n"
            "- Evidence or reference: Synthetic test response\n"
            "- Decision status: confirmed\n",
            encoding="utf-8",
        )

    def tearDown(self):
        os.chdir(self.old_cwd)
        shutil.rmtree(self.temp, ignore_errors=True)

    def prepare_project(self, project_id: str = "PLAN") -> Path:
        self.assertEqual(main(["init", project_id]), 0)
        self.assertEqual(main(["ingest", project_id, "--source", str(self.raw)]), 0)
        self.assertEqual(main(["resolve-gaps", project_id, "--source", str(self.answers)]), 0)
        self.assertEqual(main(["brief", project_id]), 0)
        self.assertEqual(main(["specs", project_id]), 0)
        return self.temp / "workspaces" / project_id

    def test_specs_pack_uses_query_from_declarative_json(self):
        workspace = self.prepare_project("PLAN_JSON")
        plans_dir = self.temp / "plans"
        plans_dir.mkdir()
        repo_plan = Path(__file__).resolve().parents[1] / "sentinel" / "retrieval_plans" / "specs_generation.json"
        data = json.loads(repo_plan.read_text(encoding="utf-8"))
        data["sections"]["strategic_foundation"]["query"] = "custom strategic retrieval needle"
        (plans_dir / "specs_generation.json").write_text(json.dumps(data), encoding="utf-8")

        pack = build_specs_generation_context("PLAN_JSON", (workspace / "02_requirements" / "requirements.md").read_text(encoding="utf-8"), retrieval_plans_dir=plans_dir)

        self.assertEqual(pack["sections"]["strategic_foundation"]["query"], "custom strategic retrieval needle")
        written = json.loads((workspace / "08_context_packs" / "specs_generation.json").read_text(encoding="utf-8"))
        self.assertEqual(written["sections"]["strategic_foundation"]["query"], "custom strategic retrieval needle")

    def test_generation_pack_results_include_valid_read_plan_anchors(self):
        workspace = self.prepare_project("PLAN_READ")
        pack = json.loads((workspace / "08_context_packs" / "specs_generation.json").read_text(encoding="utf-8"))

        read_plans = [
            result["read_plan"]
            for section in pack["sections"].values()
            for result in section.get("results", [])
            if result.get("read_plan", {}).get("source_path")
        ]
        self.assertTrue(read_plans)
        first = read_plans[0]
        source = Path(first["source_path"])
        self.assertTrue(source.exists(), first)
        lines = source.read_text(encoding="utf-8").splitlines()
        self.assertGreaterEqual(first["line_start"], 1)
        self.assertGreaterEqual(first["line_end"], first["line_start"])
        excerpt = "\n".join(lines[first["line_start"] - 1 : first["line_end"]])
        self.assertTrue(excerpt.strip())
        if first.get("section_path"):
            self.assertIn(first["section_path"].split(" > ")[-1].split("/")[0], excerpt)


if __name__ == "__main__":
    unittest.main()
