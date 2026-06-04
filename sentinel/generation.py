from __future__ import annotations

from typing import Any

from .memory import ContextBroker, get_multi_domain_context
from .maturity import evaluate
from .traceability import add_edge, add_node, nodes_by_type
from .workspace import read_json, state_path, update_state, workspace_path, write_json


PRD_SECTION_QUERIES = {
    "strategic_foundation": "problem outcome scope personas pain success metrics",
    "personas": "users personas actors goals pain points proficiency frequency impacted teams",
    "functional_requirements": "functional requirements acceptance criteria given when then business rules priority",
    "nfr_kpi": "non functional requirements security privacy reliability auditability kpi target measurement baseline timeframe",
    "jtbd_traceability": "jobs to be done jtbd emotional social traceability functional requirements",
    "execution_plan": "dependencies owners mvp roadmap rollout environments team delivery",
    "governance": "constraints compliance privacy glossary pending inputs decisions assumptions audit trail",
    "backlog_handoff": "epics user stories slicing acceptance criteria traceability progressive disclosure",
}


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
    generation_context = build_specs_generation_context(project_id, req_text)
    context["prd_sections"] = generation_context["sections"]
    state = read_json(state_path(project_id), {})
    language = str(state.get("project_language", "es")).lower()
    prd_path = base / "03_specs" / "prd.md"
    specs_path = base / "03_specs" / "specs.md"
    prd_path.write_text(render_prd(project_id, req_text, context, source_path.name, language), encoding="utf-8")
    specs_path.write_text(render_specs(project_id, req_text, context, source_path.name), encoding="utf-8")
    prd_id = add_node(project_id, "PRD", "prd", prd_path, "Human-readable PRD", domain="product")
    spec_id = add_node(project_id, "SPEC", "spec", specs_path, "AI-friendly specification", domain="product")
    parent_trace_ids: list[str] = []
    for req in nodes_by_type(project_id, "requirement"):
        add_edge(project_id, req["id"], prd_id, "elaborates")
        parent_trace_ids.append(req["id"])
    for brief in nodes_by_type(project_id, "project_brief"):
        add_edge(project_id, brief["id"], prd_id, "elaborates")
        parent_trace_ids.append(brief["id"])
    add_edge(project_id, prd_id, spec_id, "agentizes")
    trace_ids = [*parent_trace_ids, prd_id, spec_id]
    broker = ContextBroker(project_id)
    broker.index_artifact(
        prd_id, "prd", prd_path, prd_path.read_text(encoding="utf-8"), trace_ids=trace_ids
    )
    broker.index_artifact(
        spec_id, "spec", specs_path, specs_path.read_text(encoding="utf-8"), trace_ids=trace_ids
    )
    update_state(project_id, phase="specs_completed", health="CLEAN")
    return {"prd_id": prd_id, "spec_id": spec_id, "prd_path": str(prd_path), "path": str(specs_path)}


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


def build_specs_generation_context(project_id: str, req_text: str) -> dict[str, Any]:
    broker = ContextBroker(project_id)
    sections: dict[str, Any] = {}
    for section, query in PRD_SECTION_QUERIES.items():
        results = broker.retrieve(
            f"{query}\n\n{req_text[:1200]}",
            "specs_generation",
            limit=5,
            max_chars=2200,
            summary_only=True,
        )
        sections[section] = {
            "query": query,
            "results": [
                {
                    "artifact_id": row.get("artifact_id", "N/A"),
                    "artifact_type": row.get("artifact_type", "artifact"),
                    "domain": row.get("domain", "unknown"),
                    "section_path": row.get("section_path", ""),
                    "summary": row.get("summary", row.get("text", ""))[:240],
                    "why_retrieved": row.get("why_retrieved", ""),
                    "trace_ids": row.get("trace_ids", []),
                }
                for row in results
            ],
        }
    pack = {"project_id": project_id, "workflow": "specs_generation", "sections": sections}
    write_json(workspace_path(project_id) / "08_context_packs" / "specs_generation.json", pack)
    return pack


def render_prd(project_id: str, req_text: str, context: dict[str, object], source_name: str, language: str) -> str:
    if language == "en":
        return render_prd_full(project_id, req_text, context, source_name, "en")
    return render_prd_full(project_id, req_text, context, source_name, "es")


def render_prd_full(project_id: str, req_text: str, context: dict[str, object], source_name: str, language: str) -> str:
    english = language == "en"
    section_context = render_prd_section_context(context)
    title = "Executive Summary And Problem Statement" if english else "Resumen ejecutivo y planteamiento del problema"
    scope = "Project Scope" if english else "Alcance del proyecto"
    personas = "Users And Personas" if english else "Usuarios y personas"
    core = "Core Requirements" if english else "Core Requirements"
    fr_title = "Functional Requirements" if english else "Requerimientos funcionales"
    nfr_title = "Non-Functional Requirements" if english else "Requerimientos no funcionales"
    kpi_title = "Business Success Criteria (KPIs)" if english else "Criterios de exito del negocio (KPIs)"
    jtbd_title = "JTBD Traceability" if english else "JTBD Traceability"
    execution = "Execution Plan" if english else "Execution Plan"
    governance = "Governance" if english else "Governance"
    pending = "[PENDING INPUT]"
    return f"""# PRD - {project_id}

# {project_id} - Strategic Foundation

## 1. {title}

This PRD expands the mature discovery brief into a human-readable product document for Business, Product, Technology, Design, Quality, and Delivery. It must explain what will be implemented, why it matters, how success is measured, and which evidence justifies each downstream decision.

- Mature source: `02_requirements/{source_name}`
- Discovery handoff: `02_requirements/project-brief.md` when present
- Trace anchors: `REQ-001`, `PRD-001`
- Context pack used: `08_context_packs/specs_generation.json`

### Problem / Pain

{bounded_text(req_text, 1800)}

### Expected Outcome

| ID | Outcome | Source |
| --- | --- | --- |
| OUT-001 | Deliver the primary business or operational result described by the mature requirement. | `REQ-001`, `project-brief.md` |
| OUT-002 | Keep any missing metric, owner, or baseline explicit as `{pending}`. | `GAP-PRD-NFR-KPI` |

## 2. {scope}

### In Scope

- Functional capabilities required to satisfy `OUT-001`.
- Existing behavior that must be preserved and made testable.
- Product, technology, design, quality, governance, and delivery constraints recovered through local memory.

### Out of Scope

- Any item not backed by the brief, confirmed seeds, decisions, or retrieved domain context.
- Detailed implementation contracts that belong in technology/design/quality context packs.
- Sensitive client data, credentials, URLs, payloads, or identifiers in generated PRD/spec artifacts.

## 3. {personas}

### Primary Personas

| ID | Attribute | Value |
| --- | --- | --- |
| P-01 | Name/Role | Primary user or operator from `GAP-USERS` / `identity_seeds.md`; `{pending}` if not confirmed. |
| P-01 | Goals | Complete the primary job and obtain the expected outcome. |
| P-01 | Pain Points | Current pain from source requirement; keep unconfirmed pains as `{pending}`. |
| P-01 | Technical Proficiency | `{pending} - GAP-PRD-PERSONA-DETAIL` |
| P-01 | Usage Frequency | `{pending} - GAP-PRD-PERSONA-DETAIL` |

### Secondary Personas

| ID | Attribute | Value |
| --- | --- | --- |
| P-02 | Name/Role | Secondary actor, impacted team, or system owner. |
| P-02 | Goals | Support, approve, operate, consume, or audit the capability. |
| P-02 | Pain Points | `{pending} - GAP-PRD-PERSONA-DETAIL` |

# {project_id} - {core}

## 4. {fr_title}

| ID | Requirement | Priority | Source |
| --- | --- | --- | --- |
| FR-01 | The system shall deliver the primary end-to-end capability described by the mature requirement. | Must Have | `REQ-001`, `project-brief.md` |
| FR-02 | The system shall preserve explicitly unchanged behavior and compatibility constraints. | Must Have | `GAP-SCOPE`, `GAP-PRODUCT-ASIS-TOBE` |
| FR-03 | The system shall expose or consume the required data/integration signals identified by Technology context. | Must Have | `GAP-TECH-DATA-SOURCE`, `GAP-BACKEND-SURFACE` |
| FR-04 | The user-facing experience shall cover affected journeys, states, validations, and copy constraints. | Must Have | `GAP-DESIGN-FLOW`, `GAP-DESIGN-STATES`, `GAP-FRONTEND-SURFACE` |
| FR-05 | The system shall preserve traceability from requirement to acceptance criteria and tests. | Must Have | `GAP-ACCEPTANCE`, `GAP-QUALITY-HANDOFF` |

**FR-01 Acceptance Criteria:**

- Given the primary user has valid context and inputs, When they execute the primary workflow, Then the expected business outcome is achieved and traceable to `REQ-001`.
- Given required information is missing or invalid, When the user attempts the workflow, Then the system presents the confirmed recoverable behavior or records `{pending}`.

**FR-02 Acceptance Criteria:**

- Given existing behavior is marked as unchanged, When regression tests run, Then unchanged behavior remains compatible.
- Given an out-of-scope request appears, When backlog is generated, Then it is excluded or marked as a change/gap.

**FR-03 Acceptance Criteria:**

- Given a required upstream/downstream dependency is available, When the system requests or emits data, Then the source of truth and owner are traceable.
- Given integration data is unavailable, stale, or malformed, When the system handles the case, Then the failure behavior follows confirmed quality and technology context.

**FR-04 Acceptance Criteria:**

- Given the user enters an affected surface or journey, When the relevant state occurs, Then loading, empty, error, disabled, success, permission, and recovery states are handled as confirmed or flagged.
- Given copy or messaging changes are required, When UI is rendered, Then approved copy is used and unchanged messages remain unchanged.

**FR-05 Acceptance Criteria:**

- Given a story is derived from this PRD, When QA reviews it, Then it cites `REQ-001`, `PRD-001`, `SPEC-001`, FR ID, and acceptance criteria.

## 5. {nfr_title}

| ID | Category | Requirement | Target | Source |
| --- | --- | --- | --- | --- |
| NFR-01 | Security/Privacy | Respect confirmed security, privacy, and compliance constraints. | `{pending}` if no target/source exists. | `GAP-GOVERNANCE-CONSTRAINTS` |
| NFR-02 | Reliability | Define expected behavior for external failures, missing data, retries, or recovery. | `{pending}` | `GAP-TECH-NFR`, `GAP-QUALITY-HANDOFF` |
| NFR-03 | Compatibility | Preserve confirmed existing contracts and behavior. | No breaking change unless explicitly approved. | `GAP-SCOPE` |
| NFR-04 | Observability/Auditability | Ensure logs, metrics, audit records, and trace evidence meet governance needs. | `{pending}` | `GAP-PRD-NFR-KPI` |
| NFR-05 | Performance | Meet confirmed latency, throughput, or volume expectations. | `{pending}` | `GAP-TECH-NFR` |

## 6. {kpi_title}

| KPI ID | Description | Target | Measurement Method | Timeframe | Source |
| --- | --- | --- | --- | --- | --- |
| KPI-01 | Primary business or operational outcome. | `{pending}` unless confirmed. | `{pending}` | `{pending}` | `GAP-METRIC-SOURCE` |
| KPI-02 | Quality or risk reduction outcome. | `{pending}` | QA evidence / operational monitoring. | `{pending}` | `GAP-QUALITY-HANDOFF` |
| KPI-03 | Compatibility or non-regression outcome. | 0 known regressions unless otherwise defined. | Regression suite / release evidence. | Release validation. | `GAP-SCOPE` |

# {project_id} - {jtbd_title}

## 7. Jobs to Be Done

### 7a. Core Functional Job

**JTBD-01:** When the primary user faces the source scenario, they need to complete the primary job so that the expected business or operational outcome is achieved. `[Source: REQ-001]`

### 7b. Related / Secondary Jobs

**JTBD-02:** When an operator, owner, or downstream system participates in the workflow, they need confirmed data, rules, and failure behavior so that the capability remains reliable and auditable.

**JTBD-03:** When Quality validates the workflow, it needs acceptance criteria, edge cases, regression expectations, and traceability.

### 7c. Emotional and Social Jobs

**JTBD-E01:** When users rely on the new capability, they need confidence that the state/result is explainable and backed by confirmed evidence.

`{pending} - GAP-PRD-GLOSSARY-GOVERNANCE`: confirm whether a social/reputational job exists.

### 7d. Bidirectional Traceability Table (Audit)

| Req ID | Req Description | JTBD ID | Status | Notes |
| --- | --- | --- | --- | --- |
| FR-01 | Primary end-to-end capability | JTBD-01 | OK | |
| FR-02 | Preserve unchanged behavior | JTBD-02 | OK | |
| FR-03 | Data/integration signals | JTBD-02 | OK | |
| FR-04 | User-facing states/copy | JTBD-01 | OK | |
| FR-05 | Traceability to AC/tests | JTBD-03 | OK | |
| -- | Social job | JTBD-S01 | PENDING | No explicit source unless confirmed. |

## Traceability Gaps

- `GAP-PRD-FR-AC`: functional requirements and ACs may need refinement from domain context.
- `GAP-PRD-NFR-KPI`: NFR/KPI targets, measurement owner, and timeframe should be confirmed before release commitment.
- `GAP-PRD-DEPENDENCIES-ROADMAP`: owners, dependencies, MVP, and roadmap may need delivery confirmation.

# {project_id} - {execution}

## 8. Dependency Map

| Dep ID | Dependency | Type | Description | Owner | Impact if Unavailable | Source |
| --- | --- | --- | --- | --- | --- | --- |
| DEP-01 | Primary product/domain owner | Business | Confirms scope, value, and acceptance. | `{pending}` | PRD cannot be accepted. | `GAP-PRD-DEPENDENCIES-ROADMAP` |
| DEP-02 | Technology owner / source system | Technical | Confirms integrations, data ownership, contracts, and constraints. | `{pending}` | Implementation may block or invent architecture. | `GAP-TECH-DATA-SOURCE` |
| DEP-03 | Design/content owner | Design | Confirms journeys, states, copy, and prototype needs. | `{pending}` | UI/backlog may miss user states. | `GAP-DESIGN-FLOW` |
| DEP-04 | Quality owner | Quality | Confirms test strategy, evidence, and regression scope. | `{pending}` | Stories may not be testable. | `GAP-QUALITY-HANDOFF` |

## 9. Risks And Assumptions

### 9a. Assumption Register

| ID | Assumption | Impact if Wrong | Source Basis | Status |
| --- | --- | --- | --- | --- |
| ASM-01 | Details absent from confirmed evidence remain pending and must not be silently converted into backlog scope. | Rework and loss of trust. | Sentinel guardrail | Active |
| ASM-02 | Domain context in memory is sufficient to draft PRD sections, with gaps where evidence is missing. | PRD may be too generic. | `08_context_packs/specs_generation.json` | Active |

### 9b. Risk Register

| ID | Risk | Likelihood | Impact | Mitigation | Source |
| --- | --- | --- | --- | --- | --- |
| RSK-01 | PRD section appears complete but is based on weak evidence. | Medium | High | Cite sources and keep `{pending}` markers. | `GAP-PRD-*` |
| RSK-02 | Backlog agents load too much context or miss key domain signals. | Medium | Medium | Use `specs.md` retrieval plan and context pack. | `SPEC-001` |
| RSK-03 | Sensitive data leaks into generated artifacts. | Low | High | Keep local-only privacy rules and sanitize shareable outputs. | Privacy guardrail |

## 10. MVP, Nice-to-Haves, And Roadmap

### MVP Scope

- FR-01 through FR-05 when supported by confirmed evidence.
- Must include traceability and acceptance criteria for each story.

### Nice-to-Haves

- Any feature not tied to a confirmed outcome, acceptance criterion, or dependency owner.

### Roadmap

- Phase 1: close blocking PRD readiness gaps and confirm MVP.
- Phase 2: generate backlog slices from `specs.md` retrieval plan.
- Phase 3: quality audit and traceability validation.

## 11. Mandatory Constraints

- Source of truth remains workspace files; memory is retrieval aid only.
- Do not include sensitive raw payloads, credentials, URLs, account IDs, or client-specific private facts in generated framework artifacts unless explicitly approved.
- Every downstream artifact must preserve `REQ -> PRD -> SPEC -> EPIC -> US -> AC -> TC` lineage where applicable.

## 12. Suggested Or Assigned Team

| Role | Responsibility | Source |
| --- | --- | --- |
| Product / BA | Own PRD narrative, scope, FRs, KPIs, and pending inputs. | `PRD-001` |
| Technology | Own architecture, integration, contracts, source-of-truth, and NFR feasibility. | `CTX-TECH` |
| Design | Own journeys, states, copy, accessibility, and prototype evidence. | `CTX-DESIGN` |
| Quality | Own acceptance strategy, tests, regression, evidence, and readiness audit. | `CTX-QUALITY` |
| Delivery | Own dependencies, owners, timeline, rollout, and release constraints. | `GAP-DELIVERY-READINESS` |

## 13. Glossary

| Term | Definition | First Used In |
| --- | --- | --- |
| Mature requirement | Discovery output with blocking gaps closed or explicitly accepted as non-blocking. | Summary |
| PRD | Human/business product document explaining what and why. | Summary |
| Specs | Agent-friendly execution contract for progressive disclosure and backlog generation. | Traceability |
| Pending input | Explicit missing information that must not be invented. | Governance |

# {project_id} - {governance}

## Output Enhancement Suggestions

### Missing Information Notes

- `[PENDING INPUT - Personas]`: resolve `GAP-PRD-PERSONA-DETAIL`.
- `[PENDING INPUT - FR/AC]`: refine FRs and ACs from confirmed product and quality evidence.
- `[PENDING INPUT - NFR/KPI]`: confirm measurable targets, owners, method, and timeframe.
- `[PENDING INPUT - Dependencies/Roadmap]`: confirm owners, MVP, phases, dates, and rollout constraints.
- `[PENDING INPUT - Glossary/Governance]`: confirm mandatory terms, constraints, audit expectations, and decisions.

### Context Retrieved From Memory

{section_context}

### Proposed Next Meeting Agenda

1. Resolve PRD readiness gaps that affect MVP scope.
2. Confirm FR priorities and acceptance criteria with Product/Quality.
3. Confirm technical dependencies and source-of-truth ownership.
4. Confirm roadmap, owners, rollout constraints, and governance.

# Session Audit Trail

| Field | Value |
| --- | --- |
| Version | 1.0 |
| Mode | GENERATED_FROM_SENTINEL |
| Source | `02_requirements/{source_name}` |
| Context Pack | `08_context_packs/specs_generation.json` |

## Decisions Made

1. PRD sections are populated only from brief, traceable artifacts, and focused memory retrieval.
2. Missing evidence remains visible as `{pending}` or a `GAP-*` reference.
3. `specs.md` is the downstream agent contract and should be used before backlog slicing.
"""


def render_specs(project_id: str, req_text: str, context: dict[str, object], source_name: str) -> str:
    return f"""# Specs - {project_id}

## Spec Contract

- Purpose: provide an agent-friendly execution contract for backlog generation.
- Human PRD: `03_specs/prd.md`
- Mature source: `02_requirements/{source_name}`
- Trace anchors: `REQ-001`, `PRD-001`, `SPEC-001`
- Context pack: `08_context_packs/specs_generation.json`
- Rule: agents must retrieve focused context before expanding backlog slices. Do not reread the whole workspace unless the retrieval pack is insufficient.

## Requirement Snapshot

The mature requirement remains authoritative in `02_requirements/{source_name}`. This spec keeps only the execution signals agents need before progressive disclosure.

{bounded_text(req_text, 2200)}

## Backlog-Relevant Contract

| Contract Item | Rule |
| --- | --- |
| Source hierarchy | Workspace files win over memory. PRD/specs summarize, they do not replace source evidence. |
| Traceability | Every epic/story/AC must cite `REQ-001`, `PRD-001`, `SPEC-001`, and at least one FR/JTBD/rule where applicable. |
| Missing evidence | Keep `[PENDING INPUT]` or create/follow a `GAP-*`; do not invent. |
| Privacy | Do not include sensitive client data, credentials, URLs, account IDs, or raw payloads in backlog artifacts. |

## Jobs To Be Done

| JTBD ID | Context | Need | Expected Result | Source |
| --- | --- | --- | --- | --- |
| JTBD-001 | When the target user faces the scenario in `REQ-001` | Complete the primary job | Obtain the expected business outcome | `REQ-001` |

## Functional Capabilities

| Capability ID | Capability | JTBD Link | Trace Source |
| --- | --- | --- | --- |
| CAP-001 | Deliver the primary workflow described by the mature requirement. | JTBD-001 | `REQ-001`, `FR-01` |
| CAP-002 | Preserve explicitly unchanged behavior and compatibility constraints. | JTBD-002 | `FR-02` |
| CAP-003 | Make acceptance and quality evidence traceable. | JTBD-003 | `FR-05` |

## Progressive Disclosure Context Map

{render_prd_section_context(context)}

## Retrieval Plan For Backlog Agents

| Need | Suggested `/retrieve` Query | Filters | Use In Backlog |
| --- | --- | --- | --- |
| Epic value and MVP | `business outcome scope mvp kpi users` | `--workflow backlog --domain business --summary-only` | Epic outcome and priority |
| FR and AC slicing | `functional requirements acceptance criteria given when then business rules` | `--workflow backlog --domain product` | Story boundaries and ACs |
| Technical dependencies | `architecture integrations dependencies data ownership contracts failure behavior` | `--workflow backlog --domain technical` | Backend/technical stories and blockers |
| UX stories | `journey screens states validations copy accessibility unchanged behavior` | `--workflow backlog --domain design` | Frontend stories and UX acceptance |
| Quality coverage | `acceptance testability edge cases regression test data evidence` | `--workflow backlog --domain quality` | ACs, TC seeds, readiness audit |
| Open gaps | `pending input prd gaps dependencies roadmap nfr kpi` | `--workflow backlog --artifact-type gap_report` | Blockers, spikes, follow-up stories |

## Backlog Seeds

| Seed ID | Candidate Item | Type | Trace |
| --- | --- | --- | --- |
| EPIC-001 | Deliver the primary value slice from `FR-01` through `FR-05`. | Epic | `SPEC-001` |
| US-001 | Implement/enable the primary user-visible workflow. | User Story | `FR-01`, `JTBD-01` |
| US-002 | Preserve unchanged behavior and compatibility. | User Story | `FR-02` |
| US-003 | Integrate required data/source-of-truth signals. | User Story | `FR-03` |
| US-004 | Cover affected UX states, validations, and copy. | User Story | `FR-04` |
| US-005 | Produce traceable acceptance and quality evidence. | User Story | `FR-05` |

## Decision And Assumption Trail

| ID | Type | Statement | Risk If Wrong |
| --- | --- | --- | --- |
| ASM-001 | Assumption | Any detail not present in seeds, source input, or domain context remains pending confirmation. | Downstream backlog may require rework after `/sync`. |
| ASM-002 | Assumption | PRD generated enough FR/JTBD/NFR structure for first backlog slicing. | Stories may need refinement if PRD readiness gaps remain. |

## Traceability

- Parent requirement: `REQ-001`
- Parent PRD: `PRD-001`
- Mature brief: `02_requirements/project-brief.md` when present
- Context pack: `08_context_packs/specs_generation.json`
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
| Product requirement | `REQ-001`, `PRD-001`, `SPEC-001` |
| Business / Product seeds | `01_discovery/identity_seeds.md` |
| Technology context | `00_raw/02_technology_context/` if available |
| Design context | `00_raw/03_design_context/` if available |
| Quality context | `00_raw/04_quality_context/` if available |
| Retrieval plan | `03_specs/specs.md#Retrieval Plan For Backlog Agents` |

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
- [ ] Source requirement, PRD, and spec links are present.
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
            f"| {domain} | {safe_cell(top.get('summary', 'Context retrieved'), 160)} | `{top.get('artifact_id', 'N/A')}` |"
        )
    return "| Domain | Retrieved Signal | Artifact |\n| --- | --- | --- |\n" + "\n".join(rows)


def render_prd_section_context(context: dict[str, object]) -> str:
    sections = context.get("prd_sections", {}) if isinstance(context, dict) else {}
    if not isinstance(sections, dict) or not sections:
        return render_context_summary(context)
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
    return "| PRD / Specs Need | Retrieved Signal | Artifact | Trace |\n| --- | --- | --- | --- |\n" + "\n".join(rows)


def bounded_text(text: str, limit: int) -> str:
    cleaned = text.strip()
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[:limit].rstrip() + "\n\n[TRUNCATED IN GENERATED ARTIFACT - retrieve focused source context if needed]"


def safe_cell(value: Any, limit: int) -> str:
    text = str(value).replace("\n", " ").replace("|", "/").strip()
    return text[:limit]
