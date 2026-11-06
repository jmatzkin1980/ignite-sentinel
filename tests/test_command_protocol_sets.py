"""IMP-244: every CLI command is classified for the command protocol, exactly once.

A command is read-only (logged), mutating (logged, snapshot of governed artifacts,
traceability refresh) or explicitly exempt with a stated reason (it has no project,
or it creates the workspace the protocol needs). A new command that is not
classified fails this test instead of silently skipping the protocol, which is how
`/stakeholders` used to write without leaving a log entry.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import re
import shutil
import tempfile
import unittest
from pathlib import Path

from sentinel.cli import COMMANDS, main
from sentinel.protocols import MUTATING_COMMANDS, PROTOCOL_EXEMPT_COMMANDS, READ_ONLY_COMMANDS


def argparse_commands() -> set[str]:
    err = io.StringIO()
    with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
        try:
            main(["__not_a_command__"])
        except SystemExit:
            pass
    match = re.search(r"choose from ([^)]*)\)", err.getvalue())
    assert match, err.getvalue()
    return {name.strip(" '\"") for name in match.group(1).split(",")}


class ProtocolSetsTests(unittest.TestCase):
    def test_every_argparse_command_is_in_exactly_one_set(self) -> None:
        sets = {"read-only": READ_ONLY_COMMANDS, "mutating": MUTATING_COMMANDS, "exempt": set(PROTOCOL_EXEMPT_COMMANDS)}
        for command in sorted(argparse_commands()):
            with self.subTest(command=command):
                homes = [name for name, members in sets.items() if command in members]
                self.assertEqual(len(homes), 1, f"{command} is in {homes or 'no set'}")

    def test_sets_name_only_real_commands(self) -> None:
        commands = argparse_commands()
        self.assertEqual(commands, set(COMMANDS), "cli.COMMANDS must match the argparse subcommands")
        for members in (READ_ONLY_COMMANDS, MUTATING_COMMANDS, set(PROTOCOL_EXEMPT_COMMANDS)):
            self.assertEqual(members - commands, set())

    def test_exemptions_state_a_reason(self) -> None:
        self.assertEqual(set(PROTOCOL_EXEMPT_COMMANDS), {"doctor", "dashboard", "init"})
        for command, reason in PROTOCOL_EXEMPT_COMMANDS.items():
            self.assertTrue(reason.strip(), command)

    def test_stakeholders_is_mutating(self) -> None:
        self.assertIn("stakeholders", MUTATING_COMMANDS)


class StakeholdersProtocolTests(unittest.TestCase):
    def setUp(self) -> None:
        self.old = Path.cwd()
        self.tmp = Path(tempfile.mkdtemp(prefix="sentinel_protocol_"))
        os.chdir(self.tmp)
        self.addCleanup(self._cleanup)
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(["init", "PROTO"]), 0)

    def _cleanup(self) -> None:
        os.chdir(self.old)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_stakeholders_leaves_a_protocol_log_entry(self) -> None:
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(["stakeholders", "PROTO"]), 0)
        base = self.tmp / "workspaces" / "PROTO"
        log = base / "06_traceability" / "command_protocol_log.md"
        self.assertTrue(log.exists())
        self.assertIn("stakeholders", log.read_text(encoding="utf-8"))
        state = json.loads((base / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(state["last_command"], "stakeholders")
        self.assertIn("artifact_hashes", state)


if __name__ == "__main__":
    unittest.main()
