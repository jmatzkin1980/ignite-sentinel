# PRD - [PROJECT_ID]

# [PROJECT_ID] - Strategic Foundation

## 1. Executive Summary And Problem Statement

This PRD expands the mature discovery brief into a human-readable product document for Business, Product, Technology, Design, Quality, and Delivery. It must explain what will be implemented, why it matters, how success is measured, and which evidence justifies each downstream decision.

- Mature source: `02_requirements/project-brief.md`
- Discovery handoff: `02_requirements/project-brief.md` when present
- Trace anchors: `REQ-001`, `PRD-001`
- Context pack used: `08_context_packs/specs_generation.json`

### Problem / Pain

- Initiative: Operations Risk Dashboard _(source: `00_raw/`)_
- Outcome: "Objective: let operations leads review risk queues before the daily meeting." _(source: `00_raw/`)_
- KPI: `30 percent` from "Metric: reduce manual preparation by 30 percent in the first release month." _(source: `00_raw/`)_

### Expected Outcome

The outcome above is compiled from source evidence. Any missing outcome or measurement detail remains tracked in discovery gaps rather than invented here.

## 2. Project Scope

### In Scope

- `[PENDING INPUT]` - resolve `GAP-PRODUCT-ASIS-TOBE` before treating this section as evidence-backed.
- In scope: "In scope: read-only risk dashboard for open queues." _(source: `00_raw/`)_
- Out of scope: "Out of scope: editing cases." _(source: `00_raw/`)_

### Out of Scope

Items not backed by the brief, confirmed seeds, decisions, or retrieved domain context stay outside the PRD scope until a traced `/sync` or gap-resolution event confirms them.

## 3. Users And Personas

| ID | Persona Evidence | Source |
| --- | --- | --- |
| P-01 | Objective: let operations leads review risk queues before the daily meeting. | `REQ-001`, `00_raw/` |
| P-02 | Users: operations leads. | `REQ-001`, `00_raw/` |

# [PROJECT_ID] - Core Requirements

## 4. Functional Requirements

| ID | Requirement | Priority | Source |
| --- | --- | --- | --- |
| FR-E01 | When queue metrics are available, the system shall display open risk queues. | Must Have | `REQ-EARS-001` |
| FR-E02 | When a case breaches SLA, the system shall flag the queue as high risk. | Must Have | `REQ-EARS-002` |
| FR-E03 | When a queue has no open cases, the system shall hide risk indicators. | Must Have | `REQ-EARS-003` |
| FR-E04 | While risk data is stale, the system shall show a stale data warning. | Must Have | `REQ-EARS-004` |
| FR-E05 | If the metrics service is unavailable, then the system shall show risk status unknown. | Must Have | `REQ-EARS-005` |
| FR-E06 | Where audit logging is enabled, the system shall record dashboard access. | Must Have | `REQ-EARS-006` |
| FR-A07 | When queue metrics are available, the system shall display open risk queues. _(`GAP-ACCEPTANCE` / `CHG-001`)_ | Must Have | `identity_seeds.md` |

### Confirmed EARS Requirements

| ID | EARS Pattern | Testable Statement | Source |
| --- | --- | --- | --- |
| `REQ-EARS-001` | event | When queue metrics are available, the system shall display open risk queues. | GAP-ACCEPTANCE` / `CHG-001 |
| `REQ-EARS-002` | event | When a case breaches SLA, the system shall flag the queue as high risk. | GAP-ACCEPTANCE` / `CHG-002 |
| `REQ-EARS-003` | event | When a queue has no open cases, the system shall hide risk indicators. | GAP-ACCEPTANCE` / `CHG-003 |
| `REQ-EARS-004` | state | While risk data is stale, the system shall show a stale data warning. | GAP-ACCEPTANCE` / `CHG-004 |
| `REQ-EARS-005` | unwanted | If the metrics service is unavailable, then the system shall show risk status unknown. | GAP-ACCEPTANCE` / `CHG-005 |
| `REQ-EARS-006` | optional | Where audit logging is enabled, the system shall record dashboard access. | GAP-ACCEPTANCE` / `CHG-006 |

### FR-01 Acceptance Criteria

Acceptance criteria are compiled from confirmed EARS rows, confirmed gap answers, or functional evidence above. Criteria that are still missing remain visible in discovery gaps and must not be invented in this PRD.

## 5. Non-Functional Requirements

- `[PENDING INPUT]` - resolve `GAP-PRD-NFR-KPI` before treating this section as evidence-backed.
- `[PENDING INPUT]` - resolve `GAP-TECH-NFR` before treating this section as evidence-backed.

## 6. Business Success Criteria (KPIs)

| KPI ID | Description | Target | Measurement Method | Source |
| --- | --- | --- | --- | --- |
| KPI-01 | Metric: reduce manual preparation by 30 percent in the first release month. | 30 percent | Confirmed evidence or gap response | `REQ-001`, `00_raw/` |

# [PROJECT_ID] - Jobs Traceability

## 7. Jobs to Be Done

### 7a. Core Functional Job

**JTBD-01:** When the primary user faces the source scenario, they need to complete the primary job so that the expected business or operational outcome is achieved. `[Source: REQ-001]`

### 7b. Related / Secondary Jobs

**JTBD-02:** When an operator, owner, or downstream system participates in the workflow, they need confirmed data, rules, and failure behavior so that the capability remains reliable and auditable.

**JTBD-03:** When Quality validates the workflow, it needs acceptance criteria, edge cases, regression expectations, and traceability.

### 7c. Emotional and Social Jobs

**JTBD-E01:** When users rely on the new capability, they need confidence that the state/result is explainable and backed by confirmed evidence.

`[PENDING INPUT] - GAP-PRD-GLOSSARY-GOVERNANCE`: confirm whether a social/reputational job exists.

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

# [PROJECT_ID] - Execution Plan

## 8. Dependency Map

| Dep ID | Dependency | Type | Description | Owner | Impact if Unavailable | Source |
| --- | --- | --- | --- | --- | --- | --- |
| DEP-01 | Primary product/domain owner | Business | Confirms scope, value, and acceptance. | `[PENDING INPUT]` | PRD cannot be accepted. | `GAP-PRD-DEPENDENCIES-ROADMAP` |
| DEP-02 | Technology owner / source system | Technical | Confirms integrations, data ownership, contracts, and constraints. | `[PENDING INPUT]` | Implementation may block or invent architecture. | `GAP-TECH-DATA-SOURCE` |
| DEP-03 | Design/content owner | Design | Confirms journeys, states, copy, and prototype needs. | `[PENDING INPUT]` | UI/backlog may miss user states. | `GAP-DESIGN-FLOW` |
| DEP-04 | Quality owner | Quality | Confirms test strategy, evidence, and regression scope. | `[PENDING INPUT]` | Stories may not be testable. | `GAP-QUALITY-HANDOFF` |

## 9. Risks And Assumptions

### 9a. Assumption Register

| ID | Assumption | Impact if Wrong | Source Basis | Status |
| --- | --- | --- | --- | --- |
| ASM-01 | Details absent from confirmed evidence remain pending and must not be silently converted into backlog scope. | Rework and loss of trust. | Sentinel guardrail | Active |
| ASM-02 | Domain context in memory is sufficient to draft PRD sections, with gaps where evidence is missing. | PRD may be too generic. | `08_context_packs/specs_generation.json` | Active |

### 9b. Risk Register

| ID | Risk | Likelihood | Impact | Mitigation | Source |
| --- | --- | --- | --- | --- | --- |
| RSK-01 | PRD section appears complete but is based on weak evidence. | Medium | High | Cite sources and keep `[PENDING INPUT]` markers. | `GAP-PRD-*` |
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

# [PROJECT_ID] - Governance

## Output Enhancement Suggestions

### Missing Information Notes

- `[PENDING INPUT - Personas]`: resolve `GAP-PRD-PERSONA-DETAIL`.
- `[PENDING INPUT - FR/AC]`: refine FRs and ACs from confirmed product and quality evidence.
- `[PENDING INPUT - NFR/KPI]`: confirm measurable targets, owners, method, and timeframe.
- `[PENDING INPUT - Dependencies/Roadmap]`: confirm owners, MVP, phases, dates, and rollout constraints.
- `[PENDING INPUT - Glossary/Governance]`: confirm mandatory terms, constraints, audit expectations, and decisions.

### Context Retrieved From Memory

| PRD / Specs Need | Retrieved Signal | Artifact | Trace |
| --- | --- | --- | --- |
| strategic_foundation | ## 1. Identidad y Valor  Initiative: Operations Risk Dashboard _(source: `00_raw/`)_  Main pain: - Domains: product, functional, quality  Outcome and metrics: - Expected outcome: " | `REQ-003` | REQ-003 |
| personas | / PRD Section / Required Discovery Signal / Evidence Source / If Missing / / --- / --- / --- / --- / / Personas / Primary/secondary personas, goals, pains, proficiency, usage frequ | `REQ-003` | REQ-003 |
| functional_requirements | - `GAP-BUSINESS-RULES` (business, medium): Business rules, exclusions, or decision rules are not explicit enough for downstream slicing. - `GAP-PRD-PERSONA-DETAIL` (business, mediu | `REQ-003` | REQ-003 |
| nfr_kpi | ## 5. Lente Tecnico: Datos, Conectividad y Arquitectura  - [PENDING INPUT]: no evidence in client input yet; tracked by `GAP-TECH-DATA-SOURCE`. Provide via the domain context pack. | `REQ-003` | REQ-003 |
| jtbd_traceability | / PRD Section / Required Discovery Signal / Evidence Source / If Missing / / --- / --- / --- / --- / / Personas / Primary/secondary personas, goals, pains, proficiency, usage frequ | `REQ-003` | REQ-003 |
| execution_plan | - `GAP-BUSINESS-RULES` (business, medium): Business rules, exclusions, or decision rules are not explicit enough for downstream slicing. - `GAP-PRD-PERSONA-DETAIL` (business, mediu | `REQ-003` | REQ-003 |
| governance | / PRD Section / Required Discovery Signal / Evidence Source / If Missing / / --- / --- / --- / --- / / Personas / Primary/secondary personas, goals, pains, proficiency, usage frequ | `REQ-003` | REQ-003 |
| backlog_handoff | - PRD can expand this brief only from confirmed seeds, decisions, context folders, and traceable source material. - Specs must preserve system boundaries, data ownership, UX states | `REQ-003` | REQ-003 |

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
| Source | `02_requirements/project-brief.md` |
| Context Pack | `08_context_packs/specs_generation.json` |

## Decisions Made

1. PRD sections are populated only from brief, traceable artifacts, and focused memory retrieval.
2. Missing evidence remains visible as `[PENDING INPUT]` or a `GAP-*` reference.
3. `specs.md` is the downstream agent contract and should be used before backlog slicing.
