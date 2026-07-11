# Specs - [PROJECT_ID]

## Spec Contract

- Purpose: provide an agent-friendly execution contract for backlog generation.
- Human PRD: `03_specs/prd.md`
- Mature source: `02_requirements/project-brief.md`
- Trace anchors: `REQ-001`, `PRD-001`, `SPEC-001`
- Context pack: `08_context_packs/specs_generation.json`
- Rule: agents must retrieve focused context before expanding backlog slices. Do not reread the whole workspace unless the retrieval pack is insufficient.
- Unit rule: execution detail lives in `03_specs/units/SPEC-U-NNN.md`; this file is the index and handoff contract.

## Requirement Snapshot

The mature requirement remains authoritative in `02_requirements/project-brief.md`. This spec keeps only the execution signals agents need before progressive disclosure.

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

### No-Objetivos (Non-Goals)

- Sin non-goals registrados: no hay cierres out-of-scope/no-aplica ni decisiones de alcance que excluyan trabajo. Se completa solo desde datos gobernados; no se inventa.

## 4. Lente de Diseno: Flujos y Resiliencia UX

- [PENDING INPUT]: sin evidencia en el input; se rastrea en `GAP-DESIGN-FLOW`. Aportar en el context pack del dominio.

Sweet spot: identify affected journeys, screens, decisions, states, and UX constraints; detailed prototypes and final interaction specs belong in the design context pack.

## 5. Lente Tecnico: Datos, Conectividad y Arquitectura

- [PENDING INPUT]: sin evidencia en el input; se rastrea en `GAP-TECH-DATA-SOURCE`. Aportar en el context pack del dominio.

Data and contract depth: include key entities, critical fields, and contract direction only when need

[TRUNCATED IN GENERATED ARTIFACT - retrieve focused source context if needed]

## Backlog-Relevant Contract

| Contract Item | Rule |
| --- | --- |
| Source hierarchy | Workspace files win over memory. PRD/specs summarize, they do not replace source evidence. |
| Traceability | Every epic/story/AC must cite `REQ-001`, `PRD-001`, `SPEC-001`, and at least one FR/JTBD/rule where applicable. When confirmed EARS rows exist, cite the relevant `REQ-EARS-*` IDs too. |
| Missing evidence | Keep `[PENDING INPUT]` or create/follow a `GAP-*`; do not invent. |
| Story size | `Small` means the smallest independently meaningful, testable, useful slice. Do not split into micro-stories that no longer produce value or reduce a named risk. |
| Cross-cutting enablers | Enablers may live in a separate epic only when they are implementation work built in advance to support confirmed functionality across stories, epics, FRs, or implementation surfaces. They must reduce concrete risk/dependency and have objective acceptance evidence. |
| Preconditions | Generic access, environment availability, broad infrastructure readiness, or vague setup are preconditions/external tasks unless tied to confirmed project functionality and implementation evidence. |
| Privacy | Do not include sensitive client data, credentials, URLs, account IDs, or raw payloads in backlog artifacts. |

## Spec Units

| Unit ID | Execution Slice | EARS Trace | File |
| --- | --- | --- | --- |
| `SPEC-U-001` | Cuando haya metricas de cola disponibles, el sistema debe mostrar las colas de riesgo abiertas. | `REQ-EARS-001` | `03_specs/units/SPEC-U-001.md` |
| `SPEC-U-002` | Cuando un caso incumpla el SLA, el sistema debe marcar la cola como riesgo alto. | `REQ-EARS-002` | `03_specs/units/SPEC-U-002.md` |
| `SPEC-U-003` | Cuando una cola no tenga casos abiertos, el sistema debe ocultar los indicadores de riesgo. | `REQ-EARS-003` | `03_specs/units/SPEC-U-003.md` |
| `SPEC-U-004` | Mientras los datos de riesgo esten desactualizados, el sistema debe mostrar una advertencia de datos obsoletos. | `REQ-EARS-004` | `03_specs/units/SPEC-U-004.md` |
| `SPEC-U-005` | Si el servicio de metricas no esta disponible, entonces el sistema debe mostrar estado de riesgo desconocido. | `REQ-EARS-005` | `03_specs/units/SPEC-U-005.md` |
| `SPEC-U-006` | Donde el registro de auditoria este habilitado, el sistema debe registrar el acceso al tablero. | `REQ-EARS-006` | `03_specs/units/SPEC-U-006.md` |

## Confirmed EARS Requirements

These rows are parsed from `02_requirements/requirements.md` and remain source-of-truth there. Specs and backlog cite their `REQ-EARS-*` IDs so testable statements survive downstream handoff.

| ID | EARS Pattern | Testable Statement | Source |
| --- | --- | --- | --- |
| `REQ-EARS-001` | event | Cuando haya metricas de cola disponibles, el sistema debe mostrar las colas de riesgo abiertas. | GAP-ACCEPTANCE` / `CHG-001 |
| `REQ-EARS-002` | event | Cuando un caso incumpla el SLA, el sistema debe marcar la cola como riesgo alto. | GAP-ACCEPTANCE` / `CHG-002 |
| `REQ-EARS-003` | event | Cuando una cola no tenga casos abiertos, el sistema debe ocultar los indicadores de riesgo. | GAP-ACCEPTANCE` / `CHG-003 |
| `REQ-EARS-004` | state | Mientras los datos de riesgo esten desactualizados, el sistema debe mostrar una advertencia de datos obsoletos. | GAP-ACCEPTANCE` / `CHG-004 |
| `REQ-EARS-005` | unwanted | Si el servicio de metricas no esta disponible, entonces el sistema debe mostrar estado de riesgo desconocido. | GAP-ACCEPTANCE` / `CHG-005 |
| `REQ-EARS-006` | optional | Donde el registro de auditoria este habilitado, el sistema debe registrar el acceso al tablero. | GAP-ACCEPTANCE` / `CHG-006 |

## Progressive Disclosure Context Map

| PRD / Specs Need | Retrieved Signal | Artifact | Trace |
| --- | --- | --- | --- |
| strategic_foundation | ## 1. Identidad y Valor  Iniciativa: Tablero de riesgo operativo _(fuente: `00_raw/`)_  Dolor principal: - Domains: product, functional, quality  Resultado y métricas: - Resultado | `REQ-003` | REQ-003 |
| personas | / PRD Section / Required Discovery Signal / Evidence Source / If Missing / / --- / --- / --- / --- / / Personas / Primary/secondary personas, goals, pains, proficiency, usage frequ | `REQ-003` | REQ-003 |
| functional_requirements | - `GAP-BUSINESS-RULES` (business, medium): Las reglas de negocio, exclusiones o reglas de decisión no están suficientemente explícitas para slicing downstream. - `GAP-PRD-PERSONA-D | `REQ-003` | REQ-003 |
| nfr_kpi | ## 5. Lente Tecnico: Datos, Conectividad y Arquitectura  - [PENDING INPUT]: sin evidencia en el input; se rastrea en `GAP-TECH-DATA-SOURCE`. Aportar en el context pack del dominio. | `REQ-003` | REQ-003 |
| jtbd_traceability | / PRD Section / Required Discovery Signal / Evidence Source / If Missing / / --- / --- / --- / --- / / Personas / Primary/secondary personas, goals, pains, proficiency, usage frequ | `REQ-003` | REQ-003 |
| execution_plan | - `GAP-BUSINESS-RULES` (business, medium): Las reglas de negocio, exclusiones o reglas de decisión no están suficientemente explícitas para slicing downstream. - `GAP-PRD-PERSONA-D | `REQ-003` | REQ-003 |
| governance | / PRD Section / Required Discovery Signal / Evidence Source / If Missing / / --- / --- / --- / --- / / Personas / Primary/secondary personas, goals, pains, proficiency, usage frequ | `REQ-003` | REQ-003 |
| backlog_handoff | - PRD can expand this brief only from confirmed seeds, decisions, context folders, and traceable source material. - Specs must preserve system boundaries, data ownership, UX states | `REQ-003` | REQ-003 |

## Retrieval Plan For Backlog Agents

| Need | Suggested `/retrieve` Query | Filters | Use In Backlog |
| --- | --- | --- | --- |
| Epic value and MVP | `business outcome scope mvp kpi users` | `--workflow backlog --domain business --summary-only` | Epic outcome and priority |
| FR and AC slicing | `functional requirements acceptance criteria given when then business rules` | `--workflow backlog --domain product` | Story boundaries and ACs |
| Technical dependencies | `architecture integrations dependencies data ownership contracts failure behavior` | `--workflow backlog --domain technical` | Backend/technical stories and blockers |
| UX stories | `journey screens states validations copy accessibility unchanged behavior` | `--workflow backlog --domain design` | Frontend stories and UX acceptance |
| Quality coverage | `acceptance testability edge cases regression test data evidence` | `--workflow backlog --domain quality` | ACs, TC seeds, readiness audit |
| Open gaps | `pending input prd gaps dependencies roadmap nfr kpi` | `--workflow backlog --artifact-type gap_report` | Blockers, spikes, follow-up stories |
| Enabler boundary | `SAD architecture as-is to-be frontend backend prototype auth data integration audit observability enabler precondition` | `--workflow backlog --summary-only` | Decide whether a cross-cutting enabler epic is valid |

## Backlog Seeds

Backlog seeds are derived from evidence-backed spec units. If no unit exists, backlog agents must work from pending inputs and focused retrieval rather than fixed placeholder stories.

| Source Unit | Candidate Item | Type | Trace |
| --- | --- | --- | --- |
| `SPEC-U-001` | Slice the behavior described by this unit into the smallest meaningful value story. | User Story Candidate | `REQ-EARS-001` |
| `SPEC-U-002` | Slice the behavior described by this unit into the smallest meaningful value story. | User Story Candidate | `REQ-EARS-002` |
| `SPEC-U-003` | Slice the behavior described by this unit into the smallest meaningful value story. | User Story Candidate | `REQ-EARS-003` |
| `SPEC-U-004` | Slice the behavior described by this unit into the smallest meaningful value story. | User Story Candidate | `REQ-EARS-004` |
| `SPEC-U-005` | Slice the behavior described by this unit into the smallest meaningful value story. | User Story Candidate | `REQ-EARS-005` |
| `SPEC-U-006` | Slice the behavior described by this unit into the smallest meaningful value story. | User Story Candidate | `REQ-EARS-006` |

## Decision And Assumption Trail

| Source | Type | Statement | Risk If Wrong |
| --- | --- | --- | --- |
| Sentinel invariant | Rule | Any detail not present in seeds, source input, spec units, or domain context remains pending confirmation. | Downstream backlog may require rework after `/sync`. |
| PRD readiness | Rule | PRD-generated FR/JTBD/NFR structure must be checked against evidence before slicing. | Stories may need refinement if PRD readiness gaps remain. |

## Traceability

- Parent requirement: `REQ-001`
- EARS requirements: `REQ-EARS-001`, `REQ-EARS-002`, `REQ-EARS-003`, `REQ-EARS-004`, `REQ-EARS-005`, `REQ-EARS-006`
- Parent PRD: `PRD-001`
- Spec units: `SPEC-U-001`, `SPEC-U-002`, `SPEC-U-003`, `SPEC-U-004`, `SPEC-U-005`, `SPEC-U-006`
- Mature brief: `02_requirements/project-brief.md` when present
- Context pack: `08_context_packs/specs_generation.json`
- Downstream artifacts: epics, user stories, acceptance criteria, tests, and traceability matrix.
