from __future__ import annotations

import re
from pathlib import Path

from .memory import ContextBroker
from .traceability import add_edge, add_node, nodes_by_type
from .workspace import load_config, read_json, state_path, update_state, workspace_path


def evaluate(project_id: str) -> dict[str, object]:
    base = workspace_path(project_id)
    gaps_path = base / "01_discovery" / "gaps.md"
    requirements_path = base / "02_requirements" / "requirements.md"
    gaps_text = gaps_path.read_text(encoding="utf-8") if gaps_path.exists() else ""
    req_text = requirements_path.read_text(encoding="utf-8") if requirements_path.exists() else ""
    config = load_config(project_id)
    blocking = set(config.get("maturity", {}).get("blocking_gap_severities", ["critical", "high"]))
    blocking_gaps = parse_blocking_gaps(gaps_text, blocking)
    readiness = "READY_FOR_SPECS" if not blocking_gaps and req_text else "BLOCKED"
    project_brief = None
    if readiness == "READY_FOR_SPECS":
        project_brief = materialize_project_brief(project_id, req_text, gaps_text)
    report_path = base / "01_discovery" / "requirement_maturity_report.md"
    report_path.write_text(render_report(project_id, readiness, blocking_gaps, project_brief), encoding="utf-8")
    ContextBroker(project_id).index_artifact(
        "MATURITY-001",
        "maturity_report",
        report_path,
        report_path.read_text(encoding="utf-8"),
        trace_ids=["MATURITY-001"],
    )
    update_state(project_id, phase="maturity_evaluated", health="CLEAN" if readiness.startswith("READY") else "DIRTY")
    return {
        "readiness": readiness,
        "blocking_gaps": blocking_gaps,
        "report": str(report_path),
        "project_brief": str(project_brief) if project_brief else None,
    }


def generate_project_brief(project_id: str) -> dict[str, object]:
    base = workspace_path(project_id)
    gaps_path = base / "01_discovery" / "gaps.md"
    requirements_path = base / "02_requirements" / "requirements.md"
    if not requirements_path.exists():
        raise RuntimeError("Cannot generate project brief before /ingest creates requirements.md.")
    req_text = requirements_path.read_text(encoding="utf-8")
    gaps_text = gaps_path.read_text(encoding="utf-8") if gaps_path.exists() else ""
    brief_path = materialize_project_brief(project_id, req_text, gaps_text)
    update_state(project_id, phase="brief_completed", readiness_stage="READY_FOR_SPECS", health="CLEAN")
    return {"project_id": project_id, "project_brief": str(brief_path), "path": str(brief_path)}


def parse_blocking_gaps(text: str, blocking_severities: set[str]) -> list[str]:
    blocking_gaps = []
    for line in text.splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if not cells or not cells[0].startswith("GAP-"):
            continue
        if len(cells) >= 4:
            severity = cells[2] if cells[1].lower() not in blocking_severities else cells[1]
            status = cells[3] if cells[1].lower() not in blocking_severities else cells[2]
            if status.upper() in {"OPEN", "PARTIALLY_CLOSED", "ANSWERED"} and severity.lower() in blocking_severities:
                blocking_gaps.append(cells[0])
    return blocking_gaps


def materialize_project_brief(project_id: str, req_text: str, gaps_text: str) -> Path:
    base = workspace_path(project_id)
    discovery = base / "01_discovery"
    brief_path = base / "02_requirements" / "project-brief.md"
    seeds_text = read_optional(discovery / "identity_seeds.md")
    decisions_text = read_optional(discovery / "decisions.md")
    lens_review_text = read_optional(discovery / "lens_review.md")
    brief_path.write_text(
        render_project_brief(project_id, req_text, gaps_text, seeds_text, decisions_text, lens_review_text),
        encoding="utf-8",
    )

    existing = nodes_by_type(project_id, "project_brief")
    if existing:
        brief_id = existing[0]["id"]
    else:
        brief_id = add_node(project_id, "REQ", "project_brief", brief_path, "Mature project brief", domain="product")
        for req in nodes_by_type(project_id, "requirement"):
            add_edge(project_id, req["id"], brief_id, "crystallizes")
        for seed in nodes_by_type(project_id, "identity_seed_bank"):
            add_edge(project_id, seed["id"], brief_id, "grounds")
        for review in nodes_by_type(project_id, "lens_review"):
            add_edge(project_id, review["id"], brief_id, "informs")

    ContextBroker(project_id).index_artifact(
        brief_id,
        "project_brief",
        brief_path,
        brief_path.read_text(encoding="utf-8"),
        trace_ids=[brief_id],
    )
    state = read_json(state_path(project_id), {})
    artifacts = dict(state.get("artifacts", {}))
    artifacts["project_brief"] = str(brief_path.as_posix())
    update_state(project_id, artifacts=artifacts)
    return brief_path


def read_optional(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def render_project_brief(
    project_id: str,
    req_text: str,
    gaps_text: str,
    seeds_text: str,
    decisions_text: str,
    lens_review_text: str,
) -> str:
    open_gaps = summarize_open_gaps(gaps_text)
    seeds = summarize_table_artifact(seeds_text, "Seed ID", max_rows=10)
    decisions = summarize_table_artifact(decisions_text, "Decision ID", max_rows=8)
    coverage = summarize_table_artifact(lens_review_text, "Lens", max_rows=6)
    return f"""# Project Brief - {project_id}

This brief is the mature discovery output. It reflects iterated requirement evidence and is the source handoff for PRD, specs, backlog, acceptance criteria, and tests.

Depth principle: the brief should be complete enough to guide domain work without becoming the domain deliverable itself. Design, Technology, and Quality may deepen the analysis later in dedicated context packs.

## 1. Identidad y Valor

### Nombre de la Iniciativa

TBD from confirmed client language.

### Dolor Principal

{primary_requirement(req_text)}

### Resultado Esperado y Metricas de Exito

- Outcome: TBD from confirmed business/product evidence.
- Metrics: include baseline, source, measurement owner, and target threshold before downstream commitment.

## 2. Lente de Negocio: Actores y Necesidades

### Actores Participantes

- TBD: cliente/usuario final, operadores internos, sistemas consumidores, equipos propietarios y aprobadores.

### Objetivos por Rol

| Rol / Actor | Necesidad | Resultado Esperado | Fuente |
| --- | --- | --- | --- |
| TBD | TBD | TBD | `02_requirements/requirements.md` |

## 3. Lente de Producto: Proceso y Journey

### Situacion Actual (As-Is)

- Documentar el flujo actual, puntos de dolor, sistemas/pantallas afectadas y comportamiento vigente que no debe romperse.

### Proceso Ideal (To-Be)

- Documentar el flujo target, nuevas capacidades, reglas funcionales, cambios de contrato y comportamiento esperado por caso.

### Alcance

- In scope: TBD from confirmed seeds.
- Out of scope / non-goals: TBD from confirmed exclusions.
- Unchanged behavior: TBD for compatibility and regression control.

## 4. Lente de Diseno: Flujos y Resiliencia UX

- User journeys / screens: TBD.
- Interaction states: loading, empty, error, disabled, recovery, permissions, accessibility.
- Copy and messaging: TBD, with source and approval owner.
- Visual or image evidence: reference screenshots, diagrams, or design assets under `00_raw/03_design_context/`.
- Sweet spot: identify affected journeys, screens, decisions, states, and UX constraints; detailed prototypes and final interaction specs belong in the design context pack.

## 5. Lente Tecnico: Datos, Conectividad y Arquitectura

- Systems / APIs / events: identify existing endpoints/events used, endpoints/events to create, endpoints/events to modify, and owner system/team.
- Source of truth and ownership: TBD.
- Data and contract depth: include key entities, critical fields, and contract direction only when needed to understand the requirement; exhaustive dictionaries, full request/response examples, schemas, and sequence diagrams belong in the technology context pack.
- Architecture constraints: TBD.
- Observability, security, performance, privacy, and resiliency expectations: TBD.

## 6. Gobernanza y Restricciones

- Security / privacy / compliance: TBD.
- Delivery dependencies, environments, approvals, rollout and dates: TBD.
- Auditability and traceability expectations: all downstream artifacts must cite this brief and raw evidence.

## 7. Decisiones, Seeds e Inferencias

### Seeds Confirmadas o Pendientes

{seeds}

### Decisiones

{decisions}

### Cobertura Multi-Lente

{coverage}

### Inferencias Controladas

- Any inference must name the source signal and the risk if wrong.
- Inferences cannot close critical or high gaps without client/domain confirmation.

## 8. Radar de Incertidumbres: GAPs

{open_gaps}

## 9. Preparacion para PRD, Specs y Backlog

- PRD can expand this brief only from confirmed seeds, decisions, context folders, and traceable source material.
- Specs must preserve system boundaries, data ownership, UX states, NFRs, and acceptance strategy.
- Backlog must be dev-ready, testable, vertically sliced, and linked to requirement, brief, PRD, acceptance criteria, tests, and changes.

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
"""


def primary_requirement(req_text: str) -> str:
    for line in req_text.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and not stripped.startswith("- Source:") and not stripped.startswith("- Status:"):
            return stripped
    return "TBD from source requirement."


def summarize_open_gaps(gaps_text: str) -> str:
    rows = []
    for line in gaps_text.splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if not cells or not cells[0].startswith("GAP-"):
            continue
        if len(cells) >= 6 and cells[3].upper() in {"OPEN", "PARTIALLY_CLOSED", "ANSWERED"}:
            rows.append(f"- `{cells[0]}` ({cells[1]}, {cells[2]}): {cells[5]}")
    return "\n".join(rows) if rows else "- No open blocking gaps detected at maturity evaluation time."


def summarize_table_artifact(text: str, first_header: str, max_rows: int) -> str:
    rows = []
    capture = False
    for line in text.splitlines():
        if line.startswith("|") and first_header in line:
            capture = True
            rows.append(line)
            continue
        if capture and line.startswith("| ---"):
            rows.append(line)
            continue
        if capture and line.startswith("|"):
            rows.append(line)
            if len(rows) >= max_rows + 2:
                break
        elif capture and rows:
            break
    return "\n".join(rows) if rows else "- No structured evidence found yet."


def render_report(project_id: str, readiness: str, blocking_gaps: list[str], project_brief: Path | None) -> str:
    gaps = ", ".join(f"`{gap}`" for gap in blocking_gaps) or "None"
    brief_line = f"- Project brief: `{project_brief.as_posix()}`" if project_brief else "- Project brief: not generated while maturity is blocked."
    return f"""# Requirement Maturity Report - {project_id}

- Readiness: `{readiness}`
- Blocking gaps: {gaps}
{brief_line}

## Domain Readiness

| Domain | Status |
| --- | --- |
| product | {'READY' if readiness != 'BLOCKED' else 'BLOCKED'} |
| functional | {'READY' if readiness != 'BLOCKED' else 'BLOCKED'} |
| quality | {'READY' if readiness != 'BLOCKED' else 'BLOCKED'} |

## Verdict

{'The requirement can move into specs and backlog generation.' if readiness != 'BLOCKED' else 'Resolve blocking gaps before generating specs or backlog.'}
"""
