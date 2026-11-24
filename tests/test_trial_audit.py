"""tools/trial_audit.py measures a trial from its transcript (IMP-408)."""

from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "tools"))
import trial_audit  # noqa: E402

FIXTURE = REPO_ROOT / "tests" / "fixtures" / "trial_audit" / "session.jsonl"
SHELL_FIXTURE = REPO_ROOT / "tests" / "fixtures" / "trial_audit" / "shell_forms.jsonl"


class TrialAuditTests(unittest.TestCase):
    def setUp(self):
        self.report = trial_audit.audit(FIXTURE)

    def test_skills_and_commands(self):
        r = self.report
        self.assertEqual(r["skills_invoked"], {"sentinel-command-router": 1, "sentinel-gap-response": 1})
        self.assertEqual([c["verb"] for c in r["commands"]], ["ingest", "resolve-gaps", "resolve-gaps"])
        self.assertEqual(
            [c["expected_skill"] for c in r["commands"]],
            ["sentinel-discovery", "sentinel-gap-response", "sentinel-gap-response"],
        )
        self.assertEqual([c["skill_before"] for c in r["commands"]], [False, False, True])
        self.assertEqual(r["expected_missing"], ["sentinel-discovery"])
        self.assertEqual(r["late_skills"], 2)

    def test_runtime_reads(self):
        self.assertEqual(self.report["runtime_reads"], {"sentinel/gap_resolution.py": 1, "sentinel/changes.py": 1})

    def test_format_rejections(self):
        commands = self.report["commands"]
        self.assertEqual([c["line"] for c in commands], [2, 5, 9])
        self.assertEqual(
            self.report["format_rejections"],
            [{"verb": "resolve-gaps", "line": 5, "error": "sentinel error: línea 4: tipo desconocido"}],
        )
        self.assertEqual(commands[1]["exit"], 3)
        self.assertEqual(commands[2]["exit"], 0)

    def test_unparsed_lines_counted(self):
        self.assertEqual(self.report["unparsed_lines"], 1)
        self.assertEqual(self.report["summary"]["commands"], 3)
        self.assertEqual(sum(self.report["skills_invoked"].values()), 2)

    def test_markdown_and_out(self):
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(trial_audit.main([str(FIXTURE), "--out", tmp]), 0)
            md = (Path(tmp) / "trial_audit.md").read_text(encoding="utf-8")
            self.assertIn("## Runtime reads", md)
            self.assertIn("sentinel/changes.py", md)
            data = json.loads((Path(tmp) / "trial_audit.json").read_text(encoding="utf-8"))
            self.assertEqual(
                data["summary"],
                {"skills": 2, "commands": 3, "runtime_reads": 2, "format_rejections": 1, "format_retries": 0, "missing_skills": 1},
            )
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(trial_audit.main(["no-existe.jsonl"]), 2)


class ShellFormsTests(unittest.TestCase):
    """A synthetic transcript: `$L /verb`, a loop, a shell function, exit 0 with only findings."""

    def setUp(self):
        self.report = trial_audit.audit(SHELL_FIXTURE)

    def test_commands_through_a_variable_or_function_are_counted(self):
        self.assertEqual(
            [c["verb"] for c in self.report["commands"]],
            ["cross", "extract", "resolve-gaps", "resolve-gaps", "resolve-gaps"],
        )

    def test_a_non_sentinel_command_is_not_counted(self):
        self.assertEqual(self.report["summary"]["commands"], 5)

    def test_error_without_exit_code_is_a_rejection(self):
        self.assertEqual([r["line"] for r in self.report["format_rejections"]], [9])

    def test_same_input_after_findings_is_a_retry(self):
        self.assertEqual(self.report["format_retries"], [{"verb": "resolve-gaps", "line": 7, "value": "r.md"}])
        self.assertEqual(self.report["summary"]["format_retries"], 1)


if __name__ == "__main__":
    unittest.main()
