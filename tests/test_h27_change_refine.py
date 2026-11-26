"""IMP-433: `/refine-backlog --change` refines the stories of a change, without EPIC-001, against its own units and stories."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import SnapshotWorkspaceCase, run_cli, run_ok  # noqa: E402
from change_inc8b_flow import BASELINE, PID as BASE_PID, build_project_outputs, project_output_hashes  # noqa: E402
from sentinel.changes import get_change  # noqa: E402
from sentinel.compilers.change_backlog import (  # noqa: E402
    _change_story_ids, _release_story_ids, change_unit_texts, read_change_units,
)
from sentinel.core.io import forget_read_snapshots  # noqa: E402
from sentinel.discovery.change_scope import change_grounding_text  # noqa: E402
from sentinel.readiness_verdict import change_next_step  # noqa: E402
from sentinel.workspace import read_json, update_state, workspace_path  # noqa: E402
import test_change_next as tcn  # noqa: E402
import test_h27_change_grouped_backlog as grouped  # noqa: E402

CID = "CHG-001"
QUOTE = "Guardar borrador"


def source(name: str, proposals: list[dict]) -> str:
    path = Path(name)
    path.write_text(json.dumps({"proposals": proposals}), encoding="utf-8")
    return str(path)


def missing_story(unit: str, citation: str = QUOTE, **extra) -> dict:
    return {"kind": "missing-story", "source_units": [unit], "recommendation": "Add a story for the draft list.",
            "rationale": "The request asks to retake the drafts.", "citations": [citation], **extra}


def refine(project: str, name: str, proposals: list[dict], *, change: str | None = CID) -> tuple[int, str]:
    argv = ["refine-backlog", project, "--source", source(name, proposals)]
    return run_cli(argv + ["--change", change] if change else argv)


class BorrWithBacklog(SnapshotWorkspaceCase):
    """BORR: a change-only workspace walked up to its backlog and quality audit."""

    @classmethod
    def build_workspace(cls):
        tcn.ChangeNextSequence.build_workspace()
        tcn.ChangeNextSequence.test_each_row_of_the_table_in_order(unittest.TestCase())

    def setUp(self):
        super().setUp()
        forget_read_snapshots()
        self.base = workspace_path("BORR")
        self.unit = read_change_units("BORR", CID)[0]["id"]
        self.story = _change_story_ids(self.base, CID)[0]

    def test_change_refine_without_epic_001(self):
        self.assertFalse((self.base / "04_backlog" / "EPIC-001.md").exists())
        out = run_ok(["refine-backlog", "BORR", "--source", source("p.json", [missing_story(self.unit)]), "--change", CID])
        result = json.loads(out)
        self.assertEqual(result["accepted"], ["BREF-001"])
        self.assertEqual(result["change_id"], CID)
        folder = self.base / "04_backlog" / CID / "refinements"
        self.assertTrue((folder / "accepted_refinements.json").is_file())
        report = (folder / "refinement_report.md").read_text(encoding="utf-8")
        self.assertTrue(report.startswith("# Backlog Refinement Report - BORR / CHG-001"))
        self.assertIn("## Agent Backlog Refinements", (self.base / "04_backlog" / "EPIC-CHG-001.md").read_text(encoding="utf-8"))
        state = read_json(self.base / "state.json", {})
        self.assertEqual(state["changes"][CID]["refinements"]["count"], 1)
        self.assertEqual(state["changes"][CID]["refinements"]["last_id"], result["refinement_id"])
        self.assertNotIn("backlog_refinement_count", state)
        graph = (self.base / "06_traceability" / "traceability_graph.json").read_text(encoding="utf-8")
        self.assertIn('"relation": "refined_by"', graph)

    def test_change_refine_targets_a_story_of_the_change(self):
        proposal = {"kind": "reslice", "target_stories": [self.story], "source_units": [self.unit],
                    "recommendation": "Keep the draft story small.", "rationale": "One observable result.", "citations": [QUOTE]}
        run_ok(["refine-backlog", "BORR", "--source", source("p.json", [proposal]), "--change", CID])
        story = (self.base / "04_backlog" / f"{self.story}.md").read_text(encoding="utf-8")
        self.assertIn("BREF-001", story)
        self.assertIn("## Agent Backlog Refinements", story)

    def test_change_refine_on_dirty_project(self):
        update_state("BORR", health="DIRTY")
        forget_read_snapshots()
        code, out = refine("BORR", "p.json", [missing_story(self.unit)])
        self.assertEqual(code, 0, out)

    def test_refinements_dir_is_not_a_release(self):
        """RF 4: `04_backlog/CHG-nnn/refinements/` is not a release folder (7d read every `r*`)."""
        folder = self.base / "04_backlog" / CID / "refinements"
        folder.mkdir(parents=True)
        (folder / "stories.md").write_text(f"| [{self.story}](../../{self.story}.md) | x |\n", encoding="utf-8")
        self.assertEqual(_release_story_ids(self.base, CID, None), set())
        before = grouped.run_backlog("BORR", CID)["stories"]
        self.assertEqual(before, grouped.run_backlog("BORR", CID)["stories"])
        self.assertFalse(list((self.base / "04_backlog" / CID).glob("r[0-9]*")))

    def test_refine_change_makes_quality_stale(self):
        """RF 5: a refinement that touches a story of the change leaves the quality verdict of 8a behind."""
        self.assertEqual(change_next_step("BORR", CID)["key"], "done")
        proposal = {"kind": "reslice", "target_stories": [self.story], "source_units": [self.unit],
                    "recommendation": "Keep the draft story small.", "rationale": "One observable result.", "citations": [QUOTE]}
        run_ok(["refine-backlog", "BORR", "--source", source("p.json", [proposal]), "--change", CID])
        forget_read_snapshots()
        self.assertEqual(change_next_step("BORR", CID)["key"], "quality")

    def test_change_refine_refuses_a_backlog_that_is_behind(self):
        """I1 (review inc 8b): `/specs --change` dropped a unit after the backlog: refine refuses like `/quality --change`."""
        from sentinel.backlog.refinement import apply_backlog_refinement
        from sentinel.errors import GateRefusal

        units = read_change_units("BORR", CID)
        dropped = next(u for u in units if u["id"] != self.unit)
        dropped["path"].unlink()
        forget_read_snapshots()
        snapshot = {p: p.read_bytes() for p in (self.base / "04_backlog").rglob("*") if p.is_file()}
        with self.assertRaises(GateRefusal) as caught:
            apply_backlog_refinement("BORR", Path(source("b.json", [missing_story(self.unit)])), CID)
        self.assertEqual(str(caught.exception), "El backlog de CHG-001 falta o está atrasado")
        self.assertEqual(caught.exception.next_step, "/backlog BORR --change CHG-001")
        self.assertEqual({p: p.read_bytes() for p in (self.base / "04_backlog").rglob("*") if p.is_file()}, snapshot)
        code, _out = refine("BORR", "b2.json", [missing_story(self.unit)])
        self.assertEqual(code, 4)  # a gate refusal from the CLI too

    def test_epic_only_refinement_makes_quality_stale(self):
        """M1 (review inc 8b): a `missing-story` refinement writes only the change epic; it also leaves quality behind."""
        self.assertEqual(change_next_step("BORR", CID)["key"], "done")
        run_ok(["refine-backlog", "BORR", "--source", source("m.json", [missing_story(self.unit)]), "--change", CID])
        forget_read_snapshots()
        self.assertEqual(change_next_step("BORR", CID)["key"], "quality")

    def test_change_evidence_excludes_agent_refinements(self):
        """M4 (review inc 8b): a second refinement cannot cite the agent prose of the first one."""
        from sentinel.backlog.refinement import change_refinement_evidence_text

        prose = "Add a story for the draft list."
        self.assertNotIn(prose, change_refinement_evidence_text("BORR", CID))
        run_ok(["refine-backlog", "BORR", "--source", source("e.json", [missing_story(self.unit)]), "--change", CID])
        forget_read_snapshots()
        self.assertNotIn(prose, change_refinement_evidence_text("BORR", CID))
        code, out = refine("BORR", "e2.json", [missing_story(self.unit, citation=prose)])
        self.assertNotEqual(code, 0, out)

    def test_change_refine_leaves_stories_outside_its_scope(self):
        """M5 (review inc 8b): a record that targets a story outside the change (a 0.39 project refinement) is not rendered into it."""
        from sentinel.backlog.refinement import render_backlog_refinements

        other = self.base / "04_backlog" / "US-950.md"
        other.write_text("---\nid: US-950\n---\n\n# US-950\n", encoding="utf-8")
        before = other.read_bytes()
        epic = self.base / "04_backlog" / "EPIC-CHG-001.md"
        record = {"id": "BREF-009", "kind": "reslice", "target_stories": ["US-950", self.story], "source_units": [self.unit],
                  "recommendation": "Keep it small.", "rationale": "One result.", "citations": [QUOTE], "status": "accepted"}
        render_backlog_refinements(self.base, [record], epic, story_ids={self.story})
        self.assertEqual(other.read_bytes(), before)
        self.assertIn("## Agent Backlog Refinements", (self.base / "04_backlog" / f"{self.story}.md").read_text(encoding="utf-8"))

    def test_change_unit_texts_joins_the_units_of_the_change(self):
        texts = change_unit_texts("BORR", CID)
        self.assertEqual(sorted(texts), sorted(unit["id"] for unit in read_change_units("BORR", CID)))
        self.assertTrue(all(text.strip() for text in texts.values()))

    def test_change_unit_texts_adds_the_units_of_every_release(self):
        release = self.base / "03_specs" / CID / "r1" / "units"
        release.mkdir(parents=True)
        own = read_change_units("BORR", CID)[0]
        text = own["path"].read_text(encoding="utf-8").replace(own["id"], "SPEC-U-901")
        (release / "SPEC-U-901.md").write_text(text, encoding="utf-8")
        changes = read_json(self.base / "state.json", {})["changes"]
        changes[CID]["backlog_releases"] = {"r1": {"stories": [self.story]}}
        update_state("BORR", changes=changes)
        forget_read_snapshots()
        self.assertIn("SPEC-U-901", change_unit_texts("BORR", CID))
        self.assertEqual(set(change_unit_texts("BORR", CID)) - {"SPEC-U-901"}, {u["id"] for u in read_change_units("BORR", CID)})


class BorrWithoutBacklog(SnapshotWorkspaceCase):
    @classmethod
    def build_workspace(cls):
        tcn.ChangeNextSequence.build_workspace()

    def test_change_refine_refusal_language(self):
        from sentinel.backlog.refinement import apply_backlog_refinement
        from sentinel.errors import GateRefusal

        path = Path("p.json")
        path.write_text(json.dumps({"proposals": []}), encoding="utf-8")
        with self.assertRaises(GateRefusal) as caught:
            apply_backlog_refinement("BORR", path, CID)
        self.assertEqual(str(caught.exception), "CHG-001 todavía no tiene backlog para refinar")
        self.assertEqual(caught.exception.next_step, "/backlog BORR --change CHG-001")
        changes = read_json(workspace_path("BORR") / "state.json", {})["changes"]
        changes[CID]["language"] = "en"
        update_state("BORR", changes=changes)
        forget_read_snapshots()
        with self.assertRaises(GateRefusal) as caught:
            apply_backlog_refinement("BORR", path, CID)
        self.assertEqual(str(caught.exception), "CHG-001 has no backlog to refine yet")


class MixWithChangeBacklog(SnapshotWorkspaceCase):
    """MIX: a project with its backlog and a change with stories of its own."""

    @classmethod
    def build_workspace(cls):
        grouped.GroupedRemovedBacklog.build_workspace.__func__(cls)
        run_ok(["backlog", "MIX", "--change", cls.cid])

    def setUp(self):
        super().setUp()
        forget_read_snapshots()
        self.base = workspace_path("MIX")
        self.cid = type(self).cid
        self.units = {u["id"] for u in read_change_units("MIX", self.cid)}
        self.own = set(_change_story_ids(self.base, self.cid))
        lines = [ln.strip() for ln in change_grounding_text("MIX", self.cid).splitlines()
                 if len(ln.strip()) > 25 and not ln.startswith(("#", "|", "-", "*", ">", "`"))]
        self.quote = lines[0]

    def project_stories(self) -> list[str]:
        return sorted({p.stem for p in (self.base / "04_backlog").glob("US-*.md")} - self.own)

    def test_change_refine_rejects_project_story_and_unit(self):
        """RF 2: the change validates against its own stories and units, never the project's."""
        project_units = sorted({p.stem for p in (self.base / "03_specs" / "units").glob("SPEC-U-*.md")} - self.units)
        self.assertTrue(project_units and self.project_stories())
        own_unit = sorted(self.units)[0]
        before = {p.relative_to(self.base).as_posix(): p.read_bytes() for p in (self.base / "04_backlog").rglob("*") if p.is_file()}
        proposal = {"kind": "reslice", "target_stories": [self.project_stories()[0]], "source_units": [own_unit],
                    "recommendation": "Split it.", "rationale": "Because.", "citations": [self.quote]}
        code, out = refine("MIX", "p1.json", [proposal], change=self.cid)
        self.assertNotEqual(code, 0)
        report = (self.base / "04_backlog" / self.cid / "refinements" / "refinement_report.md").read_text(encoding="utf-8")
        self.assertIn("story does not exist", report)
        proposal = {"kind": "missing-story", "source_units": [project_units[0]], "recommendation": "Add it.",
                    "rationale": "Because.", "citations": [self.quote]}
        code, out = refine("MIX", "p2.json", [proposal], change=self.cid)
        self.assertNotEqual(code, 0)
        report = (self.base / "04_backlog" / self.cid / "refinements" / "refinement_report.md").read_text(encoding="utf-8")
        self.assertIn("source unit does not exist", report)
        after = {p.relative_to(self.base).as_posix(): p.read_bytes() for p in (self.base / "04_backlog").rglob("*") if p.is_file()}
        added = set(after) - set(before)
        self.assertEqual(added, {f"04_backlog/{self.cid}/refinements/refinement_report.md"})
        self.assertEqual({k: v for k, v in after.items() if k in before}, before)
        self.assertNotIn("refinements", get_change("MIX", self.cid))

    def test_project_refine_skips_change_stories(self):
        """The project's `/refine-backlog` indexes only stories without `change:`."""
        story = sorted(self.own)[0]
        proposal = {"kind": "reslice", "target_stories": [story], "source_units": ["SPEC-U-001"],
                    "recommendation": "Split it.", "rationale": "Because.", "citations": [tcn.PROJECT_EARS]}
        code, out = refine("MIX", "p.json", [proposal], change=None)
        self.assertNotEqual(code, 0)
        report = (self.base / "04_backlog" / "refinements" / "refinement_report.md").read_text(encoding="utf-8")
        self.assertIn("target story does not exist", report)

    def test_project_refine_edges_only_from_epic_001(self):
        from sentinel.core.graph import load_graph

        proposal = {"kind": "reslice", "target_stories": [self.project_stories()[0]], "source_units": ["SPEC-U-001"],
                    "recommendation": "Split it.", "rationale": "Because.", "citations": [tcn.PROJECT_EARS]}
        run_ok(["refine-backlog", "MIX", "--source", source("p.json", [proposal])])
        graph = load_graph("MIX")
        edges = [e for e in graph["edges"] if e.get("relation") == "refined_by"]
        epics = {n["id"]: str(n.get("path", "")) for n in graph["nodes"] if n.get("type") == "epic"}
        self.assertEqual(len(epics), 2)
        self.assertEqual(len(edges), 1)
        self.assertTrue(epics[edges[0]["from"]].endswith("EPIC-001.md"))


class ProjectRefineBytes(SnapshotWorkspaceCase):
    @classmethod
    def build_workspace(cls):
        build_project_outputs(Path.cwd())

    def test_project_refine_bytes_unchanged(self):
        """RF 3: taken with the code before IMP-433, hashed independently of the checkout path."""
        self.assertEqual(BASE_PID, "BASE")
        self.assertEqual(project_output_hashes(self.temp), json.loads(BASELINE.read_text(encoding="utf-8")))


if __name__ == "__main__":
    unittest.main()
