"""Discovery gap-detection and brief-coverage eval harness (IMP-020, IMP-027).

Runs the Sentinel lifecycle over synthetic fixtures with answer keys and
measures gap detection quality plus project-brief evidence coverage.
Local-first and deterministic: no network, no external services.

Two progress metrics travel with the baseline (neither fails the build):
- target_recall: semantic gaps the lexical checklist suppresses today and an
  agentic pass (IMP-021 /annotate) must catch. 0.00 at baseline.
- brief_target_coverage: narrative brief sections (1-6) that have confirmed
  evidence but the template renderer leaves as TBD; the IMP-024 brief compiler
  must populate them. 0.00 at baseline.

Usage, from the repository root:

    python tests/evals/run_discovery_evals.py

Exit code 0 when current behavior matches the recorded baseline
(must_fire detected, no NEW false positives). Known engine bugs are
documented in each answer key as known_false_positives and target_fire
and reported as progress metrics, not failures.
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import re
import sys
import tempfile
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "evals"
REPORTS = REPO_ROOT / "tests" / "evals" / "reports"

sys.path.insert(0, str(REPO_ROOT))
from sentinel.cli import main  # noqa: E402

GAP_HEADING = re.compile(r"^### (GAP-[A-Z-]+)", re.M)
BRIEF_SECTION = re.compile(r"^## (\d+)\.", re.M)
BRIEF_TRACKED_SECTIONS = ("1", "2", "3", "4", "5", "6")
BRIEF_PENDING_MARKERS = (
    "TBD",
    "[PENDING INPUT]",
    "PENDING DOMAIN",
    "No structured evidence",
    "Documentar el",
    "Documentar la",
)


def brief_section_status(brief_md: str) -> dict:
    sections: dict = {}
    current = None
    for line in brief_md.splitlines():
        match = BRIEF_SECTION.match(line)
        if match:
            current = match.group(1)
            sections.setdefault(current, [])
        elif current is not None:
            sections[current].append(line)
    status = {}
    for sec in BRIEF_TRACKED_SECTIONS:
        body = "\n".join(sections.get(sec, []))
        is_pending = any(marker in body for marker in BRIEF_PENDING_MARKERS)
        status[sec] = "pending" if is_pending else "populated"
    return status


def run_fixture(fixture_dir: Path) -> dict:
    key = json.loads((fixture_dir / "answer_key.json").read_text(encoding="utf-8"))
    requirement = fixture_dir / "requirement.md"
    project_id = "EVAL" + re.sub(r"[^A-Z]", "", fixture_dir.name.upper())[:12]

    old_cwd = Path.cwd()
    with tempfile.TemporaryDirectory(prefix="sentinel_eval_") as temp:
        os.chdir(temp)
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                assert main(["init", project_id]) == 0, f"init failed for {fixture_dir.name}"
                assert main(["ingest", project_id, "--source", str(requirement)]) == 0, (
                    f"ingest failed for {fixture_dir.name}"
                )
                assert main(["brief", project_id]) == 0, f"brief failed for {fixture_dir.name}"
            ws = Path(temp) / "workspaces" / project_id
            fired = set(GAP_HEADING.findall((ws / "01_discovery" / "gaps.md").read_text(encoding="utf-8")))
            brief_status = brief_section_status(
                (ws / "02_requirements" / "project-brief.md").read_text(encoding="utf-8")
            )
        finally:
            os.chdir(old_cwd)

    must_fire = set(key["must_fire"])
    must_not_fire = set(key["must_not_fire"])
    known_fp = set(key.get("known_false_positives", []))
    target = set(key.get("target_fire", []))

    missing = sorted(must_fire - fired)
    false_positives = sorted(fired & must_not_fire)
    new_false_positives = sorted((fired & must_not_fire) - known_fp)
    fixed_known_fp = sorted(known_fp - fired)
    target_detected = sorted(fired & target)

    brief_key = key.get("brief", {})
    brief_target = [s for s in brief_key.get("target_populated", []) if s in BRIEF_TRACKED_SECTIONS]
    brief_populated = sorted(s for s, st in brief_status.items() if st == "populated")
    brief_target_populated = sorted(s for s in brief_target if brief_status.get(s) == "populated")

    return {
        "fixture": fixture_dir.name,
        "language": key.get("language", "unknown"),
        "fired_count": len(fired),
        "fired": sorted(fired),
        "recall_must_fire": round(len(must_fire & fired) / len(must_fire), 3) if must_fire else 1.0,
        "missing_must_fire": missing,
        "false_positives": false_positives,
        "new_false_positives": new_false_positives,
        "fixed_known_false_positives": fixed_known_fp,
        "target_fire_total": len(target),
        "target_fire_detected": target_detected,
        "target_recall": round(len(target_detected) / len(target), 3) if target else 1.0,
        "brief_sections_status": brief_status,
        "brief_sections_populated": brief_populated,
        "brief_target_sections": sorted(brief_target),
        "brief_target_populated": brief_target_populated,
        "brief_target_coverage": round(len(brief_target_populated) / len(brief_target), 3) if brief_target else 1.0,
        "baseline_ok": not missing and not new_false_positives,
    }


def run_all() -> int:
    fixture_dirs = sorted(d for d in FIXTURES.iterdir() if (d / "answer_key.json").exists())
    if not fixture_dirs:
        print("No eval fixtures found under tests/fixtures/evals/")
        return 1
    results = [run_fixture(d) for d in fixture_dirs]

    report = {
        "date": date.today().isoformat(),
        "fixtures": results,
        "summary": {
            "fixtures_run": len(results),
            "baseline_ok": all(r["baseline_ok"] for r in results),
            "avg_recall_must_fire": round(sum(r["recall_must_fire"] for r in results) / len(results), 3),
            "avg_target_recall": round(sum(r["target_recall"] for r in results) / len(results), 3),
            "avg_brief_target_coverage": round(sum(r["brief_target_coverage"] for r in results) / len(results), 3),
            "total_new_false_positives": sum(len(r["new_false_positives"]) for r in results),
            "total_fixed_known_false_positives": sum(len(r["fixed_known_false_positives"]) for r in results),
        },
    }

    REPORTS.mkdir(parents=True, exist_ok=True)
    out = REPORTS / f"discovery_eval_{report['date']}.json"
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"Discovery evals — {report['date']}")
    for r in results:
        status = "OK " if r["baseline_ok"] else "FAIL"
        print(
            f"  [{status}] {r['fixture']:24s} recall={r['recall_must_fire']:.2f} "
            f"target={len(r['target_fire_detected'])}/{r['target_fire_total']} "
            f"brief={len(r['brief_target_populated'])}/{len(r['brief_target_sections'])} "
            f"new_fp={len(r['new_false_positives'])}"
        )
        for gap in r["missing_must_fire"]:
            print(f"         missing: {gap}")
        for gap in r["new_false_positives"]:
            print(f"         new false positive: {gap}")
        for gap in r["fixed_known_false_positives"]:
            print(f"         fixed known false positive: {gap} (update answer key)")
    s = report["summary"]
    print(
        f"Summary: baseline_ok={s['baseline_ok']} avg_recall={s['avg_recall_must_fire']:.2f} "
        f"avg_target_recall={s['avg_target_recall']:.2f} (IMP-015/021 progress) "
        f"avg_brief_target_coverage={s['avg_brief_target_coverage']:.2f} (IMP-024 progress)"
    )
    print(f"Report: {out}")
    return 0 if s["baseline_ok"] else 1


if __name__ == "__main__":
    sys.exit(run_all())
