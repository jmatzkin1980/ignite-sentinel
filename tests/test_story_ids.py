"""IMP-393: story ids stay stable once a workspace has changes; the project /backlog leaves change stories alone."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import SnapshotWorkspaceCase, build_matured_workspace, gap_acceptance_answer, run_ok  # noqa: E402
from sentinel.id_registry import registry_path  # noqa: E402
from sentinel.story_ids import ensure_story_ids_seeded, is_change_story  # noqa: E402
from sentinel.workspace import read_json, update_state, workspace_path  # noqa: E402

RAW = """# Operations Risk Dashboard

Objective: let operations leads review risk queues before the daily meeting.

Users: operations leads and analysts.

In scope: read-only risk dashboard for open queues and queue drilldown.
"""
EARS = ("When queue metrics are available, the system shall display open risk queues. "
        "When an operations lead selects a queue, the system shall show the queue detail with current risk indicators.")
PID = "STO"
CHANGE_STORY = """---
id: US-005
project: STO
parent_epic: EPIC-001
status: Ready
owner: "ana"
label: Spec Unit
type: value_story
change: CHG-001
source_unit: SPEC-U-050
trace:
  - SPEC-U-050
---

# US-005 - Cambio de cola
"""


def backlog_dir() -> Path:
    return workspace_path(PID) / "04_backlog"


def snapshot_stories() -> dict[str, str]:
    return {p.name: p.read_text(encoding="utf-8") for p in sorted(backlog_dir().glob("*.md"))}


def open_change() -> None:
    update_state(PID, changes={"CHG-001": {"title": "Borrador", "status": "open"}})


def add_change_story() -> None:
    (backlog_dir() / "US-005.md").write_text(CHANGE_STORY, encoding="utf-8")
    pack_path = workspace_path(PID) / "08_context_packs" / "implementation_readiness.json"
    pack = json.loads(pack_path.read_text(encoding="utf-8"))
    pack["stories"].append({"story_id": "US-005", "source_unit": "SPEC-U-050", "status": "ready"})
    pack_path.write_text(json.dumps(pack), encoding="utf-8")
    from sentinel.backlog.status import story_lifecycle_state

    lifecycle = dict(story_lifecycle_state(PID))
    lifecycle["US-005"] = {"status": "Ready", "owner": "ana"}
    update_state(PID, story_lifecycle=lifecycle)


class StoryIds(SnapshotWorkspaceCase):
    @classmethod
    def build_workspace(cls):
        build_matured_workspace(PID, RAW, gap_acceptance_answer(EARS), backlog=False)

    def test_no_changes_backlog_is_byte_identical(self):
        run_ok(["backlog", PID])
        first = snapshot_stories()
        self.assertEqual(sorted(n for n in first if n.startswith("US-")), ["US-001.md", "US-002.md"])
        run_ok(["backlog", PID])
        self.assertEqual(sorted(snapshot_stories()), sorted(first))
        self.assertEqual(
            [line for line in first["US-002.md"].splitlines() if line.startswith("id:")], ["id: US-002"]
        )
        self.assertFalse(registry_path(PID).exists())

    def test_project_backlog_keeps_change_stories(self):
        run_ok(["backlog", PID])
        open_change()
        add_change_story()
        self.assertTrue(is_change_story(backlog_dir() / "US-005.md"))
        self.assertFalse(is_change_story(backlog_dir() / "US-001.md"))
        run_ok(["backlog", PID])
        stories = snapshot_stories()
        self.assertEqual(stories["US-005.md"], CHANGE_STORY)
        self.assertIn("US-001.md", stories)
        self.assertIn("US-002.md", stories)
        state = read_json(workspace_path(PID) / "state.json", {})
        self.assertEqual(state["story_lifecycle"]["US-005"], {"status": "Ready", "owner": "ana"})
        pack = json.loads((workspace_path(PID) / "08_context_packs" / "implementation_readiness.json").read_text(encoding="utf-8"))
        self.assertIn("US-005", [item["story_id"] for item in pack["stories"]])

    def test_removed_project_story_lifecycle_still_disappears(self):
        run_ok(["backlog", PID])
        from sentinel.backlog.status import story_lifecycle_state

        lifecycle = dict(story_lifecycle_state(PID))
        lifecycle["US-077"] = {"status": "Ready", "owner": "x"}
        update_state(PID, story_lifecycle=lifecycle)
        open_change()
        run_ok(["backlog", PID])
        self.assertNotIn("US-077", read_json(workspace_path(PID) / "state.json", {})["story_lifecycle"])

    def test_project_ids_go_through_registry_with_changes(self):
        run_ok(["backlog", PID])
        open_change()
        add_change_story()
        units = workspace_path(PID) / "03_specs" / "units"
        text = (units / "SPEC-U-002.md").read_text(encoding="utf-8").replace("SPEC-U-002", "SPEC-U-009")
        (units / "SPEC-U-009.md").write_text(text, encoding="utf-8")
        run_ok(["backlog", PID])
        stories = snapshot_stories()
        self.assertIn("US-006.md", stories)  # next free id, not the change's US-005
        self.assertEqual(stories["US-005.md"], CHANGE_STORY)
        self.assertIn("SPEC-U-009", stories["US-006.md"])
        self.assertIn("SPEC-U-001", stories["US-001.md"])

    def test_seed_from_existing_stories(self):
        run_ok(["backlog", PID])
        add_change_story()
        ensure_story_ids_seeded(PID, workspace_path(PID))
        data = json.loads(registry_path(PID).read_text(encoding="utf-8"))["families"]["US"]
        self.assertEqual(data["issued"]["SPEC-U-001"], "US-001")
        self.assertEqual(data["issued"]["SPEC-U-002"], "US-002")
        self.assertEqual(data["issued"]["SPEC-U-050"], "US-005")
        self.assertEqual(data["last"], 5)


if __name__ == "__main__":
    unittest.main()
