"""IMP-290 — the plugin finds Python 3.10+ even when `python` is not on PATH.

A BA's Windows laptop often has Python installed but neither `python` nor `py`
on PATH, or only the Microsoft Store alias, which is not Python. The plugin's
hook and skills therefore run through `python.sh`, a POSIX resolver that tries
SENTINEL_PYTHON, then `python3` / `python` / `py -3` (skipping Store aliases),
then the usual Windows install folders, and fails with an actionable message.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from sentinel import adapters
from sentinel import plugin_package as pp

REPO_ROOT = Path(__file__).resolve().parents[1]
SH = shutil.which("sh")
SHIM = f"plugins/{pp.PLUGIN_NAME}/{pp.PYTHON_SHIM}"
INVOKE = f'sh "${{CLAUDE_PLUGIN_ROOT}}/{pp.PYTHON_SHIM}"'


class GeneratedInvocationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.files = pp.expected_plugin_files(REPO_ROOT)

    def test_shim_is_generated_with_lf(self) -> None:
        content = self.files[SHIM]
        self.assertTrue(content.startswith(b"#!/bin/sh\n"))
        self.assertNotIn(b"\r", content)

    def test_shim_is_checked_out_with_lf(self) -> None:
        # Git for Windows defaults to core.autocrlf=true; a CRLF shell script breaks.
        attributes = (REPO_ROOT / ".gitattributes").read_text(encoding="utf-8")
        self.assertRegex(attributes, r"(?m)^\*\.sh\s+text\s+eol=lf\s*$")

    def test_hook_runs_through_the_shim(self) -> None:
        hooks = json.loads(self.files[f"plugins/{pp.PLUGIN_NAME}/hooks/hooks.json"])
        command = hooks["hooks"]["PreToolUse"][0]["hooks"][0]["command"]
        self.assertTrue(command.startswith(INVOKE + " "), command)
        self.assertIn('"${CLAUDE_PLUGIN_ROOT}/hooks/deny-governed-artifact-write.py"', command)

    def test_skills_run_through_the_shim(self) -> None:
        overlay = adapters.SKILL_OVERLAYS["claude-plugin"]
        self.assertEqual(overlay, INVOKE + ' "${CLAUDE_PLUGIN_ROOT}/launcher.py"')
        rendered = [
            content.decode("utf-8")
            for name, content in self.files.items()
            if name.startswith(f"plugins/{pp.PLUGIN_NAME}/skills/") and name.endswith("SKILL.md")
        ]
        self.assertTrue(any(overlay in text for text in rendered))
        for text in rendered:
            self.assertNotIn('python "${CLAUDE_PLUGIN_ROOT}', text)

    def test_committed_plugin_is_in_sync(self) -> None:
        self.assertEqual(pp.plugin_out_of_sync(REPO_ROOT), [])


def _fake(directory: Path, name: str, body: str) -> Path:
    path = directory / name
    path.write_bytes(f"#!/bin/sh\n{body}\n".encode("utf-8"))
    path.chmod(0o755)
    return path


def _posix(path: Path) -> str:
    """The path as `sh` sees it (Git Bash on Windows maps C:\\x to /c/x)."""
    text = path.resolve().as_posix()
    if os.name == "nt" and len(text) > 1 and text[1] == ":":
        return f"/{text[0].lower()}{text[2:]}"
    return text


@unittest.skipUnless(SH, "needs a POSIX sh (Git Bash on Windows)")
class ResolverTests(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.shim = self.tmp / pp.PYTHON_SHIM
        self.shim.write_bytes(pp.expected_plugin_files(REPO_ROOT)[SHIM])
        self.empty = self.tmp / "empty-bin"
        self.empty.mkdir()
        # A real interpreter, reachable only through what each test puts on PATH.
        self.real = self.tmp / "real-bin"
        self.real.mkdir()
        _fake(self.real, "python", f'exec "{_posix(Path(sys.executable))}" "$@"')

    def _run(self, path_dirs: list[Path], **env: str) -> subprocess.CompletedProcess[str]:
        system = [d for d in ("/usr/bin", "/bin") if Path(d).exists()] if os.name != "nt" else []
        base = {k: v for k, v in os.environ.items() if k in {"SYSTEMROOT", "TEMP", "TMP", "HOME", "USERPROFILE"}}
        tool_dirs = []
        if os.name == "nt":
            tool_dirs = [str(Path(SH).parent)]  # Git Bash: sh, sed, command
        base["PATH"] = os.pathsep.join([str(d) for d in path_dirs] + tool_dirs + system)
        base.update(env)
        return subprocess.run(
            [SH, str(self.shim), "-c", "import sys; print(sys.version_info >= (3, 10))"],
            capture_output=True, text=True, env=base, timeout=60,
        )

    def test_uses_python_on_path(self) -> None:
        result = self._run([self.real])
        self.assertEqual(result.stdout.strip(), "True", result.stderr)

    def test_sentinel_python_wins(self) -> None:
        result = self._run([self.empty], SENTINEL_PYTHON=sys.executable)
        self.assertEqual(result.stdout.strip(), "True", result.stderr)

    def test_skips_a_python_older_than_3_10(self) -> None:
        old = self.tmp / "old-bin"
        old.mkdir()
        _fake(old, "python3", "exit 1")  # fails the version probe
        result = self._run([old, self.real])
        self.assertEqual(result.stdout.strip(), "True", result.stderr)

    def test_skips_the_microsoft_store_alias(self) -> None:
        store = self.tmp / "WindowsApps"
        store.mkdir()
        _fake(store, "python3", "echo STORE-ALIAS; exit 0")  # would pass a naive probe
        result = self._run([store, self.real])
        self.assertNotIn("STORE-ALIAS", result.stdout)
        self.assertEqual(result.stdout.strip(), "True", result.stderr)

    @unittest.skipIf(os.name == "nt", "a fake python.exe must be a real binary on Windows")
    def test_finds_python_in_the_windows_install_folder(self) -> None:
        local = self.tmp / "LocalAppData"
        folder = local / "Programs" / "Python" / "Python313"
        folder.mkdir(parents=True)
        _fake(folder, "python.exe", f'exec "{sys.executable}" "$@"')
        result = self._run([self.empty], LOCALAPPDATA=str(local))
        self.assertEqual(result.stdout.strip(), "True", result.stderr)

    def test_no_python_fails_with_guidance(self) -> None:
        result = self._run([self.empty], LOCALAPPDATA=str(self.tmp / "none"))
        self.assertEqual(result.returncode, 127)
        self.assertIn("Python 3.10", result.stderr)
        self.assertIn("SENTINEL_PYTHON", result.stderr)


if __name__ == "__main__":
    unittest.main()
