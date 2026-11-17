"""IMP-344: `/validate` warns when a brief build item has no story.

Only confirmed answers written in EARS become stories, so a brief whose §9.1 lists three
build items can produce one story and nothing said so. The cross-artifact consistency report
now names each `C-NN` that no value story covers. The warning never blocks, and slicing does
not change.
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

RAW = """# Client Request: Support Operations Dashboard

Objective: reduce support leads' weekly review preparation time.

Users: support team leads.

In scope: a ticket volume chart for every support queue.

In scope: an alert list of tickets close to an SLA breach.

In scope: a weekly export of the review pack to the shared drive.

Out of scope: editing tickets.
"""

ANSWERS = """### GAP-ACCEPTANCE
- Answer: When ticket metrics are available, the system shall show the ticket volume chart for every support queue.
- Owner / source: Synthetic client round
- Evidence or reference: Synthetic build-item coverage fixture
- Decision status: confirmed
"""


class BuildItemCoverageTest(unittest.TestCase):
    def setUp(self):
        self.old_cwd = Path.cwd()
        self.temp = Path(tempfile.mkdtemp())
        os.chdir(self.temp)

    def tearDown(self):
        os.chdir(self.old_cwd)
        shutil.rmtree(self.temp, ignore_errors=True)

    def cli(self, *argv: str) -> None:
        from sentinel.cli import main

        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(list(argv)), 0, argv)

    def test_uncovered_build_items_are_named_without_blocking(self):
        from sentinel.memory import ContextBroker
        from sentinel.validation import validate_project

        pid = "COVER"
        raw = self.temp / "raw.md"
        raw.write_text(RAW, encoding="utf-8")
        answers = self.temp / "answers.md"
        answers.write_text(ANSWERS, encoding="utf-8")
        with patch.object(ContextBroker, "_connect_lancedb", lambda self: None):
            self.cli("init", pid)
            self.cli("ingest", pid, "--source", str(raw))
            self.cli("brief", pid, "--profile", "UI", "--genesis", "greenfield")
            self.cli("resolve-gaps", pid, "--source", str(answers))
            self.cli("specs", pid)
            self.cli("backlog", pid)
            brief = (self.temp / "workspaces" / pid / "02_requirements" / "project-brief.md").read_text(encoding="utf-8")
            for item in ("`C-01`", "`C-02`", "`C-03`"):
                self.assertIn(item, brief)
            result = validate_project(pid)
        # a consistency warning, never a structural finding
        self.assertNotIn("C-02", json.dumps(result.get("findings", []), ensure_ascii=False))
        consistency = result["cross_artifact_consistency"]
        check = next(c for c in consistency["checks"] if c["id"] == "build_items_to_stories")
        self.assertEqual(check["status"], "WARN")
        self.assertEqual(check["issues"], 2)
        messages = [w["message"] for w in consistency["warnings"] if w["check"] == "build_items_to_stories"]
        self.assertEqual(len(messages), 2, messages)
        self.assertTrue(any("C-02" in m and "SLA breach" in m for m in messages), messages)
        self.assertTrue(any("C-03" in m and "weekly export" in m for m in messages), messages)
        self.assertFalse(any("C-01" in m for m in messages), messages)

    def test_matching_is_by_shared_words(self):
        from sentinel.validation import uncovered_build_items

        items = [("C-01", "In scope: a ticket volume chart for every support queue."),
                 ("C-02", "In scope: an alert list of tickets close to an SLA breach.")]
        statements = ["When metrics are available, the system shall show the ticket volume chart per queue."]
        self.assertEqual(uncovered_build_items(items, statements), [items[1]])
        self.assertEqual(uncovered_build_items(items, []), items)


if __name__ == "__main__":
    unittest.main()
