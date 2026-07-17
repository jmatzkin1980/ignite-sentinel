"""IMP-123 — Governed recency + coverage re-scoring.

A deterministic, network-free second stage runs over the merged retrieval
shortlist: fresh context (higher iteration, then later ``indexed_at``) and
on-domain context outrank stale context with equivalent vocabulary, without any
neural reranker. The bonus is bounded so it breaks near-ties but never overrides a
strong relevance gap, and it never mutates the verbatim chunk text or read_plan.
"""

from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from pathlib import Path

from sentinel.cli import main
from sentinel.memory import (
    COVERAGE_WEIGHT,
    RECENCY_WEIGHT,
    ContextBroker,
    apply_recency_coverage_rescore,
    domain_coverage,
    tokenize,
)


def _row(chunk_id: str, score: float, *, iteration: int = 1, indexed_at: str = "", domain: str = "product") -> dict:
    return {
        "chunk_id": chunk_id,
        "score": score,
        "iteration": iteration,
        "indexed_at": indexed_at,
        "domain": domain,
        "why_retrieved": "lexical match",
    }


class RescoreUnitTests(unittest.TestCase):
    def test_fresher_iteration_wins_a_lexical_tie(self) -> None:
        rows = [_row("old", 1.0, iteration=1), _row("new", 1.0, iteration=3)]
        ordered = apply_recency_coverage_rescore(rows, set())
        self.assertEqual([r["chunk_id"] for r in ordered], ["new", "old"])
        self.assertGreater(ordered[0]["score"], ordered[1]["score"])
        # Base score is preserved alongside the re-scored value for transparency.
        self.assertEqual(ordered[0]["base_score"], 1.0)
        self.assertEqual(ordered[1]["recency_score"], 0.0)
        self.assertAlmostEqual(ordered[0]["recency_score"], 1.0)

    def test_indexed_at_breaks_ties_within_same_iteration(self) -> None:
        rows = [
            _row("earlier", 1.0, iteration=2, indexed_at="2026-06-01T00:00:00+00:00"),
            _row("later", 1.0, iteration=2, indexed_at="2026-06-27T00:00:00+00:00"),
        ]
        ordered = apply_recency_coverage_rescore(rows, set())
        self.assertEqual([r["chunk_id"] for r in ordered], ["later", "earlier"])

    def test_recency_weight_zero_drops_recency_from_bonus_and_tiebreak(self) -> None:
        # Same base score, different indexed_at: with recency disabled the ordering
        # must not depend on indexed_at (wall-clock) at all, only on the
        # deterministic chunk_id tie-break. This is the guarantee the backlog
        # execution-contract retrieval relies on to be reproducible.
        rows = [
            _row("z-later", 1.0, iteration=2, indexed_at="2026-06-27T00:00:00+00:00"),
            _row("a-earlier", 1.0, iteration=2, indexed_at="2026-06-01T00:00:00+00:00"),
        ]
        ordered = apply_recency_coverage_rescore(rows, set(), recency_weight=0.0)
        self.assertEqual([r["score"] for r in ordered], [1.0, 1.0])
        self.assertEqual([r["recency_score"] for r in ordered], [0.0, 0.0])
        self.assertEqual([r["chunk_id"] for r in ordered], ["z-later", "a-earlier"])

    def test_recency_weight_zero_is_indexed_at_order_invariant(self) -> None:
        # Swapping the indexed_at values between two equally-scored rows must not
        # change their order when recency is disabled — proving wall-clock has no
        # influence on the result.
        def order(ts_z: str, ts_a: str) -> list[str]:
            rows = [
                _row("z", 1.0, iteration=1, indexed_at=ts_z),
                _row("a", 1.0, iteration=1, indexed_at=ts_a),
            ]
            return [r["chunk_id"] for r in apply_recency_coverage_rescore(rows, set(), recency_weight=0.0)]

        early, late = "2026-01-01T00:00:00+00:00", "2026-12-31T00:00:00+00:00"
        self.assertEqual(order(early, late), order(late, early))

    def test_single_recency_adds_no_differentiation(self) -> None:
        rows = [_row("a", 0.9, iteration=1), _row("b", 0.8, iteration=1)]
        ordered = apply_recency_coverage_rescore(rows, set())
        # No distinct recency span -> bonus is zero, base ordering preserved.
        self.assertEqual([r["chunk_id"] for r in ordered], ["a", "b"])
        self.assertEqual(ordered[0]["recency_score"], 0.0)
        self.assertEqual(ordered[0]["score"], 0.9)

    def test_recency_does_not_override_a_strong_relevance_gap(self) -> None:
        # A clearly more relevant but older chunk still beats a fresh weak one:
        # the bonus is bounded by RECENCY_WEIGHT + COVERAGE_WEIGHT.
        rows = [_row("relevant_old", 0.9, iteration=1), _row("weak_new", 0.4, iteration=9)]
        ordered = apply_recency_coverage_rescore(rows, set())
        self.assertEqual(ordered[0]["chunk_id"], "relevant_old")
        self.assertLessEqual(RECENCY_WEIGHT + COVERAGE_WEIGHT, 0.9 - 0.4)

    def test_domain_coverage_rewards_query_referenced_domain(self) -> None:
        tokens = set(tokenize("technical auth model for the service"))
        self.assertEqual(domain_coverage({"domain": "technical"}, tokens), 1.0)
        self.assertEqual(domain_coverage({"domain": "design"}, tokens), 0.0)
        self.assertEqual(domain_coverage({"domain": "technical"}, set()), 0.0)

    def test_coverage_lifts_on_domain_over_off_domain_at_equal_base(self) -> None:
        tokens = set(tokenize("technical service"))
        rows = [
            _row("off", 0.7, iteration=1, domain="design"),
            _row("on", 0.7, iteration=1, domain="technical"),
        ]
        ordered = apply_recency_coverage_rescore(rows, tokens)
        self.assertEqual(ordered[0]["chunk_id"], "on")
        self.assertEqual(ordered[0]["coverage_score"], 1.0)

    def test_empty_shortlist_is_returned_as_is(self) -> None:
        self.assertEqual(apply_recency_coverage_rescore([], set()), [])


class RescoreIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.old_cwd = Path.cwd()
        self.temp = Path(tempfile.mkdtemp())
        os.chdir(self.temp)
        self.assertEqual(main(["init", "REC"]), 0)
        self.broker = ContextBroker("REC")

    def tearDown(self) -> None:
        os.chdir(self.old_cwd)
        shutil.rmtree(self.temp, ignore_errors=True)

    def _index(self, artifact_id: str, text: str, *, iteration: int, domain: str = "product") -> None:
        self.broker.index_artifact(
            artifact_id=artifact_id,
            artifact_type="requirements",
            source_path=Path(f"{artifact_id}.md"),
            text=text,
            domain=domain,
            iteration=iteration,
        )

    def test_fresher_equivalent_context_ranks_first_end_to_end(self) -> None:
        text = "The notifications service sends alerts to subscribed users."
        self._index("STALE", text, iteration=1)
        self._index("FRESH", text, iteration=3)
        results = self.broker.retrieve("notifications service alerts users", "specs")
        self.assertTrue(results)
        self.assertEqual(results[0]["artifact_id"], "FRESH")
        # Re-score telemetry is exposed; verbatim content and read_plan are intact.
        self.assertIn("recency_score", results[0])
        self.assertIn("base_score", results[0])
        self.assertNotIn("context_text", results[0])
        self.assertNotIn("[document:", results[0]["text"])
        self.assertIn("read_plan", results[0])
        self.assertIn("recency boost", results[0]["why_retrieved"])

    def test_retrieve_recency_weight_zero_threads_through_and_disables_recency(self) -> None:
        text = "notifications service sends alerts to subscribed users"
        self._index("STALE", text, iteration=1)
        self._index("FRESH", text, iteration=5)
        # Recency ON (default): the fresher iteration wins the lexical tie.
        on = self.broker.retrieve("notifications service alerts users", "specs")
        self.assertEqual(on[0]["artifact_id"], "FRESH")
        # Recency OFF: the param threads through to the re-score, the recency bonus
        # is gone for every row, and freshness no longer promotes FRESH — ordering
        # falls to the deterministic chunk_id tie-break (STALE > FRESH).
        off = self.broker.retrieve("notifications service alerts users", "specs", recency_weight=0.0)
        self.assertTrue(off)
        self.assertTrue(all(r["recency_score"] == 0.0 for r in off))
        self.assertEqual(off[0]["artifact_id"], "STALE")

    def test_retrieve_is_deterministic_across_runs(self) -> None:
        self._index("A", "auth model and login token validation for the service", iteration=2, domain="technical")
        self._index("B", "auth model and login token validation for the service", iteration=1, domain="technical")
        first = [r["chunk_id"] for r in self.broker.retrieve("auth model login token", "specs")]
        second = [r["chunk_id"] for r in self.broker.retrieve("auth model login token", "specs")]
        self.assertEqual(first, second)
        self.assertEqual(first[0].split("::")[0], "A")


if __name__ == "__main__":
    unittest.main()
