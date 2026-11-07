"""IMP-284: verifiable zero network.

`sentinel/` never imports a network module (AST check in `/doctor`), opens the
browser only on `file://` pages, and the embedding extras run offline only:
`HF_HUB_OFFLINE=1` is set before a model library loads, and without a local
model the probe degrades with a message instead of downloading.
"""

from __future__ import annotations

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
