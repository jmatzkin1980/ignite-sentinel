"""IMP-425 (H27 inc 7b, task 3): the memory reads the verified config after env vars."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from sentinel import doctor, memory, semantic_setup


class SemanticConfigProbeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name) / "home"
        self.home.mkdir()
        env = {"SENTINEL_HOME": str(self.home)}
        patcher = mock.patch.dict(os.environ, env)
        patcher.start()
        self.addCleanup(patcher.stop)
        os.environ.pop("SENTINEL_MODEL2VEC_MODEL", None)
        os.environ.pop("SENTINEL_SENTENCE_TRANSFORMERS_MODEL", None)
        self.refs: list[str] = []
        self.st_refs: list[str] = []
        manifest = semantic_setup.load_manifest()
        self.pinned = semantic_setup._model(manifest)
        self.model = semantic_setup.model_dir(self.home, self.pinned)
        self.model.mkdir(parents=True)

        def fake(ref: str):
            self.refs.append(ref)
            return None, {"level": "model2vec", "outcome": "model-not-local", "detail": ""}

        p2 = mock.patch.object(memory, "_probe_model2vec", fake)
        p2.start()
        self.addCleanup(p2.stop)
        def fake_st(ref: str):
            self.st_refs.append(ref)
            return None, {"level": "st", "outcome": "skipped", "detail": ""}

        p3 = mock.patch.object(memory, "_probe_sentence_transformers", fake_st)
        p3.start()
        self.addCleanup(p3.stop)

    def _config(self, path: Path, **override) -> None:
        data = {"model_id": self.pinned["id"], "revision": self.pinned["revision"], "path": str(path)}
        data.update(override)
        (self.home / "semantic.json").write_text(json.dumps(data), encoding="utf-8")

    def test_config_feeds_probe(self) -> None:
        self._config(self.model)
        memory._probe_embedder()
        self.assertEqual(self.refs, [str(self.model)])

    def test_env_var_wins_over_config(self) -> None:
        self._config(self.model)
        with mock.patch.dict(os.environ, {"SENTINEL_MODEL2VEC_MODEL": "/otro"}):
            memory._probe_embedder()
        self.assertEqual(self.refs, ["/otro"])

    def test_sentence_transformers_env_var_wins_over_config(self) -> None:
        # IMP-425 final review I2: both variables override the installed model.
        self._config(self.model)
        with mock.patch.dict(os.environ, {"SENTINEL_SENTENCE_TRANSFORMERS_MODEL": "/approved-st"}):
            memory._probe_embedder()
        self.assertEqual(self.refs, [memory.DEFAULT_MODEL2VEC_MODEL])
        self.assertEqual(self.st_refs, ["/approved-st"])

    def test_config_for_another_revision_is_ignored(self) -> None:
        # IMP-425 final review M7: the config is tied to the manifest's pinned revision.
        for path, override in ((self.model, {"revision": "b" * 40}), (self.model, {"model_id": "other"}), (self.model.parent, {})):
            self.refs.clear()
            self._config(path, **override)
            memory._probe_embedder()
            self.assertEqual(self.refs, [memory.DEFAULT_MODEL2VEC_MODEL], override)

    def test_config_without_revision_is_ignored(self) -> None:
        (self.home / "semantic.json").write_text(json.dumps({"path": str(self.model)}), encoding="utf-8")
        memory._probe_embedder()
        self.assertEqual(self.refs, [memory.DEFAULT_MODEL2VEC_MODEL])

    def test_stale_config_makes_doctor_warn(self) -> None:
        self._config(self.model, revision="b" * 40)
        active = {"name": "m", "level": "model2vec", "version": "1", "dimensions": 8, "detail": "", "semantic": True}
        with mock.patch.object(doctor, "active_embedder_status", return_value=active):
            check = doctor.semantic_embedder_check()
        self.assertEqual(check["status"], "WARN")
        self.assertIn("/setup --semantic-memory", check["detail"])
        self.assertIn("semantic.json", check["detail"])

    def test_current_config_keeps_doctor_pass(self) -> None:
        self._config(self.model)
        active = {"name": "m", "level": "model2vec", "version": "1", "dimensions": 8, "detail": "", "semantic": True}
        with mock.patch.object(doctor, "active_embedder_status", return_value=active):
            self.assertEqual(doctor.semantic_embedder_check()["status"], "PASS")

    def test_no_config_keeps_default(self) -> None:
        memory._probe_embedder()
        self.model.rmdir()
        self._config(self.model)
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
