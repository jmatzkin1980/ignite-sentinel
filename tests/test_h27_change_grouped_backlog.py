"""IMP-416: `/backlog --change` builds stories grouped by functionality, not one per spec unit."""
from __future__ import annotations

import io
import json
import re
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import SnapshotWorkspaceCase, build_matured_workspace, export_final_brief, gap_acceptance_answer, run_ok  # noqa: E402
from sentinel.cli import main as cli_main  # noqa: E402
from sentinel.compilers.change_backlog import read_change_units  # noqa: E402
from sentinel.core.markdown import parse_frontmatter  # noqa: E402
from sentinel.readiness_verdict import _backlog_behind, change_next_step  # noqa: E402
from sentinel.workspace import read_json, workspace_path  # noqa: E402
from test_change_affected_stories import ANSWERS as REMOVED_ANSWERS  # noqa: E402
import test_change_next as tcn  # noqa: E402
from test_change_specs import EXTRA, PROJECT_EARS, PROJECT_RAW, answer, open_change  # noqa: E402

CID = "CHG-001"
SOURCE_UNITS_BLOCK = re.compile(r"^source_units:\n(?:  - .*\n)+", re.MULTILINE)


def backlog_dir(project: str) -> Path:
    return workspace_path(project) / "04_backlog"


def front_of(project: str, story_id: str) -> dict:
    return parse_frontmatter((backlog_dir(project) / f"{story_id}.md").read_text(encoding="utf-8"))


def run_backlog(project: str = "BORR", cid: str = CID) -> dict:
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = cli_main(["backlog", project, "--change", cid])
    assert code == 0, (code, err.getvalue()[-1500:])
    return json.loads(out.getvalue())


class GroupedChangeBacklog(SnapshotWorkspaceCase):
    @classmethod
    def build_workspace(cls):
        tcn.ChangeNextSequence.build_workspace()

    def walk(self) -> None:
        """The sequence of /next up to done: it runs /specs and /backlog --change on the way."""
        tcn.ChangeNextSequence.test_each_row_of_the_table_in_order(self)

    def test_grouped_stories_cover_units(self):
        self.walk()
        res = run_backlog()
        self.assertEqual(len(res["stories"]), 2)
        deltas, covered = [], []
        for story_id in res["stories"]:
            front = front_of("BORR", story_id)
            self.assertIsInstance(front["source_units"], list)
            self.assertEqual(front["source_unit"], front["source_units"][0])
            deltas.append((front["delta"], len(front["source_units"])))
            covered += front["source_units"]
            self.assertEqual(res["slices"][story_id]["units"], front["source_units"])
        self.assertEqual(sorted(deltas), [("ADDED", 2), ("MODIFIED", 1)])
        all_units = [u["id"] for u in read_change_units("BORR", CID)]
        self.assertEqual(sorted(covered), sorted(all_units))
        self.assertEqual(len(covered), len(set(covered)))
        self.assertEqual(res["report"]["slices"], res["slices"])
        self.assertEqual(set(res["slices"][res["stories"][0]]), {"functionality", "units", "axis"})
        epic = (backlog_dir("BORR") / "EPIC-CHG-001.md").read_text(encoding="utf-8")
        self.assertIn("| Story | Delta | Functionality | Units | Title |".replace("Story", "Historia").replace("Functionality", "Funcionalidad").replace("Units", "Unidades").replace("Title", "Título"), epic)

    def test_next_leaves_backlog_after_grouping(self):
        self.walk()
        run_backlog()
        units = read_change_units("BORR", CID)
        self.assertFalse(_backlog_behind(workspace_path("BORR"), CID, units, []))
        self.assertNotEqual(change_next_step("BORR", CID)["key"], "backlog")

    def test_rerun_same_ids(self):
        self.walk()
        first = run_backlog()
        names = ["EPIC-CHG-001.md", *(f"{sid}.md" for sid in first["stories"])]
        before = {n: (backlog_dir("BORR") / n).read_bytes() for n in names}
        second = run_backlog()
        self.assertEqual(second["stories"], first["stories"])
        self.assertEqual({n: (backlog_dir("BORR") / n).read_bytes() for n in names}, before)
        added = next(sid for sid in first["stories"] if front_of("BORR", sid)["delta"] == "ADDED")
        answer("BORR", CID, "b.md", EXTRA)
        export_final_brief("BORR", CID)
        run_ok(["specs", "BORR", "--change", CID])
        third = run_backlog()
        self.assertEqual(third["stories"], first["stories"])
        self.assertEqual(len(front_of("BORR", added)["source_units"]), 3)

    def test_one_retrieval_per_story(self):
        self.walk()
        from sentinel.compilers import slicing

        real = slicing.build_story_backlog_context
        with patch.object(slicing, "build_story_backlog_context", side_effect=real) as spy:
            res = run_backlog()
        self.assertEqual(spy.call_count, len(res["stories"]))
        self.assertLessEqual(len(res["stories"]), 8)

    def test_old_story_frontmatter_still_read(self):
        self.walk()
        res = run_backlog()
        path = backlog_dir("BORR") / f"{res['stories'][0]}.md"
        units_of = {sid: front_of("BORR", sid)["source_units"] for sid in res["stories"]}
        # 0.31 wrote one story per unit with a scalar `source_unit` and no `source_units`
        for sid in res["stories"]:
            file = backlog_dir("BORR") / f"{sid}.md"
            file.write_text(SOURCE_UNITS_BLOCK.sub("", file.read_text(encoding="utf-8")), encoding="utf-8")
        units = read_change_units("BORR", CID)
        self.assertTrue(_backlog_behind(workspace_path("BORR"), CID, units, []))  # the second unit of the group has no story
        legacy = path.read_text(encoding="utf-8").replace(f"id: {res['stories'][0]}", "id: US-090").replace(
            f"source_unit: {units_of[res['stories'][0]][0]}", f"source_unit: {units_of[res['stories'][0]][1]}")
        (backlog_dir("BORR") / "US-090.md").write_text(legacy, encoding="utf-8")
        self.assertFalse(_backlog_behind(workspace_path("BORR"), CID, units, []))
        (backlog_dir("BORR") / "US-090.md").unlink()
        again = run_backlog()  # the regrouping goes through the removal path and rewrites `source_units`
        self.assertEqual(again["stories"], res["stories"])
        self.assertEqual({sid: front_of("BORR", sid)["source_units"] for sid in again["stories"]}, units_of)


class GroupedRemovedBacklog(SnapshotWorkspaceCase):
    cid = CID

    @classmethod
    def build_workspace(cls):
        build_matured_workspace("MIX", PROJECT_RAW, gap_acceptance_answer(PROJECT_EARS))
        cid = cls.cid = open_change("MIX")
        Path("a.md").write_text(REMOVED_ANSWERS, encoding="utf-8")
        run_ok(["resolve-gaps", "MIX", "--source", "a.md", "--change", cid])
        run_ok(["brief", "MIX", "--change", cid])
        run_ok(["specs", "MIX", "--change", cid])

    def test_removed_group_drops_all_units(self):
        res = run_backlog("MIX", self.cid)
        units = read_change_units("MIX", self.cid)
        removed = [u["id"] for u in units if u["delta"] == "REMOVED"]
        self.assertTrue(removed)
        recorded = read_json(workspace_path("MIX") / "state.json", {})["changes"][self.cid]["backlog"]
        self.assertEqual(sorted(recorded["dropped_units"]), sorted(removed))
        self.assertEqual({front_of("MIX", sid)["delta"] for sid in res["stories"]}, {"MODIFIED"})
        self.assertFalse(_backlog_behind(workspace_path("MIX"), self.cid, units, recorded["dropped_units"]))


if __name__ == "__main__":
    unittest.main()
