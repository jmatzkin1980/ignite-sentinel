"""IMP-302 (H18): typed errors with exit codes, in the CLI and in MCP.

0 success, 1 unexpected (bug), 2 usage, 3 invalid input, 4 gate refusal,
5 unfavourable verdict, 6 workspace busy. A gate refusal names its next step.
"""
from __future__ import annotations

import contextlib
import inspect
import io
import json
import os
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sentinel.cli import main
from sentinel.errors import (
    EXIT_BUG,
    EXIT_CODES,
    EXIT_GATE,
    EXIT_INPUT,
    EXIT_USAGE,
    EXIT_VERDICT,
    GateRefusal,
    InputError,
    SentinelError,
    exit_code_for,
    infer_next_step,
)
from sentinel.mcp import ToolFailed, failing_tools_raise, raise_on_failure, run_cli

ROOT = Path(__file__).resolve().parents[1]


def cli(*argv: str) -> tuple[int, str]:
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
        try:
            code = main(list(argv))
        except SystemExit as exc:
            code = int(exc.code or 0)
    return code, out.getvalue()


class MappingTests(unittest.TestCase):
    def test_codes(self) -> None:
        self.assertEqual(exit_code_for(GateRefusal("x")), EXIT_GATE)
        self.assertEqual(exit_code_for(InputError("x")), EXIT_INPUT)
        self.assertEqual(exit_code_for(ValueError("x")), EXIT_INPUT)
        self.assertEqual(exit_code_for(KeyError("x")), EXIT_BUG)
        self.assertEqual(exit_code_for(RuntimeError("x")), EXIT_BUG)
        self.assertEqual(sorted(EXIT_CODES), [0, 1, 2, 3, 4, 5, 6])

    def test_typed_errors_stay_runtime_errors(self) -> None:
        for cls in (GateRefusal, InputError):
            self.assertTrue(issubclass(cls, RuntimeError))
            self.assertTrue(issubclass(cls, SentinelError))

    def test_next_step_is_read_from_the_message(self) -> None:
        self.assertEqual(infer_next_step("Workspace not found: P. Run /init P first."), "Run /init P first.")
        self.assertEqual(infer_next_step("Cannot annotate before /ingest creates gaps.md."), "Run /ingest first.")
        self.assertEqual(infer_next_step("bad value"), "")
        self.assertEqual(GateRefusal("x", next_step="Run /health.").next_step, "Run /health.")


class CliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.old = os.getcwd()
        self.tmp = tempfile.TemporaryDirectory()
        os.chdir(self.tmp.name)

    def tearDown(self) -> None:
        os.chdir(self.old)
        self.tmp.cleanup()

    def test_a_missing_workspace_is_a_gate_refusal_with_its_next_step(self) -> None:
        code, out = cli("status", "NOPE")
        self.assertEqual(code, EXIT_GATE, out)
        self.assertIn("next step: Run /init NOPE first.", out)

    def test_a_prerequisite_is_a_gate_refusal(self) -> None:
        self.assertEqual(cli("init", "P", "--brief-version", "1")[0], 0)
        code, out = cli("specs", "P")
        self.assertEqual(code, EXIT_GATE, out)
        self.assertIn("next step: Run /ingest first.", out)

    def test_invalid_input(self) -> None:
        code, out = cli("init", "../escape")
        self.assertEqual(code, EXIT_INPUT, out)
        self.assertEqual(cli("init", "P", "--brief-version", "1")[0], 0)
        code, out = cli("stakeholders", "P", "--add", "--domain", "design")
        self.assertEqual(code, EXIT_INPUT, out)
        self.assertNotIn("Traceback", out)

    def test_usage(self) -> None:
        self.assertEqual(cli("status")[0], EXIT_USAGE)

    def test_an_unexpected_error_is_a_bug_with_its_traceback(self) -> None:
        self.assertEqual(cli("init", "P", "--brief-version", "1")[0], 0)
        with patch("sentinel.status.project_status", side_effect=KeyError("boom")):
            code, out = cli("status", "P")
        self.assertEqual(code, EXIT_BUG)
        self.assertIn("sentinel error: 'boom'", out)
        self.assertIn("Traceback", out)

    def test_unfavourable_verdicts(self) -> None:
        with patch("sentinel.doctor.run_doctor", return_value={"verdict": "FAIL"}):
            self.assertEqual(cli("doctor")[0], EXIT_VERDICT)
        self.assertEqual(cli("init", "P", "--brief-version", "1")[0], 0)
        with patch("sentinel.validation.validate_project", return_value={"verdict": "INVALID"}):
            self.assertEqual(cli("validate", "P")[0], EXIT_VERDICT)


class McpTests(unittest.TestCase):
    def setUp(self) -> None:
        self.old = os.getcwd()
        self.tmp = tempfile.TemporaryDirectory()
        os.chdir(self.tmp.name)

    def tearDown(self) -> None:
        os.chdir(self.old)
        self.tmp.cleanup()

    def test_a_failed_command_carries_its_code_and_next_step(self) -> None:
        result = run_cli(["status", "NOPE"])
        self.assertEqual((result["exit_code"], result["code"], result["kind"]), (4, 4, "gate refusal"))
        self.assertEqual(result["next_step"], "Run /init NOPE first.")

    def test_a_failed_tool_raises_so_the_result_is_an_error(self) -> None:
        self.assertEqual(raise_on_failure({"exit_code": 0, "output": {}}), {"exit_code": 0, "output": {}})
        with self.assertRaises(ToolFailed) as raised:
            raise_on_failure(run_cli(["status", "NOPE"]))
        payload = json.loads(str(raised.exception))
        self.assertEqual((payload["code"], payload["next_step"]), (4, "Run /init NOPE first."))

    def test_the_wrapper_keeps_the_tool_signature(self) -> None:
        def sentinel_probe(project_id: str, full: bool = False) -> dict:
            return {"exit_code": 0}

        registered = []
        wrapped = failing_tools_raise(lambda fn: registered.append(fn) or fn)(sentinel_probe)
        self.assertEqual(inspect.signature(wrapped), inspect.signature(sentinel_probe))
        self.assertEqual(wrapped("P"), {"exit_code": 0})


class DocumentationTests(unittest.TestCase):
    def test_the_command_reference_has_the_exit_code_table(self) -> None:
        text = (ROOT / "user_guide" / "01-command-reference.md").read_text(encoding="utf-8")
        for code in EXIT_CODES:
            self.assertRegex(text, rf"(?m)^\| {code} \|", code)


if __name__ == "__main__":
    unittest.main()
