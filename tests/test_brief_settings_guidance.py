"""IMP-311: the brief v2 settings step is guided and enforced.

A new project compiles the brief v2, which needs the BA to confirm the profile and
genesis once (`/brief ID --profile ... --genesis ...`). Before this item nothing
asked for it: `/next` said "waiting for client answers", and `/maturity` decided
READY before compiling, so a first `/specs` ran on a provisional v1-layout brief.
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import SnapshotWorkspaceCase, gap_acceptance_answer, run_cli, run_ok  # noqa: E402

PROJECT = "GUIDED"

RAW = """# Operations Risk Dashboard

Objective: let operations leads review risk queues before the daily meeting.

Users: operations leads.

In scope: risk dashboard for open queues. Out of scope: editing cases.

Metric: reduce manual preparation by 30 percent in the first release month.
"""

EARS = "When queue metrics are available, the system shall display open risk queues."


class BriefSettingsGuidanceTests(SnapshotWorkspaceCase):
    """A v2 project (the /init default) whose gaps are answered but whose brief settings are not."""

    @classmethod
    def build_workspace(cls) -> None:
        root = Path.cwd()
        (root / "raw.md").write_text(RAW, encoding="utf-8")
        (root / "answers.md").write_text(gap_acceptance_answer(EARS), encoding="utf-8")
        run_ok(["init", PROJECT])
        run_ok(["ingest", PROJECT, "--source", str(root / "raw.md")])
        run_ok(["resolve-gaps", PROJECT, "--source", str(root / "answers.md")])

    def brief(self) -> Path:
        return self.temp / "workspaces" / PROJECT / "02_requirements" / "project-brief.md"

    def test_next_asks_for_the_brief_settings_with_a_suggested_command(self) -> None:
        step = json.loads(run_ok(["next", PROJECT]))
        self.assertEqual(step["key"], "brief_settings")
        self.assertIn(f"/brief {PROJECT} --profile ", step["command"])
        self.assertIn(" --genesis ", step["command"])

    def test_maturity_blocks_on_the_settings_and_writes_no_provisional_brief(self) -> None:
        result = json.loads(run_ok(["maturity", PROJECT]))
        self.assertEqual(result["readiness"], "BLOCKED")
        self.assertIn("GAP-BRIEF-PROFILE", result["blocking_gaps"])
        self.assertFalse(self.brief().exists(), "no v1-layout placeholder for a v2 project")

    def test_specs_refuses_until_the_settings_are_confirmed(self) -> None:
        code, _ = run_cli(["specs", PROJECT])
        self.assertEqual(code, 4)
        self.assertFalse(self.brief().exists())

    def test_confirmed_settings_clear_the_step_and_compile_the_v2_brief(self) -> None:
        run_ok(["brief", PROJECT, "--profile", "UI", "--genesis", "greenfield"])
        step = json.loads(run_ok(["next", PROJECT]))
        self.assertNotEqual(step["key"], "brief_settings")
        self.assertTrue(self.brief().read_text(encoding="utf-8").startswith("<!-- sentinel-artifact: v2 -->"))
        gaps = (self.temp / "workspaces" / PROJECT / "01_discovery" / "gaps.md").read_text(encoding="utf-8")
        rows = [line for line in gaps.splitlines() if line.startswith("|") and "GAP-BRIEF-PROFILE" in line]
        self.assertTrue(all("CLOSED" in row for row in rows), rows)

    def test_maturity_then_settings_closes_the_gap(self) -> None:
        run_ok(["maturity", PROJECT])
        run_ok(["brief", PROJECT, "--profile", "UI", "--genesis", "greenfield"])
        gaps = (self.temp / "workspaces" / PROJECT / "01_discovery" / "gaps.md").read_text(encoding="utf-8")
        row = next(line for line in gaps.splitlines() if line.startswith("|") and "GAP-BRIEF-PROFILE" in line)
        self.assertIn("CLOSED", row)
        self.assertNotEqual(json.loads(run_ok(["maturity", PROJECT]))["readiness"], "BLOCKED")

    def test_a_v1_project_is_not_asked(self) -> None:
        run_ok(["init", "LEGACY", "--brief-version", "1"])
        run_ok(["ingest", "LEGACY", "--source", str(self.temp / "raw.md")])
        step = json.loads(run_ok(["next", "LEGACY"]))
        self.assertNotEqual(step["key"], "brief_settings")


if __name__ == "__main__":
    unittest.main()
