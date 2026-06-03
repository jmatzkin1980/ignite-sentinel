from __future__ import annotations

import re
from pathlib import Path

from .memory import ContextBroker
from .traceability import add_edge, add_node, nodes_by_type
from .workspace import update_state, workspace_path


def generate_quality(project_id: str) -> dict[str, object]:
    base = workspace_path(project_id)
    stories = nodes_by_type(project_id, "user_story")
    if not stories:
        raise RuntimeError("Cannot generate quality artifacts without user stories.")

    created = []
    for index, story in enumerate(stories, start=1):
        story_path = resolve_story_path(story["path"])
        story_text = ""
        if story_path.exists():
            story_text = story_path.read_text(encoding="utf-8")
        criteria = extract_acceptance_criteria(story_text)
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

    audit_path = base / "05_quality" / "backlog_readiness_audit.md"
    audit_path.write_text(render_backlog_audit(project_id, stories), encoding="utf-8")
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
    return {"test_cases": created, "count": len(created), "audit": str(audit_path)}


def resolve_story_path(path_value: str):
    path = Path(path_value)
    if path.is_absolute():
        return path
    return Path.cwd() / path


def extract_acceptance_criteria(text: str) -> list[str]:
    criteria = []
    for line in text.splitlines():
        match = re.match(r"\|\s*(AC-\d+)\s*\|\s*(.+?)\s*\|", line)
        if match:
            criteria.append(f"{match.group(1)}: {match.group(2)}")
    return criteria or ["AC-001: Validate the main happy path and a recoverable failure path."]


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
- Assert that trace IDs remain visible in the artifact chain.
"""


def render_backlog_audit(project_id: str, stories: list[dict[str, str]]) -> str:
    rows = "\n".join(
        f"| `{story['id']}` | {story.get('title', 'User story')} | {'PASS' if story.get('id') else 'FAIL'} | Review JTBD, source links, testability, and domain context citations. |"
        for story in stories
    )
    return f"""# Backlog Readiness Audit - {project_id}

This audit checks whether backlog items are ready for downstream execution using Sentinel vNext traceability and domain context.

## Verdict

`PARTIAL`

## Story Census

| Story ID | Title | Structural Status | Review Notes |
| --- | --- | --- | --- |
{rows}

## Audit Checklist

- [ ] Each story links to a JTBD or source requirement.
- [ ] Each story is an end-to-end functional slice.
- [ ] Acceptance criteria are testable and observable.
- [ ] Technology context is cited or explicitly pending.
- [ ] Design context is cited or explicitly pending.
- [ ] Quality and risk expectations are cited or explicitly pending.
- [ ] Traceability can map requirement -> spec -> epic -> story -> AC -> TC.
"""
