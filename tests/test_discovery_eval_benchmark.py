from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_runner():
    spec = importlib.util.spec_from_file_location(
        "run_discovery_evals", REPO_ROOT / "tests" / "evals" / "run_discovery_evals.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class DiscoveryEvalBenchmarkTests(unittest.TestCase):
    def test_gap_benchmark_scores_labeled_gap_universe(self):
        runner = _load_runner()
        metrics = runner.discovery_gap_benchmark(
            fired={"GAP-A", "GAP-C"},
            must_fire={"GAP-A", "GAP-B"},
            target_fire={"GAP-T"},
            must_not_fire={"GAP-C"},
            known_false_positives=set(),
            distractors={"GAP-C", "GAP-D"},
            gap_details={
                "GAP-A": {"lens": "product"},
                "GAP-B": {"lens": "product"},
                "GAP-T": {"lens": "quality"},
            },
        )

        self.assertEqual(metrics["true_positive_total"], 1)
        self.assertEqual(metrics["false_positive_total"], 1)
        self.assertEqual(metrics["precision"], 0.5)
        self.assertEqual(metrics["recall"], 0.333)
        self.assertEqual(metrics["f1"], 0.4)
        self.assertEqual(metrics["required_recall"], 0.5)
        self.assertEqual(metrics["target_recall"], 0.0)
        self.assertEqual(metrics["distractor_total"], 2)
        self.assertEqual(metrics["distractor_false_positive_total"], 1)
        self.assertEqual(metrics["distractor_false_positive_rate"], 0.5)
        self.assertEqual(metrics["distractor_false_positives"], ["GAP-C"])
        self.assertEqual(metrics["by_lens"]["product"]["recall"], 0.5)

    def test_repeat_variance_is_population_variance(self):
        runner = _load_runner()
        self.assertEqual(runner.metric_variance([0.5, 1.0]), 0.0625)
        self.assertEqual(runner.metric_variance([1.0]), 0.0)

    def test_distractor_gap_ids_accepts_cited_objects(self):
        runner = _load_runner()
        self.assertEqual(
            runner.distractor_gap_ids(
                [
                    {
                        "gap_id": "GAP-AUTH-MODEL",
                        "source_quote": "The dashboard is internal to Support.",
                        "rationale": "Internal users are named; auth model is not a missing gap here.",
                    },
                    "GAP-SCOPE",
                ]
            ),
            {"GAP-AUTH-MODEL", "GAP-SCOPE"},
        )

    def test_repeat_variance_groups_by_fixture(self):
        runner = _load_runner()
        repeated = [
            [{"fixture": "fx", "gap_benchmark": {"precision": 1.0, "recall": 0.5, "f1": 0.667}}],
            [{"fixture": "fx", "gap_benchmark": {"precision": 1.0, "recall": 1.0, "f1": 1.0}}],
        ]

        variance = runner.repeat_variance_for_results(repeated)

        self.assertEqual(variance["fx"]["precision"], 0.0)
        self.assertEqual(variance["fx"]["recall"], 0.0625)
        self.assertEqual(variance["fx"]["f1"], 0.027722)


if __name__ == "__main__":
    unittest.main()
