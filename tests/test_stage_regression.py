"""IMP-292 — touching gaps never moves a project back unless a blocking gap opens.

Every command that rewrites gaps.md (annotate, challenge, scrutinize, self-review,
sync, resolve-gaps, gaps) used to recompute `readiness_stage` from the gap counts
alone, which tops out at READY_FOR_PROJECT_BRIEF. A project already at
READY_FOR_BACKLOG dropped back to the brief after any of them, with nothing new
blocking it. And two stages that /brief writes were unknown to the dashboard.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
import unittest
from pathlib import Path

from sentinel.cli import main
from sentinel.dashboard import LIFECYCLE_STAGES
from sentinel.discovery import apply_annotation, next_readiness_stage, parse_gap_rows

REPO = Path(__file__).resolve().parents[1]
SENTINEL = REPO / "sentinel"

RAW = (
    "# Reporting Portal\n\n"
    "We need a reporting portal for the operations team. The objective is to "
    "reduce manual work. Data is stored in the legacy billing system.\n"
)
NONE_BLOCKING = {"open": 2, "blocking_open": 0, "partially_closed": 0, "answered": 0}
BLOCKING = {"open": 2, "blocking_open": 1}
CLEAR = {"open": 0, "blocking_open": 0}


class NextStageTests(unittest.TestCase):
    def test_keeps_a_later_stage_without_blocking_gaps(self) -> None:
        for stage in ("READY_FOR_SPECS", "SPECS_BELOW_THRESHOLD", "READY_FOR_BACKLOG"):
            self.assertEqual(next_readiness_stage(stage, NONE_BLOCKING), stage)
            self.assertEqual(next_readiness_stage(stage, CLEAR), stage)

    def test_keeps_a_brief_block_until_brief_runs_again(self) -> None:
        for stage in ("BRIEF_BELOW_THRESHOLD", "SELF_CORRECTION_FAILED", "UNITS_NOT_IMPLEMENTABLE"):
            self.assertEqual(next_readiness_stage(stage, NONE_BLOCKING), stage)

    def test_a_blocking_gap_always_moves_back(self) -> None:
        for stage in ("READY_FOR_BACKLOG", "READY_FOR_SPECS", "READY_FOR_PROJECT_BRIEF", None):
            self.assertEqual(next_readiness_stage(stage, BLOCKING), "CLIENT_RESPONSE_NEEDED")

    def test_discovery_stages_still_follow_the_counts(self) -> None:
        self.assertEqual(next_readiness_stage("CLIENT_RESPONSE_NEEDED", NONE_BLOCKING), "DOMAIN_RESPONSE_NEEDED")
        self.assertEqual(next_readiness_stage("DOMAIN_RESPONSE_NEEDED", CLEAR), "READY_FOR_PROJECT_BRIEF")
        self.assertEqual(next_readiness_stage(None, CLEAR), "READY_FOR_PROJECT_BRIEF")


class GapCommandsKeepTheStageTests(unittest.TestCase):
    """Real CLI in a temp cwd: a later stage survives gap commands that add nothing blocking."""

    def setUp(self) -> None:
        self.old_cwd = Path.cwd()
        self.temp = Path(tempfile.mkdtemp())
        os.chdir(self.temp)
        src = self.temp / "raw.md"
        src.write_text(RAW, encoding="utf-8")
        self.assertEqual(main(["init", "STG", "--brief-version", "1"]), 0)
        self.assertEqual(main(["ingest", "STG", "--source", str(src)]), 0)
        self.ws = self.temp / "workspaces" / "STG"
        self._close_blocking_gaps()
        self._set_stage("READY_FOR_BACKLOG")

    def tearDown(self) -> None:
        os.chdir(self.old_cwd)
        shutil.rmtree(self.temp, ignore_errors=True)

    def _state(self) -> dict:
        return json.loads((self.ws / "state.json").read_text(encoding="utf-8"))

    def _set_stage(self, stage: str) -> None:
        state = self._state()
        state["readiness_stage"] = stage
        (self.ws / "state.json").write_text(json.dumps(state), encoding="utf-8")

    def _close_blocking_gaps(self) -> None:
        rows = parse_gap_rows((self.ws / "01_discovery" / "gaps.md").read_text(encoding="utf-8"))
        blocking = [r["id"].strip("`") for r in rows if r.get("severity", "").lower() in {"critical", "high"}]
        self.assertTrue(blocking, "fixture should start with blocking gaps")
        response = self.temp / "close.md"
        response.write_text("".join(
            f"### {gap_id}\n\n- Answer: Confirmed by the operations lead.\n- Owner / source: Ops lead\n"
            "- Evidence or reference: kickoff notes\n- Decision status: confirmed\n\n"
            for gap_id in blocking
        ), encoding="utf-8")
        self.assertEqual(main(["resolve-gaps", "STG", "--source", str(response)]), 0)
        self.assertEqual(self._state()["gap_counts"]["blocking_open"], 0)

    def _annotate(self, severity: str) -> None:
        path = self.temp / f"annotation-{severity}.json"
        path.write_text(json.dumps({"gaps": [{
            "id": f"GAP-RETENTION-{severity.upper()}",
            "lens": "technical",
            "severity": severity,
            "question": "How long must report data be retained?",
            "evidence": "legacy billing system",
        }]}), encoding="utf-8")
        apply_annotation("STG", path)

    def test_non_blocking_annotation_keeps_ready_for_backlog(self) -> None:
        self._annotate("low")
        self.assertEqual(self._state()["readiness_stage"], "READY_FOR_BACKLOG")

    def test_gaps_regeneration_keeps_ready_for_backlog(self) -> None:
        self.assertEqual(main(["gaps", "STG"]), 0)
        self.assertEqual(self._state()["readiness_stage"], "READY_FOR_BACKLOG")

    def test_blocking_annotation_moves_back(self) -> None:
        self._annotate("high")
        self.assertEqual(self._state()["readiness_stage"], "CLIENT_RESPONSE_NEEDED")


class StageGuards(unittest.TestCase):
    def test_gap_commands_do_not_recompute_the_stage_from_counts_alone(self) -> None:
        # Only /brief (maturity.py) derives the stage from the counts; everyone else
        # goes through next_readiness_stage so a later stage is kept.
        offenders = []
        for path in SENTINEL.rglob("*.py"):
            if path.name == "maturity.py":
                continue
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if re.search(r"readiness_stage[\"']?\s*[:=]\s*readiness_stage_for_counts\(", line):
                    offenders.append(f"{path.relative_to(REPO)}:{number}")
        self.assertEqual(offenders, [])

    def test_dashboard_knows_every_stage_the_runtime_writes(self) -> None:
        written = set()
        for path in SENTINEL.rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            written.update(re.findall(r"readiness_stage[\"']?\s*[:=]\s*\"([A-Z_]+)\"", text))
            written.update(re.findall(r"readiness_stage\s*=\s*\"([A-Z_]+)\"\s+if", text))
        workflow = (SENTINEL / "discovery" / "workflow.py").read_text(encoding="utf-8")
        body = workflow.split("def readiness_stage_for_counts", 1)[1].split("\ndef ", 1)[0]
        written.update(re.findall(r"return \"([A-Z_]+)\"", body))
        self.assertIn("UNITS_NOT_IMPLEMENTABLE", written)  # the scan really sees /brief's writes
        self.assertEqual(sorted(written - set(LIFECYCLE_STAGES)), [])


if __name__ == "__main__":
    unittest.main()
