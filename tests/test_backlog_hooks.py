from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from sentinel.cli import main


RAW = """# Operations Risk Dashboard

Objective: let operations leads review risk queues before the daily meeting.

Users: operations leads and analysts.

In scope: read-only risk dashboard for open queues and queue drilldown.
"""

EARS = """When queue metrics are available, the system shall display open risk queues.
When an operations lead selects a queue, the system shall show the queue detail with current risk indicators.
"""


class BacklogHooksTests(unittest.TestCase):
    def setUp(self) -> None:
        self.old_cwd = Path.cwd()
        self.temp = Path(tempfile.mkdtemp())
        os.chdir(self.temp)
        raw = self.temp / "raw.md"
        raw.write_text(RAW, encoding="utf-8")
        self.assertEqual(main(["init", "HOOKS"]), 0)
        self.assertEqual(main(["ingest", "HOOKS", "--source", str(raw)]), 0)
        answers = self.temp / "answers.md"
        answers.write_text(
            "### GAP-ACCEPTANCE\n"
            f"- Answer: {EARS}\n"
            "- Owner / source: Client workshop\n"
            "- Evidence or reference: Synthetic EARS response\n"
            "- Decision status: confirmed\n",
            encoding="utf-8",
        )
        self.assertEqual(main(["resolve-gaps", "HOOKS", "--source", str(answers)]), 0)
        self.assertEqual(main(["brief", "HOOKS"]), 0)
        self.assertEqual(main(["specs", "HOOKS"]), 0)
        self.assertEqual(main(["backlog", "HOOKS"]), 0)
        self.ws = self.temp / "workspaces" / "HOOKS"

    def tearDown(self) -> None:
        os.chdir(self.old_cwd)
        shutil.rmtree(self.temp, ignore_errors=True)

    def test_sync_spec_unit_marks_only_derived_story_stale(self) -> None:
        readiness = json.loads((self.ws / "08_context_packs" / "implementation_readiness.json").read_text(encoding="utf-8"))
        readiness["stories"].append(
            {
                **readiness["stories"][0],
                "story_id": "US-002",
                "source_unit": "SPEC-U-002",
                "trace": ["REQ-001", "PRD-001", "SPEC-001", "SPEC-U-002"],
                "story_status": "Draft",
            }
        )
        (self.ws / "08_context_packs" / "implementation_readiness.json").write_text(
            json.dumps(readiness, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        story_two = (self.ws / "04_backlog" / "US-001.md").read_text(encoding="utf-8").replace("US-001", "US-002").replace("SPEC-U-001", "SPEC-U-002")
        (self.ws / "04_backlog" / "US-002.md").write_text(story_two, encoding="utf-8")
        state = json.loads((self.ws / "state.json").read_text(encoding="utf-8"))
        state["story_lifecycle"]["US-002"] = {"status": "Draft", "owner": ""}
        (self.ws / "state.json").write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")

        source_units = [story["source_unit"] for story in readiness["stories"] if story.get("type") != "cross_cutting_enabler"]
        self.assertGreaterEqual(len(source_units), 2)

        changed_unit = source_units[0]
        unchanged_unit = source_units[1]
        changed_path = self.ws / "03_specs" / "units" / f"{changed_unit}.md"
        self.assertEqual(main(["sync", "HOOKS", "--source", str(changed_path), "--note", "spec unit changed"]), 0)

        state = json.loads((self.ws / "state.json").read_text(encoding="utf-8"))
        stale_by_story = {
            story_id: payload
            for story_id, payload in state["story_lifecycle"].items()
            if payload.get("status") == "Stale"
        }
        self.assertEqual(list(stale_by_story), ["US-001"])
        self.assertEqual(stale_by_story["US-001"]["stale_spec_units"], [changed_unit])
        self.assertNotEqual(state["story_lifecycle"]["US-002"]["status"], "Stale")
        refreshed = json.loads((self.ws / "08_context_packs" / "implementation_readiness.json").read_text(encoding="utf-8"))
        status_by_unit = {story["source_unit"]: story["story_status"] for story in refreshed["stories"] if story.get("source_unit")}
        self.assertEqual(status_by_unit[changed_unit], "Stale")
        self.assertNotEqual(status_by_unit[unchanged_unit], "Stale")

    def test_slice_plan_warns_by_default_for_missing_dor(self) -> None:
        plan = json.loads((self.ws / "08_context_packs" / "slice_plan.json").read_text(encoding="utf-8"))
        gate = plan["pre_handoff_gate"]
        self.assertFalse(gate["strict"])
        self.assertEqual(gate["verdict"], "WARN")
        self.assertTrue(gate["warnings"])
        self.assertIn("## Pre-Handoff Gate", (self.ws / "04_backlog" / "SLICE-PLAN.md").read_text(encoding="utf-8"))

    def test_strict_pre_handoff_gate_blocks_backlog_handoff(self) -> None:
        config = self.ws / "sentinel.config.yaml"
        config.write_text(
            config.read_text(encoding="utf-8") + "\nbacklog_gate:\n  threshold: 1.0\n  strict: true\n",
            encoding="utf-8",
        )
        self.assertEqual(main(["backlog", "HOOKS"]), 1)

    def test_backlog_privacy_scan_blocks_handoff_surfaces(self) -> None:
        story_path = self.ws / "04_backlog" / "US-001.md"
        story_path.write_text(story_path.read_text(encoding="utf-8") + "\npassword: super-secret\n", encoding="utf-8")

        self.assertEqual(main(["quality", "HOOKS"]), 1)


if __name__ == "__main__":
    unittest.main()
