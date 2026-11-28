"""IMP-435 (H27 inc 9a, task 1): the backlog keeps the refinements the BA accepted (A-02) and reads as a story (A-08, Q2)."""
from __future__ import annotations

import contextlib
import io
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import SnapshotWorkspaceCase, run_ok  # noqa: E402
from sentinel.cli import main  # noqa: E402
from sentinel.compilers.change_backlog import _change_story_ids, read_change_units  # noqa: E402
from sentinel.core.io import forget_read_snapshots  # noqa: E402
from sentinel.workspace import workspace_path  # noqa: E402
import test_change_next as tcn  # noqa: E402

FX = Path(__file__).resolve().parent / "fixtures" / "inc9a"
CID = "CHG-001"
SECTION = "## Agent Backlog Refinements"
QUOTE = "When an analyst submits a supplier registration above the approval threshold"


def run_err(argv: list[str]) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(list(argv))
    return code, out.getvalue(), err.getvalue()


def write_refine(name: str, proposals: list[dict]) -> str:
    path = Path(name)
    path.write_text(json.dumps({"proposals": proposals}), encoding="utf-8")
    return str(path)


class AltaCase(SnapshotWorkspaceCase):
    @classmethod
    def build_workspace(cls) -> None:
        for argv in (["init", "ALTA"], ["ingest", "ALTA", "--source", str(FX / "pedido_alta.md")],
                     ["resolve-gaps", "ALTA", "--source", str(FX / "respuestas_alta.md")],
                     ["brief", "ALTA", "--profile", "UI", "--genesis", "greenfield"],
                     ["specs", "ALTA"], ["backlog", "ALTA"]):
            run_ok(argv)

    def setUp(self):
        super().setUp()
        forget_read_snapshots()
        self.base = workspace_path("ALTA")

    def proposal(self, **extra) -> dict:
        return {"kind": "reslice", "target_stories": ["US-001"], "source_units": ["SPEC-U-001"],
                "recommendation": "Keep the registration story focused on the approvals queue.",
                "rationale": "The unit names the queue as the observable response.", "citations": [QUOTE], **extra}

    def test_refinement_survives_backlog(self):
        """A-02: refine-backlog -> specs -> backlog kept the section in neither the epic nor the story."""
        run_ok(["refine-backlog", "ALTA", "--source", write_refine("refine.json", [self.proposal()])])
        for name in ("EPIC-001.md", "US-001.md"):
            self.assertIn(SECTION, (self.base / "04_backlog" / name).read_text(encoding="utf-8"))
        run_ok(["specs", "ALTA"])
        run_ok(["backlog", "ALTA"])
        for name in ("EPIC-001.md", "US-001.md"):
            text = (self.base / "04_backlog" / name).read_text(encoding="utf-8")
            self.assertIn(SECTION, text, name)
            self.assertEqual(text.count(SECTION), 1, name)
            self.assertIn("BREF-001", text, name)

    def test_refinement_target_gone_reported(self):
        """A target story that no longer exists is named in the report, and /backlog warns on stderr."""
        run_ok(["refine-backlog", "ALTA", "--source", write_refine("refine.json", [self.proposal()])])
        folder = self.base / "04_backlog" / "refinements"
        accepted = json.loads((folder / "accepted_refinements.json").read_text(encoding="utf-8"))
        accepted[0]["target_stories"] = ["US-099"]
        (folder / "accepted_refinements.json").write_text(json.dumps(accepted), encoding="utf-8")
        forget_read_snapshots()
        code, _out, err = run_err(["backlog", "ALTA"])
        self.assertEqual(code, 0, err)
        report = (folder / "rerender_report.md").read_text(encoding="utf-8")
        self.assertIn("US-099", report)
        self.assertIn("BREF-001", report)
        self.assertIn("sentinel warning:", err)
        self.assertIn("BREF-001", err)
        self.assertNotIn("BREF-001", (self.base / "04_backlog" / "US-001.md").read_text(encoding="utf-8"))

    def test_rerender_refinements_api(self):
        from sentinel.backlog.refinement import rerender_refinements

        self.assertEqual(rerender_refinements("ALTA"), {"rendered": [], "dropped": []})
        run_ok(["refine-backlog", "ALTA", "--source", write_refine("refine.json", [self.proposal()])])
        self.assertEqual(rerender_refinements("ALTA"), {"rendered": ["BREF-001"], "dropped": []})

    def test_story_statement_reads_as_story(self):
        """A-08 (Q2): the statement is built from actor, capability and benefit, in the workspace language."""
        story = (self.base / "04_backlog" / "US-001.md").read_text(encoding="utf-8")
        epic = (self.base / "04_backlog" / "EPIC-001.md").read_text(encoding="utf-8")
        statements = [story.split("## User Story", 1)[1].split("\n## ", 1)[0],
                      epic.split("**Narrative:**", 1)[1].split("**Slicing Pattern:**", 1)[0]]
        for text in statements:
            self.assertIn("Como los analistas de Compras,", text)
            self.assertNotIn("the system shall", text)
            self.assertNotIn("target user", text)
            self.assertNotIn("quiero an analyst", text)
        self.assertIn("quiero send it to the approvals queue of the Head of Purchasing cuando an analyst submits", story)
        self.assertIn("para que la capacidad confirmada se puede planificar", story)


class BorrCase(SnapshotWorkspaceCase):
    @classmethod
    def build_workspace(cls) -> None:
        tcn.ChangeNextSequence.build_workspace()
        tcn.ChangeNextSequence.test_each_row_of_the_table_in_order(unittest.TestCase())

    def setUp(self):
        super().setUp()
        forget_read_snapshots()
        self.base = workspace_path("BORR")

    def test_change_refinement_survives_backlog(self):
        unit = read_change_units("BORR", CID)[0]["id"]
        story = _change_story_ids(self.base, CID)[0]
        proposal = {"kind": "reslice", "target_stories": [story], "source_units": [unit],
                    "recommendation": "Keep the draft story small.", "rationale": "One observable result.",
                    "citations": ["Guardar borrador"]}
        run_ok(["refine-backlog", "BORR", "--source", write_refine("refine.json", [proposal]), "--change", CID])
        run_ok(["specs", "BORR", "--change", CID])
        run_ok(["backlog", "BORR", "--change", CID])
        forget_read_snapshots()
        epic = (self.base / "04_backlog" / "EPIC-CHG-001.md").read_text(encoding="utf-8")
        self.assertIn(SECTION, epic)
        self.assertEqual(epic.count(SECTION), 1)
        story_text = (self.base / "04_backlog" / f"{story}.md").read_text(encoding="utf-8")
        self.assertIn(SECTION, story_text)
        self.assertIn("BREF-001", story_text)


if __name__ == "__main__":
    unittest.main()
