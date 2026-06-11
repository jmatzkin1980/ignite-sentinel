"""Tests for the agentic analysis protocol /annotate (IMP-021).

Proves the acceptance criteria:
- A valid agent analysis merges into gaps.md with `origin: agent`, appears in
  traceability and in /status (gap_counts), and respects the normal lifecycle.
- An invalid analysis (no verbatim citation, fabricated citation, unknown lens,
  out-of-range severity, malformed id, empty) is rejected with a clear error.
- `origin` survives /gaps regeneration (round-trip render -> parse -> render).
- On the expense-approval eval fixture, the agentic pass moves target_recall
  from 0.00 (lexical ceiling) to 1.00 — the falsifiable IMP-021 result.

Deterministic and local-first: real CLI in a temp cwd, no network.
"""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from sentinel.cli import main
from sentinel.discovery import AnnotationError, apply_annotation, validate_agent_gaps

ROOT = Path(__file__).parent

RAW = (
    "# Reporting Portal\n\n"
    "We need a reporting portal for the operations team. The objective is to "
    "reduce manual work. Data is stored in the legacy billing system.\n"
)


def _gap(**over):
    base = {
        "id": "GAP-DATA-RETENTION",
        "lens": "technical",
        "severity": "high",
        "question": "How long must report data be retained and where is the source of truth?",
        "evidence": "legacy billing system",
    }
    base.update(over)
    return base


class AnnotateValidationTests(unittest.TestCase):
    """Unit-level: validate_agent_gaps rejects ungrounded analysis."""

    def test_valid_gap_passes(self):
        gaps = validate_agent_gaps({"gaps": [_gap()]}, RAW)
        self.assertEqual(gaps[0]["id"], "GAP-DATA-RETENTION")
        self.assertEqual(gaps[0]["origin"], "agent")
        self.assertEqual(gaps[0]["status"], "OPEN")

    def test_empty_gaps_rejected(self):
        with self.assertRaises(AnnotationError):
            validate_agent_gaps({"gaps": []}, RAW)

    def test_missing_evidence_rejected(self):
        with self.assertRaises(AnnotationError):
            validate_agent_gaps({"gaps": [_gap(evidence="")]}, RAW)

    def test_fabricated_evidence_rejected(self):
        with self.assertRaises(AnnotationError):
            validate_agent_gaps({"gaps": [_gap(evidence="a quote that is not in the input")]}, RAW)

    def test_unknown_lens_rejected(self):
        with self.assertRaises(AnnotationError):
            validate_agent_gaps({"gaps": [_gap(lens="marketing")]}, RAW)

    def test_bad_severity_rejected(self):
        with self.assertRaises(AnnotationError):
            validate_agent_gaps({"gaps": [_gap(severity="urgent")]}, RAW)

    def test_malformed_id_rejected(self):
        with self.assertRaises(AnnotationError):
            validate_agent_gaps({"gaps": [_gap(id="DATA-RETENTION")]}, RAW)


class AnnotateLifecycleTests(unittest.TestCase):
    """Integration: /annotate merges, traces, and survives regeneration."""

    def setUp(self):
        self.old_cwd = Path.cwd()
        self.temp = Path(tempfile.mkdtemp())
        os.chdir(self.temp)
        self.src = self.temp / "raw.md"
        self.src.write_text(RAW, encoding="utf-8")
        self.assertEqual(main(["init", "ANN"]), 0)
        self.assertEqual(main(["ingest", "ANN", "--source", str(self.src)]), 0)
        self.ws = self.temp / "workspaces" / "ANN"

    def tearDown(self):
        os.chdir(self.old_cwd)
        shutil.rmtree(self.temp, ignore_errors=True)

    def _write_annotation(self, payload) -> Path:
        path = self.temp / "annotation.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def test_valid_annotation_merges_with_origin_agent(self):
        result = apply_annotation("ANN", self._write_annotation({"gaps": [_gap()]}))
        self.assertIn("GAP-DATA-RETENTION", result["merged"])

        gaps_md = (self.ws / "01_discovery" / "gaps.md").read_text(encoding="utf-8")
        self.assertIn("### GAP-DATA-RETENTION", gaps_md)
        self.assertIn("| Detected Trigger | Origin |", gaps_md)
        # the merged row carries origin agent in the trace table
        row = next(line for line in gaps_md.splitlines() if line.startswith("| GAP-DATA-RETENTION"))
        self.assertTrue(row.rstrip().endswith("| agent |"), row)

        # traceability: agent_annotation node + edges
        graph = (self.ws / "06_traceability" / "traceability_graph.json").read_text(encoding="utf-8")
        self.assertIn('"type": "agent_annotation"', graph)
        self.assertIn('"relation": "annotated_by"', graph)
        self.assertIn('"relation": "raises"', graph)

        # /status visibility: agent_origin count in state gap_counts
        state = json.loads((self.ws / "state.json").read_text(encoding="utf-8"))
        self.assertGreaterEqual(state["gap_counts"].get("agent_origin", 0), 1)

        # auditable annotation log records the citation
        log = (self.ws / "01_discovery" / "agent_annotation_log.md").read_text(encoding="utf-8")
        self.assertIn("GAP-DATA-RETENTION", log)
        self.assertIn("legacy billing system", log)

    def test_origin_survives_gaps_regeneration(self):
        apply_annotation("ANN", self._write_annotation({"gaps": [_gap()]}))
        self.assertEqual(main(["gaps", "ANN"]), 0)
        gaps_md = (self.ws / "01_discovery" / "gaps.md").read_text(encoding="utf-8")
        row = next(line for line in gaps_md.splitlines() if line.startswith("| GAP-DATA-RETENTION"))
        self.assertTrue(row.rstrip().endswith("| agent |"), row)

    def test_duplicate_gap_is_skipped(self):
        ann = self._write_annotation({"gaps": [_gap()]})
        apply_annotation("ANN", ann)
        second = apply_annotation("ANN", ann)
        self.assertEqual(second["merged"], [])
        self.assertIn("GAP-DATA-RETENTION", second["skipped_duplicates"])

    def test_agent_gap_is_resolvable_via_lifecycle(self):
        apply_annotation("ANN", self._write_annotation({"gaps": [_gap()]}))
        response = self.temp / "response.md"
        response.write_text(
            "### GAP-DATA-RETENTION\n\n"
            "- Answer: Reports retain data for 24 months; source of truth is the billing service.\n"
            "- Owner / source: Platform team\n"
            "- Evidence or reference: data-policy-v3\n"
            "- Decision status: confirmed\n",
            encoding="utf-8",
        )
        self.assertEqual(main(["resolve-gaps", "ANN", "--source", str(response)]), 0)
        gaps_md = (self.ws / "01_discovery" / "gaps.md").read_text(encoding="utf-8")
        row = next(line for line in gaps_md.splitlines() if line.startswith("| GAP-DATA-RETENTION"))
        self.assertIn("CLOSED", row)
        # origin tag is preserved through resolution re-render
        self.assertTrue(row.rstrip().endswith("| agent |"), row)

    def test_cli_rejects_fabricated_evidence(self):
        bad = self._write_annotation({"gaps": [_gap(evidence="totally invented quote")]})
        self.assertEqual(main(["annotate", "ANN", "--source", str(bad)]), 1)


def _load_runner():
    spec = importlib.util.spec_from_file_location(
        "run_discovery_evals", ROOT / "evals" / "run_discovery_evals.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class AnnotateBreaksLexicalCeilingTests(unittest.TestCase):
    """The falsifiable IMP-021 result on the expense-approval fixture."""

    @classmethod
    def setUpClass(cls):
        cls.runner = _load_runner()
        cls.fixture = ROOT / "fixtures" / "evals" / "expense-approval"

    def test_lexical_pass_still_suppresses(self):
        lexical = self.runner.run_fixture(self.fixture)
        self.assertEqual(lexical["target_recall"], 0.0)

    def test_annotation_pass_recovers_all_targets(self):
        agentic = self.runner.run_fixture(self.fixture, apply_annotation=True)
        self.assertEqual(agentic["target_recall"], 1.0)
        self.assertEqual(agentic["target_fire_total"], 5)
        self.assertEqual(len(agentic["target_fire_detected"]), 5)


if __name__ == "__main__":
    unittest.main()
