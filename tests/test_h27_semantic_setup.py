"""IMP-425 (H27 inc 7b): verified install of the pinned semantic model. No network:
the downloader is injected and every fixture hash is computed here."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
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


def no_fetch(url, dest, hosts, max_bytes):
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

        def fetch(url, dest, hosts, max_bytes):
            self.calls.append((url, hosts, max_bytes))
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
        for url, hosts, max_bytes in self.calls:
            self.assertEqual(hosts, ["huggingface.co", ".hf.co"])
            self.assertEqual(max_bytes, next(e["size"] for e in self.model["files"] if url.endswith(e["name"])))
        self.assertEqual(list((self.home / "models").glob(".staging-*")), [])

    def test_mismatch_refuses_and_cleans(self) -> None:
        bad = dict(GOOD, **{"model.safetensors": b"\x00\x01weights\xfe"})
        with self.assertRaises(SetupError) as raised:
            self.install(fetch=self.fake_fetch(bad))
        self.assertIn("model.safetensors: sha256 mismatch", str(raised.exception))
        self.assertFalse(config_path(self.home).exists())
        self.assertFalse(model_dir(self.home, self.model).exists())
        self.assertEqual(list((self.home / "models").glob(".staging-*")), [])

    def test_failed_upgrade_keeps_previous(self) -> None:
        self.install()
        before = config_path(self.home).read_bytes()
        bad = dict(GOOD, **{"model.safetensors": b"\x00\x01weights\xfe"})
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
        (self.fixtures / "config.json").write_bytes(b'{"fixture": nope}')
        with self.assertRaises(SetupError) as raised:
            self.install(offline_from=self.fixtures, fetch=no_fetch)
        self.assertIn("config.json: sha256 mismatch", str(raised.exception))
        self.assertFalse(config_path(self.home).exists())

    def test_package_missing_refuses_before_download(self) -> None:
        with mock.patch("importlib.util.find_spec", return_value=None):
            with self.assertRaises(SetupError) as raised:
                self.install(fetch=no_fetch)
        self.assertIn("pip install", str(raised.exception))
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
            subprocess_fetch("https://huggingface.co/a", dest, ["huggingface.co", ".hf.co"], 99)
        args, kwargs = run.call_args
        script = Path(semantic_setup.__file__).with_name("setup_download.py")
        self.assertEqual(args[0], [sys.executable, "-I", str(script), "https://huggingface.co/a", str(dest), "99", "huggingface.co", ".hf.co"])
        self.assertIs(kwargs["check"], True)
        self.assertNotIn("shell", kwargs)

    def test_fetch_from_a_pyz_extracts_the_downloader_and_cleans_up(self) -> None:
        # IMP-425 final review I1: inside a .pyz __file__ is not a file on disk.
        fake_file = self.tmp / "sentinel.pyz" / "sentinel" / "semantic_setup.py"
        dest = self.tmp / "x.bin"
        seen: dict = {}

        def run(argv, **kwargs):
            script = Path(argv[2])
            seen["argv"] = argv
            seen["exists"] = script.is_file()
            seen["bytes"] = script.read_bytes() if script.is_file() else b""
            seen["dir"] = script.parent
            return mock.Mock(returncode=0)

        real = Path(semantic_setup.__file__).with_name("setup_download.py")
        with mock.patch.object(semantic_setup, "__file__", str(fake_file)), mock.patch("subprocess.run", side_effect=run):
            subprocess_fetch("https://huggingface.co/a", dest, ["huggingface.co"], 5)
        self.assertEqual(seen["argv"][:2], [sys.executable, "-I"])
        self.assertNotIn("sentinel.pyz", seen["argv"][2])
        self.assertEqual(seen["argv"][3:], ["https://huggingface.co/a", str(dest), "5", "huggingface.co"])
        self.assertTrue(seen["exists"])
        self.assertEqual(seen["bytes"], real.read_bytes())
        self.assertFalse(seen["dir"].exists(), "the private temp dir is removed afterwards")

    def test_pyz_extraction_is_cleaned_even_when_the_download_fails(self) -> None:
        fake_file = self.tmp / "sentinel.pyz" / "sentinel" / "semantic_setup.py"
        seen: dict = {}

        def run(argv, **kwargs):
            seen["dir"] = Path(argv[2]).parent
            raise subprocess.CalledProcessError(1, argv)

        with mock.patch.object(semantic_setup, "__file__", str(fake_file)), mock.patch("subprocess.run", side_effect=run):
            with self.assertRaises(subprocess.CalledProcessError):
                subprocess_fetch("https://huggingface.co/a", self.tmp / "y.bin", ["huggingface.co"], 5)
        self.assertFalse(seen["dir"].exists())

    def test_activation_failure_restores_the_previous_install(self) -> None:
        # IMP-425 final review M1: the old model is moved aside and comes back on any failure.
        self.install()
        destination = model_dir(self.home, self.model)
        before = config_path(self.home).read_bytes()
        with mock.patch.object(semantic_setup.core_io, "write_json", side_effect=OSError("disk")):
            with self.assertRaises(OSError):
                self.install()
        self.assertEqual(config_path(self.home).read_bytes(), before)
        for name, data in GOOD.items():
            self.assertEqual((destination / name).read_bytes(), data)
        self.assertEqual([p.name for p in (self.home / "models").iterdir()], ["tiny"])
        self.assertEqual([p.name for p in destination.parent.iterdir()], [destination.name])

    def test_failed_directory_move_keeps_previous_and_cleans_staging(self) -> None:
        self.install()
        destination = model_dir(self.home, self.model)
        real_replace = os.replace

        def replace(src, dst):
            if ".staging-" in str(src):
                raise PermissionError("held by the indexer")
            return real_replace(src, dst)

        with mock.patch.object(semantic_setup.os, "replace", side_effect=replace):
            with self.assertRaises(PermissionError):
                self.install()
        for name, data in GOOD.items():
            self.assertEqual((destination / name).read_bytes(), data)
        self.assertEqual([p.name for p in (self.home / "models").iterdir()], ["tiny"])
        self.assertEqual([p.name for p in destination.parent.iterdir()], [destination.name])

    def test_first_install_failure_leaves_nothing_active(self) -> None:
        with mock.patch.object(semantic_setup.core_io, "write_json", side_effect=OSError("disk")):
            with self.assertRaises(OSError):
                self.install()
        self.assertFalse(config_path(self.home).exists())
        self.assertFalse(model_dir(self.home, self.model).exists())
        self.assertEqual(list((self.home / "models").glob(".staging-*")), [])

    def test_offline_from_checks_size_before_copying(self) -> None:
        (self.fixtures / "model.safetensors").write_bytes(GOOD["model.safetensors"] + b"more")
        copied: list[str] = []
        real_copy = semantic_setup.core_io.copy_file
        with mock.patch.object(semantic_setup.core_io, "copy_file", side_effect=lambda src, dst, **kw: (copied.append(Path(src).name), real_copy(src, dst, **kw))[1]):
            with self.assertRaises(SetupError) as raised:
                self.install(offline_from=self.fixtures, fetch=no_fetch)
        self.assertNotIn("model.safetensors", copied)
        self.assertIn("model.safetensors: size mismatch", str(raised.exception))
        self.assertFalse(config_path(self.home).exists())
        self.assertEqual(list((self.home / "models").glob(".staging-*")), [])

    def test_offline_from_hash_is_checked_before_copying(self) -> None:
        (self.fixtures / "model.safetensors").write_bytes(b"\x00\x01weights\xfe")
        copied: list[str] = []
        real_copy = semantic_setup.core_io.copy_file
        with mock.patch.object(semantic_setup.core_io, "copy_file", side_effect=lambda src, dst, **kw: (copied.append(Path(src).name), real_copy(src, dst, **kw))[1]):
            with self.assertRaises(SetupError) as raised:
                self.install(offline_from=self.fixtures, fetch=no_fetch)
        self.assertNotIn("model.safetensors", copied)
        self.assertIn("model.safetensors: sha256 mismatch", str(raised.exception))

    def test_hashing_is_streamed(self) -> None:
        big = self.tmp / "big.bin"
        payload = b"a" * (3 * 1024 * 1024 + 5)
        big.write_bytes(payload)
        with mock.patch.object(Path, "read_bytes", side_effect=AssertionError("whole file in memory")):
            digest = semantic_setup._sha256(big)
        self.assertEqual(digest, hashlib.sha256(payload).hexdigest())

    def test_manifest_names_are_validated(self) -> None:
        for bad in ("../evil", "a/b", "a\\b", "/abs", "C:\\x", "..", ".hidden", "x..y", ""):
            manifest = _manifest()
            manifest["models"][0]["files"][0]["name"] = bad
            with self.subTest(name=bad):
                with self.assertRaises(SetupError):
                    install_semantic_memory(home=self.home, manifest=manifest, fetch=no_fetch, root=self.tmp / "noroot")
                with self.assertRaises(SetupError):
                    semantic_status(home=self.home, manifest=manifest)
        for key, bad in (("id", "../x"), ("id", "a/b"), ("revision", "../" + "a" * 37), ("revision", "g" * 40)):
            manifest = _manifest()
            manifest["models"][0][key] = bad
            if key == "id":
                manifest["default"] = bad
            with self.subTest(key=key, value=bad):
                with self.assertRaises(SetupError):
                    install_semantic_memory(home=self.home, manifest=manifest, fetch=no_fetch, root=self.tmp / "noroot")
        self.assertFalse(self.home.exists())

    def test_pip_hint_follows_the_install_kind(self) -> None:
        clone = self.tmp / "clone"
        (clone / "sentinel").mkdir(parents=True)
        (clone / "sentinel" / "__init__.py").write_text("", encoding="utf-8")
        project = self.tmp / "project"
        project.mkdir()
        with mock.patch("importlib.util.find_spec", return_value=None):
            with self.assertRaises(SetupError) as in_clone:
                install_semantic_memory(home=self.home, manifest=self.manifest, fetch=no_fetch, root=clone)
            with self.assertRaises(SetupError) as outside:
                install_semantic_memory(home=self.home, manifest=self.manifest, fetch=no_fetch, root=project)
        self.assertIn("constraints/memory-semantic.txt -e .[memory-semantic]", str(in_clone.exception))
        self.assertNotIn("-e .", str(outside.exception))
        self.assertIn("model2vec sentence-transformers", str(outside.exception))
        self.assertIn(sys.executable, str(outside.exception))
        # M-5: the next step is the same command as the hint, and it does not lean on a path of the clone
        self.assertEqual(in_clone.exception.next_step, "python -m pip install -c constraints/memory-semantic.txt -e .[memory-semantic]")
        self.assertIn(outside.exception.next_step, str(outside.exception))
        self.assertNotIn("constraints/", outside.exception.next_step)

    def test_config_records_the_pinned_revision(self) -> None:
        self.install()
        config = json.loads(config_path(self.home).read_text(encoding="utf-8"))
        self.assertEqual(config["revision"], "a" * 40)
        self.assertEqual(config["model_id"], "tiny")

    def test_busy_workspace_is_skipped_with_a_warning(self) -> None:
        # IMP-425 final review I3: /setup takes the IMP-299 lock around each reindex.
        import threading

        from sentinel.core.lock import command_scope

        root = self.tmp / "repo"
        for name in ("ALFA", "BETA"):
            (root / "workspaces" / name).mkdir(parents=True)
            (root / "workspaces" / name / "state.json").write_text("{}", encoding="utf-8")
        held, release = threading.Event(), threading.Event()

        def hold() -> None:
            with command_scope("ingest", root / "workspaces" / "ALFA"):
                held.set()
                release.wait(20)

        thread = threading.Thread(target=hold)
        thread.start()
        self.addCleanup(thread.join, 20)
        self.addCleanup(release.set)
        self.assertTrue(held.wait(10))
        with mock.patch.dict(os.environ, {"SENTINEL_LOCK_TIMEOUT": "0"}), \
                mock.patch("sentinel.memory.reindex_workspace") as reindex:
            result = install_semantic_memory(home=self.home, manifest=self.manifest, fetch=self.fake_fetch(), root=root)
        self.assertEqual([call.args for call in reindex.call_args_list], [("BETA",)])
        self.assertEqual(result["reindexed"], ["BETA"])
        self.assertEqual(len(result["warnings"]), 1)
        self.assertIn("ALFA", result["warnings"][0])
        self.assertIn("sentinel /reindex ALFA --full", result["warnings"][0])

    def test_reindex_runs_while_holding_the_workspace_lock(self) -> None:
        from sentinel.core.lock import holds_lock

        root = self.tmp / "repo"
        (root / "workspaces" / "ALFA").mkdir(parents=True)
        (root / "workspaces" / "ALFA" / "state.json").write_text("{}", encoding="utf-8")
        held: list[bool] = []
        with mock.patch("sentinel.memory.reindex_workspace", side_effect=lambda *a, **k: held.append(holds_lock())):
            install_semantic_memory(home=self.home, manifest=self.manifest, fetch=self.fake_fetch(), root=root)
        self.assertEqual(held, [True])


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
