"""Tests for advanced elicitation /challenge (IMP-023).

Proves the acceptance criteria:
- /challenge produces a traced, indexed `01_discovery/challenge_report.md`.
- Findings enter as gaps tagged `origin: challenge` through the same IMP-021
  validation (verbatim evidence, declared lens, severity range) — never written
  by hand; fabricated evidence is rejected.
- The report records the technique per lens; `origin: challenge` survives /gaps
  regeneration and the gap flows through the normal lifecycle.

Deterministic and local-first: real CLI in a temp cwd, no network.
"""
from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from sentinel.cli import main
from sentinel.discovery import AnnotationError, apply_challenge, validate_agent_gaps

RAW = (
    "# Expense Approval\n\n"
    "We want to modernize how finance approves expenses. The solution must respect "
    "our compliance obligations.\n"
)


def _finding(**over):
    base = {
        "id": "GAP-GOVERNANCE-CONSTRAINTS",
        "lens": "compliance",
        "severity": "high",
        "technique": "pre-mortem",
        "question": "Which audit-trail and retention obligations must the flow satisfy?",
        "evidence": "must respect our compliance obligations",
    }
    base.update(over)
    return base


class ChallengeValidationTests(unittest.TestCase):
    def test_valid_finding_tagged_challenge(self):
        gaps = validate_agent_gaps({"gaps": [_finding()]}, RAW, origin="challenge")
        self.assertEqual(gaps[0]["origin"], "challenge")
        self.assertEqual(gaps[0]["status"], "OPEN")

    def test_fabricated_evidence_rejected(self):
        with self.assertRaises(AnnotationError):
            validate_agent_gaps({"gaps": [_finding(evidence="never said this")]}, RAW, origin="challenge")


class ChallengeLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.old_cwd = Path.cwd()
        self.temp = Path(tempfile.mkdtemp())
        os.chdir(self.temp)
        self.src = self.temp / "raw.md"
        self.src.write_text(RAW, encoding="utf-8")
        self.assertEqual(main(["init", "CHL"]), 0)
        self.assertEqual(main(["ingest", "CHL", "--source", str(self.src)]), 0)
        self.ws = self.temp / "workspaces" / "CHL"

    def tearDown(self):
        os.chdir(self.old_cwd)
        shutil.rmtree(self.temp, ignore_errors=True)

    def _write(self, payload) -> Path:
        path = self.temp / "challenge.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def test_challenge_merges_with_origin_and_report(self):
        payload = {
            "gaps": [_finding()],
            "premortem": ["At 6 months an auditor rejected the trail; retention was never defined."],
            "assumptions_inverted": ["Assumed approvals are internal-only."],
        }
        result = apply_challenge("CHL", self._write(payload))
        self.assertIn("GAP-GOVERNANCE-CONSTRAINTS", result["merged"])

        # gap merged with origin challenge in the trace table
        gaps_md = (self.ws / "01_discovery" / "gaps.md").read_text(encoding="utf-8")
        row = next(line for line in gaps_md.splitlines() if line.startswith("| GAP-GOVERNANCE-CONSTRAINTS"))
        self.assertTrue(row.rstrip().endswith("| challenge |"), row)

        # challenge_report.md exists, names the lens, technique, and pre-mortem
        report = (self.ws / "01_discovery" / "challenge_report.md").read_text(encoding="utf-8")
        self.assertIn("Challenge Report", report)
        self.assertIn("Lens: `compliance`", report)
        self.assertIn("pre-mortem", report)
        self.assertIn("auditor rejected the trail", report)

        # traceability: challenge_report node + edges
        graph = (self.ws / "06_traceability" / "traceability_graph.json").read_text(encoding="utf-8")
        self.assertIn('"type": "challenge_report"', graph)
        self.assertIn('"relation": "challenged_by"', graph)

        # /status visibility: challenge_origin count in state gap_counts
        state = json.loads((self.ws / "state.json").read_text(encoding="utf-8"))
        self.assertGreaterEqual(state["gap_counts"].get("challenge_origin", 0), 1)

    def test_origin_survives_gaps_regeneration(self):
        apply_challenge("CHL", self._write({"gaps": [_finding()]}))
        self.assertEqual(main(["gaps", "CHL"]), 0)
        gaps_md = (self.ws / "01_discovery" / "gaps.md").read_text(encoding="utf-8")
        row = next(line for line in gaps_md.splitlines() if line.startswith("| GAP-GOVERNANCE-CONSTRAINTS"))
        self.assertTrue(row.rstrip().endswith("| challenge |"), row)

    def test_cli_challenge_runs(self):
        self.assertEqual(main(["challenge", "CHL", "--source", str(self._write({"gaps": [_finding()]}))]), 0)


if __name__ == "__main__":
    unittest.main()
