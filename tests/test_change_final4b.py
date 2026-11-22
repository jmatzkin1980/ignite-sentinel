"""IMP-393: final review of increment 4b (modificada_por on change stories, specs gate with deltas, options of --change)."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import SnapshotWorkspaceCase, build_matured_workspace, gap_acceptance_answer, run_ok  # noqa: E402
from sentinel.compilers.change_backlog import compile_change_backlog  # noqa: E402
from sentinel.errors import GateRefusal, InputError  # noqa: E402
from sentinel.core.markdown import parse_frontmatter  # noqa: E402
from sentinel.change_requirements import change_requirements_path  # noqa: E402
from sentinel.traceability import load_graph  # noqa: E402
from sentinel.workspace import read_json, workspace_path  # noqa: E402
from test_change_affected_stories import ANSWERS  # noqa: E402
from test_change_specs import ALL_ANSWERS, PROJECT_EARS, PROJECT_RAW, answer, open_change  # noqa: E402


def status_of(project: str, story_id: str, *statuses: str) -> None:
    for status in statuses:
        run_ok(["story-status", project, "--story", story_id, "--set", status, "--owner", "ana"])


class ChangeOnChangeStory(SnapshotWorkspaceCase):
    @classmethod
    def build_workspace(cls):
        build_matured_workspace("MIX", PROJECT_RAW, gap_acceptance_answer(PROJECT_EARS))
        cls.first = open_change("MIX")
        Path("a.md").write_text(ANSWERS, encoding="utf-8")
        run_ok(["resolve-gaps", "MIX", "--source", "a.md", "--change", cls.first])
        run_ok(["brief", "MIX", "--change", cls.first])
        run_ok(["specs", "MIX", "--change", cls.first])

    def test_modificada_por_on_a_change_story_survives_its_rerun(self):
        base = workspace_path("MIX")
        res = json.loads(run_ok(["backlog", "MIX", "--change", self.first]))
        original = res["stories"][0]
        status_of("MIX", original, "Ready", "In Progress", "In Review", "Done")
        second = open_change("MIX", "pedido2.md")
        Path("b.md").write_text(ANSWERS.replace("Afecta: US-001", f"Afecta: {original}"), encoding="utf-8")
        run_ok(["resolve-gaps", "MIX", "--source", "b.md", "--change", second])
        run_ok(["brief", "MIX", "--change", second])
        run_ok(["specs", "MIX", "--change", second])
        new = json.loads(run_ok(["backlog", "MIX", "--change", second]))
        self.assertEqual(new["change_requests"], new["stories"])
        front = parse_frontmatter((base / "04_backlog" / f"{original}.md").read_text(encoding="utf-8"))
        self.assertEqual(front["modificada_por"], new["stories"])
        self.assertEqual(front["change"], self.first)
        self.assertIn({"from": new["stories"][0], "to": original, "relation": "modifies"}, load_graph("MIX")["edges"])
        run_ok(["backlog", "MIX", "--change", self.first])
        again = parse_frontmatter((base / "04_backlog" / f"{original}.md").read_text(encoding="utf-8"))
        self.assertEqual(again["modificada_por"], new["stories"])
        self.assertEqual(again["status"], "Done")

    def test_stale_record_is_the_current_runs_set(self):
        run_ok(["backlog", "MIX", "--change", self.first])
        res = json.loads(run_ok(["backlog", "MIX", "--change", self.first]))
        self.assertEqual(res["stale"], [])
        recorded = read_json(workspace_path("MIX") / "state.json", {})["changes"][self.first]["backlog"]["stale"]
        self.assertEqual(recorded, ["US-001", "US-002"])

    def test_project_backlog_summary_counts_change_items(self):
        run_ok(["backlog", "MIX", "--change", self.first])
        run_ok(["backlog", "MIX"])
        pack = read_json(workspace_path("MIX") / "08_context_packs" / "implementation_readiness.json", {})
        self.assertEqual(pack["summary"]["stories_total"], len(pack["stories"]))
        self.assertGreater(len(pack["stories"]), 2)


class ChangeBacklogOptions(SnapshotWorkspaceCase):
    cid = "CHG-001"

    @classmethod
    def build_workspace(cls):
        run_ok(["init", "BORR"])
        cid = open_change("BORR")
        answer("BORR", cid, "a.md", ALL_ANSWERS)
        run_ok(["brief", "BORR", "--change", cid])
        run_ok(["specs", "BORR", "--change", cid])

    def report_path(self) -> Path:
        return workspace_path("BORR") / "03_specs" / self.cid / "change_specs_report.json"

    def test_delta_changed_in_place_makes_specs_stale(self):
        path = change_requirements_path(workspace_path("BORR"), self.cid)
        text = path.read_text(encoding="utf-8")
        self.assertIn("| MODIFIED |", text)
        path.write_text(text.replace("| MODIFIED |", "| ADDED |", 1), encoding="utf-8")
        with self.assertRaises(GateRefusal) as caught:
            compile_change_backlog("BORR", self.cid)
        self.assertIn("no está al día", str(caught.exception))

    def test_report_from_an_older_version_is_refused_specifically(self):
        report = read_json(self.report_path(), {})
        report.pop("deltas")
        self.report_path().write_text(json.dumps(report), encoding="utf-8")
        with self.assertRaises(GateRefusal) as caught:
            compile_change_backlog("BORR", self.cid)
        self.assertIn("versión anterior", str(caught.exception))
        self.assertEqual(caught.exception.next_step, f"/specs BORR --change {self.cid}")
        report["deltas"] = None
        self.report_path().write_text(json.dumps(report), encoding="utf-8")
        with self.assertRaises(GateRefusal) as caught:
            compile_change_backlog("BORR", self.cid)
        self.assertIn("versión anterior", str(caught.exception))

    def test_story_format_job_applies_and_task_seeds_are_refused(self):
        with self.assertRaises(InputError) as caught:
            compile_change_backlog("BORR", self.cid, with_task_seeds=True)
        self.assertIn("--with-task-seeds", str(caught.exception))
        self.assertFalse((workspace_path("BORR") / "04_backlog" / "EPIC-CHG-001.md").exists())
        res = json.loads(run_ok(["backlog", "BORR", "--change", self.cid, "--story-format", "job"]))
        text = (workspace_path("BORR") / "04_backlog" / f"{res['stories'][0]}.md").read_text(encoding="utf-8")
        self.assertIn("## Job Story", text)


if __name__ == "__main__":
    unittest.main()
