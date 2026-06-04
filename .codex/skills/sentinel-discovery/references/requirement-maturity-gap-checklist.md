# Requirement Maturity Gap Checklist

Use this checklist when reviewing raw or iterated requirements. The goal is not to complete every domain deliverable inside discovery. The goal is to reach the sweet spot: enough confirmed information for Design, Technology, Frontend, Backend, and Quality agents to deepen their own context packs without inventing product, architecture, flows, or test strategy.

If a section is unclear, mark an explicit gap and ask a focused question.

## Product / Business

- Problem: the real pain is clear, not only the requested solution.
- Users and actors: primary user, secondary actors, operators, systems, and impacted teams are known.
- Outcome: the business or operational result is explicit.
- Scope: in scope, out of scope, non-goals, and unchanged behavior are stated.
- As-is / to-be: current process and target process can be compared.
- Rules: business rules, exceptions, edge cases, and decision logic are visible.
- Success: measurable or observable success criteria are defined, including metric source or baseline when quantitative.
- Decisions: confirmed decisions, open decisions, and assumptions are separated.

Gap examples:

- `GAP-OBJECTIVE`: outcome or pain is unclear.
- `GAP-USERS`: users, personas, roles, or impacted teams are unclear.
- `GAP-SCOPE`: scope boundaries or unchanged behavior are unclear.
- `GAP-PRODUCT-ASIS-TOBE`: current and target states are not comparable.
- `GAP-BUSINESS-RULES`: rules, exceptions, or validations are missing.

## Design / Prototype Readiness

- Journey: affected journey moments and entry/exit points are known.
- Surfaces: screens, pages, flows, or channels that change are identified.
- User decisions: what the user must understand or decide is explicit.
- States: loading, empty, error, disabled, success, permission, and recovery states are known or flagged.
- Copy: messages, labels, help text, legal/compliance copy, and copy that must remain unchanged are known.
- Visual evidence: screenshots, diagrams, sketches, prototypes, or design-system references are linked or requested.
- Prototype target: what Design should validate is clear: navigation, content hierarchy, interaction, states, or usability.

Gap examples:

- `GAP-DESIGN-FLOW`: journey, screens, or interaction model is unclear.
- `GAP-DESIGN-STATES`: UI states are missing.
- `GAP-DESIGN-PROTOTYPE-INPUT`: it is unclear what Design must prototype or validate.

## Technology Deep-Dive Readiness

- Systems: participating systems and owner teams are known.
- Source of truth: owner for each critical datum is clear.
- Endpoint/event inventory: existing endpoints/events to reuse, endpoints/events to create, endpoints/events to modify, and endpoints/events to deprecate are identified when relevant.
- Repository/component targets: repos, services, modules, or components Technology should inspect are listed or requested.
- Architecture questions: integration style, orchestration ownership, sync/async behavior, data freshness, and dependencies are visible.
- Constraints: security, privacy, compliance, performance, availability, observability, auditability, timeout/retry, and rollout constraints are known or flagged.
- Depth limit: full dictionaries, complete request/response examples, schemas, sequence diagrams, and deployment design belong in the technology context pack, not necessarily in the brief.

Gap examples:

- `GAP-TECH-DATA-SOURCE`: systems, endpoints/events, owners, source of truth, or critical fields are unclear.
- `GAP-TECH-DEEP-DIVE-INPUT`: Technology lacks enough input for repo, architecture, endpoint/event, dependency, or risk analysis.
- `GAP-TECH-NFR`: operational constraints are unclear.

## Frontend Implementation Readiness

- Surfaces: affected UI surfaces and channels are identified.
- Roles and permissions: who can see or act is known.
- Data needs: data consumed by the UI and API binding expectations are visible.
- States and validations: UI states, validation ownership, and error behavior are known.
- Copy and analytics: changed copy, events/telemetry, and unchanged copy are visible.
- Compatibility: existing behavior that must not regress is explicit.

Gap example:

- `GAP-FRONTEND-SURFACE`: affected surfaces, roles, states, validations, copy, analytics, or API bindings are unclear.

## Backend Implementation Readiness

- Capabilities: backend responsibilities and business capabilities are clear.
- Rules: validations, calculations, orchestration, and decision rules are visible.
- Integrations: upstream/downstream services, events, and failure behavior are known.
- Data: persistence, source-of-truth, idempotency, consistency, and freshness needs are explicit or flagged.
- Contracts: exposed contract changes or compatibility constraints are known at an inventory level.
- Observability: logs, metrics, tracing, audit, and alerting expectations are known or flagged.

Gap example:

- `GAP-BACKEND-SURFACE`: capabilities, integrations, rules, persistence, contracts, or failure behavior are unclear.

## Quality Handoff Readiness

- Acceptance: observable acceptance criteria exist.
- Critical paths: happy path and critical negative paths are identified.
- Edge cases: missing, invalid, stale, duplicated, unauthorized, and external-failure data cases are visible when relevant.
- Regression: existing behavior that must not change is testable.
- Test data: required data shapes, roles, environments, or fixtures are known or requested.
- Evidence: expected validation evidence and traceability expectations are clear.

Gap examples:

- `GAP-ACCEPTANCE`: acceptance conditions are missing.
- `GAP-QUALITY`: quality or testability expectations are unclear.
- `GAP-QUALITY-HANDOFF`: critical flows, edge cases, test data, regression risks, or evidence expectations are unclear.

