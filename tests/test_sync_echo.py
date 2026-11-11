"""IMP-293 — /sync never reads Sentinel's own outputs back as client sources.

The autonomous `/sync` (no `--source`) scans the 07_changes buckets for new or
modified files. Sentinel itself writes into those buckets: the digest and the
PROPOSED gap response of `/sync --digest`, and the response copy and resolution
report of `/resolve-gaps`. The digest outputs were neither recorded nor excluded,
so the next autonomous `/sync` ingested them as client input: Sentinel echoing
itself. `/resolve-gaps` already recorded its files; its test guards that.
"""
from __future__ import annotations

import os
import re
import shutil
import tempfile
import unittest
from pathlib import Path

from sentinel.cli import main
from sentinel.discovery import parse_gap_rows
from sentinel.sources import SENTINEL_OUTPUT_SUFFIXES, WORKSPACE_INPUT_DIRS, discover_pending_sources, iter_source_files

REPO = Path(__file__).resolve().parents[1]

RAW = (
    "# Reporting Portal\n\n"
    "We need a reporting portal for the operations team. The objective is to "
    "reduce manual work. Data is stored in the legacy billing system.\n"
)
MEETING = (
    "# Weekly sync\n\n"
    "- We decided the portal exports to CSV only.\n"
    "- Report data is retained for 24 months in the billing service.\n"
)


class SyncDoesNotEchoTests(unittest.TestCase):
    def setUp(self) -> None:
        self.old_cwd = Path.cwd()
        self.temp = Path(tempfile.mkdtemp())
        os.chdir(self.temp)
        src = self.temp / "raw.md"
        src.write_text(RAW, encoding="utf-8")
        self.assertEqual(main(["init", "ECHO", "--brief-version", "1"]), 0)
        self.assertEqual(main(["ingest", "ECHO", "--source", str(src)]), 0)
        self.ws = self.temp / "workspaces" / "ECHO"
        self.assertEqual(self._pending(), [])

    def tearDown(self) -> None:
        os.chdir(self.old_cwd)
        shutil.rmtree(self.temp, ignore_errors=True)

    def _pending(self) -> list[str]:
        return sorted(item["key"] for item in discover_pending_sources("ECHO"))

    def test_sync_with_digest_leaves_nothing_pending(self) -> None:
        meeting = self.temp / "meeting-notes.md"
        meeting.write_text(MEETING, encoding="utf-8")
        self.assertEqual(main(["sync", "ECHO", "--source", str(meeting), "--digest"]), 0)
        self.assertTrue(list((self.ws / "07_changes").rglob("*_interaction_digest.md")))
        self.assertEqual(self._pending(), [])

    def test_resolve_gaps_leaves_nothing_pending(self) -> None:
        rows = parse_gap_rows((self.ws / "01_discovery" / "gaps.md").read_text(encoding="utf-8"))
        gap_id = rows[0]["id"].strip("`")
        response = self.temp / "client-answers.md"
        response.write_text(
            f"### {gap_id}\n\n- Answer: Confirmed by the operations lead.\n- Owner / source: Ops lead\n"
            "- Evidence or reference: kickoff notes\n- Decision status: confirmed\n",
            encoding="utf-8",
        )
        self.assertEqual(main(["resolve-gaps", "ECHO", "--source", str(response)]), 0)
        self.assertTrue(list((self.ws / "07_changes").rglob("*_gap_resolution_report.md")))
        self.assertEqual(self._pending(), [])

    def test_a_client_file_dropped_in_a_bucket_is_still_picked_up(self) -> None:
        dropped = self.ws / "07_changes" / "01_meetings" / "kickoff.md"
        dropped.write_text(MEETING, encoding="utf-8")
        self.assertEqual(self._pending(), ["workspaces/ECHO/07_changes/01_meetings/kickoff.md"])

    def test_sentinel_output_names_are_never_candidates(self) -> None:
        folder = self.temp / "bucket"
        folder.mkdir()
        for suffix in SENTINEL_OUTPUT_SUFFIXES:
            (folder / f"note{suffix}").write_text("x", encoding="utf-8")
        (folder / "note.md").write_text("x", encoding="utf-8")
        self.assertEqual([p.name for p in iter_source_files(folder)], ["note.md"])


class SentinelWritersGuard(unittest.TestCase):
    """Every module that writes into a scanned bucket is covered by a test above."""

    COVERED = {"sync.py", "interaction_digest.py", "gap_resolution.py"}
    # Name a bucket without writing into it: sources/workspace define the buckets,
    # maturity.py cites one in the PRD gap-routing table text, source_registry.py
    # maps bucket names to source kinds (it writes only 07_changes/source_log.md).
    # anchor_review.py (IMP-258b) reads source copies from 07_changes/00_client_responses; it writes only gaps and its log.
    NOT_WRITERS = {"sources.py", "workspace.py", "maturity.py", "source_registry.py", "anchor_review.py"}

    def test_no_new_writer_into_scanned_buckets(self) -> None:
        buckets = [d.split("/", 1)[1] for d in WORKSPACE_INPUT_DIRS if d.startswith("07_changes/")]
        pattern = re.compile("|".join(re.escape(b) for b in buckets))
        writers = set()
        for path in (REPO / "sentinel").rglob("*.py"):
            if path.name in self.NOT_WRITERS:
                continue
            if pattern.search(path.read_text(encoding="utf-8")):
                writers.add(path.name)
        # interaction_digest.py receives the bucket from sync.py as target_dir.
        self.assertEqual(sorted(writers - self.COVERED), [])


if __name__ == "__main__":
    unittest.main()
