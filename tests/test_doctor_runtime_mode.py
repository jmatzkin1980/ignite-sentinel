"""IMP-314: `/doctor` outside a framework clone checks the runtime, not the clone's tree.

A user who installed the Claude Code plugin, the wheel or a `.pyz` works in a
project folder without `sentinel/`, `.codex/skills`, `AGENTS.md` or the
installers. `/doctor` used to fail on every one of those paths there.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from sentinel.doctor import run_doctor

ROOT = Path(__file__).resolve().parents[1]
FRAMEWORK_CHECKS = {"core runtime", "Codex Desktop and agent instructions", "Kilo Code agents adapter", "user guide"}


class DoctorRuntimeModeTests(unittest.TestCase):
    def test_a_project_folder_gets_the_runtime_checks_only(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            result = run_doctor(Path(folder))
        names = {check["name"] for check in result["checks"]}
        self.assertEqual(result["mode"], "runtime")
        self.assertFalse(names & FRAMEWORK_CHECKS, names & FRAMEWORK_CHECKS)
        self.assertIn("python>=3.10", names)
        self.assertIn("package imports no network module", names)
        mode = next(check for check in result["checks"] if check["name"] == "doctor mode")
        self.assertIn("--root", mode["detail"])
        self.assertNotEqual(result["verdict"], "FAIL", [c for c in result["checks"] if c["status"] == "FAIL"])

    def test_the_framework_clone_keeps_every_check(self) -> None:
        result = run_doctor(ROOT)
        names = {check["name"] for check in result["checks"]}
        self.assertEqual(result["mode"], "framework")
        self.assertTrue(FRAMEWORK_CHECKS <= names)


if __name__ == "__main__":
    unittest.main()
