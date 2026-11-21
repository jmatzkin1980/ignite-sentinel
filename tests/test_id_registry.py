"""IMP-388: persistent id registry keeps SPEC-U ids stable once a workspace has changes."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import SnapshotWorkspaceCase, build_matured_workspace, gap_acceptance_answer, run_ok  # noqa: E402
from sentinel.id_registry import assign_ids, registry_active, registry_path, seed_family  # noqa: E402
from sentinel.workspace import update_state, workspace_path  # noqa: E402

RAW = """# Operations Risk Dashboard

Objective: let operations leads review risk queues before the daily meeting.

Users: operations leads and analysts.

In scope: read-only risk dashboard for open queues and queue drilldown.
"""
EARS = ("When queue metrics are available, the system shall display open risk queues. "
        "When an operations lead selects a queue, the system shall show the queue detail with current risk indicators.")


def open_change(project: str) -> None:
    update_state(project, changes={"CHG-001": {"title": "Borrador", "status": "open"}})


def unit_ids(project: str) -> list[str]:
    return sorted(p.stem for p in (workspace_path(project) / "03_specs" / "units").glob("SPEC-U-*.md"))


class IdRegistry(SnapshotWorkspaceCase):
    @classmethod
    def build_workspace(cls):
        build_matured_workspace("REG", RAW, gap_acceptance_answer(EARS), backlog=False)

    def test_inactive_without_changes_and_project_units_stay_positional(self):
        self.assertFalse(registry_active("REG"))
        run_ok(["specs", "REG"])
        self.assertEqual(unit_ids("REG"), ["SPEC-U-001", "SPEC-U-002"])
        self.assertFalse(registry_path("REG").exists())

    def test_assign_ids_keeps_issued_and_appends(self):
        self.assertEqual(assign_ids("REG", "SPEC-U", ["REQ-EARS-001", "REQ-EARS-002"]),
                         {"REQ-EARS-001": "SPEC-U-001", "REQ-EARS-002": "SPEC-U-002"})
        self.assertEqual(assign_ids("REG", "SPEC-U", ["REQ-EARS-002", "REQ-EARS-005"]),
                         {"REQ-EARS-002": "SPEC-U-002", "REQ-EARS-005": "SPEC-U-003"})
        data = json.loads(registry_path("REG").read_text(encoding="utf-8"))
        self.assertEqual(data["schema_version"], 1)
        self.assertEqual(data["families"]["SPEC-U"]["last"], 3)

    def test_ids_never_reused_after_a_key_disappears(self):
        assign_ids("REG", "SPEC-U", ["REQ-EARS-001", "REQ-EARS-002", "REQ-EARS-003"])
        assign_ids("REG", "SPEC-U", ["REQ-EARS-002", "REQ-EARS-003"])
        self.assertEqual(assign_ids("REG", "SPEC-U", ["REQ-EARS-002", "REQ-EARS-004"])["REQ-EARS-004"], "SPEC-U-004")

    def test_seed_family_only_adds_absent_keys_and_raises_last(self):
        seed_family("REG", "SPEC-U", {"REQ-EARS-001": "SPEC-U-001", "REQ-EARS-002": "SPEC-U-007"})
        seed_family("REG", "SPEC-U", {"REQ-EARS-001": "SPEC-U-009"})
        data = json.loads(registry_path("REG").read_text(encoding="utf-8"))["families"]["SPEC-U"]
        self.assertEqual(data["issued"]["REQ-EARS-001"], "SPEC-U-001")
        self.assertEqual(data["last"], 7)

    def test_first_activation_seeds_existing_project_units(self):
        run_ok(["specs", "REG"])
        before = {p.stem: p.read_text(encoding="utf-8") for p in (workspace_path("REG") / "03_specs" / "units").glob("*.md")}
        open_change("REG")
        run_ok(["specs", "REG"])
        self.assertEqual(unit_ids("REG"), ["SPEC-U-001", "SPEC-U-002"])
        data = json.loads(registry_path("REG").read_text(encoding="utf-8"))["families"]["SPEC-U"]
        self.assertEqual(data["issued"], {"REQ-EARS-001": "SPEC-U-001", "REQ-EARS-002": "SPEC-U-002"})
        after = {p.stem: p.read_text(encoding="utf-8") for p in (workspace_path("REG") / "03_specs" / "units").glob("*.md")}
        self.assertEqual(before.keys(), after.keys())

    def test_project_specs_after_change_ids_do_not_collide(self):
        run_ok(["specs", "REG"])
        open_change("REG")
        run_ok(["specs", "REG"])
        # a change takes the next SPEC-U id (simulated; task 3 covers it end to end)
        self.assertEqual(assign_ids("REG", "SPEC-U", ["CHG-001:REQ-EARS-003"])["CHG-001:REQ-EARS-003"], "SPEC-U-003")
        run_ok(["specs", "REG"])
        self.assertEqual(unit_ids("REG"), ["SPEC-U-001", "SPEC-U-002"])
        self.assertEqual(assign_ids("REG", "SPEC-U", ["REQ-EARS-009"])["REQ-EARS-009"], "SPEC-U-004")


if __name__ == "__main__":
    unittest.main()
