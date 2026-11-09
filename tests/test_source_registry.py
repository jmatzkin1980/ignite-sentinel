"""IMP-250a — F-NN source registry: novelty by hash, row lifecycle and validity.

The manifest kept one record per path. Now each source *content* is one `F-NN`
row: the same document under two paths is one source, `/sync` twice over the
same file does not duplicate the row, a changed file is a candidate new version
that a person confirms, an open row is a `/status` finding, and validity
(current / superseded / retired / expired) changes only through `/sources`.
"""
from __future__ import annotations

import io
import json
import os
import shutil
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from sentinel.cli import main
from sentinel.readiness_verdict import build_readiness_verdict
from sentinel.source_registry import SourceRegistryError, ensure_registry, row_validity, source_kind
from sentinel.sources import (
    list_sources,
    load_source_manifest,
    open_source_row,
    source_log_path,
    update_source,
)
from sentinel.status import project_status

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


def _run(argv: list[str]) -> dict:
    out = io.StringIO()
    with redirect_stdout(out):
        code = main(argv)
    if code != 0:
        raise AssertionError(f"{argv} exited {code}: {out.getvalue()}")
    return json.loads(out.getvalue())


class SourceRegistryFlowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.old_cwd = Path.cwd()
        self.temp = Path(tempfile.mkdtemp())
        os.chdir(self.temp)
        src = self.temp / "raw.md"
        src.write_text(RAW, encoding="utf-8")
        self.assertEqual(main(["init", "REG"]), 0)
        self.assertEqual(main(["ingest", "REG", "--source", str(src)]), 0)
        self.ws = self.temp / "workspaces" / "REG"

    def tearDown(self) -> None:
        os.chdir(self.old_cwd)
        shutil.rmtree(self.temp, ignore_errors=True)

    def _rows(self) -> list[dict]:
        return load_source_manifest("REG")["registry"]

    def _bucket(self, name: str, folder: str = "01_meetings", text: str = MEETING) -> Path:
        path = self.ws / "07_changes" / folder / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def test_ingest_opens_and_closes_one_row_with_its_copy(self) -> None:
        rows = self._rows()
        self.assertEqual([row["id"] for row in rows], ["F-01"])
        self.assertEqual(rows[0]["lifecycle"], "closed")
        self.assertEqual(rows[0]["validity"], "current")
        self.assertEqual(rows[0]["paths"], ["raw.md"])
        self.assertEqual(rows[0]["copies"], ["workspaces/REG/00_raw/raw.md"])
        log = source_log_path("REG").read_text(encoding="utf-8")
        self.assertIn("| F-01 |", log)
        self.assertIn("GENERATED", log)

    def test_two_syncs_over_the_same_source_do_not_duplicate_the_row(self) -> None:
        meeting = self.temp / "meeting.md"
        meeting.write_text(MEETING, encoding="utf-8")
        first = _run(["sync", "REG", "--source", str(meeting)])
        second = _run(["sync", "REG", "--source", str(meeting)])
        self.assertEqual(first["source_id"], "F-02")
        self.assertEqual(second["source_id"], "F-02")
        rows = self._rows()
        self.assertEqual([row["id"] for row in rows], ["F-01", "F-02"])
        self.assertEqual(len(rows[1]["events"]), 2)
        self.assertEqual(rows[1]["lifecycle"], "closed")

    def test_same_source_in_two_paths_is_one_row(self) -> None:
        self._bucket("weekly.md")
        self._bucket("weekly-forwarded.md", folder="02_mail_slack")
        result = _run(["sync", "REG"])
        self.assertEqual(result["processed"], 1)
        self.assertEqual(len(result["duplicate_content"]), 1)
        rows = self._rows()
        self.assertEqual([row["id"] for row in rows], ["F-01", "F-02"])
        self.assertEqual(len(rows[1]["paths"]), 2)
        # A third copy arriving later joins the row too and is not crossed again.
        self._bucket("weekly-again.md", folder="00_client_responses")
        later = _run(["sync", "REG"])
        self.assertEqual(later["processed"], 0)
        self.assertEqual(later["duplicate_content"][0]["source_id"], "F-02")
        self.assertEqual(len(self._rows()), 2)

    def test_changed_file_is_a_candidate_version_until_a_person_confirms(self) -> None:
        notes = self._bucket("weekly.md")
        _run(["sync", "REG"])
        notes.write_text(MEETING + "- Exports also go to PDF.\n", encoding="utf-8")
        _run(["sync", "REG"])
        rows = {row["id"]: row for row in self._rows()}
        self.assertEqual(rows["F-03"]["pending_version_of"], "F-02")
        self.assertEqual(rows["F-02"]["validity"], "current")  # never "newest wins" by default
        verdict = build_readiness_verdict("REG")
        gate = next(item for item in verdict["gate_matrix"] if item["gate"] == "sources")
        self.assertEqual(gate, {"gate": "sources", "state": "OPEN", "blocks": False})
        self.assertTrue(any("F-03 is a new version of F-02" in warning for warning in verdict["warnings"]))

        _run(["sources", "REG", "--id", "F-02", "--superseded-by", "F-03", "--reason", "minutes corrected"])
        rows = {row["id"]: row for row in self._rows()}
        self.assertEqual(rows["F-02"]["validity"], "superseded")
        self.assertEqual(rows["F-02"]["superseded_by"], "F-03")
        self.assertIsNone(rows["F-03"]["pending_version_of"])
        self.assertEqual(project_status("REG", full=False)["sources"]["unconfirmed_versions"], [])
        self.assertIn("corrected by F-03", source_log_path("REG").read_text(encoding="utf-8"))

    def test_keeping_both_versions_current_also_confirms(self) -> None:
        notes = self._bucket("weekly.md")
        _run(["sync", "REG"])
        notes.write_text(MEETING + "- A second team joins.\n", encoding="utf-8")
        _run(["sync", "REG"])
        _run(["sources", "REG", "--id", "F-03", "--current"])
        self.assertEqual(project_status("REG", full=False)["sources"]["unconfirmed_versions"], [])

    def test_an_open_row_is_a_status_finding_until_closed(self) -> None:
        notes = self._bucket("weekly.md")
        source_id = open_source_row("REG", notes, "synced")  # a cross that never finished
        summary = project_status("REG", full=False)
        self.assertEqual(summary["sources"]["open"], [source_id])
        self.assertTrue(any("still open" in warning for warning in summary["verdict"]["warnings"]))
        _run(["sources", "REG", "--id", source_id, "--close", "--reason", "crossed by hand"])
        self.assertEqual(project_status("REG", full=False)["sources"]["open"], [])

    def test_counter_never_restarts(self) -> None:
        _run(["sources", "REG", "--id", "F-01", "--retire", "--reason", "client withdrew the document"])
        meeting = self.temp / "meeting.md"
        meeting.write_text(MEETING, encoding="utf-8")
        self.assertEqual(_run(["sync", "REG", "--source", str(meeting)])["source_id"], "F-02")

    def test_validity_changes_are_validated(self) -> None:
        meeting = self.temp / "meeting.md"
        meeting.write_text(MEETING, encoding="utf-8")
        _run(["sync", "REG", "--source", str(meeting)])
        bad = [
            {"retire": True},  # no reason
            {"retire": True, "reason": "dead", "replacement": "F-09"},
            {"superseded_by": "F-01"},  # itself
            {"superseded_by": "F-09"},
            {"expire": "next week"},
            {"topic": "pricing"},  # topic without expire
            {"current": True, "retire": True, "reason": "x"},
        ]
        for changes in bad:
            with self.subTest(changes=changes), self.assertRaises(SourceRegistryError):
                update_source("REG", "F-01", **changes)
        with self.assertRaises(SourceRegistryError):
            update_source("REG", "F-07", from_who="Ops")
        update_source("REG", "F-01", superseded_by="F-02")
        with self.assertRaises(SourceRegistryError):
            update_source("REG", "F-02", superseded_by="F-01")  # cycle

    def test_retire_with_replacement_and_who_delivered(self) -> None:
        meeting = self.temp / "meeting.md"
        meeting.write_text(MEETING, encoding="utf-8")
        _run(["sync", "REG", "--source", str(meeting)])
        result = _run(["sources", "REG", "--id", "F-01", "--retire", "--replacement", "F-02", "--reason", "old draft", "--from", "Ops Lead"])
        self.assertEqual(result["row"]["validity"], "retired")
        self.assertEqual(result["row"]["replacement"], "F-02")
        self.assertEqual(result["row"]["from"], "Ops Lead")
        manifest = load_source_manifest("REG")
        self.assertEqual(row_validity(manifest, "raw.md"), "retired")

    def test_expiry_can_apply_to_one_topic(self) -> None:
        update_source("REG", "F-01", expire="2026-10-01", topic="pricing")
        manifest = load_source_manifest("REG")
        self.assertEqual(row_validity(manifest, "raw.md", on="2026-11-01", topic="Pricing"), "expired")
        self.assertEqual(row_validity(manifest, "raw.md", on="2026-11-01", topic="scope"), "current")
        self.assertEqual(row_validity(manifest, "raw.md", on="2026-09-01", topic="pricing"), "current")

    def test_list_and_change_need_an_id(self) -> None:
        listing = _run(["sources", "REG"])
        self.assertEqual(listing["summary"]["rows"], 1)
        self.assertEqual(main(["sources", "REG", "--retire", "--reason", "x"]), 1)

    def test_source_log_follows_the_project_language(self) -> None:
        state_file = self.ws / "state.json"
        state = json.loads(state_file.read_text(encoding="utf-8"))
        state["project_language"] = "es"
        state_file.write_text(json.dumps(state), encoding="utf-8")
        list_sources("REG")
        log = source_log_path("REG").read_text(encoding="utf-8")
        self.assertIn("# Registro de fuentes - REG", log)
        self.assertIn("vigente", log)


class SourceRegistryMigrationTests(unittest.TestCase):
    def test_legacy_manifest_becomes_closed_rows_in_processing_order(self) -> None:
        legacy = {
            "sources": {
                "input/b.md": {"hash": "b" * 64, "status": "synced", "event_id": "CHG-2", "last_processed_at": "2026-02-01T00:00:00Z"},
                "input/a.md": {"hash": "a" * 64, "status": "initial_ingested", "event_id": None, "last_processed_at": "2026-01-01T00:00:00Z"},
                "input/a-copy.md": {"hash": "a" * 64, "status": "synced", "event_id": "CHG-3", "last_processed_at": "2026-03-01T00:00:00Z"},
                "workspaces/P/07_changes/01_meetings/b.md": {"hash": "c" * 64, "status": "change_copy", "event_id": "CHG-2"},
                "workspaces/P/07_changes/x_impact_report.md": {"hash": "d" * 64, "status": "impact_report", "event_id": "DEC-1"},
            }
        }
        manifest = ensure_registry(legacy)
        rows = manifest["registry"]
        self.assertEqual([row["id"] for row in rows], ["F-01", "F-02"])
        self.assertEqual(rows[0]["paths"], ["input/a.md", "input/a-copy.md"])
        self.assertEqual(rows[1]["copies"], ["workspaces/P/07_changes/01_meetings/b.md"])
        self.assertTrue(all(row["lifecycle"] == "closed" and row["migrated"] for row in rows))
        self.assertEqual(manifest["next_source_number"], 3)
        self.assertNotIn("source_id", manifest["sources"]["workspaces/P/07_changes/x_impact_report.md"])

    def test_kind_comes_from_the_bucket(self) -> None:
        self.assertEqual(source_kind("workspaces/P/07_changes/01_meetings/a.md"), "meeting")
        self.assertEqual(source_kind("input/client_requirement/a.md"), "client_requirement")
        self.assertEqual(source_kind("elsewhere/a.md"), "external")


if __name__ == "__main__":
    unittest.main()
