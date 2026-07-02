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


def _ratio(numerator: int, denominator: int, default: float = 1.0) -> float:
    return round(numerator / denominator, 3) if denominator else default


def _f1(precision: float, recall: float) -> float:
    return round((2 * precision * recall) / (precision + recall), 3) if precision + recall else 0.0


def metric_variance(values: list[float]) -> float:
    if len(values) <= 1:
        return 0.0
    mean = sum(values) / len(values)
    return round(sum((value - mean) ** 2 for value in values) / len(values), 6)


def distractor_gap_ids(raw_distractors: object) -> set[str]:
    """Return the answer-key gap IDs used to score domain-mined distractors."""
    if not isinstance(raw_distractors, list):
        return set()
    ids: set[str] = set()
    for item in raw_distractors:
        if isinstance(item, str):
            candidate = item.strip()
        elif isinstance(item, dict):
            candidate = str(item.get("gap_id") or item.get("id") or "").strip()
        else:
            candidate = ""
        if candidate:
            ids.add(candidate)
    return ids


def discovery_gap_benchmark(
    fired: set[str],
    must_fire: set[str],
    target_fire: set[str],
    must_not_fire: set[str],
    known_false_positives: set[str],
    distractors: set[str] | None = None,
    gap_details: dict[str, dict[str, str]] | None = None,
) -> dict[str, object]:
    """Precision/recall/F1 over the answer-key-labeled discovery gap universe.

    Existing baseline gates remain unchanged: only missing must-fire gaps and new
    false positives fail the eval. These metrics are additive benchmarking
    signals for IMP-110 and intentionally count known false positives as false
    positives so quality debt stays visible without breaking the build.
    """
    expected_positive = set(must_fire) | set(target_fire)
    expected_negative = set(must_not_fire)
    distractor_set = set(distractors or set())
    true_positive = fired & expected_positive
    false_positive = fired & expected_negative
    known_false_positive = false_positive & known_false_positives
    new_false_positive = false_positive - known_false_positives
    distractor_false_positive = fired & distractor_set
    precision = _ratio(len(true_positive), len(true_positive) + len(false_positive))
    recall = _ratio(len(true_positive), len(expected_positive))
    required_recall = _ratio(len(fired & must_fire), len(must_fire))
    target_recall = _ratio(len(fired & target_fire), len(target_fire))
    distractor_false_positive_rate = _ratio(
        len(distractor_false_positive), len(distractor_set), default=0.0
    )
    by_lens: dict[str, dict[str, float | int]] = {}
    details = gap_details or {}
    for gap_id in sorted(expected_positive):
        lens = str(details.get(gap_id, {}).get("lens", "unknown"))
        item = by_lens.setdefault(lens, {"expected": 0, "detected": 0, "recall": 0.0})
        item["expected"] = int(item["expected"]) + 1
        if gap_id in fired:
            item["detected"] = int(item["detected"]) + 1
    for item in by_lens.values():
        item["recall"] = _ratio(int(item["detected"]), int(item["expected"]))
    return {
        "expected_positive_total": len(expected_positive),
        "expected_negative_total": len(expected_negative),
        "true_positive_total": len(true_positive),
        "false_positive_total": len(false_positive),
        "known_false_positive_total": len(known_false_positive),
        "new_false_positive_total": len(new_false_positive),
        "distractor_total": len(distractor_set),
        "distractor_false_positive_total": len(distractor_false_positive),
        "distractor_false_positive_rate": distractor_false_positive_rate,
        "distractor_false_positives": sorted(distractor_false_positive),
        "precision": precision,
        "recall": recall,
        "f1": _f1(precision, recall),
        "required_recall": required_recall,
        "target_recall": target_recall,
        "by_lens": by_lens,
    }


def implicit_elicitation_benchmark(
    fired: set[str],
    raw_implicit_requirements: object,
) -> dict[str, object]:
    """Score whether deepening surfaced answer-keyed implicit requirements."""
    if not isinstance(raw_implicit_requirements, list):
        raw_implicit_requirements = []

    total = 0
    detected_total = 0
    detected: list[str] = []
    missing: list[str] = []
    by_channel: dict[str, dict[str, float | int]] = {}

    for raw_item in raw_implicit_requirements:
        if not isinstance(raw_item, dict):
            continue
        ir_id = str(raw_item.get("id") or "").strip()
        expect_gap = str(raw_item.get("expect_gap") or "").strip()
        if not expect_gap:
            continue

        raw_requires = raw_item.get("requires", "unknown")
        if isinstance(raw_requires, str):
            channels = [raw_requires.strip() or "unknown"]
        elif isinstance(raw_requires, list):
            channels = [str(channel).strip() or "unknown" for channel in raw_requires]
        else:
            channels = ["unknown"]

        total += 1
        was_detected = expect_gap in fired
        if was_detected:
            detected_total += 1
            detected.append(ir_id or expect_gap)
        else:
            missing.append(ir_id or expect_gap)

        for channel in channels:
            bucket = by_channel.setdefault(
                channel,
                {"expected": 0, "detected": 0, "ratio": 0.0},
            )
            bucket["expected"] = int(bucket["expected"]) + 1
            if was_detected:
                bucket["detected"] = int(bucket["detected"]) + 1

    for bucket in by_channel.values():
        bucket["ratio"] = _ratio(int(bucket["detected"]), int(bucket["expected"]), default=0.0)

    return {
        "total": total,
        "detected_total": detected_total,
        "ratio": _ratio(detected_total, total, default=0.0),
        "detected": sorted(detected),
        "missing": sorted(missing),
        "by_channel": by_channel,
    }


def repeat_variance_for_results(repeated_results: list[list[dict]]) -> dict[str, dict[str, float]]:
    if not repeated_results:
        return {}
    fixture_names = [row["fixture"] for row in repeated_results[0]]
    variance: dict[str, dict[str, float]] = {}
    for index, fixture in enumerate(fixture_names):
        rows = [run[index] for run in repeated_results if len(run) > index and run[index]["fixture"] == fixture]
        variance[fixture] = {
            "precision": metric_variance([float(row["gap_benchmark"]["precision"]) for row in rows]),
            "recall": metric_variance([float(row["gap_benchmark"]["recall"]) for row in rows]),
            "f1": metric_variance([float(row["gap_benchmark"]["f1"]) for row in rows]),
        }
    return variance


def eval_repeat_count() -> int:
    try:
        return max(1, int(os.environ.get("SENTINEL_EVAL_REPEAT", "1")))
    except ValueError:
        return 1


def specs_scaffolding(specs_md: str) -> dict[str, object]:
    found = sorted({item for item in SPECS_SCAFFOLDING_IDS if re.search(rf"\b{re.escape(item)}\b", specs_md)})
    return {"ids": found, "count": len(found)}


def knowledge_ledger_status(ws: Path, key: dict) -> dict[str, object]:
    ledger_key = key.get("knowledge_ledger", {})
    if not ledger_key:
        return {"ok": True, "mismatches": [], "total": 0, "by_status": {}, "by_lens": {}}
    path = ws / "01_discovery" / "knowledge_state.json"
    if not path.exists():
        return {"ok": False, "mismatches": ["knowledge_state.json missing"], "total": 0, "by_status": {}, "by_lens": {}}
    payload = json.loads(path.read_text(encoding="utf-8"))
    summary = payload.get("summary", {})
    units = payload.get("units", [])
    mismatches: list[str] = []
    total = int(summary.get("total", 0) or 0)
    min_total = int(ledger_key.get("min_total", 1))
    if total < min_total:
        mismatches.append(f"expected at least {min_total} knowledge units, got {total}")
    by_status = summary.get("by_status", {})
    for status in ledger_key.get("required_statuses", []):
        if int(by_status.get(str(status), 0) or 0) <= 0:
            mismatches.append(f"expected at least one knowledge unit with status {status}")
    by_lens = summary.get("by_lens", {})
    for lens in ledger_key.get("required_lenses", []):
        if int(by_lens.get(str(lens), 0) or 0) <= 0:
            mismatches.append(f"expected at least one knowledge unit for lens {lens}")
    if ledger_key.get("require_evidence_or_pending", True):
        for unit in units:
            evidence = unit.get("evidence", {}) if isinstance(unit, dict) else {}
            has_pending = evidence.get("note") == "[PENDING INPUT]"
            has_trace_quote = bool(evidence.get("trace_id") and evidence.get("quote"))
            if not (has_pending or has_trace_quote):
                mismatches.append(f"{unit.get('id', 'unknown')} missing evidence trace/quote or [PENDING INPUT]")
                break
    return {
        "ok": not mismatches,
        "mismatches": mismatches,
        "total": total,
        "by_status": by_status,
        "by_lens": by_lens,
    }


def assumption_status(ws: Path, key: dict) -> dict[str, object]:
    assume_key = key.get("assume", {})
    expected = assume_key.get("expected_assumptions", {}) if isinstance(assume_key, dict) else {}
    if not expected:
        return {"ok": True, "mismatches": []}
    assumptions_path = ws / "01_discovery" / "assumptions.md"
    ledger_path = ws / "01_discovery" / "knowledge_state.json"
    prd_path = ws / "03_specs" / "prd.md"
    brief_path = ws / "02_requirements" / "project-brief.md"
    mismatches: list[str] = []
    assumptions_text = assumptions_path.read_text(encoding="utf-8") if assumptions_path.exists() else ""
    ledger = json.loads(ledger_path.read_text(encoding="utf-8")) if ledger_path.exists() else {"units": []}
    prd_text = prd_path.read_text(encoding="utf-8") if prd_path.exists() else ""
    brief_text = brief_path.read_text(encoding="utf-8") if brief_path.exists() else ""
    for assumption_id, expected_fields in expected.items():
        if assumption_id not in assumptions_text:
            mismatches.append(f"assumptions.md missing {assumption_id}")
        unit = next((u for u in ledger.get("units", []) if assumption_id in json.dumps(u, ensure_ascii=False)), None)
        if not unit:
            mismatches.append(f"knowledge_state missing {assumption_id}")
        elif unit.get("status") != "ASSUMED":
            mismatches.append(f"{assumption_id} expected ASSUMED ledger unit, got {unit.get('status')}")
        for field, expected_value in expected_fields.items():
            if str(expected_value) not in assumptions_text:
                mismatches.append(f"{assumption_id} missing {field}={expected_value} in assumptions.md")
        if assume_key.get("expect_in_brief") and assumption_id not in brief_text:
            mismatches.append(f"project-brief.md missing {assumption_id}")
        if assume_key.get("expect_in_prd") and assumption_id not in prd_text:
            mismatches.append(f"prd.md missing {assumption_id}")
    return {"ok": not mismatches, "mismatches": mismatches}


def development_readiness_status(ws: Path, key: dict) -> dict[str, object]:
    readiness_key = key.get("development_readiness", {})
    if not readiness_key:
        return {"ok": True, "mismatches": []}
    path = ws / "01_discovery" / "development_readiness.json"
    if not path.exists():
        return {"ok": False, "mismatches": ["development_readiness.json missing"]}
    payload = json.loads(path.read_text(encoding="utf-8"))
    summary = payload.get("summary", {}) if isinstance(payload, dict) else {}
    matrix = payload.get("matrix", []) if isinstance(payload, dict) else []
    mismatches: list[str] = []
    min_areas = int(readiness_key.get("min_areas", 16))
    if int(summary.get("areas_total", 0) or 0) < min_areas:
        mismatches.append(f"expected at least {min_areas} readiness areas")
    by_status = summary.get("by_status", {}) if isinstance(summary.get("by_status"), dict) else {}
    for status in readiness_key.get("required_statuses", []):
        if int(by_status.get(str(status), 0) or 0) <= 0:
            mismatches.append(f"expected at least one readiness cell with status {status}")
    expected_verdict = readiness_key.get("expected_verdict")
    verdict = summary.get("crystallization_gate", {}) if isinstance(summary.get("crystallization_gate"), dict) else {}
    if expected_verdict and verdict.get("state") != expected_verdict:
        mismatches.append(f"expected verdict {expected_verdict}, got {verdict.get('state')}")
    expected_cells = readiness_key.get("expected_area_statuses", {})
    for area_name, lenses in expected_cells.items():
        area = next((row for row in matrix if row.get("area") == area_name), None)
        if not area:
            mismatches.append(f"readiness matrix missing area {area_name}")
            continue
        cells = {cell.get("lens"): cell for cell in area.get("lenses", []) if isinstance(cell, dict)}
        for lens, expected_status in lenses.items():
            actual = cells.get(lens, {}).get("status")
            if actual != expected_status:
                mismatches.append(f"{area_name}/{lens} expected {expected_status}, got {actual}")
    return {"ok": not mismatches, "mismatches": mismatches}


def run_eval_command(args: list[str]) -> dict[str, object]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        exit_code = main(args)
    return {"exit_code": exit_code, "stdout": stdout.getvalue(), "stderr": stderr.getvalue()}


def fixture_command_args(raw_args: list[str], project_id: str, fixture_dir: Path) -> list[str]:
    args: list[str] = []
    for value in raw_args:
        text = str(value).replace("{project_id}", project_id)
        if text.startswith("fixture:"):
            args.append(str(fixture_dir / text.split(":", 1)[1]))
        else:
            args.append(text)
    return args


def snapshot_workspace_files(ws: Path, relative_paths: list[str]) -> dict[str, str | None]:
    snapshots: dict[str, str | None] = {}
    for relative in relative_paths:
        path = ws / relative
        snapshots[relative] = path.read_text(encoding="utf-8") if path.exists() else None
    return snapshots


def rejection_scenarios_status(ws: Path, project_id: str, fixture_dir: Path, key: dict) -> dict[str, object]:
    scenarios = key.get("rejection_scenarios", [])
    if not scenarios:
        return {"ok": True, "mismatches": []}
    mismatches: list[str] = []
    for scenario in scenarios:
        name = str(scenario.get("name", "unnamed rejection scenario"))
        unchanged_paths = [str(item) for item in scenario.get("unchanged_paths", [])]
        before = snapshot_workspace_files(ws, unchanged_paths)
        command = fixture_command_args([str(item) for item in scenario.get("command", [])], project_id, fixture_dir)
        if not command:
            mismatches.append(f"{name}: missing command")
            continue
        result = run_eval_command(command)
        if int(result["exit_code"]) == 0:
            mismatches.append(f"{name}: expected rejection, got exit 0")
        combined_output = f"{result['stdout']}\n{result['stderr']}"
        for expected_text in scenario.get("output_contains", []):
            if str(expected_text) not in combined_output:
                mismatches.append(f"{name}: output missing {expected_text!r}")
        after = snapshot_workspace_files(ws, unchanged_paths)
        for relative, before_text in before.items():
            if after.get(relative) != before_text:
                mismatches.append(f"{name}: {relative} mutated after rejected command")
        for relative in scenario.get("forbidden_text_paths", []):
            text = (ws / str(relative)).read_text(encoding="utf-8") if (ws / str(relative)).exists() else ""
            for forbidden in scenario.get("forbidden_text", []):
                if str(forbidden) in text:
                    mismatches.append(f"{name}: forbidden text {forbidden!r} found in {relative}")
    return {"ok": not mismatches, "mismatches": mismatches}


def lifecycle_guard_status(ws: Path, project_id: str, fixture_dir: Path, key: dict) -> dict[str, object]:
    guard = key.get("lifecycle_guards", {})
    if not guard:
        return {"ok": True, "mismatches": []}
    mismatches: list[str] = []
    state = json.loads((ws / "state.json").read_text(encoding="utf-8"))
    for field, expected in guard.get("expected_state", {}).items():
        actual = state.get(field)
        if actual != expected:
            mismatches.append(f"state.{field} expected {expected!r}, got {actual!r}")
    for relative in guard.get("expected_missing_artifacts", []):
        if (ws / str(relative)).exists():
            mismatches.append(f"expected artifact to be absent: {relative}")
    for command_guard in guard.get("blocked_commands", []):
        name = str(command_guard.get("name", "blocked command"))
        command = fixture_command_args([str(item) for item in command_guard.get("command", [])], project_id, fixture_dir)
        if not command:
            mismatches.append(f"{name}: missing command")
            continue
        result = run_eval_command(command)
        if int(result["exit_code"]) == 0:
            mismatches.append(f"{name}: expected non-zero exit, got 0")
        combined_output = f"{result['stdout']}\n{result['stderr']}"
        for expected_text in command_guard.get("output_contains", []):
            if str(expected_text) not in combined_output:
                mismatches.append(f"{name}: output missing {expected_text!r}")
    return {"ok": not mismatches, "mismatches": mismatches}


def run_fixture(
    fixture_dir: Path,
    apply_annotation: bool = False,
    apply_scrutiny: bool = False,
    apply_assumptions: bool = False,
) -> dict:
    key = json.loads((fixture_dir / "answer_key.json").read_text(encoding="utf-8"))
    requirement = fixture_dir / "requirement.md"
    annotation = fixture_dir / "annotation.json"
    scrutiny = fixture_dir / "scrutiny.json"
    assumptions = fixture_dir / "assumptions.json"
    gap_responses = fixture_dir / "gap_responses.md"
    gap_response_rounds = fixture_dir / "gap_response_rounds"
    project_id = "EVAL" + re.sub(r"[^A-Z]", "", fixture_dir.name.upper())[:12]
    lifecycle_key = key.get("lifecycle_guards", {})
    skip_downstream = bool(lifecycle_key.get("skip_downstream_generation", False))

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
                ws = Path(temp) / "workspaces" / project_id
                rejection_scenarios = rejection_scenarios_status(ws, project_id, fixture_dir, key)
                # IMP-021: optionally apply the agent's stored semantic analysis
                # so target_recall reflects the agentic pass, not the lexical one.
                if apply_annotation and annotation.exists():
                    assert main(["annotate", project_id, "--source", str(annotation)]) == 0, (
                        f"annotate failed for {fixture_dir.name}"
                    )
                if apply_scrutiny and scrutiny.exists():
                    assert main(["scrutinize", project_id, "--source", str(scrutiny)]) == 0, (
                        f"scrutinize failed for {fixture_dir.name}"
                    )
                if apply_assumptions and assumptions.exists():
                    assert main(["assume", project_id, "--source", str(assumptions)]) == 0, (
                        f"assume failed for {fixture_dir.name}"
                    )
                if not apply_annotation and not apply_scrutiny:
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
                if not apply_annotation and not apply_scrutiny and not skip_downstream:
                    assert main(["specs", project_id]) == 0, f"specs failed for {fixture_dir.name}"
                    backlog_command = ["backlog", project_id]
                    if key.get("task_seeds", {}).get("with_task_seeds"):
                        backlog_command.append("--with-task-seeds")
                    assert main(backlog_command) == 0, f"backlog failed for {fixture_dir.name}"
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
            if apply_annotation or apply_scrutiny or skip_downstream:
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
            task_seeds = task_seeds_eval(ws, key) if not (apply_annotation or apply_scrutiny) else {"ok": True, "mismatches": []}
            knowledge_ledger = knowledge_ledger_status(ws, key)
            assumption_eval = assumption_status(ws, key) if apply_assumptions else {"ok": True, "mismatches": []}
            development_readiness = (
                development_readiness_status(ws, key)
                if apply_assumptions
                else {"ok": True, "mismatches": []}
            )
            implementation_feedback = (
                {"ok": True, "mismatches": []}
                if apply_annotation or apply_scrutiny
                else implementation_feedback_eval(ws, key)
            )
            metabolism_eval = (
                metabolism_status(ws, key, project_id, fixture_dir)
                if apply_assumptions
                else {"ok": True, "mismatches": []}
            )
            lifecycle_guard = lifecycle_guard_status(ws, project_id, fixture_dir, key)
        finally:
            os.chdir(old_cwd)

    must_fire = set(key["must_fire"])
    must_not_fire = set(key["must_not_fire"])
    known_fp = set(key.get("known_false_positives", []))
    target = set(key.get("target_fire", []))
    raw_distractors = key.get("distractors", [])
    distractors = distractor_gap_ids(raw_distractors)

    missing = sorted(must_fire - fired)
    false_positives = sorted(fired & must_not_fire)
    new_false_positives = sorted((fired & must_not_fire) - known_fp)
    fixed_known_fp = sorted(known_fp - fired)
    target_detected = sorted(fired & target)
    gap_benchmark = discovery_gap_benchmark(
        fired,
        must_fire,
        target,
        must_not_fire,
        known_fp,
        distractors,
        gap_details,
    )
    implicit_elicitation = implicit_elicitation_benchmark(
        fired,
        key.get("implicit_requirements", []),
    )

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
    backlog_mismatches.extend(task_seeds["mismatches"])
    backlog_mismatches.extend(knowledge_ledger["mismatches"])
    backlog_mismatches.extend(assumption_eval["mismatches"])
    backlog_mismatches.extend(development_readiness["mismatches"])
    backlog_mismatches.extend(implementation_feedback["mismatches"])
    backlog_mismatches.extend(metabolism_eval["mismatches"])
    backlog_mismatches.extend(rejection_scenarios["mismatches"])
    backlog_mismatches.extend(lifecycle_guard["mismatches"])

    expected_language = key.get("expected_language", key.get("language"))
    language_detected = state.get("project_language", "unknown")
    language_mismatch = language_detected != expected_language

    expected_gap_details = dict(key.get("expected_gap_details", {}))
    if apply_annotation:
        expected_gap_details.update(key.get("annotate", {}).get("expected_gap_details", {}))
    if apply_scrutiny:
        expected_gap_details.update(key.get("scrutinize", {}).get("expected_gap_details", {}))
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
        "gap_benchmark": gap_benchmark,
        "gap_precision": gap_benchmark["precision"],
        "gap_recall": gap_benchmark["recall"],
        "gap_f1": gap_benchmark["f1"],
        "implicit_elicitation": implicit_elicitation,
        "elicitation_ratio": implicit_elicitation["ratio"],
        "implicit_elicitation_ratio": implicit_elicitation["ratio"],
        "distractor_total": len(distractors),
        "distractors": raw_distractors,
        "distractor_false_positives": gap_benchmark["distractor_false_positives"],
        "distractor_false_positive_rate": gap_benchmark["distractor_false_positive_rate"],
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
        "task_seeds_ok": task_seeds["ok"],
        "task_seeds_mismatches": task_seeds["mismatches"],
        "knowledge_ledger_ok": knowledge_ledger["ok"],
        "knowledge_ledger_mismatches": knowledge_ledger["mismatches"],
        "knowledge_ledger_total": knowledge_ledger["total"],
        "knowledge_ledger_by_status": knowledge_ledger["by_status"],
        "knowledge_ledger_by_lens": knowledge_ledger["by_lens"],
        "assumption_ok": assumption_eval["ok"],
        "assumption_mismatches": assumption_eval["mismatches"],
        "development_readiness_ok": development_readiness["ok"],
        "development_readiness_mismatches": development_readiness["mismatches"],
        "metabolism_ok": metabolism_eval["ok"],
        "metabolism_mismatches": metabolism_eval["mismatches"],
        "implementation_feedback_ok": implementation_feedback["ok"],
        "implementation_feedback_mismatches": implementation_feedback["mismatches"],
        "rejection_scenarios_ok": rejection_scenarios["ok"],
        "rejection_scenarios_mismatches": rejection_scenarios["mismatches"],
        "lifecycle_guards_ok": lifecycle_guard["ok"],
        "lifecycle_guards_mismatches": lifecycle_guard["mismatches"],
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


def task_seeds_eval(ws: Path, key: dict) -> dict[str, object]:
    seeds_key = key.get("task_seeds", {})
    if not seeds_key:
        return {"ok": True, "mismatches": []}
    mismatches: list[str] = []
    story_id = str(seeds_key.get("expected_story", "US-001"))
    readiness = json.loads((ws / "08_context_packs" / "implementation_readiness.json").read_text(encoding="utf-8"))
    stories = {story.get("story_id"): story for story in readiness.get("stories", []) if isinstance(story, dict)}
    contract = stories.get(story_id, {}).get("task_seed_contract")
    if not isinstance(contract, dict) or not contract.get("emitted"):
        mismatches.append(f"expected task_seed_contract for {story_id}")
        return {"ok": False, "mismatches": mismatches}
    seeds = contract.get("seeds", [])
    expected_min = int(seeds_key.get("expected_min_seeds", 1))
    if not isinstance(seeds, list) or len(seeds) < expected_min:
        mismatches.append(f"expected at least {expected_min} task seeds for {story_id}, got {len(seeds) if isinstance(seeds, list) else 0}")
        seeds = []
    expected_ac = str(seeds_key.get("expected_ac", ""))
    if expected_ac and not any(expected_ac in seed.get("acceptance_criteria", []) for seed in seeds if isinstance(seed, dict)):
        mismatches.append(f"expected task seed AC trace {expected_ac}")
    if seeds_key.get("expect_boundary_note") and "does not execute" not in str(contract.get("scope_boundary", "")):
        mismatches.append("task seed contract missing boundary note")
    story_path = ws / "04_backlog" / f"{story_id}.md"
    if not story_path.exists():
        mismatches.append(f"{story_id}.md missing for task seeds")
    else:
        text = story_path.read_text(encoding="utf-8")
        for expected_text in seeds_key.get("must_contain", []):
            if str(expected_text) not in text:
                mismatches.append(f"{story_id}.md task seed section missing expected text: {expected_text}")
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


def metabolism_status(ws: Path, key: dict, project_id: str, fixture_dir: Path) -> dict[str, object]:
    metabolism_key = key.get("metabolism", {})
    if not metabolism_key:
        return {"ok": True, "mismatches": []}
    mismatches: list[str] = []
    source = fixture_dir / str(metabolism_key.get("sync_source", ""))
    if not source.exists():
        return {"ok": False, "mismatches": [f"metabolism sync source missing: {source.name}"]}
    with contextlib.redirect_stdout(io.StringIO()):
        if main(["sync", project_id, "--source", str(source), "--note", "eval knowledge metabolism"]) != 0:
            return {"ok": False, "mismatches": [f"sync failed for metabolism source {source.name}"]}
    state = json.loads((ws / "state.json").read_text(encoding="utf-8"))
    payload = state.get("last_knowledge_metabolism", {})
    expected_invalidated = sorted(str(item) for item in metabolism_key.get("expected_invalidated_assumptions", []))
    actual_invalidated = sorted(str(item) for item in payload.get("invalidated_assumptions", []))
    for item in expected_invalidated:
        if item not in actual_invalidated:
            mismatches.append(f"metabolism missing invalidated assumption {item}")
    expected_stale = str(metabolism_key.get("expected_stale_artifact_contains", ""))
    stale_artifacts = "\n".join(str(item) for item in payload.get("downstream_stale_artifacts", []))
    if expected_stale and expected_stale not in stale_artifacts:
        mismatches.append(f"metabolism stale artifacts missing {expected_stale}")
    if metabolism_key.get("require_impacted_units") and not payload.get("impacted_knowledge_units"):
        mismatches.append("metabolism did not report impacted knowledge units")

    ledger = json.loads((ws / "01_discovery" / "knowledge_state.json").read_text(encoding="utf-8"))
    expected_statuses = metabolism_key.get("expected_unit_status_by_assumption", {})
    for assumption_id, expected_status in expected_statuses.items():
        matched = [
            unit
            for unit in ledger.get("units", [])
            if any(
                link.get("type") == "assumption" and link.get("target") == assumption_id
                for link in unit.get("links", [])
            )
        ]
        if not matched:
            mismatches.append(f"ledger missing assumption unit {assumption_id}")
        elif matched[0].get("status") != expected_status:
            mismatches.append(f"{assumption_id} expected {expected_status}, got {matched[0].get('status')}")

    reports = sorted((ws / "07_changes").rglob("*impact_report.md"))
    report_text = "\n".join(path.read_text(encoding="utf-8") for path in reports)
    for term in metabolism_key.get("expected_impact_terms", []):
        if str(term) not in report_text:
            mismatches.append(f"impact report missing {term}")
    if metabolism_key.get("expect_health_dirty"):
        with contextlib.redirect_stdout(io.StringIO()):
            main(["health", project_id])
        health = json.loads((ws / "06_traceability" / "health_report.json").read_text(encoding="utf-8"))
        if health.get("verdict") != "DIRTY":
            mismatches.append(f"expected health DIRTY after metabolism, got {health.get('verdict')}")
        if not any("Knowledge changed after downstream artifacts" in item for item in health.get("findings", [])):
            mismatches.append("health report missing knowledge staleness finding")
    return {"ok": not mismatches, "mismatches": mismatches}


def run_all() -> int:
    fixture_dirs = sorted(d for d in FIXTURES.iterdir() if (d / "answer_key.json").exists())
    if not fixture_dirs:
        print("No eval fixtures found under tests/fixtures/evals/")
        return 1
    repeat_count = eval_repeat_count()
    repeated_results = [[run_fixture(d) for d in fixture_dirs] for _ in range(repeat_count)]
    results = repeated_results[0]
    repeat_variance = repeat_variance_for_results(repeated_results)
    for row in results:
        row["repeat_variance"] = repeat_variance.get(row["fixture"], {"precision": 0.0, "recall": 0.0, "f1": 0.0})

    # IMP-021 progress: re-run fixtures that carry an agent annotation through
    # the /annotate pass. Additive metric; the lexical baseline above is
    # untouched so prior baselines never regress.
    annotated_results = [
        run_fixture(d, apply_annotation=True) if (d / "annotation.json").exists() else r
        for d, r in zip(fixture_dirs, results)
    ]
    annotated_fixtures = sum(1 for d in fixture_dirs if (d / "annotation.json").exists())
    scrutinized_results = [
        run_fixture(d, apply_scrutiny=True)
        for d in fixture_dirs
        if (d / "scrutiny.json").exists()
    ]
    scrutinized_fixtures = sum(1 for d in fixture_dirs if (d / "scrutiny.json").exists())
    assumed_results = [
        run_fixture(d, apply_assumptions=True)
        for d in fixture_dirs
        if (d / "assumptions.json").exists()
    ]
    assumed_fixtures = sum(1 for d in fixture_dirs if (d / "assumptions.json").exists())
    implicit_results = [r for r in results if r["implicit_elicitation"]["total"]]
    implicit_annotated_results = [
        r for r in annotated_results if r["implicit_elicitation"]["total"]
    ]
    implicit_ratio = (
        round(sum(r["implicit_elicitation_ratio"] for r in implicit_results) / len(implicit_results), 3)
        if implicit_results
        else 0.0
    )
    implicit_ratio_with_annotations = (
        round(
            sum(r["implicit_elicitation_ratio"] for r in implicit_annotated_results)
            / len(implicit_annotated_results),
            3,
        )
        if implicit_annotated_results
        else 0.0
    )

    report = {
        "date": date.today().isoformat(),
        "fixtures": results,
        "summary": {
            "fixtures_run": len(results),
            "baseline_ok": all(r["baseline_ok"] for r in results),
            "avg_recall_must_fire": round(sum(r["recall_must_fire"] for r in results) / len(results), 3),
            "avg_gap_precision": round(sum(float(r["gap_benchmark"]["precision"]) for r in results) / len(results), 3),
            "avg_gap_recall": round(sum(float(r["gap_benchmark"]["recall"]) for r in results) / len(results), 3),
            "avg_gap_f1": round(sum(float(r["gap_benchmark"]["f1"]) for r in results) / len(results), 3),
            "repeat_count": repeat_count,
            "avg_gap_precision_variance": round(
                sum(row["repeat_variance"]["precision"] for row in results) / len(results), 6
            ),
            "avg_gap_recall_variance": round(
                sum(row["repeat_variance"]["recall"] for row in results) / len(results), 6
            ),
            "avg_gap_f1_variance": round(
                sum(row["repeat_variance"]["f1"] for row in results) / len(results), 6
            ),
            "fixtures_with_distractors": sum(1 for r in results if r["distractor_total"]),
            "avg_distractor_false_positive_rate": round(
                sum(float(r["distractor_false_positive_rate"]) for r in results) / len(results), 3
            ),
            "total_distractor_false_positives": sum(
                len(r["distractor_false_positives"]) for r in results
            ),
            "avg_target_recall": round(sum(r["target_recall"] for r in results) / len(results), 3),
            "avg_target_recall_with_annotations": round(
                sum(r["target_recall"] for r in annotated_results) / len(annotated_results), 3
            ),
            "implicit_elicitation_fixtures": len(implicit_results),
            "avg_implicit_elicitation_ratio": implicit_ratio,
            "avg_implicit_elicitation_ratio_with_annotations": implicit_ratio_with_annotations,
            "implicit_elicitation_delta": round(
                implicit_ratio_with_annotations - implicit_ratio,
                3,
            ),
            "annotated_fixtures": annotated_fixtures,
            "scrutinized_fixtures": scrutinized_fixtures,
            "scrutiny_ok": all(not r["gap_detail_mismatches"] for r in scrutinized_results),
            "assumed_fixtures": assumed_fixtures,
            "assumption_ok": all(r["assumption_ok"] for r in assumed_results),
            "development_readiness_ok": all(r["development_readiness_ok"] for r in assumed_results),
            "metabolism_ok": all(r["metabolism_ok"] for r in assumed_results),
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
            "avg_knowledge_ledger_units": round(
                sum(r["knowledge_ledger_total"] for r in results) / len(results), 3
            ),
            "total_knowledge_ledger_mismatches": sum(len(r["knowledge_ledger_mismatches"]) for r in results),
            "total_backlog_derivation_mismatches": sum(len(r["backlog_derivation_mismatches"]) for r in results),
            "total_backlog_invented_stories": sum(r["backlog_invented_story_count"] for r in results),
            "total_new_false_positives": sum(len(r["new_false_positives"]) for r in results),
            "total_fixed_known_false_positives": sum(len(r["fixed_known_false_positives"]) for r in results),
            "total_language_mismatches": sum(1 for r in results if r["language_mismatch"]),
            "total_gap_detail_mismatches": sum(len(r["gap_detail_mismatches"]) for r in results),
            "total_assumption_mismatches": sum(len(r.get("assumption_mismatches", [])) for r in assumed_results),
            "total_development_readiness_mismatches": sum(
                len(r.get("development_readiness_mismatches", [])) for r in assumed_results
            ),
            "total_rejection_scenario_mismatches": sum(
                len(r.get("rejection_scenarios_mismatches", [])) for r in results
            ),
            "total_lifecycle_guard_mismatches": sum(
                len(r.get("lifecycle_guards_mismatches", [])) for r in results
            ),
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
            f"gap_p/r/f1={float(r['gap_benchmark']['precision']):.2f}/"
            f"{float(r['gap_benchmark']['recall']):.2f}/"
            f"{float(r['gap_benchmark']['f1']):.2f} "
            f"target={len(r['target_fire_detected'])}/{r['target_fire_total']} "
            f"implicit={r['implicit_elicitation']['detected_total']}/"
            f"{r['implicit_elicitation']['total']}:"
            f"{float(r['implicit_elicitation_ratio']):.2f} "
            f"brief={len(r['brief_target_populated'])}/{len(r['brief_target_sections'])} "
            f"prd={len(r['prd_target_populated'])}/{len(r['prd_target_sections'])} "
            f"spec_scaffold={r['specs_scaffolding_count']} "
            f"backlog_stories={r['backlog_story_count']} "
            f"backlog_no_invent={r['backlog_no_invention_rate']:.2f} "
            f"backlog_slicing={r['backlog_slicing_accuracy']:.2f} "
                f"story_quality={r['story_quality_min_score']:.2f} "
                f"knowledge_units={r['knowledge_ledger_total']} "
                f"distractor_fp={len(r['distractor_false_positives'])}/{r['distractor_total']} "
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
        for mismatch in r["knowledge_ledger_mismatches"]:
            print(f"         knowledge ledger mismatch: {mismatch}")
        for mismatch in r["development_readiness_mismatches"]:
            print(f"         development readiness mismatch: {mismatch}")
        for mismatch in r["rejection_scenarios_mismatches"]:
            print(f"         rejection scenario mismatch: {mismatch}")
        for mismatch in r["lifecycle_guards_mismatches"]:
            print(f"         lifecycle guard mismatch: {mismatch}")
        expected_pending = set(r["brief_expected_pending_sections"])
        matched_pending = set(r["brief_expected_pending_matched"])
        for section in sorted(expected_pending - matched_pending):
            print(f"         brief section expected pending but populated: {section}")
    s = report["summary"]
    print(
        f"Summary: baseline_ok={s['baseline_ok']} avg_recall={s['avg_recall_must_fire']:.2f} "
        f"avg_gap_p/r/f1={s['avg_gap_precision']:.2f}/{s['avg_gap_recall']:.2f}/{s['avg_gap_f1']:.2f} "
        f"repeat={s['repeat_count']} "
            f"var_p/r/f1={s['avg_gap_precision_variance']:.6f}/"
            f"{s['avg_gap_recall_variance']:.6f}/"
            f"{s['avg_gap_f1_variance']:.6f} "
            f"distractor_fp={s['total_distractor_false_positives']}/"
            f"{s['fixtures_with_distractors']}fx "
        f"avg_target_recall={s['avg_target_recall']:.2f} lexical / "
        f"{s['avg_target_recall_with_annotations']:.2f} with /annotate "
        f"({s['annotated_fixtures']} annotated fixtures, IMP-021) "
        f"implicit_elicitation={s['avg_implicit_elicitation_ratio']:.2f} lexical / "
        f"{s['avg_implicit_elicitation_ratio_with_annotations']:.2f} with /annotate "
        f"delta={s['implicit_elicitation_delta']:.2f} "
        f"({s['implicit_elicitation_fixtures']} fixtures, IMP-156) "
        f"scrutiny_ok={s['scrutiny_ok']} ({s['scrutinized_fixtures']} scrutinized fixtures, IMP-066) "
        f"assumption_ok={s['assumption_ok']} ({s['assumed_fixtures']} assumed fixtures, IMP-067) "
        f"development_readiness_ok={s['development_readiness_ok']} (IMP-068) "
        f"metabolism_ok={s['metabolism_ok']} (IMP-069) "
        f"avg_brief_target_coverage={s['avg_brief_target_coverage']:.2f} (IMP-024 progress) "
        f"avg_brief_pending_coverage={s['avg_brief_expected_pending_coverage']:.2f} "
        f"avg_prd_target_coverage={s['avg_prd_target_coverage']:.2f} (IMP-039 compiled PRD) "
        f"ears_eligible_not_normalized={s['total_ears_eligible_not_normalized']} "
        f"avg_specs_scaffolding={s['avg_specs_scaffolding']:.2f} (IMP-042 spec units) "
        f"avg_backlog_derivation_coverage={s['avg_backlog_derivation_coverage']:.2f} (IMP-048) "
        f"avg_backlog_no_invention={s['avg_backlog_no_invention_rate']:.2f} "
        f"avg_backlog_slicing={s['avg_backlog_slicing_accuracy']:.2f} "
        f"avg_backlog_anchors={s['avg_backlog_anchor_validity']:.2f} (IMP-061) "
        f"avg_story_quality_min_score={s['avg_story_quality_min_score']:.2f} (IMP-056) "
        f"avg_knowledge_units={s['avg_knowledge_ledger_units']:.2f} (IMP-065) "
        f"rejection_mismatches={s['total_rejection_scenario_mismatches']} "
        f"lifecycle_guard_mismatches={s['total_lifecycle_guard_mismatches']}"
    )
    print(f"Report: {out}")
    return 0 if s["baseline_ok"] else 1


if __name__ == "__main__":
    sys.exit(run_all())
