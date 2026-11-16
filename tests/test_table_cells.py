"""IMP-321: one way to write a Markdown table cell, and a reader that understands it.

The independent review reproduced a lost gap: an /annotate gap whose question held a
newline was dropped from gaps.md, and one with a `|` shifted every column after it,
while the command exited 0. Writers escaped cells three ways (`\\|`, `/`, nothing) and
split_table_row split on every pipe. Now table_cell() flattens newlines and escapes
pipes, and split_table_row() splits only on unescaped pipes and unescapes them.
"""
from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from sentinel.cli import main
from sentinel.core.markdown import split_table_row, table_cell
from sentinel.discovery import parse_gap_rows

RAW = (
    "# Reporting Portal\n\n"
    "We need a reporting portal for the operations team. The objective is to "
    "reduce manual work. Data is stored in the legacy billing system.\n"
)


class TableCellUnitTests(unittest.TestCase):
    def test_table_cell_flattens_newlines_and_escapes_pipes(self):
        self.assertEqual(table_cell("line one\nline two | three"), "line one line two \\| three")
        self.assertEqual(table_cell("a\r\nb"), "a b")

    def test_already_escaped_pipe_is_not_escaped_twice(self):
        self.assertEqual(table_cell("a \\| b"), "a \\| b")

    def test_split_respects_escaped_pipes(self):
        self.assertEqual(split_table_row("| a \\| b | c |"), ["a | b", "c"])

    def test_round_trip(self):
        values = ["plain", "with | pipe", "with\nnewline", "`code | tick`"]
        row = "| " + " | ".join(table_cell(v) for v in values) + " |"
        self.assertEqual(
            split_table_row(row, strip_code_ticks=False),
            ["plain", "with | pipe", "with newline", "`code | tick`"],
        )


class GapRowIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.old_cwd = Path.cwd()
        self.temp = Path(tempfile.mkdtemp())
        os.chdir(self.temp)
        (self.temp / "raw.md").write_text(RAW, encoding="utf-8")
        self.assertEqual(main(["init", "CELLS", "--brief-version", "1"]), 0)
        self.assertEqual(main(["ingest", "CELLS", "--source", str(self.temp / "raw.md")]), 0)
        self.gaps_path = self.temp / "workspaces" / "CELLS" / "01_discovery" / "gaps.md"

    def tearDown(self):
        os.chdir(self.old_cwd)
        shutil.rmtree(self.temp, ignore_errors=True)

    def annotate(self, gaps: list[dict]) -> int:
        path = self.temp / "annotation.json"
        path.write_text(json.dumps({"gaps": gaps}), encoding="utf-8")
        return main(["annotate", "CELLS", "--source", str(path)])

    def rows(self) -> dict[str, dict]:
        return {row["id"].strip("`"): row for row in parse_gap_rows(self.gaps_path.read_text(encoding="utf-8"))}

    def test_newline_and_pipe_gaps_both_survive_and_keep_their_columns(self):
        code = self.annotate([
            {"id": "GAP-RETENTION-NEWLINE", "lens": "technical", "severity": "critical",
             "question": "How long is data kept?\nAnd who owns the source of truth?",
             "evidence": "legacy billing system"},
            {"id": "GAP-RETENTION-PIPE", "lens": "technical", "severity": "critical",
             "question": "Is retention 1 year | 5 years?", "evidence": "legacy billing system"},
        ])
        self.assertEqual(code, 0)
        for _ in range(2):  # survives a regeneration too
            rows = self.rows()
            self.assertIn("GAP-RETENTION-NEWLINE", rows)
            self.assertIn("GAP-RETENTION-PIPE", rows)
            self.assertEqual(rows["GAP-RETENTION-PIPE"]["severity"].strip("`"), "critical")
            self.assertEqual(rows["GAP-RETENTION-PIPE"]["origin"].strip("`"), "agent")
            self.assertEqual(main(["gaps", "CELLS"]), 0)


if __name__ == "__main__":
    unittest.main()
