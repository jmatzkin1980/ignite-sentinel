"""IMP-416 final fix wave: I-1..I-5 and the minors of the whole-branch review."""
from __future__ import annotations

import json
import re
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import SnapshotWorkspaceCase, build_matured_workspace, gap_acceptance_answer, run_cli, run_ok  # noqa: E402
from sentinel.compilers.change_backlog import read_change_units  # noqa: E402
from sentinel.generation import implementation_readiness_for_story  # noqa: E402
from sentinel.quality import evaluate_story_quality  # noqa: E402
from sentinel.core.io import write_json  # noqa: E402
from sentinel.workspace import read_json, read_state, update_state, workspace_path  # noqa: E402
from test_change_affected_stories import MODIFIED_ROW, REMOVED_ROW, UNCHANGED_ROW  # noqa: E402
from test_change_specs import PROJECT_EARS, PROJECT_RAW, open_change  # noqa: E402
import test_h27_change_enablers_plan as tep  # noqa: E402
import test_h27_change_grouped_backlog as tgb  # noqa: E402
from test_h27_change_grouped_backlog import backlog_dir, front_of, run_backlog  # noqa: E402


class EnablerSmall(unittest.TestCase):
    """I-1: an enabler is judged Small by its own rule, not by the units of the stories it enables."""

    def test_enabler_with_many_enabled_units_is_small(self):
        story = {
            "id": "US-010", "title": "Build screen", "type": "cross_cutting_enabler", "enables": ["US-011"],
            "trace": ["CHG-001", "SPEC-U-001", "SPEC-U-002", "SPEC-U-003"], "source_unit": "", "source_units": [],
            "slicing": "Cross-Cutting Enabler / New Surface",
        }
        item = implementation_readiness_for_story(story)
        result = evaluate_story_quality(story, "Build a screen for the stories that use it", [], item)
        signal = result["invest_audit"]["S"]
        self.assertTrue(signal["passed"], signal)

    def test_project_enabler_keeps_legacy_small(self):
        story = {"id": "US-010", "title": "e", "type": "cross_cutting_enabler", "enables": ["US-011"],
                 "trace": ["SPEC-U-001", "SPEC-U-002", "SPEC-U-003"]}
        item = implementation_readiness_for_story(story)
        self.assertNotIn("source_units", item)


def set_lifecycle(project: str, story_id: str, status: str) -> None:
    lifecycle = dict(read_state(project).get("story_lifecycle") or {})
    lifecycle[story_id] = {"status": status, "owner": "ana"}
    update_state(project, story_lifecycle=lifecycle)


def units_of_stories(project: str, ids: list[str]) -> list[str]:
    out: list[str] = []
    for sid in ids:
        front = front_of(project, sid)
        grouped = front.get("source_units")
        if isinstance(grouped, list) and grouped:
            out += list(grouped)
        elif front.get("source_unit"):
            out.append(front["source_unit"])
    return out


class BorrCase(SnapshotWorkspaceCase):
    @classmethod
    def build_workspace(cls):
        tgb.tcn.ChangeNextSequence.build_workspace()

    def walk(self) -> None:
        tgb.tcn.ChangeNextSequence.test_each_row_of_the_table_in_order(self)


class RegroupKeepsStarted(BorrCase):
    """I-2: a regroup never deletes a change story already past backlog/ready."""

    def grouped(self) -> tuple[dict, str, list[str]]:
        self.walk()
        first = run_backlog()
        sid = next(s for s in first["stories"] if len(front_of("BORR", s).get("source_units") or []) >= 2)
        return first, sid, list(front_of("BORR", sid)["source_units"])

    def test_threshold_crossing_keeps_story_in_progress(self):
        first, sid, units = self.grouped()
        set_lifecycle("BORR", sid, "In Progress")
        with patch("sentinel.compilers.change_functionalities.story_size", lambda model=None: 1):
            res = run_backlog()
        self.assertIn(sid, res["stories"])
        self.assertEqual(list(front_of("BORR", sid)["source_units"]), units)
        self.assertEqual(read_state("BORR")["story_lifecycle"][sid]["status"], "In Progress")
        all_units = [u["id"] for u in read_change_units("BORR", "CHG-001")]
        self.assertEqual(sorted(units_of_stories("BORR", res["stories"])), sorted(all_units))  # each unit exactly once

    def test_threshold_crossing_regroups_draft_story(self):
        first, sid, units = self.grouped()
        with patch("sentinel.compilers.change_functionalities.story_size", lambda model=None: 1):
            res = run_backlog()
        self.assertNotIn(sid, res["stories"])  # nothing started: it may regroup

    def test_legacy_story_done_survives_upgrade(self):
        first, sid, units = self.grouped()
        text = (backlog_dir("BORR") / f"{sid}.md").read_text(encoding="utf-8")
        legacy = text.replace(f"id: {sid}", "id: US-090")
        legacy = re.sub(r"^source_units:\n(?:  - .*\n)+", "", legacy, flags=re.MULTILINE)
        legacy = legacy.replace(f"source_unit: {front_of('BORR', sid)['source_unit']}", f"source_unit: {units[0]}")
        for other in first["stories"]:
            (backlog_dir("BORR") / f"{other}.md").unlink()
        (backlog_dir("BORR") / "US-090.md").write_text(legacy, encoding="utf-8")
        set_lifecycle("BORR", "US-090", "Done")
        res = run_backlog()
        self.assertIn("US-090", res["stories"])
        self.assertEqual(front_of("BORR", "US-090")["source_unit"], units[0])
        self.assertEqual(read_state("BORR")["story_lifecycle"]["US-090"]["status"], "Done")
        all_units = [u["id"] for u in read_change_units("BORR", "CHG-001")]
        self.assertEqual(sorted(units_of_stories("BORR", res["stories"])), sorted(all_units))


class StrictGateBeforeWrites(BorrCase):
    """I-3: the strict backlog gate refuses before anything is written."""

    def test_strict_refusal_leaves_no_partial_output(self):
        self.walk()
        config = workspace_path("BORR") / "sentinel.config.yaml"
        config.write_text(config.read_text(encoding="utf-8") + "\nbacklog_gate:\n  threshold: 1.0\n  strict: true\n",
                          encoding="utf-8")
        for path in backlog_dir("BORR").glob("US-*.md"):
            path.unlink()
        epic = backlog_dir("BORR") / "EPIC-CHG-001.md"
        plan = backlog_dir("BORR") / "CHG-001" / "SLICE-PLAN.md"
        for path in (epic, plan):
            if path.exists():
                path.unlink()
        state_before = read_state("BORR")
        code, out = run_cli(["backlog", "BORR", "--change", "CHG-001"])
        self.assertEqual(code, 4, out)
        self.assertEqual(list(backlog_dir("BORR").glob("US-*.md")), [])
        self.assertFalse(epic.exists())
        self.assertFalse(plan.exists())
        after = read_state("BORR")
        self.assertEqual(after.get("story_lifecycle"), state_before.get("story_lifecycle"))
        self.assertEqual(after["changes"]["CHG-001"].get("backlog"), state_before["changes"]["CHG-001"].get("backlog"))
        self.assertEqual(after.get("story_gates"), state_before.get("story_gates"))


class RemovedUnitsPerUnit(SnapshotWorkspaceCase):
    """I-4: every unit lands in exactly one story; a REMOVED unit without `Afecta` keeps its own."""

    cid = "CHG-001"

    @classmethod
    def build_workspace(cls):
        build_matured_workspace("MIX", PROJECT_RAW, gap_acceptance_answer(PROJECT_EARS))
        cid = cls.cid = open_change("MIX")
        free = REMOVED_ROW.replace("GAP-ACCEPTANCE", "GAP-TECH-NFR").replace("- Afecta: US-002\n", "- Afecta: ninguna\n").replace(
            "conservar los datos cargados", "avisar al comprador que el alta quedó incompleta")
        Path("a.md").write_text("\n".join([REMOVED_ROW, free, MODIFIED_ROW, UNCHANGED_ROW]), encoding="utf-8")
        run_ok(["resolve-gaps", "MIX", "--source", "a.md", "--change", cid])
        run_ok(["brief", "MIX", "--change", cid])
        run_ok(["specs", "MIX", "--change", cid])

    def test_removed_unit_without_afecta_keeps_story(self):
        res = json.loads(run_ok(["backlog", "MIX", "--change", self.cid]))
        units = read_change_units("MIX", self.cid)
        removed = [u["id"] for u in units if u["delta"] == "REMOVED"]
        self.assertEqual(len(removed), 2, [(u["id"], u["delta"], u["ears"]) for u in units])
        recorded = read_json(workspace_path("MIX") / "state.json", {})["changes"][self.cid]["backlog"]
        self.assertEqual(len(recorded["dropped_units"]), 1)
        covered = units_of_stories("MIX", res["stories"])
        kept = [u for u in removed if u not in recorded["dropped_units"]]
        self.assertEqual(len(kept), 1)
        self.assertIn(kept[0], covered)
        every = [u["id"] for u in units]
        self.assertEqual(sorted(covered + recorded["dropped_units"]), sorted(every))  # exactly one place each


class NewSurfaceDocs(SnapshotWorkspaceCase):
    """M-3, M-5, M-7: a change with a new surface (the enablers workspace)."""

    @classmethod
    def build_workspace(cls):
        tep.ChangeEnablersPlan.build_workspace()
        cls.cid = tep.ChangeEnablersPlan.cid

    def test_new_surface_as_is_has_no_facts_of_other_screens(self):  # M-5
        harvest = workspace_path(tep.PID) / "01_discovery" / "harvest.json"
        data = read_json(harvest, {})
        data.setdefault("entries", []).append(
            {"kind": "fact", "block": "B6", "text": "La pantalla de listado muestra los proveedores activos", "ref": "otro.md:L1"})
        write_json(harvest, data)
        run_ok(["specs", tep.PID, "--change", self.cid])
        text = (workspace_path(tep.PID) / "03_specs" / self.cid / "specs.md").read_text(encoding="utf-8")
        head = re.search(rf"(?m)^## FUN-\d+ — {re.escape(tep.NEW)} \(", text)
        self.assertIsNotNone(head, text)
        body = text[head.start():].split(chr(10) + "## ", 1)[0]
        as_is = body.split("### As-is", 1)[1].split("### ", 1)[0]
        self.assertIn("sin dato registrado", as_is)
        self.assertNotIn("listado muestra", as_is)

    def test_change_slice_plan_is_worded_for_the_change(self):  # M-3
        res = json.loads(run_ok(["backlog", tep.PID, "--change", self.cid]))
        plan = (workspace_path(tep.PID) / res["slice_plan"]).read_text(encoding="utf-8")
        self.assertTrue(plan.startswith("# Plan de cortes de " + self.cid), plan[:80])
        self.assertNotIn("EPIC-002-cross-cutting-enablers", plan)
        self.assertIn(f"EPIC-{self.cid}", plan)

    def test_enabler_does_not_borrow_requirements(self):  # M-7
        res = json.loads(run_ok(["backlog", tep.PID, "--change", self.cid]))
        enabler = next(s for s in res["stories"] if tep.front(s)["type"] == "cross_cutting_enabler")
        text = (workspace_path(tep.PID) / "04_backlog" / f"{enabler}.md").read_text(encoding="utf-8")
        line = next(l for l in text.splitlines() if l.startswith("- Product requirement") or f"`{self.cid}`, `FUN-" in l)
        self.assertNotRegex(line, r"REQ-EARS-\d+")


if __name__ == "__main__":
    unittest.main()
