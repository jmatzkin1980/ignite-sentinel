"""IMP-360: a knowledge change after /backlog must not deadlock /backlog.

A /sync that invalidates an assumption marks the brief, PRD, specs, BACKLOG.md
and implementation_readiness.json stale, and /health turns DIRTY. The last two
are rewritten only by /backlog, which the DIRTY gate refused, so health stayed
DIRTY forever. Now /backlog runs when every /health finding is one it clears
itself; any other finding still refuses it, and /quality waits for /backlog.
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import re
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from sentinel.cli import main
from sentinel.health import run_health

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import SnapshotWorkspaceCase  # noqa: E402


PROJECT = "UNBLOCK"
RAW = """# Client Request: Operations Risk Dashboard

Objective: let operations leads review risk queues before the daily meeting.

Users: operations leads.

In scope: read-only risk dashboard for open queues backed by the existing metrics service. Out of scope: editing tickets.

Metric: reduce preparation effort by 30 percent in the first month, measured with the existing weekly report.
"""
CONTRADICTION = (
    "Sponsor note: the assumption ASM-TECH-METRICS-SOURCE is invalidated - the existing metrics service "
    "cannot be used as the source of queue risk data; Security requires a new dedicated feed.\n"
)
STALENESS = "Knowledge changed after downstream artifacts"


def run(args: list[str]) -> tuple[int, str]:
    err = io.StringIO()
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
        code = main(args)
    return code, err.getvalue()


def ok(args: list[str]) -> None:
    code, err = run(args)
    if code != 0:
        raise AssertionError(f"{args[0]} exited {code}: {err}")


class BacklogStalenessUnblockTests(SnapshotWorkspaceCase):
    @classmethod
    def build_workspace(cls) -> None:
        work = Path.cwd()
        ws = work / "workspaces" / PROJECT
        (work / "raw.md").write_text(RAW, encoding="utf-8")
        ok(["init", PROJECT, "--brief-version", "1"])
        ok(["ingest", PROJECT, "--source", str(work / "raw.md")])
        gaps = (ws / "01_discovery" / "gaps.md").read_text(encoding="utf-8")
        blocks = [
            f"### {gid}\n"
            f"- Answer: Confirmed by the sponsor: operational detail, thresholds and owner for {gid} are defined in the workshop minutes.\n"
            "- Owner / source: Client sponsor\n- Evidence or reference: workshop minutes\n- Decision status: confirmed\n"
            for gid in dict.fromkeys(re.findall(r"\bGAP-[A-Z0-9-]+\b", gaps))
        ]
        (work / "answers.md").write_text("# Answers\n\n" + "\n".join(blocks), encoding="utf-8")
        ok(["resolve-gaps", PROJECT, "--source", str(work / "answers.md")])
        (work / "assumption.json").write_text(json.dumps({"assumptions": [{
            "id": "ASM-TECH-METRICS-SOURCE",
            "lens": "technical",
            "statement": "The dashboard will use the existing metrics service as the provisional source of queue risk data.",
            "owner": "Technology Lead",
            "risk": "med",
            "justification": "backed by the existing metrics service",
        }]}), encoding="utf-8")
        ok(["assume", PROJECT, "--source", str(work / "assumption.json")])
        ok(["brief", PROJECT])
        ok(["specs", PROJECT])
        ok(["backlog", PROJECT])
        (work / "contradiction.md").write_text(CONTRADICTION, encoding="utf-8")
        ok(["sync", PROJECT, "--source", str(work / "contradiction.md"), "--note", "contradiction.md"])
        # Move the knowledge change, and the artifacts generated before it, into
        # the past, so a regeneration in the same second still counts as later
        # (timestamps have one-second granularity).
        state_file = ws / "state.json"
        state = json.loads(state_file.read_text(encoding="utf-8"))
        artifacts = state["knowledge_staleness"]["downstream_artifacts"]
        assert artifacts, "the sync must mark downstream artifacts stale"
        now = datetime.now(timezone.utc).replace(microsecond=0)
        state["knowledge_staleness"]["recorded_at"] = (now - timedelta(seconds=10)).isoformat()
        state_file.write_text(json.dumps(state, indent=2), encoding="utf-8")
        before = (now - timedelta(seconds=60)).timestamp()
        for item in artifacts:
            os.utime(item, (before, before))
        assert run_health(PROJECT)["verdict"] == "DIRTY"

    def _ws(self) -> Path:
        return self.temp / "workspaces" / PROJECT

    def test_backlog_regenerates_the_stale_backlog_and_health_returns_clean(self) -> None:
        # The brief and specs are stale too: /backlog names the order of the fix.
        code, err = run(["backlog", PROJECT])
        self.assertEqual(code, 4, err)
        self.assertIn("Run /brief, then /specs, then /backlog.", err)

        ok(["brief", PROJECT])
        ok(["specs", PROJECT])
        report = run_health(PROJECT)
        self.assertEqual(report["verdict"], "DIRTY")
        self.assertEqual(report["findings"], report["remediated_by_backlog"])

        # /quality consumes the stale backlog, so it waits for /backlog.
        code, err = run(["quality", PROJECT])
        self.assertEqual(code, 4, err)
        self.assertIn("Run /backlog, then /quality.", err)

        ok(["backlog", PROJECT])
        state = json.loads((self._ws() / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(state["health"], "CLEAN")
        report = run_health(PROJECT)
        self.assertFalse([f for f in report["findings"] if STALENESS in f], report["findings"])
        self.assertEqual(report["verdict"], "CLEAN", report["findings"])
        ok(["quality", PROJECT])

    def test_another_finding_still_refuses_backlog(self) -> None:
        ok(["brief", PROJECT])
        ok(["specs", PROJECT])
        backlog = self._ws() / "04_backlog" / "BACKLOG.md"
        before = backlog.stat().st_mtime
        with mock.patch("sentinel.health.has_blocking_open_gap", return_value=True):
            code, err = run(["backlog", PROJECT])
        self.assertEqual(code, 4, err)
        self.assertIn("Blocking gaps remain open.", err)
        # IMP-369: each finding with its fix, in order (was "Run /health to see every finding").
        self.assertIn("1. Blocking gaps remain open. Close them with the client's answers: "
                      f"run /resolve-gaps {PROJECT} --source ANSWERS.", err)
        self.assertIn("2. Knowledge changed after BACKLOG.md, implementation_readiness.json were generated. "
                      "Run /backlog.", err)
        self.assertEqual(backlog.stat().st_mtime, before, "a refused /backlog writes nothing")
        state = json.loads((self._ws() / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(state["health"], "DIRTY")


if __name__ == "__main__":
    unittest.main()
