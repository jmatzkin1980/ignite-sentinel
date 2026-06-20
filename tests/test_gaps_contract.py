from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from pathlib import Path

from sentinel import discovery
from sentinel.backlog import gates
from sentinel.backlog.gates import blocking_gaps_for_trace
from sentinel.gaps import (
    BLOCKING_GAP_STATUSES,
    GAP_ROW_FIELDS,
    blocking_severities,
    is_blocking,
    parse_gap_table,
)
from sentinel.maturity import parse_blocking_gaps
from sentinel.workspace import ensure_workspace


class GapContractTests(unittest.TestCase):
    def test_parse_gap_table_matches_discovery_parse_gap_rows(self):
        text = "\n".join(
            [
                "| GAP-001 | product | high | OPEN | REQ-001 | Missing users | Who uses it? | client | quote | agent | pending |",
                "| GAP-002 | tech | medium | CLOSED | REQ-001 | Missing auth | Which IdP? | design | N/A | N/A | Done |",
                "| NOT-GAP | product | high | OPEN | REQ-001 | ignored | ignored | client |",
                "| GAP-003 | short | high | OPEN |",
            ]
        )
        expected = [
            {
                "id": "GAP-001",
                "lens": "product",
                "severity": "high",
                "status": "OPEN",
                "parent": "REQ-001",
                "description": "Missing users",
                "question": "Who uses it?",
                "source": "client",
                "evidence_mention": "quote",
                "origin": "agent",
                "resolution_note": "pending",
            },
            {
                "id": "GAP-002",
                "lens": "tech",
                "severity": "medium",
                "status": "CLOSED",
                "parent": "REQ-001",
                "description": "Missing auth",
                "question": "Which IdP?",
                "source": "design",
                "resolution_note": "Done",
            },
        ]
        self.assertEqual(parse_gap_table(text), expected)
        self.assertEqual(parse_gap_table(text), discovery.parse_gap_rows(text))

    def test_parse_gap_table_strips_backticks_like_existing_contract(self):
        text = "| `GAP-010` | `quality` | `critical` | `ANSWERED` | `REQ-001` | Desc | Q? | Client |\n"
        self.assertEqual(
            parse_gap_table(text),
            [
                {
                    "id": "GAP-010",
                    "lens": "quality",
                    "severity": "critical",
                    "status": "ANSWERED",
                    "parent": "REQ-001",
                    "description": "Desc",
                    "question": "Q?",
                    "source": "Client",
                }
            ],
        )

    def test_parse_gap_table_supports_legacy_rows_only_when_requested(self):
        text = "\n".join(
            [
                "| GAP-001 | high | OPEN | Missing scope |",
                "| GAP-002 | product | medium | PARTIALLY_CLOSED | Missing variant |",
            ]
        )
        self.assertEqual(parse_gap_table(text), [])
        self.assertEqual(
            parse_gap_table(text, include_legacy=True),
            [
                {
                    "id": "GAP-001",
                    "lens": "",
                    "severity": "high",
                    "status": "OPEN",
                    "parent": "",
                    "description": "Missing scope",
                    "question": "",
                    "source": "",
                },
                {
                    "id": "GAP-002",
                    "lens": "product",
                    "severity": "medium",
                    "status": "PARTIALLY_CLOSED",
                    "parent": "",
                    "description": "Missing variant",
                    "question": "",
                    "source": "",
                },
            ],
        )

    def test_parse_blocking_gaps_uses_canonical_predicate_with_legacy_support(self):
        text = "\n".join(
            [
                "| GAP-001 | high | OPEN | Missing scope |",
                "| GAP-002 | product | medium | PARTIALLY_CLOSED | Missing variant |",
                "| GAP-003 | product | low | OPEN | REQ-001 | Missing edge | Q? | Client |",
                "| GAP-004 | product | high | CLOSED | REQ-001 | Already closed | Q? | Client |",
            ]
        )
        self.assertEqual(parse_blocking_gaps(text, {"critical", "high"}), ["GAP-001"])
        self.assertEqual(parse_blocking_gaps(text, {"medium"}), ["GAP-002"])

    def test_blocking_contract_has_single_exported_status_set(self):
        self.assertEqual(GAP_ROW_FIELDS[:4], ("id", "lens", "severity", "status"))
        self.assertIs(gates.BLOCKING_GAP_STATUSES, BLOCKING_GAP_STATUSES)

    def test_blocking_severities_honors_config_with_default_fallback(self):
        self.assertEqual(blocking_severities({}), {"critical", "high"})
        self.assertEqual(
            blocking_severities({"maturity": {"blocking_gap_severities": ["HIGH", "medium", ""]}}),
            {"high", "medium"},
        )
        self.assertEqual(
            blocking_severities({"maturity": {"blocking_gap_severities": "medium"}}),
            {"critical", "high"},
        )

    def test_is_blocking_uses_canonical_predicate(self):
        self.assertTrue(is_blocking({"severity": "HIGH", "status": "OPEN"}, {"high"}))
        self.assertTrue(is_blocking({"severity": "`critical`", "status": "`ANSWERED`"}))
        self.assertFalse(is_blocking({"severity": "medium", "status": "OPEN"}))
        self.assertFalse(is_blocking({"severity": "high", "status": "CLOSED"}))

    def test_backlog_gates_use_canonical_blocking_config(self):
        old_cwd = Path.cwd()
        temp = Path(tempfile.mkdtemp())
        try:
            os.chdir(temp)
            workspace = ensure_workspace("GAPCFG")
            config = workspace / "sentinel.config.yaml"
            config.write_text(
                config.read_text(encoding="utf-8").replace(
                    "    - critical\n    - high",
                    "    - MEDIUM",
                ),
                encoding="utf-8",
            )
            gaps_path = workspace / "01_discovery" / "gaps.md"
            gaps_path.write_text(
                "| GAP-900 | product | medium | OPEN | REQ-001 | Missing variant | Q? | Client |\n"
                "| GAP-901 | product | high | OPEN | REQ-001 | Missing high | Q? | Client |\n",
                encoding="utf-8",
            )
            self.assertEqual(blocking_gaps_for_trace("GAPCFG", ["GAP-900"]), ["GAP-900"])
            self.assertEqual(blocking_gaps_for_trace("GAPCFG", ["GAP-901"]), [])
        finally:
            os.chdir(old_cwd)
            shutil.rmtree(temp)


if __name__ == "__main__":
    unittest.main()
