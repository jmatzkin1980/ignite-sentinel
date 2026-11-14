from __future__ import annotations

from .errors import InputError  # IMP-302: typed errors

import re
from pathlib import Path
from typing import Any

from .discovery import candidate_options_markdown, expected_format_for_gap, parse_gap_rows, unblocks_for_gap
from .lens_registry import lens_checks_for_lens
from .memory import ContextBroker
from .core.graph import add_edge, add_node, load_graph, nodes_by_type, save_graph
from .workspace import read_json, state_path, update_state, utc_now, workspace_path, write_json
from .core.io import write_text

DOMAINS = {"technology", "design", "quality", "frontend", "backend"}


def lens_checks_section(domain: str, language: str) -> str:
    """Render the domain lens's checks from the declarative source (IMP-033).

    Reads the same ``sentinel/lenses/*.json`` the discovery engine uses, so a
    check added to a lens file shows up here with no Python change.
    """
    lens = domain_for_node(domain)
    checks = lens_checks_for_lens(lens)
    if not checks:
        return "- (sin checks definidos para este lente)" if language == "es" else "- (no checks defined for this lens)"
    if language == "es":
        why_label, unblocks_label, format_label = "Por qué importa", "Desbloquea", "Formato esperado"
    else:
        why_label, unblocks_label, format_label = "Why it matters", "Unblocks", "Expected format"
    lines = []
    for check in checks:
        gap_id = check["id"]
        why = check.get("why")
        lines.append(f"- `{gap_id}` ({check['severity']}): {check['description']}")
        if why:
            lines.append(f"  - {why_label}: {why}")
        lines.append(f"  - {unblocks_label}: {unblocks_for_gap(gap_id, language)}")
        lines.append(f"  - {format_label}: {expected_format_for_gap(gap_id, language)}")
    return "\n".join(lines)


def generate_context_request(project_id: str, domain: str) -> dict[str, str]:
    domain = domain.lower()
    if domain not in DOMAINS:
        raise InputError(f"Unsupported context request domain: {domain}")
    base = workspace_path(project_id)
    brief_path = base / "02_requirements" / "project-brief.md"
    gaps_path = base / "01_discovery" / "gaps.md"
    request_dir = base / "08_context_packs" / "requests"
    request_dir.mkdir(parents=True, exist_ok=True)
    path = request_dir / f"{domain}_context_request.md"
    language = project_language(project_id)
    write_text(path, render_context_request(project_id, domain, language, brief_path, gaps_path))
    previous = next((node for node in nodes_by_type(project_id, "context_request") if node.get("path") == path.as_posix()), None)
    request_id = add_node(project_id, "CTX", "context_request", path, f"{domain.title()} context request", domain=domain_for_node(domain))
    if previous is not None and str(previous.get("status") or "active") != "active":
        # IMP-294: regenerating a request reopens it, and the lifecycle says so.
        _record_transition(project_id, request_id, str(previous.get("status")), "active", "context-request (regenerated)")
    for brief in nodes_by_type(project_id, "project_brief"):
        add_edge(project_id, brief["id"], request_id, "requests_domain_context")
    for gap in nodes_by_type(project_id, "gap_report"):
        add_edge(project_id, gap["id"], request_id, "informs")
    ContextBroker(project_id).index_artifact(
        request_id,
        "context_request",
        path,
        path.read_text(encoding="utf-8"),
        domain=domain_for_node(domain),
        trace_ids=[request_id],
        metadata={"request_domain": domain},
    )
    update_state(project_id, phase="context_request_generated", last_context_request=request_id)
    return {"project_id": project_id, "domain": domain, "context_request_id": request_id, "path": str(path)}


# --- IMP-294: CTX-NNN lifecycle ------------------------------------------------

CTX_STATES = ("active", "answered", "closed", "obsolete")
CTX_TRANSITIONS = {
    "active": ("answered", "obsolete"),
    "answered": ("closed", "active", "obsolete"),
    "closed": (),
    "obsolete": (),
}
CTX_REF_RE = re.compile(r"(?<![\w-])(CTX-[0-9]{3,})(?![\w-])")
LIFECYCLE_FILE = "08_context_packs/requests/ctx_lifecycle.json"


def _lifecycle_path(project_id: str) -> Path:
    return workspace_path(project_id) / LIFECYCLE_FILE


def load_ctx_lifecycle(project_id: str) -> dict[str, dict[str, Any]]:
    data = read_json(_lifecycle_path(project_id), {})
    return dict(data.get("requests", {})) if isinstance(data, dict) else {}


def _context_nodes(project_id: str) -> dict[str, dict[str, Any]]:
    return {str(node["id"]): node for node in nodes_by_type(project_id, "context_request")}


def _record_transition(project_id: str, request_id: str, old: str, new: str, via: str, reason: str = "") -> dict[str, Any]:
    graph = load_graph(project_id)
    for node in graph.get("nodes", []):
        if node.get("id") == request_id:
            node["status"] = new
    save_graph(project_id, graph)
    lifecycle = load_ctx_lifecycle(project_id)
    entry = lifecycle.setdefault(request_id, {"status": old, "history": []})
    entry["status"] = new
    entry["history"].append({"from": old, "to": new, "via": via, "reason": reason, "at": utc_now()})
    write_json(_lifecycle_path(project_id), {"version": 1, "requests": dict(sorted(lifecycle.items()))})
    return {"context_request_id": request_id, "from": old, "to": new, "via": via, "reason": reason}


def transition_context_request(project_id: str, request_id: str, status: str, reason: str = "", via: str = "context-request") -> dict[str, Any]:
    """Move a CTX along active -> answered -> closed (or obsolete). Closed and obsolete are final."""
    if status not in CTX_STATES:
        raise ValueError(f"--status must be one of {', '.join(CTX_STATES)}.")
    node = _context_nodes(project_id).get(request_id.strip().upper())
    if node is None:
        raise InputError(f"{request_id} is not a context request of {project_id}.")
    current = str(node.get("status") or "active")
    if current not in CTX_STATES:
        current = "active"
    if status not in CTX_TRANSITIONS[current]:
        allowed = ", ".join(CTX_TRANSITIONS[current]) or "none, it is final"
        raise ValueError(f"{node['id']} is {current}; it can move to: {allowed}.")
    if status in {"closed", "obsolete"} and not reason.strip():
        raise ValueError(f"--status {status} needs --reason.")
    return _record_transition(project_id, str(node["id"]), current, status, via, reason.strip())


def answer_cited_context_requests(project_id: str, text: str, change_id: str) -> list[str]:
    """/sync: an active CTX that the synced text cites becomes answered. Nothing else moves."""
    nodes = _context_nodes(project_id)
    answered: list[str] = []
    for request_id in dict.fromkeys(CTX_REF_RE.findall(text)):
        node = nodes.get(request_id)
        if node is not None and str(node.get("status") or "active") == "active":
            _record_transition(project_id, request_id, "active", "answered", f"sync {change_id}")
            answered.append(request_id)
    return answered


def context_request_summary(project_id: str) -> dict[str, int]:
    counts = {state: 0 for state in CTX_STATES}
    for node in _context_nodes(project_id).values():
        status = str(node.get("status") or "active")
        counts[status if status in counts else "active"] += 1
    return counts


def render_context_request(project_id: str, domain: str, language: str, brief_path: Path, gaps_path: Path) -> str:
    prompts = prompts_for(domain, language)
    title = prompts["title"]
    lens_checks = lens_checks_section(domain, language)
    gap_candidates = domain_gap_candidate_options_section(domain, language, gaps_path)
    if language == "es":
        return f"""---
when_to_read: al preparar o revisar el contexto de dominio {domain} de {project_id}
---
# {title} - {project_id}

## Fuente base

- Project brief: `{brief_path.as_posix()}`
- Gaps: `{gaps_path.as_posix()}`

## Objetivo

{prompts['goal']}

## Preguntas a responder

{prompts['questions']}
{gap_candidates}

## Checks del lente a cubrir

{lens_checks}

## Entregables esperados

{prompts['deliverables']}

## Declaración opcional de perfil

Si conocés explícitamente el perfil principal del respondente, agregá frontmatter `respondent_profile: technical` o `respondent_profile: business` en el archivo de contexto entregado. No lo declares si solo se deduce por carpeta, rol, título o texto libre.

## Restricciones

- Mantener source of truth en archivos versionables del workspace.
- No usar MCP remoto, servicios externos ni embeddings externos.
- Marcar cualquier supuesto como `PENDING` o `INFERRED`.
- Cada archivo entregado declara `when_to_read:` en su frontmatter (cuándo debe leerlo un agente).
- Cada hecho tiene un único dueño (`Dueño: <una persona o rol>`).
"""
    return f"""---
when_to_read: when preparing or reviewing the {domain} domain context of {project_id}
---
# {title} - {project_id}

## Base Source

- Project brief: `{brief_path.as_posix()}`
- Gaps: `{gaps_path.as_posix()}`

## Goal

{prompts['goal']}

## Questions To Answer

{prompts['questions']}
{gap_candidates}

## Lens Checks To Cover

{lens_checks}

## Expected Deliverables

{prompts['deliverables']}

## Optional Profile Declaration

When the main respondent profile is explicitly known, add `respondent_profile: technical` or `respondent_profile: business` frontmatter to the delivered context file. Do not declare it when it is only implied by folder, role, title, or free text.

## Constraints

- Keep source of truth in versionable workspace files.
- Do not use remote MCP, external services, or external embeddings.
- Mark every assumption as `PENDING` or `INFERRED`.
- Every delivered file declares `when_to_read:` in its frontmatter (when an agent should read it).
- Every fact has a single owner (`Owner: <one person or role>`).
"""


def domain_gap_candidate_options_section(domain: str, language: str, gaps_path: Path) -> str:
    if not gaps_path.exists():
        return ""
    lens = domain_for_node(domain)
    sections: list[str] = []
    for gap in parse_gap_rows(gaps_path.read_text(encoding="utf-8")):
        if gap.get("status", "OPEN") == "CLOSED":
            continue
        if gap.get("lens") != lens:
            continue
        options = candidate_options_markdown(gap, language)
        if options:
            sections.append(f"### {gap['id']}\n\n{options}")
    if not sections:
        return ""
    heading = "## Opciones candidatas citadas para gaps abiertos" if language == "es" else "## Cited Candidate Options For Open Gaps"
    return "\n\n" + heading + "\n\n" + "\n\n".join(sections)


def prompts_for(domain: str, language: str) -> dict[str, str]:
    spanish = language == "es"
    data_es = {
        "technology": (
            "Pedido de Contexto Técnico",
            "Profundizar arquitectura, repositorios/componentes, endpoints/eventos, source of truth, dependencias y riesgos.",
            "- ¿Qué repositorios o componentes deben analizarse?\n- ¿Qué endpoints/eventos se reutilizan, crean, modifican o deprecian?\n- ¿Qué fuente de verdad y owners aplican?\n- ¿Qué riesgos técnicos, NFRs y restricciones operativas existen?",
            "- Diagrama o explicación de arquitectura.\n- Inventario de endpoints/eventos.\n- Riesgos, dependencias y decisiones técnicas.\n- Recomendaciones para frontend/backend downstream.",
        ),
        "design": (
            "Pedido de Contexto de Diseño",
            "Profundizar journeys, pantallas, estados, prototipo y decisiones de interacción.",
            "- ¿Qué usuarios y momentos del journey se deben cubrir?\n- ¿Qué pantallas, estados y copy cambian?\n- ¿Qué debe validar el prototipo?\n- ¿Qué referencias visuales o restricciones de design system aplican?",
            "- Flujo de usuario.\n- Prototipo o wireframe esperado.\n- Estados UX y criterios de validación.\n- Riesgos de usabilidad/accesibilidad.",
        ),
        "quality": (
            "Pedido de Contexto de Calidad",
            "Profundizar cobertura, datos de prueba, riesgos de regresión y evidencia requerida.",
            "- ¿Qué flujos críticos y negativos deben probarse?\n- ¿Qué datos, roles y ambientes se necesitan?\n- ¿Qué regresiones son sensibles?\n- ¿Qué evidencia valida el requerimiento?",
            "- Matriz de escenarios.\n- Datos de prueba.\n- Riesgos y estrategia de automatización.\n- Evidencia requerida.",
        ),
        "frontend": (
            "Pedido de Contexto Frontend",
            "Profundizar superficies UI, estados, roles, bindings de API, validaciones y analytics.",
            "- ¿Qué superficies y componentes cambian?\n- ¿Qué estados, validaciones y copy deben implementarse?\n- ¿Qué API bindings y eventos analytics aplican?\n- ¿Qué comportamiento actual no debe romperse?",
            "- Mapa de superficies/componentes.\n- Contrato de datos consumidos.\n- Estados UI y estrategia de errores.\n- Riesgos de regresión frontend.",
        ),
        "backend": (
            "Pedido de Contexto Backend",
            "Profundizar capacidades, reglas, integraciones, persistencia, contratos y fallas.",
            "- ¿Qué capacidades y reglas debe resolver backend?\n- ¿Qué integraciones y source of truth aplican?\n- ¿Qué contratos se exponen o preservan?\n- ¿Qué comportamiento ante fallas se requiere?",
            "- Diseño de servicios/capacidades.\n- Integraciones y contratos.\n- Persistencia/source of truth.\n- Observabilidad y estrategia de fallas.",
        ),
    }
    if spanish:
        title, goal, questions, deliverables = data_es[domain]
        return {"title": title, "goal": goal, "questions": questions, "deliverables": deliverables}
    data_en = {
        "technology": (
            "Technology Context Request",
            "Deepen architecture, repositories/components, endpoints/events, source of truth, dependencies, and risks.",
            "- Which repositories or components must be analyzed?\n- Which endpoints/events are reused, created, modified, or deprecated?\n- What source of truth and owners apply?\n- What technical risks, NFRs, and operational constraints exist?",
            "- Architecture diagram or explanation.\n- Endpoint/event inventory.\n- Technical risks, dependencies, and decisions.\n- Recommendations for frontend/backend downstream work.",
        ),
        "design": (
            "Design Context Request",
            "Deepen journeys, screens, states, prototype scope, and interaction decisions.",
            "- Which users and journey moments must be covered?\n- Which screens, states, and copy change?\n- What should the prototype validate?\n- Which visual references or design-system constraints apply?",
            "- User flow.\n- Expected prototype or wireframe.\n- UX states and validation criteria.\n- Usability/accessibility risks.",
        ),
        "quality": (
            "Quality Context Request",
            "Deepen coverage, test data, regression risks, and required evidence.",
            "- Which critical and negative flows must be tested?\n- Which data, roles, and environments are needed?\n- Which regressions are sensitive?\n- What evidence validates the requirement?",
            "- Scenario matrix.\n- Test data.\n- Risks and automation strategy.\n- Required evidence.",
        ),
        "frontend": (
            "Frontend Context Request",
            "Deepen UI surfaces, states, roles, API bindings, validations, and analytics.",
            "- Which surfaces and components change?\n- Which states, validations, and copy must be implemented?\n- Which API bindings and analytics events apply?\n- What current behavior must remain unchanged?",
            "- Surface/component map.\n- Consumed data contract.\n- UI states and error strategy.\n- Frontend regression risks.",
        ),
        "backend": (
            "Backend Context Request",
            "Deepen capabilities, rules, integrations, persistence, contracts, and failure behavior.",
            "- Which capabilities and rules must backend solve?\n- Which integrations and source of truth apply?\n- Which contracts are exposed or preserved?\n- What failure behavior is required?",
            "- Service/capability design.\n- Integrations and contracts.\n- Persistence/source of truth.\n- Observability and failure strategy.",
        ),
    }
    title, goal, questions, deliverables = data_en[domain]
    return {
        "title": title,
        "goal": goal,
        "questions": questions,
        "deliverables": deliverables,
    }


def domain_for_node(domain: str) -> str:
    if domain in {"technology", "backend", "frontend"}:
        return "technical"
    return domain


def project_language(project_id: str) -> str:
    state = read_json(state_path(project_id), {})
    return state.get("project_language", "en") if state.get("project_language") in {"es", "en"} else "en"
