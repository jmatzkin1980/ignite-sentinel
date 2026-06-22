from __future__ import annotations

from pathlib import Path

from .discovery import candidate_options_markdown, expected_format_for_gap, parse_gap_rows, unblocks_for_gap
from .lens_registry import lens_checks_for_lens
from .memory import ContextBroker
from .core.graph import add_edge, add_node, nodes_by_type
from .workspace import read_json, state_path, update_state, workspace_path

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
        raise RuntimeError(f"Unsupported context request domain: {domain}")
    base = workspace_path(project_id)
    brief_path = base / "02_requirements" / "project-brief.md"
    gaps_path = base / "01_discovery" / "gaps.md"
    request_dir = base / "08_context_packs" / "requests"
    request_dir.mkdir(parents=True, exist_ok=True)
    path = request_dir / f"{domain}_context_request.md"
    language = project_language(project_id)
    path.write_text(render_context_request(project_id, domain, language, brief_path, gaps_path), encoding="utf-8")
    request_id = add_node(project_id, "CTX", "context_request", path, f"{domain.title()} context request", domain=domain_for_node(domain))
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


def render_context_request(project_id: str, domain: str, language: str, brief_path: Path, gaps_path: Path) -> str:
    prompts = prompts_for(domain, language)
    title = prompts["title"]
    lens_checks = lens_checks_section(domain, language)
    gap_candidates = domain_gap_candidate_options_section(domain, language, gaps_path)
    if language == "es":
        return f"""# {title} - {project_id}

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

## Restricciones

- Mantener source of truth en archivos versionables del workspace.
- No usar MCP remoto, servicios externos ni embeddings externos.
- Marcar cualquier supuesto como `PENDING` o `INFERRED`.
"""
    return f"""# {title} - {project_id}

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

## Constraints

- Keep source of truth in versionable workspace files.
- Do not use remote MCP, external services, or external embeddings.
- Mark every assumption as `PENDING` or `INFERRED`.
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
