from __future__ import annotations

import re
import shutil
from pathlib import Path

from .memory import ContextBroker, index_context_folders
from .sources import mark_source_processed
from .traceability import add_edge, add_node
from .workspace import ensure_workspace, update_state, workspace_path

METRIC_RE = re.compile(r"(\d+(?:[.,]\d+)?\s?%|\$\s?\d+|\d+\s?(?:usd|ars|eur|hours|horas|days|dias))", re.I)


def ingest(project_id: str, source: Path) -> dict[str, str]:
    ensure_workspace(project_id)
    base = workspace_path(project_id)
    text = source.read_text(encoding="utf-8")
    context = load_domain_context(base)
    raw_target = base / "00_raw" / f"{source.stem}.md"
    shutil.copyfile(source, raw_target)
    mark_source_processed(project_id, source, "initial_ingested")
    mark_source_processed(project_id, raw_target, "raw_copy")
    raw_id = add_node(project_id, "RAW", "raw_input", raw_target, source.stem, domain="product")

    req_text = extract_requirement(text)
    req_path = base / "02_requirements" / "requirements.md"
    req_path.write_text(render_requirement(project_id, req_text, raw_id), encoding="utf-8")
    req_id = add_node(project_id, "REQ", "requirement", req_path, "Primary requirement", domain="product")
    add_edge(project_id, raw_id, req_id, "extracts")

    gaps = detect_gaps(text, context)
    gap_path = base / "01_discovery" / "gaps.md"
    gap_path.write_text(render_gaps(project_id, gaps, req_id), encoding="utf-8")
    gap_id = add_node(
        project_id,
        "GAP",
        "gap_report",
        gap_path,
        "Discovery gaps",
        status="open" if gaps else "closed",
        domain="product",
    )
    add_edge(project_id, req_id, gap_id, "has_gap")

    dec_path = base / "01_discovery" / "decisions.md"
    dec_path.write_text(render_decisions(project_id, text, req_id), encoding="utf-8")
    dec_id = add_node(project_id, "DEC", "decision_log", dec_path, "Pending decisions", status="pending")
    add_edge(project_id, req_id, dec_id, "requires_decision")

    digest_path = base / "01_discovery" / "raw_input_digest.md"
    digest_path.write_text(render_digest(project_id, text, raw_id, req_id, gap_id), encoding="utf-8")

    seeds_path = base / "01_discovery" / "identity_seeds.md"
    seeds_path.write_text(render_identity_seeds(project_id, text, raw_id, gaps), encoding="utf-8")
    seed_id = add_node(project_id, "SEED", "identity_seed_bank", seeds_path, "Identity seeds", domain="product")
    add_edge(project_id, raw_id, seed_id, "produces_seed")
    add_edge(project_id, seed_id, req_id, "grounds")

    discovery_log_path = base / "01_discovery" / "discovery_log.md"
    discovery_log_path.write_text(render_discovery_log(project_id, text, raw_id, req_id, gaps, context), encoding="utf-8")
    discovery_log_id = add_node(project_id, "DISC", "discovery_log", discovery_log_path, "Discovery log", domain="product")
    add_edge(project_id, raw_id, discovery_log_id, "analyzed_by")
    add_edge(project_id, discovery_log_id, gap_id, "identifies")

    lens_review_path = base / "01_discovery" / "lens_review.md"
    lens_review_path.write_text(render_lens_review(project_id, text, raw_id, req_id, gaps, context), encoding="utf-8")
    lens_review_id = add_node(project_id, "DISC", "lens_review", lens_review_path, "Multi-lens critical review", domain="product")
    add_edge(project_id, raw_id, lens_review_id, "scrutinized_by")
    add_edge(project_id, lens_review_id, gap_id, "raises")

    broker = ContextBroker(project_id)
    broker.index_artifact(raw_id, "raw_input", raw_target, text, trace_ids=[raw_id])
    broker.index_artifact(req_id, "requirement", req_path, req_path.read_text(encoding="utf-8"), trace_ids=[raw_id, req_id])
    broker.index_artifact(gap_id, "gap_report", gap_path, gap_path.read_text(encoding="utf-8"), trace_ids=[req_id, gap_id])
    broker.index_artifact(dec_id, "decision_log", dec_path, dec_path.read_text(encoding="utf-8"), trace_ids=[req_id, dec_id])
    broker.index_artifact(seed_id, "identity_seed_bank", seeds_path, seeds_path.read_text(encoding="utf-8"), trace_ids=[raw_id, seed_id])
    broker.index_artifact(
        discovery_log_id,
        "discovery_log",
        discovery_log_path,
        discovery_log_path.read_text(encoding="utf-8"),
        trace_ids=[raw_id, discovery_log_id, gap_id],
    )
    broker.index_artifact(
        lens_review_id,
        "lens_review",
        lens_review_path,
        lens_review_path.read_text(encoding="utf-8"),
        trace_ids=[raw_id, lens_review_id, gap_id],
    )
    index_context_folders(project_id, broker)

    update_state(
        project_id,
        phase="discovery_completed",
        health="DIRTY" if gaps else "CLEAN",
        artifacts={
            "raw_input": str(raw_target.as_posix()),
            "requirements": str(req_path.as_posix()),
            "gaps": str(gap_path.as_posix()),
            "decisions": str(dec_path.as_posix()),
            "identity_seeds": str(seeds_path.as_posix()),
            "discovery_log": str(discovery_log_path.as_posix()),
            "lens_review": str(lens_review_path.as_posix()),
        },
        metrics={"requirements": 1, "gaps_open": len(gaps), "decisions_pending": 1, "user_stories": 0},
    )
    return {
        "raw_id": raw_id,
        "requirement_id": req_id,
        "gap_id": gap_id,
        "decision_id": dec_id,
        "seed_id": seed_id,
        "discovery_log_id": discovery_log_id,
        "lens_review_id": lens_review_id,
    }


def extract_requirement(text: str) -> str:
    lines = [line.strip(" -\t") for line in text.splitlines() if line.strip()]
    for line in lines:
        if any(word in line.lower() for word in ("need", "necesit", "require", "objetivo", "queremos", "must")):
            return line
    return lines[0] if lines else "Requirement to be refined."


def detect_gaps(text: str, context: dict[str, str] | None = None) -> list[dict[str, str]]:
    lowered = text.lower()
    context = context or {}
    tech_evidence = " ".join([text, context.get("technical", "")]).lower()
    design_evidence = " ".join([text, context.get("design", "")]).lower()
    quality_evidence = " ".join([text, context.get("quality", "")]).lower()
    checks = [
        ("GAP-OBJECTIVE", "business", "high", "Business objective or expected outcome is not explicit.", lowered, ("objetivo", "outcome", "resultado", "goal")),
        ("GAP-USERS", "business", "high", "Target users or personas are not explicit.", lowered, ("usuario", "user", "persona", "actor")),
        ("GAP-SCOPE", "product", "critical", "Scope boundaries are not explicit.", lowered, ("alcance", "scope", "in scope", "out of scope")),
        ("GAP-ACCEPTANCE", "quality", "critical", "Acceptance criteria or success conditions are missing.", lowered, ("criterio", "acceptance", "success", "done")),
        ("GAP-QUALITY", "quality", "medium", "Quality or testability expectations are not explicit.", quality_evidence, ("test", "quality", "calidad", "qa")),
        ("GAP-TECH-DATA-SOURCE", "technical", "medium", "Data source, integration, or system ownership is not explicit in source or technology context.", tech_evidence, ("data", "dato", "source", "fuente", "api", "integration", "integracion", "database", "crm", "endpoint")),
        ("GAP-TECH-NFR", "technical", "medium", "Performance, security, observability, or operational constraints are not explicit.", tech_evidence, ("performance", "seguridad", "security", "observability", "observabilidad", "sla", "timeout", "audit", "compliance")),
        ("GAP-DESIGN-FLOW", "design", "medium", "User journey, screen flow, or interaction model is not explicit in source or design context.", design_evidence, ("flow", "flujo", "screen", "pantalla", "mock", "prototype", "journey", "wireframe", "navigation")),
        ("GAP-DESIGN-STATES", "design", "medium", "Required UI states for loading, empty, error, and recovery are not explicit.", design_evidence, ("loading", "empty", "error", "idle", "state", "estado", "resiliencia", "recover")),
        ("GAP-PRODUCT-ASIS-TOBE", "product", "medium", "Current state and target state are not both explicit enough to compare impact.", lowered, ("as-is", "to-be", "situacion actual", "situación actual", "proceso actual", "proceso ideal", "estado actual", "estado futuro")),
        ("GAP-BUSINESS-RULES", "business", "medium", "Business rules, exclusions, or decision rules are not explicit enough for downstream slicing.", lowered, ("regla", "rule", "validacion", "validación", "condicion", "condición", "exclusion", "exclusión")),
        ("GAP-GOVERNANCE-CONSTRAINTS", "compliance", "medium", "Governance, security, privacy, compliance, or operational restrictions are not explicit.", lowered, ("seguridad", "security", "privacidad", "privacy", "compliance", "normativa", "restriccion", "restricción", "gobernanza")),
        ("GAP-DELIVERY-READINESS", "delivery", "medium", "Dependencies, environments, ownership, timing, or rollout constraints are not explicit.", lowered, ("dependencia", "dependency", "ambiente", "environment", "deadline", "fecha", "timeline", "owner", "responsable", "rollout")),
    ]
    gaps = [
        {"id": gap_id, "lens": lens, "severity": severity, "description": description}
        for gap_id, lens, severity, description, evidence, tokens in checks
        if not any(token in evidence for token in tokens)
    ]
    if METRIC_RE.search(text) and not any(token in lowered for token in ("source", "fuente", "baseline", "medido", "measured")):
        gaps.append(
            {
                "id": "GAP-METRIC-SOURCE",
                "lens": "business",
                "severity": "high",
                "description": "Quantitative metric appears without an explicit source or baseline.",
            }
        )
    return gaps


def render_requirement(project_id: str, req_text: str, raw_id: str) -> str:
    return f"""# Requirement Register - {project_id}

## REQ-001 Primary Requirement

- Source: `{raw_id}`
- Status: `draft`
- Domains: product, functional, quality

{req_text}
"""


def render_gaps(project_id: str, gaps: list[dict[str, str]], req_id: str) -> str:
    rows = "\n".join(
        f"| {gap['id']} | {gap.get('lens', lens_for_gap(gap['id']))} | {gap['severity']} | OPEN | `{req_id}` | {gap['description']} | {question_for_gap(gap['id'])} | Context folders and source input. |"
        for gap in gaps
    )
    if not rows:
        rows = "| NONE | All | none | CLOSED | N/A | No blocking gaps detected by deterministic scan. | N/A | Source input. |"
    return f"""# Discovery Gaps - {project_id}

| Gap ID | Lens | Severity | Status | Parent | Description | Question For Client/Domain | Source Consulted |
| --- | --- | --- | --- | --- | --- | --- | --- |
{rows}

## Resolution Trace

| Gap ID | Resolution Source | Promoted Seed | Impacted Artifacts |
| --- | --- | --- | --- |
| TBD | TBD | TBD | TBD |
"""


def render_decisions(project_id: str, text: str, req_id: str) -> str:
    decision = "Confirm scope, success criteria, and implementation constraints with stakeholders."
    if "decid" in text.lower() or "decision" in text.lower():
        decision = "Validate stated decisions and record their downstream impact."
    return f"""# Decision Log - {project_id}

| Decision ID | Status | Parent | Decision Needed |
| --- | --- | --- | --- |
| DEC-001 | PENDING | `{req_id}` | {decision} |
"""


def render_digest(project_id: str, text: str, raw_id: str, req_id: str, gap_id: str) -> str:
    return f"""# Raw Input Digest - {project_id}

- Raw source: `{raw_id}`
- Requirement: `{req_id}`
- Gap report: `{gap_id}`
- Character count: {len(text)}

## Summary

{extract_requirement(text)}
"""


def render_identity_seeds(project_id: str, text: str, raw_id: str, gaps: list[dict[str, str]]) -> str:
    seed_rows = "\n".join(
        f"| SEED-{index:03d} | {seed['lens']} | INPUT | `{raw_id}` | {seed['truth']} | {seed['status']} | {seed['type']} |"
        for index, seed in enumerate(extract_seed_candidates(text, gaps), start=1)
    )
    return f"""# Identity Seeds - {project_id}

Seeds are atomic truths or pending truths extracted from evidence. Source files remain authoritative; memory is retrieval only.

| Seed ID | Lens | Origin Type | Origin Ref | Atomic Statement | Status | Node Type |
| --- | --- | --- | --- | --- | --- | --- |
{seed_rows}
"""


def render_discovery_log(project_id: str, text: str, raw_id: str, req_id: str, gaps: list[dict[str, str]], context: dict[str, str]) -> str:
    return f"""# Discovery Log - {project_id}

- Source: `{raw_id}`
- Requirement: `{req_id}`

## Input Census

| Source ID | Status |
| --- | --- |
| `{raw_id}` | FORENSIC_SCAN_COMPLETE |

## Business Lens / JTBD

| JTBD ID | Context | Need | Expected Result | Certainty |
| --- | --- | --- | --- | --- |
| JTBD-001 | {extract_context(text)} | {extract_need(text)} | {extract_result(text)} | INFERRED_FROM_INPUT |

## Technology Context Lens

| Area | Discovery Signal | Required Follow-Up |
| --- | --- | --- |
| Data / Integration | {lens_signal('technical', context)} | Confirm any missing integration, data ownership, security, performance, or observability gaps. |

## Design Context Lens

| Area | Discovery Signal | Required Follow-Up |
| --- | --- | --- |
| UX / UI | {lens_signal('design', context)} | Confirm missing states, navigation, accessibility, or experience constraints. |

## Quality Lens

| Area | Discovery Signal | Required Follow-Up |
| --- | --- | --- |
| Testability | {quality_signal(text)} | Convert unresolved quality expectations into acceptance criteria or gaps. |

## Atomic Inventory

| ID | Type | Domain | Description |
| --- | --- | --- | --- |
| ATOM-001 | REQUIREMENT | product | {extract_requirement(text)} |

## Refinement Hooks

{render_refinement_hooks(gaps)}
"""


def render_lens_review(
    project_id: str,
    text: str,
    raw_id: str,
    req_id: str,
    gaps: list[dict[str, str]],
    context: dict[str, str],
) -> str:
    lens_rows = "\n".join(
        f"| {lens['lens']} | {lens['role']} | {lens['evidence']} | {lens['critical_questions']} | {lens['gap_ids']} |"
        for lens in build_lens_reviews(text, gaps, context)
    )
    rubric_rows = "\n".join(
        f"| {item['area']} | {item['mature_signal']} | {item['lens']} | {item['gap_when_missing']} |"
        for item in mature_requirement_rubric()
    )
    return f"""# Multi-Lens Critical Review - {project_id}

- Raw source: `{raw_id}`
- Requirement: `{req_id}`

This artifact forces discovery to scrutinize the request from Product, Technology, Design, and Quality before downstream PRD/spec/backlog work.

| Lens | Reviewer Stance | Evidence Found | Critical Questions | Related Gaps |
| --- | --- | --- | --- | --- |
{lens_rows}

## Mature Requirement Coverage Rubric

| Area | Mature Signal | Primary Lens | Gap When Missing |
| --- | --- | --- | --- |
{rubric_rows}

## Crystallization Gate

- Product must confirm outcome, users, scope, and priority.
- Technology must confirm data sources, integrations, constraints, security, and observability when relevant.
- Design must confirm journey, screens, states, accessibility, and interaction expectations when relevant.
- Quality must confirm acceptance strategy, testability, risk scenarios, and metric fidelity.
- Any unanswered critical or high gap blocks maturity; medium gaps stay visible for PRD/spec/backlog assumptions.
"""


def build_lens_reviews(text: str, gaps: list[dict[str, str]], context: dict[str, str]) -> list[dict[str, str]]:
    return [
        lens_review(
            "business/product",
            "Senior BA / Product Lead",
            text,
            context.get("business", ""),
            gaps,
            ("GAP-OBJECTIVE", "GAP-USERS", "GAP-SCOPE", "GAP-METRIC-SOURCE"),
            "What outcome, user, scope boundary, metric source, or priority remains ambiguous?",
        ),
        lens_review(
            "product",
            "Product Strategist",
            text,
            context.get("business", ""),
            gaps,
            ("GAP-PRODUCT-ASIS-TOBE", "GAP-BUSINESS-RULES", "GAP-DELIVERY-READINESS"),
            "Is the as-is/to-be delta, rule set, dependency map, and rollout path clear enough to shape PRD and backlog?",
        ),
        lens_review(
            "technical",
            "Tech Lead",
            text,
            context.get("technical", ""),
            gaps,
            ("GAP-TECH-DATA-SOURCE", "GAP-TECH-NFR"),
            "Which data sources, integrations, security, performance, observability, or ownership constraints are required?",
        ),
        lens_review(
            "design",
            "UX/UI Designer",
            text,
            context.get("design", ""),
            gaps,
            ("GAP-DESIGN-FLOW", "GAP-DESIGN-STATES"),
            "Which journey, screens, states, error/empty/loading behavior, or accessibility requirements are unresolved?",
        ),
        lens_review(
            "quality",
            "Quality Lead",
            text,
            context.get("quality", ""),
            gaps,
            ("GAP-ACCEPTANCE", "GAP-QUALITY"),
            "What acceptance criteria, risks, negative paths, stale/missing data cases, or test evidence are missing?",
        ),
    ]


def mature_requirement_rubric() -> list[dict[str, str]]:
    return [
        {
            "area": "Identity and value",
            "mature_signal": "Initiative name, pain, target outcome, measurable success, and metric source are explicit.",
            "lens": "Business/Product",
            "gap_when_missing": "GAP-OBJECTIVE or GAP-METRIC-SOURCE",
        },
        {
            "area": "Actors and responsibilities",
            "mature_signal": "Stakeholders, users, external teams, owners, and role-level objectives are identified.",
            "lens": "Business/Product",
            "gap_when_missing": "GAP-USERS",
        },
        {
            "area": "Scope boundaries",
            "mature_signal": "In scope, out of scope, unchanged behavior, and non-goals are stated.",
            "lens": "Product",
            "gap_when_missing": "GAP-SCOPE",
        },
        {
            "area": "As-is / to-be delta",
            "mature_signal": "Current process, target process, and functional delta are comparable.",
            "lens": "Product",
            "gap_when_missing": "GAP-PRODUCT-ASIS-TOBE",
        },
        {
            "area": "Business rules and edge cases",
            "mature_signal": "Decision rules, exceptions, fallbacks, and boundary cases are explicit.",
            "lens": "Business/Quality",
            "gap_when_missing": "GAP-BUSINESS-RULES",
        },
        {
            "area": "Data and integrations",
            "mature_signal": "Systems, APIs/events, contracts, key fields, ownership, and data source of truth are clear.",
            "lens": "Technology",
            "gap_when_missing": "GAP-TECH-DATA-SOURCE",
        },
        {
            "area": "Non-functional constraints",
            "mature_signal": "Security, privacy, performance, observability, availability, and compliance constraints are visible.",
            "lens": "Technology/Compliance",
            "gap_when_missing": "GAP-TECH-NFR or GAP-GOVERNANCE-CONSTRAINTS",
        },
        {
            "area": "UX journey and states",
            "mature_signal": "User flows, affected screens, copy/messaging, empty/loading/error states, and unchanged UX are clear.",
            "lens": "Design",
            "gap_when_missing": "GAP-DESIGN-FLOW or GAP-DESIGN-STATES",
        },
        {
            "area": "Acceptance and quality",
            "mature_signal": "Happy path, negative paths, stale/missing data, test data, and acceptance criteria are testable.",
            "lens": "Quality",
            "gap_when_missing": "GAP-ACCEPTANCE or GAP-QUALITY",
        },
        {
            "area": "Delivery readiness",
            "mature_signal": "Dependencies, environments, pending approvals, timing, rollout, and open uncertainties are tracked.",
            "lens": "Delivery/Product",
            "gap_when_missing": "GAP-DELIVERY-READINESS",
        },
    ]


def lens_review(
    lens: str,
    role: str,
    text: str,
    context_text: str,
    gaps: list[dict[str, str]],
    gap_ids: tuple[str, ...],
    question: str,
) -> dict[str, str]:
    evidence = "Source + domain context" if context_text.strip() else "Source only; no domain context folder evidence"
    related = [gap["id"] for gap in gaps if gap["id"] in gap_ids or gap.get("lens") in {lens, lens.split("/")[0]}]
    return {
        "lens": lens,
        "role": role,
        "evidence": evidence if text.strip() else "No source evidence",
        "critical_questions": question,
        "gap_ids": ", ".join(f"`{gap_id}`" for gap_id in sorted(set(related))) or "None",
    }


def extract_seed_candidates(text: str, gaps: list[dict[str, str]]) -> list[dict[str, str]]:
    seeds: list[dict[str, str]] = []
    for line in [line.strip(" -\t") for line in text.splitlines() if line.strip()]:
        lowered = line.lower()
        if any(token in lowered for token in ("objetivo", "goal", "outcome")):
            seeds.append({"lens": "business", "truth": line, "status": "KNOWN", "type": "BIZ_OBJECTIVE"})
        elif any(token in lowered for token in ("usuario", "user", "persona", "actor")):
            seeds.append({"lens": "business", "truth": line, "status": "KNOWN", "type": "USER_CONTEXT"})
        elif any(token in lowered for token in ("alcance", "scope", "out of scope")):
            seeds.append({"lens": "product", "truth": line, "status": "KNOWN", "type": "SCOPE_RULE"})
        elif any(token in lowered for token in ("quality", "calidad", "qa", "test")):
            seeds.append({"lens": "quality", "truth": line, "status": "KNOWN", "type": "QUALITY_EXPECTATION"})
        elif METRIC_RE.search(line):
            status = "KNOWN" if any(token in lowered for token in ("source", "fuente", "baseline", "medido", "measured")) else "PENDING_SOURCE"
            seeds.append({"lens": "business", "truth": line, "status": status, "type": "METRIC"})
    for gap in gaps:
        seeds.append({"lens": lens_for_gap(gap["id"]), "truth": gap["description"], "status": "PENDING", "type": "GAP_PLACEHOLDER"})
    return seeds or [{"lens": "product", "truth": extract_requirement(text), "status": "INFERRED", "type": "PRIMARY_REQUIREMENT"}]


def load_domain_context(base: Path) -> dict[str, str]:
    folders = {
        "business": base / "00_raw" / "01_business_context",
        "technical": base / "00_raw" / "02_technology_context",
        "design": base / "00_raw" / "03_design_context",
        "quality": base / "00_raw" / "04_quality_context",
        "interactions": base / "00_raw" / "05_interactions",
    }
    context: dict[str, str] = {}
    for domain, folder in folders.items():
        chunks = []
        if folder.exists():
            for path in sorted(folder.rglob("*.md")) + sorted(folder.rglob("*.txt")):
                chunks.append(path.read_text(encoding="utf-8"))
        context[domain] = "\n\n".join(chunks)
    return context


def lens_signal(domain: str, context: dict[str, str]) -> str:
    text = context.get(domain, "").strip()
    if text:
        return f"{domain.title()} context folder contains evidence ({len(text)} chars)."
    return f"No {domain} context folder evidence was found during discovery."


def lens_for_gap(gap_id: str) -> str:
    if "TECH" in gap_id:
        return "technical"
    if "DESIGN" in gap_id:
        return "design"
    if "GOVERNANCE" in gap_id:
        return "compliance"
    if "DELIVERY" in gap_id:
        return "delivery"
    if "QUALITY" in gap_id or "ACCEPTANCE" in gap_id:
        return "quality"
    if "USERS" in gap_id or "SCOPE" in gap_id or "OBJECTIVE" in gap_id or "BUSINESS" in gap_id:
        return "business"
    if "METRIC" in gap_id:
        return "business"
    return "product"


def question_for_gap(gap_id: str) -> str:
    questions = {
        "GAP-OBJECTIVE": "What business outcome should this requirement achieve?",
        "GAP-USERS": "Which users, personas, or roles are in scope?",
        "GAP-SCOPE": "What is explicitly in scope and out of scope?",
        "GAP-ACCEPTANCE": "What observable conditions prove the requirement is done?",
        "GAP-QUALITY": "What quality, testability, risk, or compliance expectations apply?",
        "GAP-METRIC-SOURCE": "What is the source or baseline for the quantitative metric?",
        "GAP-TECH-DATA-SOURCE": "Which systems, APIs, events, key fields, owners, and source-of-truth data are involved?",
        "GAP-TECH-NFR": "What security, performance, observability, availability, or operational constraints apply?",
        "GAP-DESIGN-FLOW": "Which user journey, screens, flows, copy, or interaction changes are in scope?",
        "GAP-DESIGN-STATES": "What loading, empty, error, recovery, and accessibility states must be handled?",
        "GAP-PRODUCT-ASIS-TOBE": "What is the current process, target process, and exact delta between them?",
        "GAP-BUSINESS-RULES": "Which rules, exceptions, validations, fallbacks, or exclusions govern the behavior?",
        "GAP-GOVERNANCE-CONSTRAINTS": "Which security, privacy, compliance, audit, or operational restrictions must be respected?",
        "GAP-DELIVERY-READINESS": "Which dependencies, environments, approvals, owners, dates, or rollout constraints remain pending?",
    }
    return questions.get(gap_id, "What confirmed information resolves this uncertainty?")


def extract_context(text: str) -> str:
    return "When the target user faces the operational situation described in the source input"


def extract_need(text: str) -> str:
    return extract_requirement(text)


def extract_result(text: str) -> str:
    for line in text.splitlines():
        if any(token in line.lower() for token in ("resultado", "success", "outcome", "para", "so that")):
            return line.strip(" -\t")
    return "Obtain the expected business outcome without unresolved ambiguity."


def quality_signal(text: str) -> str:
    return "Quality expectations are present in source input." if any(
        token in text.lower() for token in ("quality", "calidad", "qa", "test")
    ) else "Quality expectations are not explicit enough."


def render_refinement_hooks(gaps: list[dict[str, str]]) -> str:
    if not gaps:
        return "- No blocking refinement hooks detected."
    return "\n".join(f"- {gap['id']}: {question_for_gap(gap['id'])}" for gap in gaps)
