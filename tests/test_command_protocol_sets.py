"""IMP-244: a command that writes runs inside the command protocol.

Every command is read-only (logged), mutating (logged, snapshot of governed
artifacts, traceability refresh) or explicitly exempt with a stated reason. Since
IMP-303 that classification lives in the single command registry and is checked by
`tests/test_command_registry.py`. This file keeps the behaviour check: `/stakeholders`
used to write without leaving a log entry.
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


class StakeholdersProtocolTests(unittest.TestCase):
    def setUp(self) -> None:
        self.old = Path.cwd()
        self.tmp = Path(tempfile.mkdtemp(prefix="sentinel_protocol_"))
        os.chdir(self.tmp)
        self.addCleanup(self._cleanup)
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(["init", "PROTO", "--brief-version", "1"]), 0)

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
