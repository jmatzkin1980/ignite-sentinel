"""Discovery, brief, PRD, and specs eval harness (IMP-020, IMP-027, IMP-039).

Runs the Sentinel lifecycle over synthetic fixtures with answer keys and
measures gap detection quality plus project-brief, PRD, and specs evidence
coverage.
Local-first and deterministic: no network, no external services.

Two progress metrics travel with the baseline (neither fails the build):
- target_recall: semantic gaps the lexical checklist suppresses today and an
  agentic pass (IMP-021 /annotate) must catch. 0.00 at baseline.
- brief_target_coverage: narrative brief sections (1-6) that have confirmed
  evidence but the template renderer leaves as TBD; the IMP-024 brief compiler
  must populate them. 0.00 at baseline.
- prd_target_coverage: PRD narrative sections that have confirmed evidence
  and should be compiled from it in IMP-039.
- specs_scaffolding_count: fixed scaffold IDs in specs.md. IMP-042 keeps this
  at zero by decomposing specs into evidence-backed units.

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
from sentinel.discovery import parse_gap_rows  # noqa: E402

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
PRD_SECTION = re.compile(r"^## (\d+)\.", re.M)
PRD_TRACKED_SECTIONS = tuple(str(item) for item in range(1, 14))
PRD_PENDING_MARKERS = (
    "[PENDING INPUT]",
    "PENDING INPUT",
    "TBD",
    "GAP-PRD-",
    "GAP-METRIC-SOURCE",
)
SPECS_SCAFFOLDING_IDS = (
    "JTBD-001",
    "CAP-001",
    "CAP-002",
    "CAP-003",
    "US-001",
    "US-002",
    "US-003",
    "US-004",
    "US-005",
    "ASM-001",
    "ASM-002",
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


def prd_section_status(prd_md: str) -> dict:
    sections: dict = {}
    current = None
    for line in prd_md.splitlines():
        match = PRD_SECTION.match(line)
        if match:
            current = match.group(1)
            sections.setdefault(current, [])
        elif current is not None:
            sections[current].append(line)
    status = {}
    for sec in PRD_TRACKED_SECTIONS:
        body = "\n".join(sections.get(sec, []))
        is_pending = (not body.strip()) or any(marker in body for marker in PRD_PENDING_MARKERS)
        status[sec] = "pending" if is_pending else "populated"
    return status


def specs_scaffolding(specs_md: str) -> dict[str, object]:
    found = sorted({item for item in SPECS_SCAFFOLDING_IDS if re.search(rf"\b{re.escape(item)}\b", specs_md)})
    return {"ids": found, "count": len(found)}


def run_fixture(fixture_dir: Path, apply_annotation: bool = False) -> dict:
    key = json.loads((fixture_dir / "answer_key.json").read_text(encoding="utf-8"))
    requirement = fixture_dir / "requirement.md"
    annotation = fixture_dir / "annotation.json"
    gap_responses = fixture_dir / "gap_responses.md"
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
                # IMP-021: optionally apply the agent's stored semantic analysis
                # so target_recall reflects the agentic pass, not the lexical one.
                if apply_annotation and annotation.exists():
                    assert main(["annotate", project_id, "--source", str(annotation)]) == 0, (
                        f"annotate failed for {fixture_dir.name}"
                    )
                if gap_responses.exists() and not apply_annotation:
                    assert main(["resolve-gaps", project_id, "--source", str(gap_responses)]) == 0, (
                        f"resolve-gaps failed for {fixture_dir.name}"
                    )
                assert main(["brief", project_id]) == 0, f"brief failed for {fixture_dir.name}"
                if not apply_annotation:
                    assert main(["specs", project_id]) == 0, f"specs failed for {fixture_dir.name}"
            ws = Path(temp) / "workspaces" / project_id
            gaps_md = (ws / "01_discovery" / "gaps.md").read_text(encoding="utf-8")
            gap_rows = parse_gap_rows(gaps_md)
            fired = set(GAP_HEADING.findall(gaps_md))
            gap_details = {row["id"]: row for row in gap_rows}
            state = json.loads((ws / "state.json").read_text(encoding="utf-8"))
            brief_status = brief_section_status(
                (ws / "02_requirements" / "project-brief.md").read_text(encoding="utf-8")
            )
            if apply_annotation:
                prd_status = {section: "pending" for section in PRD_TRACKED_SECTIONS}
                specs_scaffold = {"ids": [], "count": 0}
            else:
                prd_status = prd_section_status((ws / "03_specs" / "prd.md").read_text(encoding="utf-8"))
                specs_text = (ws / "03_specs" / "specs.md").read_text(encoding="utf-8")
                specs_scaffold = specs_scaffolding(specs_text)
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
    brief_pending_target = [s for s in brief_key.get("target_pending", []) if s in BRIEF_TRACKED_SECTIONS]
    brief_populated = sorted(s for s, st in brief_status.items() if st == "populated")
    brief_pending = sorted(s for s, st in brief_status.items() if st == "pending")
    brief_target_populated = sorted(s for s in brief_target if brief_status.get(s) == "populated")
    brief_target_pending = sorted(s for s in brief_pending_target if brief_status.get(s) == "pending")

    prd_key = key.get("prd", {})
    prd_target = [str(s) for s in prd_key.get("target_populated", []) if str(s) in PRD_TRACKED_SECTIONS]
    prd_populated = sorted(s for s, st in prd_status.items() if st == "populated")
    prd_pending = sorted(s for s, st in prd_status.items() if st == "pending")
    prd_target_populated = sorted(s for s in prd_target if prd_status.get(s) == "populated")

    ears_key = key.get("ears", {})
    expected_ears_eligible = sorted(ears_key.get("expected_eligible_not_normalized", []))
    ears_eligible_not_normalized = sorted(
        row["id"] for row in gap_rows if "EARS-eligible" in str(row.get("resolution_note", ""))
    )
    ears_eligible_mismatch = ears_eligible_not_normalized != expected_ears_eligible

    expected_language = key.get("expected_language", key.get("language"))
    language_detected = state.get("project_language", "unknown")
    language_mismatch = language_detected != expected_language

    expected_gap_details = dict(key.get("expected_gap_details", {}))
    if apply_annotation:
        expected_gap_details.update(key.get("annotate", {}).get("expected_gap_details", {}))
    gap_detail_mismatches = []
    for gap_id, expected in expected_gap_details.items():
        actual = gap_details.get(gap_id)
        if not actual:
            gap_detail_mismatches.append({"gap": gap_id, "field": "presence", "expected": "present", "actual": "missing"})
            continue
        for field, expected_value in expected.items():
            actual_value = actual.get(field)
            if actual_value != expected_value:
                gap_detail_mismatches.append(
                    {"gap": gap_id, "field": field, "expected": expected_value, "actual": actual_value}
                )

    origin_counts: dict[str, int] = {}
    severity_counts: dict[str, int] = {}
    lens_counts: dict[str, int] = {}
    for row in gap_rows:
        origin = row.get("origin", "checklist")
        severity = row.get("severity", "unknown")
        lens = row.get("lens", "unknown")
        origin_counts[origin] = origin_counts.get(origin, 0) + 1
        severity_counts[severity] = severity_counts.get(severity, 0) + 1
        lens_counts[lens] = lens_counts.get(lens, 0) + 1

    return {
        "fixture": fixture_dir.name,
        "language": key.get("language", "unknown"),
        "expected_language": expected_language,
        "detected_language": language_detected,
        "language_mismatch": language_mismatch,
        "fired_count": len(fired),
        "fired": sorted(fired),
        "origin_counts": origin_counts,
        "severity_counts": severity_counts,
        "lens_counts": lens_counts,
        "gap_detail_mismatches": gap_detail_mismatches,
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
        "brief_sections_pending": brief_pending,
        "brief_target_sections": sorted(brief_target),
        "brief_target_populated": brief_target_populated,
        "brief_target_coverage": round(len(brief_target_populated) / len(brief_target), 3) if brief_target else 1.0,
        "brief_expected_pending_sections": sorted(brief_pending_target),
        "brief_expected_pending_matched": brief_target_pending,
        "brief_expected_pending_coverage": (
            round(len(brief_target_pending) / len(brief_pending_target), 3) if brief_pending_target else 1.0
        ),
        "prd_sections_status": prd_status,
        "prd_sections_populated": prd_populated,
        "prd_sections_pending": prd_pending,
        "prd_target_sections": sorted(prd_target),
        "prd_target_populated": prd_target_populated,
        "prd_target_coverage": round(len(prd_target_populated) / len(prd_target), 3) if prd_target else 1.0,
        "ears_expected_eligible_not_normalized": expected_ears_eligible,
        "ears_eligible_not_normalized": ears_eligible_not_normalized,
        "ears_eligible_mismatch": ears_eligible_mismatch,
        "specs_scaffolding_ids": specs_scaffold["ids"],
        "specs_scaffolding_count": specs_scaffold["count"],
        "baseline_ok": (
            not missing
            and not new_false_positives
            and not language_mismatch
            and not gap_detail_mismatches
            and not ears_eligible_mismatch
            and sorted(brief_pending_target) == brief_target_pending
            and not specs_scaffold["ids"]
        ),
    }


def run_all() -> int:
    fixture_dirs = sorted(d for d in FIXTURES.iterdir() if (d / "answer_key.json").exists())
    if not fixture_dirs:
        print("No eval fixtures found under tests/fixtures/evals/")
        return 1
    results = [run_fixture(d) for d in fixture_dirs]

    # IMP-021 progress: re-run fixtures that carry an agent annotation through
    # the /annotate pass. Additive metric; the lexical baseline above is
    # untouched so prior baselines never regress.
    annotated_results = [
        run_fixture(d, apply_annotation=True) if (d / "annotation.json").exists() else r
        for d, r in zip(fixture_dirs, results)
    ]
    annotated_fixtures = sum(1 for d in fixture_dirs if (d / "annotation.json").exists())

    report = {
        "date": date.today().isoformat(),
        "fixtures": results,
        "summary": {
            "fixtures_run": len(results),
            "baseline_ok": all(r["baseline_ok"] for r in results),
            "avg_recall_must_fire": round(sum(r["recall_must_fire"] for r in results) / len(results), 3),
            "avg_target_recall": round(sum(r["target_recall"] for r in results) / len(results), 3),
            "avg_target_recall_with_annotations": round(
                sum(r["target_recall"] for r in annotated_results) / len(annotated_results), 3
            ),
            "annotated_fixtures": annotated_fixtures,
            "avg_brief_target_coverage": round(sum(r["brief_target_coverage"] for r in results) / len(results), 3),
            "avg_brief_expected_pending_coverage": round(
                sum(r["brief_expected_pending_coverage"] for r in results) / len(results), 3
            ),
            "avg_prd_target_coverage": round(sum(r["prd_target_coverage"] for r in results) / len(results), 3),
            "total_ears_eligible_not_normalized": sum(len(r["ears_eligible_not_normalized"]) for r in results),
            "total_ears_eligible_mismatches": sum(1 for r in results if r["ears_eligible_mismatch"]),
            "avg_specs_scaffolding": round(sum(r["specs_scaffolding_count"] for r in results) / len(results), 3),
            "total_specs_scaffolding": sum(r["specs_scaffolding_count"] for r in results),
            "total_new_false_positives": sum(len(r["new_false_positives"]) for r in results),
            "total_fixed_known_false_positives": sum(len(r["fixed_known_false_positives"]) for r in results),
            "total_language_mismatches": sum(1 for r in results if r["language_mismatch"]),
            "total_gap_detail_mismatches": sum(len(r["gap_detail_mismatches"]) for r in results),
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
            f"prd={len(r['prd_target_populated'])}/{len(r['prd_target_sections'])} "
            f"spec_scaffold={r['specs_scaffolding_count']} "
            f"new_fp={len(r['new_false_positives'])}"
        )
        for gap in r["missing_must_fire"]:
            print(f"         missing: {gap}")
        for gap in r["new_false_positives"]:
            print(f"         new false positive: {gap}")
        for gap in r["fixed_known_false_positives"]:
            print(f"         fixed known false positive: {gap} (update answer key)")
        if r["language_mismatch"]:
            print(f"         language mismatch: expected {r['expected_language']} got {r['detected_language']}")
        for mismatch in r["gap_detail_mismatches"]:
            print(
                f"         gap metadata mismatch: {mismatch['gap']} {mismatch['field']} "
                f"expected {mismatch['expected']} got {mismatch['actual']}"
            )
        if r["ears_eligible_mismatch"]:
            print(
                "         EARS eligible mismatch: expected "
                f"{r['ears_expected_eligible_not_normalized']} got {r['ears_eligible_not_normalized']}"
            )
        expected_pending = set(r["brief_expected_pending_sections"])
        matched_pending = set(r["brief_expected_pending_matched"])
        for section in sorted(expected_pending - matched_pending):
            print(f"         brief section expected pending but populated: {section}")
    s = report["summary"]
    print(
        f"Summary: baseline_ok={s['baseline_ok']} avg_recall={s['avg_recall_must_fire']:.2f} "
        f"avg_target_recall={s['avg_target_recall']:.2f} lexical / "
        f"{s['avg_target_recall_with_annotations']:.2f} with /annotate "
        f"({s['annotated_fixtures']} annotated fixtures, IMP-021) "
        f"avg_brief_target_coverage={s['avg_brief_target_coverage']:.2f} (IMP-024 progress) "
        f"avg_brief_pending_coverage={s['avg_brief_expected_pending_coverage']:.2f} "
        f"avg_prd_target_coverage={s['avg_prd_target_coverage']:.2f} (IMP-039 compiled PRD) "
        f"ears_eligible_not_normalized={s['total_ears_eligible_not_normalized']} "
        f"avg_specs_scaffolding={s['avg_specs_scaffolding']:.2f} (IMP-042 spec units)"
    )
    print(f"Report: {out}")
    return 0 if s["baseline_ok"] else 1


if __name__ == "__main__":
    sys.exit(run_all())
