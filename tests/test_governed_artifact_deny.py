"""IMP-179: deterministic governed-artifact deny, enforced on every surface.

A governed artifact (project-brief.md, 03_specs/*.md, 04_backlog/*.md) may be
mutated only through its owning command (invariant #1). This denies a hand
Write/Edit at the tool boundary. The decision logic lives once in
sentinel.hooks_logic and is enforced by the Codex hook (block), the Claude
PreToolUse command hook (deny), and the Kilo file.deny globs — these guards must
protect the same set. Reads and the CLI itself are never blocked.
"""

import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

from sentinel import hooks_logic
from sentinel.hooks_logic import GOVERNED_ARTIFACT_GLOBS, governed_artifact_deny_reason, is_governed_artifact

REPO = Path(__file__).resolve().parents[1]
CLAUDE_HOOK = REPO / ".claude" / "hooks" / "deny-governed-artifact-write.py"
CLAUDE_SETTINGS = REPO / ".claude" / "settings.json"
KILO_CONFIG = REPO / "kilo.jsonc"

GOVERNED_SAMPLES = [
    "workspaces/DEMO/02_requirements/project-brief.md",
    "workspaces/DEMO/03_specs/prd.md",
    "workspaces/DEMO/03_specs/specs.md",
    "workspaces/DEMO/04_backlog/BACKLOG.md",
    "workspaces/DEMO/04_backlog/US-001.md",
    r"C:\dev\repo\workspaces\DEMO\03_specs\prd.md",  # windows separators
]
NOT_GOVERNED_SAMPLES = [
    "workspaces/DEMO/01_discovery/gaps.md",
    "workspaces/DEMO/02_requirements/other.md",
    "workspaces/DEMO/03_specs/units/SPEC-U-001.md",  # nested, not top-level 03_specs/*.md
    "sentinel/cli.py",
    "README.md",
    "input/client_requirement/raw.md",
]


class GovernedArtifactMatch(unittest.TestCase):
    def test_governed_samples_match(self):
        for path in GOVERNED_SAMPLES:
            self.assertTrue(is_governed_artifact(path), f"should be governed: {path}")

    def test_non_governed_samples_do_not_match(self):
        for path in NOT_GOVERNED_SAMPLES:
            self.assertFalse(is_governed_artifact(path), f"should not be governed: {path}")


class GovernedArtifactDenyDecision(unittest.TestCase):
    def test_mutating_tool_on_governed_artifact_denies(self):
        for tool in ("Write", "Edit", "MultiEdit", "apply_patch", "write_to_file"):
            self.assertIsNotNone(
                governed_artifact_deny_reason(tool, GOVERNED_SAMPLES[0]),
                f"{tool} on a governed artifact must be denied",
            )

    def test_read_tools_are_allowed(self):
        for tool in ("Read", "Grep", "Glob", "view", ""):
            self.assertIsNone(
                governed_artifact_deny_reason(tool, GOVERNED_SAMPLES[0]),
                f"{tool!r} must never be denied (reads and unknown tools fail open)",
            )

    def test_mutating_tool_on_non_governed_path_is_allowed(self):
        self.assertIsNone(governed_artifact_deny_reason("Write", "sentinel/cli.py"))

    def test_codex_hook_blocks_governed_write(self):
        decision = hooks_logic.pre_tool_use_decision("Write", {"path": GOVERNED_SAMPLES[0]})
        self.assertEqual(decision["decision"], "block")
        self.assertIn("owning command", decision["reason"])

    def test_codex_hook_allows_non_governed_write(self):
        decision = hooks_logic.pre_tool_use_decision("Write", {"path": "sentinel/cli.py"})
        self.assertEqual(decision["decision"], "allow")


class ClaudePreToolUseHookScript(unittest.TestCase):
    def _run(self, payload):
        return subprocess.run(
            [sys.executable, str(CLAUDE_HOOK)],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
        )

    def test_denies_governed_write(self):
        result = self._run({"tool_name": "Write", "tool_input": {"file_path": GOVERNED_SAMPLES[0]}})
        self.assertEqual(result.returncode, 0)
        emitted = json.loads(result.stdout)
        decision = emitted["hookSpecificOutput"]
        self.assertEqual(decision["hookEventName"], "PreToolUse")
        self.assertEqual(decision["permissionDecision"], "deny")
        self.assertIn("owning command", decision["permissionDecisionReason"])

    def test_allows_non_governed_write(self):
        result = self._run({"tool_name": "Edit", "tool_input": {"file_path": "sentinel/cli.py"}})
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "")

    def test_malformed_stdin_fails_open(self):
        result = subprocess.run(
            [sys.executable, str(CLAUDE_HOOK)], input="not json", capture_output=True, text=True
        )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "")


class CrossSurfaceConsistency(unittest.TestCase):
    """The three surfaces must protect the same governed set."""

    def test_kilo_deny_lists_every_governed_glob(self):
        text = KILO_CONFIG.read_text(encoding="utf-8")
        for glob in GOVERNED_ARTIFACT_GLOBS:
            self.assertIn(glob, text, f"kilo.jsonc file.deny is missing governed glob: {glob}")

    def test_claude_settings_wire_the_pretooluse_deny(self):
        settings = json.loads(CLAUDE_SETTINGS.read_text(encoding="utf-8"))
        pre = settings["hooks"]["PreToolUse"]
        self.assertTrue(pre, "no PreToolUse hook wired")
        entry = pre[0]
        self.assertEqual(entry["matcher"], "Write|Edit")
        commands = " ".join(h.get("command", "") for h in entry["hooks"])
        self.assertIn("deny-governed-artifact-write.py", commands)

    def test_every_glob_maps_to_a_denied_concrete_path(self):
        # Ties the glob list (Kilo/settings source of truth) to the regex used by
        # the Codex/Claude hooks — a concretized glob must be denied for a write.
        for glob in GOVERNED_ARTIFACT_GLOBS:
            concrete = glob.replace("workspaces/*/", "workspaces/DEMO/").replace("/*.md", "/sample.md")
            self.assertIsNotNone(
                governed_artifact_deny_reason("Write", concrete),
                f"glob {glob} concretized to {concrete} is not denied by the shared logic",
            )


if __name__ == "__main__":
    unittest.main()
