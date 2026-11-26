"""IMP-425 (H27 inc 7b, task 4): the `/setup` command. No network: the downloader is never reachable."""

from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from sentinel import semantic_setup
from sentinel.cli import main
from sentinel.commands import EXEMPT, REGISTRY
from sentinel.mcp import describe_tools

from tests.helpers import run_cli, run_ok

GOOD = {"config.json": b'{"fixture": true}', "model.safetensors": b"\x00\x01weights\xff"}


def _manifest() -> dict:
    return {
        "schema": 1,
        "default": "tiny",
        "allowed_hosts": ["huggingface.co"],
        "allowed_host_suffixes": [],
        "models": [{
            "id": "tiny", "embedder": "model2vec", "repo": "o/tiny", "revision": "a" * 40,
            "url_template": "https://huggingface.co/{repo}/resolve/{revision}/{name}",
            "files": [{"name": n, "sha256": hashlib.sha256(b).hexdigest(), "size": len(b)} for n, b in GOOD.items()],
        }],
    }


def run_cli_err(argv: list[str]) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = main(list(argv))
        except SystemExit as exc:
            code = int(exc.code or 0)
    return code, out.getvalue(), err.getvalue()


class SetupCommandTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.home = self.root / "home"
        patcher = mock.patch.dict(os.environ, {"SENTINEL_HOME": str(self.home)})
        patcher.start()
        self.addCleanup(patcher.stop)
        p = mock.patch.object(semantic_setup, "load_manifest", _manifest)
        p.start()
        self.addCleanup(p.stop)
        p = mock.patch("importlib.util.find_spec", return_value=object())
        p.start()
        self.addCleanup(p.stop)
        p = mock.patch.object(semantic_setup, "subprocess_fetch", side_effect=AssertionError("network"))
        self.fetch = p.start()
        self.addCleanup(p.stop)

    def _source(self, bad: bool = False) -> Path:
        src = self.root / "src"
        src.mkdir()
        for name, data in GOOD.items():
            (src / name).write_bytes(data[:-1] + b"x" if bad and name == "model.safetensors" else data)
        return src

    def test_setup_registered_exempt_no_mcp(self) -> None:
        entry = next(c for c in REGISTRY if c.name == "setup")
        self.assertEqual(entry.protocol, EXEMPT)
        self.assertIs(entry.mcp, False)
        self.assertEqual(entry.skill, "sentinel-health")
        self.assertNotIn("sentinel_setup", [t["name"] for t in describe_tools()])

    def test_cli_status_runs_without_project(self) -> None:
        out = run_ok(["/setup", "--semantic-memory", "--status"])
        self.assertEqual(json.loads(out)["status"], "missing")

    def test_status_exit_codes(self) -> None:
        # IMP-425 final review M5: 0 for installed and missing, 1 for a mismatch.
        self.assertEqual(run_cli_err(["/setup", "--semantic-memory", "--status"])[0], 0)
        code, _, _ = run_cli_err(["/setup", "--semantic-memory", "--offline-from", str(self._source()), "--root", str(self.root)])
        self.assertEqual(code, 0)
        code, out, _ = run_cli_err(["/setup", "--semantic-memory", "--status"])
        self.assertEqual((code, json.loads(out)["status"]), (0, "installed"))
        target = next((self.home / "models").rglob("model.safetensors"))
        target.write_bytes(b"tampered")
        code, out, _ = run_cli_err(["/setup", "--semantic-memory", "--status"])
        self.assertEqual((code, json.loads(out)["status"]), (1, "mismatch"))

    def test_cli_requires_flag(self) -> None:
        self.assertEqual(run_cli_err(["/setup"])[0], 2)
        self.assertEqual(run_cli_err(["/setup", "--semantic-memory", "--status", "--offline-from", "x"])[0], 2)

    def test_cli_offline_from(self) -> None:
        code, out, _ = run_cli_err(["/setup", "--semantic-memory", "--offline-from", str(self._source()), "--root", str(self.root)])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["status"], "installed")

    def test_cli_offline_from_corrupt_exits_1(self) -> None:
        code, out, err = run_cli_err(["/setup", "--semantic-memory", "--offline-from", str(self._source(bad=True)), "--root", str(self.root)])
        self.assertEqual(code, 1)
        self.assertIn("sha256 mismatch", err)
        self.assertFalse((self.home / "semantic.json").exists())

    def test_reindex_failure_keeps_model_and_warns(self) -> None:
        ws = self.root / "workspaces" / "ALPHA"
        ws.mkdir(parents=True)
        (ws / "state.json").write_text("{}", encoding="utf-8")
        with mock.patch.object(semantic_setup.memory, "reindex_workspace", side_effect=RuntimeError("boom")):
            code, out, _ = run_cli_err(["/setup", "--semantic-memory", "--offline-from", str(self._source()), "--root", str(self.root)])
        self.assertEqual(code, 0)
        result = json.loads(out)
        self.assertEqual(result["status"], "installed")
        self.assertTrue((self.home / "semantic.json").is_file())
        self.assertEqual(result["reindexed"], [])
        self.assertEqual(len(result["warnings"]), 1)
        self.assertIn("ALPHA", result["warnings"][0])
        self.assertIn("boom", result["warnings"][0])
        self.assertIn("/reindex ALPHA --full", result["warnings"][0])

    def test_project_commands_never_fetch(self) -> None:
        old = Path.cwd()
        os.chdir(self.root)
        self.addCleanup(os.chdir, old)
        (self.root / "raw.md").write_text("# Pedido\nEl sistema debe permitir alta de proveedores.\n", encoding="utf-8")
        with mock.patch.object(semantic_setup, "install_semantic_memory", side_effect=AssertionError("install")) as install:
            for argv in (["init", "NOFETCH", "--brief-version", "1"],
                         ["ingest", "NOFETCH", "--source", "raw.md"],
                         ["next", "NOFETCH"],
                         ["reindex", "NOFETCH", "--full"],
                         ["doctor"]):
                run_cli(argv)
            install.assert_not_called()
        self.fetch.assert_not_called()


class GuideExceptionTests(unittest.TestCase):
    CANON = ("Sentinel never downloads, except /setup --semantic-memory, which runs only when you ask for it "
             "(you, or your agent at your request in chat) and which checks every file's sha256 before using it.")
    OLD = ("which you run yourself", "the person runs it, not an agent", "yourself, once")
    GUIDE = Path(__file__).resolve().parent.parent / "user_guide"

    def test_guide_states_the_one_exception(self) -> None:
        for page in sorted(self.GUIDE.glob("*.md")):
            text = page.read_text(encoding="utf-8")
            self.assertNotIn("never downloads a model", text, page.name)
            self.assertNotIn("never downloads one", text, page.name)
            for old in self.OLD:
                self.assertNotIn(old, text, page.name)
        for name in ("05-traceability-and-memory.md", "06-installation-vscode.md",
                     "09-secure-environments.md", "16-portability.md"):
            self.assertIn(self.CANON, (self.GUIDE / name).read_text(encoding="utf-8"), name)
        admin = (self.GUIDE / "20-admin-guide.md").read_text(encoding="utf-8")
        manifest = semantic_setup.load_manifest()
        for host in list(manifest["allowed_hosts"]) + list(manifest.get("allowed_host_suffixes", [])):
            self.assertIn(host, admin)
        self.assertIn("--offline-from", admin)

    def test_skills_and_commands_say_the_same_thing(self) -> None:
        # IMP-425 final review I4: asked by the person, run by the person or their agent; never automatic.
        repo = self.GUIDE.parent
        for relative in (".agents/skills/sentinel-health/SKILL.md", ".claude/skills/sentinel-health/SKILL.md",
                         ".codex/skills/sentinel-health/SKILL.md", "plugins/ignite-sentinel/skills/sentinel-health/SKILL.md",
                         ".agents/skills/sentinel-command-router/SKILL.md", ".claude/commands/setup.md",
                         ".kilo/commands/setup.md", "sentinel/templates/commands_manifest.json"):
            text = (repo / relative).read_text(encoding="utf-8")
            self.assertNotIn("yourself", text.split("/setup --semantic-memory", 1)[-1][:200], relative)
            self.assertRegex(text, r"(?i)only when the user asks|only at the user|only when asked", relative)
        command = (self.GUIDE / "01-command-reference.md").read_text(encoding="utf-8")
        self.assertIn("never automatic", command)


if __name__ == "__main__":
    unittest.main()
