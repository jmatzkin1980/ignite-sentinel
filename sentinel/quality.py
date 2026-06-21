from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .backlog.gates import evaluate_story_gates, update_story_gate_state
from .memory import ContextBroker
from .core.graph import add_edge, add_node, nodes_by_type
from .readiness_primitives import above_threshold, average_score
from .workspace import read_json, state_path, update_state, workspace_path


REQUIRED_AC_CLASSES = {"fail-to-pass", "pass-to-pass", "evidence"}
STORY_QUALITY_MIN_SCORE = 0.8
TECHNICAL_LAYER_TERMS = {
    "endpoint",
    "api",
    "table",
    "database",
    "schema",
    "repository",
    "service",
    "worker",
    "component",
    "infra",
    "infrastructure",
    "migration",
}
BEHAVIOR_TERMS = {
    "user",
    "usuario",
    "system",
    "sistema",
    "display",
    "show",
    "view",
    "submit",
    "approve",
    "reject",
    "notify",
    "block",
    "recover",
    "audit",
    "trace",
    "mostrar",
    "ver",
    "aprobar",
    "rechazar",
    "notificar",
    "bloquear",
}


def generate_quality(project_id: str) -> dict[str, object]:
    base = workspace_path(project_id)
    stories = nodes_by_type(project_id, "user_story")
    if not stories:
        raise RuntimeError("Cannot generate quality artifacts without user stories.")

    readiness_by_story = implementation_readiness_by_story(project_id)
    quality_results: dict[str, dict[str, Any]] = {}
    created = []
    for index, story in enumerate(stories, start=1):
        story_path = resolve_story_path(story["path"])
        story_text = ""
        if story_path.exists():
            story_text = story_path.read_text(encoding="utf-8")
        criteria = extract_acceptance_criteria(story_text)
        criterion_details = extract_acceptance_details(story_text)
        readiness_item = readiness_by_story.get(story["id"], {})
        quality_results[story["id"]] = evaluate_story_quality(story, story_text, criterion_details, readiness_item)
        tc_path = base / "05_quality" / f"TC-{index:03d}.md"
        tc_path.write_text(render_test_case(project_id, story["id"], criteria), encoding="utf-8")
        tc_id = add_node(project_id, "TC", "test_case", tc_path, f"Test coverage for {story['id']}", domain="quality")
        add_edge(project_id, story["id"], tc_id, "covered_by")
        ContextBroker(project_id).index_artifact(
            tc_id,
            "test_case",
            tc_path,
            tc_path.read_text(encoding="utf-8"),
            domain="quality",
            trace_ids=[story["id"], tc_id],
        )
        created.append(tc_id)

    update_state(project_id, story_quality=quality_results)
    state = read_json(state_path(project_id), {})
    lifecycle = state.get("story_lifecycle", {}) if isinstance(state.get("story_lifecycle", {}), dict) else {}
    for story in stories:
        readiness_item = dict(readiness_by_story.get(story["id"], {}))
        lifecycle_entry = lifecycle.get(story["id"], {}) if isinstance(lifecycle.get(story["id"], {}), dict) else {}
        if lifecycle_entry.get("owner"):
            readiness_item["owner"] = lifecycle_entry["owner"]
        story_path = resolve_story_path(story["path"])
        story_text = story_path.read_text(encoding="utf-8") if story_path.exists() else ""
        gate_story = story_for_gate(story, story_text, readiness_item)
        update_story_gate_state(project_id, story["id"], evaluate_story_gates(project_id, gate_story, readiness_item))

    audit_path = base / "05_quality" / "backlog_readiness_audit.md"
    audit_path.write_text(render_backlog_audit(project_id, stories, quality_results), encoding="utf-8")
    audit_id = add_node(project_id, "QA", "backlog_readiness_audit", audit_path, "Backlog readiness audit", domain="quality")
    for story in stories:
        add_edge(project_id, story["id"], audit_id, "audited_by")
    ContextBroker(project_id).index_artifact(
        audit_id,
        "backlog_readiness_audit",
        audit_path,
        audit_path.read_text(encoding="utf-8"),
        domain="quality",
        trace_ids=[audit_id, *[story["id"] for story in stories]],
    )

    update_state(project_id, phase="quality_completed")
    return {"test_cases": created, "count": len(created), "audit": str(audit_path), "story_quality": quality_results}


def resolve_story_path(path_value: str):
    path = Path(path_value)
    if path.is_absolute():
        return path
    return Path.cwd() / path


def extract_acceptance_criteria(text: str) -> list[str]:
    criteria = []
    for line in text.splitlines():
        classified = re.match(r"\|\s*(AC-\d+(?:-\d+)?)\s*\|\s*([^|]+?)\s*\|\s*(.+?)\s*\|", line)
        if classified:
            criteria.append(f"{classified.group(1)} [{classified.group(2).strip()}]: {classified.group(3).strip()}")
            continue
        legacy = re.match(r"\|\s*(AC-\d+(?:-\d+)?)\s*\|\s*(.+?)\s*\|", line)
        if legacy:
            criteria.append(f"{legacy.group(1)}: {legacy.group(2)}")
    return criteria or ["AC-001: Validate the main happy path and a recoverable failure path."]


def extract_acceptance_details(text: str) -> list[dict[str, str]]:
    criteria: list[dict[str, str]] = []
    for line in text.splitlines():
        match = re.match(r"\|\s*(AC-\d+(?:-\d+)?)\s*\|\s*([^|]+?)\s*\|\s*(.+?)\s*\|", line)
        if not match:
            continue
        classification = match.group(2).strip()
        if classification.lower() in {"classification", "---"}:
            continue
        criteria.append(
            {
                "id": match.group(1).strip(),
                "classification": classification,
                "text": match.group(3).strip(),
            }
        )
    return criteria


def implementation_readiness_by_story(project_id: str) -> dict[str, dict[str, Any]]:
    path = workspace_path(project_id) / "08_context_packs" / "implementation_readiness.json"
    pack = read_json(path, {})
    stories = pack.get("stories", []) if isinstance(pack, dict) else []
    return {
        str(item.get("story_id", "")): item
        for item in stories
        if isinstance(item, dict) and item.get("story_id")
    }


def story_for_gate(story: dict[str, Any], story_text: str, readiness_item: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": story["id"],
        "owner": readiness_item.get("owner", ""),
        "acceptance": extract_acceptance_details(story_text),
        "trace": readiness_item.get("trace", []),
        "slicing": readiness_item.get("slicing", slicing_from_story_text(story_text)),
        "readiness": readiness_item.get("readiness", ""),
        "readiness_score": readiness_item.get("readiness_score", 0.0),
    }


def slicing_from_story_text(text: str) -> str:
    match = re.search(r"\*\*Slicing Pattern:\*\*\s*(.+)", text)
    return match.group(1).strip() if match else ""


def evaluate_story_quality(
    story: dict[str, Any],
    story_text: str,
    criteria: list[dict[str, str]],
    readiness_item: dict[str, Any] | None = None,
) -> dict[str, Any]:
    readiness = readiness_item or {}
    story_id = str(story.get("id", readiness.get("story_id", "")))
    story_type = str(readiness.get("type", "") or type_from_story_text(story_text))
    slicing = str(readiness.get("slicing", "") or slicing_from_story_text(story_text)).strip()
    source_unit = str(readiness.get("source_unit", ""))
    trace = [str(item) for item in readiness.get("trace", []) if str(item).strip()]
    dependencies = [str(item) for item in readiness.get("dependencies", []) if str(item).strip()]
    enables = [str(item) for item in readiness.get("enables", []) if str(item).strip()]
    ac_classes = {str(item.get("classification", "")).strip() for item in criteria}
    lowered = f"{story.get('title', '')} {story_text}".lower()
    has_behavior = any(term in lowered for term in BEHAVIOR_TERMS)
    layer_only = any(term in lowered for term in TECHNICAL_LAYER_TERMS) and not has_behavior
    is_enabler = story_type == "cross_cutting_enabler"
    is_pending = "[pending input]" in lowered or story_type == "pending"

    checks = [
        quality_check(
            "slicing_pattern_governed",
            slicing.startswith("Cross-Cutting Enabler /")
            or slicing in {
                "Workflow Step / Happy Path",
                "Rules / Regression Slice",
                "Data / External Dependency",
                "Interface / UX State",
                "Quality Evidence / Traceability",
            },
            "Story must use a governed INVEST/SPIDR/Lawrence slicing pattern.",
        ),
        quality_check(
            "vertical_slice",
            (is_enabler and bool(enables)) or (not is_enabler and not layer_only and has_behavior),
            "Story must describe an end-to-end behavior or a concrete enabler boundary, not an isolated technical layer.",
        ),
        quality_check(
            "small_but_valuable",
            (is_enabler and bool(enables))
            or (
                not is_enabler
                and not is_pending
                and has_behavior
                and not layer_only
                and (source_unit.startswith("SPEC-U-") or any(item.startswith("SPEC-U") for item in trace))
            ),
            "Story must be small but still independently meaningful, testable and useful.",
        ),
        quality_check(
            "acceptance_criteria_coverage",
            REQUIRED_AC_CLASSES.issubset(ac_classes),
            "Acceptance criteria must cover fail-to-pass, pass-to-pass and evidence expectations.",
            observed=sorted(ac_classes),
        ),
        quality_check(
            "traceability_chain",
            bool(trace) and (is_enabler or any(item.startswith("SPEC-U") for item in trace + [source_unit])),
            "Traceability must connect the story to its SPEC-U/REQ evidence or concrete enabler evidence.",
            trace=trace,
        ),
        quality_check(
            "independent_dependencies",
            all("[PENDING" not in item for item in dependencies),
            "Dependencies must be explicit and must not hide a pending layer-only prerequisite.",
            dependencies=dependencies,
        ),
    ]
    score = average_score(1.0 if item["passed"] else 0.0 for item in checks)
    warnings = [str(item["warning"]) for item in checks if not item["passed"]]
    status = "PASS" if above_threshold(score, 1.0) else "WARN" if above_threshold(score, STORY_QUALITY_MIN_SCORE) else "FAIL"
    verdict = "ready-for-handoff" if status == "PASS" else "review-before-handoff"
    return {
        "story_id": story_id,
        "score": score,
        "status": status,
        "verdict": verdict,
        "threshold": STORY_QUALITY_MIN_SCORE,
        "checks": checks,
        "warnings": warnings,
    }


def type_from_story_text(text: str) -> str:
    match = re.search(r"\*\*Type:\*\*\s*(.+)", text)
    return match.group(1).strip() if match else ""


def quality_check(key: str, passed: bool, warning: str, **extra: Any) -> dict[str, Any]:
    item = {"key": key, "passed": bool(passed), "warning": "" if passed else warning}
    item.update(extra)
    return item


def render_test_case(project_id: str, story_id: str, criteria: list[str]) -> str:
    rows = "\n".join(f"| TC step for {criterion.split(':', 1)[0]} | {criterion} |" for criterion in criteria)
    return f"""# Test Case Set - {story_id}

- Project: `{project_id}`
- Source story: `{story_id}`
- Status: `draft`

## Coverage Matrix

| Test Step | Acceptance Criterion |
| --- | --- |
{rows}

## Automation Notes

- Prepare valid input data for the happy path.
- Prepare missing or invalid input data for validation paths.
- Separate fail-to-pass checks, pass-to-pass regression checks, and evidence checks when classifications are present.
- Assert that trace IDs remain visible in the artifact chain.
"""


def render_backlog_audit(project_id: str, stories: list[dict[str, str]], quality_results: dict[str, dict[str, Any]]) -> str:
    verdict = quality_audit_verdict(quality_results)
    rows = "\n".join(
        render_audit_row(story, quality_results.get(story["id"], {}))
        for story in stories
    )
    detail_sections = "\n\n".join(
        render_story_quality_detail(story["id"], quality_results.get(story["id"], {}))
        for story in stories
    )
    return f"""# Backlog Readiness Audit - {project_id}

This audit checks whether backlog items are ready for downstream execution using Sentinel vNext traceability and domain context.

## Verdict

`{verdict}`

## Story Census

| Story ID | Title | INVEST/SPIDR Score | Status | Review Notes |
| --- | --- | ---: | --- | --- |
{rows}

## Story Quality Checks

{detail_sections}

## Audit Checklist

- [x] Each story is evaluated against the governed INVEST/SPIDR/Lawrence slicing model.
- [x] Each story is checked for end-to-end behavior or a concrete enabler boundary.
- [x] Acceptance criteria coverage checks fail-to-pass, pass-to-pass, and evidence expectations.
- [x] Traceability checks connect story -> SPEC-U/REQ or concrete enabler evidence -> AC -> TC.
- [x] Findings are non-blocking by default and feed DoR warnings through `state.json#story_gates`.
"""


def quality_audit_verdict(quality_results: dict[str, dict[str, Any]]) -> str:
    if not quality_results:
        return "PARTIAL"
    statuses = {str(item.get("status", "")) for item in quality_results.values()}
    if statuses == {"PASS"}:
        return "PASS"
    if "FAIL" in statuses:
        return "ATTENTION"
    return "PARTIAL"


def render_audit_row(story: dict[str, str], result: dict[str, Any]) -> str:
    notes = "; ".join(result.get("warnings", [])) if result.get("warnings") else "No INVEST/SPIDR warnings."
    return (
        f"| `{story['id']}` | {story.get('title', 'User story')} | "
        f"{float(result.get('score', 0.0)):.2f} | {result.get('status', 'UNKNOWN')} | {notes} |"
    )


def render_story_quality_detail(story_id: str, result: dict[str, Any]) -> str:
    checks = result.get("checks", []) if isinstance(result, dict) else []
    rows = "\n".join(
        f"| {item.get('key', '')} | {'PASS' if item.get('passed') else 'WARN'} | {item.get('warning') or 'OK'} |"
        for item in checks
        if isinstance(item, dict)
    )
    return f"""### {story_id}

| Check | Status | Finding |
| --- | --- | --- |
{rows or '| story_quality | WARN | No quality evaluation was available. |'}"""
