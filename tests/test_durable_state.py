"""IMP-300 (H18): state.json keeps only what is durable, versioned and migrated."""
from __future__ import annotations

import io
import json
import os
import shutil
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from sentinel.cli import main
from sentinel.core.paths import command_log_path, derived_state_path, state_path, workspace_path
from sentinel.core.state import DERIVED_KEYS, SCHEMA_VERSION, read_command_log, read_state, update_state
from sentinel.errors import EXIT_INPUT

PROJECT = "DURABLE"
RAW = "# Billing Portal\n\nFinance users review monthly invoices before approval. Approval must be logged.\n"


def _run(argv: list[str]) -> tuple[int, str]:
    out = io.StringIO()
    with redirect_stdout(out), redirect_stderr(io.StringIO()):
        code = main(argv)
    return code, out.getvalue()


def _raw(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


class DurableStateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.old_cwd = Path.cwd()
        self.temp = Path(tempfile.mkdtemp())
        os.chdir(self.temp)
        raw = self.temp / "billing.md"
        raw.write_text(RAW, encoding="utf-8")
        self.assertEqual(_run(["init", PROJECT, "--brief-version", "1"])[0], 0)
        self.assertEqual(_run(["ingest", PROJECT, "--source", str(raw)])[0], 0)
        self.workspace = workspace_path(PROJECT)

    def tearDown(self) -> None:
        os.chdir(self.old_cwd)
        shutil.rmtree(self.temp, ignore_errors=True)

    def write_090_state(self, **extra: object) -> dict:
        """The state as 0.9.0 left it: one file, no schema_version, the command log inside."""
        state = read_state(PROJECT)
        state.pop("schema_version", None)
        state["command_log"] = [
            {"timestamp": "2026-11-01T10:00:00Z", "command": "ingest", "phase": "discovery", "health": "DIRTY", "summary": "completed"},
            {"timestamp": "2026-11-01T10:05:00Z", "command": "status", "phase": "discovery", "health": "DIRTY", "summary": "completed"},
        ]
        state.update(extra)
        shutil.rmtree(self.workspace / ".sentinel", ignore_errors=True)
        state_path(PROJECT).write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
        return state

    def test_state_json_holds_only_durable_keys_with_a_schema_version(self) -> None:
        durable = _raw(state_path(PROJECT))
        self.assertEqual(durable["schema_version"], SCHEMA_VERSION)
        self.assertFalse(set(DERIVED_KEYS) & set(durable), "derived keys left in state.json")
        self.assertNotIn("command_log", durable)
        self.assertIn("gap_counts", _raw(derived_state_path(PROJECT)))
        self.assertIn("gap_counts", read_state(PROJECT), "read_state merges both halves")
        self.assertTrue(read_command_log(PROJECT), "commands are logged to the jsonl")

    def test_update_state_routes_each_key_to_its_half(self) -> None:
        update_state(PROJECT, gap_counts={"open": 7}, phase="discovery")
        self.assertEqual(_raw(derived_state_path(PROJECT))["gap_counts"], {"open": 7})
        self.assertNotIn("gap_counts", _raw(state_path(PROJECT)))
        self.assertEqual(_raw(state_path(PROJECT))["phase"], "discovery")

    def test_a_090_workspace_migrates_once_with_a_backup(self) -> None:
        absolute = (self.workspace / "08_context_packs" / "exports" / "prd.md").as_posix()
        legacy = self.write_090_state(last_export=absolute, maturity_metrics={"maturity_score": 0.4})
        original = state_path(PROJECT).read_bytes()

        self.assertEqual(_run(["status", PROJECT])[0], 0)

        backup = self.workspace / ".sentinel" / "state.json.bak-0.9.0"
        self.assertEqual(backup.read_bytes(), original)
        durable = _raw(state_path(PROJECT))
        self.assertEqual(durable["schema_version"], SCHEMA_VERSION)
        self.assertEqual(durable["migrated_from"], "0.9.0")
        self.assertFalse(set(DERIVED_KEYS) & set(durable))
        self.assertNotIn("command_log", durable)
        self.assertEqual(durable["last_export"], "08_context_packs/exports/prd.md")
        self.assertEqual(durable["phase"], legacy["phase"])
        self.assertEqual(durable["brief_settings"], legacy["brief_settings"])
        derived = _raw(derived_state_path(PROJECT))
        self.assertEqual(derived["gap_counts"], legacy["gap_counts"])
        self.assertEqual(derived["maturity_metrics"], {"maturity_score": 0.4})
        commands = [entry["command"] for entry in read_command_log(PROJECT)]
        self.assertEqual(commands, ["ingest", "status", "status"], "the old log first, then the new command")

        self.assertEqual(_run(["status", PROJECT])[0], 0)
        self.assertEqual(backup.read_bytes(), original, "the backup is written once")

    def test_a_newer_schema_is_refused_and_left_untouched(self) -> None:
        state = _raw(state_path(PROJECT))
        state["schema_version"] = SCHEMA_VERSION + 1
        state_path(PROJECT).write_text(json.dumps(state), encoding="utf-8")
        before = state_path(PROJECT).read_bytes()
        self.assertEqual(_run(["status", PROJECT])[0], EXIT_INPUT)
        self.assertEqual(_run(["sync", PROJECT])[0], EXIT_INPUT)
        self.assertEqual(state_path(PROJECT).read_bytes(), before)

    def test_deleting_the_derived_state_and_running_status_gives_the_same_status(self) -> None:
        def status() -> dict:
            code, text = _run(["status", PROJECT, "--full"])
            self.assertEqual(code, 0)
            return json.loads(text)

        before = status()
        shutil.rmtree(self.workspace / ".sentinel" / "derived")
        after = status()
        self.assertEqual(after, before)

    def test_the_command_log_is_append_only_and_tolerates_a_torn_line(self) -> None:
        path = command_log_path(PROJECT)
        count = len(read_command_log(PROJECT))
        with open(path, "a", encoding="utf-8") as handle:
            handle.write('{"command": "half')  # a crash mid-line
        self.assertEqual(_run(["status", PROJECT])[0], 0)
        self.assertEqual(len(read_command_log(PROJECT)), count + 1)
        self.assertTrue(path.read_text(encoding="utf-8").startswith("{"))


if __name__ == "__main__":
    unittest.main()
