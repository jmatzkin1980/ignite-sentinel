from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from sentinel.cli import main
from sentinel.slice_plan import generate_slice_plan


class SlicePlanTests(unittest.TestCase):
    def setUp(self) -> None:
        self.old_cwd = Path.cwd()
        self.temp = Path(tempfile.mkdtemp())
        os.chdir(self.temp)
        self.assertEqual(main(["init", "PLAN"]), 0)
        self.workspace = self.temp / "workspaces" / "PLAN"

    def tearDown(self) -> None:
        os.chdir(self.old_cwd)
        shutil.rmtree(self.temp, ignore_errors=True)

    def test_slice_plan_places_enablers_before_parallel_value_wave(self) -> None:
        stories = [
            {
                "id": "US-001",
                "type": "value_story",
                "title": "First value story",
                "dependencies": [],
                "enables": [],
                "execution_contract": {"retrieval_plan": [{"agent": "Planner"}]},
                "trace": ["SPEC-U-001"],
                "source_unit": "SPEC-U-001",
            },
            {
                "id": "US-002",
                "type": "value_story",
                "title": "Second value story",
                "dependencies": [],
                "enables": [],
                "execution_contract": {"retrieval_plan": [{"agent": "Planner"}]},
                "trace": ["SPEC-U-002"],
                "source_unit": "SPEC-U-002",
            },
            {
                "id": "US-003",
                "type": "cross_cutting_enabler",
                "title": "Shared integration contract",
                "dependencies": [],
                "enables": ["US-001", "US-002"],
                "execution_contract": {"critical_surfaces": {"anchor": {"source_path": "x.md", "line_start": 1, "line_end": 1}}},
                "trace": ["SPEC-001"],
                "source_unit": "",
            },
        ]
        readiness = {
            "stories": [
                {
                    "story_id": "US-001",
                    "type": "value_story",
                    "readiness_score": 1.0,
                    "dor": {"passed": True},
                    "dod": {"passed": False},
                    "source_unit": "SPEC-U-001",
                    "execution_contract": stories[0]["execution_contract"],
                    "retrieval_plan": stories[0]["execution_contract"]["retrieval_plan"],
                },
                {
                    "story_id": "US-002",
                    "type": "value_story",
                    "readiness_score": 0.8,
                    "dor": {"passed": True},
                    "dod": {"passed": False},
                    "source_unit": "SPEC-U-002",
                    "execution_contract": stories[1]["execution_contract"],
                    "retrieval_plan": stories[1]["execution_contract"]["retrieval_plan"],
                },
                {
                    "story_id": "US-003",
                    "type": "cross_cutting_enabler",
                    "readiness_score": 0.6,
                    "dor": {"passed": False, "missing": ["Technology context"]},
                    "dod": {"passed": False},
                    "source_unit": "",
                    "execution_contract": stories[2]["execution_contract"],
                    "retrieval_plan": [],
                },
            ]
        }

        result = generate_slice_plan("PLAN", stories, readiness)
        self.assertTrue((self.workspace / "04_backlog" / "SLICE-PLAN.md").exists())
        plan = json.loads((self.workspace / "08_context_packs" / "slice_plan.json").read_text(encoding="utf-8"))

        self.assertEqual(plan["phases"]["enabler_phase"][0]["story_id"], "US-003")
        wave_one = plan["phases"]["implementation_waves"][0]["stories"]
        self.assertEqual([item["story_id"] for item in wave_one], ["US-001", "US-002"])
        self.assertEqual(plan["handoff_packs"]["US-001"]["position"]["prerequisites"], ["US-003"])
        self.assertEqual(plan["handoff_packs"]["US-002"]["position"]["parallel_group"], "wave-01")
        self.assertEqual(plan["checkpoints"][0]["id"], "CHK-ENABLERS")
        self.assertIn("Ignite does not create or execute downstream tasks", Path(result["path"]).read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
