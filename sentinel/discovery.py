from __future__ import annotations

import re
import shutil
from pathlib import Path

from .memory import ContextBroker, index_context_folders
from .sources import mark_source_processed
from .traceability import add_edge, add_node
from .workspace import ensure_workspace, load_config, update_state, workspace_path

METRIC_RE = re.compile(r"(\d+(?:[.,]\d+)?\s?%|\$\s?\d+|\d+\s?(?:usd|ars|eur|hours|horas|days|dias))", re.I)


def ingest(project_id: str, source: Path) -> dict[str, str]:
    ensure_workspace(project_id)
    base = workspace_path(project_id)
    text = source.read_text(encoding="utf-8")
    language = resolve_project_language(load_config(project_id).get("project_language", "auto"), text)
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
    gap_path.write_text(render_gaps(project_id, gaps, req_id, language), encoding="utf-8")
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
        project_language=language,
        privacy_mode="local-only",
        readiness_stage="CLIENT_RESPONSE_NEEDED" if gaps else "READY_FOR_PROJECT_BRIEF",
        gap_counts=count_gaps(gaps),
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


PERSONA_HINTS = (
    "user", "usuario", "usuarios", "actor", "actores", "persona", "lead", "leads",
    "analyst", "analista", "manager", "operator", "operador", "cliente", "customer",
    "equipo", "team", "back office", "stakeholder", "supervisor",
)

REQUIREMENT_HINTS = (
    "must", "shall", "should", "need", "want", "require", "expect",
    "queremos", "necesit", "debe", "deber", "se requiere", "permitir", "esperamos",
)


def split_evidence_sentences(text: str) -> list[str]:
    """Split raw evidence into clean sentences, dropping markdown noise."""
    import re as _re

    cleaned_lines = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        line = line.lstrip("-*>0123456789. \t")
        if line:
            cleaned_lines.append(line)
    blob = " ".join(cleaned_lines)
    parts = _re.split(r"(?<=[.!?])\s+", blob)
    return [part.strip() for part in parts if len(part.strip()) >= 15]


def extract_personas(text: str, limit: int = 5) -> list[dict[str, str]]:
    """Extract persona/actor evidence sentences from raw client input."""
    results: list[dict[str, str]] = []
    seen: set[str] = set()
    for sentence in split_evidence_sentences(text):
        lowered = sentence.lower()
        if any(hint in lowered for hint in PERSONA_HINTS):
            key = lowered[:80]
            if key in seen:
                continue
            seen.add(key)
            results.append({"evidence": sentence})
            if len(results) >= limit:
                break
    return results


def extract_functional_signals(text: str, limit: int = 7) -> list[dict[str, str]]:
    """Extract requirement-like statements (modal/need language) from raw input."""
    results: list[dict[str, str]] = []
    seen: set[str] = set()
    for sentence in split_evidence_sentences(text):
        lowered = sentence.lower()
        if any(hint in lowered for hint in REQUIREMENT_HINTS):
            key = lowered[:80]
            if key in seen:
                continue
            seen.add(key)
            results.append({"statement": sentence})
            if len(results) >= limit:
                break
    return results


def extract_metric_signals(text: str, limit: int = 5) -> list[dict[str, str]]:
    """Extract quantitative metric mentions with their evidence sentence."""
    results: list[dict[str, str]] = []
    seen: set[str] = set()
    for sentence in split_evidence_sentences(text):
        match = METRIC_RE.search(sentence)
        if not match:
            continue
        key = sentence.lower()[:80]
        if key in seen:
            continue
        seen.add(key)
        results.append({"metric": match.group(0), "evidence": sentence})
        if len(results) >= limit:
            break
    return results


def detect_gaps(text: str, context: dict[str, str] | None = None) -> list[dict[str, str]]:
    lowered = text.lower()
    context = context or {}
    tech_evidence = " ".join([text, context.get("technical", "")]).lower()
    design_evidence = " ".join([text, context.get("design", "")]).lower()
    quality_evidence = " ".join([text, context.get("quality", "")]).lower()
    frontend_evidence = " ".join([text, context.get("design", ""), context.get("technical", "")]).lower()
    checks = [
        ("GAP-OBJECTIVE", "business", "high", "Business objective or expected outcome is not explicit.", lowered, ("objetivo", "objective", "outcome", "resultado", "goal", "purpose", "proposito", "propósito", "aim")),
        ("GAP-USERS", "business", "high", "Target users or personas are not explicit.", lowered, ("usuario", "user", "persona", "actor")),
        ("GAP-SCOPE", "product", "critical", "Scope boundaries are not explicit.", lowered, ("alcance", "scope", "in scope", "out of scope")),
        ("GAP-ACCEPTANCE", "quality", "critical", "Acceptance criteria or success conditions are missing.", lowered, ("criterio", "acceptance", "success", "done")),
        ("GAP-QUALITY", "quality", "medium", "Quality or testability expectations are not explicit.", quality_evidence, ("test", "quality", "calidad", "qa")),
        ("GAP-TECH-DATA-SOURCE", "technical", "medium", "Data source, integration, or system ownership is not explicit in source or technology context.", tech_evidence, ("data", "dato", "source", "fuente", "api", "integration", "integracion", "database", "crm", "endpoint")),
        ("GAP-TECH-NFR", "technical", "medium", "Performance, security, observability, or operational constraints are not explicit.", tech_evidence, ("performance", "seguridad", "security", "observability", "observabilidad", "sla", "timeout", "audit", "compliance")),
        ("GAP-PRODUCT-ASIS-TOBE", "product", "medium", "Current state and target state are not both explicit enough to compare impact.", lowered, ("as-is", "to-be", "situacion actual", "situación actual", "proceso actual", "proceso ideal", "estado actual", "estado futuro")),
        ("GAP-BUSINESS-RULES", "business", "medium", "Business rules, exclusions, or decision rules are not explicit enough for downstream slicing.", lowered, ("regla", "rule", "validacion", "validación", "condicion", "condición", "exclusion", "exclusión")),
        ("GAP-GOVERNANCE-CONSTRAINTS", "compliance", "medium", "Governance, security, privacy, compliance, or operational restrictions are not explicit.", lowered, ("seguridad", "security", "privacidad", "privacy", "compliance", "normativa", "restriccion", "restricción", "gobernanza")),
        ("GAP-DELIVERY-READINESS", "delivery", "medium", "Dependencies, environments, ownership, timing, or rollout constraints are not explicit.", lowered, ("dependencia", "dependency", "ambiente", "environment", "deadline", "fecha", "timeline", "owner", "responsable", "rollout")),
        ("GAP-BACKLOG-SLICING-READINESS", "product", "medium", "Backlog slicing signals are not explicit enough: first value slice, workflow paths, variants, rule deferral, or story boundaries are unclear.", lowered, ("slice", "slicing", "vertical", "historia", "story", "epica", "epic", "workflow", "path", "variante", "variant", "mvp")),
        ("GAP-BACKLOG-ENABLERS", "technical", "medium", "Cross-cutting enablers are not explicit enough: implementation work that must be built in advance across frontend/backend or architecture surfaces must be tied to confirmed project functionality and boundary.", " ".join([lowered, tech_evidence, design_evidence, quality_evidence]), ("enabler", "habilitador", "sad", "architecture", "arquitectura", "as-is", "to-be", "frontend", "backend", "prototype", "prototipo", "auth", "permiso", "permission", "database", "base de datos", "query", "api", "endpoint", "integration", "audit", "observability", "observabilidad")),
        ("GAP-QUALITY-HANDOFF", "quality", "medium", "Quality handoff is not explicit enough: critical flows, edge cases, test data, regression risks, or evidence expectations are unclear.", quality_evidence, ("test", "quality", "calidad", "qa", "happy path", "edge", "borde", "regression", "regresion", "evidencia", "data")),
        ("GAP-PRD-PERSONA-DETAIL", "business", "medium", "Persona attributes are not complete enough for a PRD: goals, pain points, proficiency, and usage frequency are unclear.", lowered, ("pain", "dolor", "goal", "objetivo", "frecuencia", "frequency", "proficiency", "habilidad", "perfil")),
        ("GAP-PRD-FR-AC", "product", "medium", "Functional requirements are not decomposed with source-backed acceptance criteria.", lowered, ("fr-", "requerimiento funcional", "functional requirement", "acceptance criteria", "criterios de aceptacion", "criterios de aceptación", "given", "when", "then")),
        ("GAP-PRD-NFR-KPI", "quality", "medium", "NFRs, KPIs, targets, measurement method, or timeframe are not explicit enough for PRD governance.", lowered, ("nfr", "non functional", "no funcional", "kpi", "target", "measurement", "medicion", "medición", "timeframe", "baseline")),
        ("GAP-PRD-DEPENDENCIES-ROADMAP", "delivery", "medium", "Dependencies, owners, MVP scope, nice-to-haves, or roadmap are not explicit enough for PRD execution planning.", lowered, ("mvp", "roadmap", "dependencia", "dependency", "owner", "responsable", "nice-to-have", "fase", "phase")),
        ("GAP-PRD-GLOSSARY-GOVERNANCE", "compliance", "medium", "Glossary, mandatory constraints, pending inputs, or governance/audit notes are not explicit enough for a complete PRD.", lowered, ("glosario", "glossary", "restriccion", "restricción", "mandatory", "audit", "auditoria", "governance", "gobernanza", "pending input")),
    ]
    gaps = [
        {"id": gap_id, "lens": lens, "severity": severity, "description": description}
        for gap_id, lens, severity, description, evidence, tokens in checks
        if not any(token in evidence for token in tokens)
    ]
    # Inquisitive tier (IMP-015): a surface mentioned in the evidence does not
    # answer the question about that surface. These gaps only close when the
    # counterpart information is described; a bare mention anchors the question
    # to the input instead of suppressing it.
    inquisitive_rules = [
        ("GAP-DESIGN-FLOW", "design", "medium", "User journey, screen flow, or interaction model is not explicit in source or design context.", design_evidence,
         ("screen", "pantalla", "dashboard", "portal", " ui ", "page", "web", "app"),
         ("journey", "flow", "flujo", "navigation", "navegacion", "navegación", "wireframe", "mock", "prototype", "prototipo", "recorrido")),
        ("GAP-DESIGN-STATES", "design", "medium", "Required UI states for loading, empty, error, and recovery are not explicit.", design_evidence,
         ("screen", "pantalla", "dashboard", "portal", " ui ", "page", "web", "app"),
         ("loading", "empty", "error state", "estado de error", "vacío", "vacio", "spinner", "skeleton", "ui states", "estados de ui", "recovery")),
        ("GAP-DESIGN-PROTOTYPE-INPUT", "design", "medium", "The requirement does not make clear what Design must prototype or validate in user flows.", design_evidence,
         ("screen", "pantalla", "dashboard", "portal", " ui ", "page", "web", "app"),
         ("prototype", "prototipo", "wireframe", "figma", "mock", "maqueta")),
        ("GAP-FRONTEND-SURFACE", "technical", "medium", "Frontend implementation surface is not explicit enough: affected screens, states, validations, copy, roles, or API binding needs are unclear.", frontend_evidence,
         ("frontend", "pantalla", "screen", "dashboard", "portal", " ui ", "web", "app"),
         ("validation", "validacion", "validación", "copy", "role", " rol ", "permiso", "binding", "component", "componente")),
        ("GAP-BACKEND-SURFACE", "technical", "medium", "Backend implementation surface is not explicit enough: capabilities, integrations, rules, persistence, contracts, or failure behavior are unclear.", tech_evidence,
         ("backend", "api", "endpoint", "service", "servicio", "integration", "integracion", "integración", "sync", "sincroniza"),
         ("contract", "contrato", "persist", "database", "base de datos", "failure", "falla", "retry", "reintento", "timeout", "idempot", "error handling", "manejo de errores")),
        ("GAP-TECH-DEEP-DIVE-INPUT", "technical", "medium", "Technology has insufficient input to perform repository, architecture, endpoint/event, source-of-truth, or risk analysis.", tech_evidence,
         ("api", "endpoint", "integration", "integracion", "integración", "system", "sistema", "platform", "plataforma", "service", "servicio"),
         ("repo", "repository", "arquitectura", "architecture", "source of truth", "diagrama", "diagram", " sad ")),
    ]
    for gap_id, lens, severity, description, evidence, triggers, counterparts in inquisitive_rules:
        if any(token in evidence for token in counterparts):
            continue
        gap = {"id": gap_id, "lens": lens, "severity": severity, "description": description}
        mention = next((token.strip() for token in triggers if token in evidence), None)
        if mention:
            gap["evidence_mention"] = mention
        gaps.append(gap)
    metric_match = METRIC_RE.search(text)
    if metric_match and not any(token in lowered for token in ("source", "fuente", "baseline", "medido", "measured")):
        gaps.append(
            {
                "id": "GAP-METRIC-SOURCE",
                "lens": "business",
                "severity": "high",
                "description": "Quantitative metric appears without an explicit source or baseline.",
                "evidence_mention": metric_match.group(0),
            }
        )
    return gaps


def count_gaps(gaps: list[dict[str, str]]) -> dict[str, int]:
    counts = {
        "open": 0,
        "closed": 0,
        "partially_closed": 0,
        "answered": 0,
        "blocking_open": 0,
        "total": len(gaps),
    }
    for gap in gaps:
        status = str(gap.get("status", "OPEN")).upper()
        severity = str(gap.get("severity", "")).lower()
        if status == "OPEN":
            counts["open"] += 1
            if severity in {"critical", "high"}:
                counts["blocking_open"] += 1
        elif status == "ANSWERED":
            counts["answered"] += 1
            if severity in {"critical", "high"}:
                counts["blocking_open"] += 1
        elif status == "PARTIALLY_CLOSED":
            counts["partially_closed"] += 1
            if severity in {"critical", "high"}:
                counts["blocking_open"] += 1
        elif status == "CLOSED":
            counts["closed"] += 1
    return counts


def parse_gap_rows(text: str) -> list[dict[str, str]]:
    gaps: list[dict[str, str]] = []
    for line in text.splitlines():
        cells = [cell.strip().strip("`") for cell in line.strip().strip("|").split("|")]
        if not cells or not cells[0].startswith("GAP-"):
            continue
        if len(cells) >= 8:
            gap = {
                "id": cells[0],
                "lens": cells[1],
                "severity": cells[2],
                "status": cells[3],
                "parent": cells[4],
                "description": cells[5],
                "question": cells[6],
                "source": cells[7],
            }
            if len(cells) >= 9 and cells[8] not in {"", "N/A"}:
                gap["evidence_mention"] = cells[8]
            gaps.append(gap)
    return gaps


def regenerate_gaps(project_id: str) -> dict[str, object]:
    base = workspace_path(project_id)
    gaps_path = base / "01_discovery" / "gaps.md"
    if not gaps_path.exists():
        raise RuntimeError("Cannot regenerate gaps before /ingest creates 01_discovery/gaps.md.")
    existing = parse_gap_rows(gaps_path.read_text(encoding="utf-8"))
    req_id = existing[0].get("parent", "REQ-001").strip("`") if existing else "REQ-001"
    state_language = load_config(project_id).get("project_language", "auto")
    state_path = base / "state.json"
    if state_path.exists():
        try:
            import json

            state = json.loads(state_path.read_text(encoding="utf-8"))
            state_language = state.get("project_language", state_language)
        except Exception:
            pass
    language = str(state_language if state_language in {"es", "en"} else "en")
    gaps_path.write_text(render_gaps(project_id, existing, req_id, language), encoding="utf-8")
    counts = count_gaps(existing)
    update_state(project_id, gap_counts=counts, readiness_stage=readiness_stage_for_counts(counts))
    return {"project_id": project_id, "path": str(gaps_path), "gap_counts": counts}


def readiness_stage_for_counts(counts: dict[str, int]) -> str:
    if counts.get("blocking_open", 0):
        return "CLIENT_RESPONSE_NEEDED"
    if counts.get("open", 0) or counts.get("partially_closed", 0) or counts.get("answered", 0):
        return "DOMAIN_RESPONSE_NEEDED"
    return "READY_FOR_PROJECT_BRIEF"


def render_requirement(project_id: str, req_text: str, raw_id: str) -> str:
    return f"""# Requirement Register - {project_id}

## REQ-001 Primary Requirement

- Source: `{raw_id}`
- Status: `draft`
- Domains: product, functional, quality

{req_text}
"""


def resolve_project_language(configured_language: object, text: str) -> str:
    configured = str(configured_language or "auto").lower()
    if configured in {"es", "en"}:
        return configured
    return detect_language(text)


def detect_language(text: str) -> str:
    lowered = text.lower()
    spanish_markers = (
        " objetivo",
        " usuario",
        " usuarios",
        " alcance",
        " criterio",
        " criterios",
        " calidad",
        " requerimiento",
        " pantalla",
        " flujo",
        " diseño",
        " tecnología",
        " integración",
        " validación",
        " negocio",
        " fuente",
        " datos",
        " qué",
        " cómo",
        " para ",
        " con ",
        " debe ",
        " deberán ",
    )
    english_markers = (
        " goal",
        " user",
        " users",
        " scope",
        " acceptance",
        " quality",
        " requirement",
        " screen",
        " flow",
        " design",
        " technology",
        " integration",
        " validation",
        " business",
        " source",
        " data",
        " what",
        " how",
        " should",
        " must",
    )
    spanish_score = sum(1 for marker in spanish_markers if marker in f" {lowered} ")
    english_score = sum(1 for marker in english_markers if marker in f" {lowered} ")
    if any(char in lowered for char in "áéíóúñ¿¡"):
        spanish_score += 2
    return "es" if spanish_score > english_score else "en"


def no_gaps_text(language: str) -> str:
    if language == "es":
        return """## No se detectaron gaps abiertos

El escaneo determinístico de discovery no detectó gaps bloqueantes ni de seguimiento. Si el cliente o los equipos de dominio tienen contexto adicional, agregarlo en `Notas adicionales` y devolverlo como input de cambio.
"""
    return """## No Open Gaps Detected

No blocking or follow-up gaps were detected by the deterministic discovery scan. If the client or domain teams have additional context, add it under `Additional Notes` and send it back as a change input.
"""


def source_consulted_text(language: str) -> str:
    return "Carpetas de contexto e input fuente." if language == "es" else "Context folders and source input."


def none_gap_row(language: str) -> str:
    if language == "es":
        return "| NONE | Todos | none | CLOSED | N/A | No se detectaron gaps bloqueantes por escaneo determinístico. | N/A | Input fuente. | N/A |"
    return "| NONE | All | none | CLOSED | N/A | No blocking gaps detected by deterministic scan. | N/A | Source input. | N/A |"


def description_for_gap(gap: dict[str, str], language: str = "en") -> str:
    if language != "es":
        return gap["description"]
    descriptions = {
        "GAP-OBJECTIVE": "El objetivo de negocio o resultado esperado no está explícito.",
        "GAP-USERS": "Los usuarios, personas o actores objetivo no están explícitos.",
        "GAP-SCOPE": "Los límites de alcance no están explícitos.",
        "GAP-ACCEPTANCE": "Faltan criterios de aceptación o condiciones de éxito.",
        "GAP-QUALITY": "Las expectativas de calidad o testeabilidad no están explícitas.",
        "GAP-METRIC-SOURCE": "Aparece una métrica cuantitativa sin fuente o baseline explícito.",
        "GAP-TECH-DATA-SOURCE": "La fuente de datos, integración u ownership de sistema no está explícito en el input o contexto técnico.",
        "GAP-TECH-NFR": "No están explícitas restricciones de performance, seguridad, observabilidad u operación.",
        "GAP-DESIGN-FLOW": "El journey de usuario, flujo de pantallas o modelo de interacción no está explícito en el input o contexto de diseño.",
        "GAP-DESIGN-STATES": "No están explícitos los estados requeridos de UI: loading, empty, error y recuperación.",
        "GAP-DESIGN-PROTOTYPE-INPUT": "No queda claro qué debe prototipar o validar Diseño en los flujos de usuario.",
        "GAP-PRODUCT-ASIS-TOBE": "El estado actual y el estado objetivo no están suficientemente claros para comparar impacto.",
        "GAP-BUSINESS-RULES": "Las reglas de negocio, exclusiones o reglas de decisión no están suficientemente explícitas para slicing downstream.",
        "GAP-FRONTEND-SURFACE": "La superficie de implementación frontend no está suficientemente explícita: pantallas, estados, validaciones, copy, roles o bindings de API.",
        "GAP-BACKEND-SURFACE": "La superficie de implementación backend no está suficientemente explícita: capacidades, integraciones, reglas, persistencia, contratos o comportamiento ante fallas.",
        "GAP-TECH-DEEP-DIVE-INPUT": "Tecnología no cuenta con suficiente input para análisis de repositorios, arquitectura, endpoints/eventos, source of truth o riesgos.",
        "GAP-GOVERNANCE-CONSTRAINTS": "No están explícitas restricciones de gobernanza, seguridad, privacidad, compliance u operación.",
        "GAP-DELIVERY-READINESS": "No están explícitas dependencias, ambientes, ownership, fechas o restricciones de rollout.",
        "GAP-BACKLOG-SLICING-READINESS": "No estan explicitas las senales necesarias para slicing de backlog: primer slice de valor, paths, variantes, reglas diferibles o limites de historia.",
        "GAP-BACKLOG-ENABLERS": "No estan claros los enablers transversales validos: trabajo de implementacion frontend/backend o arquitectura que debe construirse antes para soportar funcionalidades confirmadas dentro del boundary del proyecto.",
        "GAP-QUALITY-HANDOFF": "El handoff a Calidad no está suficientemente explícito: flujos críticos, casos borde, datos de prueba, riesgos de regresión o evidencia esperada.",
    }
    return descriptions.get(gap["id"], gap["description"])


def render_gaps(project_id: str, gaps: list[dict[str, str]], req_id: str, language: str = "en") -> str:
    response_sections = "\n\n".join(render_gap_response_section(gap, req_id, language) for gap in gaps)
    if not response_sections:
        response_sections = no_gaps_text(language)

    rows = "\n".join(
        f"| {gap['id']} | {gap.get('lens', lens_for_gap(gap['id']))} | {gap['severity']} | {gap.get('status', 'OPEN')} | `{req_id}` | {description_for_gap(gap, language)} | {question_for_gap(gap['id'], language)} | {source_consulted_text(language)} | {gap.get('evidence_mention') or 'N/A'} |"
        for gap in gaps
    )
    if not rows:
        rows = none_gap_row(language)
    if language == "es":
        return f"""# Gaps de Discovery - {project_id}

Versión del documento: `1.0`
Proyecto: `{project_id}`
Requerimiento padre: `{req_id}`
Audiencia: stakeholders del cliente, Producto, Tecnología, Diseño, Calidad y Delivery.
Propósito: recopilar información faltante o ambigua para madurar el requerimiento y poder generar project brief, PRD, specs, backlog, criterios de aceptación y tests.

## Cómo responder

Por favor responder directamente debajo de cada gap. Una respuesta breve sirve si es precisa. Si la respuesta corresponde a otro equipo, indicar el owner y cualquier información parcial disponible.

Formato sugerido de respuesta:

- Respuesta:
- Owner / fuente:
- Evidencia o referencia:
- Estado de decisión: confirmado / pendiente / no aplica

## Secciones para respuesta del cliente

{response_sections}

## Notas adicionales

Agregar cualquier nuevo requerimiento, restricción, decisión, screenshot, diagrama o ejemplo que no haya quedado cubierto arriba.

## Tabla de trazabilidad del framework

Esta tabla se mantiene para trazabilidad y procesamiento automático de Sentinel.

| Gap ID | Lente | Severidad | Estado | Padre | Descripción | Pregunta para cliente/dominio | Fuente consultada | Disparador detectado |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
{rows}

## Trazabilidad de resolución

| Gap ID | Fuente de resolución | Seed promovida | Artefactos impactados |
| --- | --- | --- | --- |
| TBD | TBD | TBD | TBD |
"""
    return f"""# Discovery Gaps - {project_id}

Document version: `1.0`
Project: `{project_id}`
Parent requirement: `{req_id}`
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

{response_sections}

## Additional Notes

Add any new requirement, constraint, decision, screenshot, diagram, or example that was not covered above.

## Framework Trace Table

This table is kept for Sentinel traceability and automated processing.

| Gap ID | Lens | Severity | Status | Parent | Description | Question For Client/Domain | Source Consulted | Detected Trigger |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
{rows}

## Resolution Trace

| Gap ID | Resolution Source | Promoted Seed | Impacted Artifacts |
| --- | --- | --- | --- |
| TBD | TBD | TBD | TBD |
"""


def evidence_note_for_gap(gap: dict[str, str], language: str = "en") -> str:
    mention = str(gap.get("evidence_mention", "")).strip()
    if not mention:
        return ""
    if language == "es":
        notes = {
            "GAP-DESIGN-FLOW": f'El input menciona "{mention}" pero no describe el journey, la navegación ni el flujo de interacción alrededor.',
            "GAP-DESIGN-STATES": f'El input menciona "{mention}" pero no describe los estados de carga, vacío, error y recuperación.',
            "GAP-DESIGN-PROTOTYPE-INPUT": f'El input menciona "{mention}" pero no indica qué debe prototipar o validar Diseño.',
            "GAP-FRONTEND-SURFACE": f'El input menciona "{mention}" pero no detalla validaciones, roles, copy ni binding de datos de esa superficie.',
            "GAP-BACKEND-SURFACE": f'El input menciona "{mention}" pero no describe contratos, persistencia ni comportamiento ante fallas.',
            "GAP-TECH-DEEP-DIVE-INPUT": f'El input menciona "{mention}" pero no aporta arquitectura, repositorios ni source of truth para profundizar.',
            "GAP-METRIC-SOURCE": f'La métrica "{mention}" aparece sin fuente, baseline ni método de medición.',
        }
        return notes.get(gap["id"], f'El input menciona "{mention}" pero no describe la información faltante de este gap.')
    notes = {
        "GAP-DESIGN-FLOW": f'The input mentions "{mention}" but does not describe the journey, navigation, or interaction flow around it.',
        "GAP-DESIGN-STATES": f'The input mentions "{mention}" but does not describe loading, empty, error, and recovery states.',
        "GAP-DESIGN-PROTOTYPE-INPUT": f'The input mentions "{mention}" but does not state what Design must prototype or validate.',
        "GAP-FRONTEND-SURFACE": f'The input mentions "{mention}" but does not detail validations, roles, copy, or data binding for that surface.',
        "GAP-BACKEND-SURFACE": f'The input mentions "{mention}" but does not describe contracts, persistence, or failure behavior.',
        "GAP-TECH-DEEP-DIVE-INPUT": f'The input mentions "{mention}" but provides no architecture, repository, or source-of-truth input to deepen it.',
        "GAP-METRIC-SOURCE": f'The metric "{mention}" appears without a source, baseline, or measurement method.',
    }
    return notes.get(gap["id"], f'The input mentions "{mention}" but does not describe the missing information for this gap.')


def render_gap_response_section(gap: dict[str, str], req_id: str, language: str = "en") -> str:
    gap_id = gap["id"]
    lens = gap.get("lens", lens_for_gap(gap_id))
    evidence_note = evidence_note_for_gap(gap, language)
    evidence_label = "Evidencia que dispara la pregunta:" if language == "es" else "Evidence that triggers the question:"
    evidence_block = f"\n{evidence_label}\n{evidence_note}\n" if evidence_note else ""
    if language == "es":
        return f"""### {gap_id} - {human_title_for_gap(gap_id, language)}

- Lente: `{lens}`
- Severidad: `{gap['severity']}`
- Estado: `{gap.get('status', 'OPEN')}`
- Requerimiento relacionado: `{req_id}`

Descripción breve:
{description_for_gap(gap, language)}
{evidence_block}
Por qué lo preguntamos:
{why_gap_matters(gap_id, language)}

Pregunta:
{question_for_gap(gap_id, language)}

Ejemplo de respuesta útil:
{example_response_for_gap(gap_id, language)}

Respuesta del cliente / dominio:

- Respuesta:
- Owner / fuente:
- Evidencia o referencia:
- Estado de decisión:
"""
    return f"""### {gap_id} - {human_title_for_gap(gap_id)}

- Lens: `{lens}`
- Severity: `{gap['severity']}`
- Status: `{gap.get('status', 'OPEN')}`
- Related requirement: `{req_id}`

Brief description:
{gap['description']}
{evidence_block}
Why we are asking:
{why_gap_matters(gap_id)}

Question:
{question_for_gap(gap_id)}

Example of a useful answer:
{example_response_for_gap(gap_id)}

Client / domain response:

- Answer:
- Owner / source:
- Evidence or reference:
- Decision status:
"""


def human_title_for_gap(gap_id: str, language: str = "en") -> str:
    prd_titles_es = {
        "GAP-PRD-PERSONA-DETAIL": "Detalle de personas para PRD",
        "GAP-PRD-FR-AC": "Requerimientos funcionales y criterios de aceptacion",
        "GAP-PRD-NFR-KPI": "NFRs, KPIs y medicion",
        "GAP-PRD-DEPENDENCIES-ROADMAP": "Dependencias y roadmap",
        "GAP-PRD-GLOSSARY-GOVERNANCE": "Glosario y gobernanza",
    }
    prd_titles_en = {
        "GAP-PRD-PERSONA-DETAIL": "PRD Persona Detail",
        "GAP-PRD-FR-AC": "Functional Requirements And ACs",
        "GAP-PRD-NFR-KPI": "NFRs, KPIs, And Measurement",
        "GAP-PRD-DEPENDENCIES-ROADMAP": "Dependencies And Roadmap",
        "GAP-PRD-GLOSSARY-GOVERNANCE": "Glossary And Governance",
    }
    if language == "es" and gap_id in prd_titles_es:
        return prd_titles_es[gap_id]
    if gap_id in prd_titles_en:
        return prd_titles_en[gap_id]
    if language == "es":
        titles = {
            "GAP-OBJECTIVE": "Resultado esperado",
            "GAP-USERS": "Usuarios y actores",
            "GAP-SCOPE": "Límites de alcance",
            "GAP-ACCEPTANCE": "Señal de aceptación",
            "GAP-QUALITY": "Expectativas de calidad",
            "GAP-METRIC-SOURCE": "Fuente de métrica",
            "GAP-TECH-DATA-SOURCE": "Sistemas y ownership de datos",
            "GAP-TECH-NFR": "Restricciones operativas",
            "GAP-DESIGN-FLOW": "Journey y pantallas",
            "GAP-DESIGN-STATES": "Estados de UX",
            "GAP-DESIGN-PROTOTYPE-INPUT": "Foco del prototipo",
            "GAP-PRODUCT-ASIS-TOBE": "Proceso actual y objetivo",
            "GAP-BUSINESS-RULES": "Reglas de negocio",
            "GAP-FRONTEND-SURFACE": "Superficie frontend",
            "GAP-BACKEND-SURFACE": "Superficie backend",
            "GAP-TECH-DEEP-DIVE-INPUT": "Profundización técnica",
            "GAP-GOVERNANCE-CONSTRAINTS": "Restricciones de gobernanza",
            "GAP-DELIVERY-READINESS": "Preparación de delivery",
            "GAP-BACKLOG-SLICING-READINESS": "Preparacion de slicing de backlog",
            "GAP-BACKLOG-ENABLERS": "Enablers transversales validos",
            "GAP-QUALITY-HANDOFF": "Handoff de calidad",
        }
        return titles.get(gap_id, "Información necesaria")
    titles = {
        "GAP-OBJECTIVE": "Expected Outcome",
        "GAP-USERS": "Users And Actors",
        "GAP-SCOPE": "Scope Boundaries",
        "GAP-ACCEPTANCE": "Acceptance Signal",
        "GAP-QUALITY": "Quality Expectations",
        "GAP-METRIC-SOURCE": "Metric Source",
        "GAP-TECH-DATA-SOURCE": "Systems And Data Ownership",
        "GAP-TECH-NFR": "Operational Constraints",
        "GAP-DESIGN-FLOW": "User Journey And Screens",
        "GAP-DESIGN-STATES": "UX States",
        "GAP-DESIGN-PROTOTYPE-INPUT": "Prototype Focus",
        "GAP-PRODUCT-ASIS-TOBE": "Current And Target Process",
        "GAP-BUSINESS-RULES": "Business Rules",
        "GAP-FRONTEND-SURFACE": "Frontend Surface",
        "GAP-BACKEND-SURFACE": "Backend Surface",
        "GAP-TECH-DEEP-DIVE-INPUT": "Technology Deep Dive",
        "GAP-GOVERNANCE-CONSTRAINTS": "Governance Constraints",
        "GAP-DELIVERY-READINESS": "Delivery Readiness",
        "GAP-BACKLOG-SLICING-READINESS": "Backlog Slicing Readiness",
        "GAP-BACKLOG-ENABLERS": "Valid Cross-Cutting Enablers",
        "GAP-QUALITY-HANDOFF": "Quality Handoff",
    }
    return titles.get(gap_id, "Information Needed")


def why_gap_matters(gap_id: str, language: str = "en") -> str:
    prd_reasons_es = {
        "GAP-PRD-PERSONA-DETAIL": "El PRD necesita personas con objetivos, dolores, frecuencia y habilidad para orientar experiencia, adopcion y soporte.",
        "GAP-PRD-FR-AC": "El PRD debe listar requerimientos funcionales con criterios de aceptacion trazables para que backlog y QA no inventen alcance.",
        "GAP-PRD-NFR-KPI": "NFRs y KPIs con targets, metodo de medicion y ventana temporal permiten validar valor y calidad objetivamente.",
        "GAP-PRD-DEPENDENCIES-ROADMAP": "Dependencias, owners, MVP y roadmap sostienen la planificacion y evitan historias bloqueadas por supuestos.",
        "GAP-PRD-GLOSSARY-GOVERNANCE": "Glosario, restricciones mandatorias, pending inputs y audit trail preservan entendimiento compartido y trazabilidad.",
    }
    prd_reasons_en = {
        "GAP-PRD-PERSONA-DETAIL": "The PRD needs personas with goals, pain points, frequency, and proficiency to guide experience, adoption, and support decisions.",
        "GAP-PRD-FR-AC": "The PRD must list functional requirements with traceable acceptance criteria so backlog and QA do not invent scope.",
        "GAP-PRD-NFR-KPI": "NFRs and KPIs with targets, measurement method, and timeframe make value and quality objectively verifiable.",
        "GAP-PRD-DEPENDENCIES-ROADMAP": "Dependencies, owners, MVP, and roadmap support planning and prevent stories from being blocked by assumptions.",
        "GAP-PRD-GLOSSARY-GOVERNANCE": "Glossary, mandatory constraints, pending inputs, and audit trail preserve shared understanding and traceability.",
    }
    if language == "es" and gap_id in prd_reasons_es:
        return prd_reasons_es[gap_id]
    if gap_id in prd_reasons_en:
        return prd_reasons_en[gap_id]
    if language == "es":
        reasons = {
            "GAP-OBJECTIVE": "Sin el resultado esperado, los agentes downstream podrían optimizar la solución pedida en lugar del objetivo real de negocio.",
            "GAP-USERS": "Diseño, permisos, journeys, criterios de aceptación y rollout pueden cambiar según quién usa u opera la capacidad.",
            "GAP-SCOPE": "Los límites claros evitan que PRD, specs y backlog incluyan trabajo no previsto.",
            "GAP-ACCEPTANCE": "Calidad e implementación necesitan condiciones observables para saber cuándo el requerimiento está terminado.",
            "GAP-QUALITY": "Las expectativas de calidad orientan el análisis de riesgo, la profundidad de pruebas y la evidencia requerida.",
            "GAP-METRIC-SOURCE": "Las métricas necesitan fuente o baseline para medir el éxito de manera consistente.",
            "GAP-TECH-DATA-SOURCE": "Tecnología necesita suficiente contexto de sistemas y ownership para analizar arquitectura sin inventar integraciones.",
            "GAP-TECH-NFR": "Las restricciones operativas afectan arquitectura, implementación, monitoreo y readiness de salida.",
            "GAP-DESIGN-FLOW": "Diseño necesita journeys y pantallas afectadas para crear flujos o prototipos significativos.",
            "GAP-DESIGN-STATES": "Los estados UX faltantes suelen convertirse en ambigüedad de implementación o casos borde sin testear.",
            "GAP-DESIGN-PROTOTYPE-INPUT": "Un prototipo solo es útil si Diseño sabe qué decisión, flujo o interacción debe validar.",
            "GAP-PRODUCT-ASIS-TOBE": "El delta entre comportamiento actual y objetivo guía el análisis de impacto y el slicing de backlog.",
            "GAP-BUSINESS-RULES": "Las reglas y excepciones determinan validaciones, casos borde y criterios de aceptación.",
            "GAP-FRONTEND-SURFACE": "Frontend necesita superficies, estados, copy y bindings afectados antes de estimar o implementar responsablemente.",
            "GAP-BACKEND-SURFACE": "Backend necesita contexto de capacidades, integraciones, persistencia y comportamiento ante fallas antes de diseñar servicios.",
            "GAP-TECH-DEEP-DIVE-INPUT": "Los agentes técnicos necesitan dirección suficiente para inspeccionar repositorios, componentes, endpoints y riesgos eficientemente.",
            "GAP-GOVERNANCE-CONSTRAINTS": "Seguridad, privacidad, compliance y auditoría pueden cambiar diseño, implementación y testing.",
            "GAP-DELIVERY-READINESS": "Dependencias, owners, ambientes y fechas determinan secuencia y factibilidad de salida.",
            "GAP-BACKLOG-SLICING-READINESS": "El backlog necesita saber cual es el primer slice de valor, que variantes pueden diferirse y donde no conviene cortar por debajo del valor.",
            "GAP-BACKLOG-ENABLERS": "Los enablers transversales solo son validos si son implementacion previa/cross que soporta funcionalidad confirmada dentro del boundary del proyecto.",
            "GAP-QUALITY-HANDOFF": "QA necesita flujos críticos, casos borde, datos y expectativas de evidencia para profundizar cobertura.",
        }
        return reasons.get(gap_id, "Esta información es necesaria para evitar supuestos en artefactos downstream.")
    reasons = {
        "GAP-OBJECTIVE": "Without the expected outcome, downstream agents may optimize for the requested feature instead of the real business result.",
        "GAP-USERS": "Design, permissions, journeys, acceptance criteria, and rollout can change depending on who uses or operates the capability.",
        "GAP-SCOPE": "Clear boundaries prevent the PRD, specs, and backlog from including unintended work.",
        "GAP-ACCEPTANCE": "Quality and implementation agents need observable conditions to know when the requirement is done.",
        "GAP-QUALITY": "Quality expectations guide risk analysis, test depth, and required evidence.",
        "GAP-METRIC-SOURCE": "Metrics need a source or baseline so success can be measured consistently.",
        "GAP-TECH-DATA-SOURCE": "Technology needs enough system and ownership context to analyze architecture without inventing integrations.",
        "GAP-TECH-NFR": "Operational constraints affect architecture, implementation choices, monitoring, and release readiness.",
        "GAP-DESIGN-FLOW": "Design needs affected journeys and screens to create meaningful flows or prototypes.",
        "GAP-DESIGN-STATES": "Missing UX states often become implementation ambiguity or untested edge cases.",
        "GAP-DESIGN-PROTOTYPE-INPUT": "A prototype is useful only if Design knows what decision, flow, or interaction it must validate.",
        "GAP-PRODUCT-ASIS-TOBE": "The delta between current and target behavior drives impact analysis and backlog slicing.",
        "GAP-BUSINESS-RULES": "Rules and exceptions determine validations, edge cases, and acceptance criteria.",
        "GAP-FRONTEND-SURFACE": "Frontend agents need affected surfaces, states, copy, and bindings before estimating or implementing responsibly.",
        "GAP-BACKEND-SURFACE": "Backend agents need capability, integration, persistence, and failure-behavior context before designing services.",
        "GAP-TECH-DEEP-DIVE-INPUT": "Technical agents need enough direction to inspect repositories, components, endpoints, and risks efficiently.",
        "GAP-GOVERNANCE-CONSTRAINTS": "Security, privacy, compliance, and audit constraints can change design, implementation, and testing.",
        "GAP-DELIVERY-READINESS": "Dependencies, owners, environments, and timing determine sequencing and release feasibility.",
        "GAP-BACKLOG-SLICING-READINESS": "Backlog needs the first value slice, deferrable variants, and the boundary where splitting smaller would stop producing value.",
        "GAP-BACKLOG-ENABLERS": "Cross-cutting enablers are valid only when they are advance/cross implementation work that supports confirmed functionality inside the project boundary.",
        "GAP-QUALITY-HANDOFF": "QA needs critical flows, edge cases, data, and evidence expectations to deepen coverage.",
    }
    return reasons.get(gap_id, "This information is needed to avoid assumptions in downstream artifacts.")


def example_response_for_gap(gap_id: str, language: str = "en") -> str:
    prd_examples_es = {
        "GAP-PRD-PERSONA-DETAIL": "Persona primaria: operador central. Objetivo: resolver casos sin TI. Dolor: proceso manual riesgoso. Frecuencia: diaria. Habilidad: herramienta interna avanzada.",
        "GAP-PRD-FR-AC": "FR-01: el sistema debe listar elementos pendientes. AC: Given existen pendientes, When el operador consulta, Then ve ID, estado, responsable y fecha con fuente trazable.",
        "GAP-PRD-NFR-KPI": "NFR: auditoria disponible por 2 anios. KPI: 0 operaciones incorrectas, medido por incidentes post-release diarios durante el primer mes.",
        "GAP-PRD-DEPENDENCIES-ROADMAP": "MVP: consulta, regla principal y auditoria. Dependencias: servicio X owner Equipo A, copy owner Diseno, credenciales owner Seguridad. Fase 2: reportes.",
        "GAP-PRD-GLOSSARY-GOVERNANCE": "Glosario: 'estado grisado' significa no operable. Restriccion: no exponer datos sensibles en logs. Pending input: owner de metrica.",
    }
    prd_examples_en = {
        "GAP-PRD-PERSONA-DETAIL": "Primary persona: central operator. Goal: resolve cases without IT. Pain: risky manual process. Frequency: daily. Proficiency: advanced internal tool.",
        "GAP-PRD-FR-AC": "FR-01: the system must list pending items. AC: Given pending items exist, When the operator opens the list, Then ID, status, owner, and date are visible with source trace.",
        "GAP-PRD-NFR-KPI": "NFR: audit records available for 2 years. KPI: 0 incorrect operations, measured through daily post-release incidents during month one.",
        "GAP-PRD-DEPENDENCIES-ROADMAP": "MVP: query, main rule, and audit. Dependencies: service X owner Team A, copy owner Design, credentials owner Security. Phase 2: reporting.",
        "GAP-PRD-GLOSSARY-GOVERNANCE": "Glossary: 'disabled state' means not operable. Constraint: do not expose sensitive data in logs. Pending input: metric owner.",
    }
    if language == "es" and gap_id in prd_examples_es:
        return prd_examples_es[gap_id]
    if gap_id in prd_examples_en:
        return prd_examples_en[gap_id]
    if language == "es":
        examples = {
            "GAP-OBJECTIVE": "El objetivo es reducir el tiempo de revisión manual de analistas operativos mostrando casos de alto riesgo antes de la reunión diaria.",
            "GAP-USERS": "Usuarios primarios: analistas de operaciones. Supervisores solo revisan estado resumido. Compliance consume evidencia de auditoría pero no usa la pantalla.",
            "GAP-SCOPE": "In scope: indicador de riesgo en dashboard diario. Out of scope: reportes históricos, facturación y planificación de dotación. Los filtros existentes deben mantenerse.",
            "GAP-ACCEPTANCE": "Dado que una cola tiene casos por encima del umbral de SLA, cuando carga el dashboard, entonces la cola se marca como alto riesgo y el analista puede identificarla sin abrir el detalle.",
            "GAP-QUALITY": "QA debe cubrir happy path, sin datos, datos desactualizados, falla de servicio externo y permisos insuficientes.",
            "GAP-METRIC-SOURCE": "El baseline sale del reporte semanal de operaciones, owner Support Ops; el target es detectar colas de alto riesgo antes de las 9:30 AM.",
            "GAP-TECH-DATA-SOURCE": "Reutilizar `GET /queues`; modificarlo para incluir `slaRisk`. La fuente de verdad de riesgo es Case Management, owner Operations Platform.",
            "GAP-TECH-NFR": "La respuesta del dashboard debe mantenerse debajo de 2 segundos p95. Loguear fallas de cálculo y exponer métricas de datos faltantes/desactualizados.",
            "GAP-DESIGN-FLOW": "El indicador aparece en la lista del dashboard diario. Los usuarios entran por Home > Operaciones > Colas diarias y deciden qué cola revisar primero.",
            "GAP-DESIGN-STATES": "Mostrar skeleton durante carga, estado neutral sin colas, warning para datos desactualizados y error genérico existente ante fallas de servicio.",
            "GAP-DESIGN-PROTOTYPE-INPUT": "Prototipar la lista del dashboard con estados normal, alto riesgo, datos desactualizados y vacío para validar escaneabilidad con analistas.",
            "GAP-PRODUCT-ASIS-TOBE": "Hoy los analistas abren cada cola para inferir riesgo. To-be: la lista muestra riesgo directamente para priorizar antes de abrir detalle.",
            "GAP-BUSINESS-RULES": "Una cola es de alto riesgo cuando más de 10 casos están a menos de 30 minutos de breach de SLA o cuando cualquier caso ya está vencido.",
            "GAP-FRONTEND-SURFACE": "Superficie afectada: dashboard diario de Operaciones. Agregar badge de riesgo, preservar filtros existentes, bindear `slaRisk` y trackear `risk_badge_clicked`.",
            "GAP-BACKEND-SURFACE": "Backend enriquece summaries de cola con SLA risk, maneja indisponibilidad de Case Management como `riskUnknown` y no persiste riesgo localmente.",
            "GAP-TECH-DEEP-DIVE-INPUT": "Tecnología debe revisar `ops-dashboard-web`, `queue-summary-api` y documentación de integración de Case Management antes de proponer arquitectura.",
            "GAP-GOVERNANCE-CONSTRAINTS": "No agregar PII en la lista del dashboard. Logs de auditoría no deben incluir nombres de clientes ni números de documento.",
            "GAP-DELIVERY-READINESS": "Dependencia: Case Management debe exponer umbral de SLA antes del 15 de junio. Rollout con feature flag primero para supervisores de Operaciones.",
            "GAP-BACKLOG-SLICING-READINESS": "Primer slice: usuario autorizado ve un caso de alto riesgo con datos vigentes. Diferir exportacion, bulk actions y reglas avanzadas. No dividir en crear boton/endpoint/tabla porque ninguna parte sola valida valor.",
            "GAP-BACKLOG-ENABLERS": "Enabler valido: soporte backend compartido para consultas de riesgo y permisos por rol del flujo, con validacion objetiva. No enabler: 'asegurar que una herramienta interna sea accesible'; eso es precondicion operacional.",
            "GAP-QUALITY-HANDOFF": "Tests críticos: alto riesgo, riesgo normal, datos de fuente desactualizados, permisos faltantes, cola vacía y regresión de filtros existentes.",
        }
        return examples.get(gap_id, "Una respuesta útil indica decisión, owner/fuente, evidencia y si está confirmado o pendiente.")
    examples = {
        "GAP-OBJECTIVE": "The goal is to reduce manual review time for operations analysts by making high-risk cases visible before the daily standup.",
        "GAP-USERS": "Primary users are operations analysts. Supervisors only review summary status. The compliance team consumes audit evidence but does not use the screen.",
        "GAP-SCOPE": "In scope: daily dashboard risk indicator. Out of scope: historical reporting, billing, and workforce scheduling. Existing filters must keep working.",
        "GAP-ACCEPTANCE": "Given a queue has cases above the SLA threshold, when the dashboard loads, then the queue is marked as high risk and the analyst can identify it without opening case details.",
        "GAP-QUALITY": "QA should cover happy path, no data, stale data, external service failure, and permission denied scenarios.",
        "GAP-METRIC-SOURCE": "Baseline comes from the weekly operations report owned by Support Ops; target is to detect high-risk queues before 9:30 AM daily.",
        "GAP-TECH-DATA-SOURCE": "Reuse `GET /queues`; modify it to include `slaRisk`. Risk source of truth is the Case Management service owned by Operations Platform.",
        "GAP-TECH-NFR": "Dashboard response should stay under 2 seconds p95. Log risk-calculation failures and expose metrics for missing/stale source data.",
        "GAP-DESIGN-FLOW": "The indicator appears on the daily dashboard list. Users enter from Home > Operations > Daily queues and decide which queue to inspect first.",
        "GAP-DESIGN-STATES": "Show skeleton while loading, neutral state when there are no queues, warning state for stale data, and existing generic error for service failures.",
        "GAP-DESIGN-PROTOTYPE-INPUT": "Prototype the dashboard list with normal, high-risk, stale-data, and empty states to validate scanability with analysts.",
        "GAP-PRODUCT-ASIS-TOBE": "Today analysts open each queue to infer risk. To-be: the list shows risk directly so they can prioritize before opening details.",
        "GAP-BUSINESS-RULES": "A queue is high risk when more than 10 cases are within 30 minutes of SLA breach or any case is already breached.",
        "GAP-FRONTEND-SURFACE": "Affected surface is the Daily Operations dashboard. Add risk badge, preserve existing filters, bind to `slaRisk`, and track `risk_badge_clicked`.",
        "GAP-BACKEND-SURFACE": "Backend enriches queue summaries with SLA risk, handles unavailable Case Management data as `riskUnknown`, and does not persist risk locally.",
        "GAP-TECH-DEEP-DIVE-INPUT": "Technology should inspect `ops-dashboard-web`, `queue-summary-api`, and Case Management integration docs before proposing architecture.",
        "GAP-GOVERNANCE-CONSTRAINTS": "No PII should be added to the dashboard list. Audit logs must not include customer names or document numbers.",
        "GAP-DELIVERY-READINESS": "Dependency: Case Management team must expose SLA threshold by June 15. Rollout behind feature flag for Operations supervisors first.",
        "GAP-BACKLOG-SLICING-READINESS": "First slice: authorized user sees one high-risk case with current data. Defer export, bulk actions, and advanced rules. Do not split into button/endpoint/table because none validates value alone.",
        "GAP-BACKLOG-ENABLERS": "Valid enabler: shared backend support for risk queries and role permissions for the flow, with objective validation. Not an enabler: 'make an internal tool accessible'; that is an operational precondition.",
        "GAP-QUALITY-HANDOFF": "Critical tests: high risk, normal risk, stale source data, missing permissions, empty queue, and regression of existing filters.",
    }
    return examples.get(gap_id, "A useful answer names the decision, owner/source, evidence, and whether the answer is confirmed or pending.")


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
            ("GAP-PRODUCT-ASIS-TOBE", "GAP-BUSINESS-RULES", "GAP-DELIVERY-READINESS", "GAP-BACKLOG-SLICING-READINESS"),
            "Is the as-is/to-be delta, rule set, dependency map, and rollout path clear enough to shape PRD and backlog?",
        ),
        lens_review(
            "technical",
            "Tech Lead",
            text,
            context.get("technical", ""),
            gaps,
            ("GAP-TECH-DATA-SOURCE", "GAP-TECH-NFR", "GAP-FRONTEND-SURFACE", "GAP-BACKEND-SURFACE", "GAP-TECH-DEEP-DIVE-INPUT", "GAP-BACKLOG-ENABLERS"),
            "Which systems, endpoint/event surfaces, create/modify/reuse decisions, security, observability, or ownership constraints are required before Technology can deepen the design?",
        ),
        lens_review(
            "design",
            "UX/UI Designer",
            text,
            context.get("design", ""),
            gaps,
            ("GAP-DESIGN-FLOW", "GAP-DESIGN-STATES", "GAP-DESIGN-PROTOTYPE-INPUT"),
            "Which journey, screens, states, error/empty/loading behavior, or accessibility requirements are unresolved?",
        ),
        lens_review(
            "quality",
            "Quality Lead",
            text,
            context.get("quality", ""),
            gaps,
            ("GAP-ACCEPTANCE", "GAP-QUALITY", "GAP-QUALITY-HANDOFF"),
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
            "mature_signal": "Systems, APIs/events, create/modify/reuse decisions, ownership, source of truth, and critical fields are clear enough for Technology to produce detailed context packs.",
            "lens": "Technology",
            "gap_when_missing": "GAP-TECH-DATA-SOURCE",
        },
        {
            "area": "Technology deep-dive readiness",
            "mature_signal": "Repositories or components to inspect, architecture questions, endpoint/event inventory, dependencies, and technical risks are explicit enough for a technical context pack.",
            "lens": "Technology",
            "gap_when_missing": "GAP-TECH-DEEP-DIVE-INPUT",
        },
        {
            "area": "Frontend implementation readiness",
            "mature_signal": "Affected surfaces, roles, UI states, validations, copy, analytics/telemetry needs, and API binding expectations are visible.",
            "lens": "Frontend/Design",
            "gap_when_missing": "GAP-FRONTEND-SURFACE",
        },
        {
            "area": "Backend implementation readiness",
            "mature_signal": "Capabilities, business rules, integrations, persistence/source-of-truth needs, exposed contracts, observability, and failure behavior are visible.",
            "lens": "Backend/Technology",
            "gap_when_missing": "GAP-BACKEND-SURFACE",
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
            "area": "Design prototype readiness",
            "mature_signal": "The brief states what Design should validate or prototype, including target users, journey moments, decisions, states, and visual evidence references.",
            "lens": "Design",
            "gap_when_missing": "GAP-DESIGN-PROTOTYPE-INPUT",
        },
        {
            "area": "Acceptance and quality",
            "mature_signal": "Happy path, negative paths, stale/missing data, test data, and acceptance criteria are testable.",
            "lens": "Quality",
            "gap_when_missing": "GAP-ACCEPTANCE or GAP-QUALITY",
        },
        {
            "area": "Quality handoff readiness",
            "mature_signal": "Critical flows, edge cases, regression areas, test data needs, and evidence expectations are explicit enough for QA to deepen coverage.",
            "lens": "Quality",
            "gap_when_missing": "GAP-QUALITY-HANDOFF",
        },
        {
            "area": "Delivery readiness",
            "mature_signal": "Dependencies, environments, pending approvals, timing, rollout, and open uncertainties are tracked.",
            "lens": "Delivery/Product",
            "gap_when_missing": "GAP-DELIVERY-READINESS",
        },
        {
            "area": "Backlog slicing readiness",
            "mature_signal": "First value slice, meaningful story boundary, deferred variants/rules, and valid cross-cutting enablers are explicit enough to avoid micro-stories or loose infrastructure work.",
            "lens": "Product/Technology/Quality",
            "gap_when_missing": "GAP-BACKLOG-SLICING-READINESS or GAP-BACKLOG-ENABLERS",
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


def question_for_gap(gap_id: str, language: str = "en") -> str:
    if language == "es":
        questions = {
            "GAP-OBJECTIVE": "¿Qué resultado de negocio debería lograr este requerimiento?",
            "GAP-USERS": "¿Qué usuarios, personas o roles están dentro del alcance?",
            "GAP-SCOPE": "¿Qué está explícitamente dentro y fuera del alcance?",
            "GAP-ACCEPTANCE": "¿Qué condiciones observables demuestran que el requerimiento está terminado?",
            "GAP-QUALITY": "¿Qué expectativas de calidad, testeabilidad, riesgo o compliance aplican?",
            "GAP-METRIC-SOURCE": "¿Cuál es la fuente o baseline de la métrica cuantitativa?",
            "GAP-TECH-DATA-SOURCE": "¿Qué sistemas, endpoints, eventos, decisiones de crear/modificar/reutilizar, owners, fuente de verdad y campos críticos están involucrados?",
            "GAP-TECH-NFR": "¿Qué restricciones de seguridad, performance, observabilidad, disponibilidad u operación aplican?",
            "GAP-DESIGN-FLOW": "¿Qué journey, pantallas, flujos, copy o cambios de interacción están dentro del alcance?",
            "GAP-DESIGN-STATES": "¿Qué estados de loading, empty, error, recuperación y accesibilidad deben contemplarse?",
            "GAP-DESIGN-PROTOTYPE-INPUT": "¿Qué debería prototipar o validar Diseño, y qué usuarios, momentos del journey, estados y referencias visuales deberían guiarlo?",
            "GAP-PRODUCT-ASIS-TOBE": "¿Cuál es el proceso actual, el proceso objetivo y el delta exacto entre ambos?",
            "GAP-BUSINESS-RULES": "¿Qué reglas, excepciones, validaciones, fallbacks o exclusiones gobiernan el comportamiento?",
            "GAP-FRONTEND-SURFACE": "¿Qué superficies frontend, roles, estados, validaciones, copy, analytics y bindings de API se ven afectados?",
            "GAP-BACKEND-SURFACE": "¿Qué capacidades backend, integraciones, reglas, persistencia/source of truth, contratos y comportamiento ante fallas se ven afectados?",
            "GAP-TECH-DEEP-DIVE-INPUT": "¿Qué repositorios/componentes, preguntas de arquitectura, inventario de endpoints/eventos, dependencias y riesgos debería inspeccionar Tecnología?",
            "GAP-GOVERNANCE-CONSTRAINTS": "¿Qué restricciones de seguridad, privacidad, compliance, auditoría u operación deben respetarse?",
            "GAP-DELIVERY-READINESS": "¿Qué dependencias, ambientes, aprobaciones, owners, fechas o restricciones de rollout quedan pendientes?",
            "GAP-BACKLOG-SLICING-READINESS": "¿Cuál es el primer slice de valor observable, qué variantes o reglas pueden diferirse y dónde cortar más pequeño dejaría de aportar valor?",
            "GAP-BACKLOG-ENABLERS": "¿Qué enablers transversales de implementación frontend/backend o arquitectura deben construirse antes para soportar esta funcionalidad, qué scope habilitan y cómo se distinguen de una precondición operacional genérica?",
            "GAP-QUALITY-HANDOFF": "¿Qué flujos críticos, casos borde, datos de prueba, riesgos de regresión y evidencia esperada debería usar Calidad para profundizar cobertura?",
        }
        return questions.get(gap_id, "¿Qué información confirmada resuelve esta incertidumbre?")
    questions = {
        "GAP-OBJECTIVE": "What business outcome should this requirement achieve?",
        "GAP-USERS": "Which users, personas, or roles are in scope?",
        "GAP-SCOPE": "What is explicitly in scope and out of scope?",
        "GAP-ACCEPTANCE": "What observable conditions prove the requirement is done?",
        "GAP-QUALITY": "What quality, testability, risk, or compliance expectations apply?",
        "GAP-METRIC-SOURCE": "What is the source or baseline for the quantitative metric?",
        "GAP-TECH-DATA-SOURCE": "Which systems, endpoints, events, create/modify/reuse decisions, owners, source-of-truth data, and critical fields are involved?",
        "GAP-TECH-NFR": "What security, performance, observability, availability, or operational constraints apply?",
        "GAP-DESIGN-FLOW": "Which user journey, screens, flows, copy, or interaction changes are in scope?",
        "GAP-DESIGN-STATES": "What loading, empty, error, recovery, and accessibility states must be handled?",
        "GAP-DESIGN-PROTOTYPE-INPUT": "What should Design prototype or validate, and which users, journey moments, states, and visual references should guide it?",
        "GAP-PRODUCT-ASIS-TOBE": "What is the current process, target process, and exact delta between them?",
        "GAP-BUSINESS-RULES": "Which rules, exceptions, validations, fallbacks, or exclusions govern the behavior?",
        "GAP-FRONTEND-SURFACE": "Which frontend surfaces, roles, states, validations, copy, analytics, and API binding needs are affected?",
        "GAP-BACKEND-SURFACE": "Which backend capabilities, integrations, rules, persistence/source-of-truth needs, contracts, and failure behaviors are affected?",
        "GAP-TECH-DEEP-DIVE-INPUT": "Which repositories/components, architecture questions, endpoint/event inventory, dependencies, and technical risks should Technology inspect?",
        "GAP-GOVERNANCE-CONSTRAINTS": "Which security, privacy, compliance, audit, or operational restrictions must be respected?",
        "GAP-DELIVERY-READINESS": "Which dependencies, environments, approvals, owners, dates, or rollout constraints remain pending?",
        "GAP-BACKLOG-SLICING-READINESS": "What is the first observable value slice, which variants or rules can be deferred, and where would a smaller split stop producing value?",
        "GAP-BACKLOG-ENABLERS": "Which frontend/backend or architecture implementation enablers must be built in advance to support this functionality, what scope do they enable, and how are they different from a generic operational precondition?",
        "GAP-QUALITY-HANDOFF": "Which critical flows, edge cases, test data, regression risks, and evidence expectations should Quality use for deeper coverage?",
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
