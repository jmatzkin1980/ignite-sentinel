"""IMP-398 (H26 inc 1): the project verdict knows the changes.

A workspace that only holds changes used to report NOT_READY with "Discovery has not run" although the
project has no discovery to run. The verdict now lists each pending change step; workspaces with a
project or without changes keep the verdict they had.
"""
from __future__ import annotations

import json
import shutil
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import (  # noqa: E402
    SnapshotWorkspaceCase, build_matured_workspace, complete_extraction, export_final_brief, gap_acceptance_answer, run_ok,
)
from sentinel.readiness_verdict import build_readiness_verdict  # noqa: E402

NOT_MEASURED = "not measured"
from test_change_next import CID, cli_json, load_baseline, set_change  # noqa: E402
from test_change_flow import SCOPE_ANSWER  # noqa: E402
from test_change_specs import ALL_ANSWERS, PROJECT_EARS, PROJECT_RAW, answer, open_change  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"
DISCOVERY = "Discovery has not run"


class ChangeOnly(SnapshotWorkspaceCase):
    @classmethod
    def build_workspace(cls):
        shutil.copy(FIXTURES / "change_borrador.md", Path.cwd() / "pedido.md")
        run_ok(["init", "BORR"])
        run_ok(["ingest", "BORR", "--source", "pedido.md", "--change"])

    def test_pending_step_blocks_instead_of_discovery(self):
        verdict = build_readiness_verdict("BORR")
        self.assertEqual(verdict["verdict"], "NOT_READY")
        self.assertFalse([b for b in verdict["blockers"] if DISCOVERY in b])
        self.assertEqual(verdict["blockers"], [f"{CID}: scope. Cerrar el borde del cambio."])
        self.assertEqual(cli_json(["status", "BORR"])["verdict"]["blockers"], verdict["blockers"])

    def test_lenses_blocker_counts_in_the_change_language(self):
        (Path.cwd() / "scope.md").write_text(SCOPE_ANSWER, encoding="utf-8")
        run_ok(["resolve-gaps", "BORR", "--source", "scope.md", "--change", CID])
        load_baseline("BORR")
        (blocker,) = build_readiness_verdict("BORR")["blockers"]
        self.assertRegex(blocker, rf"^{CID}: lenses \(\d+ bloqueante/s\)\. ")
        set_change("BORR", language="en")
        (blocker,) = build_readiness_verdict("BORR")["blockers"]
        self.assertRegex(blocker, rf"^{CID}: lenses \(\d+ blocking\)\. Close the change's blocking questions\.$")

    def test_all_done_has_measured_coverage_and_no_coverage_warning(self):
        (Path.cwd() / "scope.md").write_text(SCOPE_ANSWER, encoding="utf-8")
        run_ok(["resolve-gaps", "BORR", "--source", "scope.md", "--change", CID])
        load_baseline("BORR")
        answer("BORR", CID, "a.md", ALL_ANSWERS)
        complete_extraction("BORR", CID)
        run_ok(["brief", "BORR", "--change", CID])
        export_final_brief("BORR", CID)
        for command in ("specs", "backlog"):
            run_ok([command, "BORR", "--change", CID])
        verdict = build_readiness_verdict("BORR")
        self.assertEqual(verdict["changes"][0]["next_step"]["key"], "done")
        self.assertEqual(verdict["blockers"], [])
        self.assertEqual(verdict["verdict"], "READY_WITH_WARNINGS")
        # done means the request is fully extracted: the coverage is measured in the change's step, never "not measured"
        self.assertFalse([w for w in verdict["warnings"] if NOT_MEASURED in w])
        coverage = verdict["changes"][0]["next_step"]["text"]
        self.assertRegex(coverage, r"La extracción cubre (\d+) de \1 ")
        self.assertNotRegex(coverage, r"La extracción cubre 0 de")
        gaps_gate = next(g for g in verdict["gate_matrix"] if g["gate"] == "gaps")
        self.assertEqual(gaps_gate, {"gate": "gaps", "state": "NOT_APPLICABLE", "blocks": False})
        self.assertFalse([w for w in verdict["warnings"] + verdict["blockers"] if DISCOVERY in w])


class WithoutChanges(SnapshotWorkspaceCase):
    @classmethod
    def build_workspace(cls):
        run_ok(["init", "NOCH"])

    def test_same_output_as_before(self):
        verdict = build_readiness_verdict("NOCH")
        self.assertNotIn("changes", verdict)
        self.assertEqual(verdict["verdict"], "NOT_READY")
        self.assertEqual(verdict["blockers"], ["Discovery has not run: there is no 01_discovery/gaps.md."])
        self.assertEqual(next(g for g in verdict["gate_matrix"] if g["gate"] == "gaps"), {"gate": "gaps", "state": "NOT_RUN", "blocks": True})
        self.assertFalse([w for w in verdict["warnings"] if NOT_MEASURED in w])


class Mixed(SnapshotWorkspaceCase):
    @classmethod
    def build_workspace(cls):
        build_matured_workspace("MIX", PROJECT_RAW, gap_acceptance_answer(PROJECT_EARS), backlog=False)

    def test_project_verdict_unchanged_by_a_change(self):
        before = build_readiness_verdict("MIX")
        cid = open_change("MIX")
        run_ok(["sources", "MIX", "--change", cid, "--no-baseline", "--reason", "Sistema nuevo"])  # state only: keeps the project's sources untouched
        after = build_readiness_verdict("MIX")
        self.assertEqual(after.pop("changes")[0]["next_step"]["key"], "lenses")
        for key in ("verdict", "blockers", "warnings", "blocking_open", "partial_coverage", "gate_matrix", "counts", "next_step"):
            self.assertEqual(after[key], before[key], key)
        self.assertFalse([w for w in after["warnings"] if NOT_MEASURED in w])


if __name__ == "__main__":
    unittest.main()
