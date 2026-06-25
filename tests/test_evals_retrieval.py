"""Retrieval eval harness with section-level golden queries (IMP-032, hardened IMP-120).

Makes the memory architecture falsifiable AND discriminant. Per fixture, golden
queries map a natural-language query to the specific artifact **section/chunk**
that should be retrieved (not a whole document), and every fixture workspace is
seeded with a shared corpus of multi-domain distractor documents. We score
recall@5 and MRR over the active backend (json-hybrid by default; lancedb when
installed) and the active embedder (hash fallback by default; semantic local
when installed). The JSON report compares metrics ``by_backend`` and
``by_embedder``.

Before IMP-120 the golden queries pointed at whole ``requirements.md`` /
``gaps.md`` files and the fixture workspace had a handful of docs, so recall
saturated at 1.0 and the harness could not prove any retrieval improvement.
Section-level targets plus cross-domain distractors make recall fall below the
trivial ceiling and force the engine to discriminate the correct section from
look-alike distractor content. The test stays green as a non-regression gate
with a recalibrated (non-saturated) threshold; raising the bar is the job of the
retrieval-quality items (IMP-121+), which this harness now measures.

A JSON report is written under tests/evals/reports/ each run.
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import shutil
import tempfile
from datetime import date
from pathlib import Path
import unittest

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "evals"
REPORTS = REPO_ROOT / "tests" / "evals" / "reports"
DISTRACTORS = FIXTURES / "_distractors"

# Shared multi-domain distractor corpus -> workspace context folders (IMP-120).
# Each distractor doc is wrong-domain reference material that lexically competes
# with the golden queries (objective/users/scope/metric/dashboard) so a query
# can no longer win by trivial keyword overlap inside a tiny workspace.
DISTRACTOR_FOLDERS = {
    "business": "00_raw/01_business_context",
    "technology": "00_raw/02_technology_context",
    "design": "00_raw/03_design_context",
    "quality": "00_raw/04_quality_context",
}


def distractor_stems() -> set[str]:
    if not DISTRACTORS.exists():
        return set()
    return {p.stem for p in DISTRACTORS.rglob("*.md")}


def seed_distractors(workspace: Path) -> int:
    """Copy the shared distractor corpus into the workspace context folders."""
    seeded = 0
    for domain, rel in DISTRACTOR_FOLDERS.items():
        source = DISTRACTORS / domain
        if not source.is_dir():
            continue
        target = workspace / rel
        target.mkdir(parents=True, exist_ok=True)
        for doc in sorted(source.glob("*.md")):
            shutil.copyfile(doc, target / doc.name)
            seeded += 1
    return seeded


def _row_matches(row: dict, gq: dict, distractors: set[str]) -> bool:
    """A row is a target hit iff it matches the expected section AND artifact.

    Distractor chunks can never count as a hit: they live under context folders
    and carry their own section paths, so they only compete by out-ranking.
    """
    source_path = str(row.get("source_path", ""))
    if any(stem in source_path for stem in distractors):
        return False
    section = str(row.get("section_path", ""))
    expected_section = gq.get("expected_section", "")
    if expected_section and expected_section.lower() not in section.lower():
        return False
    expected_artifacts = gq.get("expected_artifacts", [])
    if expected_artifacts and not any(name in source_path for name in expected_artifacts):
        return False
    # A golden query must constrain at least one axis.
    return bool(expected_section or expected_artifacts)


def _is_distractor(row: dict, distractors: set[str]) -> bool:
    source_path = str(row.get("source_path", ""))
    return any(stem in source_path for stem in distractors)


def _score_query(broker, gq: dict, distractors: set[str]) -> dict:
    results = broker.retrieve(gq["query"], gq.get("workflow", "specs"), limit=5)
    rank = 0
    distractor_rank = 0
    for index, row in enumerate(results, start=1):
        if rank == 0 and _row_matches(row, gq, distractors):
            rank = index
        if distractor_rank == 0 and _is_distractor(row, distractors):
            distractor_rank = index
    # The engine "discriminates" on a hit when the correct section out-ranks any
    # look-alike distractor chunk that surfaced for the same query.
    discriminates = bool(rank) and (distractor_rank == 0 or rank < distractor_rank)
    return {
        "id": gq["id"],
        "kind": gq.get("kind", "same-language"),
        "hit": rank > 0,
        "rank": rank,
        "mrr": round(1.0 / rank, 3) if rank else 0.0,
        "distractor_in_top5": distractor_rank > 0,
        "discriminates": discriminates,
    }


def _run_fixture(fixture_dir: Path, distractors: set[str]) -> dict | None:
    key = json.loads((fixture_dir / "answer_key.json").read_text(encoding="utf-8"))
    golden = key.get("golden_queries")
    if not golden:
        return None
    from sentinel.cli import main
    from sentinel.memory import ContextBroker, reindex_workspace

    project_id = "RET" + "".join(c for c in fixture_dir.name.upper() if c.isalpha())[:10]
    old_cwd = Path.cwd()
    with tempfile.TemporaryDirectory(prefix="sentinel_ret_") as temp:
        os.chdir(temp)
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                assert main(["init", project_id]) == 0
                assert main(["ingest", project_id, "--source", str(fixture_dir / "requirement.md")]) == 0
                workspace = Path(temp) / "workspaces" / project_id
                seeded = seed_distractors(workspace)
                if seeded:
                    reindex_workspace(project_id, full=True)
                broker = ContextBroker(project_id)
                backend = broker.backend
                backend_degradation_reason = broker.lancedb_degraded_reason or None
                fts_ready = broker.fts_ready
                scored = [_score_query(broker, gq, distractors) for gq in golden]
        finally:
            os.chdir(old_cwd)

    def _recall(kind: str) -> float:
        rows = [s for s in scored if s["kind"] == kind]
        return round(sum(1 for s in rows if s["hit"]) / len(rows), 3) if rows else 1.0

    same = [s for s in scored if s["kind"] == "same-language"]
    same_hits = [s for s in same if s["hit"]]
    return {
        "fixture": fixture_dir.name,
        "backend": backend,
        "backend_degradation_reason": backend_degradation_reason,
        "fts_ready": fts_ready,
        "distractors_seeded": seeded,
        "queries": scored,
        "recall_same_language": _recall("same-language"),
        "recall_cross_lingual": _recall("cross-lingual"),
        "mrr_same_language": round(sum(s["mrr"] for s in same) / len(same), 3) if same else 1.0,
        "distractor_in_top5_rate": round(sum(1 for s in scored if s["distractor_in_top5"]) / len(scored), 3) if scored else 0.0,
        "discrimination_rate": round(sum(1 for s in same_hits if s["discriminates"]) / len(same_hits), 3) if same_hits else 1.0,
    }


def _group_summary(results: list[dict], key: str) -> dict[str, dict[str, float | int]]:
    summary: dict[str, dict[str, float | int]] = {}
    for value in sorted({row[key] for row in results}):
        rows = [row for row in results if row[key] == value]
        summary[value] = {
            "fixtures": len(rows),
            "avg_recall_same_language": round(sum(r["recall_same_language"] for r in rows) / len(rows), 3),
            "avg_recall_cross_lingual": round(sum(r["recall_cross_lingual"] for r in rows) / len(rows), 3),
            "avg_mrr_same_language": round(sum(r["mrr_same_language"] for r in rows) / len(rows), 3),
            "avg_discrimination_rate": round(sum(r["discrimination_rate"] for r in rows) / len(rows), 3),
        }
    return summary


class RetrievalEvalTests(unittest.TestCase):
    # Recalibrated, non-saturated gate (IMP-120). Section-level golden queries
    # over a distractor-seeded workspace make hash-mode recall fall well below
    # the old universal 1.0. These floors guard against regression below the
    # measured baseline without pretending retrieval is solved.
    SAME_LANGUAGE_RECALL_FLOOR = 0.4
    SAME_LANGUAGE_MRR_FLOOR = 0.25

    @classmethod
    def setUpClass(cls):
        from sentinel.memory import active_embedder_status

        cls.embedder_status = active_embedder_status()
        cls.distractors = distractor_stems()
        cls.results = [r for d in sorted(FIXTURES.iterdir())
                       if d.is_dir() and (d / "answer_key.json").exists()
                       for r in [_run_fixture(d, cls.distractors)] if r]
        REPORTS.mkdir(parents=True, exist_ok=True)
        n = len(cls.results) or 1
        report = {
            "date": date.today().isoformat(),
            "embedder": cls.embedder_status,
            "distractor_docs": sorted(cls.distractors),
            "fixtures": cls.results,
            "summary": {
                "avg_recall_same_language": round(sum(r["recall_same_language"] for r in cls.results) / n, 3) if cls.results else 1.0,
                "avg_recall_cross_lingual": round(sum(r["recall_cross_lingual"] for r in cls.results) / n, 3) if cls.results else 0.0,
                "avg_mrr_same_language": round(sum(r["mrr_same_language"] for r in cls.results) / n, 3) if cls.results else 1.0,
                "avg_discrimination_rate": round(sum(r["discrimination_rate"] for r in cls.results) / n, 3) if cls.results else 1.0,
                "by_backend": _group_summary(cls.results, "backend"),
                "by_embedder": _group_summary([{**r, "embedder": cls.embedder_status["level"]} for r in cls.results], "embedder"),
            },
        }
        (REPORTS / f"retrieval_eval_{report['date']}.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        cls.report = report

    def test_has_section_level_golden_queries(self):
        self.assertTrue(self.results, "no fixtures with golden_queries found")
        self.assertGreaterEqual(len(self.results), 4, "all eval fixtures should define golden_queries")
        # Every golden query must constrain a specific section (the IMP-120 gate),
        # not just a whole artifact.
        for fixture in sorted(FIXTURES.iterdir()):
            key_path = fixture / "answer_key.json"
            if not (fixture.is_dir() and key_path.exists()):
                continue
            for gq in json.loads(key_path.read_text(encoding="utf-8")).get("golden_queries", []):
                self.assertTrue(
                    gq.get("expected_section"),
                    f"{fixture.name}/{gq.get('id')} must declare an expected_section (IMP-120)",
                )

    def test_hash_mode_is_discriminant_not_saturated(self):
        # The whole point of IMP-120: in the hash fallback, section-level recall
        # must no longer be a universal 1.0 — otherwise the harness cannot prove
        # any retrieval improvement. Under a semantic embedder, higher recall is
        # the GOAL (IMP-121+), so non-saturation is a hash-mode baseline property.
        if self.embedder_status.get("semantic"):
            self.skipTest("non-saturation is a hash-fallback property; semantic mode is expected to lift recall")
        self.assertLess(
            self.report["summary"]["avg_recall_same_language"],
            1.0,
            "hash-mode section-level recall saturated at 1.0 — the harness is no longer discriminant",
        )

    def test_same_language_retrieval_meets_recalibrated_baseline(self):
        # Non-regression floor over section-level golden queries (recalibrated).
        self.assertGreaterEqual(
            self.report["summary"]["avg_recall_same_language"],
            self.SAME_LANGUAGE_RECALL_FLOOR,
        )
        self.assertGreaterEqual(
            self.report["summary"]["avg_mrr_same_language"],
            self.SAME_LANGUAGE_MRR_FLOOR,
        )

    def test_distractors_are_seeded_and_discriminated(self):
        # Distractors must actually be present in every workspace, and on a hit
        # the correct section must out-rank look-alike distractor chunks.
        for fixture in self.results:
            self.assertGreater(fixture["distractors_seeded"], 0, f"{fixture['fixture']} seeded no distractors")
        self.assertGreaterEqual(self.report["summary"]["avg_discrimination_rate"], 0.5)

    def test_report_compares_backend_and_embedder_metrics(self):
        summary = self.report["summary"]
        for axis in ("by_backend", "by_embedder"):
            self.assertTrue(summary[axis], f"retrieval report should include {axis} metrics")
            for label, metrics in summary[axis].items():
                self.assertGreaterEqual(metrics["fixtures"], 1)
                self.assertIn("avg_mrr_same_language", metrics)
                self.assertIn("avg_discrimination_rate", metrics)
        for backend in summary["by_backend"]:
            self.assertIn(backend, {"json-hybrid", "lancedb-hybrid"})

    def test_cross_lingual_is_progress_metric_or_semantic_gate(self):
        # In hash fallback this is only recorded; with semantic embeddings it is
        # the IMP-029 gate that section-level cross-lingual retrieval must clear.
        self.assertIsInstance(self.report["summary"]["avg_recall_cross_lingual"], float)
        if self.embedder_status.get("semantic"):
            self.assertGreater(
                self.report["summary"]["avg_recall_cross_lingual"],
                0.0,
                "semantic embedder is active but cross-lingual section retrieval did not improve",
            )


if __name__ == "__main__":
    unittest.main()
