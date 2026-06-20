"""PRD compiler and renderer.

This module owns the product-facing PRD rendering path. ``sentinel.generation``
re-exports the public functions as a compatibility facade for older imports.
"""
from __future__ import annotations

import re
from typing import Any

from ..discovery import (
    extract_functional_signals,
    extract_metric_signals,
    extract_personas,
    prd_section_for_gap,
    split_evidence_sentences,
)


EARS_REQUIREMENT_ID_RE = re.compile(r"^REQ-EARS-\d{3}$")


def render_prd(project_id: str, req_text: str, context: dict[str, object], source_name: str, language: str, evidence_text: str = "") -> str:
    if language == "en":
        return render_prd_full(project_id, req_text, context, source_name, "en", evidence_text)
    return render_prd_full(project_id, req_text, context, source_name, "es", evidence_text)


def compile_prd_sections(
    project_id: str,
    req_text: str,
    context: dict[str, object],
    language: str,
    evidence_text: str = "",
) -> dict[str, str]:
    """Compile PRD sections from evidence, confirmed gap answers, and EARS rows."""
    english = language == "en"
    pending = "[PENDING INPUT]"
    raw_text = str(context.get("raw_text") or evidence_text or "")
    evidence_source = raw_text or req_text
    sentences = split_evidence_sentences(evidence_source)
    gap_answers = context.get("gap_answers", {})
    if not isinstance(gap_answers, dict):
        gap_answers = {}

    objective = first_sentence_with(sentences, ("objective", "goal", "objetivo", "bajar", "reduce", "cut", "modernize"))
    scope_in = first_sentence_with(sentences, ("in scope", "scope:", "alcance", "primera version"))
    scope_out = first_sentence_with(sentences, ("out of scope", "fuera de alcance"))
    current = first_sentence_with(sentences, ("today", "currently", "hoy", "actual", "by hand", "a mano", "telefonico"))
    personas = extract_personas(evidence_source)
    functionals = extract_functional_signals(evidence_source)
    metrics = extract_metric_signals(evidence_source)
    ears_rows = context.get("ears_requirements", [])
    if not isinstance(ears_rows, list):
        ears_rows = []

    def source_ref(source: str = "00_raw/") -> str:
        label = "source" if english else "fuente"
        return f"_({label}: `{source}`)_"

    def quote(sentence: str) -> str:
        return f'"{sentence}" {source_ref()}'

    def pending_line(gap_id: str) -> str:
        action = "resolve" if english else "resolver"
        return f"- `{pending}` - {action} `{gap_id}` before treating this section as evidence-backed."

    def confirmed_for_section(section: str, include_gap_id: bool = True) -> list[str]:
        lines: list[str] = []
        for gap_id, payload in gap_answers.items():
            if not isinstance(payload, dict) or prd_section_for_gap(str(gap_id)) != section:
                continue
            statement = str(payload.get("statement", "")).strip()
            source = str(payload.get("source", "")).strip()
            if statement:
                if include_gap_id:
                    src = f"`{gap_id}`" + (f" / `{source}`" if source else "")
                else:
                    src = f"`{source}`" if source else "`identity_seeds.md`"
                lines.append(f"- {statement} _({src})_")
        return lines

    title = project_title(evidence_source, project_id)
    outcome_lines: list[str] = [
        f"- {'Initiative' if english else 'Iniciativa'}: {title} {source_ref()}",
    ]
    if objective:
        outcome_lines.append(f"- {'Outcome' if english else 'Resultado'}: {quote(objective)}")
    else:
        outcome_lines.extend(confirmed_for_section("1") or [pending_line("GAP-OBJECTIVE")])
    if metrics:
        metric = metrics[0]
        outcome_lines.append(f"- KPI: `{metric['metric']}` from {quote(metric['evidence'])}")
    sections: dict[str, str] = {"1": "\n".join(outcome_lines)}

    scope_lines: list[str] = []
    scope_lines.append(f"- {'Current state' if english else 'Estado actual'}: {quote(current)}" if current else pending_line("GAP-PRODUCT-ASIS-TOBE"))
    scope_lines.append(f"- In scope: {quote(scope_in)}" if scope_in else pending_line("GAP-SCOPE"))
    scope_lines.append(f"- Out of scope: {quote(scope_out)}" if scope_out else pending_line("GAP-SCOPE"))
    sections["2"] = "\n".join(scope_lines)

    persona_lines = [
        f"| P-{i + 1:02d} | {row['evidence']} | `REQ-001`, `00_raw/` |"
        for i, row in enumerate(personas)
    ]
    if confirmed_for_section("3"):
        persona_lines.extend(f"| P-A{i + 1:02d} | {line.lstrip('- ')} | `identity_seeds.md` |" for i, line in enumerate(confirmed_for_section("3")))
    if persona_lines:
        sections["3"] = "| ID | Persona Evidence | Source |\n| --- | --- | --- |\n" + "\n".join(persona_lines)
    else:
        sections["3"] = pending_line("GAP-USERS")

    fr_rows: list[str] = []
    for i, row in enumerate(functionals, start=1):
        fr_rows.append(f"| FR-{i:02d} | {row['statement']} | Must Have | `REQ-001`, `00_raw/` |")
    for row in ears_rows:
        if isinstance(row, dict):
            req_id = str(row.get("id", "")).strip()
            statement = str(row.get("statement", "")).strip()
            if req_id and statement:
                fr_rows.append(f"| FR-E{len(fr_rows) + 1:02d} | {statement} | Must Have | `{req_id}` |")
    for line in confirmed_for_section("4"):
        fr_rows.append(f"| FR-A{len(fr_rows) + 1:02d} | {line.lstrip('- ')} | Must Have | `identity_seeds.md` |")
    if fr_rows:
        sections["4"] = "| ID | Requirement | Priority | Source |\n| --- | --- | --- | --- |\n" + "\n".join(fr_rows)
    else:
        sections["4"] = pending_line("GAP-PRD-FR-AC")

    quality_lines = confirmed_for_section("5")
    sections["5"] = "\n".join(quality_lines) if quality_lines else "\n".join(
        [
            pending_line("GAP-PRD-NFR-KPI"),
            pending_line("GAP-TECH-NFR"),
        ]
    )

    if metrics:
        kpi_rows = []
        for i, metric in enumerate(metrics, start=1):
            kpi_rows.append(
                f"| KPI-{i:02d} | {metric['evidence']} | {metric['metric']} | Confirmed evidence or gap response | `REQ-001`, `00_raw/` |"
            )
        for line in confirmed_for_section("6", include_gap_id=False):
            kpi_rows.append(f"| KPI-A{len(kpi_rows) + 1:02d} | {line.lstrip('- ')} | Confirmed | Confirmed response | `identity_seeds.md` |")
        sections["6"] = "| KPI ID | Description | Target | Measurement Method | Source |\n| --- | --- | --- | --- | --- |\n" + "\n".join(kpi_rows)
    else:
        kpi_lines = confirmed_for_section("6")
        sections["6"] = "\n".join(kpi_lines) if kpi_lines else pending_line("GAP-METRIC-SOURCE")

    return sections


def first_sentence_with(sentences: list[str], cues: tuple[str, ...]) -> str:
    for sentence in sentences:
        lowered = sentence.lower()
        if any(cue in lowered for cue in cues):
            return sentence
    return ""


def project_title(text: str, fallback: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            return stripped.lstrip("#").strip()
    return fallback


def render_prd_full(project_id: str, req_text: str, context: dict[str, object], source_name: str, language: str, evidence_text: str = "") -> str:
    english = language == "en"
    section_context = render_prd_section_context(context)
    title = "Executive Summary And Problem Statement" if english else "Resumen ejecutivo y planteamiento del problema"
    scope = "Project Scope" if english else "Alcance del proyecto"
    personas = "Users And Personas" if english else "Usuarios y personas"
    core = "Core Requirements" if english else "Core Requirements"
    fr_title = "Functional Requirements" if english else "Requerimientos funcionales"
    nfr_title = "Non-Functional Requirements" if english else "Requerimientos no funcionales"
    kpi_title = "Business Success Criteria (KPIs)" if english else "Criterios de exito del negocio (KPIs)"
    jtbd_title = "Jobs Traceability" if english else "Trazabilidad de trabajos"
    execution = "Execution Plan" if english else "Execution Plan"
    governance = "Governance" if english else "Governance"
    pending = "[PENDING INPUT]"
    evidence_source = evidence_text or req_text
    extracted_personas = extract_personas(evidence_source)
    extracted_frs = extract_functional_signals(evidence_source)
    extracted_metrics = extract_metric_signals(evidence_source)
    personas_evidence_title = "Evidence-Backed Personas" if english else "Personas con evidencia del input"
    fr_evidence_title = "Evidence-Backed Functional Statements" if english else "Declaraciones funcionales con evidencia del input"
    ears_title = "Confirmed EARS Requirements" if english else "Requerimientos EARS confirmados"
    ears_block = render_ears_requirements_table(context)
    compiled = compile_prd_sections(project_id, req_text, context, language, evidence_text)
    if extracted_personas:
        persona_rows = "\n".join(
            f'| P-E{i + 1} | "{row["evidence"]}" | `REQ-001` |' for i, row in enumerate(extracted_personas)
        )
        personas_evidence_block = (
            f"### {personas_evidence_title}\n\n"
            "| ID | Evidence From Source | Source |\n| --- | --- | --- |\n"
            f"{persona_rows}\n"
        )
    else:
        personas_evidence_block = (
            f"### {personas_evidence_title}\n\n"
            f"`{pending}` - no persona evidence was extracted from the source input; see `GAP-USERS` and `GAP-PRD-PERSONA-DETAIL`.\n"
        )
    if extracted_frs:
        fr_rows = "\n".join(
            f'| FR-E{i + 1:02d} | "{row["statement"]}" | `REQ-001` |' for i, row in enumerate(extracted_frs)
        )
        fr_evidence_block = (
            f"### {fr_evidence_title}\n\n"
            "| ID | Statement (verbatim evidence) | Source |\n| --- | --- | --- |\n"
            f"{fr_rows}\n"
        )
    else:
        fr_evidence_block = (
            f"### {fr_evidence_title}\n\n"
            f"`{pending}` - no requirement-like statements were extracted from the source input; see `GAP-PRD-FR-AC`.\n"
        )
    if extracted_metrics:
        metric = extracted_metrics[0]
        kpi_primary_row = (
            f'| KPI-01 | "{metric["evidence"]}" | {metric["metric"]} (confirm baseline) | `{pending}` | `{pending}` | `REQ-001`, `GAP-METRIC-SOURCE` |'
        )
    else:
        kpi_primary_row = (
            f"| KPI-01 | Primary business or operational outcome. | `{pending}` unless confirmed. | `{pending}` | `{pending}` | `GAP-METRIC-SOURCE` |"
        )
    from ..assumptions import render_prd_assumption_rows

    governed_assumption_rows = render_prd_assumption_rows(project_id)
    assumption_rows = governed_assumption_rows or "\n".join(
        [
            "| ASM-01 | Details absent from confirmed evidence remain pending and must not be silently converted into backlog scope. | Rework and loss of trust. | Sentinel guardrail | Active |",
            "| ASM-02 | Domain context in memory is sufficient to draft PRD sections, with gaps where evidence is missing. | PRD may be too generic. | `08_context_packs/specs_generation.json` | Active |",
        ]
    )
    assumption_header = (
        "| ID | Assumption | Risk | Owner | Source Basis | Linked Gap | Status |\n| --- | --- | --- | --- | --- | --- | --- |"
        if governed_assumption_rows else
        "| ID | Assumption | Impact if Wrong | Source Basis | Status |\n| --- | --- | --- | --- | --- |"
    )
    return f"""# PRD - {project_id}

# {project_id} - Strategic Foundation

## 1. {title}

This PRD expands the mature discovery brief into a human-readable product document for Business, Product, Technology, Design, Quality, and Delivery. It must explain what will be implemented, why it matters, how success is measured, and which evidence justifies each downstream decision.

- Mature source: `02_requirements/{source_name}`
- Discovery handoff: `02_requirements/project-brief.md` when present
- Trace anchors: `REQ-001`, `PRD-001`
- Context pack used: `08_context_packs/specs_generation.json`

### Problem / Pain

{compiled['1']}

### Expected Outcome

The outcome above is compiled from source evidence. Any missing outcome or measurement detail remains tracked in discovery gaps rather than invented here.

## 2. {scope}

### In Scope

{compiled['2']}

### Out of Scope

Items not backed by the brief, confirmed seeds, decisions, or retrieved domain context stay outside the PRD scope until a traced `/sync` or gap-resolution event confirms them.

## 3. {personas}

{compiled['3']}

# {project_id} - {core}

## 4. {fr_title}

{compiled['4']}

### {ears_title}

{ears_block or "No confirmed EARS rows are present yet; functional requirements above remain sourced from confirmed discovery evidence."}

### FR-01 Acceptance Criteria

Acceptance criteria are compiled from confirmed EARS rows, confirmed gap answers, or functional evidence above. Criteria that are still missing remain visible in discovery gaps and must not be invented in this PRD.

## 5. {nfr_title}

{compiled['5']}

## 6. {kpi_title}

{compiled['6']}

# {project_id} - {jtbd_title}

## 7. Jobs to Be Done

### 7a. Core Functional Job

**JTBD-01:** When the primary user faces the source scenario, they need to complete the primary job so that the expected business or operational outcome is achieved. `[Source: REQ-001]`

### 7b. Related / Secondary Jobs

**JTBD-02:** When an operator, owner, or downstream system participates in the workflow, they need confirmed data, rules, and failure behavior so that the capability remains reliable and auditable.

**JTBD-03:** When Quality validates the workflow, it needs acceptance criteria, edge cases, regression expectations, and traceability.

### 7c. Emotional and Social Jobs

**JTBD-E01:** When users rely on the new capability, they need confidence that the state/result is explainable and backed by confirmed evidence.

`{pending} - GAP-PRD-GLOSSARY-GOVERNANCE`: confirm whether a social/reputational job exists.

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

# {project_id} - {execution}

## 8. Dependency Map

| Dep ID | Dependency | Type | Description | Owner | Impact if Unavailable | Source |
| --- | --- | --- | --- | --- | --- | --- |
| DEP-01 | Primary product/domain owner | Business | Confirms scope, value, and acceptance. | `{pending}` | PRD cannot be accepted. | `GAP-PRD-DEPENDENCIES-ROADMAP` |
| DEP-02 | Technology owner / source system | Technical | Confirms integrations, data ownership, contracts, and constraints. | `{pending}` | Implementation may block or invent architecture. | `GAP-TECH-DATA-SOURCE` |
| DEP-03 | Design/content owner | Design | Confirms journeys, states, copy, and prototype needs. | `{pending}` | UI/backlog may miss user states. | `GAP-DESIGN-FLOW` |
| DEP-04 | Quality owner | Quality | Confirms test strategy, evidence, and regression scope. | `{pending}` | Stories may not be testable. | `GAP-QUALITY-HANDOFF` |

## 9. Risks And Assumptions

### 9a. Assumption Register

{assumption_header}
{assumption_rows}

### 9b. Risk Register

| ID | Risk | Likelihood | Impact | Mitigation | Source |
| --- | --- | --- | --- | --- | --- |
| RSK-01 | PRD section appears complete but is based on weak evidence. | Medium | High | Cite sources and keep `{pending}` markers. | `GAP-PRD-*` |
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

# {project_id} - {governance}

## Output Enhancement Suggestions

### Missing Information Notes

- `[PENDING INPUT - Personas]`: resolve `GAP-PRD-PERSONA-DETAIL`.
- `[PENDING INPUT - FR/AC]`: refine FRs and ACs from confirmed product and quality evidence.
- `[PENDING INPUT - NFR/KPI]`: confirm measurable targets, owners, method, and timeframe.
- `[PENDING INPUT - Dependencies/Roadmap]`: confirm owners, MVP, phases, dates, and rollout constraints.
- `[PENDING INPUT - Glossary/Governance]`: confirm mandatory terms, constraints, audit expectations, and decisions.

### Context Retrieved From Memory

{section_context}

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
| Source | `02_requirements/{source_name}` |
| Context Pack | `08_context_packs/specs_generation.json` |

## Decisions Made

1. PRD sections are populated only from brief, traceable artifacts, and focused memory retrieval.
2. Missing evidence remains visible as `{pending}` or a `GAP-*` reference.
3. `specs.md` is the downstream agent contract and should be used before backlog slicing.
"""


def render_ears_requirements_table(
    context: dict[str, object],
    empty_text: str = "",
) -> str:
    rows = context.get("ears_requirements", []) if isinstance(context, dict) else []
    if not isinstance(rows, list) or not rows:
        return empty_text
    rendered_rows: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        req_id = str(row.get("id", ""))
        if not EARS_REQUIREMENT_ID_RE.match(req_id):
            continue
        pattern = safe_cell(str(row.get("pattern", "")), 80)
        statement = safe_cell(str(row.get("statement", "")), 260)
        source = safe_cell(str(row.get("source", "")), 120)
        rendered_rows.append(f"| `{req_id}` | {pattern} | {statement} | {source} |")
    if not rendered_rows:
        return empty_text
    return (
        "| ID | EARS Pattern | Testable Statement | Source |\n"
        "| --- | --- | --- | --- |\n"
        + "\n".join(rendered_rows)
    )


def render_context_summary(context: dict[str, object]) -> str:
    domains = context.get("domains", {}) if isinstance(context, dict) else {}
    rows: list[str] = []
    for domain, results in domains.items():
        if not results:
            rows.append(f"| {domain} | No focused context retrieved. | N/A |")
            continue
        top = results[0]
        if not isinstance(top, dict):
            continue
        rows.append(
            f"| {domain} | {safe_cell(top.get('summary', 'Context retrieved'), 160)} | `{top.get('artifact_id', 'N/A')}` |"
        )
    return "| Domain | Retrieved Signal | Artifact |\n| --- | --- | --- |\n" + "\n".join(rows)


def render_prd_section_context(context: dict[str, object]) -> str:
    sections = context.get("prd_sections", {}) if isinstance(context, dict) else {}
    if not isinstance(sections, dict) or not sections:
        return render_context_summary(context)
    rows: list[str] = []
    for section, payload in sections.items():
        if not isinstance(payload, dict):
            continue
        results = payload.get("results", [])
        if not results:
            rows.append(f"| {section} | No focused context retrieved. | N/A | N/A |")
            continue
        top = results[0]
        if not isinstance(top, dict):
            continue
        trace_ids = top.get("trace_ids", [])
        trace = ", ".join(trace_ids) if isinstance(trace_ids, list) else str(trace_ids)
        rows.append(
            f"| {section} | {safe_cell(top.get('summary', 'Context retrieved'), 180)} | `{top.get('artifact_id', 'N/A')}` | {safe_cell(trace or 'N/A', 80)} |"
        )
    return "| PRD / Specs Need | Retrieved Signal | Artifact | Trace |\n| --- | --- | --- | --- |\n" + "\n".join(rows)


def safe_cell(value: Any, limit: int) -> str:
    text = str(value).replace("\n", " ").replace("|", "/").strip()
    return text[:limit]
