"""Regression: the knowledge-staleness marker must follow its own remediation
contract (H5 campaign finding BUG-02).

Before the fix, `state.json#knowledge_staleness` was write-only: regenerating
the listed downstream artifacts (the remediation the /health finding itself
prescribes) never cleared it, so health stayed DIRTY forever and the preflight
kept /backlog, /quality and /refine-backlog blocked. Meanwhile any later
metabolism pass WITHOUT knowledge movement overwrote the marker with an empty
one, clearing it even though nothing was regenerated.

After the fix:
- the marker carries ``recorded_at``; /health drops artifacts regenerated
  strictly after it and stops reporting once all listed artifacts are fresh;
- a metabolism pass without knowledge movement preserves a pending marker.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
import time
import unittest
from pathlib import Path

from sentinel.cli import main
from sentinel.health import run_health


RAW = """# Client Request: Operations Risk Dashboard

Objective: let operations leads review risk queues before the daily meeting.

Users: operations leads.

In scope: read-only risk dashboard for open queues backed by the existing metrics service. Out of scope: editing tickets.

Metric: reduce preparation effort by 30 percent in the first month, measured with the existing weekly report.
"""

CONTRADICTION = """Sponsor note: the assumption ASM-TECH-METRICS-SOURCE is invalidated - the existing metrics service cannot be used as the source of queue risk data; Security requires a new dedicated feed.
"""

TRIVIAL = """Administrative note: the demo moves to Thursday. No impact on scope, requirements or assumptions.
"""


class KnowledgeStalenessLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.old_cwd = Path.cwd()
        self.temp = Path(tempfile.mkdtemp())
        os.chdir(self.temp)
        self.project = "STALENESS"
        (self.temp / "raw.md").write_text(RAW, encoding="utf-8")

    def tearDown(self):
        os.chdir(self.old_cwd)
        shutil.rmtree(self.temp, ignore_errors=True)

    def _workspace(self) -> Path:
        return self.temp / "workspaces" / self.project

    def _state(self) -> dict:
        return json.loads((self._workspace() / "state.json").read_text(encoding="utf-8"))

    def _answer_all_open_gaps(self) -> Path:
        gaps_text = (self._workspace() / "01_discovery" / "gaps.md").read_text(encoding="utf-8")
        gap_ids = list(dict.fromkeys(re.findall(r"\bGAP-[A-Z0-9-]+\b", gaps_text)))
        blocks = [
            f"### {gid}\n"
            f"- Answer: Confirmed by the sponsor: operational detail, thresholds and owner for {gid} are defined in the workshop minutes.\n"
            "- Owner / source: Client sponsor\n"
            "- Evidence or reference: workshop minutes\n"
            "- Decision status: confirmed\n"
            for gid in gap_ids
        ]
        answers = self.temp / "answers.md"
        answers.write_text("# Answers\n\n" + "\n".join(blocks), encoding="utf-8")
        return answers

    def _reach_specs_with_assumption(self):
        self.assertEqual(main(["init", self.project]), 0)
        self.assertEqual(main(["ingest", self.project, "--source", str(self.temp / "raw.md")]), 0)
        self.assertEqual(main(["resolve-gaps", self.project, "--source", str(self._answer_all_open_gaps())]), 0)
        assumption = self.temp / "assumption.json"
        assumption.write_text(json.dumps({
            "assumptions": [{
                "id": "ASM-TECH-METRICS-SOURCE",
                "lens": "technical",
                "statement": "The dashboard will use the existing metrics service as the provisional source of queue risk data.",
                "owner": "Technology Lead",
                "risk": "med",
                "justification": "backed by the existing metrics service",
            }]
        }), encoding="utf-8")
        self.assertEqual(main(["assume", self.project, "--source", str(assumption)]), 0)
        self.assertEqual(main(["brief", self.project]), 0)
        self.assertEqual(main(["specs", self.project]), 0)

    def _sync_note(self, name: str, text: str):
        note = self.temp / name
        note.write_text(text, encoding="utf-8")
        self.assertEqual(main(["sync", self.project, "--source", str(note), "--note", name]), 0)

    def _staleness_findings(self) -> list[str]:
        report = run_health(self.project)
        return [f for f in report.get("findings", []) if "Knowledge changed after downstream artifacts" in f]

    def test_staleness_marker_lifecycle(self):
        self._reach_specs_with_assumption()

        # 1) knowledge movement after specs: marker recorded with artifacts + timestamp
        self._sync_note("contradiction.md", CONTRADICTION)
        marker = self._state().get("knowledge_staleness", {})
        self.assertTrue(marker.get("downstream_artifacts"), "expected downstream artifacts in staleness marker")
        self.assertTrue(marker.get("recorded_at"), "marker must carry recorded_at")
        self.assertTrue(self._staleness_findings(), "health must report the staleness finding")

        # 2) regression (accidental clear): a pass with NO knowledge movement
        #    must not clear a pending marker
        self._sync_note("trivial.md", TRIVIAL)
        marker_after_trivial = self._state().get("knowledge_staleness", {})
        self.assertTrue(
            marker_after_trivial.get("downstream_artifacts"),
            "a trivial sync must not clear a pending staleness marker",
        )
        self.assertTrue(self._staleness_findings(), "finding must survive an unrelated trivial sync")

        # 3) the prescribed remediation clears it: regenerate the listed
        #    artifacts strictly after recorded_at (bump mtimes past the
        #    one-second timestamp granularity)
        self.assertEqual(main(["brief", self.project]), 0)
        self.assertEqual(main(["specs", self.project]), 0)
        future = time.time() + 2
        for item in self._state()["knowledge_staleness"]["downstream_artifacts"]:
            path = Path(item)
            if path.exists():
                os.utime(path, (future, future))
        self.assertEqual(self._staleness_findings(), [], "regenerated artifacts must satisfy the marker")
