"""IMP-295: retrieval recency must not depend on wall-clock seconds.

`indexed_at` has one-second resolution, so two artifacts indexed in the same second tie and two
indexed across a second boundary do not. The recency re-score then picked a different top result
between identical runs (the backlog Product evidence flipped between `REQ-002` and `PRD-001`).
Recency now follows the order of indexing (`index_seq`), which is the same on every run.
"""

import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sentinel.memory import ContextBroker, apply_recency_coverage_rescore


def _rows(second_of_b: str) -> list[dict]:
    base = {"iteration": 1, "domain": "product", "why_retrieved": "lexical"}
    return [
        {**base, "chunk_id": "PRD-001::chunk-001", "score": 1.0, "index_seq": 2, "indexed_at": f"2026-11-11T10:00:{second_of_b}+00:00"},
        {**base, "chunk_id": "REQ-002::chunk-001", "score": 1.02, "index_seq": 1, "indexed_at": "2026-11-11T10:00:00+00:00"},
    ]


class RecencyDeterminismTest(unittest.TestCase):
    def test_ranking_ignores_the_wall_clock_second(self):
        same_second = [r["chunk_id"] for r in apply_recency_coverage_rescore(_rows("00"), {"scope"})]
        next_second = [r["chunk_id"] for r in apply_recency_coverage_rescore(_rows("01"), {"scope"})]
        self.assertEqual(same_second, next_second)

    def test_index_seq_follows_indexing_order_and_survives_reload(self):
        tmp = Path(tempfile.mkdtemp())
        old_cwd = Path.cwd()
        os.chdir(tmp)  # workspaces/ resolves against the cwd
        try:
            with patch.object(ContextBroker, "_connect_lancedb", lambda self: None):
                source = tmp / "a.md"
                source.write_text("# A\nalpha", encoding="utf-8")
                broker = ContextBroker("SEQ")
                broker.index_artifact("A-1", "requirement", source, source.read_text(encoding="utf-8"))
                broker.index_artifact("B-1", "prd", source, "# B\nbeta")
                again = ContextBroker("SEQ")
                again.index_artifact("C-1", "spec", source, "# C\ngamma")
                seqs = {c["artifact_id"]: c["index_seq"] for c in again.data["chunks"]}
        finally:
            os.chdir(old_cwd)
            shutil.rmtree(tmp, ignore_errors=True)
        self.assertEqual(seqs, {"A-1": 1, "B-1": 2, "C-1": 3})


if __name__ == "__main__":
    unittest.main()
