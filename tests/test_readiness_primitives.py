from __future__ import annotations

import unittest

from sentinel.readiness_primitives import (
    above_threshold,
    average_score,
    is_blocking_gap,
    weighted_score,
)


class ReadinessPrimitivesTests(unittest.TestCase):
    def test_above_threshold_preserves_inclusive_gate_semantics(self):
        self.assertTrue(above_threshold(0.8, 0.8))
        self.assertTrue(above_threshold(0.81, 0.8))
        self.assertFalse(above_threshold(0.79, 0.8))
        self.assertFalse(above_threshold(0.8, 0.8, inclusive=False))

    def test_average_score_rounds_like_existing_readiness_scores(self):
        self.assertEqual(average_score([]), 0.0)
        self.assertEqual(average_score([1.0, 0.65, 0.0]), 0.55)
        self.assertEqual(average_score([1, 1, 0]), 0.667)

    def test_weighted_score_maps_status_cells_to_average_score(self):
        cells = [{"status": "CONFIRMED"}, {"status": "ASSUMED"}, {"status": "OPEN"}]
        weights = {"CONFIRMED": 1.0, "ASSUMED": 0.65, "OPEN": 0.0}
        self.assertEqual(weighted_score(cells, weights), 0.55)
        self.assertEqual(weighted_score([{"quality": "pass"}, {"quality": "fail"}], {"pass": 1}, status_key="quality"), 0.5)

    def test_is_blocking_gap_reuses_canonical_gap_predicate(self):
        self.assertTrue(is_blocking_gap({"severity": "high", "status": "OPEN"}))
        self.assertTrue(is_blocking_gap({"severity": "medium", "status": "ANSWERED"}, {"medium"}))
        self.assertFalse(is_blocking_gap({"severity": "high", "status": "CLOSED"}))


if __name__ == "__main__":
    unittest.main()
