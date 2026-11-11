<!-- sentinel-artifact: v2 -->
# Project Brief — [PROJECT_ID]

## 0. Header

### 0.1 How to read this document

- Every statement is one of these. A fact carries a structured citation (document, section, id and what it supports) of the source that says it.
- `⏳` PENDING (gap): the client owes this data; it blocks.
- `⏳` PENDING DOMAIN (gap): domain context owes it; it can be deferred.
- `N/A — reason. If condition, it opens.`: it does not apply to this project, and says what would open it.
- `(inferred)`: an inference, marked in the same sentence.

### 0.2 Status, validity and sources

#### Status, validity and sources

- Profile: UI
- Genesis: greenfield
- Validation direction: to-build

Sources:

- `F-01` `raw.md` (current)
- `F-02` `answer-1.md` (current)
- `F-03` `answer-2.md` (current)
- `F-04` `answer-3.md` (current)
- `F-05` `answer-4.md` (current)
- `F-06` `answer-5.md` (current)
- `F-07` `answer-6.md` (current)

Certainty by section:

| Section | Facts | ⏳ client | ⏳ domain | N/A |
|---|---|---|---|---|
| 0 | 0 | 0 | 0 | 0 |
| 1 | 3 | 1 | 1 | 0 |
| 2 | 1 | 2 | 4 | 0 |
| 3 | 1 | 3 | 4 | 1 |
| 4 | 0 | 8 | 2 | 0 |
| 5 | 0 | 0 | 44 | 6 |
| 6 | 2 | 0 | 0 | 0 |
| 7 | 0 | 0 | 1 | 0 |
| 8 | 0 | 0 | 0 | 0 |
| 9 | 1 | 0 | 1 | 0 |
| A | 0 | 1 | 0 | 0 |

⚠ Low reliability: 72 of 80 applicable places are still pending.

#### Ready to build

Ready to build: no. 15 pending marks block (§7).

## 1. Overview

### 1.1 Identity and Value

- Objective: let operations leads review risk queues before the daily meeting. [[sources § Source log - [PROJECT_ID] # F-01 — supports: Identity and Value]]

### 1.2 The Core Pain

⏳ PENDING (GAP-BRIEF-S1)

### 1.3 Success Metrics / Scope

- Metric: reduce manual preparation by 30 percent in the first release month. [[sources § Source log - [PROJECT_ID] # F-01 — supports: Success Metrics / Scope]]

### 1.4 Starting Point and End Point

⏳ PENDING DOMAIN (GAP-BRIEF-S1)

### 1.5 Release Acceptance Criteria

- When queue metrics are available, the system shall display open risk queues. (`GAP-ACCEPTANCE`) [[sources § Source log - [PROJECT_ID] # F-02 — supports: Release Acceptance Criteria (GAP-ACCEPTANCE)]]
- When a case breaches SLA, the system shall flag the queue as high risk. (`GAP-ACCEPTANCE`) [[sources § Source log - [PROJECT_ID] # F-03 — supports: Release Acceptance Criteria (GAP-ACCEPTANCE)]]
- When a queue has no open cases, the system shall hide risk indicators. (`GAP-ACCEPTANCE`) [[sources § Source log - [PROJECT_ID] # F-04 — supports: Release Acceptance Criteria (GAP-ACCEPTANCE)]]
- While risk data is stale, the system shall show a stale data warning. (`GAP-ACCEPTANCE`) [[sources § Source log - [PROJECT_ID] # F-05 — supports: Release Acceptance Criteria (GAP-ACCEPTANCE)]]
- If the metrics service is unavailable, then the system shall show risk status unknown. (`GAP-ACCEPTANCE`) [[sources § Source log - [PROJECT_ID] # F-06 — supports: Release Acceptance Criteria (GAP-ACCEPTANCE)]]
- Where audit logging is enabled, the system shall record dashboard access. (`GAP-ACCEPTANCE`) [[sources § Source log - [PROJECT_ID] # F-07 — supports: Release Acceptance Criteria (GAP-ACCEPTANCE)]]

#### Acceptance criteria

→ 1.5

#### Executable verification

→ 1.5

## 2. Business Lens

### 2.1 Actors and Goals by Role

- Objective: let operations leads review risk queues before the daily meeting. [[sources § Source log - [PROJECT_ID] # F-01 — supports: Actors and Goals by Role]]
- Users: operations leads. [[sources § Source log - [PROJECT_ID] # F-01 — supports: Actors and Goals by Role]]

### 2.2 Critical Business Rules

#### Critical business rules

⏳ PENDING (GAP-BUSINESS-RULES)

#### Regulatory obligations

⏳ PENDING DOMAIN (GAP-BUSINESS-RULES)

#### Notifications

⏳ PENDING DOMAIN (GAP-BUSINESS-RULES)

### 2.3 Main Use Case

⏳ PENDING (GAP-BRIEF-S2)

### 2.4 Business Need

⏳ PENDING DOMAIN (GAP-BRIEF-S2)

### 2.5 Business Date and Calendar

⏳ PENDING DOMAIN (GAP-BRIEF-S2)

## 3. Product Lens

### 3.1 As-Is Situation

- Metric: reduce manual preparation by 30 percent in the first release month. [[sources § Source log - [PROJECT_ID] # F-01 — supports: As-Is Situation]]

### 3.2 To-Be Process

#### To-Be process

⏳ PENDING (GAP-PRODUCT-ASIS-TOBE)

#### Input validations

⏳ PENDING (GAP-PRODUCT-ASIS-TOBE)

#### Manual operation and back office

⏳ PENDING DOMAIN (GAP-PRODUCT-ASIS-TOBE)

#### Cutover, coexistence and rollback

N/A — nothing installed to respect: everything is created in this project. If a resource, system or data to reuse, extend or replace appears, they open.

### 3.3 Sequence Diagram / To-Be Flow

⏳ PENDING DOMAIN (GAP-PRODUCT-ASIS-TOBE)

### 3.4 State Machine and Lifecycle

⏳ PENDING DOMAIN (GAP-PRODUCT-ASIS-TOBE)

### 3.5 Transition Logic

⏳ PENDING DOMAIN (GAP-PRODUCT-ASIS-TOBE)

### 3.6 Error Handling / Edge Cases

#### Edge cases and errors

⏳ PENDING (GAP-QUALITY-HANDOFF)

#### Cross-cutting scenarios

| Scenario | Lens | Where it is specified | Status |
|---|---|---|---|
| T1 Permission denied | design, technical | §4.1 › Screen states, §5.11 › Authorization and permissions | pending there |
| T2 Error | design, technical | §4.2 › Messages to the user, §5.15 | pending there |
| T3 Empty | design | §4.1 › Screen states | pending there |
| T4 Loading | design | §4.1 › Screen states | pending there |
| T5 Concurrency | technical | §5.7 › Idempotency and concurrency | pending there |
| T6 Duplicate | product, technical | §3.6 › Edge cases and errors, §5.7 › Idempotency and concurrency | pending there |
| T7 Audit | technical | §5.11 › Audit | pending there |
| T8 Internationalization | design, technical | §4.1 › Language, locale and formats, §5.21 | pending there |
| T9 Accessibility | design | §4.4 | pending there |
| T10 Feature flag | technical | §5.3 › Parameters and switches | pending there |
| T11 Migration | technical | §5.13 › Data migration | pending there |
| T12 Session expired | design, technical | §4.1 › Screen states, §5.11 › Authentication and session | pending there |
| T13 Dependency down | product, technical | §3.6 › Edge cases and errors, §5.6 › Integration resilience | pending there |
| T14 Duplicate event | technical | §5.14 | pending there |
| T15 Volume | technical | §5.16 › Quality and performance attributes | pending there |
| T16 Personal data | technical, compliance | §5.4 › Personal data: classification, purpose and retention | pending there |

## 4. Design Lens

### 4.1 Screen Flow

#### Per-screen sheet

⏳ PENDING (GAP-DESIGN-FLOW)

#### Design system and visual conventions

⏳ PENDING (GAP-DESIGN-FLOW)

#### Screen map and navigation

⏳ PENDING (GAP-DESIGN-FLOW)

#### Screen states

⏳ PENDING (GAP-DESIGN-FLOW) — states: ideal; first-use empty; no results; loading; partial; error; 401 (and what happens to typed input); 403 (empty is not no permission; first use is not no results)

#### Language, locale and formats

⏳ PENDING (GAP-DESIGN-FLOW)

### 4.2 UX Considerations

#### UX decisions and uncommitted ideas

⏳ PENDING DOMAIN (GAP-DESIGN-FLOW)

#### Messages to the user

⏳ PENDING (GAP-DESIGN-FLOW)

### 4.3 Prototype and Design Precedents

⏳ PENDING (GAP-DESIGN-PROTOTYPE-INPUT)

### 4.4 Accessibility

⏳ PENDING (GAP-DESIGN-FLOW)

### 4.5 Help and Training

⏳ PENDING DOMAIN (GAP-DESIGN-FLOW)

## 5. Technical Lens

### 5.0 Opening

⏳ PENDING DOMAIN (GAP-TECH-DEEP-DIVE-INPUT)

### 5.1 Architecture and Integrations

#### Architecture and components

⏳ PENDING DOMAIN (GAP-FRONTEND-SURFACE)

#### Existing resources inventory

N/A — see 3.2/cutover.

#### Architecture decisions

⏳ PENDING DOMAIN (GAP-FRONTEND-SURFACE)

### 5.2 Technology Stack

#### Technology stack

⏳ PENDING DOMAIN (GAP-PRD-ROLLOUT-ENVIRONMENTS)

#### Environments, deployment and rollback

⏳ PENDING DOMAIN (GAP-PRD-ROLLOUT-ENVIRONMENTS)

### 5.3 Data Sources / Repositories

#### Data sources

⏳ PENDING DOMAIN (GAP-TECH-DATA-SOURCE)

#### Repositories, configuration and secrets

⏳ PENDING DOMAIN (GAP-TECH-DATA-SOURCE)

#### Parameters and switches

⏳ PENDING DOMAIN (GAP-TECH-DATA-SOURCE)

### 5.4 Data Model / ERD

#### Data model

⏳ PENDING DOMAIN (GAP-TECH-DEEP-DIVE-INPUT)

#### Personal data: classification, purpose and retention

⏳ PENDING DOMAIN (GAP-TECH-DEEP-DIVE-INPUT)

### 5.5 Inherited Query / Pattern

N/A — see 3.2/cutover.

### 5.6 Integration Map

#### Integration map

⏳ PENDING DOMAIN (GAP-TECH-DEEP-DIVE-INPUT)

#### Integration resilience

⏳ PENDING DOMAIN (GAP-TECH-DEEP-DIVE-INPUT)

### 5.7 API Contracts

#### Global API conventions

⏳ PENDING DOMAIN (GAP-TECH-DEEP-DIVE-INPUT)

#### Idempotency and concurrency

⏳ PENDING DOMAIN (GAP-TECH-DEEP-DIVE-INPUT)

#### Versioning and compatibility

⏳ PENDING DOMAIN (GAP-TECH-DEEP-DIVE-INPUT)

#### Per-endpoint contracts

⏳ PENDING DOMAIN (GAP-TECH-DEEP-DIVE-INPUT)

### 5.8 Field Mapping (DB → API → UI)

#### Field mapping

⏳ PENDING DOMAIN (GAP-TECH-DEEP-DIVE-INPUT)

#### Impact on what is installed

N/A — see 3.2/cutover.

### 5.9 Batch Processing / Change Notification

#### File interfaces

⏳ PENDING DOMAIN (GAP-TECH-DEEP-DIVE-INPUT)

#### Restart, re-run and reconciliation

⏳ PENDING DOMAIN (GAP-TECH-DEEP-DIVE-INPUT)

### 5.10 Caching and High Availability Strategy

⏳ PENDING DOMAIN (GAP-TECH-DEEP-DIVE-INPUT)

### 5.11 Governance and Constraints

#### Imposed constraints

⏳ PENDING DOMAIN (GAP-GOVERNANCE-CONSTRAINTS)

#### Authentication and session

⏳ PENDING DOMAIN (GAP-GOVERNANCE-CONSTRAINTS)

#### Authorization and permissions

⏳ PENDING DOMAIN (GAP-GOVERNANCE-CONSTRAINTS)

#### Data protection

⏳ PENDING DOMAIN (GAP-GOVERNANCE-CONSTRAINTS)

#### Audit

⏳ PENDING DOMAIN (GAP-GOVERNANCE-CONSTRAINTS)

#### Regulation: controls and verification

⏳ PENDING DOMAIN (GAP-GOVERNANCE-CONSTRAINTS)

#### Limits for implementers

⏳ PENDING DOMAIN (GAP-GOVERNANCE-CONSTRAINTS)

### 5.12 Services

#### Services

⏳ PENDING DOMAIN (GAP-BACKEND-SURFACE)

#### Client state

⏳ PENDING DOMAIN (GAP-BACKEND-SURFACE)

#### Jobs and execution calendar

⏳ PENDING DOMAIN (GAP-BACKEND-SURFACE)

### 5.13 Legacy Inventory and Inherited Rules (technical As-Is)

#### Legacy inventory and inherited rules

N/A — see 3.2/cutover.

#### Data migration

⏳ PENDING DOMAIN (GAP-TECH-DEEP-DIVE-INPUT)

### 5.14 Events / Messaging

⏳ PENDING DOMAIN (GAP-TECH-DEEP-DIVE-INPUT)

### 5.15 Error Handling and Status Codes

⏳ PENDING DOMAIN (GAP-TECH-DEEP-DIVE-INPUT)

### 5.16 Observability

#### Quality and performance attributes

⏳ PENDING DOMAIN (GAP-PRD-NFR-KPI)

#### SLI and SLO

⏳ PENDING DOMAIN (GAP-PRD-NFR-KPI)

#### Observability

⏳ PENDING DOMAIN (GAP-PRD-NFR-KPI)

#### Alerts, runbooks and support

⏳ PENDING DOMAIN (GAP-PRD-NFR-KPI)

### 5.17 Parity Verification

N/A — it replaces no system whose outputs must be matched. If one appears, 5.17 and 5.13 open as required.

### 5.18 Usage Limits

⏳ PENDING DOMAIN (GAP-TECH-DEEP-DIVE-INPUT)

### 5.19 Browsers and Devices

⏳ PENDING DOMAIN (GAP-TECH-DEEP-DIVE-INPUT)

### 5.20 Routing and Route Protection

⏳ PENDING DOMAIN (GAP-TECH-DEEP-DIVE-INPUT)

### 5.21 Technical Internationalization

⏳ PENDING DOMAIN (GAP-TECH-DEEP-DIVE-INPUT)

### 5.22 Client Security

⏳ PENDING DOMAIN (GAP-TECH-DEEP-DIVE-INPUT)

### 5.23 Analytics Events

⏳ PENDING DOMAIN (GAP-TECH-DEEP-DIVE-INPUT)

### 5.24 Tenant Isolation

N/A — a single customer or tenant. If a second one is added, 5.24 and the tenant column in 5.4 open.

### 5.25 Abuse and Anti-automation

⏳ PENDING DOMAIN (GAP-TECH-DEEP-DIVE-INPUT)

## 6. Release Agreements

### 6.1 In Scope

- In scope: read-only risk dashboard for open queues. [[sources § Source log - [PROJECT_ID] # F-01 — supports: In Scope]]

### 6.2 Out of Scope

- Out of scope: editing cases. [[sources § Source log - [PROJECT_ID] # F-01 — supports: Out of Scope]]

### 6.3 Cascade — Propagation Status to Other Documents

First v2 compilation: every section is `ADDED`. PRD, specs and backlog regenerate from this brief.

## 7. Dependencies and Open Questions

### 7.1 Open Items Table (pre-development form)

#### Open items table

28 open gaps in `gaps.md`.

| Gap | Severity | Origin |
|---|---|---|
| `GAP-BACKEND-SURFACE` | medium | checklist |
| `GAP-BACKLOG-ENABLERS` | medium | checklist |
| `GAP-BACKLOG-SLICING-READINESS` | medium | checklist |
| `GAP-BRIEF-S1` | medium | checklist |
| `GAP-BRIEF-S2` | medium | checklist |
| `GAP-BUSINESS-RULES` | medium | checklist |
| `GAP-CTP-EXCLUSION` | medium | checklist |
| `GAP-DELIVERY-READINESS` | medium | checklist |
| `GAP-DESIGN-FLOW` | medium | checklist |
| `GAP-DESIGN-PROTOTYPE-INPUT` | medium | checklist |
| `GAP-DESIGN-STATES` | medium | checklist |
| `GAP-FRONTEND-SURFACE` | medium | checklist |
| `GAP-GOVERNANCE-CONSTRAINTS` | medium | checklist |
| `GAP-METRIC-DEFINITION` | medium | checklist |
| `GAP-METRIC-SOURCE` | medium | checklist |
| `GAP-PRD-DEPENDENCIES-ROADMAP` | medium | checklist |
| `GAP-PRD-FR-AC` | medium | checklist |
| `GAP-PRD-GLOSSARY-GOVERNANCE` | medium | checklist |
| `GAP-PRD-GOVERNANCE` | medium | checklist |
| `GAP-PRD-NFR-KPI` | medium | checklist |
| `GAP-PRD-PERSONA-DETAIL` | medium | checklist |
| `GAP-PRD-ROLLOUT-ENVIRONMENTS` | medium | checklist |
| `GAP-PRODUCT-ASIS-TOBE` | medium | checklist |
| `GAP-QUALITY` | medium | checklist |
| `GAP-QUALITY-HANDOFF` | medium | checklist |
| `GAP-TECH-DATA-SOURCE` | medium | checklist |
| `GAP-TECH-DEEP-DIVE-INPUT` | medium | checklist |
| `GAP-TECH-NFR` | medium | checklist |

#### Risks, debt and viability

⏳ PENDING DOMAIN (GAP-PRD-DEPENDENCIES-ROADMAP)

### 7.2 Open Items Seeded in the Body (⏳)

15 client marks (block) and 57 domain marks (deferrable) in the body.

| Place | Class | Gap |
|---|---|---|
| 1.2 | client | `GAP-BRIEF-S1` |
| 1.4 | domain | `GAP-BRIEF-S1` |
| 2.2/rules | client | `GAP-BUSINESS-RULES` |
| 2.2/regulatory | domain | `GAP-BUSINESS-RULES` |
| 2.2/notifications | domain | `GAP-BUSINESS-RULES` |
| 2.3 | client | `GAP-BRIEF-S2` |
| 2.4 | domain | `GAP-BRIEF-S2` |
| 2.5 | domain | `GAP-BRIEF-S2` |
| 3.2/process | client | `GAP-PRODUCT-ASIS-TOBE` |
| 3.2/validations | client | `GAP-PRODUCT-ASIS-TOBE` |
| 3.2/manual_ops | domain | `GAP-PRODUCT-ASIS-TOBE` |
| 3.3 | domain | `GAP-PRODUCT-ASIS-TOBE` |
| 3.4 | domain | `GAP-PRODUCT-ASIS-TOBE` |
| 3.5 | domain | `GAP-PRODUCT-ASIS-TOBE` |
| 3.6/edge_cases | client | `GAP-QUALITY-HANDOFF` |
| 4.1/screens | client | `GAP-DESIGN-FLOW` |
| 4.1/design_system | client | `GAP-DESIGN-FLOW` |
| 4.1/screen_map | client | `GAP-DESIGN-FLOW` |
| 4.1/screen_states | client | `GAP-DESIGN-FLOW` |
| 4.1/locale | client | `GAP-DESIGN-FLOW` |
| 4.2/ux_decisions | domain | `GAP-DESIGN-FLOW` |
| 4.2/messages | client | `GAP-DESIGN-FLOW` |
| 4.3 | client | `GAP-DESIGN-PROTOTYPE-INPUT` |
| 4.4 | client | `GAP-DESIGN-FLOW` |
| 4.5 | domain | `GAP-DESIGN-FLOW` |
| 5.0 | domain | `GAP-TECH-DEEP-DIVE-INPUT` |
| 5.1/components | domain | `GAP-FRONTEND-SURFACE` |
| 5.1/decisions | domain | `GAP-FRONTEND-SURFACE` |
| 5.2/stack | domain | `GAP-PRD-ROLLOUT-ENVIRONMENTS` |
| 5.2/environments | domain | `GAP-PRD-ROLLOUT-ENVIRONMENTS` |
| 5.3/data_sources | domain | `GAP-TECH-DATA-SOURCE` |
| 5.3/repos | domain | `GAP-TECH-DATA-SOURCE` |
| 5.3/parameters | domain | `GAP-TECH-DATA-SOURCE` |
| 5.4/model | domain | `GAP-TECH-DEEP-DIVE-INPUT` |
| 5.4/personal_data | domain | `GAP-TECH-DEEP-DIVE-INPUT` |
| 5.6/map | domain | `GAP-TECH-DEEP-DIVE-INPUT` |
| 5.6/resilience | domain | `GAP-TECH-DEEP-DIVE-INPUT` |
| 5.7/conventions | domain | `GAP-TECH-DEEP-DIVE-INPUT` |
| 5.7/idempotency | domain | `GAP-TECH-DEEP-DIVE-INPUT` |
| 5.7/versioning | domain | `GAP-TECH-DEEP-DIVE-INPUT` |
| 5.7/endpoints | domain | `GAP-TECH-DEEP-DIVE-INPUT` |
| 5.8/mapping | domain | `GAP-TECH-DEEP-DIVE-INPUT` |
| 5.9/file_interfaces | domain | `GAP-TECH-DEEP-DIVE-INPUT` |
| 5.9/restart | domain | `GAP-TECH-DEEP-DIVE-INPUT` |
| 5.10 | domain | `GAP-TECH-DEEP-DIVE-INPUT` |
| 5.11/constraints | domain | `GAP-GOVERNANCE-CONSTRAINTS` |
| 5.11/authn | domain | `GAP-GOVERNANCE-CONSTRAINTS` |
| 5.11/authz | domain | `GAP-GOVERNANCE-CONSTRAINTS` |
| 5.11/data_protection | domain | `GAP-GOVERNANCE-CONSTRAINTS` |
| 5.11/audit | domain | `GAP-GOVERNANCE-CONSTRAINTS` |
| 5.11/regulatory_controls | domain | `GAP-GOVERNANCE-CONSTRAINTS` |
| 5.11/implementer_limits | domain | `GAP-GOVERNANCE-CONSTRAINTS` |
| 5.12/services | domain | `GAP-BACKEND-SURFACE` |
| 5.12/client_state | domain | `GAP-BACKEND-SURFACE` |
| 5.12/jobs | domain | `GAP-BACKEND-SURFACE` |
| 5.13/data_migration | domain | `GAP-TECH-DEEP-DIVE-INPUT` |
| 5.14 | domain | `GAP-TECH-DEEP-DIVE-INPUT` |
| 5.15 | domain | `GAP-TECH-DEEP-DIVE-INPUT` |
| 5.16/quality_attributes | domain | `GAP-PRD-NFR-KPI` |
| 5.16/sli_slo | domain | `GAP-PRD-NFR-KPI` |
| 5.16/observability | domain | `GAP-PRD-NFR-KPI` |
| 5.16/alerts | domain | `GAP-PRD-NFR-KPI` |
| 5.18 | domain | `GAP-TECH-DEEP-DIVE-INPUT` |
| 5.19 | domain | `GAP-TECH-DEEP-DIVE-INPUT` |
| 5.20 | domain | `GAP-TECH-DEEP-DIVE-INPUT` |
| 5.21 | domain | `GAP-TECH-DEEP-DIVE-INPUT` |
| 5.22 | domain | `GAP-TECH-DEEP-DIVE-INPUT` |
| 5.23 | domain | `GAP-TECH-DEEP-DIVE-INPUT` |
| 5.25 | domain | `GAP-TECH-DEEP-DIVE-INPUT` |
| A.glossary | client | `GAP-PRD-GLOSSARY-GOVERNANCE` |
| 9.1/non_software | domain | `GAP-BACKLOG-ENABLERS` |
| 7.1/risks | domain | `GAP-PRD-DEPENDENCIES-ROADMAP` |

## 8. Assumptions

### 8.1 Assumptions List

No assumptions recorded.

## 9. Things to Build

### 9.1 Build List or Phases

#### Build list or phases

- `C-01` In scope: read-only risk dashboard for open queues. [[sources § Source log - [PROJECT_ID] # F-01 — supports: Build List or Phases]] — depends on: none

#### Non-software work

⏳ PENDING DOMAIN (GAP-BACKLOG-ENABLERS)

#### Conclusion

Ready to build: no. 15 pending marks block (§7).

## A.glossary Domain Glossary

⏳ PENDING (GAP-PRD-GLOSSARY-GOVERNANCE)

## A.provenance Provenance and Reference Data

| Source | Facts cited |
|---|---|
| `F-01` | 8 |
| `F-02` | 1 |
| `F-03` | 1 |
| `F-04` | 1 |
| `F-05` | 1 |
| `F-06` | 1 |
| `F-07` | 1 |
