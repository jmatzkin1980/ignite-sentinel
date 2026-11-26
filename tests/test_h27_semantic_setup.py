"""IMP-425 (H27 inc 7b): verified install of the pinned semantic model. No network:
the downloader is injected and every fixture hash is computed here."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from sentinel import semantic_setup
from sentinel.semantic_setup import (
    SetupError,
    config_path,
    install_semantic_memory,
    load_manifest,
    model_dir,
    semantic_status,
    subprocess_fetch,
)

GOOD = {"config.json": b'{"fixture": true}', "model.safetensors": b"\x00\x01weights\xff"}


def _manifest(files: dict[str, bytes] | None = None) -> dict:
    files = files or GOOD
    return {
        "schema": 1,
        "default": "tiny",
        "allowed_hosts": ["huggingface.co"],
        "allowed_host_suffixes": [".hf.co"],
        "models": [
            {
                "id": "tiny",
                "embedder": "model2vec",
                "repo": "org/tiny",
                "revision": "a" * 40,
                "url_template": "https://huggingface.co/{repo}/resolve/{revision}/{name}",
                "files": [
                    {"name": name, "sha256": hashlib.sha256(data).hexdigest(), "size": len(data)}
                    for name, data in files.items()
                ],
            }
        ],
    }


def no_fetch(url, dest, hosts):
    raise AssertionError("the network must not be used here")


class _Base(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.home = self.tmp / "home"
        self.fixtures = self.tmp / "fixtures"
        self.fixtures.mkdir()
        for name, data in GOOD.items():
            (self.fixtures / name).write_bytes(data)
        self.manifest = _manifest()
        self.model = self.manifest["models"][0]
        self.calls: list[tuple] = []
        patcher = mock.patch("importlib.util.find_spec", return_value=object())
        patcher.start()
        self.addCleanup(patcher.stop)
        env = mock.patch.dict(os.environ, {"SENTINEL_HOME": str(self.home)})
        env.start()
        self.addCleanup(env.stop)

    def fake_fetch(self, payload: dict[str, bytes] | None = None):
        payload = payload or GOOD

        def fetch(url, dest, hosts):
            self.calls.append((url, hosts))
            Path(dest).write_bytes(payload[url.rsplit("/", 1)[-1]])

        return fetch

    def install(self, **kwargs):
        kwargs.setdefault("fetch", self.fake_fetch())
        return install_semantic_memory(home=self.home, manifest=self.manifest, root=self.tmp / "noroot", **kwargs)


class ManifestTests(unittest.TestCase):
    def test_manifest_is_pinned(self) -> None:
        manifest = load_manifest()
        ids = [model["id"] for model in manifest["models"]]
        self.assertIn(manifest["default"], ids)
        hosts = set(manifest["allowed_hosts"])
        for model in manifest["models"]:
            self.assertRegex(model["revision"], r"^[0-9a-f]{40}$")
            self.assertTrue(model["url_template"].startswith("https://"))
            self.assertIn(re.match(r"https://([^/]+)/", model["url_template"]).group(1), hosts)
            self.assertTrue(model["files"])
            for entry in model["files"]:
                self.assertRegex(entry["sha256"], r"^[0-9a-f]{64}$")
                self.assertIsInstance(entry["size"], int)
                self.assertGreater(entry["size"], 0)
        for suffix in manifest["allowed_host_suffixes"]:
            self.assertTrue(suffix.startswith("."))


class InstallTests(_Base):
    def test_install_verifies_then_activates(self) -> None:
        result = self.install()
        destination = model_dir(self.home, self.model)
        self.assertEqual(result["status"], "installed")
        self.assertEqual(result["path"], str(destination))
        self.assertEqual(result["reindexed"], [])
        for name, data in GOOD.items():
            self.assertEqual((destination / name).read_bytes(), data)
        config = json.loads(config_path(self.home).read_text(encoding="utf-8"))
        self.assertEqual(config["path"], str(destination))
        self.assertEqual(config["revision"], "a" * 40)
        self.assertEqual(config["files"]["config.json"], hashlib.sha256(GOOD["config.json"]).hexdigest())
        urls = {call[0] for call in self.calls}
        self.assertIn(f"https://huggingface.co/org/tiny/resolve/{'a' * 40}/config.json", urls)
        for _, hosts in self.calls:
            self.assertEqual(hosts, ["huggingface.co", ".hf.co"])
        self.assertEqual(list((self.home / "models").glob(".staging-*")), [])

    def test_mismatch_refuses_and_cleans(self) -> None:
        bad = dict(GOOD, **{"model.safetensors": b"tampered"})
        with self.assertRaises(SetupError) as raised:
            self.install(fetch=self.fake_fetch(bad))
        self.assertIn("model.safetensors: sha256 mismatch", str(raised.exception))
        self.assertFalse(config_path(self.home).exists())
        self.assertFalse(model_dir(self.home, self.model).exists())
        self.assertEqual(list((self.home / "models").glob(".staging-*")), [])

    def test_failed_upgrade_keeps_previous(self) -> None:
        self.install()
        before = config_path(self.home).read_bytes()
        bad = dict(GOOD, **{"model.safetensors": b"tampered"})
        with self.assertRaises(SetupError):
            self.install(fetch=self.fake_fetch(bad))
        self.assertEqual(config_path(self.home).read_bytes(), before)
        destination = model_dir(self.home, self.model)
        for name, data in GOOD.items():
            self.assertEqual((destination / name).read_bytes(), data)
        self.assertEqual(list((self.home / "models").glob(".staging-*")), [])

    def test_size_mismatch_refuses(self) -> None:
        manifest = _manifest()
        manifest["models"][0]["files"][0]["size"] += 1
        with self.assertRaises(SetupError) as raised:
            install_semantic_memory(home=self.home, manifest=manifest, fetch=self.fake_fetch(), root=self.tmp / "noroot")
        self.assertIn("size mismatch", str(raised.exception))
        self.assertFalse(config_path(self.home).exists())

    def test_offline_from_same_check(self) -> None:
        result = self.install(offline_from=self.fixtures, fetch=no_fetch)
        self.assertEqual(result["status"], "installed")
        empty = self.tmp / "empty"
        empty.mkdir()
        other = self.tmp / "home2"
        with self.assertRaises(SetupError) as raised:
            install_semantic_memory(home=other, manifest=self.manifest, offline_from=empty, fetch=no_fetch, root=self.tmp / "noroot")
        self.assertIn("config.json missing in", str(raised.exception))
        self.assertFalse(config_path(other).exists())
        self.assertEqual(list((other / "models").glob(".staging-*")), [])

    def test_offline_from_wrong_bytes_is_refused(self) -> None:
        (self.fixtures / "config.json").write_bytes(b"other")
        with self.assertRaises(SetupError) as raised:
            self.install(offline_from=self.fixtures, fetch=no_fetch)
        self.assertIn("config.json: sha256 mismatch", str(raised.exception))
        self.assertFalse(config_path(self.home).exists())

    def test_package_missing_refuses_before_download(self) -> None:
        with mock.patch("importlib.util.find_spec", return_value=None):
            with self.assertRaises(SetupError) as raised:
                self.install(fetch=no_fetch)
        self.assertIn("constraints/memory-semantic.txt", str(raised.exception))
        self.assertIn("model2vec is not installed", str(raised.exception))
        self.assertFalse(self.home.exists())

    def test_reindexes_every_workspace(self) -> None:
        root = self.tmp / "repo"
        for name in ("ALFA", "BETA", "_template"):
            (root / "workspaces" / name).mkdir(parents=True)
            (root / "workspaces" / name / "state.json").write_text("{}", encoding="utf-8")
        (root / "workspaces" / "NOSTATE").mkdir()
        with mock.patch("sentinel.memory.reindex_workspace") as reindex:
            result = install_semantic_memory(home=self.home, manifest=self.manifest, fetch=self.fake_fetch(), root=root)
        self.assertEqual([call.args for call in reindex.call_args_list], [("ALFA",), ("BETA",)])
        self.assertTrue(all(call.kwargs == {"full": True} for call in reindex.call_args_list))
        self.assertEqual(result["reindexed"], ["ALFA", "BETA"])

    def test_default_fetch_is_a_subprocess(self) -> None:
        dest = self.tmp / "x.bin"
        with mock.patch("subprocess.run") as run:
            subprocess_fetch("https://huggingface.co/a", dest, ["huggingface.co", ".hf.co"])
        args, kwargs = run.call_args
        script = Path(semantic_setup.__file__).with_name("setup_download.py")
        self.assertEqual(args[0], [sys.executable, "-I", str(script), "https://huggingface.co/a", str(dest), "huggingface.co", ".hf.co"])
        self.assertIs(kwargs["check"], True)


class StatusTests(_Base):
    def status(self):
        return semantic_status(home=self.home, manifest=self.manifest)

    def test_status_without_network(self) -> None:
        self.assertEqual(self.status()["status"], "missing")
        self.install(offline_from=self.fixtures, fetch=no_fetch)
        status = self.status()
        self.assertEqual(status["status"], "installed")
        self.assertTrue(all(item["ok"] for item in status["files"]))
        target = model_dir(self.home, self.model) / "model.safetensors"
        target.write_bytes(b"\x00\x01weights\xfe")
        status = self.status()
        self.assertEqual(status["status"], "mismatch")
        self.assertEqual({item["name"]: item["ok"] for item in status["files"]}, {"config.json": True, "model.safetensors": False})


if __name__ == "__main__":
    unittest.main()
