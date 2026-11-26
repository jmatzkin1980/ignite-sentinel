"""IMP-425 (H27 inc 7b, task 3): the memory reads the verified config after env vars."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from sentinel import doctor, memory


class SemanticConfigProbeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name) / "home"
        self.home.mkdir()
        self.model = Path(self.tmp.name) / "model"
        self.model.mkdir()
        env = {"SENTINEL_HOME": str(self.home)}
        patcher = mock.patch.dict(os.environ, env)
        patcher.start()
        self.addCleanup(patcher.stop)
        os.environ.pop("SENTINEL_MODEL2VEC_MODEL", None)
        self.refs: list[str] = []

        def fake(ref: str):
            self.refs.append(ref)
            return None, {"level": "model2vec", "outcome": "model-not-local", "detail": ""}

        p2 = mock.patch.object(memory, "_probe_model2vec", fake)
        p2.start()
        self.addCleanup(p2.stop)
        p3 = mock.patch.object(memory, "_probe_sentence_transformers", lambda ref: (None, {"level": "st", "outcome": "skipped", "detail": ""}))
        p3.start()
        self.addCleanup(p3.stop)

    def _config(self, path: Path) -> None:
        (self.home / "semantic.json").write_text(json.dumps({"path": str(path)}), encoding="utf-8")

    def test_config_feeds_probe(self) -> None:
        self._config(self.model)
        memory._probe_embedder()
        self.assertEqual(self.refs, [str(self.model)])

    def test_env_var_wins_over_config(self) -> None:
        self._config(self.model)
        with mock.patch.dict(os.environ, {"SENTINEL_MODEL2VEC_MODEL": "/otro"}):
            memory._probe_embedder()
        self.assertEqual(self.refs, ["/otro"])

    def test_no_config_keeps_default(self) -> None:
        memory._probe_embedder()
        self._config(Path(self.tmp.name) / "gone")
        memory._probe_embedder()
        self.assertEqual(self.refs, [memory.DEFAULT_MODEL2VEC_MODEL] * 2)

    def test_corrupt_config_keeps_default(self) -> None:
        (self.home / "semantic.json").write_text("{nope", encoding="utf-8")
        memory._probe_embedder()
        self.assertEqual(self.refs, [memory.DEFAULT_MODEL2VEC_MODEL])


class DoctorNamesSetupTests(unittest.TestCase):
    ABSENT = {"name": "hash", "level": "hash", "version": "1", "dimensions": 8, "detail": "", "semantic": False}

    def test_absent_stays_warn_and_names_setup(self) -> None:
        diag = {"candidates": [{"level": "model2vec", "outcome": "package-missing"}],
                "recommendation": memory._embedder_recommendation([{"outcome": "package-missing"}])}
        with mock.patch.object(doctor, "active_embedder_status", return_value=self.ABSENT), \
                mock.patch.object(doctor, "embedder_diagnostics", return_value=diag):
            check = doctor.semantic_embedder_check()
        self.assertEqual(check["status"], "WARN")
        self.assertIn("/setup --semantic-memory", check["detail"])
        self.assertIn("--offline-from", check["detail"])

    def test_fallback_text_names_setup(self) -> None:
        with mock.patch.object(doctor, "active_embedder_status", return_value=self.ABSENT), \
                mock.patch.object(doctor, "embedder_diagnostics", side_effect=RuntimeError("x")):
            check = doctor.semantic_embedder_check()
        self.assertEqual(check["status"], "WARN")
        self.assertIn("/setup --semantic-memory", check["detail"])

    def test_recommendation_names_setup(self) -> None:
        for outcome in ("model-not-local", "model-unavailable"):
            text = memory._embedder_recommendation([{"outcome": outcome}])
            self.assertIn("/setup --semantic-memory", text)
            self.assertIn("--offline-from", text)
            self.assertNotIn("never downloads", text)


if __name__ == "__main__":
    unittest.main()
