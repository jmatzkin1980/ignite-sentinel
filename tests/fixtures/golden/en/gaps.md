# Discovery Gaps - [PROJECT_ID]

Document version: `1.0`
Project: `[PROJECT_ID]`
Parent requirement: `REQ-001`
Audience: Client stakeholders, Product, Technology, Design, Quality, and Delivery.
Purpose: collect missing or ambiguous information so the requirement can mature into a project brief, PRD, specs, backlog, acceptance criteria, and tests.

## How To Respond

Please answer directly under each gap. A short answer is fine if it is precise. If a question belongs to another team, name the owner and add any known partial answer.

Suggested response format:

- Answer:
- Owner / source:
- Evidence or reference:
- Decision status: confirmed / pending / not applicable

## Client Response Sections

### GAP-BUSINESS-RULES - Business Rules

- Lens: `business`
- Severity: `medium`
- Status: `OPEN`
- Related requirement: `REQ-001`

Brief description:
Business rules, exclusions, or decision rules are not explicit enough for downstream slicing.

Why it matters (risk if left open):
Rules and exceptions determine validations, edge cases, and acceptance criteria.

What answering this unblocks:
PRD functional requirements/ACs, specs business rules, and Quality edge cases.

Question:
Which rules, exceptions, validations, fallbacks, or exclusions govern the behavior?

Expected response format:
Rules in EARS form when they describe behavior: If <condition/rule>, then the system shall <response>; include thresholds and exceptions.

Example of a useful answer:
A queue is high risk when more than 10 cases are within 30 minutes of SLA breach or any case is already breached.


Client / domain response:

- Answer:
- Owner / source:
- Evidence or reference:
- Decision status:


### GAP-PRD-PERSONA-DETAIL - PRD Persona Detail

- Lens: `business`
- Severity: `medium`
- Status: `OPEN`
- Related requirement: `REQ-001`

Brief description:
Persona attributes are not complete enough for a PRD: goals, pain points, proficiency, and usage frequency are unclear.

Why it matters (risk if left open):
The PRD needs personas with goals, pain points, frequency, and proficiency to guide experience, adoption, and support decisions.

What answering this unblocks:
The PRD Personas section.

Question:
What confirmed information resolves this uncertainty?

Expected response format:
Per persona: goal, pains, usage frequency, and proficiency.

Example of a useful answer:
Primary persona: central operator. Goal: resolve cases without IT. Pain: risky manual process. Frequency: daily. Proficiency: advanced internal tool.


Client / domain response:

- Answer:
- Owner / source:
- Evidence or reference:
- Decision status:


### GAP-METRIC-SOURCE - Metric Source

- Lens: `business`
- Severity: `medium`
- Status: `OPEN`
- Related requirement: `REQ-001`

Brief description:
Quantitative metric appears without an explicit source or baseline.

Evidence that triggers the question:
The metric "30 percent" appears without a source, baseline, or measurement method.

Why it matters (risk if left open):
Metrics need a source or baseline so success can be measured consistently.

What answering this unblocks:
Brief KPIs and the PRD NFRs/KPIs and measurement section.

Question:
What is the source or baseline for the quantitative metric?

Expected response format:
Metric name + baseline source/owner + target value + measurement window.

Example of a useful answer:
Baseline comes from the weekly operations report owned by Support Ops; target is to detect high-risk queues before 9:30 AM daily.

Cited candidate options (not selected):
- Option A: Confirm `30 percent` is the success target and provide source, baseline, owner, and measurement method. Local citation: `30 percent`.
- Option B: Treat `30 percent` as a directional target until source/baseline are confirmed, naming the missing evidence. Local citation: `30 percent`.
These options do not close the gap; the BA/owner must confirm an answer.


Client / domain response:

- Answer:
- Owner / source:
- Evidence or reference:
- Decision status:


### GAP-METRIC-DEFINITION - Metric Definition

- Lens: `business`
- Severity: `medium`
- Status: `OPEN`
- Related requirement: `REQ-001`

Brief description:
A metric, KPI, or indicator concept is named without its definition, formula, unit, source, or threshold.

Evidence that triggers the question:
The input mentions "metric" but does not define the metric: missing formula/unit, source, or threshold.

Why it matters (risk if left open):
A metric named without a definition, source, or threshold is not measurable or commitable and drags ambiguity into KPIs and success criteria.

What answering this unblocks:
Brief KPIs and the PRD NFRs/KPIs and measurement section.

Question:
How is each metric/KPI defined (formula, unit), what source does it come from, and what is its baseline and target threshold?

Expected response format:
Per metric: definition/formula, unit, data source/owner, baseline, and target threshold.

Example of a useful answer:
The 'resolution time' metric is the average hours between open and close, source Case Management, baseline 8h, target threshold 6h.

Cited candidate options (not selected):
- Option A: Confirm `metric` is in scope and answer the missing `Metric Definition` detail. Local citation: `metric`.
- Option B: Confirm `metric` is context-only, out of scope, or pending, and state the boundary. Local citation: `metric`.
These options do not close the gap; the BA/owner must confirm an answer.


Client / domain response:

- Answer:
- Owner / source:
- Evidence or reference:
- Decision status:


### GAP-PRODUCT-ASIS-TOBE - Current And Target Process

- Lens: `product`
- Severity: `medium`
- Status: `OPEN`
- Related requirement: `REQ-001`

Brief description:
Current state and target state are not both explicit enough to compare impact.

Why it matters (risk if left open):
The delta between current and target behavior drives impact analysis and backlog slicing.

What answering this unblocks:
Brief section 3 (as-is/to-be) and backlog slicing.

Question:
What is the current process, target process, and exact delta between them?

Expected response format:
Current behavior vs target behavior, stated as a delta.

Example of a useful answer:
Today analysts open each queue to infer risk. To-be: the list shows risk directly so they can prioritize before opening details.


Client / domain response:

- Answer:
- Owner / source:
- Evidence or reference:
- Decision status:


### GAP-BACKLOG-SLICING-READINESS - Backlog Slicing Readiness

- Lens: `product`
- Severity: `medium`
- Status: `OPEN`
- Related requirement: `REQ-001`

Brief description:
Backlog slicing signals are not explicit enough: first value slice, workflow paths, variants, rule deferral, or story boundaries are unclear.

Why it matters (risk if left open):
Backlog needs the first value slice, deferrable variants, and the boundary where splitting smaller would stop producing value.

What answering this unblocks:
The backlog's first value slice and slice boundaries.

Question:
What is the first observable value slice, which variants or rules can be deferred, and where would a smaller split stop producing value?

Expected response format:
The first value slice plus what can be deferred and where not to split.

Example of a useful answer:
First slice: authorized user sees one high-risk case with current data. Defer export, bulk actions, and advanced rules. Do not split into button/endpoint/table because none validates value alone.


Client / domain response:

- Answer:
- Owner / source:
- Evidence or reference:
- Decision status:


### GAP-PRD-FR-AC - Functional Requirements And ACs

- Lens: `product`
- Severity: `medium`
- Status: `OPEN`
- Related requirement: `REQ-001`

Brief description:
Functional requirements are not decomposed with source-backed acceptance criteria.

Why it matters (risk if left open):
The PRD must list functional requirements with traceable acceptance criteria so backlog and QA do not invent scope.

What answering this unblocks:
The PRD Functional Requirements section (FRs with acceptance criteria).

Question:
What confirmed information resolves this uncertainty?

Expected response format:
FR-NN with a traceable EARS statement (When/If/While/Where/The system shall...) plus acceptance criterion and priority.

Example of a useful answer:
FR-01: the system must list pending items. AC: Given pending items exist, When the operator opens the list, Then ID, status, owner, and date are visible with source trace.


Client / domain response:

- Answer:
- Owner / source:
- Evidence or reference:
- Decision status:


### GAP-ACCEPTANCE - Acceptance Signal

- Lens: `quality`
- Severity: `critical`
- Status: `CLOSED`
- Related requirement: `REQ-001`

Brief description:
Acceptance criteria or success conditions are missing.

Why it matters (risk if left open):
Quality and implementation agents need observable conditions to know when the requirement is done.

What answering this unblocks:
PRD acceptance criteria, specs ACs, and Quality test cases.

Question:
What observable conditions prove the requirement is done?

Expected response format:
One or more EARS or Given/When/Then statements with observable conditions. EARS example: When <trigger>, the system shall <observable response>.

Example of a useful answer:
Given a queue has cases above the SLA threshold, when the dashboard loads, then the queue is marked as high risk and the analyst can identify it without opening case details.


Client / domain response:

- Answer:
- Owner / source:
- Evidence or reference:
- Decision status:


### GAP-QUALITY - Quality Expectations

- Lens: `quality`
- Severity: `medium`
- Status: `OPEN`
- Related requirement: `REQ-001`

Brief description:
Quality or testability expectations are not explicit.

Why it matters (risk if left open):
Quality expectations guide risk analysis, test depth, and required evidence.

What answering this unblocks:
PRD NFRs and the Quality handoff/test strategy.

Question:
What quality, testability, risk, or compliance expectations apply?

Expected response format:
Quality expectations as bullets: risk areas, test depth, and required evidence.

Example of a useful answer:
QA should cover happy path, no data, stale data, external service failure, and permission denied scenarios.


Client / domain response:

- Answer:
- Owner / source:
- Evidence or reference:
- Decision status:


### GAP-QUALITY-HANDOFF - Quality Handoff

- Lens: `quality`
- Severity: `medium`
- Status: `OPEN`
- Related requirement: `REQ-001`

Brief description:
Quality handoff is not explicit enough: critical flows, edge cases, test data, regression risks, or evidence expectations are unclear.

Why it matters (risk if left open):
QA needs critical flows, edge cases, data, and evidence expectations to deepen coverage.

What answering this unblocks:
Quality test cases and the coverage map.

Question:
Which critical flows, edge cases, test data, regression risks, and evidence expectations should Quality use for deeper coverage?

Expected response format:
Critical flows, edge cases, test data, and evidence expectations.

Example of a useful answer:
Critical tests: high risk, normal risk, stale source data, missing permissions, empty queue, and regression of existing filters.


Client / domain response:

- Answer:
- Owner / source:
- Evidence or reference:
- Decision status:


### GAP-PRD-NFR-KPI - NFRs, KPIs, And Measurement

- Lens: `quality`
- Severity: `medium`
- Status: `OPEN`
- Related requirement: `REQ-001`

Brief description:
NFRs, KPIs, targets, measurement method, or timeframe are not explicit enough for PRD governance.

Why it matters (risk if left open):
NFRs and KPIs with targets, measurement method, and timeframe make value and quality objectively verifiable.

What answering this unblocks:
The PRD NFRs and KPIs section.

Question:
What confirmed information resolves this uncertainty?

Expected response format:
NFR/KPI with target, measurement method, and timeframe.

Example of a useful answer:
NFR: audit records available for 2 years. KPI: 0 incorrect operations, measured through daily post-release incidents during month one.


Client / domain response:

- Answer:
- Owner / source:
- Evidence or reference:
- Decision status:


### GAP-TECH-DATA-SOURCE - Systems And Data Ownership

- Lens: `technical`
- Severity: `medium`
- Status: `OPEN`
- Related requirement: `REQ-001`

Brief description:
Data source, integration, or system ownership is not explicit in source or technology context.

Why it matters (risk if left open):
Technology needs enough system and ownership context to analyze architecture without inventing integrations.

What answering this unblocks:
Brief section 5 (technical) and the specs system boundaries and data ownership.

Question:
Which systems, endpoints, events, create/modify/reuse decisions, owners, source-of-truth data, and critical fields are involved?

Expected response format:
Systems/endpoints involved, source of truth, and owning team.

Example of a useful answer:
Reuse `GET /queues`; modify it to include `slaRisk`. Risk source of truth is the Case Management service owned by Operations Platform.


Client / domain response:

- Answer:
- Owner / source:
- Evidence or reference:
- Decision status:


### GAP-TECH-NFR - Operational Constraints

- Lens: `technical`
- Severity: `medium`
- Status: `OPEN`
- Related requirement: `REQ-001`

Brief description:
Performance, security, observability, or operational constraints are not explicit.

Why it matters (risk if left open):
Operational constraints affect architecture, implementation choices, monitoring, and release readiness.

What answering this unblocks:
PRD NFRs and the specs operational-constraints section.

Question:
What security, performance, observability, availability, or operational constraints apply?

Expected response format:
Named NFRs with concrete thresholds (latency, retention, availability) and how they are observed.

Example of a useful answer:
Dashboard response should stay under 2 seconds p95. Log risk-calculation failures and expose metrics for missing/stale source data.


Client / domain response:

- Answer:
- Owner / source:
- Evidence or reference:
- Decision status:


### GAP-BACKLOG-ENABLERS - Valid Cross-Cutting Enablers

- Lens: `technical`
- Severity: `medium`
- Status: `OPEN`
- Related requirement: `REQ-001`

Brief description:
Cross-cutting enablers are not explicit enough: implementation work that must be built in advance across frontend/backend or architecture surfaces must be tied to confirmed project functionality and boundary.

Why it matters (risk if left open):
Cross-cutting enablers are valid only when they are advance/cross implementation work that supports confirmed functionality inside the project boundary.

What answering this unblocks:
The backlog's cross-cutting enablers.

Question:
Which frontend/backend or architecture implementation enablers must be built in advance to support this functionality, what scope do they enable, and how are they different from a generic operational precondition?

Expected response format:
Each enabler with the capability boundary it supports and objective completion evidence.

Example of a useful answer:
Valid enabler: shared backend support for risk queries and role permissions for the flow, with objective validation. Not an enabler: 'make an internal tool accessible'; that is an operational precondition.


Client / domain response:

- Answer:
- Owner / source:
- Evidence or reference:
- Decision status:


### GAP-FRONTEND-SURFACE - Frontend Surface

- Lens: `technical`
- Severity: `medium`
- Status: `OPEN`
- Related requirement: `REQ-001`

Brief description:
Frontend implementation surface is not explicit enough: affected screens, states, validations, copy, roles, or API binding needs are unclear.

Evidence that triggers the question:
The input mentions "dashboard" but does not detail validations, roles, copy, or data binding for that surface.

Why it matters (risk if left open):
Frontend agents need affected surfaces, states, copy, and bindings before estimating or implementing responsibly.

What answering this unblocks:
The specs frontend surface and the Frontend context pack / backlog stories.

Question:
Which frontend surfaces, roles, states, validations, copy, analytics, and API binding needs are affected?

Expected response format:
Affected surface(s), states, validations, copy, and analytics events.

Example of a useful answer:
Affected surface is the Daily Operations dashboard. Add risk badge, preserve existing filters, bind to `slaRisk`, and track `risk_badge_clicked`.

Cited candidate options (not selected):
- Option A: Apply the missing `Frontend Surface` detail to the mentioned surface `dashboard`. Local citation: `dashboard`.
- Option B: Declare `dashboard` out of MVP scope and name the alternative or deferral. Local citation: `dashboard`.
These options do not close the gap; the BA/owner must confirm an answer.


Client / domain response:

- Answer:
- Owner / source:
- Evidence or reference:
- Decision status:


### GAP-BACKEND-SURFACE - Backend Surface

- Lens: `technical`
- Severity: `medium`
- Status: `OPEN`
- Related requirement: `REQ-001`

Brief description:
Backend implementation surface is not explicit enough: capabilities, integrations, rules, persistence, contracts, or failure behavior are unclear.

Why it matters (risk if left open):
Backend agents need capability, integration, persistence, and failure-behavior context before designing services.

What answering this unblocks:
The specs backend surface and the Backend context pack / backlog stories.

Question:
Which backend capabilities, integrations, rules, persistence/source-of-truth needs, contracts, and failure behaviors are affected?

Expected response format:
Capabilities, contracts, persistence/source of truth, and failure behavior.

Example of a useful answer:
Backend enriches queue summaries with SLA risk, handles unavailable Case Management data as `riskUnknown`, and does not persist risk locally.


Client / domain response:

- Answer:
- Owner / source:
- Evidence or reference:
- Decision status:


### GAP-TECH-DEEP-DIVE-INPUT - Technology Deep Dive

- Lens: `technical`
- Severity: `medium`
- Status: `OPEN`
- Related requirement: `REQ-001`

Brief description:
Technology has insufficient input to perform repository, architecture, endpoint/event, source-of-truth, or risk analysis.

Why it matters (risk if left open):
Technical agents need enough direction to inspect repositories, components, endpoints, and risks efficiently.

What answering this unblocks:
The Technology context pack and the solution architecture (SAD).

Question:
Which repositories/components, architecture questions, endpoint/event inventory, dependencies, and technical risks should Technology inspect?

Expected response format:
Repositories/components, endpoints, and source of truth to inspect.

Example of a useful answer:
Technology should inspect `ops-dashboard-web`, `queue-summary-api`, and Case Management integration docs before proposing architecture.


Client / domain response:

- Answer:
- Owner / source:
- Evidence or reference:
- Decision status:


### GAP-GOVERNANCE-CONSTRAINTS - Governance Constraints

- Lens: `compliance`
- Severity: `medium`
- Status: `OPEN`
- Related requirement: `REQ-001`

Brief description:
Governance, security, privacy, compliance, or operational restrictions are not explicit.

Why it matters (risk if left open):
Security, privacy, compliance, and audit constraints can change design, implementation, and testing.

What answering this unblocks:
Brief section 6 (governance) and the PRD governance section.

Question:
Which security, privacy, compliance, audit, or operational restrictions must be respected?

Expected response format:
Named security/privacy/compliance/audit constraints that apply.

Example of a useful answer:
No PII should be added to the dashboard list. Audit logs must not include customer names or document numbers.


Client / domain response:

- Answer:
- Owner / source:
- Evidence or reference:
- Decision status:


### GAP-PRD-GLOSSARY-GOVERNANCE - Glossary And Governance

- Lens: `compliance`
- Severity: `medium`
- Status: `OPEN`
- Related requirement: `REQ-001`

Brief description:
Glossary, mandatory constraints, pending inputs, or governance/audit notes are not explicit enough for a complete PRD.

Why it matters (risk if left open):
Glossary, mandatory constraints, pending inputs, and audit trail preserve shared understanding and traceability.

What answering this unblocks:
The PRD Governance section (glossary, constraints, audit trail).

Question:
What confirmed information resolves this uncertainty?

Expected response format:
Glossary terms, mandatory constraints, and pending inputs with owner.

Example of a useful answer:
Glossary: 'disabled state' means not operable. Constraint: do not expose sensitive data in logs. Pending input: metric owner.


Client / domain response:

- Answer:
- Owner / source:
- Evidence or reference:
- Decision status:


### GAP-DELIVERY-READINESS - Delivery Readiness

- Lens: `delivery`
- Severity: `medium`
- Status: `OPEN`
- Related requirement: `REQ-001`

Brief description:
Dependencies, environments, ownership, timing, or rollout constraints are not explicit.

Why it matters (risk if left open):
Dependencies, owners, environments, and timing determine sequencing and release feasibility.

What answering this unblocks:
The PRD execution plan and backlog sequencing/rollout.

Question:
Which dependencies, environments, approvals, owners, dates, or rollout constraints remain pending?

Expected response format:
Dependencies with owners, environments, dates, and rollout approach.

Example of a useful answer:
Dependency: Case Management team must expose SLA threshold by June 15. Rollout behind feature flag for Operations supervisors first.


Client / domain response:

- Answer:
- Owner / source:
- Evidence or reference:
- Decision status:


### GAP-PRD-DEPENDENCIES-ROADMAP - Dependencies And Roadmap

- Lens: `delivery`
- Severity: `medium`
- Status: `OPEN`
- Related requirement: `REQ-001`

Brief description:
Dependencies, owners, MVP scope, nice-to-haves, or roadmap are not explicit enough for PRD execution planning.

Why it matters (risk if left open):
Dependencies, owners, MVP, and roadmap support planning and prevent stories from being blocked by assumptions.

What answering this unblocks:
The PRD Execution Plan (dependencies, MVP, roadmap).

Question:
What confirmed information resolves this uncertainty?

Expected response format:
MVP, dependencies with owner, and roadmap phases.

Example of a useful answer:
MVP: query, main rule, and audit. Dependencies: service X owner Team A, copy owner Design, credentials owner Security. Phase 2: reporting.


Client / domain response:

- Answer:
- Owner / source:
- Evidence or reference:
- Decision status:


### GAP-PRD-ROLLOUT-ENVIRONMENTS - Rollout And Environments

- Lens: `delivery`
- Severity: `medium`
- Status: `OPEN`
- Related requirement: `REQ-001`

Brief description:
Rollout approach, target environments, or release constraints are not explicit enough for PRD execution planning.

Why it matters (risk if left open):
Rollout, environments, and release constraints prevent specs and backlog from inventing sequencing or exit conditions.

What answering this unblocks:
The PRD Execution Plan (rollout, environments, and release constraints).

Question:
Which environments, rollout strategy, release constraints, and rollback criterion must be confirmed in the PRD?

Expected response format:
Target environments, rollout strategy, release constraints, and rollback criterion.

Example of a useful answer:
Rollout: feature flag first in staging, then pilot with supervisors. Production requires approved window and rollback plan.


Client / domain response:

- Answer:
- Owner / source:
- Evidence or reference:
- Decision status:


### GAP-DESIGN-FLOW - User Journey And Screens

- Lens: `design`
- Severity: `medium`
- Status: `OPEN`
- Related requirement: `REQ-001`

Brief description:
User journey, screen flow, or interaction model is not explicit in source or design context.

Evidence that triggers the question:
The input mentions "dashboard" but does not describe the journey, navigation, or interaction flow around it.

Why it matters (risk if left open):
Design needs affected journeys and screens to create meaningful flows or prototypes.

What answering this unblocks:
Brief section 4 (design), specs UX flows, and the Design context pack.

Question:
Which user journey, screens, flows, copy, or interaction changes are in scope?

Expected response format:
Entry point and step-by-step journey to the affected screen(s).

Example of a useful answer:
The indicator appears on the daily dashboard list. Users enter from Home > Operations > Daily queues and decide which queue to inspect first.

Cited candidate options (not selected):
- Option A: Confirm `dashboard` is in scope and answer the missing `User Journey And Screens` detail. Local citation: `dashboard`.
- Option B: Confirm `dashboard` is context-only, out of scope, or pending, and state the boundary. Local citation: `dashboard`.
These options do not close the gap; the BA/owner must confirm an answer.


Client / domain response:

- Answer:
- Owner / source:
- Evidence or reference:
- Decision status:


### GAP-DESIGN-STATES - UX States

- Lens: `design`
- Severity: `medium`
- Status: `OPEN`
- Related requirement: `REQ-001`

Brief description:
Required UI states for loading, empty, error, and recovery are not explicit.

Evidence that triggers the question:
The input mentions "dashboard" but does not describe loading, empty, error, and recovery states.

Why it matters (risk if left open):
Missing UX states often become implementation ambiguity or untested edge cases.

What answering this unblocks:
Specs UX states and Quality edge-case coverage.

Question:
What loading, empty, error, recovery, and accessibility states must be handled?

Expected response format:
The loading, empty, error, and recovery states for the surface.

Example of a useful answer:
Show skeleton while loading, neutral state when there are no queues, warning state for stale data, and existing generic error for service failures.

Cited candidate options (not selected):
- Option A: Apply the missing `UX States` detail to the mentioned surface `dashboard`. Local citation: `dashboard`.
- Option B: Declare `dashboard` out of MVP scope and name the alternative or deferral. Local citation: `dashboard`.
These options do not close the gap; the BA/owner must confirm an answer.


Client / domain response:

- Answer:
- Owner / source:
- Evidence or reference:
- Decision status:


### GAP-DESIGN-PROTOTYPE-INPUT - Prototype Focus

- Lens: `design`
- Severity: `medium`
- Status: `OPEN`
- Related requirement: `REQ-001`

Brief description:
The requirement does not make clear what Design must prototype or validate in user flows.

Evidence that triggers the question:
The input mentions "dashboard" but does not state what Design must prototype or validate.

Why it matters (risk if left open):
A prototype is useful only if Design knows what decision, flow, or interaction it must validate.

What answering this unblocks:
The Design context pack and the prototype scope.

Question:
What should Design prototype or validate, and which users, journey moments, states, and visual references should guide it?

Expected response format:
The decision/flow/interaction the prototype must validate.

Example of a useful answer:
Prototype the dashboard list with normal, high-risk, stale-data, and empty states to validate scanability with analysts.

Cited candidate options (not selected):
- Option A: Confirm `dashboard` is in scope and answer the missing `Prototype Focus` detail. Local citation: `dashboard`.
- Option B: Confirm `dashboard` is context-only, out of scope, or pending, and state the boundary. Local citation: `dashboard`.
These options do not close the gap; the BA/owner must confirm an answer.


Client / domain response:

- Answer:
- Owner / source:
- Evidence or reference:
- Decision status:


## Additional Notes

Add any new requirement, constraint, decision, screenshot, diagram, or example that was not covered above.

## Framework Trace Table

This table is kept for Sentinel traceability and automated processing.

| Gap ID | Lens | Severity | Status | Parent | Description | Question For Client/Domain | Source Consulted | Detected Trigger | Origin | Resolution Note | Unit |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| GAP-BUSINESS-RULES | business | medium | OPEN | `REQ-001` | Business rules, exclusions, or decision rules are not explicit enough for downstream slicing. | Which rules, exceptions, validations, fallbacks, or exclusions govern the behavior? | Context folders and source input. | N/A | checklist | N/A | N/A |
| GAP-PRD-PERSONA-DETAIL | business | medium | OPEN | `REQ-001` | Persona attributes are not complete enough for a PRD: goals, pain points, proficiency, and usage frequency are unclear. | What confirmed information resolves this uncertainty? | Context folders and source input. | N/A | checklist | N/A | N/A |
| GAP-METRIC-SOURCE | business | medium | OPEN | `REQ-001` | Quantitative metric appears without an explicit source or baseline. | What is the source or baseline for the quantitative metric? | Context folders and source input. | 30 percent | checklist | N/A | RU-003 |
| GAP-METRIC-DEFINITION | business | medium | OPEN | `REQ-001` | A metric, KPI, or indicator concept is named without its definition, formula, unit, source, or threshold. | How is each metric/KPI defined (formula, unit), what source does it come from, and what is its baseline and target threshold? | Context folders and source input. | metric | checklist | N/A | RU-003 |
| GAP-PRODUCT-ASIS-TOBE | product | medium | OPEN | `REQ-001` | Current state and target state are not both explicit enough to compare impact. | What is the current process, target process, and exact delta between them? | Context folders and source input. | N/A | checklist | N/A | N/A |
| GAP-BACKLOG-SLICING-READINESS | product | medium | OPEN | `REQ-001` | Backlog slicing signals are not explicit enough: first value slice, workflow paths, variants, rule deferral, or story boundaries are unclear. | What is the first observable value slice, which variants or rules can be deferred, and where would a smaller split stop producing value? | Context folders and source input. | N/A | checklist | N/A | N/A |
| GAP-PRD-FR-AC | product | medium | OPEN | `REQ-001` | Functional requirements are not decomposed with source-backed acceptance criteria. | What confirmed information resolves this uncertainty? | Context folders and source input. | N/A | checklist | N/A | N/A |
| GAP-ACCEPTANCE | quality | critical | CLOSED | `REQ-001` | Acceptance criteria or success conditions are missing. | What observable conditions prove the requirement is done? | Context folders and source input. | N/A | checklist | N/A | N/A |
| GAP-QUALITY | quality | medium | OPEN | `REQ-001` | Quality or testability expectations are not explicit. | What quality, testability, risk, or compliance expectations apply? | Context folders and source input. | N/A | checklist | N/A | N/A |
| GAP-QUALITY-HANDOFF | quality | medium | OPEN | `REQ-001` | Quality handoff is not explicit enough: critical flows, edge cases, test data, regression risks, or evidence expectations are unclear. | Which critical flows, edge cases, test data, regression risks, and evidence expectations should Quality use for deeper coverage? | Context folders and source input. | N/A | checklist | N/A | N/A |
| GAP-PRD-NFR-KPI | quality | medium | OPEN | `REQ-001` | NFRs, KPIs, targets, measurement method, or timeframe are not explicit enough for PRD governance. | What confirmed information resolves this uncertainty? | Context folders and source input. | N/A | checklist | N/A | N/A |
| GAP-TECH-DATA-SOURCE | technical | medium | OPEN | `REQ-001` | Data source, integration, or system ownership is not explicit in source or technology context. | Which systems, endpoints, events, create/modify/reuse decisions, owners, source-of-truth data, and critical fields are involved? | Context folders and source input. | N/A | checklist | N/A | N/A |
| GAP-TECH-NFR | technical | medium | OPEN | `REQ-001` | Performance, security, observability, or operational constraints are not explicit. | What security, performance, observability, availability, or operational constraints apply? | Context folders and source input. | N/A | checklist | N/A | N/A |
| GAP-BACKLOG-ENABLERS | technical | medium | OPEN | `REQ-001` | Cross-cutting enablers are not explicit enough: implementation work that must be built in advance across frontend/backend or architecture surfaces must be tied to confirmed project functionality and boundary. | Which frontend/backend or architecture implementation enablers must be built in advance to support this functionality, what scope do they enable, and how are they different from a generic operational precondition? | Context folders and source input. | N/A | checklist | N/A | N/A |
| GAP-FRONTEND-SURFACE | technical | medium | OPEN | `REQ-001` | Frontend implementation surface is not explicit enough: affected screens, states, validations, copy, roles, or API binding needs are unclear. | Which frontend surfaces, roles, states, validations, copy, analytics, and API binding needs are affected? | Context folders and source input. | dashboard | checklist | N/A | RU-001 |
| GAP-BACKEND-SURFACE | technical | medium | OPEN | `REQ-001` | Backend implementation surface is not explicit enough: capabilities, integrations, rules, persistence, contracts, or failure behavior are unclear. | Which backend capabilities, integrations, rules, persistence/source-of-truth needs, contracts, and failure behaviors are affected? | Context folders and source input. | N/A | checklist | N/A | N/A |
| GAP-TECH-DEEP-DIVE-INPUT | technical | medium | OPEN | `REQ-001` | Technology has insufficient input to perform repository, architecture, endpoint/event, source-of-truth, or risk analysis. | Which repositories/components, architecture questions, endpoint/event inventory, dependencies, and technical risks should Technology inspect? | Context folders and source input. | N/A | checklist | N/A | N/A |
| GAP-GOVERNANCE-CONSTRAINTS | compliance | medium | OPEN | `REQ-001` | Governance, security, privacy, compliance, or operational restrictions are not explicit. | Which security, privacy, compliance, audit, or operational restrictions must be respected? | Context folders and source input. | N/A | checklist | N/A | N/A |
| GAP-PRD-GLOSSARY-GOVERNANCE | compliance | medium | OPEN | `REQ-001` | Glossary, mandatory constraints, pending inputs, or governance/audit notes are not explicit enough for a complete PRD. | What confirmed information resolves this uncertainty? | Context folders and source input. | N/A | checklist | N/A | N/A |
| GAP-DELIVERY-READINESS | delivery | medium | OPEN | `REQ-001` | Dependencies, environments, ownership, timing, or rollout constraints are not explicit. | Which dependencies, environments, approvals, owners, dates, or rollout constraints remain pending? | Context folders and source input. | N/A | checklist | N/A | N/A |
| GAP-PRD-DEPENDENCIES-ROADMAP | delivery | medium | OPEN | `REQ-001` | Dependencies, owners, MVP scope, nice-to-haves, or roadmap are not explicit enough for PRD execution planning. | What confirmed information resolves this uncertainty? | Context folders and source input. | N/A | checklist | N/A | N/A |
| GAP-PRD-ROLLOUT-ENVIRONMENTS | delivery | medium | OPEN | `REQ-001` | Rollout approach, target environments, or release constraints are not explicit enough for PRD execution planning. | Which environments, rollout strategy, release constraints, and rollback criterion must be confirmed in the PRD? | Context folders and source input. | N/A | checklist | N/A | N/A |
| GAP-DESIGN-FLOW | design | medium | OPEN | `REQ-001` | User journey, screen flow, or interaction model is not explicit in source or design context. | Which user journey, screens, flows, copy, or interaction changes are in scope? | Context folders and source input. | dashboard | checklist | N/A | RU-001 |
| GAP-DESIGN-STATES | design | medium | OPEN | `REQ-001` | Required UI states for loading, empty, error, and recovery are not explicit. | What loading, empty, error, recovery, and accessibility states must be handled? | Context folders and source input. | dashboard | checklist | N/A | RU-001 |
| GAP-DESIGN-PROTOTYPE-INPUT | design | medium | OPEN | `REQ-001` | The requirement does not make clear what Design must prototype or validate in user flows. | What should Design prototype or validate, and which users, journey moments, states, and visual references should guide it? | Context folders and source input. | dashboard | checklist | N/A | RU-001 |

## Resolution Trace

| Gap ID | Resolution Source | Promoted Seed | Impacted Artifacts |
| --- | --- | --- | --- |
| TBD | TBD | TBD | TBD |
