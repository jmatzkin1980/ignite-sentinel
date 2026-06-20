from __future__ import annotations

import re
from typing import Any

from ..core.markdown import frontmatter_list
from ..slicing_model import load_slicing_model
from .prd import render_ears_requirements_table


EARS_REQUIREMENT_ID_RE = re.compile(r"^REQ-EARS-\d{3}$")

TASK_SEED_BOUNDARY_NOTE = (
    "Task seeds are optional implementation intentions for downstream agents. "
    "Ignite does not execute, estimate, assign, schedule or manage these tasks; "
    "downstream planning may expand, reorder or discard them while preserving story scope "
    "and traceability."
)


def build_domain_context_coverage(backlog_context: dict[str, Any]) -> list[dict[str, str]]:
    sections = backlog_context.get("sections", {}) if isinstance(backlog_context, dict) else {}
    domain_specs = [
        ("Product", ("epic_value", "functional_slicing"), "Defines value, scope, slicing, FR/JTBD links and acceptance intent."),
        ("Technology", ("technical_dependencies", "execution_commands", "critical_surfaces", "engineering_practices"), "Defines architecture, commands, affected surfaces, constraints and implementation risks."),
        ("Design", ("ux_states", "design_match"), "Defines journeys, screens, states, components, tokens and interaction rules."),
        ("Quality", ("quality_risks", "regression_contract"), "Defines testability, regression, evidence, test data and quality gates."),
        ("Delivery", ("open_uncertainty",), "Defines blockers, sequencing, dependencies, roadmap and planning uncertainty."),
    ]
    coverage: list[dict[str, str]] = []
    for domain, keys, impact in domain_specs:
        evidence = first_context_result(sections, keys)
        status = "Confirmed" if evidence else "Pending"
        coverage.append(
            {
                "domain": domain,
                "evidence": evidence_label(evidence) if evidence else "[PENDING DOMAIN CONTEXT]",
                "status": status,
                "impact": impact,
            }
        )
    return coverage


def first_context_result(sections: dict[str, Any], keys: tuple[str, ...]) -> dict[str, Any] | None:
    for key in keys:
        section = sections.get(key, {}) if isinstance(sections, dict) else {}
        results = section.get("results", []) if isinstance(section, dict) else []
        if results:
            return results[0]
    return None


def evidence_label(row: dict[str, Any]) -> str:
    artifact_id = str(row.get("artifact_id", "N/A"))
    artifact_type = str(row.get("artifact_type", "artifact"))
    section = str(row.get("section_path", "")).strip()
    if section:
        return f"`{artifact_id}` ({artifact_type}, {section})"
    return f"`{artifact_id}` ({artifact_type})"


def build_agent_execution_contract(
    story: dict[str, Any],
    backlog_context: dict[str, Any],
    domain_coverage: list[dict[str, str]],
) -> dict[str, Any]:
    sections = backlog_context.get("sections", {}) if isinstance(backlog_context, dict) else {}
    technical_ready = coverage_status(domain_coverage, "Technology") == "Confirmed"
    design_ready = coverage_status(domain_coverage, "Design") == "Confirmed"
    quality_ready = coverage_status(domain_coverage, "Quality") == "Confirmed"
    execution_ready = technical_ready and quality_ready
    if story.get("domain") == "design":
        execution_ready = execution_ready and design_ready

    return {
        "readiness": "Ready With Domain Evidence" if execution_ready else "Needs Domain Context",
        "agent_profile": agent_profile_for_story(story),
        "decision_priority": "Business value > correctness > safety/privacy > test evidence > implementation elegance",
        "commands": context_signal(sections, ("execution_commands",), "[PENDING TECHNOLOGY CONTEXT] Provide build, lint, test, typecheck, migration or boot commands."),
        "critical_surfaces": context_signal(sections, ("critical_surfaces", "technical_dependencies"), "[PENDING TECHNOLOGY CONTEXT] Provide affected files, services, APIs, data stores, modules or shared surfaces."),
        "design_match": design_signal_for_story(story, sections),
        "engineering_practices": context_signal(sections, ("engineering_practices",), "[PENDING TECHNOLOGY CONTEXT] Provide engineering handbook, ADRs, style rules, logging/error patterns or repo conventions."),
        "validation": validation_contract_for_story(story),
        "autonomy": autonomy_contract_for_story(story),
        "blast_radius": blast_radius_for_story(story),
        "parallelization": parallelization_note_for_story(story),
        "retrieval_plan": retrieval_plan_for_story(story),
    }


def coverage_status(coverage: list[dict[str, str]], domain: str) -> str:
    for row in coverage:
        if row.get("domain") == domain:
            return row.get("status", "Pending")
    return "Pending"


def context_signal(sections: dict[str, Any], keys: tuple[str, ...], pending: str) -> dict[str, Any]:
    row = first_context_result(sections, keys)
    if not row:
        return {"status": "Pending", "source": "[PENDING DOMAIN CONTEXT]", "summary": pending}
    return {
        "status": "Confirmed",
        "source": evidence_label(row),
        "summary": str(row.get("summary", "Context retrieved"))[:320],
        "anchor": anchor_for_context_row(row),
    }


def anchor_for_context_row(row: dict[str, Any]) -> dict[str, Any]:
    read_plan = row.get("read_plan", {})
    if not isinstance(read_plan, dict):
        read_plan = read_plan_for_row(row)
    return {
        "source_path": str(read_plan.get("source_path", row.get("source_path", row.get("file_path", "")))),
        "section_path": str(read_plan.get("section_path", row.get("section_path", ""))),
        "line_start": int(read_plan.get("line_start", row.get("line_start", 0)) or 0),
        "line_end": int(read_plan.get("line_end", row.get("line_end", 0)) or 0),
    }


def read_plan_for_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_path": row.get("source_path", row.get("file_path", "")),
        "section_path": row.get("section_path", ""),
        "line_start": int(row.get("line_start", 0) or 0),
        "line_end": int(row.get("line_end", 0) or 0),
    }


def design_signal_for_story(story: dict[str, Any], sections: dict[str, Any]) -> dict[str, Any]:
    if story.get("domain") != "design" and story.get("label") != "Enabler":
        return {"status": "Not Applicable", "source": "N/A", "summary": "No direct design execution contract is required for this story unless design context later marks it as impacted."}
    return context_signal(sections, ("design_match", "ux_states"), "[PENDING DESIGN CONTEXT] Provide prototype, UX states, components, tokens, accessibility or interaction rules.")


def agent_profile_for_story(story: dict[str, Any]) -> str:
    if story.get("type") == "cross_cutting_enabler":
        return "Implementation enabler agent with Technology and Quality review"
    domain = story.get("domain")
    if domain == "technical":
        return "Backend/integration planning agent with Quality verifier"
    if domain == "design":
        return "Frontend/design implementation agent with Quality verifier"
    if domain == "quality":
        return "Quality verifier agent with Product traceability review"
    return "Product-to-implementation planning agent"


def validation_contract_for_story(story: dict[str, Any]) -> dict[str, str]:
    fail_to_pass = [item["id"] for item in story.get("acceptance", []) if item.get("classification") == "fail-to-pass"]
    pass_to_pass = [item["id"] for item in story.get("acceptance", []) if item.get("classification") == "pass-to-pass"]
    evidence = [item["id"] for item in story.get("acceptance", []) if item.get("classification") == "evidence"]
    return {
        "fail_to_pass": ", ".join(fail_to_pass) or "[PENDING QUALITY CONTEXT]",
        "pass_to_pass": ", ".join(pass_to_pass) or "[PENDING QUALITY CONTEXT]",
        "evidence": ", ".join(evidence) or "[PENDING QUALITY CONTEXT]",
    }


def autonomy_contract_for_story(story: dict[str, Any]) -> dict[str, list[str]]:
    return {
        "always": [
            "Preserve trace IDs in implementation notes, tests or evidence.",
            "Write or update tests/evidence for the acceptance criteria before marking the story done.",
            "Use retrieved domain context and workspace source files as authority.",
        ],
        "ask_first": [
            "Changing database schemas, auth/permission behavior, external contracts, deployment settings or shared platform configuration.",
            "Adding new dependencies or expanding scope beyond the story boundary.",
            "Editing files or surfaces not cited by Technology/Design context when the blast radius is unclear.",
        ],
        "never": [
            "Invent missing Technology, Design or Quality context.",
            "Commit credentials, private URLs, raw payloads, account IDs or sensitive client facts.",
            "Modify unrelated flows to make the story pass.",
        ],
    }


def blast_radius_for_story(story: dict[str, Any]) -> list[str]:
    return [
        "Keep changes inside the confirmed capability boundary for this story.",
        "Do not alter upstream discovery, PRD or specs without a traced /sync or gap-resolution event.",
        "Treat unlisted shared systems, auth flows, data contracts, design system foundations and deployment settings as out of scope unless domain context explicitly includes them.",
    ]


def parallelization_note_for_story(story: dict[str, Any]) -> str:
    dependencies = story.get("dependencies", [])
    enables = story.get("enables", [])
    if enables:
        return f"Build before dependent stories when planning execution. Enables: {', '.join(enables)}."
    if dependencies:
        return f"Sequence after dependencies are accepted or stubbed with explicit contracts: {', '.join(dependencies)}."
    return "Can be planned as an early slice if domain context is sufficient and no shared-surface conflict is detected."


def retrieval_plan_for_story(story: dict[str, Any]) -> list[dict[str, str]]:
    story_id = story["id"]
    title = story["title"]
    plan = [
        {
            "agent": "Planner",
            "workflow": "planning",
            "query": f"{story_id} {title} dependencies sequencing parallelization blast radius",
            "domain": "any",
            "expected_evidence": "Dependencies, blockers, enables edges, sequencing and scope boundaries.",
            "required_before": "planning",
        },
        {
            "agent": "QA",
            "workflow": "quality",
            "query": f"{story_id} {title} fail-to-pass pass-to-pass regression evidence test data acceptance",
            "domain": "quality",
            "expected_evidence": "Acceptance criteria classifications, regression expectations, evidence and test data.",
            "required_before": "test design",
        },
    ]
    if story.get("domain") in {"technical"} or story.get("type") == "cross_cutting_enabler":
        plan.append(
            {
                "agent": "Technology",
                "workflow": "implementation",
                "query": f"{story_id} {title} architecture commands critical files api data contracts failure behavior",
                "domain": "technical",
                "expected_evidence": "Commands, affected surfaces, API/data contracts, engineering practices and failure behavior.",
                "required_before": "implementation",
            }
        )
    if story.get("domain") == "design":
        plan.append(
            {
                "agent": "Design/Frontend",
                "workflow": "frontend",
                "query": f"{story_id} {title} journey screens states components tokens validation accessibility",
                "domain": "design",
                "expected_evidence": "Screens, UX states, component mapping, tokens, accessibility and interaction rules.",
                "required_before": "frontend implementation",
            }
        )
    return plan


def render_epic(project_id: str, stories: list[dict[str, Any]], backlog_context: dict[str, Any]) -> str:
    story_sections = "\n\n".join(render_story_section(story) for story in stories)
    story_rows = "\n".join(
        f"| `{story['id']}` | {story['type']} | {story['title']} | {story['label']} | {story['slicing']} | {', '.join(story['dependencies']) or 'None'} | {', '.join(story['trace'])} |"
        for story in stories
    )
    domain_coverage = stories[0].get("domain_coverage", build_domain_context_coverage(backlog_context)) if stories else build_domain_context_coverage(backlog_context)
    readiness = backlog_context.get("implementation_readiness", {})
    ears_block = render_ears_requirements_table(backlog_context)
    trace_frontmatter = frontmatter_list(["REQ-001", *ears_trace_ids(backlog_context), "PRD-001", "SPEC-001"])
    slicing_model = load_slicing_model()
    return f"""---
id: EPIC-001
project: {project_id}
status: draft
priority: Must Have
trace:
{trace_frontmatter}
context_pack: 08_context_packs/backlog_generation.json
slicing_model: vertical-value-slices
---

# EPIC-001 - Deliver Validated Requirement Value

## Outcome

Deliver the first ordered set of vertical slices derived from evidence-backed Spec Units, proving the mature requirement can create user and business value while preserving traceability for downstream AI planning, implementation, and testing agents.

## Source And Retrieval

| Field | Value |
| --- | --- |
| Project | `{project_id}` |
| Primary sources | `02_requirements/project-brief.md`, `03_specs/prd.md`, `03_specs/specs.md` |
| Context pack | `08_context_packs/backlog_generation.json` |
| Implementation readiness | `08_context_packs/implementation_readiness.json` ({readiness.get('verdict', 'PENDING')}) |
| Generation rule | Use focused local retrieval before slicing. Workspace files remain source of truth; memory is a retrieval aid. |
| Privacy | Do not copy credentials, private URLs, raw payloads, account IDs, or confidential client-specific facts into backlog artifacts. |

## Confirmed EARS Requirements

These normalized statements come from `02_requirements/requirements.md`. Stories and acceptance criteria should preserve applicable `REQ-EARS-*` IDs when planning or testing the backlog.

{ears_block or "`[PENDING INPUT]` - no confirmed EARS statements are present in `02_requirements/requirements.md`."}

## Domain Context Coverage

Backlog generation consumes living domain context when Technology, Design, Quality, Delivery or other roles add files to the workspace and those files are ingested or synced. The backlog cites retrieved evidence when available and leaves `[PENDING DOMAIN CONTEXT]` when a domain contract is still missing.

{render_domain_context_coverage(domain_coverage)}

## Epic Scope

### In Scope

- End-to-end functional slices derived from confirmed `SPEC-U-*` units.
- Acceptance criteria in declarative Given/When/Then form.
- Agent execution contracts derived from retrieved domain context, or explicit pending markers when context is missing.
- Dependencies, assumptions, readiness and done checks visible to humans and AI agents.
- Explicit `[PENDING INPUT]` markers when context was not retrieved or not confirmed.

### Out Of Scope

- Layer-only implementation tasks unless they are framed as spikes or scaffolding needed to unlock a value slice.
- Unconfirmed enhancements, inferred business rules, or low-level implementation contracts that belong in domain context packs.
- Rewriting upstream discovery, PRD, or specs without a `/sync` or gap-resolution event.

## Slicing Strategy

{render_slicing_strategy_table(slicing_model)}

## Story Map

| Story | Type | Title | Label | Slicing Pattern | Dependencies | Trace |
| --- | --- | --- | --- | --- | --- | --- |
{story_rows}

## Cross-Cutting Enabler Boundary

{render_enabler_boundary(slicing_model)}

## Retrieved Context Summary

{render_backlog_context_summary(backlog_context)}

## Stories

{story_sections}

## Epic Readiness Checklist

- [ ] Each story is traceable to `REQ-001`, `PRD-001`, `SPEC-001`, and at least one confirmed `SPEC-U-*` or explicit `[PENDING INPUT]` gap.
- [ ] Each story has declarative acceptance criteria with happy, validation, failure/recovery and quality evidence paths.
- [ ] Dependencies and pending context are explicit.
- [ ] No story is only a technical layer unless marked as a spike/scaffolding exception.
- [ ] The epic can be handed to planning, implementation and test agents without loading the entire workspace.
"""


def render_slicing_strategy_table(slicing_model: dict[str, Any]) -> str:
    rows = [
        f"| {row['heuristic']} | {row['applies']} |"
        for row in slicing_model.get("strategy_rows", [])
    ]
    return "| Heuristic | How Sentinel Applies It |\n| --- | --- |\n" + "\n".join(rows)


def render_enabler_boundary(slicing_model: dict[str, Any]) -> str:
    paragraphs = slicing_model.get("enabler_boundary", {}).get("paragraphs", [])
    return "\n\n".join(str(item) for item in paragraphs)


def render_enabler_epic(
    project_id: str,
    enablers: list[dict[str, Any]],
    value_stories: list[dict[str, Any]],
    backlog_context: dict[str, Any],
) -> str:
    story_sections = "\n\n".join(render_story_section(story) for story in enablers)
    rows = "\n".join(
        f"| `{story['id']}` | {story['title']} | {', '.join(story['enables'])} | {story['slicing']} | {', '.join(story['trace'])} |"
        for story in enablers
    )
    value_rows = "\n".join(f"| `{story['id']}` | {story['title']} |" for story in value_stories)
    domain_coverage = enablers[0].get("domain_coverage", build_domain_context_coverage(backlog_context)) if enablers else build_domain_context_coverage(backlog_context)
    ears_block = render_ears_requirements_table(backlog_context)
    trace_frontmatter = frontmatter_list(["REQ-001", *ears_trace_ids(backlog_context), "PRD-001", "SPEC-001"])
    return f"""---
id: EPIC-002
project: {project_id}
status: draft
priority: Must Have
type: cross_cutting_enabler_epic
trace:
{trace_frontmatter}
context_pack: 08_context_packs/backlog_generation.json
---

# EPIC-002 - Cross-Cutting Enablers For Validated Requirement Value

## Boundary Rule

This epic exists only for implementation enablers that must be built in advance to support the functionality being built in `EPIC-001` or the confirmed project scope. It must not collect generic infrastructure, vague setup, or broad platform aspirations.

## Domain Context Coverage

{render_domain_context_coverage(domain_coverage)}

## Confirmed EARS Requirements

{ears_block or "`[PENDING INPUT]` - no confirmed EARS statements are present in `02_requirements/requirements.md`."}

## Accepted Enabler Test

An item belongs here only when all checks pass:

- It supports a named story, epic, FR, capability, or implementation surface inside the confirmed project boundary.
- It reduces a concrete dependency, risk, contract uncertainty, permission concern, data need, UX foundation need, backend/frontend foundation need, or evidence need.
- It has objective acceptance criteria.
- It is inside the project boundary confirmed by discovery/specs.
- It is not merely a precondition such as "environment exists", "make an internal tool accessible", or "internal tool is accessible".

## Value Stories Enabled

| Story | Title |
| --- | --- |
{value_rows}

## Enabler Story Map

| Story | Title | Enables | Slicing Pattern | Trace |
| --- | --- | --- | --- | --- |
{rows}

## Retrieved Context Summary

{render_backlog_context_summary(backlog_context)}

## Stories

{story_sections}
"""


def render_story_section(story: dict[str, Any]) -> str:
    dependencies = ", ".join(story["dependencies"]) or "None"
    acceptance = "\n\n".join(render_gherkin_criterion(item) for item in story["acceptance"])
    owner = story.get("owner") or "[UNASSIGNED]"
    dor = story.get("dor", {})
    dod = story.get("dod", {})
    return f"""### {story['id']} - {story['title']} [Label: {story['label']}]

**Description:** {story['description']}

**Lifecycle:** {story.get('status', 'Draft')} / {owner}

**Narrative:**
As a target user,
I want {story['goal'].lower()},
So that {story['benefit'].lower()}

**Slicing Pattern:** {story['slicing']}

**Slicing Rationale:** {story.get('slicing_rationale', '[PENDING INPUT]')}

**Type:** {story['type']}

**Dependencies:** {dependencies}

**Enables:** {", ".join(story.get("enables", [])) or "N/A"}

**Context Used:**
| Need | Artifact | Signal |
| --- | --- | --- |
| {story['context']['need']} | `{story['context']['artifact_id']}` ({story['context']['artifact_type']}) | {safe_cell(story['context']['summary'], 220)} |

**Domain Context Coverage:**

{render_domain_context_coverage(story.get('domain_coverage', []))}

**Agent Execution Contract:**

{render_agent_execution_contract(story.get('execution_contract', {}))}

**Retrieval Plan For Execution Agents:**

{render_execution_retrieval_plan(story.get('execution_contract', {}).get('retrieval_plan', []))}

{render_task_seed_contract_section(story.get('task_seed_contract'), '**Task Seed Contract:**')}

**In Scope:**
- The smallest user-observable behavior that satisfies `{story['fr']}`.
- Required validation, recoverable failure behavior and trace evidence for this slice.
- Domain context cited above, or `[PENDING INPUT]` if the evidence is missing.

**Out Of Scope:**
- Unconfirmed variations, optimizations or implementation details not required for this slice.
- Sensitive raw data, credentials, private URLs or client-specific operational facts.

**Acceptance Criteria:**

{acceptance}

**Definition Of Ready:**
- {gate_checkbox(dor, 'readiness_score')} Product, design, technology and quality context is cited or explicitly pending.
- {gate_checkbox(dor, 'slicing_pattern_assigned')} Dependencies are known and do not hide a layer-only prerequisite.
- {gate_checkbox(dor, 'acceptance_criteria_classified')} Acceptance criteria are testable without reading the full workspace.
- {gate_checkbox(dor, 'no_blocking_trace_gaps')} Open gaps or assumptions are visible before planning.

{render_gate_missing_block('DoR', dor)}

**Definition Of Done:**
- {gate_checkbox(dod, 'acceptance_evidence_traced')} Code and artifact review completed.
- {gate_checkbox(dod, 'acceptance_evidence_traced')} Happy, validation and failure/recovery paths verified.
- {gate_checkbox(dod, 'acceptance_evidence_traced')} Trace IDs remain visible in implementation notes, tests or evidence.
- {gate_checkbox(dod, 'ready_gate_passed')} No unrelated scope was added during implementation.

{render_gate_missing_block('DoD', dod)}

**Traceability:** {", ".join(story['trace'])}
"""


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


def render_gherkin_criterion(criterion: dict[str, str]) -> str:
    classification = criterion.get("classification", "acceptance")
    return f"""> **{criterion['id']} - {criterion['name']} [{classification}]:**
> Given {criterion['given']},
> When {criterion['when']},
> Then {criterion['then']}."""


def render_domain_context_coverage(coverage: list[dict[str, str]]) -> str:
    if not coverage:
        return "| Domain | Evidence Used | Status | Impact |\n| --- | --- | --- | --- |\n| All | [PENDING DOMAIN CONTEXT] | Pending | No domain coverage was available at generation time. |"
    rows = "\n".join(
        f"| {row.get('domain', 'Unknown')} | {row.get('evidence', '[PENDING DOMAIN CONTEXT]')} | {row.get('status', 'Pending')} | {safe_cell(row.get('impact', ''), 180)} |"
        for row in coverage
    )
    return f"""| Domain | Evidence Used | Status | Impact |
| --- | --- | --- | --- |
{rows}"""


def render_agent_execution_contract(contract: dict[str, Any]) -> str:
    if not contract:
        return "[PENDING DOMAIN CONTEXT] Agent execution contract was not generated."
    commands = contract.get("commands", {})
    critical_surfaces = contract.get("critical_surfaces", {})
    design_match = contract.get("design_match", {})
    engineering_practices = contract.get("engineering_practices", {})
    validation = contract.get("validation", {})
    autonomy = contract.get("autonomy", {})
    return f"""| Field | Value |
| --- | --- |
| Readiness | {contract.get('readiness', 'Needs Domain Context')} |
| Agent profile | {contract.get('agent_profile', 'Planning agent')} |
| Decision priority | {contract.get('decision_priority', 'Business value > correctness > safety > evidence')} |
| Commands | {render_context_signal_inline(commands)} |
| Critical surfaces | {render_context_signal_inline(critical_surfaces)} |
| Design match | {render_context_signal_inline(design_match)} |
| Engineering practices | {render_context_signal_inline(engineering_practices)} |
| Fail-to-Pass | {validation.get('fail_to_pass', '[PENDING QUALITY CONTEXT]')} |
| Pass-to-Pass | {validation.get('pass_to_pass', '[PENDING QUALITY CONTEXT]')} |
| Evidence | {validation.get('evidence', '[PENDING QUALITY CONTEXT]')} |
| Parallelization | {safe_cell(contract.get('parallelization', ''), 220)} |

**Autonomy Limits**

- Always: {', '.join(autonomy.get('always', []))}
- Ask First: {', '.join(autonomy.get('ask_first', []))}
- Never: {', '.join(autonomy.get('never', []))}

**Blast Radius**

{render_bullet_list(contract.get('blast_radius', []))}
"""


def render_execution_retrieval_plan(plan: list[dict[str, str]]) -> str:
    if not plan:
        return "| Agent | Domain | Query | Expected Evidence | Required Before |\n| --- | --- | --- | --- | --- |\n| Planner | any | [PENDING CONTEXT QUERY] | [PENDING CONTEXT] | implementation |"
    rows = "\n".join(
        f"| {item.get('agent', 'Execution agent')} | {item.get('domain', 'any')} | `{safe_cell(item.get('query', ''), 220)}` | {safe_cell(item.get('expected_evidence', ''), 180)} | {item.get('required_before', 'implementation')} |"
        for item in plan
    )
    return f"""| Agent | Domain | Query | Expected Evidence | Required Before |
| --- | --- | --- | --- | --- |
{rows}"""


def render_task_seed_contract_section(contract: object, heading: str = "## Task Seed Contract") -> str:
    if not isinstance(contract, dict) or not contract.get("emitted"):
        return ""
    seeds = contract.get("seeds", [])
    rows = "\n".join(render_task_seed_row(seed) for seed in seeds if isinstance(seed, dict)) if isinstance(seeds, list) else ""
    rows = rows or "| N/A | N/A | N/A | N/A | N/A | N/A |"
    return f"""{heading}

> {contract.get('scope_boundary', TASK_SEED_BOUNDARY_NOTE)}

Source: {contract.get('source', 'Derived from acceptance criteria and critical surfaces.')}

| Seed | Kind | Intention | AC Trace | Critical Surfaces | Parallelizable |
| --- | --- | --- | --- | --- | --- |
{rows}
"""


def render_task_seed_row(seed: dict[str, Any]) -> str:
    ac_refs = ", ".join(f"`{item}`" for item in seed.get("acceptance_criteria", [])) or "`[PENDING AC]`"
    surfaces = "; ".join(str(item) for item in seed.get("critical_surfaces", [])) or "[PENDING DOMAIN CONTEXT]"
    parallelizable = "yes" if seed.get("parallelizable") else "no"
    return (
        f"| `{seed.get('id', 'TSEED-UNKNOWN')}` | {seed.get('kind', 'intent')} | "
        f"{safe_cell(seed.get('intention', ''), 220)} | {ac_refs} | {safe_cell(surfaces, 220)} | {parallelizable} |"
    )


def render_context_signal_inline(signal: dict[str, Any]) -> str:
    status = signal.get("status", "Pending")
    source = signal.get("source", "[PENDING DOMAIN CONTEXT]")
    summary = safe_cell(signal.get("summary", ""), 220)
    anchor = render_anchor_inline(signal.get("anchor", {}))
    if anchor:
        return f"{status}: {source} - {summary} ({anchor})"
    return f"{status}: {source} - {summary}"


def render_anchor_inline(anchor: object) -> str:
    if not isinstance(anchor, dict):
        return ""
    source_path = str(anchor.get("source_path", "")).strip()
    line_start = int(anchor.get("line_start", 0) or 0)
    line_end = int(anchor.get("line_end", 0) or 0)
    section_path = str(anchor.get("section_path", "")).strip()
    if not source_path or line_start <= 0 or line_end < line_start:
        return ""
    location = f"{source_path}:{line_start}-{line_end}"
    return f"Anchor: {location}; section: {safe_cell(section_path or 'N/A', 120)}"


def render_bullet_list(items: list[str]) -> str:
    if not items:
        return "- [PENDING DOMAIN CONTEXT]"
    return "\n".join(f"- {item}" for item in items)


def render_story(project_id: str, epic_id: str, story: dict[str, Any]) -> str:
    rows = "\n".join(
        f"| {criterion['id']} | {criterion.get('classification', 'acceptance')} | Given {criterion['given']}, When {criterion['when']}, Then {criterion['then']}. |"
        for criterion in story["acceptance"]
    )
    normalized_reqs = [item for item in story.get("trace", []) if EARS_REQUIREMENT_ID_RE.match(str(item))]
    normalized_req_text = ", ".join(f"`{item}`" for item in normalized_reqs) or "`N/A`"
    dor = story.get("dor", {})
    dod = story.get("dod", {})
    return f"""---
id: {story['id']}
project: {project_id}
parent_epic: {epic_id}
status: {story.get('status', 'Draft')}
owner: "{story.get('owner', '')}"
label: {story['label']}
type: {story['type']}
trace:
{frontmatter_list(story['trace'])}
---

# {story['id']} - {story['title']}

This file mirrors the story embedded in its parent epic so quality and traceability tooling can address the story as an individual node.

## User Story

As a target user, I want {story['goal'].lower()} so that {story['benefit'].lower()}

## Context References

| Context Type | Source |
| --- | --- |
| Product requirement | `REQ-001`, `PRD-001`, `SPEC-001`, `{story['fr']}`, `{story['jtbd']}` |
| Normalized EARS requirements | {normalized_req_text} |
| Backlog context pack | `08_context_packs/backlog_generation.json` |
| Retrieved signal | `{story['context']['artifact_id']}` ({story['context']['artifact_type']}) |

## Domain Context Coverage

{render_domain_context_coverage(story.get('domain_coverage', []))}

## Agent Execution Contract

{render_agent_execution_contract(story.get('execution_contract', {}))}

## Retrieval Plan For Execution Agents

{render_execution_retrieval_plan(story.get('execution_contract', {}).get('retrieval_plan', []))}

{render_task_seed_contract_section(story.get('task_seed_contract'))}

## Functional Slice

- Slicing pattern: {story['slicing']}.
- Slicing rationale: {story.get('slicing_rationale', '[PENDING INPUT]')}.
- Story type: {story['type']}.
- Dependencies: {', '.join(story['dependencies']) or 'None'}.
- Enables: {', '.join(story.get('enables', [])) or 'N/A'}.
- This story must deliver user-observable value or explicit quality evidence, not an isolated implementation layer.
- Missing context remains `[PENDING INPUT]` and should be resolved upstream through gaps, `/sync`, or domain context packs.

## Lifecycle

- Status: {story.get('status', 'Draft')}.
- Owner: {story.get('owner') or '[UNASSIGNED]'}.
- Update only via `/story-status {project_id} --story {story['id']} --set STATE [--owner NAME]`.

## Acceptance Criteria

| AC ID | Classification | Criterion |
| --- | --- | --- |
{rows}

## Readiness Checklist

- {gate_checkbox(dor, 'slicing_pattern_assigned')} JTBD link is present.
- {gate_checkbox(dor, 'no_blocking_trace_gaps')} Source requirement, PRD, spec, FR and context pack links are present.
- {gate_checkbox(dor, 'acceptance_criteria_classified')} Acceptance criteria are testable.
- {gate_checkbox(dor, 'readiness_score')} Required technology/design/quality context is cited or explicitly marked as pending.

{render_gate_missing_block('DoR', dor)}

## Done Checklist

- {gate_checkbox(dod, 'acceptance_evidence_traced')} Downstream acceptance evidence is traced.
- {gate_checkbox(dod, 'ready_gate_passed')} DoR remains satisfied at closure time.

{render_gate_missing_block('DoD', dod)}
"""


def render_backlog_context_summary(context: dict[str, object]) -> str:
    sections = context.get("sections", {}) if isinstance(context, dict) else {}
    if not isinstance(sections, dict) or not sections:
        return "| Need | Retrieved Signal | Artifact | Trace |\n| --- | --- | --- | --- |\n| backlog | No focused context retrieved. | N/A | N/A |"
    rows: list[str] = []
    for section, payload in sections.items():
        if not isinstance(payload, dict):
            continue
        results = payload.get("results", [])
        if not results:
            rows.append(f"| {section} | No focused context retrieved. | N/A | N/A |")
            continue
        top = results[0]
        if not isinstance(top, dict):
            continue
        trace_ids = top.get("trace_ids", [])
        trace = ", ".join(trace_ids) if isinstance(trace_ids, list) else str(trace_ids)
        rows.append(
            f"| {section} | {safe_cell(top.get('summary', 'Context retrieved'), 180)} | `{top.get('artifact_id', 'N/A')}` | {safe_cell(trace or 'N/A', 80)} |"
        )
    return "| Backlog Need | Retrieved Signal | Artifact | Trace |\n| --- | --- | --- | --- |\n" + "\n".join(rows)


def ears_trace_ids(context: dict[str, object]) -> list[str]:
    rows = context.get("ears_requirements", []) if isinstance(context, dict) else []
    if not isinstance(rows, list):
        return []
    ids: list[str] = []
    for row in rows:
        if isinstance(row, dict):
            req_id = str(row.get("id", ""))
            if EARS_REQUIREMENT_ID_RE.match(req_id):
                ids.append(req_id)
    return ids


def safe_cell(value: Any, limit: int) -> str:
    text = str(value).replace("\n", " ").replace("|", "/").strip()
    return text[:limit]
