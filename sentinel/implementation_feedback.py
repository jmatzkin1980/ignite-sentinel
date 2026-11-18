from __future__ import annotations

from .errors import InputError  # IMP-302: typed errors

import re
from pathlib import Path
from typing import Any

from .core.markdown import table_cell
from .core.graph import add_edge, add_node, upsert_node
from .core.markdown import parse_table_rows, split_table_row
from .memory import ContextBroker
from .payload_hygiene import archive_payload, sanitize_payload
from .workspace import read_json, state_path, update_state, utc_now, workspace_path
from .core.io import write_text
from .core.text import unique_path


class ImplementationFeedbackError(InputError):
    """Raised when implementation feedback cannot be metabolized."""


VALID_FINDING_TYPES = {"new-dependency", "gap", "ac-challenge", "surface-not-covered"}
VALID_STATUSES = {"open", "resolved"}
FINDING_ID_RE = re.compile(r"IFB-(\d+)")
GAP_ID_RE = re.compile(r"GAP-FEEDBACK-(\d+)")


def apply_implementation_feedback(project_id: str, source: Path) -> dict[str, object]:
    base = workspace_path(project_id)
    if not any((base / "04_backlog").glob("EPIC-*.md")):
        # IMP-312: /init creates the folder; the backlog exists once /backlog wrote an epic
        raise ImplementationFeedbackError("Cannot process implementation feedback before /backlog creates 04_backlog/EPIC-001.md.", gate=True)
    if not source.exists():
        raise ImplementationFeedbackError(f"Implementation feedback source not found: {source}")

    data = read_json(source, {})
    if not isinstance(data, dict):
        raise ImplementationFeedbackError("Implementation feedback source must be a JSON object with a findings array.")
    story_index = load_story_index(base)
    accepted, rejected = validate_findings(data, story_index, existing_feedback_ids(project_id))
    # IMP-342: validated as written; stored and rendered redacted and neutralized
    accepted = sanitize_payload(base, accepted)
    rejected = sanitize_payload(base, rejected, verbatim_keys=("reason",))  # runtime prose: redacted only
    if not accepted:
        # IMP-323: refuse before touching gaps, stories, the payload archive, state or the graph;
        # only the report of why each finding was refused is written.
        from .prd import rejection_summary

        write_feedback_report(project_id, accepted, rejected, source)
        raise ImplementationFeedbackError(
            "No implementation feedback findings were accepted: " + rejection_summary(rejected)
            + " Details in 07_changes/05_implementation_feedback/feedback_report.md."
        )

    feedback_dir = base / "07_changes" / "05_implementation_feedback"
    feedback_dir.mkdir(parents=True, exist_ok=True)
    archived = unique_path(feedback_dir / source.name)
    archive_payload(base, source, archived)
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
            from .backlog.hooks import mark_stale_stories_for_spec_units

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
    recompute_health_without_open_feedback(project_id)

    return {
        "feedback_id": run_id,
        "accepted": [item["id"] for item in accepted],
        "rejected": rejected,
        "staleness": stale_results,
        "source": str(archived.as_posix()),
        "report": str(report_path.as_posix()),
    }


def highest_number(ids: Any, pattern: re.Pattern[str]) -> int:
    numbers = [int(found.group(1)) for found in (pattern.fullmatch(str(item).strip()) for item in ids) if found]
    return max(numbers, default=0)


def existing_feedback_ids(project_id: str) -> tuple[list[str], list[str]]:
    """IMP-367: finding ids and gap ids earlier runs already used."""
    state = read_json(state_path(project_id), {})
    payload = state.get("implementation_feedback", {}) if isinstance(state, dict) else {}
    findings = payload.get("findings", {}) if isinstance(payload, dict) else {}
    findings = findings if isinstance(findings, dict) else {}
    gap_ids = [str(item.get("gap_id")) for item in findings.values() if isinstance(item, dict) and item.get("gap_id")]
    gap_ids.extend(existing_gap_rows(feedback_gaps_path(project_id)))
    return list(findings), gap_ids


def validate_findings(
    data: dict[str, Any],
    story_index: dict[str, dict[str, Any]],
    existing_ids: tuple[list[str], list[str]] = ([], []),
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    findings = data.get("findings")
    if not isinstance(findings, list) or not findings:
        raise ImplementationFeedbackError("Implementation feedback source must contain a non-empty findings array.")
    # IMP-367: a default id continues after the highest one already used (by an earlier
    # run or explicitly in this payload), so a later run never overwrites a finding.
    explicit = [item for item in findings if isinstance(item, dict)]
    next_finding = highest_number([*existing_ids[0], *(item.get("id") or "" for item in explicit)], FINDING_ID_RE)
    next_gap = highest_number([*existing_ids[1], *(item.get("gap_id") or "" for item in explicit)], GAP_ID_RE)
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, str]] = []
    for finding in findings:
        given = str(finding.get("id") or "").strip() if isinstance(finding, dict) else ""
        if not given:
            next_finding += 1
        finding_id = given or f"IFB-{next_finding:03d}"
        reason = validate_finding_shape(finding, story_index)
        if reason:
            rejected.append({"id": finding_id, "reason": reason})
            continue
        normalized = normalize_finding(finding, finding_id, story_index)
        if normalized.get("gap_id") == "":
            next_gap += 1
            normalized["gap_id"] = f"GAP-FEEDBACK-{next_gap:03d}"
        accepted.append(normalized)
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
    story_index: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """The stored finding; a gap without an explicit gap_id gets "" (numbered by the caller)."""
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
        normalized["gap_id"] = str(finding.get("gap_id") or "").strip()
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


def recompute_health_without_open_feedback(project_id: str) -> None:
    """IMP-367: once no feedback is open, health follows the current findings.

    Open feedback sets health DIRTY; resolving the last finding must not leave it DIRTY
    until /health runs, nor force CLEAN over another cause. Runs after the run's report
    is indexed, so the new CHG node is not itself a finding.
    """
    state = read_json(state_path(project_id), {})
    payload = state.get("implementation_feedback", {}) if isinstance(state, dict) else {}
    if isinstance(payload, dict) and payload.get("open_by_story"):
        return
    if str(state.get("health", "")).upper() != "DIRTY":
        return
    from .health import run_health

    run_health(project_id)


def refresh_feedback_story_gates(project_id: str, findings: list[dict[str, Any]]) -> None:
    if not findings:
        return
    from .backlog.gates import evaluate_story_gates, update_story_gate_state
    from .backlog.status import story_for_gate, update_story_gate_sections

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
            summary=table_cell(item["summary"], 160),
        )
        for item in accepted
    ) or "| N/A | N/A | N/A | N/A | N/A | N/A | N/A |"
    rejected_rows = "\n".join(f"| `{item['id']}` | {item['reason']} |" for item in rejected) or "| N/A | N/A |"
    write_text(path, f"""# Implementation Feedback Report - {project_id}

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
""")
    return path


def feedback_gaps_path(project_id: str) -> Path:
    return workspace_path(project_id) / "01_discovery" / "implementation_feedback_gaps.md"


def existing_gap_rows(path: Path) -> dict[str, str]:
    """IMP-367: the gap rows already in the file, by gap id, in file order."""
    if not path.exists():
        return {}
    rows: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("| `GAP-"):
            continue
        gap_id = split_table_row(line)[0]
        if gap_id:
            rows[gap_id] = line
    return rows


def write_feedback_gaps(project_id: str, findings: list[dict[str, Any]]) -> Path | None:
    gap_findings = [item for item in findings if item.get("gap_id")]
    if not gap_findings:
        return None
    path = feedback_gaps_path(project_id)
    # IMP-367: cumulative; a later run updates its rows by gap id (a resolved gap is
    # marked RESOLVED) and keeps every row of earlier runs.
    by_id = existing_gap_rows(path)
    for item in gap_findings:
        by_id[str(item["gap_id"])] = (
            f"| `{item['gap_id']}` | `{item['story_id']}` | {item['type']} | {item['status'].upper()} | {table_cell(item['summary'], 180)} |"
        )
    rows = "\n".join(by_id.values())
    write_text(path, f"""# Implementation Feedback Gaps - {project_id}

These gaps were opened by `/implementation-feedback`. They are downstream findings that require BA/Product review before the affected story is treated as Done.

| Gap | Story | Type | Status | Summary |
| --- | --- | --- | --- | --- |
{rows}
""")
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
