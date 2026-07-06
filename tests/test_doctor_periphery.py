"""IMP-177 (H1 + doc 38 E2): /doctor content checks for the peripheral surfaces.

Existence-only path checks let content drift pass green (the same false-green H5
closed for skills). These verify the new checks PASS on the real repo and FAIL
when a hand-edit invitation returns, the launcher loses exit-code propagation, the
opt-in hook example JSON breaks, or the read-only verifier's tool allowlist grows
to include a denylisted tool.
"""

import json
import tempfile
import unittest
from pathlib import Path

from sentinel.doctor import (
    agentic_surface_checks,
    hook_governance_checks,
    launcher_exit_code_check,
)

REPO = Path(__file__).resolve().parents[1]


class HookGovernanceDoctorCheck(unittest.TestCase):
    def test_repo_hooks_pass(self):
        for check in hook_governance_checks(REPO):
            self.assertEqual(check["status"], "PASS", f"{check['name']}: {check['detail']}")

    def test_reintroduced_invitation_is_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            hooks = root / ".codex" / "hooks"
            hooks.mkdir(parents=True)
            (hooks / "bad.py").write_text("# run /reindex after manual artifact edits\n", encoding="utf-8")
            statuses = {c["status"] for c in hook_governance_checks(root)}
            self.assertIn("FAIL", statuses)


class LauncherDoctorCheck(unittest.TestCase):
    def test_repo_launcher_passes(self):
        self.assertEqual(launcher_exit_code_check(REPO)["status"], "PASS")

    def test_missing_propagation_is_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "installers").mkdir(parents=True)
            (root / "installers" / "sentinel.ps1").write_text("& $python -m sentinel @args\n", encoding="utf-8")
            self.assertEqual(launcher_exit_code_check(root)["status"], "FAIL")


class AgenticSurfaceDoctorCheck(unittest.TestCase):
    def test_repo_surface_passes(self):
        for check in agentic_surface_checks(REPO):
            self.assertEqual(check["status"], "PASS", f"{check['name']}: {check['detail']}")

    def _scaffold(self, root: Path, agent_tools: str, example_json: str) -> None:
        hooks = root / ".claude" / "hooks"
        agents = root / ".claude" / "agents"
        hooks.mkdir(parents=True)
        agents.mkdir(parents=True)
        (hooks / "verify-governed-artifact.example.json").write_text(example_json, encoding="utf-8")
        (agents / "ignite-verifier.md").write_text(
            f"---\nname: ignite-verifier\ndescription: verifier\ntools: {agent_tools}\n---\n\n## Denylist (hard)\nnever Write/Edit/Bash.\n",
            encoding="utf-8",
        )

    def test_broken_example_json_is_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._scaffold(root, "Read, Grep, Glob", "{ not valid json")
            statuses = {c["status"] for c in agentic_surface_checks(root)}
            self.assertIn("FAIL", statuses)

    def test_allowlist_granting_denylisted_tool_is_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._scaffold(root, "Read, Grep, Glob, Bash", json.dumps({"hooks": {}}))
            checks = {c["name"]: c for c in agentic_surface_checks(root)}
            coherence = checks["agentic surface: verifier tool allowlist coherent"]
            self.assertEqual(coherence["status"], "FAIL")
            self.assertIn("Bash", coherence["detail"])


if __name__ == "__main__":
    unittest.main()
