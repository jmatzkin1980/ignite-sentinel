from __future__ import annotations

from .memory import ContextBroker
from .maturity import evaluate
from .traceability import add_edge, add_node, nodes_by_type
from .workspace import update_state, workspace_path


def generate_specs(project_id: str) -> dict[str, str]:
    maturity = evaluate(project_id)
    if maturity["readiness"] == "BLOCKED":
        raise RuntimeError("Cannot generate specs while requirement maturity is BLOCKED.")
    base = workspace_path(project_id)
    req_path = base / "02_requirements" / "requirements.md"
    req_text = req_path.read_text(encoding="utf-8")
    specs_path = base / "03_specs" / "prd_ai_friendly.md"
    specs_path.write_text(render_specs(project_id, req_text), encoding="utf-8")
    spec_id = add_node(project_id, "SPEC", "spec", specs_path, "AI-friendly PRD", domain="product")
    for req in nodes_by_type(project_id, "requirement"):
        add_edge(project_id, req["id"], spec_id, "elaborates")
    ContextBroker(project_id).index_artifact(
        spec_id, "spec", specs_path, specs_path.read_text(encoding="utf-8"), trace_ids=[spec_id]
    )
    update_state(project_id, phase="specs_completed", health="CLEAN")
    return {"spec_id": spec_id, "path": str(specs_path)}


def generate_backlog(project_id: str) -> dict[str, str]:
    maturity = evaluate(project_id)
    if maturity["readiness"] == "BLOCKED":
        raise RuntimeError("Cannot generate backlog while requirement maturity is BLOCKED.")
    specs = nodes_by_type(project_id, "spec")
    if not specs:
        generate_specs(project_id)
        specs = nodes_by_type(project_id, "spec")
    base = workspace_path(project_id)
    epic_path = base / "04_backlog" / "EPIC-001.md"
    epic_path.write_text(render_epic(project_id), encoding="utf-8")
    epic_id = add_node(project_id, "EPIC", "epic", epic_path, "Deliver validated requirement value", domain="product")
    for spec in specs:
        add_edge(project_id, spec["id"], epic_id, "decomposes_to")

    story_path = base / "04_backlog" / "US-001.md"
    story_path.write_text(render_story(project_id, epic_id), encoding="utf-8")
    story_id = add_node(project_id, "US", "user_story", story_path, "User can complete the primary job", domain="functional")
    add_edge(project_id, epic_id, story_id, "contains")

    ac_id = add_node(project_id, "AC", "acceptance_criteria", story_path, "Acceptance criteria for US-001", domain="quality")
    add_edge(project_id, story_id, ac_id, "validated_by")

    broker = ContextBroker(project_id)
    broker.index_artifact(epic_id, "epic", epic_path, epic_path.read_text(encoding="utf-8"), trace_ids=[epic_id])
    broker.index_artifact(story_id, "user_story", story_path, story_path.read_text(encoding="utf-8"), trace_ids=[epic_id, story_id, ac_id])
    update_state(project_id, phase="backlog_completed", health="CLEAN", metrics={"requirements": 1, "gaps_open": 0, "decisions_pending": 1, "user_stories": 1})
    return {"epic_id": epic_id, "story_id": story_id, "acceptance_id": ac_id, "path": str(story_path)}


def render_specs(project_id: str, req_text: str) -> str:
    return f"""# AI-Friendly PRD - {project_id}

## Purpose

Transform the validated requirement into a shared source of truth for Product, Technology, Design, Quality, and Delivery.

## Source Requirement

{req_text}

## Functional Scope

- Preserve the primary user job from `REQ-001`.
- Keep scope, constraints, open decisions, and acceptance criteria traceable.

## Domain Notes

| Domain | Expected Consumer | Required Signal |
| --- | --- | --- |
| Product | BA / PM | Business value, scope, rules |
| Technology | TL / FE / BE | Constraints, integrations, data assumptions |
| Design | UX/UI | User journey and interaction states |
| Quality | QE / Automation | Testable outcomes and edge cases |
| Delivery | PM | Dependencies, sequencing, risks |
"""


def render_epic(project_id: str) -> str:
    return f"""# EPIC-001 - Deliver Validated Requirement Value

- Project: `{project_id}`
- Trace parent: `SPEC-001`
- Status: `draft`

## Outcome

Deliver the first end-to-end slice that proves the matured requirement can create user and business value.
"""


def render_story(project_id: str, epic_id: str) -> str:
    return f"""# US-001 - Complete Primary User Job

- Project: `{project_id}`
- Parent epic: `{epic_id}`
- Trace parent: `SPEC-001`
- Status: `draft`

## User Story

As a target user, I want to complete the primary job described by the matured requirement so that I can obtain the expected business outcome.

## Acceptance Criteria

| AC ID | Criterion |
| --- | --- |
| AC-001 | Given the user has valid inputs, when the primary action is completed, then the system records the expected outcome. |
| AC-002 | Given required information is missing, when the user attempts to continue, then the system presents a clear recoverable validation state. |
| AC-003 | Given the outcome is produced, when QA validates the story, then source requirement and spec IDs are visible in the artifact. |
"""
