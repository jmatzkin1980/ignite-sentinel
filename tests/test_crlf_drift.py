"""IMP-291 — a line-ending-only change is not drift, not a new source, not a hand edit.

Sentinel writes with `os.linesep` (CRLF on Windows) and git or an editor can flip a
file to LF without touching its content. Drift, the source manifest and the
out-of-CLI-edit check hashed raw bytes, so that flip read as "source changed",
"modified" and "edited outside the CLI". Hashes are now taken over content with
CRLF folded to LF; a hash recorded before this change still matches the raw bytes.
A derived artifact with no recorded source fingerprint is reported as unverifiable
instead of silently passing [A29].
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from sentinel.cli import main
from sentinel.core.hashing import content_sha256, hash_matches
from sentinel.drift import derived_drift_warnings, record_derived_source_fingerprint
from sentinel.health import out_of_cli_edit_warnings
from sentinel.protocols import snapshot_governed_artifact_hashes
from sentinel.sources import discover_pending_sources, mark_source_processed
from sentinel.workspace import workspace_path


def _flip(path: Path, to_crlf: bool) -> None:
    data = path.read_bytes().replace(b"\r\n", b"\n")
    path.write_bytes(data.replace(b"\n", b"\r\n") if to_crlf else data)


class HashingTests(unittest.TestCase):
    def test_line_endings_do_not_change_the_hash(self) -> None:
        self.assertEqual(content_sha256(b"a\r\nb\r\n"), content_sha256(b"a\nb\n"))
        self.assertNotEqual(content_sha256(b"a\nb\n"), content_sha256(b"a\nc\n"))

    def test_a_hash_recorded_before_imp_291_still_matches(self) -> None:
        raw = b"a\r\nb\r\n"
        legacy = hashlib.sha256(raw).hexdigest()
        self.assertTrue(hash_matches(legacy, raw))
        self.assertTrue(hash_matches(content_sha256(raw), b"a\nb\n"))
        self.assertFalse(hash_matches(legacy, b"a\r\nc\r\n"))


class CrlfFlipTests(unittest.TestCase):
    def setUp(self) -> None:
        self.old_cwd = Path.cwd()
        self.temp = Path(tempfile.mkdtemp())
        os.chdir(self.temp)
        self.assertEqual(main(["init", "EOL"]), 0)
        self.base = workspace_path("EOL")
        self.brief = self.base / "02_requirements" / "project-brief.md"
        self.reqs = self.base / "02_requirements" / "requirements.md"
        self.brief.parent.mkdir(parents=True, exist_ok=True)
        self.brief.write_bytes(b"# Brief\r\n\r\nObjective: reduce churn.\r\n")
        self.reqs.write_bytes(b"# Requirements\r\n\r\nREQ-EARS-001: the system shall notify.\r\n")

    def tearDown(self) -> None:
        os.chdir(self.old_cwd)
        shutil.rmtree(self.temp, ignore_errors=True)

    def test_drift_ignores_a_line_ending_flip(self) -> None:
        record_derived_source_fingerprint("EOL", "specs")
        _flip(self.brief, to_crlf=False)
        self.assertEqual(derived_drift_warnings("EOL"), [])
        self.brief.write_bytes(b"# Brief\n\nObjective: reduce churn AND raise NPS.\n")
        self.assertTrue(any("DRIFTED" in w for w in derived_drift_warnings("EOL")))

    def test_source_manifest_ignores_a_line_ending_flip(self) -> None:
        note = self.base / "07_changes" / "01_meetings" / "kickoff.md"
        note.write_bytes(b"# Kickoff\r\n\r\nWe agreed on CSV.\r\n")
        mark_source_processed("EOL", note, "synced")
        _flip(note, to_crlf=False)
        self.assertEqual(discover_pending_sources("EOL"), [])

    def test_out_of_cli_edit_ignores_a_line_ending_flip(self) -> None:
        state_file = self.base / "state.json"
        state = json.loads(state_file.read_text(encoding="utf-8"))
        state["artifact_hashes"] = snapshot_governed_artifact_hashes("EOL")
        state_file.write_text(json.dumps(state), encoding="utf-8")
        _flip(self.brief, to_crlf=False)
        self.assertEqual(out_of_cli_edit_warnings("EOL", self.base), [])
        self.brief.write_bytes(b"# Brief\n\nObjective: hand edited.\n")
        self.assertEqual(len(out_of_cli_edit_warnings("EOL", self.base)), 1)

    def test_derived_artifact_without_fingerprint_is_unverifiable(self) -> None:
        specs = self.base / "03_specs" / "specs.md"
        specs.parent.mkdir(parents=True, exist_ok=True)
        specs.write_text("# Specs\n", encoding="utf-8")
        warnings = derived_drift_warnings("EOL")
        self.assertEqual(len(warnings), 1, warnings)
        self.assertIn("cannot be verified", warnings[0])
        self.assertIn("`specs`", warnings[0])
        record_derived_source_fingerprint("EOL", "specs")
        self.assertEqual(derived_drift_warnings("EOL"), [])


if __name__ == "__main__":
    unittest.main()
