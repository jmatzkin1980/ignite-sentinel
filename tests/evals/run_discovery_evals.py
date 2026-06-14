"""Discovery, brief, PRD, specs, and backlog eval harness.

Runs the Sentinel lifecycle over synthetic fixtures with answer keys and
measures gap detection quality plus project-brief, PRD, specs, and backlog
evidence coverage.
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
- backlog metrics: derivation from Spec Units, no-invention, slicing pattern
  baseline, and future per-story anchor/context checks (IMP-061).

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
import shutil
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
BACKLOG_LEGACY_SEED_TITLES = (
    "Habilitar el flujo principal de valor",
    "Preservar comportamiento existente y compatibilidad",
    "Conectar datos e integraciones necesarias",
    "Cubrir estados de experiencia y validaciones",
    "Producir evidencia de aceptacion y trazabilidad",
)

EVAL_CONTEXT_FOLDERS = {
    "technology": "00_raw/02_technology_context",
    "design": "00_raw/03_design_context",
    "quality": "00_raw/04_quality_context",
    "business": "00_raw/01_business_context",
    "interactions": "00_raw/05_interactions",
}


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
    gap_response_rounds = fixture_dir / "gap_response_rounds"
    project_id = "EVAL" + re.sub(r"[^A-Z]", "", fixture_dir.name.upper())[:12]

    old_cwd = Path.cwd()
    with tempfile.TemporaryDirectory(prefix="sentinel_eval_") as temp:
        os.chdir(temp)
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                assert main(["init", project_id]) == 0, f"init failed for {fixture_dir.name}"
                copy_fixture_domain_context(fixture_dir, Path(temp) / "workspaces" / project_id)
                assert main(["ingest", project_id, "--source", str(requirement)]) == 0, (
                    f"ingest failed for {fixture_dir.name}"
                )
                # IMP-021: optionally apply the agent's stored semantic analysis
                # so target_recall reflects the agentic pass, not the lexical one.
                if apply_annotation and annotation.exists():
                    assert main(["annotate", project_id, "--source", str(annotation)]) == 0, (
                        f"annotate failed for {fixture_dir.name}"
                    )
                if not apply_annotation:
                    response_sources = []
                    if gap_responses.exists():
                        response_sources.append(gap_responses)
                    if gap_response_rounds.exists():
                        response_sources.extend(sorted(gap_response_rounds.glob("*.md")))
                    for response_source in response_sources:
                        assert main(["resolve-gaps", project_id, "--source", str(response_source)]) == 0, (
                            f"resolve-gaps failed for {fixture_dir.name}: {response_source.name}"
                        )
                assert main(["brief", project_id]) == 0, f"brief failed for {fixture_dir.name}"
                if not apply_annotation:
                    assert main(["specs", project_id]) == 0, f"specs failed for {fixture_dir.name}"
                    assert main(["backlog", project_id]) == 0, f"backlog failed for {fixture_dir.name}"
                    refinement_source = fixture_dir / "backlog_refinement.json"
                    if refinement_source.exists():
                        assert main(["refine-backlog", project_id, "--source", str(refinement_source)]) == 0, (
                            f"refine-backlog failed for {fixture_dir.name}"
                        )
                    story_status_key = key.get("story_status", {})
                    if story_status_key:
                        command = [
                            "story-status",
                            project_id,
                            "--story",
                            str(story_status_key["story"]),
                            "--set",
                            str(story_status_key["set"]),
                        ]
                        if story_status_key.get("owner"):
                            command.extend(["--owner", str(story_status_key["owner"])])
                        assert main(command) == 0, f"story-status failed for {fixture_dir.name}"
                    if key.get("story_quality"):
                        assert main(["quality", project_id]) == 0, f"quality failed for {fixture_dir.name}"
                    hooks_key = key.get("backlog_hooks", {})
                    if hooks_key.get("sync_stale_spec_unit"):
                        unit_id = str(hooks_key["sync_stale_spec_unit"])
                        unit_path = Path(temp) / "workspaces" / project_id / "03_specs" / "units" / f"{unit_id}.md"
                        assert unit_path.exists(), f"stale hook Spec Unit missing for {fixture_dir.name}: {unit_id}"
                        assert main(["sync", project_id, "--source", str(unit_path), "--note", "eval stale hook"]) == 0, (
                            f"sync stale hook failed for {fixture_dir.name}"
                        )
                    feedback_key = key.get("implementation_feedback", {})
                    if feedback_key:
                        feedback_source = fixture_dir / str(feedback_key.get("source", "implementation_feedback.json"))
                        assert feedback_source.exists(), (
                            f"implementation feedback source missing for {fixture_dir.name}: {feedback_source.name}"
                        )
                        assert main(["implementation-feedback", project_id, "--source", str(feedback_source)]) == 0, (
                            f"implementation-feedback failed for {fixture_dir.name}"
                        )
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
                backlog_derivation = {
                    "story_count": 0,
                    "story_ids": [],
                    "source_units": [],
                    "trace_unit_count": 0,
                    "mismatches": [],
                    "coverage": 1.0,
                    "no_invention_rate": 1.0,
                    "invented_story_count": 0,
                    "slicing_accuracy": 1.0,
                    "anchor_validity": 1.0,
                    "context_distinctness": 1.0,
                }
            else:
                prd_status = prd_section_status((ws / "03_specs" / "prd.md").read_text(encoding="utf-8"))
                specs_text = (ws / "03_specs" / "specs.md").read_text(encoding="utf-8")
                specs_scaffold = specs_scaffolding(specs_text)
                backlog_derivation = backlog_derivation_status(ws, key)
            backlog_refinement = backlog_refinement_status(ws, key)
            story_status = story_status_eval(ws, key)
            backlog_rollup = backlog_rollup_eval(ws, key)
            slice_plan = slice_plan_eval(ws, key)
            story_quality = story_quality_eval(ws, key)
            backlog_hooks = backlog_hooks_eval(ws, key)
            implementation_feedback = (
                {"ok": True, "mismatches": []}
                if apply_annotation
                else implementation_feedback_eval(ws, key)
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
    backlog_mismatches = backlog_derivation["mismatches"]
    backlog_mismatches.extend(backlog_refinement["mismatches"])
    backlog_mismatches.extend(story_status["mismatches"])
    backlog_mismatches.extend(backlog_rollup["mismatches"])
    backlog_mismatches.extend(slice_plan["mismatches"])
    backlog_mismatches.extend(story_quality["mismatches"])
    backlog_mismatches.extend(backlog_hooks["mismatches"])
    backlog_mismatches.extend(implementation_feedback["mismatches"])

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
        "backlog_story_count": backlog_derivation["story_count"],
        "backlog_story_ids": backlog_derivation["story_ids"],
        "backlog_source_units": backlog_derivation["source_units"],
        "backlog_trace_unit_count": backlog_derivation["trace_unit_count"],
        "backlog_derivation_mismatches": backlog_mismatches,
        "backlog_derivation_coverage": backlog_derivation["coverage"],
        "backlog_no_invention_rate": backlog_derivation["no_invention_rate"],
        "backlog_invented_story_count": backlog_derivation["invented_story_count"],
        "backlog_slicing_accuracy": backlog_derivation["slicing_accuracy"],
        "backlog_anchor_validity": backlog_derivation["anchor_validity"],
        "backlog_context_distinctness": backlog_derivation["context_distinctness"],
        "story_quality_min_score": story_quality["min_score"],
        "backlog_refinement_ok": backlog_refinement["ok"],
        "backlog_refinement_mismatches": backlog_refinement["mismatches"],
        "story_status_ok": story_status["ok"],
        "story_status_mismatches": story_status["mismatches"],
        "backlog_hooks_ok": backlog_hooks["ok"],
        "backlog_hooks_mismatches": backlog_hooks["mismatches"],
        "implementation_feedback_ok": implementation_feedback["ok"],
        "implementation_feedback_mismatches": implementation_feedback["mismatches"],
        "baseline_ok": (
            not missing
            and not new_false_positives
            and not language_mismatch
            and not gap_detail_mismatches
            and not ears_eligible_mismatch
            and sorted(brief_pending_target) == brief_target_pending
            and not specs_scaffold["ids"]
            and not backlog_mismatches
        ),
    }


def copy_fixture_domain_context(fixture_dir: Path, workspace: Path) -> None:
    context_root = fixture_dir / "domain_context"
    if not context_root.exists():
        return
    for domain, target_relative in EVAL_CONTEXT_FOLDERS.items():
        source_dir = context_root / domain
        if not source_dir.exists():
            continue
        target_dir = workspace / target_relative
        target_dir.mkdir(parents=True, exist_ok=True)
        for source in sorted(source_dir.rglob("*")):
            if not source.is_file() or source.suffix.lower() not in {".md", ".txt"}:
                continue
            relative = source.relative_to(source_dir)
            target = target_dir / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)


def backlog_derivation_status(ws: Path, key: dict) -> dict[str, object]:
    backlog_key = key.get("backlog", {})
    readiness_path = ws / "08_context_packs" / "implementation_readiness.json"
    if not readiness_path.exists():
        return {
            "story_count": 0,
            "story_ids": [],
            "source_units": [],
            "trace_unit_count": 0,
            "mismatches": ["implementation_readiness.json missing"],
            "coverage": 0.0,
            "no_invention_rate": 0.0,
            "invented_story_count": 0,
            "slicing_accuracy": 0.0,
            "anchor_validity": 0.0,
            "context_distinctness": 0.0,
        }
    readiness = json.loads(readiness_path.read_text(encoding="utf-8"))
    value_stories = [story for story in readiness.get("stories", []) if story.get("type") != "cross_cutting_enabler"]
    story_ids = sorted(
        str(story.get("story_id", story.get("id", "")))
        for story in value_stories
        if story.get("story_id") or story.get("id")
    )
    source_units = sorted(
        story.get("source_unit")
        for story in value_stories
        if isinstance(story.get("source_unit"), str) and str(story.get("source_unit")).startswith("SPEC-U-")
    )
    trace_unit_count = sum(
        1
        for story in value_stories
        if any(str(trace).startswith("SPEC-U-") for trace in story.get("trace", []))
    )
    story_files = sorted((ws / "04_backlog").glob("US-*.md"))
    story_ids_from_files = [path.stem for path in story_files]
    story_text_by_id = {path.stem: path.read_text(encoding="utf-8") for path in story_files}
    story_text = "\n".join(story_text_by_id.values())
    if not story_ids:
        story_ids = story_ids_from_files
    mismatches: list[str] = []
    expected_count = backlog_key.get("expected_story_count")
    if expected_count is not None and len(value_stories) != int(expected_count):
        mismatches.append(f"expected {expected_count} backlog stories, got {len(value_stories)}")
    expected_story_ids = sorted(str(item) for item in backlog_key.get("expected_story_ids", []))
    if expected_story_ids and story_ids != expected_story_ids:
        mismatches.append(f"expected story ids {expected_story_ids}, got {story_ids}")
    expected_units = sorted(str(item) for item in backlog_key.get("expected_source_units", []))
    if expected_units and source_units != expected_units:
        mismatches.append(f"expected source units {expected_units}, got {source_units}")
    if backlog_key.get("require_spec_unit_trace") and trace_unit_count != len(value_stories):
        mismatches.append(f"expected every story to trace to SPEC-U, got {trace_unit_count}/{len(value_stories)}")
    if backlog_key.get("expect_pending_stub"):
        if len(value_stories) != 1:
            mismatches.append(f"expected one pending backlog stub, got {len(value_stories)} stories")
        if value_stories and value_stories[0].get("type") != "pending_input_stub":
            mismatches.append(f"expected pending_input_stub, got {value_stories[0].get('type')}")
        if "[PENDING INPUT]" not in story_text:
            mismatches.append("expected pending backlog stub, but no [PENDING INPUT] marker was rendered")
    legacy_hits = sorted(title for title in BACKLOG_LEGACY_SEED_TITLES if title in story_text)
    if legacy_hits:
        mismatches.append(f"legacy seed titles rendered: {legacy_hits}")
    invented_stories = [
        story
        for story in value_stories
        if story.get("type") == "value_story" and not str(story.get("source_unit", "")).startswith("SPEC-U-")
    ]
    if backlog_key.get("require_no_invented_stories", bool(backlog_key)) and invented_stories:
        mismatches.append(
            "value stories without SPEC-U source_unit: "
            + ", ".join(str(story.get("id", "[unknown]")) for story in invented_stories)
        )
    slicing_mismatches = slicing_pattern_mismatches(value_stories, story_text_by_id, backlog_key)
    mismatches.extend(slicing_mismatches)
    anchor_mismatches, anchor_validity = backlog_anchor_status(ws, value_stories, backlog_key)
    mismatches.extend(anchor_mismatches)
    context_mismatches, context_distinctness = backlog_context_status(value_stories, backlog_key)
    mismatches.extend(context_mismatches)
    coverage = round(trace_unit_count / len(value_stories), 3) if value_stories else 0.0
    if not backlog_key:
        coverage = 1.0
    elif backlog_key.get("expect_pending_stub") and not expected_units:
        coverage = 1.0 if not mismatches else 0.0
    no_invention_rate = (
        round((len(value_stories) - len(invented_stories)) / len(value_stories), 3) if value_stories else 1.0
    )
    expected_slicing = backlog_key.get("expected_slicing_by_source_unit", {})
    slicing_accuracy = 1.0
    if expected_slicing:
        slicing_accuracy = round((len(expected_slicing) - len(slicing_mismatches)) / len(expected_slicing), 3)
    return {
        "story_count": len(value_stories),
        "story_ids": story_ids,
        "source_units": source_units,
        "trace_unit_count": trace_unit_count,
        "mismatches": mismatches,
        "coverage": coverage,
        "no_invention_rate": no_invention_rate,
        "invented_story_count": len(invented_stories),
        "slicing_accuracy": slicing_accuracy,
        "anchor_validity": anchor_validity,
        "context_distinctness": context_distinctness,
    }


def slicing_pattern_mismatches(
    value_stories: list[dict],
    story_text_by_id: dict[str, str],
    backlog_key: dict,
) -> list[str]:
    expected = {str(k): str(v) for k, v in backlog_key.get("expected_slicing_by_source_unit", {}).items()}
    if not expected:
        return []
    by_unit = {}
    for index, story in enumerate(value_stories, start=1):
        unit = str(story.get("source_unit", ""))
        if not unit.startswith("SPEC-U-"):
            continue
        slicing = str(story.get("slicing", ""))
        if not slicing:
            story_id = str(story.get("id") or f"US-{index:03d}")
            match = re.search(r"^(?:\*\*Slicing Pattern:\*\*|- Slicing pattern:) (.+?)(?:\.)?$", story_text_by_id.get(story_id, ""), re.M)
            slicing = match.group(1).strip() if match else ""
        by_unit[unit] = slicing
    mismatches = []
    for unit, expected_slicing in sorted(expected.items()):
        actual = by_unit.get(unit)
        if actual != expected_slicing:
            mismatches.append(f"expected slicing {expected_slicing!r} for {unit}, got {actual!r}")
    return mismatches


def collect_anchor_candidates(value: object) -> list[dict]:
    anchors: list[dict] = []
    if isinstance(value, dict):
        if {"source_path", "line_start", "line_end"}.issubset(value):
            anchors.append(value)
        for item in value.values():
            anchors.extend(collect_anchor_candidates(item))
    elif isinstance(value, list):
        for item in value:
            anchors.extend(collect_anchor_candidates(item))
    return anchors


def backlog_anchor_status(ws: Path, value_stories: list[dict], backlog_key: dict) -> tuple[list[str], float]:
    anchor_key = backlog_key.get("anchors", {})
    if not anchor_key.get("require_valid"):
        return [], 1.0
    anchors = []
    for story in value_stories:
        anchors.extend(collect_anchor_candidates(story.get("execution_contract", {})))
    if not anchors:
        return ["expected valid backlog anchors, got none"], 0.0
    mismatches = []
    valid = 0
    for anchor in anchors:
        source_path = ws / str(anchor.get("source_path", ""))
        line_start = int(anchor.get("line_start", 0) or 0)
        line_end = int(anchor.get("line_end", 0) or 0)
        if not source_path.exists():
            mismatches.append(f"anchor source missing: {anchor.get('source_path')}")
            continue
        lines = source_path.read_text(encoding="utf-8").splitlines()
        if line_start < 1 or line_end < line_start or line_end > len(lines):
            mismatches.append(f"anchor line range invalid: {anchor.get('source_path')}:{line_start}-{line_end}")
            continue
        valid += 1
    return mismatches, round(valid / len(anchors), 3)


def backlog_context_status(value_stories: list[dict], backlog_key: dict) -> tuple[list[str], float]:
    context_key = backlog_key.get("context", {})
    if not context_key.get("require_distinct_critical_surfaces"):
        return [], 1.0
    surfaces = {
        json.dumps(story.get("execution_contract", {}).get("critical_surfaces", {}), sort_keys=True)
        for story in value_stories
    }
    expected_min = int(context_key.get("min_distinct_critical_surfaces", len(value_stories)))
    distinct = len(surfaces)
    if distinct < expected_min:
        return [f"expected at least {expected_min} distinct critical surface contexts, got {distinct}"], (
            round(distinct / expected_min, 3) if expected_min else 1.0
        )
    return [], 1.0


def backlog_refinement_status(ws: Path, key: dict) -> dict[str, object]:
    refinement_key = key.get("backlog_refinement", {})
    if not refinement_key:
        return {"ok": True, "mismatches": []}
    mismatches: list[str] = []
    report_path = ws / "04_backlog" / "refinements" / "refinement_report.md"
    accepted_path = ws / "04_backlog" / "refinements" / "accepted_refinements.json"
    if not report_path.exists():
        return {"ok": False, "mismatches": ["refinement_report.md missing"]}
    accepted = json.loads(accepted_path.read_text(encoding="utf-8")) if accepted_path.exists() else []
    accepted_ids = sorted(str(item.get("id", "")) for item in accepted if item.get("id"))
    expected = sorted(str(item) for item in refinement_key.get("expected_accepted", []))
    if expected and accepted_ids != expected:
        mismatches.append(f"expected accepted refinements {expected}, got {accepted_ids}")
    epic_text = (ws / "04_backlog" / "EPIC-001.md").read_text(encoding="utf-8")
    if refinement_key.get("expect_origin_agent") and "Origin: agent" not in epic_text:
        mismatches.append("expected Origin: agent refinement section in EPIC-001.md")
    return {"ok": not mismatches, "mismatches": mismatches}


def story_status_eval(ws: Path, key: dict) -> dict[str, object]:
    status_key = key.get("story_status", {})
    if not status_key:
        return {"ok": True, "mismatches": []}
    mismatches: list[str] = []
    story_id = str(status_key.get("story", ""))
    expected_status = str(status_key.get("set", ""))
    expected_owner = str(status_key.get("owner", ""))
    state = json.loads((ws / "state.json").read_text(encoding="utf-8"))
    lifecycle = state.get("story_lifecycle", {}).get(story_id, {})
    gate = state.get("story_gates", {}).get(story_id, {})
    if lifecycle.get("status") != expected_status:
        mismatches.append(f"expected {story_id} status {expected_status}, got {lifecycle.get('status')}")
    if expected_owner and lifecycle.get("owner") != expected_owner:
        mismatches.append(f"expected {story_id} owner {expected_owner}, got {lifecycle.get('owner')}")
    if status_key.get("expect_dor_missing"):
        dor = gate.get("dor", {}) if isinstance(gate, dict) else {}
        if dor.get("passed") is not False or not dor.get("missing"):
            mismatches.append(f"expected {story_id} DoR gate to persist missing items")
    if status_key.get("expect_dor_passed"):
        dor = gate.get("dor", {}) if isinstance(gate, dict) else {}
        if dor.get("passed") is not True:
            mismatches.append(f"expected {story_id} DoR gate to pass")
    if status_key.get("expect_dod_missing"):
        dod = gate.get("dod", {}) if isinstance(gate, dict) else {}
        if dod.get("passed") is not False or not dod.get("missing"):
            mismatches.append(f"expected {story_id} DoD gate to persist missing items")
    story_path = ws / "04_backlog" / f"{story_id}.md"
    if not story_path.exists():
        mismatches.append(f"{story_id}.md missing")
    else:
        text = story_path.read_text(encoding="utf-8")
        if f"status: {expected_status}" not in text:
            mismatches.append(f"{story_id}.md missing status frontmatter {expected_status}")
        if expected_owner and f'owner: "{expected_owner}"' not in text:
            mismatches.append(f"{story_id}.md missing owner frontmatter {expected_owner}")
    return {"ok": not mismatches, "mismatches": mismatches}


def backlog_rollup_eval(ws: Path, key: dict) -> dict[str, object]:
    rollup_key = key.get("backlog_rollup", {})
    if not rollup_key:
        return {"ok": True, "mismatches": []}
    mismatches: list[str] = []
    board_path = ws / "04_backlog" / "BACKLOG.md"
    if not board_path.exists():
        mismatches.append("BACKLOG.md missing")
        return {"ok": False, "mismatches": mismatches}
    state = json.loads((ws / "state.json").read_text(encoding="utf-8"))
    summary = state.get("backlog_rollup", {})
    for status, expected in rollup_key.get("expected_status_counts", {}).items():
        actual = summary.get("status_counts", {}).get(status)
        if actual != expected:
            mismatches.append(f"expected backlog rollup {status}={expected}, got {actual}")
    if "expected_stories_total" in rollup_key and summary.get("stories_total") != rollup_key["expected_stories_total"]:
        mismatches.append(f"expected backlog rollup stories_total={rollup_key['expected_stories_total']}, got {summary.get('stories_total')}")
    text = board_path.read_text(encoding="utf-8")
    for expected_text in rollup_key.get("must_contain", []):
        if str(expected_text) not in text:
            mismatches.append(f"BACKLOG.md missing expected text: {expected_text}")
    return {"ok": not mismatches, "mismatches": mismatches}


def slice_plan_eval(ws: Path, key: dict) -> dict[str, object]:
    plan_key = key.get("slice_plan", {})
    if not plan_key:
        return {"ok": True, "mismatches": []}
    mismatches: list[str] = []
    md_path = ws / "04_backlog" / "SLICE-PLAN.md"
    json_path = ws / "08_context_packs" / "slice_plan.json"
    if not md_path.exists():
        mismatches.append("SLICE-PLAN.md missing")
    if not json_path.exists():
        mismatches.append("slice_plan.json missing")
    if mismatches:
        return {"ok": False, "mismatches": mismatches}
    plan = json.loads(json_path.read_text(encoding="utf-8"))
    summary = plan.get("summary", {})
    if "expected_stories_total" in plan_key and summary.get("stories_total") != plan_key["expected_stories_total"]:
        mismatches.append(f"expected slice plan stories_total={plan_key['expected_stories_total']}, got {summary.get('stories_total')}")
    if "expected_enablers_min" in plan_key and summary.get("enablers_total", 0) < plan_key["expected_enablers_min"]:
        mismatches.append(f"expected at least {plan_key['expected_enablers_min']} enablers, got {summary.get('enablers_total')}")
    phases = plan.get("phases", {})
    enabler_ids = [item.get("story_id") for item in phases.get("enabler_phase", [])]
    if plan_key.get("require_enablers_first") and summary.get("enablers_total", 0):
        for story_id, pack in plan.get("handoff_packs", {}).items():
            if pack.get("position", {}).get("phase") == "implementation":
                prerequisites = set(pack.get("position", {}).get("prerequisites", []))
                if not prerequisites.intersection(enabler_ids):
                    mismatches.append(f"expected {story_id} to carry enabler prerequisite in slice plan")
                    break
    for story_id in plan_key.get("expected_handoff_packs", []):
        pack = plan.get("handoff_packs", {}).get(story_id)
        if not pack:
            mismatches.append(f"slice plan missing handoff pack for {story_id}")
            continue
        if not pack.get("retrieval_plan"):
            mismatches.append(f"slice plan handoff pack for {story_id} missing retrieval_plan")
        if "position" not in pack:
            mismatches.append(f"slice plan handoff pack for {story_id} missing position")
    text = md_path.read_text(encoding="utf-8")
    for expected_text in plan_key.get("must_contain", []):
        if str(expected_text) not in text:
            mismatches.append(f"SLICE-PLAN.md missing expected text: {expected_text}")
    return {"ok": not mismatches, "mismatches": mismatches}


def story_quality_eval(ws: Path, key: dict) -> dict[str, object]:
    quality_key = key.get("story_quality", {})
    if not quality_key:
        return {"ok": True, "mismatches": [], "min_score": 1.0}
    mismatches: list[str] = []
    state = json.loads((ws / "state.json").read_text(encoding="utf-8"))
    story_quality = state.get("story_quality", {})
    audit_path = ws / "05_quality" / "backlog_readiness_audit.md"
    if not audit_path.exists():
        mismatches.append("backlog_readiness_audit.md missing")
    if not isinstance(story_quality, dict) or not story_quality:
        mismatches.append("state.json missing story_quality results")
        return {"ok": False, "mismatches": mismatches, "min_score": 0.0}
    min_score = min(float(item.get("score", 0.0)) for item in story_quality.values() if isinstance(item, dict))
    expected_min = float(quality_key.get("min_score", 0.0))
    if min_score < expected_min:
        mismatches.append(f"expected story quality min_score >= {expected_min:.2f}, got {min_score:.2f}")
    for story_id in quality_key.get("expected_stories", []):
        result = story_quality.get(str(story_id), {})
        if not result:
            mismatches.append(f"story_quality missing {story_id}")
            continue
        checks = {item.get("key"): item for item in result.get("checks", []) if isinstance(item, dict)}
        for check in quality_key.get("required_checks", []):
            if check not in checks:
                mismatches.append(f"story_quality {story_id} missing check {check}")
    if quality_key.get("expect_dor_item"):
        expected_item = str(quality_key["expect_dor_item"])
        for story_id in quality_key.get("expected_stories", []):
            gate = state.get("story_gates", {}).get(str(story_id), {})
            dor_items = gate.get("dor", {}).get("items", []) if isinstance(gate, dict) else []
            if expected_item not in {item.get("key") for item in dor_items if isinstance(item, dict)}:
                mismatches.append(f"{story_id} DoR missing {expected_item}")
    if audit_path.exists():
        audit_text = audit_path.read_text(encoding="utf-8")
        for expected_text in quality_key.get("must_contain", []):
            if str(expected_text) not in audit_text:
                mismatches.append(f"backlog_readiness_audit.md missing expected text: {expected_text}")
    return {"ok": not mismatches, "mismatches": mismatches, "min_score": min_score}


def backlog_hooks_eval(ws: Path, key: dict) -> dict[str, object]:
    hooks_key = key.get("backlog_hooks", {})
    if not hooks_key:
        return {"ok": True, "mismatches": []}
    mismatches: list[str] = []
    state = json.loads((ws / "state.json").read_text(encoding="utf-8"))
    plan_path = ws / "08_context_packs" / "slice_plan.json"
    if hooks_key.get("expect_pre_handoff_warn"):
        if not plan_path.exists():
            mismatches.append("slice_plan.json missing for pre-handoff gate")
        else:
            gate = json.loads(plan_path.read_text(encoding="utf-8")).get("pre_handoff_gate", {})
            if gate.get("verdict") != "WARN" or not gate.get("warnings"):
                mismatches.append(f"expected pre-handoff WARN with warnings, got {gate}")
    expected_stale = str(hooks_key.get("expected_stale_story", ""))
    if expected_stale:
        lifecycle = state.get("story_lifecycle", {})
        actual_status = lifecycle.get(expected_stale, {}).get("status") if isinstance(lifecycle, dict) else None
        if actual_status != "Stale":
            mismatches.append(f"expected {expected_stale} to be Stale after /sync, got {actual_status}")
    expected_unchanged = str(hooks_key.get("expected_unchanged_story", ""))
    if expected_unchanged:
        lifecycle = state.get("story_lifecycle", {})
        actual_status = lifecycle.get(expected_unchanged, {}).get("status") if isinstance(lifecycle, dict) else None
        if actual_status == "Stale":
            mismatches.append(f"expected {expected_unchanged} to remain non-Stale after unrelated Spec Unit change")
    return {"ok": not mismatches, "mismatches": mismatches}


def implementation_feedback_eval(ws: Path, key: dict) -> dict[str, object]:
    feedback_key = key.get("implementation_feedback", {})
    if not feedback_key:
        return {"ok": True, "mismatches": []}
    mismatches: list[str] = []
    state = json.loads((ws / "state.json").read_text(encoding="utf-8"))
    payload = state.get("implementation_feedback", {})
    findings = payload.get("findings", {}) if isinstance(payload, dict) else {}
    expected_id = str(feedback_key.get("expected_finding", ""))
    finding = findings.get(expected_id) if isinstance(findings, dict) else None
    if not isinstance(finding, dict):
        mismatches.append(f"implementation_feedback missing finding {expected_id}")
        return {"ok": False, "mismatches": mismatches}
    expected_story = str(feedback_key.get("expected_story", ""))
    if expected_story and finding.get("story_id") != expected_story:
        mismatches.append(f"expected feedback story {expected_story}, got {finding.get('story_id')}")
    expected_gap = str(feedback_key.get("expected_gap", ""))
    if expected_gap and finding.get("gap_id") != expected_gap:
        mismatches.append(f"expected feedback gap {expected_gap}, got {finding.get('gap_id')}")
    if expected_story:
        open_ids = payload.get("open_by_story", {}).get(expected_story, []) if isinstance(payload, dict) else []
        if expected_id not in open_ids:
            mismatches.append(f"expected {expected_id} to block DoD for {expected_story}")
    if feedback_key.get("expect_stale") and expected_story:
        lifecycle = state.get("story_lifecycle", {})
        actual_status = lifecycle.get(expected_story, {}).get("status") if isinstance(lifecycle, dict) else None
        if actual_status != "Stale":
            mismatches.append(f"expected {expected_story} to be Stale after implementation feedback, got {actual_status}")
    expected_dod_item = str(feedback_key.get("expect_dod_item", ""))
    if expected_dod_item and expected_story:
        gate = state.get("story_gates", {}).get(expected_story, {})
        dod_items = gate.get("dod", {}).get("items", []) if isinstance(gate, dict) else []
        if expected_dod_item not in {item.get("key") for item in dod_items if isinstance(item, dict)}:
            mismatches.append(f"{expected_story} DoD missing {expected_dod_item}")
    report_path = ws / "07_changes" / "05_implementation_feedback" / "feedback_report.md"
    if not report_path.exists():
        mismatches.append("implementation feedback report missing")
    else:
        report_text = report_path.read_text(encoding="utf-8")
        if expected_id and expected_id not in report_text:
            mismatches.append(f"feedback report missing {expected_id}")
    graph = json.loads((ws / "06_traceability" / "traceability_graph.json").read_text(encoding="utf-8"))
    node_types = {node.get("type") for node in graph.get("nodes", []) if isinstance(node, dict)}
    edge_relations = {edge.get("relation") for edge in graph.get("edges", []) if isinstance(edge, dict)}
    if "implementation_feedback" not in node_types:
        mismatches.append("trace graph missing implementation_feedback node")
    if "feedback_from_implementation" not in edge_relations:
        mismatches.append("trace graph missing feedback_from_implementation edge")
    return {"ok": not mismatches, "mismatches": mismatches}


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
            "avg_backlog_derivation_coverage": round(
                sum(r["backlog_derivation_coverage"] for r in results) / len(results), 3
            ),
            "avg_backlog_no_invention_rate": round(
                sum(r["backlog_no_invention_rate"] for r in results) / len(results), 3
            ),
            "avg_backlog_slicing_accuracy": round(
                sum(r["backlog_slicing_accuracy"] for r in results) / len(results), 3
            ),
            "avg_backlog_anchor_validity": round(
                sum(r["backlog_anchor_validity"] for r in results) / len(results), 3
            ),
            "avg_backlog_context_distinctness": round(
                sum(r["backlog_context_distinctness"] for r in results) / len(results), 3
            ),
            "avg_story_quality_min_score": round(
                sum(r["story_quality_min_score"] for r in results) / len(results), 3
            ),
            "total_backlog_derivation_mismatches": sum(len(r["backlog_derivation_mismatches"]) for r in results),
            "total_backlog_invented_stories": sum(r["backlog_invented_story_count"] for r in results),
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
            f"backlog_stories={r['backlog_story_count']} "
            f"backlog_no_invent={r['backlog_no_invention_rate']:.2f} "
            f"backlog_slicing={r['backlog_slicing_accuracy']:.2f} "
            f"story_quality={r['story_quality_min_score']:.2f} "
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
        for mismatch in r["backlog_derivation_mismatches"]:
            print(f"         backlog derivation mismatch: {mismatch}")
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
        f"avg_specs_scaffolding={s['avg_specs_scaffolding']:.2f} (IMP-042 spec units) "
        f"avg_backlog_derivation_coverage={s['avg_backlog_derivation_coverage']:.2f} (IMP-048) "
        f"avg_backlog_no_invention={s['avg_backlog_no_invention_rate']:.2f} "
        f"avg_backlog_slicing={s['avg_backlog_slicing_accuracy']:.2f} "
        f"avg_backlog_anchors={s['avg_backlog_anchor_validity']:.2f} (IMP-061) "
        f"avg_story_quality_min_score={s['avg_story_quality_min_score']:.2f} (IMP-056)"
    )
    print(f"Report: {out}")
    return 0 if s["baseline_ok"] else 1


if __name__ == "__main__":
    sys.exit(run_all())
