"""IMP-243: PROJECT_ID is validated at the CLI boundary (and therefore for MCP tools).

`/init ../../escape` used to create a workspace outside `workspaces/`. The id must
match ``^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$`` and resolve inside ``workspaces/``; an
invalid id fails with exit != 0, a clear message with a valid example, and nothing
is created. `/doctor` lists existing workspaces whose folder name is not a valid id.
"""

from __future__ import annotations

import contextlib
import io
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from sentinel.cli import main
from sentinel.core.paths import InvalidProjectId, validate_project_id

INVALID = ["../x", "../../escape", "a/b", "a\\b", "C:\\x", "C:x", "", "x" * 65, "-lead", "_template", "a b", "a.b", "ü"]
VALID = ["P", "ACME_PORTAL", "risk-dashboard-01", "a" * 64, "9LIVES"]


class _TempRoot(unittest.TestCase):
    def setUp(self) -> None:
        self.old = Path.cwd()
        self.tmp = Path(tempfile.mkdtemp(prefix="sentinel_pid_"))
        os.chdir(self.tmp)
        self.addCleanup(self._cleanup)

    def _cleanup(self) -> None:
        os.chdir(self.old)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_cli(self, *argv: str) -> tuple[int, str]:
        err = io.StringIO()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
            try:
                code = main(list(argv))
            except SystemExit as exc:  # argparse rejects ids that look like options (e.g. -lead)
                code = int(exc.code or 0)
                err.write(" PROJECT_ID rejected by argparse")
        return code, err.getvalue()


class ValidatorTests(_TempRoot):
    def test_valid_ids_pass(self) -> None:
        for project_id in VALID:
            with self.subTest(project_id=project_id):
                self.assertEqual(validate_project_id(project_id), project_id)

    def test_invalid_ids_are_rejected_with_an_example(self) -> None:
        for project_id in INVALID:
            with self.subTest(project_id=project_id), self.assertRaises(InvalidProjectId) as ctx:
                validate_project_id(project_id)
            self.assertIn("ACME_PORTAL", str(ctx.exception))

    def test_error_is_value_error(self) -> None:
        self.assertTrue(issubclass(InvalidProjectId, ValueError))


class CliBoundaryTests(_TempRoot):
    def test_init_with_invalid_id_fails_and_creates_nothing(self) -> None:
        for project_id in INVALID:
            with self.subTest(project_id=project_id):
                code, err = self.run_cli("init", project_id)
                self.assertNotEqual(code, 0)
                self.assertIn("PROJECT_ID", err)
        created = [path for path in self.tmp.rglob("*")]
        self.assertEqual(created, [], f"nothing may be created, found {created[:5]}")

    def test_other_commands_reject_before_touching_disk(self) -> None:
        for argv in (["status", "../x"], ["ingest", "../x", "--source", "nope.md"], ["view", "a/b", "--artifact", "prd"]):
            with self.subTest(argv=argv):
                code, err = self.run_cli(*argv)
                self.assertNotEqual(code, 0)
                self.assertIn("PROJECT_ID", err)
        self.assertEqual(list(self.tmp.rglob("*")), [])

    def test_valid_id_still_works(self) -> None:
        code, _ = self.run_cli("init", "ACME_PORTAL")
        self.assertEqual(code, 0)
        self.assertTrue((self.tmp / "workspaces" / "ACME_PORTAL" / "state.json").exists())

    def test_slash_alias_is_validated_too(self) -> None:
        code, err = self.run_cli("/init", "../escape")
        self.assertNotEqual(code, 0)
        self.assertFalse((self.tmp.parent / "escape").exists())

    def test_mcp_tools_get_a_structured_error(self) -> None:
        from sentinel.mcp import run_cli

        result = run_cli(["init", "../escape"])
        self.assertNotEqual(result["exit_code"], 0)
        self.assertFalse((self.tmp.parent / "escape").exists())


class DoctorTests(_TempRoot):
    def test_doctor_lists_workspaces_with_invalid_ids(self) -> None:
        from sentinel.doctor import project_ids_check

        (self.tmp / "workspaces" / "GOOD_ONE").mkdir(parents=True)
        (self.tmp / "workspaces" / "has.dot").mkdir()
        (self.tmp / "workspaces" / "_template").mkdir()
        result = project_ids_check(self.tmp)
        self.assertEqual(result["status"], "WARN")
        self.assertIn("has.dot", result["detail"])
        self.assertNotIn("GOOD_ONE", result["detail"])
        self.assertNotIn("_template", result["detail"])

    def test_doctor_passes_without_invalid_ids(self) -> None:
        from sentinel.doctor import project_ids_check

        (self.tmp / "workspaces" / "GOOD_ONE").mkdir(parents=True)
        self.assertEqual(project_ids_check(self.tmp)["status"], "PASS")


if __name__ == "__main__":
    unittest.main()
