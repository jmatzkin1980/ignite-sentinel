"""IMP-222 (H11, eval-hardening 1/2): guards for the held-out split and the
deviation-point detection added to ``tests/evals/run_discovery_evals.py``.

Two properties, both deterministic and product-free:

- **Held-out split.** A fixture may declare ``"split": "held_out"`` in its
  ``answer_key.json`` to mark it as generalization data never used to tune the
  engine. The runner reports tuning vs held-out metrics separately so a
  generalization gap (memorization) becomes visible instead of being averaged
  away into one aggregate.
- **Deviation-point.** ``collect_baseline_deviations`` reproduces the per-fixture
  baseline verdict as an ordered list of concrete points (which field diverged,
  expected vs actual). ``bool(...)`` is True iff ``baseline_ok`` is False — same
  signals, finer grain — so a regression names *where* it diverged, not just the
  aggregate pass/fail.

Mirrors the ``_load_runner`` pattern in test_discovery_eval_benchmark.py.
"""
from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "evals"


def _load_runner():
    spec = importlib.util.spec_from_file_location(
        "run_discovery_evals", REPO_ROOT / "tests" / "evals" / "run_discovery_evals.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _clean_row(fixture: str = "fx", split: str = "tuning") -> dict:
    """A synthetic fixture result row that passes every baseline condition."""
    return {
        "fixture": fixture,
        "split": split,
        "baseline_ok": True,
        "missing_must_fire": [],
        "new_false_positives": [],
        "language_mismatch": False,
        "expected_language": "en",
        "detected_language": "en",
        "gap_detail_mismatches": [],
        "ears_eligible_mismatch": False,
        "ears_expected_eligible_not_normalized": [],
        "ears_eligible_not_normalized": [],
        "brief_expected_pending_sections": ["3"],
        "brief_expected_pending_matched": ["3"],
        "specs_scaffolding_ids": [],
        "backlog_derivation_mismatches": [],
        "gap_benchmark": {"f1": 1.0},
        "recall_must_fire": 1.0,
        "target_recall": 1.0,
    }


class FixtureSplitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runner = _load_runner()

    def test_split_defaults_to_tuning(self):
        self.assertEqual(self.runner.fixture_split({}), "tuning")
        self.assertEqual(self.runner.fixture_split({"split": "tuning"}), "tuning")
        self.assertEqual(self.runner.fixture_split({"split": "whatever"}), "tuning")

    def test_held_out_marker_is_case_insensitive(self):
        self.assertEqual(self.runner.fixture_split({"split": "held_out"}), "held_out")
        self.assertEqual(self.runner.fixture_split({"split": " HELD_OUT "}), "held_out")

    def test_declared_held_out_fixtures_are_marked_on_disk(self):
        """The tuning/held-out partition is a real, non-degenerate split: at least
        one fixture on each side, and the intended held-out fixtures carry it."""
        splits = {}
        for key_path in sorted(FIXTURES.glob("*/answer_key.json")):
            key = json.loads(key_path.read_text(encoding="utf-8"))
            splits[key_path.parent.name] = self.runner.fixture_split(key)
        held_out = {name for name, s in splits.items() if s == "held_out"}
        tuning = {name for name, s in splits.items() if s == "tuning"}
        self.assertTrue(held_out, "expected at least one held-out fixture")
        self.assertTrue(tuning, "expected at least one tuning fixture")
        self.assertIn("adversarial-thin-intake", held_out)
        self.assertIn("adversarial-partial-gap-response", held_out)
        self.assertIn("implicit-complete-intake", held_out)


class BaselineDeviationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runner = _load_runner()

    def test_clean_row_has_no_deviations(self):
        row = _clean_row()
        self.assertEqual(self.runner.collect_baseline_deviations(row), [])
        # Consistency invariant: deviations are non-empty iff baseline failed.
        self.assertEqual(bool(self.runner.collect_baseline_deviations(row)), not row["baseline_ok"])

    def test_each_baseline_condition_produces_one_ordered_point(self):
        row = _clean_row()
        row["baseline_ok"] = False
        row["missing_must_fire"] = ["GAP-B"]
        row["new_false_positives"] = ["GAP-X"]
        row["language_mismatch"] = True
        row["detected_language"] = "es"
        row["gap_detail_mismatches"] = [{"gap": "GAP-A", "field": "lens"}]
        row["ears_eligible_mismatch"] = True
        row["brief_expected_pending_matched"] = []  # expected ["3"] != matched []
        row["specs_scaffolding_ids"] = ["US-001"]
        row["backlog_derivation_mismatches"] = ["missing SPEC-U-1"]

        devs = self.runner.collect_baseline_deviations(row)
        fields = [d["field"] for d in devs]
        self.assertEqual(
            fields,
            [
                "must_fire",
                "false_positives",
                "language",
                "gap_details",
                "ears",
                "brief_pending",
                "specs_scaffolding",
                "backlog_derivation",
            ],
        )
        language = next(d for d in devs if d["field"] == "language")
        self.assertEqual(language["expected"], "en")
        self.assertEqual(language["actual"], "es")
        # Invariant holds on the dirty row too.
        self.assertEqual(bool(devs), not row["baseline_ok"])

    def test_deviation_points_span_fixtures_and_gates_in_order(self):
        clean = _clean_row(fixture="alpha")
        dirty = _clean_row(fixture="beta", split="held_out")
        dirty["baseline_ok"] = False
        dirty["missing_must_fire"] = ["GAP-B"]
        gates = {
            "compose": {"ok": True, "mismatches": []},
            "self-review": {"ok": False, "mismatches": ["fabricated citation"]},
        }

        points = self.runner.deviation_points_for_results([clean, dirty], gates)
        self.assertEqual(len(points), 2)
        self.assertEqual(points[0]["fixture"], "beta")
        self.assertEqual(points[0]["split"], "held_out")
        self.assertEqual(points[0]["field"], "must_fire")
        self.assertEqual(points[1]["fixture"], "self-review")
        self.assertEqual(points[1]["field"], "gate")

    def test_no_deviation_points_when_everything_green(self):
        points = self.runner.deviation_points_for_results(
            [_clean_row("alpha"), _clean_row("beta")],
            {"compose": {"ok": True, "mismatches": []}},
        )
        self.assertEqual(points, [])


class SplitMetricsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runner = _load_runner()

    def test_split_metrics_partition_by_split(self):
        rows = [_clean_row("a", "tuning"), _clean_row("b", "held_out")]
        rows[1]["baseline_ok"] = False
        rows[1]["missing_must_fire"] = ["GAP-B"]
        rows[1]["gap_benchmark"] = {"f1": 0.5}

        tuning = self.runner.split_metrics(rows, "tuning")
        held_out = self.runner.split_metrics(rows, "held_out")
        self.assertEqual(tuning["fixtures_run"], 1)
        self.assertTrue(tuning["baseline_ok"])
        self.assertEqual(tuning["deviation_points"], 0)
        self.assertEqual(held_out["fixtures_run"], 1)
        self.assertFalse(held_out["baseline_ok"])
        self.assertEqual(held_out["deviation_points"], 1)
        self.assertEqual(held_out["avg_gap_f1"], 0.5)

    def test_empty_split_is_vacuously_ok(self):
        metrics = self.runner.split_metrics([_clean_row("a", "tuning")], "held_out")
        self.assertEqual(metrics["fixtures_run"], 0)
        self.assertTrue(metrics["baseline_ok"])


if __name__ == "__main__":
    unittest.main()
