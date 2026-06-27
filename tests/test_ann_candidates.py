"""IMP-124 — LanceDB as ANN candidate generator, JSON as fallback.

When a LanceDB table is active, the candidate set is produced by vector + FTS
(ANN) so the VDB contributes recall and scale instead of only re-ranking a full
JSON scan. The JSON store stays the source of truth for verbatim content and
metadata, and the unconditional full-scan remains the fallback whenever LanceDB
is absent, returns nothing, or yields stale ids — so no SSoT chunk is ever
unreachable and json-hybrid behaves identically to before.
"""

from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from pathlib import Path

from sentinel.cli import main
from sentinel.memory import ContextBroker


class CandidateGenerationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.old_cwd = Path.cwd()
        self.temp = Path(tempfile.mkdtemp())
        os.chdir(self.temp)
        self.assertEqual(main(["init", "ANN"]), 0)
        self.broker = ContextBroker("ANN")
        self._index("A", "alpha unique widget metric for the dashboard")
        self._index("B", "beta distinct gadget pipeline for the service")
        self._index("C", "gamma separate module workflow for the backlog")

    def tearDown(self) -> None:
        os.chdir(self.old_cwd)
        shutil.rmtree(self.temp, ignore_errors=True)

    def _index(self, artifact_id: str, text: str) -> None:
        self.broker.index_artifact(
            artifact_id=artifact_id,
            artifact_type="requirements",
            source_path=Path(f"{artifact_id}.md"),
            text=text,
            domain="product",
        )

    def test_json_fullscan_reaches_all_chunks_without_lancedb(self) -> None:
        # Default test env has no LanceDB table: the full scan must reach every
        # SSoT chunk and the path is reported as json-fullscan.
        self.assertIsNone(self.broker._table)
        for token, expected in (("widget", "A"), ("gadget", "B"), ("module", "C")):
            results = self.broker.retrieve(token, "specs")
            self.assertTrue(results, token)
            self.assertEqual(results[0]["artifact_id"], expected)
            self.assertEqual(self.broker.last_candidate_source, "json-fullscan")

    def test_lancedb_active_restricts_candidates_to_ann(self) -> None:
        # With an active table whose ANN/FTS candidates are only B, a strong
        # lexical match on A must NOT surface — candidates come from the VDB.
        self.broker._table = object()
        self.broker._lancedb_candidates = lambda *a, **k: {"B::chunk-001": {"score": 0.5, "vector_rank": 1}}
        results = self.broker.retrieve("alpha unique widget", "specs")
        self.assertTrue(results)
        self.assertTrue(all(row["artifact_id"] == "B" for row in results))
        self.assertEqual(self.broker.last_candidate_source, "lancedb-ann")

    def test_empty_lancedb_candidates_fall_back_to_fullscan(self) -> None:
        # Active table but empty candidate set (empty table / mid-query
        # degradation): fall back to the full scan so A is still reachable.
        self.broker._table = object()
        self.broker._lancedb_candidates = lambda *a, **k: {}
        results = self.broker.retrieve("alpha unique widget", "specs")
        self.assertTrue(any(row["artifact_id"] == "A" for row in results))
        self.assertEqual(self.broker.last_candidate_source, "json-fullscan")

    def test_stale_lancedb_ids_fall_back_to_fullscan(self) -> None:
        # ANN returns ids that no longer resolve to a JSON chunk (stale rows):
        # rather than returning nothing, fall back to the full scan.
        self.broker._table = object()
        self.broker._lancedb_candidates = lambda *a, **k: {"GHOST::chunk-001": {"score": 1.0}}
        results = self.broker.retrieve("alpha unique widget", "specs")
        self.assertTrue(any(row["artifact_id"] == "A" for row in results))
        self.assertEqual(self.broker.last_candidate_source, "json-fullscan")

    def test_context_pack_exposes_candidate_source(self) -> None:
        pack = self.broker.build_context_pack("widget", "specs")
        self.assertEqual(pack["candidate_source"], "json-fullscan")
        self.assertEqual(pack["backend"], "json-hybrid")


if __name__ == "__main__":
    unittest.main()
