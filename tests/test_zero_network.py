"""IMP-284: verifiable zero network.

`sentinel/` never imports a network module (AST check in `/doctor`), opens the
browser only on `file://` pages, and the embedding extras run offline only:
`HF_HUB_OFFLINE=1` is set before a model library loads, and without a local
model the probe degrades with a message instead of downloading.
"""

from __future__ import annotations

import ast
import importlib.util
import os
import socket
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

from sentinel import memory
from sentinel.core.local_browser import open_local_file
from sentinel.doctor import network_import_violations, network_isolation_check

PACKAGE_DIR = Path(__file__).resolve().parents[1] / "sentinel"


def _package(tmp: str, source: str, name: str = "seeded.py") -> Path:
    root = Path(tmp) / "sentinel"
    root.mkdir()
    (root / name).write_text(source, encoding="utf-8")
    return root


class NetworkImportTests(unittest.TestCase):
    def test_the_package_imports_no_network_module(self) -> None:
        self.assertEqual(network_import_violations(PACKAGE_DIR), [])
        self.assertEqual(network_isolation_check()["status"], "PASS")

    def test_a_seeded_import_fails(self) -> None:
        seeds = [
            "import socket\n",
            "import urllib.request\n",
            "from http import client\n",
            "from http.server import HTTPServer\n",
            "import ftplib\n",
            "import smtplib\n",
            "import ssl\n",
            "import requests\n",
            "def f():\n    import httpx\n",
            "import importlib\nimportlib.import_module('socket')\n",
            "__import__('urllib.request')\n",
        ]
        for source in seeds:
            with self.subTest(source=source), tempfile.TemporaryDirectory() as tmp:
                violations = network_import_violations(_package(tmp, source))
                self.assertEqual(len(violations), 1, violations)
                self.assertIn("seeded.py:", violations[0])
                with mock.patch("sentinel.doctor._package_dir", return_value=Path(tmp) / "sentinel"):
                    self.assertEqual(network_isolation_check()["status"], "FAIL")

    def test_relative_and_lookalike_imports_pass(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(network_import_violations(_package(tmp, "from .http import x\nimport sslib\nimport httpie_docs\n")), [])

    def test_webbrowser_is_confined_to_the_local_opener(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            violations = network_import_violations(_package(tmp, "import webbrowser\n"))
        self.assertTrue(any("webbrowser" in item for item in violations), violations)

    def test_packaged_build_without_sources_is_not_a_failure(self) -> None:
        with mock.patch("sentinel.doctor._package_dir", return_value=Path("sentinel.pyz") / "sentinel"):
            self.assertEqual(network_isolation_check()["status"], "WARN")


DOWNLOADER = PACKAGE_DIR / "setup_download.py"


def _load_downloader():
    spec = importlib.util.spec_from_file_location("setup_download_under_test", DOWNLOADER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SetupDownloaderFenceTests(unittest.TestCase):
    """IMP-425: the one declared exception to zero network lives in one file."""

    def test_only_the_setup_downloader_may_import_network(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(network_import_violations(_package(tmp, "import urllib.request\n", name="setup_download.py")), [])
        with tempfile.TemporaryDirectory() as tmp:
            violations = network_import_violations(_package(tmp, "import urllib.request\n", name="other.py"))
            self.assertEqual(len(violations), 1, violations)
        self.assertEqual(network_import_violations(PACKAGE_DIR), [])

    def test_no_module_imports_the_downloader(self) -> None:
        offenders = []
        for path in sorted(PACKAGE_DIR.rglob("*.py")):
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8-sig"))):
                names: list[str] = []
                if isinstance(node, ast.Import):
                    names = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom):
                    names = [node.module or ""] + [alias.name for alias in node.names]
                if any(name.endswith("setup_download") for name in names):
                    offenders.append(f"{path.name}:{node.lineno}")
        self.assertEqual(offenders, [])

    def test_downloader_refuses_foreign_hosts(self) -> None:
        module = _load_downloader()
        hosts = ["huggingface.co", ".hf.co"]
        self.assertTrue(module.host_allowed("https://huggingface.co/a", ["huggingface.co"]))
        self.assertTrue(module.host_allowed("https://us.aws.cdn.hf.co/a", hosts))
        for url in (
            "https://evil.example/a",
            "http://huggingface.co/a",
            "https://huggingface.co.evil.example/a",
            "https://hf.co/a",
            "https://evilhf.co/a",
            "https://huggingface.co@evil.example/a",
        ):
            with self.subTest(url=url):
                self.assertFalse(module.host_allowed(url, hosts))
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(module, "_open") as opened:
            dest = Path(tmp) / "x.bin"
            with mock.patch("sys.stderr"):
                self.assertEqual(module.main(["https://evil.example/a", str(dest), "10", "huggingface.co"]), 2)
            opened.assert_not_called()
            self.assertFalse(dest.exists())

    def test_downloader_streams_to_part_then_renames(self) -> None:
        import io

        module = _load_downloader()
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(module, "_open", return_value=io.BytesIO(b"abc")):
            dest = Path(tmp) / "x.bin"
            self.assertEqual(module.main(["https://huggingface.co/a", str(dest), "3", "huggingface.co"]), 0)
            self.assertEqual(dest.read_bytes(), b"abc")
            self.assertFalse(Path(str(dest) + ".part").exists())

    def test_downloader_stops_past_the_declared_size(self) -> None:
        import io

        module = _load_downloader()
        module.CHUNK = 4
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(module, "_open", return_value=io.BytesIO(b"x" * 100)):
            dest = Path(tmp) / "x.bin"
            with mock.patch("sys.stderr"):
                self.assertEqual(module.main(["https://huggingface.co/a", str(dest), "10", "huggingface.co"]), 1)
            self.assertFalse(dest.exists())
            self.assertFalse(Path(str(dest) + ".part").exists())

    def test_downloader_refuses_a_bigger_content_length_up_front(self) -> None:
        import io

        module = _load_downloader()
        response = io.BytesIO(b"abc")
        response.headers = {"Content-Length": "999"}
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(module, "_open", return_value=response):
            dest = Path(tmp) / "x.bin"
            with mock.patch("sys.stderr"):
                self.assertEqual(module.main(["https://huggingface.co/a", str(dest), "10", "huggingface.co"]), 1)
            self.assertFalse(dest.exists())

    def test_downloader_needs_a_numeric_size(self) -> None:
        module = _load_downloader()
        with mock.patch.object(module, "_open") as opened, mock.patch("sys.stderr"):
            self.assertEqual(module.main(["https://huggingface.co/a", "x", "huggingface.co", "huggingface.co"]), 2)
        opened.assert_not_called()

    def test_downloader_imports_only_stdlib(self) -> None:
        tops = set()
        for node in ast.walk(ast.parse(DOWNLOADER.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                tops.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                tops.add(node.module.split(".")[0])
        self.assertTrue(tops)
        self.assertLessEqual(tops, set(sys.stdlib_module_names))
        self.assertNotIn("sentinel", tops)


class LocalBrowserTests(unittest.TestCase):
    def test_opens_only_file_uris(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, mock.patch("webbrowser.open") as opened:
            page = Path(tmp) / "view.html"
            page.write_text("<html></html>", encoding="utf-8")
            open_local_file(page)
        opened.assert_called_once()
        self.assertTrue(opened.call_args.args[0].startswith("file://"))

    def test_refuses_remote_and_missing_targets(self) -> None:
        with mock.patch("webbrowser.open") as opened:
            for target in ("https://example.com", "http://localhost:8000", Path("does-not-exist.html")):
                with self.subTest(target=target), self.assertRaises(ValueError):
                    open_local_file(target)
        opened.assert_not_called()


class OfflineEmbeddingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.env = mock.patch.dict(os.environ, {}, clear=False)
        self.env.start()
        self.addCleanup(self.env.stop)
        for key in ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE", "HF_DATASETS_OFFLINE"):
            os.environ.pop(key, None)

    def test_offline_flags_are_set_before_the_model_library_loads(self) -> None:
        seen: dict[str, str | None] = {}

        class StaticModel:
            @staticmethod
            def from_pretrained(ref: str, local_files_only: bool = False):
                seen["offline"] = os.environ.get("HF_HUB_OFFLINE")
                seen["local_only"] = str(local_files_only)
                raise OSError("not in the local cache")

        fake = types.ModuleType("model2vec")
        fake.StaticModel = StaticModel
        with mock.patch.dict(sys.modules, {"model2vec": fake}):
            embedder, diag = memory._probe_model2vec("org/model")
        self.assertIsNone(embedder)
        self.assertEqual(seen, {"offline": "1", "local_only": "True"})
        self.assertEqual(diag["outcome"], "model-unavailable")
        self.assertIn("no download", diag["detail"])
        self.assertEqual(os.environ.get("TRANSFORMERS_OFFLINE"), "1")

    def test_no_local_model_means_no_traffic(self) -> None:
        attempts: list[object] = []

        def refuse(*args: object, **kwargs: object) -> None:
            attempts.append(args)
            raise OSError("network disabled in test")

        with mock.patch.dict(os.environ, {
            "SENTINEL_MODEL2VEC_MODEL": "missing/model-ref",
            "SENTINEL_SENTENCE_TRANSFORMERS_MODEL": "missing/other-ref",
        }), mock.patch.object(socket.socket, "connect", refuse), mock.patch.object(socket, "create_connection", refuse):
            embedder, diagnostics = memory._probe_embedder()
        self.assertEqual(attempts, [])
        self.assertIsInstance(embedder, memory.HashEmbedder)
        self.assertTrue(all(item["outcome"] != "active" for item in diagnostics))


if __name__ == "__main__":
    unittest.main()
