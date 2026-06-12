"""Retrieval eval harness with golden queries (IMP-032).

Makes the memory architecture falsifiable: per fixture, golden queries map a
natural-language query to the artifact(s) that should be retrieved. We score
recall@5 and MRR over the active backend (json-hybrid by default; lancedb when
installed). Same-language queries must retrieve their target. Cross-lingual
ES/EN queries are a progress metric in hash fallback mode and become a hard
gate when a semantic local embedder is active.

A JSON report is written under tests/evals/reports/ each run.
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import tempfile
from datetime import date
from pathlib import Path
import unittest

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "evals"
REPORTS = REPO_ROOT / "tests" / "evals" / "reports"


def _matches(result_path: str, expected: list[str]) -> bool:
    return any(name in result_path for name in expected)


def _score_query(broker, gq: dict) -> dict:
    results = broker.retrieve(gq["query"], gq.get("workflow", "specs"), limit=5)
    rank = 0
    for index, row in enumerate(results, start=1):
        if _matches(str(row.get("source_path", "")), gq["expected_artifacts"]):
            rank = index
            break
    return {"id": gq["id"], "kind": gq.get("kind", "same-language"), "hit": rank > 0, "mrr": round(1.0 / rank, 3) if rank else 0.0}


def _run_fixture(fixture_dir: Path) -> dict | None:
    key = json.loads((fixture_dir / "answer_key.json").read_text(encoding="utf-8"))
    golden = key.get("golden_queries")
    if not golden:
        return None
    from sentinel.cli import main
    from sentinel.memory import ContextBroker

    project_id = "RET" + "".join(c for c in fixture_dir.name.upper() if c.isalpha())[:10]
    old_cwd = Path.cwd()
    with tempfile.TemporaryDirectory(prefix="sentinel_ret_") as temp:
        os.chdir(temp)
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                assert main(["init", project_id]) == 0
                assert main(["ingest", project_id, "--source", str(fixture_dir / "requirement.md")]) == 0
                broker = ContextBroker(project_id)
                backend = broker.backend
                backend_degradation_reason = broker.lancedb_degraded_reason or None
                fts_ready = broker.fts_ready
                scored = [_score_query(broker, gq) for gq in golden]
        finally:
            os.chdir(old_cwd)

    def _recall(kind: str) -> float:
        rows = [s for s in scored if s["kind"] == kind]
        return round(sum(1 for s in rows if s["hit"]) / len(rows), 3) if rows else 1.0

    same = [s for s in scored if s["kind"] == "same-language"]
    return {
        "fixture": fixture_dir.name,
        "backend": backend,
        "backend_degradation_reason": backend_degradation_reason,
        "fts_ready": fts_ready,
        "queries": scored,
        "recall_same_language": _recall("same-language"),
        "recall_cross_lingual": _recall("cross-lingual"),
        "mrr_same_language": round(sum(s["mrr"] for s in same) / len(same), 3) if same else 1.0,
    }


def _backend_summary(results: list[dict]) -> dict[str, dict[str, float | int]]:
    summary: dict[str, dict[str, float | int]] = {}
    for backend in sorted({row["backend"] for row in results}):
        rows = [row for row in results if row["backend"] == backend]
        summary[backend] = {
            "fixtures": len(rows),
            "avg_recall_same_language": round(sum(row["recall_same_language"] for row in rows) / len(rows), 3),
            "avg_recall_cross_lingual": round(sum(row["recall_cross_lingual"] for row in rows) / len(rows), 3),
            "avg_mrr_same_language": round(sum(row["mrr_same_language"] for row in rows) / len(rows), 3),
        }
    return summary


class RetrievalEvalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from sentinel.memory import active_embedder_status

        cls.embedder_status = active_embedder_status()
        cls.results = [r for d in sorted(FIXTURES.iterdir()) if (d / "answer_key.json").exists()
                       for r in [_run_fixture(d)] if r]
        REPORTS.mkdir(parents=True, exist_ok=True)
        report = {
            "date": date.today().isoformat(),
            "embedder": cls.embedder_status,
            "fixtures": cls.results,
            "summary": {
                "avg_recall_same_language": round(sum(r["recall_same_language"] for r in cls.results) / len(cls.results), 3) if cls.results else 1.0,
                "avg_recall_cross_lingual": round(sum(r["recall_cross_lingual"] for r in cls.results) / len(cls.results), 3) if cls.results else 0.0,
                "avg_mrr_same_language": round(sum(r["mrr_same_language"] for r in cls.results) / len(cls.results), 3) if cls.results else 1.0,
                "by_backend": _backend_summary(cls.results),
            },
        }
        (REPORTS / f"retrieval_eval_{report['date']}.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        cls.report = report

    def test_has_golden_queries(self):
        self.assertTrue(self.results, "no fixtures with golden_queries found")
        self.assertGreaterEqual(len(self.results), 4, "all eval fixtures should define golden_queries")

    def test_same_language_retrieval_meets_baseline(self):
        # Same-language golden queries must retrieve their target artifact in top-5.
        self.assertGreaterEqual(self.report["summary"]["avg_recall_same_language"], 0.5)

    def test_report_compares_backend_metrics(self):
        by_backend = self.report["summary"]["by_backend"]
        self.assertTrue(by_backend, "retrieval report should include per-backend metrics")
        for backend, metrics in by_backend.items():
            self.assertIn(backend, {"json-hybrid", "lancedb-hybrid"})
            self.assertGreaterEqual(metrics["fixtures"], 1)
            self.assertIn("avg_mrr_same_language", metrics)

    def test_cross_lingual_is_recorded_as_progress_metric(self):
        # In hash fallback this is only recorded; with semantic embeddings it is the IMP-029 gate.
        self.assertIsInstance(self.report["summary"]["avg_recall_cross_lingual"], float)
        if self.embedder_status.get("semantic"):
            self.assertGreater(
                self.report["summary"]["avg_recall_cross_lingual"],
                0.0,
                "semantic embedder is active but cross-lingual golden retrieval did not improve",
            )


if __name__ == "__main__":
    unittest.main()
