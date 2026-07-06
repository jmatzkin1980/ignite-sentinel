# Project Brief - [PROJECT_ID]

This brief is the mature discovery output. It reflects iterated requirement evidence and is the source handoff for PRD, specs, backlog, acceptance criteria, and tests.

Depth principle: the brief should be complete enough to guide domain work without becoming the domain deliverable itself. Design, Technology, and Quality may deepen the analysis later in dedicated context packs.

## 1. Identidad y Valor

Iniciativa: Tablero de riesgo operativo _(fuente: `00_raw/`)_

Dolor principal:
- Domains: product, functional, quality

Resultado y métricas:
- Resultado esperado: "Objetivo: que los lideres de operaciones revisen las colas de riesgo antes de la reunion diaria." _(fuente: `00_raw/`)_
- Métrica: `30 por ciento` — "Metrica: reducir la preparacion manual un 30 por ciento en el primer mes de release." _(fuente: `00_raw/`)_

## 2. Lente de Negocio: Actores y Necesidades

- Usuarios: lideres de operaciones. _(fuente: `00_raw/`)_

## 3. Lente de Producto: Proceso y Journey

- Situación actual (as-is): "Metrica: reducir la preparacion manual un 30 por ciento en el primer mes de release." _(fuente: `00_raw/`)_
- Proceso objetivo (to-be): se rastrea en `GAP-PRODUCT-ASIS-TOBE`.
- In scope: "Alcance: tablero de solo lectura de colas abiertas." _(fuente: `00_raw/`)_
- Out of scope: "Fuera de alcance: editar casos." _(fuente: `00_raw/`)_

## 4. Lente de Diseno: Flujos y Resiliencia UX

- [PENDING INPUT]: sin evidencia en el input; se rastrea en `GAP-DESIGN-FLOW`. Aportar en el context pack del dominio.

Sweet spot: identify affected journeys, screens, decisions, states, and UX constraints; detailed prototypes and final interaction specs belong in the design context pack.

## 5. Lente Tecnico: Datos, Conectividad y Arquitectura

- [PENDING INPUT]: sin evidencia en el input; se rastrea en `GAP-TECH-DATA-SOURCE`. Aportar en el context pack del dominio.

Data and contract depth: include key entities, critical fields, and contract direction only when needed; exhaustive dictionaries, schemas, and sequence diagrams belong in the technology context pack.

## 6. Gobernanza y Restricciones

- [PENDING INPUT]: sin evidencia en el input; se rastrea en `GAP-GOVERNANCE-CONSTRAINTS`. Aportar en el context pack del dominio.

Auditability and traceability expectations: all downstream artifacts must cite this brief and raw evidence.

## 7. Decisiones, Seeds e Inferencias

### Seeds Confirmadas o Pendientes

| Seed ID | Lens | Origin Type | Origin Ref | Atomic Statement | Status | Node Type |
| --- | --- | --- | --- | --- | --- | --- |
| SEED-001 | business | INPUT | `RAW-001` | Objetivo: que los lideres de operaciones revisen las colas de riesgo antes de la reunion diaria. | KNOWN | BIZ_OBJECTIVE |
| SEED-002 | business | INPUT | `RAW-001` | Usuarios: lideres de operaciones. | KNOWN | USER_CONTEXT |
| SEED-003 | product | INPUT | `RAW-001` | Alcance: tablero de solo lectura de colas abiertas. Fuera de alcance: editar casos. | KNOWN | SCOPE_RULE |
| SEED-004 | business | INPUT | `RAW-001` | Metrica: reducir la preparacion manual un 30 por ciento en el primer mes de release. | PENDING_SOURCE | METRIC |
| SEED-005 | business | INPUT | `RAW-001` | Business rules, exclusions, or decision rules are not explicit enough for downstream slicing. | PENDING | GAP_PLACEHOLDER |
| SEED-006 | product | INPUT | `RAW-001` | Persona attributes are not complete enough for a PRD: goals, pain points, proficiency, and usage frequency are unclear. | PENDING | GAP_PLACEHOLDER |
| SEED-007 | business | INPUT | `RAW-001` | Quantitative metric appears without an explicit source or baseline. | PENDING | GAP_PLACEHOLDER |
| SEED-008 | business | INPUT | `RAW-001` | A metric, KPI, or indicator concept is named without its definition, formula, unit, source, or threshold. | PENDING | GAP_PLACEHOLDER |
| SEED-009 | product | INPUT | `RAW-001` | Current state and target state are not both explicit enough to compare impact. | PENDING | GAP_PLACEHOLDER |
| SEED-010 | product | INPUT | `RAW-001` | Backlog slicing signals are not explicit enough: first value slice, workflow paths, variants, rule deferral, or story boundaries are unclear. | PENDING | GAP_PLACEHOLDER |

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

- `GAP-BUSINESS-RULES` (business, medium): Las reglas de negocio, exclusiones o reglas de decisión no están suficientemente explícitas para slicing downstream.
- `GAP-PRD-PERSONA-DETAIL` (business, medium): Persona attributes are not complete enough for a PRD: goals, pain points, proficiency, and usage frequency are unclear.
- `GAP-METRIC-SOURCE` (business, medium): Aparece una métrica cuantitativa sin fuente o baseline explícito.
- `GAP-METRIC-DEFINITION` (business, medium): Se nombra una métrica, KPI o indicador sin su definición, fórmula, unidad, fuente ni umbral.
- `GAP-PRODUCT-ASIS-TOBE` (product, medium): El estado actual y el estado objetivo no están suficientemente claros para comparar impacto.
- `GAP-BACKLOG-SLICING-READINESS` (product, medium): No estan explicitas las senales necesarias para slicing de backlog: primer slice de valor, paths, variantes, reglas diferibles o limites de historia.
- `GAP-PRD-FR-AC` (product, medium): Functional requirements are not decomposed with source-backed acceptance criteria.
- `GAP-QUALITY` (quality, medium): Las expectativas de calidad o testeabilidad no están explícitas.
- `GAP-QUALITY-HANDOFF` (quality, medium): El handoff a Calidad no está suficientemente explícito: flujos críticos, casos borde, datos de prueba, riesgos de regresión o evidencia esperada.
- `GAP-PRD-NFR-KPI` (quality, medium): NFRs, KPIs, targets, measurement method, or timeframe are not explicit enough for PRD governance.
- `GAP-TECH-DATA-SOURCE` (technical, medium): La fuente de datos, integración u ownership de sistema no está explícito en el input o contexto técnico.
- `GAP-TECH-NFR` (technical, medium): No están explícitas restricciones de performance, seguridad, observabilidad u operación.
- `GAP-BACKLOG-ENABLERS` (technical, medium): No estan claros los enablers transversales validos: trabajo de implementacion frontend/backend o arquitectura que debe construirse antes para soportar funcionalidades confirmadas dentro del boundary del proyecto.
- `GAP-FRONTEND-SURFACE` (technical, medium): La superficie de implementación frontend no está suficientemente explícita: pantallas, estados, validaciones, copy, roles o bindings de API.
- `GAP-BACKEND-SURFACE` (technical, medium): La superficie de implementación backend no está suficientemente explícita: capacidades, integraciones, reglas, persistencia, contratos o comportamiento ante fallas.
- `GAP-TECH-DEEP-DIVE-INPUT` (technical, medium): Tecnología no cuenta con suficiente input para análisis de repositorios, arquitectura, endpoints/eventos, source of truth o riesgos.
- `GAP-GOVERNANCE-CONSTRAINTS` (compliance, medium): No están explícitas restricciones de gobernanza, seguridad, privacidad, compliance u operación.
- `GAP-PRD-GLOSSARY-GOVERNANCE` (compliance, medium): Glossary, mandatory constraints, pending inputs, or governance/audit notes are not explicit enough for a complete PRD.
- `GAP-DELIVERY-READINESS` (delivery, medium): No están explícitas dependencias, ambientes, ownership, fechas o restricciones de rollout.
- `GAP-PRD-DEPENDENCIES-ROADMAP` (delivery, medium): Dependencies, owners, MVP scope, nice-to-haves, or roadmap are not explicit enough for PRD execution planning.
- `GAP-PRD-ROLLOUT-ENVIRONMENTS` (delivery, medium): Rollout approach, target environments, or release constraints are not explicit enough for PRD execution planning.
- `GAP-DESIGN-FLOW` (design, medium): El journey de usuario, flujo de pantallas o modelo de interacción no está explícito en el input o contexto de diseño.
- `GAP-DESIGN-STATES` (design, medium): No están explícitos los estados requeridos de UI: loading, empty, error y recuperación.
- `GAP-DESIGN-PROTOTYPE-INPUT` (design, medium): No queda claro qué debe prototipar o validar Diseño en los flujos de usuario.

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
