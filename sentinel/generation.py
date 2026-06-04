from __future__ import annotations

from .memory import ContextBroker, get_multi_domain_context
from .maturity import evaluate
from .traceability import add_edge, add_node, nodes_by_type
from .workspace import update_state, workspace_path


def generate_specs(project_id: str) -> dict[str, str]:
    maturity = evaluate(project_id)
    if maturity["readiness"] == "BLOCKED":
        raise RuntimeError("Cannot generate specs while requirement maturity is BLOCKED.")
    base = workspace_path(project_id)
    req_path = base / "02_requirements" / "requirements.md"
    brief_path = base / "02_requirements" / "project-brief.md"
    source_path = brief_path if brief_path.exists() else req_path
    req_text = source_path.read_text(encoding="utf-8")
    context = get_multi_domain_context(req_text, project_id)
    specs_path = base / "03_specs" / "prd_ai_friendly.md"
    specs_path.write_text(render_specs(project_id, req_text, context, source_path.name), encoding="utf-8")
    spec_id = add_node(project_id, "SPEC", "spec", specs_path, "AI-friendly PRD", domain="product")
    for req in nodes_by_type(project_id, "requirement"):
        add_edge(project_id, req["id"], spec_id, "elaborates")
    for brief in nodes_by_type(project_id, "project_brief"):
        add_edge(project_id, brief["id"], spec_id, "elaborates")
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


def render_specs(project_id: str, req_text: str, context: dict[str, object], source_name: str) -> str:
    return f"""# AI-Friendly PRD - {project_id}

## Product Purpose

Transform the validated requirement into a shared source of truth for Product, Technology, Design, Quality, and Delivery.

## Source Requirement

- Mature source: `02_requirements/{source_name}`

{req_text}

## Scope Boundaries

- In scope: Preserve the primary user job from `REQ-001` and confirmed scope seeds.
- Out of scope: Keep exclusions explicit and traceable to source evidence.
- Guardrail: Do not invent metrics, users, or acceptance criteria without sourced evidence.

## Jobs To Be Done

| JTBD ID | Context | Need | Expected Result | Source |
| --- | --- | --- | --- | --- |
| JTBD-001 | When the target user faces the scenario in `REQ-001` | Complete the primary job | Obtain the expected business outcome | `REQ-001` |

## Functional Capabilities

| Capability ID | Capability | JTBD Link | Trace Source |
| --- | --- | --- | --- |
| CAP-001 | Deliver the primary workflow described by the matured requirement. | JTBD-001 | `REQ-001` |

## Domain Context Retrieved From Memory

{render_context_summary(context)}

## Acceptance Strategy

- Acceptance criteria must validate the JTBD outcome, missing/invalid data, and traceability.
- Quality scenarios must include happy path, recoverable failure path, and stale/missing data where relevant.

## Decision And Assumption Trail

| ID | Type | Statement | Risk If Wrong |
| --- | --- | --- | --- |
| ASM-001 | Assumption | Any detail not present in seeds, source input, or domain context remains pending confirmation. | Downstream backlog may require rework after `/sync`. |

## Traceability

- Parent requirement: `REQ-001`
- Mature brief: `02_requirements/project-brief.md` when present
- Downstream artifacts: epics, user stories, acceptance criteria, tests, and traceability matrix.
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
- JTBD: `JTBD-001`

## User Story

As a target user, I want to complete the primary job described by the matured requirement so that I can obtain the expected business outcome.

## Context References

| Context Type | Source |
| --- | --- |
| Product requirement | `REQ-001`, `SPEC-001` |
| Business / Product seeds | `01_discovery/identity_seeds.md` |
| Technology context | `00_raw/02_technology_context/` if available |
| Design context | `00_raw/03_design_context/` if available |
| Quality context | `00_raw/04_quality_context/` if available |

## Functional Slice

- This story must deliver an end-to-end user-visible outcome, not a layer-only technical task.
- Any missing technical, design, or quality input must remain explicit as a gap or assumption.

## Acceptance Criteria

| AC ID | Criterion |
| --- | --- |
| AC-001 | Given the user has valid inputs, when the primary action is completed, then the system records the expected outcome. |
| AC-002 | Given required information is missing, when the user attempts to continue, then the system presents a clear recoverable validation state. |
| AC-003 | Given the outcome is produced, when QA validates the story, then source requirement and spec IDs are visible in the artifact. |

## Readiness Checklist

- [ ] JTBD link is present.
- [ ] Source requirement and PRD/spec link are present.
- [ ] Acceptance criteria are testable.
- [ ] Required technology/design/quality context is cited or explicitly marked as pending.
"""


def render_context_summary(context: dict[str, object]) -> str:
    domains = context.get("domains", {}) if isinstance(context, dict) else {}
    rows: list[str] = []
    for domain, results in domains.items():
        if not results:
            rows.append(f"| {domain} | No focused context retrieved. | N/A |")
            continue
        top = results[0]
        rows.append(
            f"| {domain} | {top.get('summary', 'Context retrieved')[:160]} | `{top.get('artifact_id', 'N/A')}` |"
        )
    return "| Domain | Retrieved Signal | Artifact |\n| --- | --- | --- |\n" + "\n".join(rows)
