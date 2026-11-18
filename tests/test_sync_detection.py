"""IMP-370: /sync raises gaps from the change, and gives a routed source a kind.

Found by live runs: every /sync added GAP-AUTH-MODEL and GAP-CTP-BATCH (evidence
"auth", "batch process") although the note named neither, because the scan read
the workspace text (gaps ledger, brief, specs) as if it were the change; and the
weak-word gaps it found there were listed as `reopened_gaps` while they stayed
CLOSED. A note synced from a "meetings" path stayed `unclassified`.
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

from sentinel.cli import main
from sentinel.sync import detect_sync_gaps

RAW = (
    "# Claims portal\n\n"
    "Policyholders should file a claim with photos and follow its status. Claims adjusters approve claims.\n"
)
LEDGER_NOISE = (
    "# Gaps\n\nThe gap questions name surfaces without their detail, for example: "
    "which login applies to adjusters, and when the nightly batch process runs.\n"
)


def run(*argv: str) -> tuple[int, str]:
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
        code = main(list(argv))
    return code, out.getvalue()


class DetectSyncGapsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.base = Path(tempfile.mkdtemp())
        (self.base / "01_discovery").mkdir(parents=True)
        (self.base / "01_discovery" / "gaps.md").write_text(LEDGER_NOISE, encoding="utf-8")

    def tearDown(self) -> None:
        shutil.rmtree(self.base, ignore_errors=True)

    def test_workspace_wording_does_not_raise_mention_gaps(self) -> None:
        ids = {gap["id"] for gap in detect_sync_gaps(self.base, "A claim accepts at most 10 photos.")}
        self.assertNotIn("GAP-AUTH-MODEL", ids)
        self.assertNotIn("GAP-CTP-BATCH", ids)

    def test_a_mention_in_the_change_still_raises_its_gap(self) -> None:
        gaps = {gap["id"]: gap for gap in detect_sync_gaps(self.base, "Adjusters must log in with auth before approving.")}
        self.assertIn("GAP-AUTH-MODEL", gaps)
        self.assertEqual(gaps["GAP-AUTH-MODEL"]["evidence_mention"], "auth")


class SyncFlowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.old = os.getcwd()
        self.temp = Path(tempfile.mkdtemp())
        os.chdir(self.temp)
        Path("raw.md").write_text(RAW, encoding="utf-8")
        self.assertEqual(run("init", "SYD", "--brief-version", "1")[0], 0)
        self.assertEqual(run("ingest", "SYD", "--source", "raw.md")[0], 0)
        gaps = Path("workspaces/SYD/01_discovery/gaps.md")
        gaps.write_text(gaps.read_text(encoding="utf-8") + "\n" + LEDGER_NOISE, encoding="utf-8")

    def tearDown(self) -> None:
        os.chdir(self.old)
        shutil.rmtree(self.temp, ignore_errors=True)

    def sync(self, rel: str, text: str) -> dict:
        path = Path(rel)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        code, out = run("sync", "SYD", "--source", rel)
        self.assertEqual(code, 0, out)
        return json.loads(out)

    def test_a_note_that_names_neither_adds_neither_gap(self) -> None:
        result = self.sync("input/meetings/minutes.md", "# Minutes\n\nA claim accepts at most 10 photos.\n")
        self.assertNotIn("GAP-AUTH-MODEL", result["merged_gaps"])
        self.assertNotIn("GAP-CTP-BATCH", result["merged_gaps"])
        self.assertNotIn("reopened_gaps", result)
        self.assertIsInstance(result["closed_gaps_detected_again"], list)
        report = Path(result["path"]).with_name(Path(result["path"]).stem + "_impact_report.md")
        self.assertIn("## Closed Gaps Detected Again", report.read_text(encoding="utf-8"))

    def test_a_meeting_note_gets_the_minutes_authority(self) -> None:
        result = self.sync("input/meetings/minutes.md", "# Minutes\n\nA claim accepts at most 10 photos.\n")
        self.assertEqual(result["source_authority"]["authority"], "minutes")
        self.assertNotIn("next_step", result["source_authority"])

    def test_an_unrouted_note_says_how_to_set_its_kind(self) -> None:
        result = self.sync("input/notes/late.md", "# Note\n\nThe photo limit stays at 10 per claim.\n")
        authority = result["source_authority"]
        self.assertEqual(authority["authority"], "unclassified")
        self.assertIn(f"/sources SYD --id {authority['source_id']} --authority KIND", authority["next_step"])


if __name__ == "__main__":
    unittest.main()
