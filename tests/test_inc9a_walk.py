"""IMP-435 (H27 inc 9a) task 8: the two walks of the review end where they should, without `/next` looping.

- Project `ALTA`: init -> ingest -> brief --profile --genesis -> resolve-gaps -> `/next` = specs -> specs -> backlog ->
  refine-backlog -> backlog (the refinement stays) -> quality -> `/next` = handoff.
- Change of `FinalCase` (consolidated, extracted, sealed final): split --propose/--confirm -> `/next` = r1 -> derive and
  close r1 -> an `ADDED` unit lands on r1 -> `series_closed_units` -> `--move` -> r2 -> quality ->
  `/next --change` = done ->
  `/export --artifact brief --change` (working draft) -> `/next --change` still done.
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import SnapshotWorkspaceCase, run_ok  # noqa: E402
from test_h26_cross_record import CID, PID  # noqa: E402
from test_inc9a_change_series import BA, SeriesCase, run_all  # noqa: E402

from sentinel.core.io import forget_read_snapshots  # noqa: E402
from sentinel.workspace import workspace_path  # noqa: E402

FX = Path(__file__).resolve().parent / "fixtures" / "inc9a"
SECTION = "## Agent Backlog Refinements"
QUOTE = "When an analyst submits a supplier registration above the approval threshold"


def next_of(*argv: str) -> dict:
    forget_read_snapshots()
    return json.loads(run_ok(["next", *argv]))


class ProjectWalk(SnapshotWorkspaceCase):
    @classmethod
    def build_workspace(cls) -> None:
        run_ok(["init", "ALTA"])

    def test_project_walk_reaches_handoff(self):
        """A-02, A-03, A-13: the project goes from the request to the handoff and /next names each step."""
        base = workspace_path("ALTA")
        run_ok(["ingest", "ALTA", "--source", str(FX / "pedido_alta.md")])
        run_ok(["brief", "ALTA", "--profile", "UI", "--genesis", "greenfield"])
        run_ok(["resolve-gaps", "ALTA", "--source", str(FX / "respuestas_alta.md")])
        step = next_of("ALTA")
        self.assertEqual(step["key"], "specs", step)
        self.assertTrue(step["command"].startswith("/specs ALTA"), step)
        self.assertNotIn("PROJECT_ID", step["text"] + step["command"])
        run_ok(["specs", "ALTA"])
        run_ok(["backlog", "ALTA"])
        refine = Path("refine.json")
        refine.write_text(json.dumps({"proposals": [{
            "kind": "reslice", "target_stories": ["US-001"], "source_units": ["SPEC-U-001"],
            "recommendation": "Keep the registration story focused on the approvals queue.",
            "rationale": "The unit names the queue as the observable response.", "citations": [QUOTE]}]}),
            encoding="utf-8")
        run_ok(["refine-backlog", "ALTA", "--source", str(refine)])
        forget_read_snapshots()
        run_ok(["backlog", "ALTA"])
        for name in ("EPIC-001.md", "US-001.md"):
            text = (base / "04_backlog" / name).read_text(encoding="utf-8")
            self.assertEqual(text.count(SECTION), 1, name)
        forget_read_snapshots()
        run_ok(["quality", "ALTA"])
        step = next_of("ALTA")
        self.assertEqual(step["key"], "handoff", step)


class ChangeWalk(SeriesCase):
    def test_confirmed_series_does_not_advise_propose(self):
        """I-2: with a confirmed series /next and /status --change show one decided notice, never /split --propose."""
        self.confirmed()
        for argv in (["next", PID, "--change", CID], ["status", PID, "--change", CID]):
            forget_read_snapshots()
            out = run_ok(argv)
            self.assertNotIn("--propose", out, argv)
        step = self.step()
        self.assertEqual([w["trigger"] for w in step.get("warnings", []) if w.get("trigger") == "third_party_contract"], [])

    def test_change_walk_reaches_done(self):
        """B-03, B-04, B-06, B-07: the series of the change ends done, and a working export keeps it done."""
        self.confirmed()
        step = self.step()
        self.assertTrue(step["command"].startswith(f"/specs {PID} --change {CID} --release r1"), step)
        self.build_and_close("r1")
        unit = self.add_unit_on_r1()
        step = self.step()
        self.assertEqual(step["key"], "series_closed_units", step)
        self.assertIn(f"--move --unit {unit} --from r1 --to r2", step["command"])
        forget_read_snapshots()
        code, out, err = run_all(["split", PID, "--move", "--unit", unit, "--from", "r1", "--to", "r2",
                                  "--reason", "llegó con el último pedido", *BA, "--change", CID])
        self.assertEqual(code, 0, (out, err))
        step = self.step()
        self.assertTrue(step["command"].startswith(f"/specs {PID} --change {CID} --release r2"), step)
        self.build_and_close("r2")
        step = self.step()
        self.assertEqual(step["key"], "quality", step)  # the change's stories have no current audit yet
        run_ok(["quality", PID, "--change", CID])
        step = self.step()
        self.assertEqual(step["key"], "done", step)
        final = workspace_path(PID) / "02_requirements" / CID
        sealed = {p.name: p.read_bytes() for p in final.rglob("*project-brief*.md") if "draft" not in p.name}
        forget_read_snapshots()
        result = json.loads(run_ok(["export", PID, "--artifact", "brief", "--change", CID]))
        self.assertEqual(result.get("deliverable"), "draft", result)
        self.assertEqual(sealed, {p.name: p.read_bytes() for p in final.rglob("*project-brief*.md")
                                  if "draft" not in p.name})
        step = self.step()
        self.assertEqual(step["key"], "done", step)


if __name__ == "__main__":
    unittest.main()
