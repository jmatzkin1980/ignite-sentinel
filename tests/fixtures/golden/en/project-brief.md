# Project Brief - [PROJECT_ID]

This brief is the mature discovery output. It reflects iterated requirement evidence and is the source handoff for PRD, specs, backlog, acceptance criteria, and tests.

Depth principle: the brief should be complete enough to guide domain work without becoming the domain deliverable itself. Design, Technology, and Quality may deepen the analysis later in dedicated context packs.

## 1. Identidad y Valor

Initiative: Operations Risk Dashboard _(source: `00_raw/`)_

Main pain:
- Domains: product, functional, quality

Outcome and metrics:
- Expected outcome: "Objective: let operations leads review risk queues before the daily meeting." _(source: `00_raw/`)_
- Metric: `30 percent` — "Metric: reduce manual preparation by 30 percent in the first release month." _(source: `00_raw/`)_

## 2. Lente de Negocio: Actores y Necesidades

- Objective: let operations leads review risk queues before the daily meeting. _(source: `00_raw/`)_
- Users: operations leads. _(source: `00_raw/`)_

## 3. Lente de Producto: Proceso y Journey

- Current state (as-is): "Metric: reduce manual preparation by 30 percent in the first release month." _(source: `00_raw/`)_
- Target process (to-be): tracked by `GAP-PRODUCT-ASIS-TOBE`.
- In scope: "In scope: read-only risk dashboard for open queues." _(source: `00_raw/`)_
- Out of scope: "Out of scope: editing cases." _(source: `00_raw/`)_

### No-Objetivos (Non-Goals)

- No non-goals recorded: no out-of-scope/not-applicable gap closures or scope decisions exclude work yet. Populated only from governed data; never invented.

## 4. Lente de Diseno: Flujos y Resiliencia UX

- [PENDING INPUT]: no evidence in client input yet; tracked by `GAP-DESIGN-FLOW`. Provide via the domain context pack.

Sweet spot: identify affected journeys, screens, decisions, states, and UX constraints; detailed prototypes and final interaction specs belong in the design context pack.

## 5. Lente Tecnico: Datos, Conectividad y Arquitectura

- [PENDING INPUT]: no evidence in client input yet; tracked by `GAP-TECH-DATA-SOURCE`. Provide via the domain context pack.

Data and contract depth: include key entities, critical fields, and contract direction only when needed; exhaustive dictionaries, schemas, and sequence diagrams belong in the technology context pack.

## 6. Gobernanza y Restricciones

- [PENDING INPUT]: no evidence in client input yet; tracked by `GAP-GOVERNANCE-CONSTRAINTS`. Provide via the domain context pack.

Auditability and traceability expectations: all downstream artifacts must cite this brief and raw evidence.

## 7. Decisiones, Seeds e Inferencias

### Seeds Confirmadas o Pendientes

| Seed ID | Lens | Origin Type | Origin Ref | Atomic Statement | Status | Node Type |
| --- | --- | --- | --- | --- | --- | --- |
| SEED-001 | business | INPUT | `RAW-001` | Users: operations leads. | KNOWN | USER_CONTEXT |
| SEED-002 | product | INPUT | `RAW-001` | In scope: read-only risk dashboard for open queues. Out of scope: editing cases. | KNOWN | SCOPE_RULE |
| SEED-003 | business | INPUT | `RAW-001` | Metric: reduce manual preparation by 30 percent in the first release month. | PENDING_SOURCE | METRIC |
| SEED-004 | business | INPUT | `RAW-001` | Business rules, exclusions, or decision rules are not explicit enough for downstream slicing. | PENDING | GAP_PLACEHOLDER |
| SEED-005 | product | INPUT | `RAW-001` | Persona attributes are not complete enough for a PRD: goals, pain points, proficiency, and usage frequency are unclear. | PENDING | GAP_PLACEHOLDER |
| SEED-006 | business | INPUT | `RAW-001` | Quantitative metric appears without an explicit source or baseline. | PENDING | GAP_PLACEHOLDER |
| SEED-007 | business | INPUT | `RAW-001` | A metric, KPI, or indicator concept is named without its definition, formula, unit, source, or threshold. | PENDING | GAP_PLACEHOLDER |
| SEED-008 | product | INPUT | `RAW-001` | Current state and target state are not both explicit enough to compare impact. | PENDING | GAP_PLACEHOLDER |
| SEED-009 | product | INPUT | `RAW-001` | Backlog slicing signals are not explicit enough: first value slice, workflow paths, variants, rule deferral, or story boundaries are unclear. | PENDING | GAP_PLACEHOLDER |
| SEED-010 | product | INPUT | `RAW-001` | Functional requirements are not decomposed with source-backed acceptance criteria. | PENDING | GAP_PLACEHOLDER |

### Decisiones

| Decision ID | Status | Parent | Decision Needed |
| --- | --- | --- | --- |
| DEC-001 | PENDING | `REQ-001` | Confirm scope, success criteria, and implementation constraints with stakeholders. |

### Supuestos Gobernados

- No structured evidence found yet.

### Cobertura Multi-Lente

| Lens | Reviewer Stance | Evidence Found | Critical Questions | Related Gaps |
| --- | --- | --- | --- | --- |
| business/product | Senior BA / Product Lead | Source only; no domain context folder evidence | What outcome, user, scope boundary, metric source, or priority remains ambiguous? | `GAP-BUSINESS-RULES`, `GAP-METRIC-DEFINITION`, `GAP-METRIC-SOURCE`, `GAP-PRD-PERSONA-DETAIL` |
| product | Product Strategist | Source only; no domain context folder evidence | Is the as-is/to-be delta, rule set, dependency map, and rollout path clear enough to shape PRD and backlog? | `GAP-BACKLOG-SLICING-READINESS`, `GAP-BUSINESS-RULES`, `GAP-DELIVERY-READINESS`, `GAP-PRD-FR-AC`, `GAP-PRODUCT-ASIS-TOBE` |
| technical | Tech Lead | Source only; no domain context folder evidence | Which systems, endpoint/event surfaces, create/modify/reuse decisions, security, observability, or ownership constraints are required before Technology can deepen the design? | `GAP-BACKEND-SURFACE`, `GAP-BACKLOG-ENABLERS`, `GAP-FRONTEND-SURFACE`, `GAP-TECH-DATA-SOURCE`, `GAP-TECH-DEEP-DIVE-INPUT`, `GAP-TECH-NFR` |
| design | UX/UI Designer | Source only; no domain context folder evidence | Which journey, screens, states, error/empty/loading behavior, or accessibility requirements are unresolved? | `GAP-DESIGN-FLOW`, `GAP-DESIGN-PROTOTYPE-INPUT`, `GAP-DESIGN-STATES` |
| quality | Quality Lead | Source only; no domain context folder evidence | What acceptance criteria, risks, negative paths, stale/missing data cases, or test evidence are missing? | `GAP-ACCEPTANCE`, `GAP-PRD-NFR-KPI`, `GAP-QUALITY`, `GAP-QUALITY-HANDOFF` |

### Inferencias Controladas

- Any inference must name the source signal and the risk if wrong.
- Inferences cannot close critical or high gaps without client/domain confirmation.

## 8. Radar de Incertidumbres: GAPs

- `GAP-BUSINESS-RULES` (business, medium): Business rules, exclusions, or decision rules are not explicit enough for downstream slicing.
- `GAP-PRD-PERSONA-DETAIL` (business, medium): Persona attributes are not complete enough for a PRD: goals, pain points, proficiency, and usage frequency are unclear.
- `GAP-METRIC-SOURCE` (business, medium): Quantitative metric appears without an explicit source or baseline.
- `GAP-METRIC-DEFINITION` (business, medium): A metric, KPI, or indicator concept is named without its definition, formula, unit, source, or threshold.
- `GAP-PRODUCT-ASIS-TOBE` (product, medium): Current state and target state are not both explicit enough to compare impact.
- `GAP-BACKLOG-SLICING-READINESS` (product, medium): Backlog slicing signals are not explicit enough: first value slice, workflow paths, variants, rule deferral, or story boundaries are unclear.
- `GAP-PRD-FR-AC` (product, medium): Functional requirements are not decomposed with source-backed acceptance criteria.
- `GAP-QUALITY` (quality, medium): Quality or testability expectations are not explicit.
- `GAP-QUALITY-HANDOFF` (quality, medium): Quality handoff is not explicit enough: critical flows, edge cases, test data, regression risks, or evidence expectations are unclear.
- `GAP-PRD-NFR-KPI` (quality, medium): NFRs, KPIs, targets, measurement method, or timeframe are not explicit enough for PRD governance.
- `GAP-TECH-DATA-SOURCE` (technical, medium): Data source, integration, or system ownership is not explicit in source or technology context.
- `GAP-TECH-NFR` (technical, medium): Performance, security, observability, or operational constraints are not explicit.
- `GAP-BACKLOG-ENABLERS` (technical, medium): Cross-cutting enablers are not explicit enough: implementation work that must be built in advance across frontend/backend or architecture surfaces must be tied to confirmed project functionality and boundary.
- `GAP-FRONTEND-SURFACE` (technical, medium): Frontend implementation surface is not explicit enough: affected screens, states, validations, copy, roles, or API binding needs are unclear.
- `GAP-BACKEND-SURFACE` (technical, medium): Backend implementation surface is not explicit enough: capabilities, integrations, rules, persistence, contracts, or failure behavior are unclear.
- `GAP-TECH-DEEP-DIVE-INPUT` (technical, medium): Technology has insufficient input to perform repository, architecture, endpoint/event, source-of-truth, or risk analysis.
- `GAP-GOVERNANCE-CONSTRAINTS` (compliance, medium): Governance, security, privacy, compliance, or operational restrictions are not explicit.
- `GAP-PRD-GLOSSARY-GOVERNANCE` (compliance, medium): Glossary, mandatory constraints, pending inputs, or governance/audit notes are not explicit enough for a complete PRD.
- `GAP-DELIVERY-READINESS` (delivery, medium): Dependencies, environments, ownership, timing, or rollout constraints are not explicit.
- `GAP-PRD-DEPENDENCIES-ROADMAP` (delivery, medium): Dependencies, owners, MVP scope, nice-to-haves, or roadmap are not explicit enough for PRD execution planning.
- `GAP-PRD-ROLLOUT-ENVIRONMENTS` (delivery, medium): Rollout approach, target environments, or release constraints are not explicit enough for PRD execution planning.
- `GAP-DESIGN-FLOW` (design, medium): User journey, screen flow, or interaction model is not explicit in source or design context.
- `GAP-DESIGN-STATES` (design, medium): Required UI states for loading, empty, error, and recovery are not explicit.
- `GAP-DESIGN-PROTOTYPE-INPUT` (design, medium): The requirement does not make clear what Design must prototype or validate in user flows.

## 9. Preparacion para PRD, Specs y Backlog

- PRD can expand this brief only from confirmed seeds, decisions, context folders, and traceable source material.
- Specs must preserve system boundaries, data ownership, UX states, NFRs, and acceptance strategy.
- Backlog must be dev-ready, testable, vertically sliced, and linked to requirement, brief, PRD, acceptance criteria, tests, and changes.
- Backlog slicing must not split below the value boundary. A small story must remain meaningful, testable, and useful by itself.
- Cross-cutting enablers are implementation work, frontend/backend/architecture, that must be built in advance to support confirmed functionality across stories, epics, FRs, or implementation surfaces.
- A valid enabler names the capability boundary it supports, why it must be built earlier, which risk/dependency it reduces, and what objective evidence proves completion.
- Generic setup, environment availability, broad infrastructure hardening, or statements such as "make an internal tool accessible" are operational preconditions or external tasks unless tied to confirmed project functionality and implementation evidence.

### Backlog Readiness Signals

| Signal | Expected Evidence | If Missing |
| --- | --- | --- |
| First value slice | The smallest observable increment that validates user/business value. | Open `GAP-BACKLOG-SLICING-READINESS`. |
| Slice boundaries | Paths, variants, rule deferral, and the point where smaller splits stop producing value. | Open `GAP-BACKLOG-SLICING-READINESS`. |
| Cross-cutting enablers | Frontend/backend/architecture work from SAD, as-is/to-be architecture, design prototypes, or specs that must be built in advance to support confirmed functionality. | Open `GAP-BACKLOG-ENABLERS`. |
| Preconditions vs backlog | Operational setup that must exist but should not become a loose backlog item. | Keep as dependency/precondition, not a user story. |

## 10. PRD Coverage Readiness

| PRD Section | Required Discovery Signal | Evidence Source | If Missing |
| --- | --- | --- | --- |
| Personas | Primary/secondary personas, goals, pains, proficiency, usage frequency, impacted teams. | `01_discovery/identity_seeds.md`, `00_raw/01_business_context/` | Open `GAP-PRD-PERSONA-DETAIL`. |
| Functional Requirements | Source-backed FRs, priority, and acceptance criteria per FR. | `02_requirements/requirements.md`, `01_discovery/lens_review.md`, quality context | Open `GAP-PRD-FR-AC`. |
| NFRs and KPIs | Security, privacy, reliability, auditability, compatibility, targets, measurement method, timeframe. | `00_raw/04_quality_context/`, governance notes, decisions | Open `GAP-PRD-NFR-KPI`. |
| JTBD Traceability | Core, secondary, emotional/social jobs mapped to FRs. | `01_discovery/discovery_log.md`, `identity_seeds.md` | Keep traceability gap visible. |
| Execution Plan | Dependencies, owners, MVP, nice-to-haves, roadmap, rollout constraints. | `00_raw/01_business_context/`, `07_changes/03_domain_updates/` | Open `GAP-PRD-DEPENDENCIES-ROADMAP`. |
| Governance | Mandatory constraints, glossary, pending inputs, decisions, assumptions, audit trail. | `01_discovery/decisions.md`, `gaps.md`, context folders | Open `GAP-PRD-GLOSSARY-GOVERNANCE`. |

PRD generation must retrieve focused context for each row instead of rereading the full workspace. Any section that lacks enough evidence should be explicit as `[PENDING INPUT]`, not invented.

## 11. Domain Context Pack Requests

| Domain | Minimum Brief Signal | Expected Deepening Outside This Brief |
| --- | --- | --- |
| Design | Affected users, journeys, screens, states, copy constraints, and visual evidence references. | User flows, prototypes, accessibility notes, interaction specs, and visual QA criteria. |
| Technology | Systems, endpoint/event inventory, create/modify/reuse decision, ownership, source of truth, constraints, and risks. | Architecture diagrams, sequence diagrams, contracts, schemas, data dictionaries, deployment concerns, and NFR implementation detail. |
| Frontend | Affected surfaces, roles, states, validations, copy, analytics, and compatibility constraints. | Component mapping, API binding detail, state management, error handling implementation, and UI test plan. |
| Backend | Capabilities, integrations, rules, persistence/source-of-truth needs, security, observability, and failure behavior. | Service design, database/schema changes, API contracts, orchestration detail, and integration test strategy. |
| Quality | Acceptance strategy, critical paths, edge cases, risk areas, test data needs, and trace expectations. | Test cases, automation approach, regression suite, coverage map, and evidence requirements. |
