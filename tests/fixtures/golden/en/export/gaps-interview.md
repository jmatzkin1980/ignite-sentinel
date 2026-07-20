# Interview Script - [PROJECT_ID]

READ-ONLY derived view of the open gaps, ordered as a meeting script (blocking gaps first, grouped by lens). Probing questions come from the cited candidate options (IMP-113); they are never invented. This script does NOT replace `01_discovery/gaps.md` (the source of truth) and closes no gap.


## Follow-up questions

### business

1. Business Rules (`GAP-BUSINESS-RULES`, severity `medium`, lens `business`)

- Ask: Which rules, exceptions, validations, fallbacks, or exclusions govern the behavior?

2. Metric Definition (`GAP-METRIC-DEFINITION`, severity `medium`, lens `business`)

- Cited context: The input mentions "metric" but does not define the metric: missing formula/unit, source, or threshold.
- Ask: How is each metric/KPI defined (formula, unit), what source does it come from, and what is its baseline and target threshold?
- Probing questions:
  - Confirm `metric` is in scope and answer the missing `Metric Definition` detail. Local citation: `metric`.
  - Confirm `metric` is context-only, out of scope, or pending, and state the boundary. Local citation: `metric`.

3. Metric Source (`GAP-METRIC-SOURCE`, severity `medium`, lens `business`)

- Cited context: The metric "30 percent" appears without a source, baseline, or measurement method.
- Ask: What is the source or baseline for the quantitative metric?
- Probing questions:
  - Confirm `30 percent` is the success target and provide source, baseline, owner, and measurement method. Local citation: `30 percent`.
  - Treat `30 percent` as a directional target until source/baseline are confirmed, naming the missing evidence. Local citation: `30 percent`.

4. PRD Persona Detail (`GAP-PRD-PERSONA-DETAIL`, severity `medium`, lens `business`)

- Ask: What confirmed information resolves this uncertainty?

### compliance

5. Governance Constraints (`GAP-GOVERNANCE-CONSTRAINTS`, severity `medium`, lens `compliance`)

- Ask: Which security, privacy, compliance, audit, or operational restrictions must be respected?

6. Glossary And Governance (`GAP-PRD-GLOSSARY-GOVERNANCE`, severity `medium`, lens `compliance`)

- Ask: What confirmed information resolves this uncertainty?

### delivery

7. Delivery Readiness (`GAP-DELIVERY-READINESS`, severity `medium`, lens `delivery`)

- Ask: Which dependencies, environments, approvals, owners, dates, or rollout constraints remain pending?

8. Dependencies And Roadmap (`GAP-PRD-DEPENDENCIES-ROADMAP`, severity `medium`, lens `delivery`)

- Ask: What confirmed information resolves this uncertainty?

9. Rollout And Environments (`GAP-PRD-ROLLOUT-ENVIRONMENTS`, severity `medium`, lens `delivery`)

- Ask: Which environments, rollout strategy, release constraints, and rollback criterion must be confirmed in the PRD?

### design

10. User Journey And Screens (`GAP-DESIGN-FLOW`, severity `medium`, lens `design`)

- Cited context: The input mentions "dashboard" but does not describe the journey, navigation, or interaction flow around it.
- Ask: Which user journey, screens, flows, copy, or interaction changes are in scope?
- Probing questions:
  - Confirm `dashboard` is in scope and answer the missing `User Journey And Screens` detail. Local citation: `dashboard`.
  - Confirm `dashboard` is context-only, out of scope, or pending, and state the boundary. Local citation: `dashboard`.

11. Prototype Focus (`GAP-DESIGN-PROTOTYPE-INPUT`, severity `medium`, lens `design`)

- Cited context: The input mentions "dashboard" but does not state what Design must prototype or validate.
- Ask: What should Design prototype or validate, and which users, journey moments, states, and visual references should guide it?
- Probing questions:
  - Confirm `dashboard` is in scope and answer the missing `Prototype Focus` detail. Local citation: `dashboard`.
  - Confirm `dashboard` is context-only, out of scope, or pending, and state the boundary. Local citation: `dashboard`.

12. UX States (`GAP-DESIGN-STATES`, severity `medium`, lens `design`)

- Cited context: The input mentions "dashboard" but does not describe loading, empty, error, and recovery states.
- Ask: What loading, empty, error, recovery, and accessibility states must be handled?
- Probing questions:
  - Apply the missing `UX States` detail to the mentioned surface `dashboard`. Local citation: `dashboard`.
  - Declare `dashboard` out of MVP scope and name the alternative or deferral. Local citation: `dashboard`.

### product

13. Backlog Slicing Readiness (`GAP-BACKLOG-SLICING-READINESS`, severity `medium`, lens `product`)

- Ask: What is the first observable value slice, which variants or rules can be deferred, and where would a smaller split stop producing value?

14. Functional Requirements And ACs (`GAP-PRD-FR-AC`, severity `medium`, lens `product`)

- Ask: What confirmed information resolves this uncertainty?

15. Current And Target Process (`GAP-PRODUCT-ASIS-TOBE`, severity `medium`, lens `product`)

- Ask: What is the current process, target process, and exact delta between them?

### quality

16. NFRs, KPIs, And Measurement (`GAP-PRD-NFR-KPI`, severity `medium`, lens `quality`)

- Ask: What confirmed information resolves this uncertainty?

17. Quality Expectations (`GAP-QUALITY`, severity `medium`, lens `quality`)

- Ask: What quality, testability, risk, or compliance expectations apply?

18. Quality Handoff (`GAP-QUALITY-HANDOFF`, severity `medium`, lens `quality`)

- Ask: Which critical flows, edge cases, test data, regression risks, and evidence expectations should Quality use for deeper coverage?

### technical

19. Backend Surface (`GAP-BACKEND-SURFACE`, severity `medium`, lens `technical`)

- Ask: Which backend capabilities, integrations, rules, persistence/source-of-truth needs, contracts, and failure behaviors are affected?

20. Valid Cross-Cutting Enablers (`GAP-BACKLOG-ENABLERS`, severity `medium`, lens `technical`)

- Ask: Which frontend/backend or architecture implementation enablers must be built in advance to support this functionality, what scope do they enable, and how are they different from a generic operational precondition?

21. Frontend Surface (`GAP-FRONTEND-SURFACE`, severity `medium`, lens `technical`)

- Cited context: The input mentions "dashboard" but does not detail validations, roles, copy, or data binding for that surface.
- Ask: Which frontend surfaces, roles, states, validations, copy, analytics, and API binding needs are affected?
- Probing questions:
  - Apply the missing `Frontend Surface` detail to the mentioned surface `dashboard`. Local citation: `dashboard`.
  - Declare `dashboard` out of MVP scope and name the alternative or deferral. Local citation: `dashboard`.

22. Systems And Data Ownership (`GAP-TECH-DATA-SOURCE`, severity `medium`, lens `technical`)

- Ask: Which systems, endpoints, events, create/modify/reuse decisions, owners, source-of-truth data, and critical fields are involved?

23. Technology Deep Dive (`GAP-TECH-DEEP-DIVE-INPUT`, severity `medium`, lens `technical`)

- Ask: Which repositories/components, architecture questions, endpoint/event inventory, dependencies, and technical risks should Technology inspect?

24. Operational Constraints (`GAP-TECH-NFR`, severity `medium`, lens `technical`)

- Ask: What security, performance, observability, availability, or operational constraints apply?
