"""Tests for EARS requirement normalization (IMP-026).

- classify_ears recognizes the five EARS patterns (EN + ES) and rejects prose.
- When a functional gap closes with a substantive answer already written in EARS
  syntax, /resolve-gaps accumulates it into requirements.md as a REQ-EARS-* row
  with its pattern and source; a prose answer is NOT normalized (invariant #3).
"""
from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from pathlib import Path

from sentinel.cli import main
from sentinel.discovery import parse_gap_rows
from sentinel.ears import classify_ears, is_ears
from sentinel.gap_resolution import resolve_gaps

RAW = (
    "# Ops Dashboard\n\n"
    "We need a dashboard for the operations team to see queue risk.\n"
)


class EarsClassifyTests(unittest.TestCase):
    def test_patterns(self):
        self.assertEqual(classify_ears("The system shall display the queue."), "ubiquitous")
        self.assertEqual(classify_ears("When a case breaches SLA, the system shall flag it."), "event")
        self.assertEqual(classify_ears("While data is stale, the dashboard shall warn."), "state")
        self.assertEqual(classify_ears("If the service is down, then the system shall show riskUnknown."), "unwanted")
        self.assertEqual(classify_ears("Where audit logging is enabled, the system shall record access."), "optional")
        self.assertEqual(classify_ears("Cuando un caso supera el SLA, el sistema debe marcarlo."), "event")

    def test_prose_is_not_ears(self):
        self.assertIsNone(classify_ears("We want a nice dashboard."))
        self.assertFalse(is_ears("Reduce manual work by 30%."))


class EarsResolutionTests(unittest.TestCase):
    def setUp(self):
        self.old_cwd = Path.cwd()
        self.temp = Path(tempfile.mkdtemp())
        os.chdir(self.temp)
        src = self.temp / "raw.md"
        src.write_text(RAW, encoding="utf-8")
        self.assertEqual(main(["init", "EARS"]), 0)
        self.assertEqual(main(["ingest", "EARS", "--source", str(src)]), 0)
        self.ws = self.temp / "workspaces" / "EARS"

    def tearDown(self):
        os.chdir(self.old_cwd)
        shutil.rmtree(self.temp, ignore_errors=True)

    def _first_two_gap_ids(self):
        gaps = parse_gap_rows((self.ws / "01_discovery" / "gaps.md").read_text(encoding="utf-8"))
        ids = [g["id"] for g in gaps if g["id"] != "NONE"]
        return ids[:2]

    def test_ears_answer_normalized_prose_not(self):
        ids = self._first_two_gap_ids()
        self.assertGreaterEqual(len(ids), 2, "fixture should produce at least two gaps")
        ears_gap, prose_gap = ids[0], ids[1]
        ears_stmt = "When a case breaches its SLA, the system shall flag the queue as high risk."
        answered = self.temp / "answers.md"
        answered.write_text(
            f"### {ears_gap} - x\n"
            f"- Answer: {ears_stmt}\n- Owner / source: Ops\n- Evidence or reference: Workshop\n- Decision status: confirmed\n\n"
            f"### {prose_gap} - y\n"
            f"- Answer: The team reviews queues every morning before standup.\n- Owner / source: Ops\n- Evidence or reference: Workshop\n- Decision status: confirmed\n",
            encoding="utf-8",
        )
        resolve_gaps("EARS", answered)
        req = (self.ws / "02_requirements" / "requirements.md").read_text(encoding="utf-8")
        self.assertIn("## Normalized Requirements (EARS)", req)
        self.assertIn("REQ-EARS-001", req)
        self.assertIn("| event |", req)
        self.assertIn(ears_stmt, req)
        self.assertIn(f"`{ears_gap}`", req)
        # The prose answer must NOT be normalized.
        self.assertNotIn("reviews queues every morning", req)


if __name__ == "__main__":
    unittest.main()
