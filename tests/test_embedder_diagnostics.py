"""IMP-121 — local semantic embedder detection/diagnosis hardening.

These tests assert two invariants:

* With no local semantic model present, behavior is identical to the current
  deterministic hash fallback (no error, no network) and the diagnosis explains why.
* When a local model is available, detection picks it up and reports semantic active.

The "model present" branch is exercised by injecting a fake ``model2vec`` module so the
suite stays green and offline regardless of what is installed in the environment.
"""

from __future__ import annotations

import os
import sys
import unittest
from unittest import mock

import sentinel.memory as memory


class EmbedderFallbackTests(unittest.TestCase):
    def test_fallback_is_hash_and_behavior_unchanged(self) -> None:
        status = memory.active_embedder_status()
        if status["semantic"]:
            self.skipTest("a real local semantic model is installed; fallback identity is a hash-mode property")
        embedder = memory.detect_embedder()
        self.assertIsInstance(embedder, memory.HashEmbedder)
        self.assertEqual(status["level"], "hash")
        self.assertFalse(status["semantic"])
        # Identical to the deterministic hash embedding: detection added no behavior change.
        text = "metric source and target users of the dashboard"
        self.assertEqual(embedder.embed(text), memory.hash_embedding(text))
        self.assertEqual(len(embedder.embed(text)), memory.VECTOR_DIMENSIONS)

    def test_diagnostics_report_candidates_and_recommendation(self) -> None:
        diag = memory.embedder_diagnostics()
        self.assertIn("active", diag)
        self.assertIn("semantic", diag)
        self.assertIn("candidates", diag)
        self.assertIn("recommendation", diag)
        self.assertTrue(diag["candidates"], "expected at least one probed candidate")
        for candidate in diag["candidates"]:
            self.assertIn("level", candidate)
            self.assertIn("outcome", candidate)
            self.assertIn("detail", candidate)
            self.assertIn("model_ref", candidate)
        if not diag["semantic"]:
            self.assertTrue(diag["recommendation"], "fallback mode must offer an actionable recommendation")

    def test_remote_refs_are_refused_without_network(self) -> None:
        with mock.patch.dict(
            os.environ,
            {
                "SENTINEL_MODEL2VEC_MODEL": "https://example.com/model.bin",
                "SENTINEL_SENTENCE_TRANSFORMERS_MODEL": "http://example.com/st",
            },
        ):
            embedder = memory.detect_embedder()
            diag = memory.embedder_diagnostics()
        self.assertIsInstance(embedder, memory.HashEmbedder)
        outcomes = {candidate["outcome"] for candidate in diag["candidates"]}
        self.assertEqual(outcomes, {"skipped"})
        for candidate in diag["candidates"]:
            self.assertIn("local-first", candidate["detail"])

    def test_looks_local_model_ref(self) -> None:
        self.assertFalse(memory._looks_local_model_ref("https://huggingface.co/x"))
        self.assertFalse(memory._looks_local_model_ref("http://x/y"))
        self.assertTrue(memory._looks_local_model_ref("minishlab/potion-multilingual-128M"))
        self.assertTrue(memory._looks_local_model_ref(str(memory.Path(__file__).parent)))


class FakeStaticModel:
    """Minimal stand-in for model2vec.StaticModel that loads only with local_files_only."""

    def __init__(self) -> None:
        self.calls = 0

    @classmethod
    def from_pretrained(cls, model_ref: str, local_files_only: bool = False):  # noqa: FBT002
        if not local_files_only:
            raise AssertionError("Sentinel must enforce local_files_only (no download)")
        return cls()

    def encode(self, texts: list[str]):
        # Deterministic 3-dim "semantic" vector keyed on coarse meaning buckets.
        out = []
        for text in texts:
            lowered = text.lower()
            out.append(
                [
                    1.0 if any(t in lowered for t in ("metric", "metrica", "target", "objetivo")) else 0.0,
                    1.0 if any(t in lowered for t in ("user", "usuario", "lead")) else 0.0,
                    1.0 if any(t in lowered for t in ("dashboard", "tablero")) else 0.0,
                ]
            )
        return out


class InjectedSemanticModelTests(unittest.TestCase):
    def test_injected_model2vec_is_detected_as_semantic(self) -> None:
        fake_module = mock.Mock()
        fake_module.StaticModel = FakeStaticModel
        with mock.patch.dict(sys.modules, {"model2vec": fake_module}):
            embedder = memory.detect_embedder()
            diag = memory.embedder_diagnostics()
        self.assertIsInstance(embedder, memory.Model2VecEmbedder)
        self.assertTrue(embedder.status.semantic)
        self.assertEqual(embedder.status.level, "model2vec")
        self.assertEqual(embedder.status.dimensions, 3)
        self.assertTrue(diag["semantic"])
        self.assertEqual(diag["recommendation"], "")
        active = next(c for c in diag["candidates"] if c["level"] == "model2vec")
        self.assertEqual(active["outcome"], "active")


if __name__ == "__main__":
    unittest.main()
