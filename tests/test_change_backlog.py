"""IMP-393: `/backlog --change` builds one story per spec unit of a change, under an epic of its own."""
from __future__ import annotations

import io
import json
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import SnapshotWorkspaceCase, build_matured_workspace, gap_acceptance_answer, run_cli, run_ok  # noqa: E402
from sentinel import mcp as sentinel_mcp  # noqa: E402
from sentinel.cli import main as cli_main  # noqa: E402
from sentinel.compilers.change_backlog import compile_change_backlog  # noqa: E402
from sentinel.core.markdown import parse_frontmatter  # noqa: E402
from sentinel.errors import GateRefusal  # noqa: E402
from sentinel.traceability import load_graph  # noqa: E402
from sentinel.workspace import read_json, update_state, workspace_path  # noqa: E402
from test_change_specs import (  # noqa: E402
    ALL_ANSWERS, EXTRA, PROJECT_EARS, PROJECT_RAW, answer, open_change, units_dir,
)
from test_mcp_parity import _tools  # noqa: E402

PROJECT_TRACE = ("REQ-001", "PRD-001", "SPEC-001")


def backlog_dir(project: str) -> Path:
    return workspace_path(project) / "04_backlog"


def story(project: str, story_id: str) -> str:
    return (backlog_dir(project) / f"{story_id}.md").read_text(encoding="utf-8")


def readiness(project: str) -> dict:
    return read_json(workspace_path(project) / "08_context_packs" / "implementation_readiness.json", {})


def state(project: str) -> dict:
    return read_json(workspace_path(project) / "state.json", {})


class ChangeBacklog(SnapshotWorkspaceCase):
    cid = "CHG-001"

    @classmethod
    def build_workspace(cls):
        run_ok(["init", "BORR"])
        cid = open_change("BORR")
        answer("BORR", cid, "a.md", ALL_ANSWERS)
        run_ok(["brief", "BORR", "--change", cid])
        run_ok(["specs", "BORR", "--change", cid])

    def run_backlog(self) -> dict:
        return json.loads(run_ok(["backlog", "BORR", "--change", self.cid]))

    def test_builds_stories_under_change_epic(self):
        res = self.run_backlog()
        self.assertEqual(res["stories"], ["US-001", "US-002"])  # IMP-416: one story per functionality x delta
        self.assertEqual(res["epic"], "EPIC-CHG-001")
        self.assertEqual((res["change_requests"], res["stale"], res["warnings"]), ([], [], []))
        epic = (backlog_dir("BORR") / "EPIC-CHG-001.md").read_text(encoding="utf-8")
        self.assertIn("guardar borrador", epic.lower())
        self.assertFalse((backlog_dir("BORR") / "EPIC-001.md").exists())
        covered: list[str] = []
        for story_id in res["stories"]:
            text = story("BORR", story_id)
            front = parse_frontmatter(text)
            self.assertEqual(front["parent_epic"], "EPIC-CHG-001")
            self.assertEqual(front["change"], self.cid)
            self.assertEqual(front["source_unit"], front["source_units"][0])
            covered += front["source_units"]
            self.assertIn(front["delta"], ("ADDED", "MODIFIED"))
            for unit_id in front["source_units"]:
                unit_front = parse_frontmatter((units_dir("BORR") / f"{unit_id}.md").read_text(encoding="utf-8"))
                self.assertEqual(front["delta"], unit_front["delta"])
            self.assertEqual(front["type"], "value_story")
            self.assertEqual(front["trace"][0], self.cid)
            self.assertEqual(front["trace"], sorted(front["trace"]))
            self.assertTrue(set(front["source_units"]) <= set(front["trace"]))
            self.assertNotIn(", ".join(PROJECT_TRACE), text)
            self.assertNotIn("`REQ-001`, `PRD-001`", text)
            self.assertEqual(len(front["trace"]), 1 + 2 * len(front["source_units"]))
            self.assertTrue(any(t.startswith("REQ-EARS-") for t in front["trace"]))
        self.assertEqual(sorted(covered), sorted(p.stem for p in units_dir("BORR").glob("SPEC-U-*.md")))
        graph = load_graph("BORR")
        nodes = {n["id"]: n for n in graph["nodes"]}
        self.assertEqual(nodes["EPIC-CHG-001"]["type"], "epic")
        self.assertEqual({k for k in nodes if k.startswith("EPIC-")}, {"EPIC-CHG-001"})
        for story_id in res["stories"]:
            self.assertEqual(nodes[story_id]["type"], "user_story")
            self.assertIn({"from": "EPIC-CHG-001", "to": story_id, "relation": "contains"}, graph["edges"])
        self.assertNotIn("EPIC-003", nodes)

    def test_state_next_step_and_board(self):
        before_phase = state("BORR")["phase"]
        res = self.run_backlog()
        after = state("BORR")
        self.assertEqual(after["phase"], before_phase)
        record = after["changes"][self.cid]["backlog"]
        self.assertEqual(record["stories"], res["stories"])
        self.assertEqual(record["change_requests"], [])
        self.assertTrue(record["generated_at"])
        self.assertNotIn("prd", res["next_step"].lower())
        self.assertIn("BACKLOG.md", res["next_step"])
        board = (backlog_dir("BORR") / "BACKLOG.md").read_text(encoding="utf-8")
        self.assertIn("EPIC-CHG-001", board)
        self.assertIn("US-002", board)

    def test_unchanged_rows_become_pass_to_pass(self):
        res = self.run_backlog()
        self.assertEqual(len(res["report"]["pass_to_pass"]), 1)
        for index, story_id in enumerate(res["stories"], start=1):
            text = story("BORR", story_id)
            n = len(parse_frontmatter(text)["source_units"])  # IMP-416: a happy path per unit, 3 shared, evidence, then preserved
            evidence, preserved_ac = f"AC-{index:03d}-{n + 4:02d}", f"AC-{index:03d}-{n + 5:02d}"
            row = next(line for line in text.splitlines() if line.startswith(f"| {preserved_ac} |"))
            self.assertIn("pass-to-pass", row)
            self.assertIn("el comportamiento preservado sigue igual", row)
            self.assertIn("continuar validando los datos", row)
            self.assertIn(res["report"]["pass_to_pass"][0], row)
            self.assertIn(f"{evidence} | evidence", text)
            pass_to_pass = next(line for line in text.splitlines() if line.startswith("| Pass-to-Pass |"))
            self.assertIn(f"AC-{index:03d}-{n + 3:02d}", pass_to_pass)
            self.assertIn(preserved_ac, pass_to_pass)
            item = next(i for i in readiness("BORR")["stories"] if i["story_id"] == story_id)
            self.assertIn(preserved_ac, item["validation"]["pass_to_pass"])

    def test_readiness_and_lifecycle_start_draft(self):
        res = self.run_backlog()
        items = {i["story_id"]: i for i in readiness("BORR")["stories"]}
        self.assertEqual(sorted(items), res["stories"])
        self.assertEqual(items["US-001"]["source_units"][0], items["US-001"]["source_unit"])
        self.assertEqual(sorted(u for i in items.values() for u in i["source_units"]), ["SPEC-U-001", "SPEC-U-002", "SPEC-U-003"])
        lifecycle = state("BORR")["story_lifecycle"]
        for story_id in res["stories"]:
            self.assertEqual(lifecycle[story_id]["status"], "Draft")

    def test_story_status_works_on_change_story(self):
        self.run_backlog()
        run_ok(["story-status", "BORR", "--story", "US-001", "--set", "Ready", "--owner", "ana"])
        self.assertEqual(state("BORR")["story_lifecycle"]["US-001"]["status"], "Ready")
        again = self.run_backlog()
        self.assertEqual(again["stories"], ["US-001", "US-002"])
        self.assertEqual(state("BORR")["story_lifecycle"]["US-001"]["status"], "Ready")
        self.assertEqual(state("BORR")["story_lifecycle"]["US-001"]["owner"], "ana")
        self.assertIn("status: Ready", story("BORR", "US-001"))

    def test_rerun_with_same_inputs_is_identical(self):
        self.run_backlog()
        files = ["EPIC-CHG-001.md", "US-001.md", "US-002.md"]
        before = {n: (backlog_dir("BORR") / n).read_text(encoding="utf-8") for n in files}
        context = (workspace_path("BORR") / "08_context_packs" / self.cid / "backlog_generation.json").read_text(encoding="utf-8")
        self.run_backlog()
        self.run_backlog()
        for name, text in before.items():
            self.assertEqual((backlog_dir("BORR") / name).read_text(encoding="utf-8"), text, name)
        after = (workspace_path("BORR") / "08_context_packs" / self.cid / "backlog_generation.json").read_text(encoding="utf-8")
        self.assertEqual(after, context)

    def test_rerun_removes_superseded_story_keeps_ids(self):
        self.run_backlog()
        kept = story("BORR", "US-001")
        (units_dir("BORR") / "SPEC-U-001.md").unlink()  # the MODIFIED unit: its story (US-002) has no unit left
        second = self.run_backlog()
        self.assertEqual(second["stories"], ["US-001"])
        self.assertEqual(second["report"]["removed"], ["US-002"])
        self.assertFalse((backlog_dir("BORR") / "US-002.md").exists())
        self.assertEqual(story("BORR", "US-001").count("US-001"), kept.count("US-001"))
        self.assertEqual([i["story_id"] for i in readiness("BORR")["stories"]], ["US-001"])
        self.assertNotIn("US-002", state("BORR")["story_lifecycle"])
        self.assertNotIn("US-002", {n["id"] for n in load_graph("BORR")["nodes"]})
        # the unit comes back with its own id: the story gets its old number back, never another one
        answer("BORR", self.cid, "b.md", EXTRA)
        run_ok(["specs", "BORR", "--change", self.cid])
        third = self.run_backlog()
        self.assertEqual(third["stories"], ["US-001", "US-002"])  # the ADDED story takes the extra unit, the MODIFIED one is back

    def test_refuses_without_change_specs(self):
        (workspace_path("BORR") / "03_specs" / self.cid / "specs.md").unlink()
        with self.assertRaises(GateRefusal) as caught:
            compile_change_backlog("BORR", self.cid)
        self.assertIn("03_specs/CHG-001/specs.md", str(caught.exception))
        self.assertEqual(caught.exception.next_step, f"/specs BORR --change {self.cid}")
        run_ok(["specs", "BORR", "--change", self.cid])
        for path in units_dir("BORR").glob("SPEC-U-*.md"):
            path.unlink()
        with self.assertRaises(GateRefusal) as caught:
            compile_change_backlog("BORR", self.cid)
        self.assertEqual(caught.exception.next_step, f"/specs BORR --change {self.cid}")
        self.assertFalse((backlog_dir("BORR") / "EPIC-CHG-001.md").exists())

    def test_refusal_after_forget_keeps_memory_indexed(self):
        from sentinel.memory import ContextBroker

        self.run_backlog()
        with patch("sentinel.backlog.hooks.assert_backlog_privacy_clean", side_effect=GateRefusal("privacy")):
            with self.assertRaises(GateRefusal) as caught:
                compile_change_backlog("BORR", self.cid)
        self.assertEqual(str(caught.exception), "privacy")
        indexed = {a["artifact_id"] for a in ContextBroker("BORR").data.get("artifacts", [])}
        self.assertTrue({"EPIC-CHG-001", "US-001", "US-002", "IMPL-READINESS"} <= indexed)
        for story_id in ("US-001", "EPIC-CHG-001", "IMPL-READINESS"):
            rows = ContextBroker("BORR").retrieve(story_id, "test", limit=20)
            self.assertIn(story_id, {r["artifact_id"] for r in rows})

    def test_refuses_with_blocking_gap_open(self):
        changes = state("BORR")["changes"]
        changes[self.cid]["gap_counts"]["blocking_open"] = 2
        update_state("BORR", changes=changes)
        with self.assertRaises(GateRefusal) as caught:
            compile_change_backlog("BORR", self.cid)
        self.assertIn("2 gap(s) bloqueante(s)", str(caught.exception))
        self.assertEqual(caught.exception.next_step, f"/resolve-gaps BORR --change {self.cid}")
        self.assertFalse((backlog_dir("BORR") / "EPIC-CHG-001.md").exists())

    def test_refuses_when_specs_are_stale(self):
        answer("BORR", self.cid, "b.md", EXTRA)  # a new row after /specs --change
        for language, fragment in (("es", "no está al día"), ("en", "is not current")):
            changes = state("BORR")["changes"]
            changes[self.cid]["language"] = language
            update_state("BORR", changes=changes)
            with self.assertRaises(GateRefusal) as caught:
                compile_change_backlog("BORR", self.cid)
            self.assertIn(fragment, str(caught.exception))
            self.assertEqual(caught.exception.next_step, f"/specs BORR --change {self.cid}")
        self.assertFalse((backlog_dir("BORR") / "EPIC-CHG-001.md").exists())
        run_ok(["specs", "BORR", "--change", self.cid])
        self.assertEqual(len(self.run_backlog()["stories"]), 2)  # IMP-416: the extra ADDED row joins its group

    def test_english_change_gets_english_text(self):
        changes = state("BORR")["changes"]
        changes[self.cid]["language"] = "en"
        update_state("BORR", changes=changes)
        res = self.run_backlog()
        self.assertTrue(res["next_step"].startswith("Review the board"))
        epic = (backlog_dir("BORR") / "EPIC-CHG-001.md").read_text(encoding="utf-8")
        self.assertIn("Deliver the change CHG-001", epic)
        self.assertIn("## Preserved behavior", epic)
        n = len(parse_frontmatter(story("BORR", "US-001"))["source_units"])
        row = next(line for line in story("BORR", "US-001").splitlines() if line.startswith(f"| AC-001-{n + 5:02d} |"))
        self.assertIn("the preserved behavior stays the same", row)
        self.assertNotIn("sigue igual", row)

    def test_unknown_change_refused(self):
        code, _ = run_cli(["backlog", "BORR", "--change", "CHG-009"])
        self.assertEqual(code, 4)

    def test_cli_mcp_and_release_refusal(self):
        code, out = run_cli(["backlog", "BORR", "--change", self.cid])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["change_id"], self.cid)
        code, _ = run_cli(["backlog", "BORR", "--change", self.cid, "--release", "r1"])
        self.assertEqual(code, 3)
        err = io.StringIO()
        with redirect_stderr(err), redirect_stdout(io.StringIO()):
            cli_main(["backlog", "BORR", "--change", self.cid, "--release", "r1"])
        self.assertIn("/backlog --change no se combina con --release", err.getvalue())
        captured: list[list[str]] = []
        with patch.object(sentinel_mcp, "run_cli", lambda arguments: captured.append(arguments) or {"exit_code": 0}):
            _tools()["sentinel_backlog"](project_id="BORR", change=self.cid)
            _tools()["sentinel_backlog"](project_id="BORR")
        self.assertEqual(captured[0], ["backlog", "BORR", "--change", self.cid])
        self.assertEqual(captured[1], ["backlog", "BORR"])

    def test_plain_backlog_in_change_only_workspace_refuses(self):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = cli_main(["backlog", "BORR"])
        self.assertEqual(code, 4)
        self.assertIn(f"/backlog BORR --change {self.cid}", err.getvalue() + out.getvalue())
        self.assertFalse((backlog_dir("BORR") / "EPIC-CHG-001.md").exists())


class ChangeBacklogWithProject(SnapshotWorkspaceCase):
    @classmethod
    def build_workspace(cls):
        build_matured_workspace("MIX", PROJECT_RAW, gap_acceptance_answer(PROJECT_EARS))
        cid = open_change("MIX")
        cls.cid = cid
        answer("MIX", cid, "a.md", ALL_ANSWERS.replace("- Delta: MODIFIED\n", "- Delta: MODIFIED\n- Afecta: ninguna\n"))
        run_ok(["brief", "MIX", "--change", cid])
        run_ok(["specs", "MIX", "--change", cid])

    def snapshot(self) -> dict[str, str]:
        return {p.name: p.read_text(encoding="utf-8") for p in sorted(backlog_dir("MIX").glob("*.md"))
                if p.name.startswith(("US-", "EPIC-001"))}

    def test_project_stories_untouched(self):
        before = self.snapshot()
        self.assertEqual(sorted(before), ["EPIC-001.md", "US-001.md", "US-002.md"])
        res = json.loads(run_ok(["backlog", "MIX", "--change", self.cid]))
        self.assertEqual(res["stories"], ["US-003", "US-004"])
        self.assertEqual({k: v for k, v in self.snapshot().items() if k in before}, before)
        self.assertNotIn("change:", before["US-001.md"])
        items = {i["story_id"] for i in readiness("MIX")["stories"]}
        self.assertTrue({"US-001", "US-002", "US-003", "US-004"} <= items)
        epics = {n["id"] for n in load_graph("MIX")["nodes"] if n["type"] == "epic"}
        self.assertIn("EPIC-001", epics)
        self.assertIn(f"EPIC-{self.cid}", epics)
        self.assertEqual({e for e in epics if e.startswith("EPIC-CHG")}, {f"EPIC-{self.cid}"})

    def test_project_backlog_after_change_keeps_change_stories(self):
        run_ok(["backlog", "MIX", "--change", self.cid])
        change_files = {n: (backlog_dir("MIX") / n).read_text(encoding="utf-8")
                        for n in ("US-003.md", "US-004.md", f"EPIC-{self.cid}.md")}
        run_ok(["backlog", "MIX"])
        for name, text in change_files.items():
            self.assertEqual((backlog_dir("MIX") / name).read_text(encoding="utf-8"), text)
        self.assertEqual(state("MIX")["story_lifecycle"]["US-004"]["status"], "Draft")
        items = {i["story_id"] for i in readiness("MIX")["stories"]}
        self.assertTrue({"US-003", "US-004", "US-005"} <= items)


if __name__ == "__main__":
    unittest.main()
