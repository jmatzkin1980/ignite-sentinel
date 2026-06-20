from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import re
from typing import Any

from ..memory import ContextBroker
from ..retrieval_plans import compose_plan_query, load_retrieval_plan
from ..slicing_model import load_slicing_model
from ..workspace import workspace_path
from .backlog import build_agent_execution_contract, build_domain_context_coverage, read_plan_for_row
from .specs import read_spec_units


DOMAIN_CONTEXT_FOLDERS = {
    "Product": ("00_raw/00_client_requirement", "00_raw/01_business_context", "00_raw/05_interactions", "07_changes"),
    "Technology": ("00_raw/02_technology_context",),
    "Design": ("00_raw/03_design_context",),
    "Quality": ("00_raw/04_quality_context",),
    "Delivery": ("07_changes",),
}

EARS_REQUIREMENT_ID_RE = re.compile(r"^REQ-EARS-\d{3}$")

BACKLOG_STORY_SEEDS = [
    {
        "title": "Habilitar el flujo principal de valor",
        "type": "value_story",
        "fr": "FR-01",
        "jtbd": "JTBD-001",
        "slicing": "Workflow Step / Happy Path",
        "label": "Basic",
        "description": "Entrega el primer recorrido funcional de punta a punta para que el usuario objetivo obtenga el resultado de negocio confirmado.",
        "goal": "Completar el trabajo principal con informacion suficiente, comportamiento observable y resultado trazable.",
        "benefit": "Permite validar valor temprano sin esperar a que todas las variaciones, reglas finas o optimizaciones esten completas.",
    },
    {
        "title": "Preservar comportamiento existente y compatibilidad",
        "type": "value_story",
        "fr": "FR-02",
        "jtbd": "JTBD-002",
        "slicing": "Rules / Regression Slice",
        "label": "Compatibility",
        "description": "Asegura que el cambio no rompa comportamientos explicitamente marcados como vigentes o fuera del alcance de modificacion.",
        "goal": "Mantener contratos, datos, permisos o experiencias existentes que el brief haya declarado como inalterables.",
        "benefit": "Reduce riesgo de regresion y evita que agentes downstream inventen cambios colaterales.",
    },
    {
        "title": "Conectar datos e integraciones necesarias",
        "type": "value_story",
        "fr": "FR-03",
        "jtbd": "JTBD-002",
        "slicing": "Data / External Dependency",
        "label": "Integration",
        "description": "Cubre las senales de datos, contratos o dependencias externas requeridas para que el flujo sea confiable y verificable.",
        "goal": "Consumir o exponer la fuente de verdad minima para soportar el resultado del usuario.",
        "benefit": "Hace explicitos propietarios, fallas recuperables y limites de datos antes de planificar implementacion.",
    },
    {
        "title": "Cubrir estados de experiencia y validaciones",
        "type": "value_story",
        "fr": "FR-04",
        "jtbd": "JTBD-001",
        "slicing": "Interface / UX State",
        "label": "UX",
        "description": "Define la experiencia usable alrededor del flujo: estados, validaciones, mensajes, permisos y recuperacion.",
        "goal": "Lograr que el usuario entienda que puede hacer, que falta, que fallo y como recuperarse.",
        "benefit": "Mejora la ejecutabilidad para agentes frontend/design y evita historias tecnicas sin comportamiento visible.",
    },
    {
        "title": "Producir evidencia de aceptacion y trazabilidad",
        "type": "value_story",
        "fr": "FR-05",
        "jtbd": "JTBD-003",
        "slicing": "Quality Evidence / Traceability",
        "label": "Quality",
        "description": "Cierra el circuito de aceptacion con criterios, evidencia, pruebas semilla y trazas hacia requerimientos, specs y riesgos.",
        "goal": "Permitir que Quality y agentes de testeo validen el incremento sin reinterpretar el contexto completo.",
        "benefit": "Convierte la velocidad de generacion en trabajo auditable, verificable y seguro de entregar.",
    },
]

ENABLER_CANDIDATES = [
    {
        "key": "auth",
        "tokens": ("auth", "autenticacion", "autenticaciÃ³n", "authorization", "autorizacion", "autorizaciÃ³n", "permission", "permiso", "role", "rol"),
        "title": "Alinear permisos y acceso para los slices del flujo",
        "fr": "NFR-01",
        "jtbd": "JTBD-002",
        "label": "Enabler",
        "slicing": "Cross-Cutting Enabler / Security Boundary",
        "description": "Define el minimo control de acceso necesario para que las historias de valor puedan ejecutarse sin exponer capacidades fuera del rol confirmado.",
        "goal": "habilitar permisos verificables estrictamente vinculados al flujo funcional confirmado",
        "benefit": "las historias de valor pueden implementarse sin duplicar o inventar reglas de acceso",
    },
    {
        "key": "data_foundation",
        "tokens": ("database", "base de datos", "tabla", "table", "query", "queries", "consulta", "persist", "persistencia", "schema", "esquema"),
        "title": "Preparar persistencia y consultas internas del flujo",
        "fr": "FR-03",
        "jtbd": "JTBD-002",
        "label": "Enabler",
        "slicing": "Cross-Cutting Enabler / Data Foundation",
        "description": "Prepara la persistencia o consulta interna minima que varias historias necesitan para entregar el comportamiento funcional confirmado.",
        "goal": "habilitar datos verificables para las historias de valor dependientes",
        "benefit": "los slices funcionales pueden consumir informacion consistente sin convertir cada historia en una tarea de infraestructura",
    },
    {
        "key": "backend_foundation",
        "tokens": ("backend", "service", "servicio", "worker", "job", "orchestration", "orquestacion", "orquestaciÃ³n", "domain layer", "capa de dominio", "use case", "caso de uso"),
        "title": "Preparar soporte backend transversal de la funcionalidad",
        "fr": "FR-03",
        "jtbd": "JTBD-002",
        "label": "Enabler",
        "slicing": "Cross-Cutting Enabler / Backend Foundation",
        "description": "Construye el soporte backend previo que varias funcionalidades del scope necesitan para operar de forma consistente.",
        "goal": "habilitar servicios o logica backend compartida dentro del boundary funcional confirmado",
        "benefit": "las historias de valor pueden implementarse sobre una base tecnica comun sin duplicar comportamiento ni acoplarse a decisiones no confirmadas",
    },
    {
        "key": "frontend_foundation",
        "tokens": ("frontend", "front", "component", "componente", "design system", "sistema de diseno", "sistema de diseÃ±o", "prototype", "prototipo", "screen shell", "layout", "state management", "estado compartido"),
        "title": "Preparar soporte frontend transversal de la funcionalidad",
        "fr": "FR-04",
        "jtbd": "JTBD-001",
        "label": "Enabler",
        "slicing": "Cross-Cutting Enabler / Frontend Foundation",
        "description": "Construye el soporte frontend previo que varias historias del scope necesitan para compartir estructura, estados o patrones de interaccion.",
        "goal": "habilitar componentes, estados o patrones frontend compartidos dentro del boundary funcional confirmado",
        "benefit": "las historias de valor pueden implementarse con consistencia de experiencia sin crear trabajo visual o tecnico generico",
    },
    {
        "key": "integration_contract",
        "tokens": ("api", "endpoint", "event", "evento", "integration", "integracion", "integraciÃ³n", "webhook", "contract", "contrato"),
        "title": "Estabilizar contrato de integracion usado por el flujo",
        "fr": "FR-03",
        "jtbd": "JTBD-002",
        "label": "Enabler",
        "slicing": "Cross-Cutting Enabler / Integration Contract",
        "description": "Alinea el contrato de integracion minimo que desbloquea varias historias de valor dentro del boundary del proyecto.",
        "goal": "dejar disponible un contrato verificable para los slices que dependen de sistemas externos",
        "benefit": "frontend, backend y calidad pueden avanzar contra un contrato acotado y trazable",
    },
    {
        "key": "audit_observability",
        "tokens": ("audit", "auditoria", "auditorÃ­a", "log", "logging", "observability", "observabilidad", "trace", "traza"),
        "title": "Asegurar evidencia transversal de auditoria y observabilidad",
        "fr": "FR-05",
        "jtbd": "JTBD-003",
        "label": "Enabler",
        "slicing": "Cross-Cutting Enabler / Evidence",
        "description": "Define la evidencia transversal minima requerida para aceptar y operar las historias de valor del flujo.",
        "goal": "producir evidencia verificable para las historias funcionales y sus pruebas",
        "benefit": "calidad y operacion pueden validar el incremento sin agregar trazas ad hoc al final",
    },
]


def build_backlog_story_specs(project_id: str, backlog_context: dict[str, Any]) -> list[dict[str, Any]]:
    specs: list[dict[str, Any]] = []
    global_domain_coverage = build_domain_context_coverage(backlog_context)
    backlog_context["domain_context_coverage"] = global_domain_coverage
    spec_units = read_spec_units(project_id)
    slicing_model = load_slicing_model()
    if not spec_units:
        story = pending_backlog_story(global_domain_coverage, backlog_context, slicing_model)
        story["context_pack"] = "08_context_packs/backlog_generation.json"
        story["context_pack_section"] = "sections"
        story["execution_contract"] = build_agent_execution_contract(story, backlog_context, global_domain_coverage)
        return [story]
    for index, unit in enumerate(spec_units, start=1):
        story_id = f"US-{index:03d}"
        story_context = build_story_backlog_context(project_id, story_id, unit, backlog_context)
        domain_coverage = build_domain_context_coverage(story_context)
        backlog_context.setdefault("per_story", {})[story_id] = story_context
        source_context = context_row_for_spec_unit(unit)
        trace = trace_ids_for_spec_unit(unit)
        statement = str(unit.get("statement", "")).strip()
        title = title_for_spec_unit_story(unit)
        goal = goal_for_spec_unit(unit)
        slicing_decision = slicing_decision_for_spec_unit(unit, slicing_model)
        story = {
            "id": story_id,
            "type": "value_story",
            "title": title,
            "label": "Spec Unit",
            "fr": str(unit.get("id", "SPEC-U-PENDING")),
            "jtbd": ", ".join(str(item) for item in unit.get("ears", [])) or "[PENDING INPUT]",
            "slicing": slicing_decision["slicing"],
            "slicing_rationale": slicing_decision["rationale"],
            "description": f"Entrega el comportamiento confirmado en `{unit.get('id', 'SPEC-U-PENDING')}` como un slice vertical trazable.",
            "goal": goal,
            "benefit": "la capacidad confirmada se puede planificar, implementar y validar sin reinterpretar el PRD o inventar alcance",
            "domain": domain_for_spec_unit(unit),
            "trace": trace,
            "context": source_context,
            "domain_coverage": domain_coverage,
            "context_pack": "08_context_packs/backlog_generation.json",
            "context_pack_section": f"per_story.{story_id}",
            "dependencies": [],
            "enables": [],
            "acceptance": acceptance_criteria_for_spec_unit_story(story_id, unit, statement),
            "source_unit": str(unit.get("id", "")),
        }
        story["execution_contract"] = build_agent_execution_contract(story, story_context, domain_coverage)
        specs.append(story)
    return specs


def build_story_backlog_context(
    project_id: str,
    story_id: str,
    unit: dict[str, Any],
    backlog_context: dict[str, Any],
) -> dict[str, Any]:
    broker = ContextBroker(project_id)
    plan = load_retrieval_plan("backlog_generation")
    unit_context = spec_unit_query_context(story_id, unit)
    sections: dict[str, Any] = {}
    for section, retrieval in plan["sections"].items():
        domain = retrieval.get("domain")
        filters = dict(retrieval.get("filters", {}))
        query = compose_plan_query(retrieval, unit_context)
        retrieval_domain = "technical" if section == "critical_surfaces" and domain is None else domain
        results = broker.retrieve(
            query,
            "backlog_generation_story",
            limit=int(retrieval["limit"]),
            domain=retrieval_domain,
            artifact_type=filters.get("artifact_type"),
            status=filters.get("status"),
            language=filters.get("language"),
            sensitivity=filters.get("sensitivity"),
            section=filters.get("section"),
            max_chars=int(retrieval["budget_chars"]),
            summary_only=True,
        )
        if not results and retrieval_domain != domain:
            results = broker.retrieve(
                query,
                "backlog_generation_story",
                limit=int(retrieval["limit"]),
                domain=domain,
                artifact_type=filters.get("artifact_type"),
                status=filters.get("status"),
                language=filters.get("language"),
                sensitivity=filters.get("sensitivity"),
                section=filters.get("section"),
                max_chars=int(retrieval["budget_chars"]),
                summary_only=True,
            )
        sections[section] = {
            "query": query,
            "domain": retrieval_domain or "any",
            "filters": filters,
            "limit": retrieval["limit"],
            "budget_chars": retrieval["budget_chars"],
            "summary_chars": retrieval["summary_chars"],
            "lenses": retrieval["lenses"],
            "source_sections": retrieval["source_sections"],
            "results": [
                {
                    "artifact_id": row.get("artifact_id", "N/A"),
                    "artifact_type": row.get("artifact_type", "artifact"),
                    "domain": row.get("domain", "unknown"),
                    "section_path": row.get("section_path", ""),
                    "summary": row.get("summary", row.get("text", ""))[: int(retrieval["summary_chars"])],
                    "why_retrieved": row.get("why_retrieved", ""),
                    "trace_ids": row.get("trace_ids", []),
                    "source_hash": row.get("source_hash", ""),
                    "read_plan": row.get("read_plan", read_plan_for_row(row)),
                }
                for row in results
            ],
        }
    story_context = {
        "story_id": story_id,
        "source_unit": str(unit.get("id", "SPEC-U-PENDING")),
        "workflow": "backlog_generation_story",
        "retrieval_plan": deepcopy(backlog_context.get("retrieval_plan", {})),
        "slicing_model": backlog_context.get("slicing_model", "vertical_value_slices_with_spidr_lawrence_invest"),
        "domain_context_snapshot": deepcopy(
            backlog_context.get("domain_context_snapshot", domain_context_snapshot(project_id))
        ),
        "sections": sections,
    }
    story_context["domain_context_coverage"] = build_domain_context_coverage(story_context)
    return story_context


def spec_unit_query_context(story_id: str, unit: dict[str, Any]) -> str:
    parts = [
        f"Story: {story_id}",
        f"Spec Unit: {unit.get('id', 'SPEC-U-PENDING')}",
        f"Title: {unit.get('title', '')}",
        f"Statement: {unit.get('statement', '')}",
        f"EARS: {', '.join(str(item) for item in unit.get('ears', []))}",
        f"Slicing Pattern: {unit.get('slicing', '')}",
        f"Trace: {', '.join(str(item) for item in unit.get('trace', []))}",
    ]
    return "\n".join(part for part in parts if part.strip())


def pending_backlog_story(
    domain_coverage: list[dict[str, str]],
    backlog_context: dict[str, Any],
    slicing_model: dict[str, Any] | None = None,
) -> dict[str, Any]:
    decision = slicing_fallback_decision(slicing_model or load_slicing_model())
    return {
        "id": "US-001",
        "type": "pending_input_stub",
        "title": "[PENDING INPUT] Confirm evidence-backed Spec Units before slicing backlog",
        "label": "Pending",
        "fr": "[PENDING INPUT]",
        "jtbd": "[PENDING INPUT]",
        "slicing": decision["slicing"],
        "slicing_rationale": "[PENDING INPUT] No confirmed Spec Unit exists, so the fallback slicing pattern is retained until evidence can select a more specific SPIDR/Lawrence path.",
        "description": "No evidence-backed `SPEC-U-*` unit exists yet, so Sentinel preserves the missing input instead of creating placeholder stories.",
        "goal": "confirmar Spec Units funcionales trazables antes de derivar historias de valor",
        "benefit": "el backlog no inventa alcance y el BA puede resolver los gaps que desbloquean slicing",
        "domain": "functional",
        "trace": ["REQ-001", "PRD-001", "SPEC-001", "GAP-PRD-FR-AC", "GAP-BACKLOG-SLICING-READINESS"],
        "context": {
            "need": "spec_units",
            "artifact_id": "03_specs/units/",
            "artifact_type": "pending",
            "summary": "[PENDING INPUT] No evidence-backed Spec Units were found. Resolve functional/EARS evidence and rerun /specs before deriving backlog stories.",
        },
        "domain_coverage": domain_coverage,
        "dependencies": [],
        "enables": [],
        "acceptance": acceptance_criteria_for_pending_story("US-001"),
    }


def title_for_spec_unit_story(unit: dict[str, Any]) -> str:
    unit_id = str(unit.get("id", "SPEC-U-PENDING"))
    statement = str(unit.get("statement", "")).strip()
    if statement:
        cleaned = re.sub(r"^(When|While|If|Where|The system shall|Cuando|Mientras|Si|Donde)\s+", "", statement, flags=re.I)
        cleaned = cleaned.rstrip(".")
        return f"{unit_id} - {safe_cell(cleaned, 96)}"
    raw_title = str(unit.get("title", unit_id)).strip()
    return f"{unit_id} - {safe_cell(raw_title, 96)}"


def goal_for_spec_unit(unit: dict[str, Any]) -> str:
    statement = str(unit.get("statement", "")).strip()
    if statement:
        return statement
    return f"implementar el comportamiento confirmado en {unit.get('id', 'SPEC-U-PENDING')}"


def slicing_decision_for_spec_unit(unit: dict[str, Any], slicing_model: dict[str, Any] | None = None) -> dict[str, str]:
    model = slicing_model or load_slicing_model()
    text = " ".join(str(unit.get(key, "")) for key in ("statement", "pattern", "title")).lower()
    for pattern in model.get("patterns", []):
        tokens = [str(token).lower() for token in pattern.get("tokens", [])]
        if tokens and any(token in text for token in tokens):
            unit_id = str(unit.get("id", "SPEC-U-PENDING"))
            return {
                "slicing": str(pattern["slicing"]),
                "slicing_pattern_id": str(pattern["id"]),
                "rationale": f"{unit_id}: {pattern['rationale']}",
            }
    return slicing_fallback_decision(model, unit)


def slicing_fallback_decision(
    slicing_model: dict[str, Any],
    unit: dict[str, Any] | None = None,
) -> dict[str, str]:
    fallback = next(
        pattern
        for pattern in slicing_model.get("patterns", [])
        if pattern.get("slicing") == "Workflow Step / Happy Path"
    )
    prefix = f"{unit.get('id', 'SPEC-U-PENDING')}: " if unit else ""
    return {
        "slicing": str(fallback["slicing"]),
        "slicing_pattern_id": str(fallback["id"]),
        "rationale": f"{prefix}{fallback['rationale']}",
    }


def domain_for_spec_unit(unit: dict[str, Any]) -> str:
    text = " ".join(str(unit.get(key, "")) for key in ("statement", "pattern", "title")).lower()
    if any(token in text for token in ("api", "integration", "integracion", "data", "database", "contract", "service", "backend")):
        return "technical"
    if any(token in text for token in ("screen", "ui", "ux", "journey", "pantalla", "interfaz", "form")):
        return "design"
    if any(token in text for token in ("test", "quality", "evidence", "regression", "acceptance")):
        return "quality"
    return "functional"


def context_row_for_spec_unit(unit: dict[str, Any]) -> dict[str, str]:
    return {
        "need": "spec_unit",
        "artifact_id": str(unit.get("id", "SPEC-U-PENDING")),
        "artifact_type": "spec_unit",
        "summary": safe_cell(str(unit.get("statement") or unit.get("title") or "[PENDING INPUT]"), 260),
    }


def trace_ids_for_spec_unit(unit: dict[str, Any]) -> list[str]:
    trace = ["REQ-001", "PRD-001", "SPEC-001", str(unit.get("id", "SPEC-U-PENDING"))]
    trace.extend(str(item) for item in unit.get("trace_ids", []) if str(item).strip())
    trace.extend(str(item) for item in unit.get("ears", []) if str(item).strip())
    seen: set[str] = set()
    ordered: list[str] = []
    for item in trace:
        if item and item not in seen:
            ordered.append(item)
            seen.add(item)
    return ordered


def build_cross_cutting_enabler_specs(
    project_id: str,
    value_stories: list[dict[str, Any]],
    backlog_context: dict[str, Any],
) -> list[dict[str, Any]]:
    enabled_value_stories = [story for story in value_stories if story.get("type") == "value_story"]
    if not enabled_value_stories:
        return []
    evidence = cross_cutting_enabler_evidence(project_id)
    if not evidence:
        return []
    domain_coverage = value_stories[0].get("domain_coverage", []) if value_stories else []
    ears_ids = ears_trace_ids(backlog_context)
    specs: list[dict[str, Any]] = []
    start = len(value_stories) + 1
    for candidate in ENABLER_CANDIDATES:
        if not any(token in evidence for token in candidate["tokens"]):
            continue
        story_id = f"US-{start + len(specs):03d}"
        trace = ["REQ-001", *ears_ids, "PRD-001", "SPEC-001", candidate["fr"], candidate["jtbd"]]
        story = {
            "id": story_id,
            "type": "cross_cutting_enabler",
            "title": candidate["title"],
            "label": candidate["label"],
            "fr": candidate["fr"],
            "jtbd": candidate["jtbd"],
            "slicing": candidate["slicing"],
            "description": candidate["description"],
            "goal": candidate["goal"],
            "benefit": candidate["benefit"],
            "domain": "technical",
            "trace": trace,
            "context": {
                "need": "cross_cutting_enabler",
                "artifact_id": "00_raw/*",
                "artifact_type": "source_context",
                "summary": "Concrete source/context terms indicate this enabler supports project functionality across multiple stories, capabilities, or implementation surfaces inside the project boundary.",
            },
            "domain_coverage": domain_coverage,
            "dependencies": [],
            "enables": [story["id"] for story in enabled_value_stories],
            "acceptance": acceptance_criteria_for_enabler(story_id, candidate),
        }
        story["execution_contract"] = build_agent_execution_contract(story, backlog_context, domain_coverage)
        specs.append(story)
    return specs


def cross_cutting_enabler_evidence(project_id: str) -> str:
    base = workspace_path(project_id)
    chunks: list[str] = []
    raw_path = base / "00_raw"
    for item in sorted(raw_path.rglob("*")) if raw_path.exists() else []:
        if item.is_file() and item.suffix.lower() in {".md", ".txt"}:
            chunks.append(item.read_text(encoding="utf-8"))
    text = "\n".join(chunks).lower()
    loose_preconditions = ("herramienta interna accesible", "internal tool accessible", "ambiente disponible", "environment available")
    if any(phrase in text for phrase in loose_preconditions) and not any(
        token in text for candidate in ENABLER_CANDIDATES for token in candidate["tokens"]
    ):
        return ""
    return text


def story_domain(fr_id: str) -> str:
    if fr_id == "FR-03":
        return "technical"
    if fr_id == "FR-04":
        return "design"
    if fr_id == "FR-05":
        return "quality"
    return "functional"


def story_dependencies(index: int) -> list[str]:
    if index == 1:
        return []
    if index in {2, 3, 4}:
        return ["US-001"]
    return ["US-001", "US-002", "US-003", "US-004"]


def context_row_for_story(seed: dict[str, str], backlog_context: dict[str, Any]) -> dict[str, str]:
    preferred = {
        "FR-01": "functional_slicing",
        "FR-02": "quality_risks",
        "FR-03": "technical_dependencies",
        "FR-04": "ux_states",
        "FR-05": "quality_risks",
    }.get(seed["fr"], "epic_value")
    section = backlog_context.get("sections", {}).get(preferred, {})
    results = section.get("results", []) if isinstance(section, dict) else []
    if results:
        top = results[0]
        return {
            "need": preferred,
            "artifact_id": str(top.get("artifact_id", "N/A")),
            "artifact_type": str(top.get("artifact_type", "artifact")),
            "summary": str(top.get("summary", "Context retrieved")),
        }
    return {
        "need": preferred,
        "artifact_id": "N/A",
        "artifact_type": "pending",
        "summary": "[PENDING INPUT] No focused context retrieved for this story. Use /retrieve before implementation.",
    }


def acceptance_criteria_for_spec_unit_story(
    story_id: str,
    unit: dict[str, Any],
    statement: str,
) -> list[dict[str, str]]:
    base = story_id.replace("US-", "AC-")
    unit_id = str(unit.get("id", "SPEC-U-PENDING"))
    ears_ids = ", ".join(str(item) for item in unit.get("ears", []) if str(item).strip()) or "[PENDING INPUT]"
    behavior = statement or f"el comportamiento confirmado en {unit_id}"
    return [
        {
            "id": f"{base}-01",
            "name": "Spec Unit Happy Path",
            "classification": "fail-to-pass",
            "given": f"`{unit_id}` esta confirmado y sus fuentes estan disponibles",
            "when": behavior,
            "then": "el sistema produce el resultado observable indicado por la unidad y conserva la traza hacia la evidencia",
        },
        {
            "id": f"{base}-02",
            "name": "Spec Unit Validation Path",
            "classification": "fail-to-pass",
            "given": f"una precondicion, dato o regla requerida por `{unit_id}` no se cumple",
            "when": "el usuario o sistema intenta completar el slice",
            "then": "el avance riesgoso se bloquea o queda recuperable sin registrar exito falso",
        },
        {
            "id": f"{base}-03",
            "name": "Failure And Recovery Path",
            "classification": "fail-to-pass",
            "given": "una dependencia, dato, permiso o estado externo citado por la unidad no esta disponible",
            "when": "el sistema intenta completar el slice",
            "then": "la falla queda visible, no se oculta informacion parcial como definitiva y se preserva la auditabilidad",
        },
        {
            "id": f"{base}-04",
            "name": "Regression Path",
            "classification": "pass-to-pass",
            "given": "existen comportamientos vigentes, contratos o pruebas relacionadas antes de implementar esta historia",
            "when": "se valida el incremento junto con la regresion definida por Quality o el repositorio",
            "then": "las capacidades existentes siguen pasando sin cambios colaterales fuera del blast radius declarado",
        },
        {
            "id": f"{base}-05",
            "name": "Quality Evidence Path",
            "classification": "evidence",
            "given": "Quality revisa la historia para aceptacion o automatizacion",
            "when": "consulta criterios, alcance, dependencias y trazas",
            "then": f"encuentra {unit_id}, {ears_ids}, REQ-001, PRD-001, SPEC-001 y los criterios en formato verificable",
        },
    ]


def acceptance_criteria_for_pending_story(story_id: str) -> list[dict[str, str]]:
    base = story_id.replace("US-", "AC-")
    return [
        {
            "id": f"{base}-01",
            "name": "Pending Spec Unit Evidence",
            "classification": "evidence",
            "given": "no existe una Spec Unit funcional confirmada",
            "when": "Sentinel genera el backlog",
            "then": "la historia permanece como `[PENDING INPUT]` y apunta a los gaps que desbloquean slicing, sin inventar alcance",
        }
    ]


def acceptance_criteria_for_story(story_id: str, seed: dict[str, str]) -> list[dict[str, str]]:
    base = story_id.replace("US-", "AC-")
    return [
        {
            "id": f"{base}-01",
            "name": "Happy Path",
            "classification": "fail-to-pass",
            "given": "el usuario objetivo tiene permisos vigentes, datos validos y el contexto minimo confirmado",
            "when": f"ejecuta la capacidad cubierta por {seed['fr']}",
            "then": "el sistema produce el resultado esperado y deja evidencia trazable hacia el requerimiento y la spec",
        },
        {
            "id": f"{base}-02",
            "name": "Validation Path",
            "classification": "fail-to-pass",
            "given": "falta informacion obligatoria, la seleccion es ambigua o una regla confirmada no se cumple",
            "when": "el usuario intenta avanzar con el flujo",
            "then": "el sistema bloquea el avance riesgoso, explica la condicion recuperable y no registra exito falso",
        },
        {
            "id": f"{base}-03",
            "name": "Failure And Recovery Path",
            "classification": "fail-to-pass",
            "given": "una dependencia, dato, permiso o estado externo no esta disponible",
            "when": "el sistema intenta completar el slice",
            "then": "la falla queda visible, no se oculta informacion parcial como definitiva y se preserva la auditabilidad",
        },
        {
            "id": f"{base}-04",
            "name": "Regression Path",
            "classification": "pass-to-pass",
            "given": "existen comportamientos vigentes, contratos o pruebas relacionadas antes de implementar esta historia",
            "when": "se valida el incremento junto con la regresion definida por Quality o el repositorio",
            "then": "las capacidades existentes siguen pasando sin cambios colaterales fuera del blast radius declarado",
        },
        {
            "id": f"{base}-05",
            "name": "Quality Evidence Path",
            "classification": "evidence",
            "given": "Quality revisa la historia para aceptacion o automatizacion",
            "when": "consulta criterios, alcance, dependencias y trazas",
            "then": f"encuentra {seed['fr']}, {seed['jtbd']}, REQ-001, PRD-001, SPEC-001 y los criterios en formato verificable",
        },
    ]


def acceptance_criteria_for_enabler(story_id: str, seed: dict[str, str]) -> list[dict[str, str]]:
    base = story_id.replace("US-", "AC-")
    return [
        {
            "id": f"{base}-01",
            "name": "Boundary Fit",
            "classification": "fail-to-pass",
            "given": "el enabler fue propuesto para el backlog",
            "when": "Product, Technology y Quality revisan su alcance",
            "then": "queda ligado a funcionalidad, FR, epica, historia o superficie de implementacion concreta dentro del boundary del proyecto y no a infraestructura generica",
        },
        {
            "id": f"{base}-02",
            "name": "Enables Project Functionality",
            "classification": "fail-to-pass",
            "given": "las funcionalidades, historias o superficies dependientes estan identificadas",
            "when": "el enabler se completa",
            "then": "el scope funcional habilitado puede avanzar con menos incertidumbre, dependencia o riesgo verificable",
        },
        {
            "id": f"{base}-03",
            "name": "Observable Validation",
            "classification": "evidence",
            "given": "el enabler no produce valor usuario directo",
            "when": "Quality valida su resultado",
            "then": "existe una evidencia objetiva que demuestra que el riesgo o dependencia fue reducido",
        },
        {
            "id": f"{base}-04",
            "name": "No Loose Infrastructure",
            "classification": "pass-to-pass",
            "given": "aparece trabajo de setup, ambiente o infraestructura no especifica",
            "when": "no habilita una historia, riesgo o contrato trazable",
            "then": "se rechaza como backlog item y se trata como precondicion operacional o tarea externa al scope",
        },
    ]


def domain_context_snapshot(project_id: str) -> dict[str, Any]:
    base = workspace_path(project_id)
    domains: dict[str, Any] = {}
    all_hash = sha256()
    for domain, folders in DOMAIN_CONTEXT_FOLDERS.items():
        files: list[dict[str, str]] = []
        domain_hash = sha256()
        for folder in folders:
            path = base / folder
            if not path.exists():
                continue
            for item in sorted(path.rglob("*")):
                if "04_regeneration" in item.parts:
                    continue
                if item.is_file() and item.suffix.lower() in {".md", ".txt", ".json", ".yaml", ".yml"}:
                    text = item.read_text(encoding="utf-8")
                    digest = sha256(text.encode("utf-8")).hexdigest()
                    relative = item.relative_to(base).as_posix()
                    files.append({"path": relative, "hash": digest})
                    domain_hash.update(relative.encode("utf-8"))
                    domain_hash.update(digest.encode("utf-8"))
        aggregate = domain_hash.hexdigest() if files else "empty"
        domains[domain] = {"aggregate_hash": aggregate, "file_count": len(files), "files": files}
        all_hash.update(domain.encode("utf-8"))
        all_hash.update(aggregate.encode("utf-8"))
    return {"aggregate_hash": all_hash.hexdigest(), "domains": domains}


def ears_trace_ids(context: dict[str, object]) -> list[str]:
    rows = context.get("ears_requirements", []) if isinstance(context, dict) else []
    if not isinstance(rows, list):
        return []
    ids: list[str] = []
    for row in rows:
        if isinstance(row, dict):
            req_id = str(row.get("id", ""))
            if EARS_REQUIREMENT_ID_RE.match(req_id):
                ids.append(req_id)
    return ids


def safe_cell(value: Any, limit: int) -> str:
    text = str(value).replace("\n", " ").replace("|", "/").strip()
    return text[:limit]
