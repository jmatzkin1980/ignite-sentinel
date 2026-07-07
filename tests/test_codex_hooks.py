"""Coverage for the Codex hooks and their shared decision logic (IMP-172).

The hooks previously (a) invited hand-editing of governed artifacts, (b) indexed
workspace files into memory as a silent side channel, and (c) carried a dead
local-first guardrail anchored to the pre-rename repo name. They now delegate to
``sentinel.hooks_logic`` and only ever SIGNAL. These tests lock that in.
"""

import importlib.util
import re
import unittest
from pathlib import Path

from sentinel import hooks_logic

REPO_ROOT = Path(__file__).resolve().parents[1]
HOOKS_DIR = REPO_ROOT / ".codex" / "hooks"
# Matches the verb "patch"/"patching" in prose, not identifiers like `apply_patch`.
FORBIDDEN_INVITATIONS = re.compile(r"manual artifact edits|(?<!\w)patch", re.IGNORECASE)


def _load_hook(filename):
    path = HOOKS_DIR / filename
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class HooksLogicDecisions(unittest.TestCase):
    def test_pre_allows_and_is_silent_for_workspace_path(self):
        # A non-governed workspace path: no misplacement warning, and no deny.
        result = hooks_logic.pre_tool_use_decision(
            "Write", {"path": "workspaces/DEMO/01_discovery/gaps.md"}
        )
        self.assertEqual(result["decision"], "allow")
        self.assertNotIn("Warning", result["reason"])

    def test_pre_warns_on_misplaced_workspace_content(self):
        result = hooks_logic.pre_tool_use_decision(
            "Write", {"path": "somewhere/02_requirements/project-brief.md"}
        )
        self.assertEqual(result["decision"], "allow")  # signals, never blocks
        self.assertIn("local-first", result["reason"])

    def test_pre_does_not_false_fire_on_framework_docs(self):
        for path in ("README.md", "docs/evolution/10-base.md", "sentinel/cli.py", "user_guide/00.md"):
            self.assertIsNone(
                hooks_logic.local_first_warning(path),
                f"local-first guardrail false-fired on framework file {path}",
            )

    def test_post_reminds_to_regenerate_governed_artifact(self):
        result = hooks_logic.post_tool_use_decision(
            "Write", {"path": "workspaces/DEMO/03_specs/prd.md"}
        )
        self.assertEqual(result["decision"], "allow")
        self.assertIn("/health", result["reason"])
        self.assertIn("owning Sentinel command", result["reason"])

    def test_post_flags_project_language_for_client_facing_artifacts(self):
        result = hooks_logic.post_tool_use_decision(
            "Write", {"path": "workspaces/DEMO/01_discovery/gaps.md"}
        )
        self.assertIn("project_language", result["reason"])

    def test_decisions_allow_for_non_governed_paths(self):
        # Non-governed paths are never blocked. (Governed-artifact writes DO block
        # in pre — IMP-179 — covered by tests/test_governed_artifact_deny.py.)
        for path in ("", "workspaces/DEMO/01_discovery/gaps.md", "/etc/passwd", "somewhere/07_changes/x.md"):
            self.assertEqual(hooks_logic.pre_tool_use_decision("Write", {"path": path})["decision"], "allow")
            self.assertEqual(hooks_logic.post_tool_use_decision("Write", {"path": path})["decision"], "allow")

    def test_post_never_blocks_even_governed(self):
        # PostToolUse is verification-only; it never blocks, even for a governed artifact.
        result = hooks_logic.post_tool_use_decision("Write", {"path": "workspaces/DEMO/03_specs/prd.md"})
        self.assertEqual(result["decision"], "allow")

    def test_bad_args_are_tolerated(self):
        for args in (None, {}, {"path": None}, "not-a-dict"):
            self.assertEqual(hooks_logic.pre_tool_use_decision("Write", args)["decision"], "allow")
            self.assertEqual(hooks_logic.post_tool_use_decision("Write", args)["decision"], "allow")


class GuardrailFiresOnRealRepoPath(unittest.TestCase):
    """A3: the old guardrail used the hard-coded ``ignite-sentinel/`` substring and
    never fired after the -vnext rename. The new one must fire on a real repo path."""

    def test_misplaced_workspace_artifact_under_repo_root(self):
        real_path = str(REPO_ROOT / "02_requirements" / "project-brief.md")
        self.assertIsNotNone(hooks_logic.local_first_warning(real_path))


class NoForbiddenInvitations(unittest.TestCase):
    def test_hook_sources_free_of_hand_edit_invitations(self):
        sources = list(HOOKS_DIR.glob("*.py")) + [REPO_ROOT / "sentinel" / "hooks_logic.py"]
        for src in sources:
            text = src.read_text(encoding="utf-8")
            self.assertIsNone(
                FORBIDDEN_INVITATIONS.search(text),
                f"{src.name} still contains a hand-edit invitation ('manual artifact edits'/'patch')",
            )


class NoSideChannelIndexing(unittest.TestCase):
    """A2: the post hook must not index memory or duplicate runtime classification."""

    def test_post_hook_has_no_indexing_symbols(self):
        text = (HOOKS_DIR / "post_tool_use_audit.py").read_text(encoding="utf-8")
        self.assertNotIn("index_workspace_artifact", text)
        self.assertNotIn("classify_path", text)
        self.assertNotIn("ContextBroker", text)


class HookShimsDelegate(unittest.TestCase):
    def test_post_shim_allows_and_delegates(self):
        module = _load_hook("post_tool_use_audit.py")
        result = module.post_tool_use("Write", {"path": "workspaces/DEMO/03_specs/prd.md"})
        self.assertEqual(result["decision"], "allow")
        self.assertIn("/validate", result["reason"])

    def test_pre_shim_allows_and_delegates(self):
        module = _load_hook("pre_tool_use_policy.py")
        result = module.pre_tool_use("Write", {"path": "somewhere/02_requirements/brief.md"})
        self.assertEqual(result["decision"], "allow")
        self.assertIn("local-first", result["reason"])


if __name__ == "__main__":
    unittest.main()
