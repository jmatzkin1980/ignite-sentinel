from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from .core.markdown import parse_table_rows
from .memory import ContextBroker
from .traceability import add_edge, add_node, upsert_node
from .workspace import read_json, state_path, update_state, utc_now, workspace_path, write_json


class ImplementationFeedbackError(RuntimeError):
    """Raised when implementation feedback cannot be metabolized."""


VALID_FINDING_TYPES = {"new-dependency", "gap", "ac-challenge", "surface-not-covered"}
VALID_STATUSES = {"open", "resolved"}


def apply_implementation_feedback(project_id: str, source: Path) -> dict[str, object]:
    base = workspace_path(project_id)
    if not (base / "04_backlog").exists():
        raise ImplementationFeedbackError("Cannot process implementation feedback before /backlog creates 04_backlog/.")
    if not source.exists():
        raise ImplementationFeedbackError(f"Implementation feedback source not found: {source}")

    data = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ImplementationFeedbackError("Implementation feedback source must be a JSON object with a findings array.")
    story_index = load_story_index(base)
    accepted, rejected = validate_findings(data, story_index)

    feedback_dir = base / "07_changes" / "05_implementation_feedback"
    feedback_dir.mkdir(parents=True, exist_ok=True)
    archived = unique_path(feedback_dir / source.name)
    shutil.copyfile(source, archived)
    report_path = write_feedback_report(project_id, accepted, rejected, archived)
    write_feedback_gaps(project_id, accepted)

    run_id = add_node(
        project_id,
        "CHG",
        "implementation_feedback",
        report_path,
        f"Implementation feedback from {source.name}",
        status="open" if any(item["status"] == "open" for item in accepted) else "resolved",
        domain="delivery",
    )
    for finding in accepted:
        finding["trace_id"] = run_id
        add_edge(project_id, run_id, finding["story_id"], "feedback_from_implementation")
        if finding.get("acceptance_criteria"):
            add_edge(project_id, run_id, str(finding["acceptance_criteria"]), "challenges_acceptance_criteria")
        if finding.get("gap_id"):
            upsert_node(
                project_id,
                str(finding["gap_id"]),
                "implementation_feedback_gap",
                report_path,
                f"Implementation feedback gap for {finding['story_id']}",
                status=finding["status"],
                domain="delivery",
            )
            add_edge(project_id, run_id, str(finding["gap_id"]), "opens_feedback_gap")

    stale_results = []
    for finding in accepted:
        if finding.get("mark_stale"):
            from .backlog_hooks import mark_stale_stories_for_spec_units

            stale_results.append(
                mark_stale_stories_for_spec_units(
                    project_id,
                    [str(unit) for unit in finding.get("source_units", [])],
                    f"Implementation feedback {finding['id']} requires backlog review.",
                    run_id,
                )
            )

    persist_feedback_state(project_id, accepted, run_id, archived, report_path)
    refresh_feedback_story_gates(project_id, accepted)
    ContextBroker(project_id).index_artifact(
        run_id,
        "implementation_feedback",
        report_path,
        report_path.read_text(encoding="utf-8"),
        domain="delivery",
        trace_ids=[run_id, *[item["story_id"] for item in accepted]],
    )

    if not accepted:
        raise ImplementationFeedbackError(
            "No implementation feedback findings were accepted. See 07_changes/05_implementation_feedback/feedback_report.md."
        )
    return {
        "feedback_id": run_id,
        "accepted": [item["id"] for item in accepted],
        "rejected": rejected,
        "staleness": stale_results,
        "source": str(archived.as_posix()),
        "report": str(report_path.as_posix()),
    }


def validate_findings(data: dict[str, Any], story_index: dict[str, dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    findings = data.get("findings")
    if not isinstance(findings, list) or not findings:
        raise ImplementationFeedbackError("Implementation feedback source must contain a non-empty findings array.")
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, str]] = []
    for index, finding in enumerate(findings, start=1):
        finding_id = str(finding.get("id") or f"IFB-{index:03d}") if isinstance(finding, dict) else f"IFB-{index:03d}"
        reason = validate_finding_shape(finding, story_index)
        if reason:
            rejected.append({"id": finding_id, "reason": reason})
            continue
        accepted.append(normalize_finding(finding, finding_id, index, story_index))
    return accepted, rejected


def validate_finding_shape(finding: Any, story_index: dict[str, dict[str, Any]]) -> str:
    if not isinstance(finding, dict):
        return "finding must be an object"
    finding_type = str(finding.get("type", "")).strip()
    if finding_type not in VALID_FINDING_TYPES:
        return f"type must be one of {', '.join(sorted(VALID_FINDING_TYPES))}"
    story_id = str(finding.get("story", finding.get("story_id", ""))).strip()
    if story_id not in story_index:
        return f"story does not exist: {story_id}"
    ac_id = str(finding.get("acceptance_criteria", "")).strip()
    if ac_id and ac_id not in story_index[story_id]["acceptance_criteria"]:
        return f"acceptance criteria does not belong to {story_id}: {ac_id}"
    if str(finding.get("status", "open")).strip().lower() not in VALID_STATUSES:
        return f"status must be one of {', '.join(sorted(VALID_STATUSES))}"
    if not str(finding.get("summary", "")).strip():
        return "summary is required"
    if not str(finding.get("evidence", "")).strip():
        return "evidence is required; implementation feedback cannot be anonymous"
    if bool(finding.get("mark_stale")) and not normalized_list(finding.get("source_units", [])):
        return "mark_stale requires source_units so Sentinel can stale only affected stories"
    return ""


def normalize_finding(
    finding: dict[str, Any],
    finding_id: str,
    index: int,
    story_index: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    story_id = str(finding.get("story", finding.get("story_id", ""))).strip()
    finding_type = str(finding["type"]).strip()
    status = str(finding.get("status", "open")).strip().lower()
    source_units = normalized_list(finding.get("source_units", [])) or story_index[story_id].get("source_units", [])
    normalized = {
        "id": finding_id,
        "type": finding_type,
        "status": status,
        "story_id": story_id,
        "acceptance_criteria": str(finding.get("acceptance_criteria", "")).strip(),
        "summary": str(finding.get("summary", "")).strip(),
        "evidence": str(finding.get("evidence", "")).strip(),
        "source": str(finding.get("source", "")).strip() or "implementation",
        "source_units": source_units,
        "blocks_dod": bool(finding.get("blocks_dod", True)),
        "mark_stale": bool(finding.get("mark_stale", False)),
        "created_at": utc_now(),
    }
    if finding_type == "gap":
        normalized["gap_id"] = str(finding.get("gap_id") or f"GAP-FEEDBACK-{index:03d}").strip()
    return normalized


def load_story_index(base: Path) -> dict[str, dict[str, Any]]:
    stories: dict[str, dict[str, Any]] = {}
    readiness = read_json(base / "08_context_packs" / "implementation_readiness.json", {})
    readiness_by_story = {
        str(item.get("story_id")): item
        for item in readiness.get("stories", []) if isinstance(item, dict) and item.get("story_id")
    } if isinstance(readiness, dict) else {}
    for path in sorted((base / "04_backlog").glob("US-*.md")):
        text = path.read_text(encoding="utf-8")
        story_id = path.stem
        readiness_item = readiness_by_story.get(story_id, {})
        source_units = [str(readiness_item.get("source_unit", "")).strip()]
        source_units.extend(str(item).strip() for item in readiness_item.get("trace", []) if str(item).startswith("SPEC-U-"))
        stories[story_id] = {
            "path": path,
            "acceptance_criteria": {item["id"] for item in acceptance_from_story_markdown(text)},
            "source_units": sorted({item for item in source_units if item}),
        }
    return stories


def persist_feedback_state(
    project_id: str,
    findings: list[dict[str, Any]],
    run_id: str,
    source: Path,
    report: Path,
) -> None:
    state = read_json(state_path(project_id), {})
    payload = state.get("implementation_feedback", {})
    if not isinstance(payload, dict):
        payload = {}
    existing = payload.get("findings", {})
    if not isinstance(existing, dict):
        existing = {}
    for finding in findings:
        existing[finding["id"]] = finding
    payload["findings"] = existing
    payload["last_feedback_id"] = run_id
    payload["last_source"] = source.as_posix()
    payload["last_report"] = report.as_posix()
    payload["open_by_story"] = open_feedback_by_story(existing)
    updates: dict[str, Any] = {"implementation_feedback": payload}
    if payload["open_by_story"]:
        updates["health"] = "DIRTY"
    update_state(project_id, **updates)


def refresh_feedback_story_gates(project_id: str, findings: list[dict[str, Any]]) -> None:
    if not findings:
        return
    from .backlog_gates import evaluate_story_gates, update_story_gate_state
    from .backlog_status import story_for_gate, update_story_gate_sections

    state = read_json(state_path(project_id), {})
    lifecycle = state.get("story_lifecycle", {})
    story_ids = sorted({str(item.get("story_id", "")).strip() for item in findings if item.get("story_id")})
    for story_id in story_ids:
        owner = ""
        if isinstance(lifecycle, dict) and isinstance(lifecycle.get(story_id), dict):
            owner = str(lifecycle[story_id].get("owner", ""))
        story = story_for_gate(project_id, story_id, owner)
        gate_result = evaluate_story_gates(project_id, story)
        update_story_gate_state(project_id, story_id, gate_result)
        story_path = workspace_path(project_id) / "04_backlog" / f"{story_id}.md"
        if story_path.exists():
            update_story_gate_sections(story_path, gate_result)


def open_feedback_by_story(findings: dict[str, Any]) -> dict[str, list[str]]:
    by_story: dict[str, list[str]] = {}
    for finding_id, finding in findings.items():
        if not isinstance(finding, dict):
            continue
        if finding.get("status") != "open" or not finding.get("blocks_dod", True):
            continue
        story_id = str(finding.get("story_id", "")).strip()
        if story_id:
            by_story.setdefault(story_id, []).append(str(finding_id))
    return {story: sorted(ids) for story, ids in by_story.items()}


def open_feedback_for_story(project_id: str, story_id: str) -> list[dict[str, str]]:
    state = read_json(state_path(project_id), {})
    payload = state.get("implementation_feedback", {})
    findings = payload.get("findings", {}) if isinstance(payload, dict) else {}
    if not isinstance(findings, dict):
        return []
    result: list[dict[str, str]] = []
    for finding_id, finding in findings.items():
        if not isinstance(finding, dict):
            continue
        if finding.get("story_id") != story_id or finding.get("status") != "open" or not finding.get("blocks_dod", True):
            continue
        result.append(
            {
                "id": str(finding_id),
                "type": str(finding.get("type", "")),
                "summary": str(finding.get("summary", "")),
            }
        )
    return sorted(result, key=lambda item: item["id"])


def write_feedback_report(
    project_id: str,
    accepted: list[dict[str, Any]],
    rejected: list[dict[str, str]],
    source: Path,
) -> Path:
    path = workspace_path(project_id) / "07_changes" / "05_implementation_feedback" / "feedback_report.md"
    accepted_rows = "\n".join(
        "| `{id}` | {type} | `{story}` | `{ac}` | {status} | {stale} | {summary} |".format(
            id=item["id"],
            type=item["type"],
            story=item["story_id"],
            ac=item.get("acceptance_criteria") or "N/A",
            status=item["status"],
            stale="yes" if item.get("mark_stale") else "no",
            summary=safe_cell(item["summary"], 160),
        )
        for item in accepted
    ) or "| N/A | N/A | N/A | N/A | N/A | N/A | N/A |"
    rejected_rows = "\n".join(f"| `{item['id']}` | {item['reason']} |" for item in rejected) or "| N/A | N/A |"
    path.write_text(
        f"""# Implementation Feedback Report - {project_id}

Source: `{source.as_posix()}`

This report records downstream implementation findings as governed feedback. Findings may open `GAP-FEEDBACK-*`, create `CHG` trace anchors, mark affected stories `Stale`, or block DoD. They do not rewrite backlog scope directly.

## Accepted Findings

| Finding | Type | Story | AC | Status | Marks Stale | Summary |
| --- | --- | --- | --- | --- | --- | --- |
{accepted_rows}

## Rejected Findings

| Finding | Reason |
| --- | --- |
{rejected_rows}
""",
        encoding="utf-8",
    )
    return path


def write_feedback_gaps(project_id: str, findings: list[dict[str, Any]]) -> Path | None:
    gap_findings = [item for item in findings if item.get("gap_id")]
    if not gap_findings:
        return None
    path = workspace_path(project_id) / "01_discovery" / "implementation_feedback_gaps.md"
    rows = "\n".join(
        f"| `{item['gap_id']}` | `{item['story_id']}` | {item['type']} | {item['status'].upper()} | {safe_cell(item['summary'], 180)} |"
        for item in gap_findings
    )
    path.write_text(
        f"""# Implementation Feedback Gaps - {project_id}

These gaps were opened by `/implementation-feedback`. They are downstream findings that require BA/Product review before the affected story is treated as Done.

| Gap | Story | Type | Status | Summary |
| --- | --- | --- | --- | --- |
{rows}
""",
        encoding="utf-8",
    )
    return path


def normalized_list(value: object) -> list[str]:
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


def acceptance_from_story_markdown(text: str) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    for line in text.splitlines():
        if not line.startswith("| AC-"):
            continue
        cells = parse_table_rows(line, strip_code_ticks=False)[0]
        if len(cells) >= 2:
            items.append({"id": cells[0], "classification": cells[1]})
    return items


def unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    for index in range(2, 1000):
        candidate = path.with_name(f"{path.stem}-{index}{path.suffix}")
        if not candidate.exists():
            return candidate
    raise ImplementationFeedbackError(f"Could not allocate unique path for {path}")


def safe_cell(value: Any, limit: int) -> str:
    return str(value).replace("\n", " ").replace("|", "/").strip()[:limit]
