"""Eval report retention: runners keep the newest N reports per kind.

Reports under ``tests/evals/reports/`` are git-ignored and reproducible, but
they used to accumulate forever (one file per kind per day). The shared
``report_store`` helper writes a report and prunes older ones of the same kind,
so local disk usage stays bounded without losing the latest baselines.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent / "evals"))
import report_store  # noqa: E402


class ReportStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="sentinel_reports_")
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name)

    def _seed(self, kind: str, dates: list[str]) -> None:
        for day in dates:
            (self.dir / f"{kind}_{day}.json").write_text("{}", encoding="utf-8")

    def test_write_report_creates_dated_file(self) -> None:
        out = report_store.write_report("discovery_eval", "2026-11-05", {"ok": True}, reports_dir=self.dir, keep=5)
        self.assertEqual(out, self.dir / "discovery_eval_2026-11-05.json")
        self.assertEqual(json.loads(out.read_text(encoding="utf-8")), {"ok": True})

    def test_keeps_newest_n_per_kind_only(self) -> None:
        self._seed("discovery_eval", ["2026-06-01", "2026-06-02", "2026-06-03"])
        self._seed("retrieval_eval", ["2026-06-01", "2026-06-02"])
        report_store.write_report("discovery_eval", "2026-06-04", {}, reports_dir=self.dir, keep=2)
        names = sorted(p.name for p in self.dir.iterdir())
        self.assertEqual(
            names,
            [
                "discovery_eval_2026-06-03.json",
                "discovery_eval_2026-06-04.json",
                "retrieval_eval_2026-06-01.json",
                "retrieval_eval_2026-06-02.json",
            ],
        )

    def test_prefix_of_another_kind_is_not_pruned(self) -> None:
        # "discovery_eval" must not match "discovery_eval_extra_<date>".
        self._seed("discovery_eval_extra", ["2026-06-01"])
        report_store.write_report("discovery_eval", "2026-06-04", {}, reports_dir=self.dir, keep=1)
        self.assertTrue((self.dir / "discovery_eval_extra_2026-06-01.json").exists())

    def test_keep_zero_or_negative_keeps_everything(self) -> None:
        self._seed("discovery_eval", ["2026-06-01", "2026-06-02"])
        report_store.write_report("discovery_eval", "2026-06-03", {}, reports_dir=self.dir, keep=0)
        self.assertEqual(len(list(self.dir.glob("discovery_eval_*.json"))), 3)

    def test_prune_dry_run_lists_without_deleting(self) -> None:
        self._seed("discovery_eval", ["2026-06-01", "2026-06-02", "2026-06-03"])
        doomed = report_store.prune("discovery_eval", reports_dir=self.dir, keep=1, dry_run=True)
        self.assertEqual([p.name for p in doomed], ["discovery_eval_2026-06-01.json", "discovery_eval_2026-06-02.json"])
        self.assertEqual(len(list(self.dir.glob("*.json"))), 3)

    def test_env_controls_keep_and_disable(self) -> None:
        with patch.dict(os.environ, {"SENTINEL_EVAL_KEEP_REPORTS": "1"}):
            self.assertEqual(report_store.default_keep(), 1)
        with patch.dict(os.environ, {"SENTINEL_EVAL_KEEP_REPORTS": "nope"}):
            self.assertEqual(report_store.default_keep(), report_store.DEFAULT_KEEP)
        with patch.dict(os.environ, {"SENTINEL_EVAL_REPORTS": "0"}):
            self.assertIsNone(report_store.write_report("discovery_eval", "2026-06-01", {}, reports_dir=self.dir))
        self.assertEqual(list(self.dir.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
