"""IMP-223 (H11, eval-hardening 2/2): guards for the context-rot measurement
added to ``tests/evals/run_discovery_evals.py``.

Context-rot = how much noise/dilution the discovery output pack (the gaps the
retrieval-informed pipeline surfaces downstream to brief/specs/backlog)
accumulates, tracked against the workspace size it was surfaced from. As a
workspace grows, a degrading memory dilutes the pack with false positives; this
metric makes that trend visible.

Three properties, all deterministic and product-free:

- **Per-fixture signal.** ``context_rot_signal`` derives ``dilution`` (the share
  of the surfaced pack that is noise, ``1 - precision``), ``distractor_leak``
  (the planted-noise subset), ``pack_size`` and ``input_chars`` from one row.
- **Growth trend.** ``context_rot_report`` orders fixtures by workspace size and
  reports ``growth_delta`` (upper-half minus lower-half mean dilution): positive
  means the pack dilutes as the workspace grows.
- **Measurement, not gate.** The threshold only *flags* fixtures for visibility;
  ``rot_ok`` reflects that flag but is never wired into ``baseline_ok`` — a
  metric with no failure baseline must not block the pipeline (doc 43 seed 7).

Mirrors the ``_load_runner`` pattern in test_evals_generalization.py.
"""
from __future__ import annotations

import importlib.util
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


def _row(
    fixture: str,
    *,
    input_chars: int,
    precision: float,
    fired: int = 3,
    false_positives: list | None = None,
    distractor_rate: float = 0.0,
    split: str = "tuning",
) -> dict:
    """A minimal fixture result row carrying only the fields context-rot reads."""
    return {
        "fixture": fixture,
        "split": split,
        "input_chars": input_chars,
        "fired_count": fired,
        "gap_precision": precision,
        "gap_benchmark": {"precision": precision},
        "false_positives": false_positives if false_positives is not None else [],
        "distractor_false_positive_rate": distractor_rate,
    }


class ContextRotSignalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runner = _load_runner()

    def test_clean_pack_has_no_rot(self):
        sig = self.runner.context_rot_signal(_row("a", input_chars=100, precision=1.0))
        self.assertEqual(sig["dilution"], 0.0)
        self.assertEqual(sig["distractor_leak"], 0.0)
        self.assertEqual(sig["input_chars"], 100)
        self.assertEqual(sig["pack_size"], 3)

    def test_dilution_is_precision_complement(self):
        sig = self.runner.context_rot_signal(
            _row("a", input_chars=100, precision=0.4, false_positives=["GAP-X", "GAP-Y"], distractor_rate=0.5)
        )
        self.assertEqual(sig["dilution"], 0.6)
        self.assertEqual(sig["noise_count"], 2)
        self.assertEqual(sig["distractor_leak"], 0.5)

    def test_signal_reads_precision_from_benchmark_when_flat_field_absent(self):
        row = _row("a", input_chars=100, precision=0.8)
        del row["gap_precision"]
        sig = self.runner.context_rot_signal(row)
        self.assertAlmostEqual(sig["dilution"], 0.2, places=3)


class ContextRotReportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runner = _load_runner()

    def test_fixtures_ordered_by_workspace_size(self):
        rows = [
            _row("big", input_chars=5000, precision=1.0),
            _row("small", input_chars=100, precision=1.0),
            _row("mid", input_chars=1000, precision=1.0),
        ]
        report = self.runner.context_rot_report(rows)
        self.assertEqual([s["fixture"] for s in report["fixtures"]], ["small", "mid", "big"])

    def test_growth_delta_positive_when_large_workspaces_dilute_more(self):
        rows = [
            _row("s1", input_chars=100, precision=1.0),
            _row("s2", input_chars=200, precision=1.0),
            _row("big1", input_chars=4000, precision=0.5),
            _row("big2", input_chars=5000, precision=0.5),
        ]
        report = self.runner.context_rot_report(rows)
        self.assertEqual(report["lower_half_mean_dilution"], 0.0)
        self.assertEqual(report["upper_half_mean_dilution"], 0.5)
        self.assertEqual(report["growth_delta"], 0.5)
        self.assertEqual(report["max_dilution"], 0.5)

    def test_clean_run_has_zero_rot_and_is_ok(self):
        rows = [_row("a", input_chars=100, precision=1.0), _row("b", input_chars=900, precision=1.0)]
        report = self.runner.context_rot_report(rows)
        self.assertEqual(report["mean_dilution"], 0.0)
        self.assertEqual(report["growth_delta"], 0.0)
        self.assertEqual(report["flagged"], [])
        self.assertTrue(report["rot_ok"])

    def test_threshold_flags_but_only_reports(self):
        rows = [
            _row("clean", input_chars=100, precision=1.0),
            _row("rotten", input_chars=200, precision=0.3),  # dilution 0.7 > 0.5
        ]
        report = self.runner.context_rot_report(rows)
        self.assertIn("rotten", report["flagged"])
        self.assertNotIn("clean", report["flagged"])
        self.assertFalse(report["rot_ok"])
        # Informative only: the report exposes no baseline/return-code field.
        self.assertNotIn("baseline_ok", report)

    def test_custom_threshold_respected(self):
        rows = [_row("mild", input_chars=100, precision=0.7)]  # dilution 0.3
        self.assertEqual(self.runner.context_rot_report(rows, threshold=0.2)["flagged"], ["mild"])
        self.assertEqual(self.runner.context_rot_report(rows, threshold=0.5)["flagged"], [])

    def test_empty_results_are_vacuously_clean(self):
        report = self.runner.context_rot_report([])
        self.assertEqual(report["mean_dilution"], 0.0)
        self.assertEqual(report["max_dilution"], 0.0)
        self.assertEqual(report["growth_delta"], 0.0)
        self.assertTrue(report["rot_ok"])

    def test_report_is_deterministic(self):
        rows = [
            _row("a", input_chars=300, precision=0.6),
            _row("b", input_chars=100, precision=0.9),
        ]
        self.assertEqual(self.runner.context_rot_report(rows), self.runner.context_rot_report(rows))


class FixtureInputCharsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runner = _load_runner()

    def test_input_chars_positive_and_ranks_by_workspace_size(self):
        """The workspace-size axis is a real, non-degenerate signal on disk: the
        known-smallest fixture carries fewer input chars than a larger one."""
        thin = self.runner.fixture_input_chars(FIXTURES / "adversarial-thin-intake")
        big = self.runner.fixture_input_chars(FIXTURES / "ops-risk-backlog")
        self.assertGreater(thin, 0)
        self.assertGreater(big, thin)


if __name__ == "__main__":
    unittest.main()
