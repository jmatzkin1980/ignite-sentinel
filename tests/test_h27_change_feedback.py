"""IMP-433: `/implementation-feedback` checks and marks the units of the stories of a change."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import SnapshotWorkspaceCase, run_cli, run_ok  # noqa: E402
from change_inc8b_flow import BASELINE, build_project_outputs, project_output_hashes  # noqa: E402
from sentinel.backlog.hooks import mark_stale_stories_for_spec_units, story_spec_units  # noqa: E402
from sentinel.compilers.change_backlog import _change_story_ids, read_change_units  # noqa: E402
from sentinel.core.graph import load_graph  # noqa: E402
from sentinel.core.io import forget_read_snapshots  # noqa: E402
from sentinel.core.markdown import parse_frontmatter  # noqa: E402
from sentinel.workspace import read_json, workspace_path  # noqa: E402
import test_change_next as tcn  # noqa: E402
import test_h27_change_grouped_backlog as grouped  # noqa: E402

CID = "CHG-001"
REPORT = Path("07_changes") / "05_implementation_feedback" / "feedback_report.md"


def finding(story: str, **extra) -> dict:
    return {"type": "surface-not-covered", "story": story, "summary": "The draft list loses the last entry.",
            "evidence": "Implementation test run: the last draft is missing after saving.", "source": "test run", **extra}


def feedback(project: str, name: str, findings: list[dict]) -> tuple[int, str]:
    path = Path(name)
    path.write_text(json.dumps({"findings": findings}), encoding="utf-8")
    return run_cli(["implementation-feedback", project, "--source", str(path)])


class BorrWithBacklog(SnapshotWorkspaceCase):
    @classmethod
    def build_workspace(cls):
        tcn.ChangeNextSequence.build_workspace()
        tcn.ChangeNextSequence.test_each_row_of_the_table_in_order(unittest.TestCase())

    def setUp(self):
        super().setUp()
        forget_read_snapshots()
        self.base = workspace_path("BORR")

    def grouped_story(self) -> tuple[str, list[str]]:
        for story in _change_story_ids(self.base, CID):
            units = parse_frontmatter((self.base / "04_backlog" / f"{story}.md").read_text(encoding="utf-8")).get("source_units", [])
            if len(units) >= 2:
                return story, list(units)
        raise AssertionError("no grouped story in the fixture")

    def test_change_story_unknown_unit_rejected(self):
        story = _change_story_ids(self.base, CID)[0]
        code, _out = feedback("BORR", "f.json", [finding(story, source_units=["SPEC-U-999"])])
        self.assertNotEqual(code, 0)
        report = (self.base / REPORT).read_text(encoding="utf-8")
        self.assertIn("source unit does not exist for CHG-001: SPEC-U-999", report)

    def test_change_story_own_unit_accepted(self):
        story, units = self.grouped_story()
        out = json.loads(run_ok(["implementation-feedback", "BORR", "--source", self._write("g.json", [finding(story, source_units=units)])]))
        self.assertEqual(out["rejected"], [])
        self.assertEqual(len(out["accepted"]), 1)
        edges = [(e["from"], e["relation"]) for e in load_graph("BORR")["edges"] if e["to"] == out["feedback_id"]]
        self.assertIn((CID, "feedback_for"), edges)

    def _write(self, name: str, findings: list[dict]) -> str:
        Path(name).write_text(json.dumps({"findings": findings}), encoding="utf-8")
        return name

    def test_change_story_mark_stale_grouped(self):
        story, units = self.grouped_story()
        pack = self.base / "08_context_packs" / "implementation_readiness.json"
        data = read_json(pack, {})
        item = next(i for i in data["stories"] if i["story_id"] == story)
        self.assertEqual(item["source_units"], units)
        item["trace"] = [t for t in item.get("trace", []) if t != units[1]]
        pack.write_text(json.dumps(data), encoding="utf-8")
        forget_read_snapshots()
        self.assertEqual(story_spec_units({"source_unit": units[0], "trace": [], "source_units": units}), set(units))
        result = mark_stale_stories_for_spec_units("BORR", [units[1]], "test")
        self.assertEqual(result["stale_stories"], [story])
        forget_read_snapshots()
        front = parse_frontmatter((self.base / "04_backlog" / f"{story}.md").read_text(encoding="utf-8"))
        self.assertEqual(front["status"], "Stale")

    def test_feedback_mark_stale_by_second_unit(self):
        story, units = self.grouped_story()
        run_ok(["implementation-feedback", "BORR", "--source", self._write("s.json", [finding(story, source_units=[units[1]], mark_stale=True)])])
        forget_read_snapshots()
        front = parse_frontmatter((self.base / "04_backlog" / f"{story}.md").read_text(encoding="utf-8"))
        self.assertEqual(front["status"], "Stale")

    def test_story_of_a_missing_change_does_not_refuse_the_run(self):
        """M6 (review inc 8b): a story naming a change no longer in state leaves the other findings alone."""
        (self.base / "04_backlog" / "US-990.md").write_text("---\nid: US-990\nchange: CHG-009\n---\n\n# US-990\n", encoding="utf-8")
        story = _change_story_ids(self.base, CID)[0]
        out = json.loads(run_ok(["implementation-feedback", "BORR", "--source", self._write("x.json", [finding(story)])]))
        self.assertEqual(len(out["accepted"]), 1)
        code, _out = feedback("BORR", "y.json", [finding("US-990", source_units=["SPEC-U-001"])])
        self.assertNotEqual(code, 0)
        self.assertIn("source unit does not exist for CHG-009: SPEC-U-001", (self.base / REPORT).read_text(encoding="utf-8"))

    def test_change_only_report_has_change_column(self):
        story = _change_story_ids(self.base, CID)[0]
        run_ok(["implementation-feedback", "BORR", "--source", self._write("c.json", [finding(story)])])
        report = (self.base / REPORT).read_text(encoding="utf-8")
        self.assertIn("| Finding | Type | Story | Change | AC | Status | Marks Stale | Summary |", report)


class MixWithChangeBacklog(SnapshotWorkspaceCase):
    @classmethod
    def build_workspace(cls):
        grouped.GroupedRemovedBacklog.build_workspace.__func__(cls)
        run_ok(["backlog", "MIX", "--change", cls.cid])

    def test_feedback_report_change_column(self):
        base = workspace_path("MIX")
        own = _change_story_ids(base, type(self).cid)[0]
        project = sorted({p.stem for p in (base / "04_backlog").glob("US-*.md")} - set(_change_story_ids(base, type(self).cid)))[0]
        Path("m.json").write_text(json.dumps({"findings": [finding(project), finding(own)]}), encoding="utf-8")
        run_ok(["implementation-feedback", "MIX", "--source", "m.json"])
        report = (base / REPORT).read_text(encoding="utf-8")
        self.assertIn("| Finding | Type | Story | Change | AC |", report)
        rows = {ln.split("|")[3].strip(" `"): ln.split("|")[4].strip() for ln in report.splitlines() if ln.startswith("| `IFB-")}
        self.assertEqual(rows[own], type(self).cid)
        self.assertEqual(rows[project], "N/A")

    def test_project_story_keeps_project_report_shape(self):
        base = workspace_path("MIX")
        project = sorted({p.stem for p in (base / "04_backlog").glob("US-*.md")} - set(_change_story_ids(base, type(self).cid)))[0]
        Path("p.json").write_text(json.dumps({"findings": [finding(project, source_units=["SPEC-U-001"])]}), encoding="utf-8")
        run_ok(["implementation-feedback", "MIX", "--source", "p.json"])
        report = (base / REPORT).read_text(encoding="utf-8")
        self.assertIn("| Finding | Type | Story | AC | Status | Marks Stale | Summary |", report)
        self.assertNotIn("Change |", report)

    def test_change_story_rejects_unit_of_nobody(self):
        base = workspace_path("MIX")
        own = _change_story_ids(base, type(self).cid)[0]
        units = [u["id"] for u in read_change_units("MIX", type(self).cid)]
        code, _out = feedback("MIX", "n.json", [finding(own, source_units=["SPEC-U-998"])])
        self.assertNotEqual(code, 0)
        self.assertTrue(units)

    def test_change_story_rejects_project_unit(self):
        """I2 (review inc 8b): a story of a change answers only for its change's units; a project unit is refused (like refine),
        so a change-scoped finding never marks a project story Stale."""
        cid = type(self).cid
        base = workspace_path("MIX")
        own = _change_story_ids(base, cid)[0]
        change_units = {u["id"] for u in read_change_units("MIX", cid)}
        project_unit = next(p.stem for p in sorted((base / "03_specs" / "units").glob("SPEC-U-*.md")) if p.stem not in change_units)
        project_stories = sorted({p.stem for p in (base / "04_backlog").glob("US-*.md")} - set(_change_story_ids(base, cid)))
        before = {sid: (base / "04_backlog" / f"{sid}.md").read_bytes() for sid in project_stories}
        code, _out = feedback("MIX", "pu.json", [finding(own, source_units=[project_unit], mark_stale=True)])
        self.assertNotEqual(code, 0)
        report = (base / REPORT).read_text(encoding="utf-8")
        self.assertIn(f"source unit does not exist for {cid}: {project_unit}", report)
        self.assertEqual({sid: (base / "04_backlog" / f"{sid}.md").read_bytes() for sid in project_stories}, before)


class ProjectFeedbackBytes(SnapshotWorkspaceCase):
    @classmethod
    def build_workspace(cls):
        build_project_outputs(Path.cwd())

    def test_project_feedback_bytes_unchanged(self):
        """RF 3: the project report has no Change column and every byte of the three outputs is as before IMP-433."""
        self.assertEqual(project_output_hashes(self.temp), json.loads(BASELINE.read_text(encoding="utf-8")))
        report = (self.temp / "workspaces" / "BASE" / REPORT).read_text(encoding="utf-8")
        self.assertIn("| Finding | Type | Story | AC | Status | Marks Stale | Summary |", report)
        self.assertNotIn("| Change |", report)


if __name__ == "__main__":
    unittest.main()
