# Backlog Readiness Audit - [PROJECT_ID]

This audit checks whether backlog items are ready for downstream execution using Sentinel vNext traceability and domain context.

## Verdict

`PARTIAL`

## Story Census

| Story ID | Title | INVEST/SPIDR Score | Status | Review Notes |
| --- | --- | ---: | --- | --- |
| `US-001` | SPEC-U-001 - haya metricas de cola disponibles, el sistema debe mostrar las colas de riesgo abiertas | 0.83 | WARN | Story must be small but still independently meaningful, testable and useful. |
| `US-002` | SPEC-U-002 - un caso incumpla el SLA, el sistema debe marcar la cola como riesgo alto | 0.83 | WARN | Story must be small but still independently meaningful, testable and useful. |
| `US-003` | SPEC-U-003 - una cola no tenga casos abiertos, el sistema debe ocultar los indicadores de riesgo | 0.83 | WARN | Story must be small but still independently meaningful, testable and useful. |
| `US-004` | SPEC-U-004 - los datos de riesgo esten desactualizados, el sistema debe mostrar una advertencia de datos obso | 0.83 | WARN | Story must be small but still independently meaningful, testable and useful. |
| `US-005` | SPEC-U-005 - el servicio de metricas no esta disponible, entonces el sistema debe mostrar estado de riesgo de | 0.83 | WARN | Story must be small but still independently meaningful, testable and useful. |
| `US-006` | SPEC-U-006 - el registro de auditoria este habilitado, el sistema debe registrar el acceso al tablero | 0.83 | WARN | Story must be small but still independently meaningful, testable and useful. |
| `US-007` | Preparar persistencia y consultas internas del flujo | 1.00 | PASS | No INVEST/SPIDR warnings. |

## Story Quality Checks

### US-001

| Check | Status | Finding |
| --- | --- | --- |
| slicing_pattern_governed | PASS | OK |
| vertical_slice | PASS | OK |
| small_but_valuable | WARN | Story must be small but still independently meaningful, testable and useful. |
| acceptance_criteria_coverage | PASS | OK |
| traceability_chain | PASS | OK |
| independent_dependencies | PASS | OK |

#### Parallel INVEST Audit

Passed `5/6` structural signals.

| Letter | Signal | Status | Finding | Evidence |
| --- | --- | --- | --- | --- |
| I | Independent | PASS | No prerequisite story or pending dependency is required to start this slice. | source_unit: `SPEC-U-001`; trace: `REQ-001`, `PRD-001`, `SPEC-001`, `SPEC-U-001`, `REQ-EARS-001` |
| N | Negotiable | PASS | The story is framed as a traced outcome contract with acceptance coverage. | trace: `SPEC-U-001`, `REQ-001`, `SPEC-001`, `REQ-EARS-001`; acceptance_ids: `AC-001-01`, `AC-001-02`, `AC-001-03`, `AC-001-04`, `AC-001-05`; acceptance_classes: `evidence`, `fail-to-pass`, `pass-to-pass` |
| V | Valuable | PASS | Value is anchored to upstream requirements or to enabled downstream stories. | source_unit: `SPEC-U-001`; trace: `SPEC-U-001`, `REQ-001`, `SPEC-001`, `REQ-EARS-001` |
| E | Estimable | PASS | Scope, dependencies, and acceptance coverage are explicit enough to estimate. | trace: `SPEC-U-001`, `REQ-001`, `SPEC-001`, `REQ-EARS-001`; acceptance_classes: `evidence`, `fail-to-pass`, `pass-to-pass`; readiness_score: 0.60 |
| S | Small | WARN | The slice looks broad because upstream scope or prerequisite coupling is not tightly bounded. | source_unit: `SPEC-U-001`; trace: `SPEC-U-001`, `REQ-001`, `SPEC-001`, `REQ-EARS-001` |
| T | Testable | PASS | Classified acceptance criteria cover fail-to-pass, pass-to-pass, and evidence paths. | acceptance_ids: `AC-001-01`, `AC-001-02`, `AC-001-03`, `AC-001-04`, `AC-001-05`; acceptance_classes: `evidence`, `fail-to-pass`, `pass-to-pass` |


### US-002

| Check | Status | Finding |
| --- | --- | --- |
| slicing_pattern_governed | PASS | OK |
| vertical_slice | PASS | OK |
| small_but_valuable | WARN | Story must be small but still independently meaningful, testable and useful. |
| acceptance_criteria_coverage | PASS | OK |
| traceability_chain | PASS | OK |
| independent_dependencies | PASS | OK |

#### Parallel INVEST Audit

Passed `5/6` structural signals.

| Letter | Signal | Status | Finding | Evidence |
| --- | --- | --- | --- | --- |
| I | Independent | PASS | No prerequisite story or pending dependency is required to start this slice. | source_unit: `SPEC-U-002`; trace: `REQ-001`, `PRD-001`, `SPEC-001`, `SPEC-U-002`, `REQ-EARS-002` |
| N | Negotiable | PASS | The story is framed as a traced outcome contract with acceptance coverage. | trace: `SPEC-U-002`, `REQ-001`, `SPEC-001`, `REQ-EARS-002`; acceptance_ids: `AC-002-01`, `AC-002-02`, `AC-002-03`, `AC-002-04`, `AC-002-05`; acceptance_classes: `evidence`, `fail-to-pass`, `pass-to-pass` |
| V | Valuable | PASS | Value is anchored to upstream requirements or to enabled downstream stories. | source_unit: `SPEC-U-002`; trace: `SPEC-U-002`, `REQ-001`, `SPEC-001`, `REQ-EARS-002` |
| E | Estimable | PASS | Scope, dependencies, and acceptance coverage are explicit enough to estimate. | trace: `SPEC-U-002`, `REQ-001`, `SPEC-001`, `REQ-EARS-002`; acceptance_classes: `evidence`, `fail-to-pass`, `pass-to-pass`; readiness_score: 0.60 |
| S | Small | WARN | The slice looks broad because upstream scope or prerequisite coupling is not tightly bounded. | source_unit: `SPEC-U-002`; trace: `SPEC-U-002`, `REQ-001`, `SPEC-001`, `REQ-EARS-002` |
| T | Testable | PASS | Classified acceptance criteria cover fail-to-pass, pass-to-pass, and evidence paths. | acceptance_ids: `AC-002-01`, `AC-002-02`, `AC-002-03`, `AC-002-04`, `AC-002-05`; acceptance_classes: `evidence`, `fail-to-pass`, `pass-to-pass` |


### US-003

| Check | Status | Finding |
| --- | --- | --- |
| slicing_pattern_governed | PASS | OK |
| vertical_slice | PASS | OK |
| small_but_valuable | WARN | Story must be small but still independently meaningful, testable and useful. |
| acceptance_criteria_coverage | PASS | OK |
| traceability_chain | PASS | OK |
| independent_dependencies | PASS | OK |

#### Parallel INVEST Audit

Passed `5/6` structural signals.

| Letter | Signal | Status | Finding | Evidence |
| --- | --- | --- | --- | --- |
| I | Independent | PASS | No prerequisite story or pending dependency is required to start this slice. | source_unit: `SPEC-U-003`; trace: `REQ-001`, `PRD-001`, `SPEC-001`, `SPEC-U-003`, `REQ-EARS-003` |
| N | Negotiable | PASS | The story is framed as a traced outcome contract with acceptance coverage. | trace: `SPEC-U-003`, `REQ-001`, `SPEC-001`, `REQ-EARS-003`; acceptance_ids: `AC-003-01`, `AC-003-02`, `AC-003-03`, `AC-003-04`, `AC-003-05`; acceptance_classes: `evidence`, `fail-to-pass`, `pass-to-pass` |
| V | Valuable | PASS | Value is anchored to upstream requirements or to enabled downstream stories. | source_unit: `SPEC-U-003`; trace: `SPEC-U-003`, `REQ-001`, `SPEC-001`, `REQ-EARS-003` |
| E | Estimable | PASS | Scope, dependencies, and acceptance coverage are explicit enough to estimate. | trace: `SPEC-U-003`, `REQ-001`, `SPEC-001`, `REQ-EARS-003`; acceptance_classes: `evidence`, `fail-to-pass`, `pass-to-pass`; readiness_score: 0.60 |
| S | Small | WARN | The slice looks broad because upstream scope or prerequisite coupling is not tightly bounded. | source_unit: `SPEC-U-003`; trace: `SPEC-U-003`, `REQ-001`, `SPEC-001`, `REQ-EARS-003` |
| T | Testable | PASS | Classified acceptance criteria cover fail-to-pass, pass-to-pass, and evidence paths. | acceptance_ids: `AC-003-01`, `AC-003-02`, `AC-003-03`, `AC-003-04`, `AC-003-05`; acceptance_classes: `evidence`, `fail-to-pass`, `pass-to-pass` |


### US-004

| Check | Status | Finding |
| --- | --- | --- |
| slicing_pattern_governed | PASS | OK |
| vertical_slice | PASS | OK |
| small_but_valuable | WARN | Story must be small but still independently meaningful, testable and useful. |
| acceptance_criteria_coverage | PASS | OK |
| traceability_chain | PASS | OK |
| independent_dependencies | PASS | OK |

#### Parallel INVEST Audit

Passed `5/6` structural signals.

| Letter | Signal | Status | Finding | Evidence |
| --- | --- | --- | --- | --- |
| I | Independent | PASS | No prerequisite story or pending dependency is required to start this slice. | source_unit: `SPEC-U-004`; trace: `REQ-001`, `PRD-001`, `SPEC-001`, `SPEC-U-004`, `REQ-EARS-004` |
| N | Negotiable | PASS | The story is framed as a traced outcome contract with acceptance coverage. | trace: `SPEC-U-004`, `REQ-001`, `SPEC-001`, `REQ-EARS-004`; acceptance_ids: `AC-004-01`, `AC-004-02`, `AC-004-03`, `AC-004-04`, `AC-004-05`; acceptance_classes: `evidence`, `fail-to-pass`, `pass-to-pass` |
| V | Valuable | PASS | Value is anchored to upstream requirements or to enabled downstream stories. | source_unit: `SPEC-U-004`; trace: `SPEC-U-004`, `REQ-001`, `SPEC-001`, `REQ-EARS-004` |
| E | Estimable | PASS | Scope, dependencies, and acceptance coverage are explicit enough to estimate. | trace: `SPEC-U-004`, `REQ-001`, `SPEC-001`, `REQ-EARS-004`; acceptance_classes: `evidence`, `fail-to-pass`, `pass-to-pass`; readiness_score: 0.60 |
| S | Small | WARN | The slice looks broad because upstream scope or prerequisite coupling is not tightly bounded. | source_unit: `SPEC-U-004`; trace: `SPEC-U-004`, `REQ-001`, `SPEC-001`, `REQ-EARS-004` |
| T | Testable | PASS | Classified acceptance criteria cover fail-to-pass, pass-to-pass, and evidence paths. | acceptance_ids: `AC-004-01`, `AC-004-02`, `AC-004-03`, `AC-004-04`, `AC-004-05`; acceptance_classes: `evidence`, `fail-to-pass`, `pass-to-pass` |


### US-005

| Check | Status | Finding |
| --- | --- | --- |
| slicing_pattern_governed | PASS | OK |
| vertical_slice | PASS | OK |
| small_but_valuable | WARN | Story must be small but still independently meaningful, testable and useful. |
| acceptance_criteria_coverage | PASS | OK |
| traceability_chain | PASS | OK |
| independent_dependencies | PASS | OK |

#### Parallel INVEST Audit

Passed `5/6` structural signals.

| Letter | Signal | Status | Finding | Evidence |
| --- | --- | --- | --- | --- |
| I | Independent | PASS | No prerequisite story or pending dependency is required to start this slice. | source_unit: `SPEC-U-005`; trace: `REQ-001`, `PRD-001`, `SPEC-001`, `SPEC-U-005`, `REQ-EARS-005` |
| N | Negotiable | PASS | The story is framed as a traced outcome contract with acceptance coverage. | trace: `SPEC-U-005`, `REQ-001`, `SPEC-001`, `REQ-EARS-005`; acceptance_ids: `AC-005-01`, `AC-005-02`, `AC-005-03`, `AC-005-04`, `AC-005-05`; acceptance_classes: `evidence`, `fail-to-pass`, `pass-to-pass` |
| V | Valuable | PASS | Value is anchored to upstream requirements or to enabled downstream stories. | source_unit: `SPEC-U-005`; trace: `SPEC-U-005`, `REQ-001`, `SPEC-001`, `REQ-EARS-005` |
| E | Estimable | PASS | Scope, dependencies, and acceptance coverage are explicit enough to estimate. | trace: `SPEC-U-005`, `REQ-001`, `SPEC-001`, `REQ-EARS-005`; acceptance_classes: `evidence`, `fail-to-pass`, `pass-to-pass`; readiness_score: 0.60 |
| S | Small | WARN | The slice looks broad because upstream scope or prerequisite coupling is not tightly bounded. | source_unit: `SPEC-U-005`; trace: `SPEC-U-005`, `REQ-001`, `SPEC-001`, `REQ-EARS-005` |
| T | Testable | PASS | Classified acceptance criteria cover fail-to-pass, pass-to-pass, and evidence paths. | acceptance_ids: `AC-005-01`, `AC-005-02`, `AC-005-03`, `AC-005-04`, `AC-005-05`; acceptance_classes: `evidence`, `fail-to-pass`, `pass-to-pass` |


### US-006

| Check | Status | Finding |
| --- | --- | --- |
| slicing_pattern_governed | PASS | OK |
| vertical_slice | PASS | OK |
| small_but_valuable | WARN | Story must be small but still independently meaningful, testable and useful. |
| acceptance_criteria_coverage | PASS | OK |
| traceability_chain | PASS | OK |
| independent_dependencies | PASS | OK |

#### Parallel INVEST Audit

Passed `5/6` structural signals.

| Letter | Signal | Status | Finding | Evidence |
| --- | --- | --- | --- | --- |
| I | Independent | PASS | No prerequisite story or pending dependency is required to start this slice. | source_unit: `SPEC-U-006`; trace: `REQ-001`, `PRD-001`, `SPEC-001`, `SPEC-U-006`, `REQ-EARS-006` |
| N | Negotiable | PASS | The story is framed as a traced outcome contract with acceptance coverage. | trace: `SPEC-U-006`, `REQ-001`, `SPEC-001`, `REQ-EARS-006`; acceptance_ids: `AC-006-01`, `AC-006-02`, `AC-006-03`, `AC-006-04`, `AC-006-05`; acceptance_classes: `evidence`, `fail-to-pass`, `pass-to-pass` |
| V | Valuable | PASS | Value is anchored to upstream requirements or to enabled downstream stories. | source_unit: `SPEC-U-006`; trace: `SPEC-U-006`, `REQ-001`, `SPEC-001`, `REQ-EARS-006` |
| E | Estimable | PASS | Scope, dependencies, and acceptance coverage are explicit enough to estimate. | trace: `SPEC-U-006`, `REQ-001`, `SPEC-001`, `REQ-EARS-006`; acceptance_classes: `evidence`, `fail-to-pass`, `pass-to-pass`; readiness_score: 0.60 |
| S | Small | WARN | The slice looks broad because upstream scope or prerequisite coupling is not tightly bounded. | source_unit: `SPEC-U-006`; trace: `SPEC-U-006`, `REQ-001`, `SPEC-001`, `REQ-EARS-006` |
| T | Testable | PASS | Classified acceptance criteria cover fail-to-pass, pass-to-pass, and evidence paths. | acceptance_ids: `AC-006-01`, `AC-006-02`, `AC-006-03`, `AC-006-04`, `AC-006-05`; acceptance_classes: `evidence`, `fail-to-pass`, `pass-to-pass` |


### US-007

| Check | Status | Finding |
| --- | --- | --- |
| slicing_pattern_governed | PASS | OK |
| vertical_slice | PASS | OK |
| small_but_valuable | PASS | OK |
| acceptance_criteria_coverage | PASS | OK |
| traceability_chain | PASS | OK |
| independent_dependencies | PASS | OK |

#### Parallel INVEST Audit

Passed `5/6` structural signals.

| Letter | Signal | Status | Finding | Evidence |
| --- | --- | --- | --- | --- |
| I | Independent | PASS | No prerequisite story or pending dependency is required to start this slice. | source_unit: `[PENDING INPUT]`; trace: `REQ-001`, `REQ-EARS-001`, `REQ-EARS-002`, `REQ-EARS-003`, `REQ-EARS-004`, `REQ-EARS-005`, `REQ-EARS-006`, `PRD-001`, `SPEC-001`, `FR-03`, `JTBD-002`; enables: `US-001`, `US-002`, `US-003`, `US-004`, `US-005`, `US-006` |
| N | Negotiable | PASS | The story is framed as a traced outcome contract with acceptance coverage. | trace: `[PENDING INPUT]`, `REQ-001`, `REQ-EARS-001`, `REQ-EARS-002`, `REQ-EARS-003`, `REQ-EARS-004`, `REQ-EARS-005`, `REQ-EARS-006`, `SPEC-001`, `FR-03`, `JTBD-002`; acceptance_ids: `AC-007-01`, `AC-007-02`, `AC-007-03`, `AC-007-04`; acceptance_classes: `evidence`, `fail-to-pass`, `pass-to-pass` |
| V | Valuable | PASS | Value is anchored to upstream requirements or to enabled downstream stories. | source_unit: `[PENDING INPUT]`; trace: `[PENDING INPUT]`, `REQ-001`, `REQ-EARS-001`, `REQ-EARS-002`, `REQ-EARS-003`, `REQ-EARS-004`, `REQ-EARS-005`, `REQ-EARS-006`, `SPEC-001`, `FR-03`, `JTBD-002`; enables: `US-001`, `US-002`, `US-003`, `US-004`, `US-005`, `US-006` |
| E | Estimable | PASS | Scope, dependencies, and acceptance coverage are explicit enough to estimate. | trace: `[PENDING INPUT]`, `REQ-001`, `REQ-EARS-001`, `REQ-EARS-002`, `REQ-EARS-003`, `REQ-EARS-004`, `REQ-EARS-005`, `REQ-EARS-006`, `SPEC-001`, `FR-03`, `JTBD-002`; acceptance_classes: `evidence`, `fail-to-pass`, `pass-to-pass`; readiness_score: 0.50 |
| S | Small | WARN | The slice looks broad because upstream scope or prerequisite coupling is not tightly bounded. | source_unit: `[PENDING INPUT]`; trace: `[PENDING INPUT]`, `REQ-001`, `REQ-EARS-001`, `REQ-EARS-002`, `REQ-EARS-003`, `REQ-EARS-004`, `REQ-EARS-005`, `REQ-EARS-006`, `SPEC-001`, `FR-03`, `JTBD-002`; enables: `US-001`, `US-002`, `US-003`, `US-004`, `US-005`, `US-006` |
| T | Testable | PASS | Classified acceptance criteria cover fail-to-pass, pass-to-pass, and evidence paths. | acceptance_ids: `AC-007-01`, `AC-007-02`, `AC-007-03`, `AC-007-04`; acceptance_classes: `evidence`, `fail-to-pass`, `pass-to-pass` |


## Audit Checklist

- [x] Each story is evaluated against the governed INVEST/SPIDR/Lawrence slicing model.
- [x] Each story is checked for end-to-end behavior or a concrete enabler boundary.
- [x] Acceptance criteria coverage checks fail-to-pass, pass-to-pass, and evidence expectations.
- [x] Traceability checks connect story -> SPEC-U/REQ or concrete enabler evidence -> AC -> TC.
- [x] Parallel INVEST audit now surfaces structural signals for Independent, Negotiable, Valuable, Estimable, Small, and Testable without changing the current verdict.
- [x] Findings remain non-blocking by default and feed DoR warnings through `state.json#story_gates`.
