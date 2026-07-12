from __future__ import annotations

import re
from hashlib import sha256
from pathlib import Path
from typing import Any

from .gates import (
    evaluate_story_gates,
    register_acceptance_evidence,
    update_story_gate_state,
)
from .rollup import backlog_status
from ..core.markdown import parse_frontmatter, parse_table_rows, update_frontmatter_keys
from ..core.graph import add_edge, add_node, nodes_by_type
from ..deltas import DELTA_LEGEND, delta_marker
from ..workspace import read_json, state_path, update_state, utc_now, workspace_path


class StoryStatusError(RuntimeError):
    """Raised when a story lifecycle update cannot be applied."""


STORY_STATUSES = ("Draft", "Ready", "In Progress", "In Review", "Done", "Blocked", "Stale")
STATUS_ALIASES = {status.lower(): status for status in STORY_STATUSES}
STATUS_ALIASES.update({status.lower().replace(" ", "-"): status for status in STORY_STATUSES})

LEGAL_TRANSITIONS = {
    "Draft": {"Ready", "Blocked", "Stale"},
    "Ready": {"Draft", "In Progress", "Blocked", "Stale"},
    "In Progress": {"In Review", "Blocked", "Stale"},
    "In Review": {"In Progress", "Done", "Blocked", "Stale"},
    "Done": {"Stale"},
    "Blocked": {"Draft", "Ready", "In Progress", "Stale"},
    "Stale": {"Draft", "Ready", "Blocked"},
}

AC_FREEZE_VERSION = 1


def normalize_story_status(value: str) -> str:
    status = STATUS_ALIASES.get(str(value).strip().lower())
    if not status:
        raise StoryStatusError(f"Invalid story status '{value}'. Allowed: {', '.join(STORY_STATUSES)}.")
    return status


def story_lifecycle_state(project_id: str) -> dict[str, dict[str, str]]:
    state = read_json(state_path(project_id), {})
    lifecycle = state.get("story_lifecycle", {})
    return lifecycle if isinstance(lifecycle, dict) else {}


def lifecycle_for_story(project_id: str, story_id: str) -> dict[str, str]:
    lifecycle = story_lifecycle_state(project_id)
    current = lifecycle.get(story_id, {})
    return {
        "status": normalize_story_status(str(current.get("status", "Draft"))),
        "owner": str(current.get("owner", "")).strip(),
    }


def apply_lifecycle_to_stories(project_id: str, stories: list[dict[str, Any]]) -> dict[str, dict[str, str]]:
    lifecycle = story_lifecycle_state(project_id)
    active_ids = {str(story["id"]) for story in stories}
    merged: dict[str, dict[str, str]] = {}
    for story in stories:
        story_id = str(story["id"])
        previous = lifecycle.get(story_id, {})
        try:
            status = normalize_story_status(str(previous.get("status", "Draft")))
        except StoryStatusError:
            status = "Draft"
        owner = str(previous.get("owner", "")).strip()
        story["status"] = status
        story["owner"] = owner
        merged[story_id] = {
            **(previous if isinstance(previous, dict) else {}),
            "status": status,
            "owner": owner,
        }
    for story_id, previous in lifecycle.items():
        if story_id not in active_ids:
            continue
        merged.setdefault(
            story_id,
            {
                **(previous if isinstance(previous, dict) else {}),
                "status": str(previous.get("status", "Draft")),
                "owner": str(previous.get("owner", "")).strip(),
            },
        )
    update_state(project_id, story_lifecycle=merged)
    return merged


def update_story_status(
    project_id: str,
    story_id: str,
    status: str,
    owner: str | None = None,
    evidence: Path | None = None,
) -> dict[str, object]:
    story_id = normalize_story_id(story_id)
    next_status = normalize_story_status(status)
    base = workspace_path(project_id)
    story_path = base / "04_backlog" / f"{story_id}.md"
    if not story_path.exists():
        raise StoryStatusError(f"Story does not exist: {story_id}. Run /backlog before /story-status.")

    current = lifecycle_for_story(project_id, story_id)
    current_status = current["status"]
    if next_status != current_status and next_status not in LEGAL_TRANSITIONS[current_status]:
        raise StoryStatusError(f"Illegal story transition: {current_status} -> {next_status}.")

    next_owner = current["owner"] if owner is None else str(owner).strip()
    evidence_record = register_acceptance_evidence(project_id, story_id, evidence) if evidence else None
    gate_result = evaluate_story_gates(project_id, story_for_gate(project_id, story_id, next_owner))
    if next_status == "Ready" and gate_result["strict"] and not gate_result["dor"]["passed"]:
        raise StoryStatusError("DoR gate blocks Ready: " + "; ".join(gate_result["dor"]["missing"]))
    if next_status == "Done" and gate_result["strict"] and not gate_result["dod"]["passed"]:
        raise StoryStatusError("DoD gate blocks Done: " + "; ".join(gate_result["dod"]["missing"]))

    freeze_record = None
    if next_status == "Ready":
        freeze_record = register_acceptance_criteria_freeze(project_id, story_id, story_path)

    lifecycle = story_lifecycle_state(project_id)
    lifecycle[story_id] = {
        "status": next_status,
        "owner": next_owner,
        "updated_at": utc_now(),
    }
    update_state(project_id, story_lifecycle=lifecycle, last_story_status_update=story_id)
    update_story_frontmatter(story_path, next_status, next_owner)
    update_story_gate_state(project_id, story_id, gate_result)
    update_story_gate_sections(story_path, gate_result)
    append_status_log(project_id, story_id, current_status, next_status, next_owner)
    change_id = add_node(
        project_id,
        "CHG",
        "story_status_change",
        base / "04_backlog" / "status_log.md",
        f"{story_id} {current_status} -> {next_status}",
        status="applied",
        domain="delivery",
    )
    story_node = story_node_id(project_id, story_id)
    if story_node:
        add_edge(project_id, change_id, story_node, "updates_story_status")
    if next_status != current_status and next_status in {"In Progress", "In Review", "Done"}:
        from .hooks import mark_stale_stories_for_activity_divergence

        mark_stale_stories_for_activity_divergence(project_id, story_id, change_id=change_id)
    board = backlog_status(project_id)

    return {
        "story_id": story_id,
        "previous_status": current_status,
        "status": next_status,
        "owner": next_owner,
        "dor": gate_result["dor"],
        "dod": gate_result["dod"],
        "warnings": transition_warnings(next_status, gate_result),
        "evidence": evidence_record,
        "acceptance_criteria_freeze": freeze_record,
        "backlog_board": board["path"],
        "change_id": change_id,
        "path": str(story_path.as_posix()),
    }


def transition_warnings(status: str, gate_result: dict[str, Any]) -> list[str]:
    if status == "Ready" and not gate_result["dor"]["passed"]:
        return [f"DoR missing: {item}" for item in gate_result["dor"]["missing"]]
    if status == "Done" and not gate_result["dod"]["passed"]:
        return [f"DoD missing: {item}" for item in gate_result["dod"]["missing"]]
    return []


def story_for_gate(project_id: str, story_id: str, owner: str) -> dict[str, Any]:
    readiness = readiness_item_for_story(project_id, story_id)
    story_path = workspace_path(project_id) / "04_backlog" / f"{story_id}.md"
    text = story_path.read_text(encoding="utf-8")
    return {
        "id": story_id,
        "owner": owner,
        "acceptance": acceptance_from_story_markdown(text),
        "trace": readiness.get("trace", trace_from_frontmatter(text)),
        "slicing": readiness.get("slicing", slicing_from_story_markdown(text)),
        "readiness": readiness.get("readiness", ""),
        "readiness_score": readiness.get("readiness_score", 0.0),
    }


def readiness_item_for_story(project_id: str, story_id: str) -> dict[str, Any]:
    path = workspace_path(project_id) / "08_context_packs" / "implementation_readiness.json"
    pack = read_json(path, {})
    for item in pack.get("stories", []) if isinstance(pack, dict) else []:
        if item.get("story_id") == story_id:
            return item
    return {}


def acceptance_from_story_markdown(text: str) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    for line in text.splitlines():
        if not line.startswith("| AC-"):
            continue
        cells = parse_table_rows(line, strip_code_ticks=False)[0]
        if len(cells) >= 2:
            items.append({"id": cells[0], "classification": cells[1]})
    return items


def register_acceptance_criteria_freeze(project_id: str, story_id: str, story_path: Path) -> dict[str, Any]:
    state = read_json(state_path(project_id), {})
    freezes = state.get("acceptance_criteria_freezes", {})
    if not isinstance(freezes, dict):
        freezes = {}
    existing = freezes.get(story_id)
    if isinstance(existing, dict) and existing.get("items"):
        return existing

    text = story_path.read_text(encoding="utf-8")
    record = {
        "version": AC_FREEZE_VERSION,
        "story_id": story_id,
        "frozen_at": utc_now(),
        "source": f"04_backlog/{story_id}.md",
        "trigger": "/story-status --set Ready",
        "items": acceptance_snapshot_from_items(acceptance_snapshot_from_story_markdown(text)),
    }
    freezes[story_id] = record
    update_state(project_id, acceptance_criteria_freezes=freezes)
    return record


def audit_acceptance_criteria_freezes(project_id: str, stories: list[dict[str, Any]]) -> list[dict[str, Any]]:
    state = read_json(state_path(project_id), {})
    freezes = state.get("acceptance_criteria_freezes", {})
    if not isinstance(freezes, dict) or not freezes:
        return []

    deltas: list[dict[str, Any]] = []
    for story in stories:
        story_id = str(story.get("id", "")).strip()
        freeze = freezes.get(story_id)
        if not isinstance(freeze, dict):
            continue
        frozen_items = keyed_acceptance_items(freeze.get("items", []))
        current_items = keyed_acceptance_items(acceptance_snapshot_from_items(story.get("acceptance", [])))
        for ac_id, frozen in frozen_items.items():
            current = current_items.get(ac_id)
            if current is None:
                deltas.append(acceptance_delta(story_id, ac_id, "removed", frozen, None))
                continue
            if frozen.get("hash") != current.get("hash"):
                deltas.append(acceptance_delta(story_id, ac_id, "changed", frozen, current))
        for ac_id, current in current_items.items():
            if ac_id not in frozen_items:
                deltas.append(acceptance_delta(story_id, ac_id, "added_after_freeze", None, current))

    if deltas:
        report_path = write_acceptance_criteria_delta_report(project_id, deltas)
        state = read_json(state_path(project_id), {})
        delta_history = state.get("acceptance_criteria_deltas", [])
        if not isinstance(delta_history, list):
            delta_history = []
        delta_history.append(
            {
                "version": AC_FREEZE_VERSION,
                "recorded_at": utc_now(),
                "path": report_path.relative_to(workspace_path(project_id)).as_posix(),
                "delta_count": len(deltas),
            }
        )
        update_state(project_id, acceptance_criteria_deltas=delta_history)
        add_acceptance_delta_trace(project_id, report_path, deltas)
    return deltas


def acceptance_snapshot_from_story_markdown(text: str) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    for line in text.splitlines():
        if not line.startswith("| AC-"):
            continue
        cells = parse_table_rows(line, strip_code_ticks=False)[0]
        if len(cells) >= 2:
            item = {"id": cells[0], "classification": cells[1]}
            if len(cells) >= 3:
                item["criterion"] = cells[2]
            items.append(item)
    return items


def keyed_acceptance_items(items: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(items, list):
        return {}
    return {
        str(item.get("id", "")).strip(): item
        for item in items
        if isinstance(item, dict) and str(item.get("id", "")).strip()
    }


def acceptance_snapshot_from_items(items: Any) -> list[dict[str, str]]:
    if not isinstance(items, list):
        return []
    snapshot: list[dict[str, str]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        ac_id = str(item.get("id", "")).strip()
        if not ac_id:
            continue
        classification = str(item.get("classification", "acceptance")).strip() or "acceptance"
        criterion = criterion_text(item)
        fingerprint = f"{ac_id}\n{classification}\n{criterion}"
        snapshot.append(
            {
                "id": ac_id,
                "classification": classification,
                "criterion": criterion,
                "hash": sha256(fingerprint.encode("utf-8")).hexdigest(),
            }
        )
    return snapshot


def criterion_text(item: dict[str, Any]) -> str:
    if item.get("criterion"):
        return normalize_ac_text(str(item.get("criterion", "")))
    parts = [
        str(item.get("given", "")).strip(),
        str(item.get("when", "")).strip(),
        str(item.get("then", "")).strip(),
    ]
    if any(parts):
        return normalize_ac_text(f"Given {parts[0]}, When {parts[1]}, Then {parts[2]}.")
    return ""


def normalize_ac_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def acceptance_delta(
    story_id: str,
    ac_id: str,
    change_type: str,
    frozen: dict[str, Any] | None,
    current: dict[str, Any] | None,
) -> dict[str, Any]:
    return {
        "story_id": story_id,
        "ac_id": ac_id,
        "change_type": change_type,
        "frozen": frozen or {},
        "current": current or {},
    }


def write_acceptance_criteria_delta_report(project_id: str, deltas: list[dict[str, Any]]) -> Path:
    path = workspace_path(project_id) / "04_backlog" / "acceptance_criteria_deltas.md"
    timestamp = utc_now()
    rows = "\n".join(
        "| {story} | `{ac}` | {delta} | {kind} | {before} | {after} |".format(
            story=delta["story_id"],
            ac=delta["ac_id"],
            delta=delta_marker(delta["change_type"]),
            kind=delta["change_type"],
            before=markdown_cell(delta.get("frozen", {}).get("criterion", "N/A")),
            after=markdown_cell(delta.get("current", {}).get("criterion", "N/A")),
        )
        for delta in deltas
    )
    path.write_text(
        f"""# Acceptance Criteria Delta Report - {project_id}

Generated: {timestamp}

This report records explicit diffs against acceptance criteria frozen by `/story-status --set Ready`.
Existing frozen criteria must not change silently during backlog regeneration; new criteria are listed as `added_after_freeze` for review.
{DELTA_LEGEND}

| Story | AC | Delta | Change | Frozen Criterion | Current Criterion |
| --- | --- | --- | --- | --- | --- |
{rows}
""",
        encoding="utf-8",
    )
    return path


def markdown_cell(value: Any) -> str:
    text = normalize_ac_text(str(value or "N/A"))
    return text.replace("|", "\\|")


def add_acceptance_delta_trace(project_id: str, report_path: Path, deltas: list[dict[str, Any]]) -> str:
    delta_id = add_node(
        project_id,
        "CHG",
        "acceptance_criteria_delta",
        report_path,
        "Acceptance criteria delta report",
        status="review-needed",
        domain="quality",
    )
    for delta in deltas:
        story_node = story_node_id(project_id, str(delta.get("story_id", "")))
        if story_node:
            add_edge(project_id, delta_id, story_node, "records_acceptance_delta_for")
    return delta_id


def trace_from_frontmatter(text: str) -> list[str]:
    trace = parse_frontmatter(text).get("trace", [])
    if not isinstance(trace, list):
        return []
    return [str(value) for value in trace if str(value).strip()]


def slicing_from_story_markdown(text: str) -> str:
    for line in text.splitlines():
        if line.startswith("- Slicing pattern:"):
            return line.split(":", 1)[1].strip().rstrip(".")
    return ""


def normalize_story_id(value: str) -> str:
    candidate = str(value).strip().upper()
    if not re.fullmatch(r"US-\d{3}", candidate):
        raise StoryStatusError("story must use the US-NNN format.")
    return candidate


def story_node_id(project_id: str, story_id: str) -> str:
    expected = f"04_backlog/{story_id}.md"
    for node in nodes_by_type(project_id, "user_story"):
        path = str(node.get("path", ""))
        if path.endswith(expected):
            return str(node.get("id", ""))
    return ""


def update_story_frontmatter(path: Path, status: str, owner: str) -> None:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise StoryStatusError(f"Story frontmatter not found: {path.name}")
    rendered = update_frontmatter_keys(text, {"status": status, "owner": owner}, quote_keys={"owner"})
    if rendered is None:
        raise StoryStatusError(f"Story frontmatter not closed: {path.name}")
    rendered = update_story_lifecycle_section(rendered, status, owner)
    path.write_text(rendered, encoding="utf-8")


def update_story_lifecycle_section(text: str, status: str, owner: str) -> str:
    replacement = (
        "## Lifecycle\n\n"
        f"- Status: {status}.\n"
        f"- Owner: {owner or '[UNASSIGNED]'}.\n"
    )
    pattern = re.compile(r"## Lifecycle\n\n- Status: .*?\n- Owner: .*?\n", re.DOTALL)
    if pattern.search(text):
        return pattern.sub(replacement, text, count=1)
    marker = "\n## Acceptance Criteria\n"
    if marker not in text:
        return text
    return text.replace(marker, "\n" + replacement + marker, 1)


def update_story_gate_sections(path: Path, gate_result: dict[str, Any]) -> None:
    text = path.read_text(encoding="utf-8")
    dor = gate_result.get("dor", {})
    dod = gate_result.get("dod", {})
    readiness = (
        "## Readiness Checklist\n\n"
        f"- {gate_checkbox(dor, 'slicing_pattern_assigned')} JTBD link is present.\n"
        f"- {gate_checkbox(dor, 'no_blocking_trace_gaps')} Source requirement, PRD, spec, FR and context pack links are present.\n"
        f"- {gate_checkbox(dor, 'acceptance_criteria_classified')} Acceptance criteria are testable.\n"
        f"- {gate_checkbox(dor, 'readiness_score')} Required technology/design/quality context is cited or explicitly marked as pending.\n\n"
        f"{render_gate_missing_block('DoR', dor)}"
    )
    done = (
        "## Done Checklist\n\n"
        f"- {gate_checkbox(dod, 'acceptance_evidence_traced')} Downstream acceptance evidence is traced.\n"
        f"- {gate_checkbox(dod, 'implementation_feedback_resolved')} Open implementation feedback is resolved.\n"
        f"- {gate_checkbox(dod, 'ready_gate_passed')} DoR remains satisfied at closure time.\n\n"
        f"{render_gate_missing_block('DoD', dod)}"
    )
    text = replace_section(text, "## Readiness Checklist", readiness)
    text = replace_section(text, "## Done Checklist", done)
    path.write_text(text, encoding="utf-8")


def replace_section(text: str, heading: str, replacement: str) -> str:
    pattern = re.compile(rf"{re.escape(heading)}\n\n.*?(?=\n## |\Z)", re.DOTALL)
    if pattern.search(text):
        return pattern.sub(replacement, text, count=1)
    return text.rstrip() + "\n\n" + replacement + "\n"


def gate_checkbox(gate: dict[str, Any], key: str) -> str:
    for item in gate.get("items", []) if isinstance(gate, dict) else []:
        if item.get("key") == key:
            return "[x]" if item.get("passed") else "[ ]"
    return "[ ]"


def render_gate_missing_block(label: str, gate: dict[str, Any]) -> str:
    missing = gate.get("missing", []) if isinstance(gate, dict) else []
    if not missing:
        return f"**{label} Gate:** Passed."
    rows = "\n".join(f"- {item}" for item in missing)
    return f"**{label} Gate Missing Items:**\n{rows}"


def append_status_log(project_id: str, story_id: str, previous: str, status: str, owner: str) -> Path:
    path = workspace_path(project_id) / "04_backlog" / "status_log.md"
    timestamp = utc_now()
    if path.exists():
        text = path.read_text(encoding="utf-8").rstrip()
    else:
        text = (
            f"# Story Status Log - {project_id}\n\n"
            "| Timestamp | Story | From | To | Owner |\n"
            "| --- | --- | --- | --- | --- |"
        )
    row = f"| {timestamp} | `{story_id}` | {previous} | {status} | {owner or 'N/A'} |"
    path.write_text(text + "\n" + row + "\n", encoding="utf-8")
    return path
