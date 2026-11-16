"""IMP-331: state.json keeps a rolling backup; a missing or broken state is refused, never rebuilt."""
from __future__ import annotations

import io
import os
import shutil
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from sentinel.cli import main
from sentinel.core.io import read_json
from sentinel.core.paths import state_path, workspace_path
from sentinel.core.state import read_state, update_state
from sentinel.doctor import workspace_portability_check
from sentinel.errors import EXIT_INPUT, exit_code_for, next_step_for

PROJECT = "RECOVERY"
RAW = "# Billing Portal\n\nFinance users review monthly invoices before approval. Approval must be logged.\n"


def _run(argv: list[str]) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = main(argv)
    return code, out.getvalue(), err.getvalue()


class StateRecoveryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.old_cwd = Path.cwd()
        self.temp = Path(tempfile.mkdtemp())
        os.chdir(self.temp)
        raw = self.temp / "billing.md"
        raw.write_text(RAW, encoding="utf-8")
        self.assertEqual(_run(["init", PROJECT])[0], 0)
        self.assertEqual(_run(["ingest", PROJECT, "--source", str(raw)])[0], 0)
        self.workspace = workspace_path(PROJECT)
        self.state = state_path(PROJECT)
        self.backup = self.workspace / ".sentinel" / "state.json.bak"

    def tearDown(self) -> None:
        os.chdir(self.old_cwd)
        shutil.rmtree(self.temp, ignore_errors=True)

    def test_each_state_update_keeps_the_previous_state_as_backup(self) -> None:
        self.assertTrue(self.backup.is_file(), "a used workspace has a state backup")
        previous = self.state.read_bytes()
        update_state(PROJECT, phase="discovery_checked")
        self.assertEqual(self.backup.read_bytes(), previous)
        self.assertEqual(read_json(self.state)["phase"], "discovery_checked")

    def test_a_deleted_state_with_a_backup_is_refused_naming_both_files(self) -> None:
        self.state.unlink()
        code, _, err = _run(["status", PROJECT])
        self.assertEqual(code, EXIT_INPUT, err)
        self.assertIn("state.json is missing", err)
        self.assertIn(".sentinel/state.json.bak", err)
        self.assertIn("next step:", err)
        self.assertFalse(self.state.exists(), "the state must not be rebuilt silently")

    def test_a_deleted_state_without_backup_on_a_used_workspace_is_refused(self) -> None:
        self.state.unlink()
        self.backup.unlink(missing_ok=True)
        for argv in (["status", PROJECT], ["init", PROJECT]):
            code, _, err = _run(argv)
            self.assertEqual(code, EXIT_INPUT, f"{argv}: {err}")
            self.assertIn("no backup", err)
            self.assertFalse(self.state.exists(), f"{argv} invented a new state")
        with self.assertRaises(Exception) as caught:
            update_state(PROJECT, phase="x")
        self.assertEqual(exit_code_for(caught.exception), EXIT_INPUT)

    def test_a_corrupt_state_exits_3_naming_the_file_and_the_backup(self) -> None:
        self.state.write_text('{"phase": ', encoding="utf-8")
        code, _, err = _run(["status", PROJECT])
        self.assertEqual(code, EXIT_INPUT, err)
        self.assertIn("state.json", err)
        self.assertIn("not valid JSON", err)
        self.assertIn(".sentinel/state.json.bak", err)
        self.assertNotIn("Traceback", err)

    def test_a_corrupt_workspace_json_is_reported_with_its_path_and_a_next_step(self) -> None:
        graph = self.workspace / "06_traceability" / "traceability_graph.json"
        graph.write_text('{"nodes": [', encoding="utf-8")
        with self.assertRaises(ValueError) as caught:  # still a ValueError for older handlers
            read_json(graph)
        self.assertIn("06_traceability/traceability_graph.json", str(caught.exception))
        self.assertIn(PROJECT, str(caught.exception))
        self.assertEqual(exit_code_for(caught.exception), EXIT_INPUT)
        self.assertTrue(next_step_for(caught.exception))

    def test_a_new_workspace_still_initializes(self) -> None:
        code, _, err = _run(["init", "FRESH"])
        self.assertEqual(code, 0, err)
        self.assertIsInstance(read_json(state_path("FRESH")), dict)
        self.assertEqual(read_state("NO_SUCH_PROJECT", {"x": 1}), {"x": 1})

    def test_doctor_reports_an_unreadable_or_missing_state(self) -> None:
        self.state.write_text("not json", encoding="utf-8")
        check = workspace_portability_check(self.temp)
        self.assertEqual(check["status"], "WARN")
        self.assertIn(f"{PROJECT}: state.json", check["detail"])
        self.state.unlink()
        check = workspace_portability_check(self.temp)
        self.assertIn(f"{PROJECT}: state.json is missing", check["detail"])


if __name__ == "__main__":
    unittest.main()
