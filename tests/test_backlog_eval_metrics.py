"""Unit tests for IMP-061 backlog eval metrics."""
from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from tests.evals.run_discovery_evals import backlog_derivation_status


class BacklogEvalMetricsTests(unittest.TestCase):
    def setUp(self):
        self.temp = Path(tempfile.mkdtemp())
        (self.temp / "04_backlog").mkdir(parents=True)
        (self.temp / "08_context_packs").mkdir(parents=True)

    def tearDown(self):
        shutil.rmtree(self.temp, ignore_errors=True)

    def _write_readiness(self, stories: list[dict]) -> None:
        (self.temp / "08_context_packs" / "implementation_readiness.json").write_text(
            json.dumps({"stories": stories}, indent=2),
            encoding="utf-8",
        )

    def test_pending_stub_counts_as_no_invention_coverage(self):
        self._write_readiness(
            [
                {
                    "type": "pending_input_stub",
                    "trace": ["REQ-001", "PRD-001", "SPEC-001", "GAP-BACKLOG-SLICING-READINESS"],
                    "source_unit": "[PENDING INPUT]",
                }
            ]
        )
        (self.temp / "04_backlog" / "US-001.md").write_text(
            "# US-001\n\n[PENDING INPUT]\n\n## Functional Slice\n\n- Slicing pattern: Workflow Step / Happy Path.\n",
            encoding="utf-8",
        )

        result = backlog_derivation_status(
            self.temp,
            {
                "backlog": {
                    "expected_story_count": 1,
                    "expected_story_ids": ["US-001"],
                    "expected_source_units": [],
                    "expect_pending_stub": True,
                    "require_no_invented_stories": True,
                }
            },
        )

        self.assertEqual(result["mismatches"], [])
        self.assertEqual(result["coverage"], 1.0)
        self.assertEqual(result["no_invention_rate"], 1.0)

    def test_value_story_without_spec_unit_is_invention_regression(self):
        self._write_readiness(
            [
                {
                    "type": "value_story",
                    "trace": ["REQ-001", "PRD-001", "SPEC-001"],
                    "source_unit": "[PENDING INPUT]",
                }
            ]
        )
        (self.temp / "04_backlog" / "US-001.md").write_text(
            "# US-001\n\n## Functional Slice\n\n- Slicing pattern: Workflow Step / Happy Path.\n",
            encoding="utf-8",
        )

        result = backlog_derivation_status(
            self.temp,
            {
                "backlog": {
                    "expected_story_count": 1,
                    "expected_story_ids": ["US-001"],
                    "require_no_invented_stories": True,
                }
            },
        )

        self.assertEqual(result["invented_story_count"], 1)
        self.assertLess(result["no_invention_rate"], 1.0)
        self.assertTrue(any("without SPEC-U source_unit" in item for item in result["mismatches"]))

    def test_slicing_answer_key_is_checked_from_story_markdown(self):
        self._write_readiness(
            [
                {
                    "type": "value_story",
                    "trace": ["REQ-001", "PRD-001", "SPEC-001", "SPEC-U-001"],
                    "source_unit": "SPEC-U-001",
                }
            ]
        )
        (self.temp / "04_backlog" / "US-001.md").write_text(
            "# US-001\n\n## Functional Slice\n\n- Slicing pattern: Workflow Step / Happy Path.\n",
            encoding="utf-8",
        )

        result = backlog_derivation_status(
            self.temp,
            {
                "backlog": {
                    "expected_story_count": 1,
                    "expected_story_ids": ["US-001"],
                    "expected_source_units": ["SPEC-U-001"],
                    "expected_slicing_by_source_unit": {"SPEC-U-001": "Rules / Regression Slice"},
                    "require_spec_unit_trace": True,
                    "require_no_invented_stories": True,
                }
            },
        )

        self.assertEqual(result["slicing_accuracy"], 0.0)
        self.assertTrue(any("expected slicing" in item for item in result["mismatches"]))


if __name__ == "__main__":
    unittest.main()
