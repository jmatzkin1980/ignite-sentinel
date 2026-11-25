from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import re
from typing import Any

from ..core.markdown import table_cell
from ..memory import shared_broker
from ..retrieval_plans import compose_plan_query, load_retrieval_plan
from ..slicing_model import load_slicing_model
from ..workspace import workspace_path
from .backlog import build_agent_execution_contract, build_domain_context_coverage, read_plan_for_row
from .prd import ears_trace_ids
from .specs import read_spec_units


DOMAIN_CONTEXT_FOLDERS = {
    "Product": ("00_raw/00_client_requirement", "00_raw/01_business_context", "00_raw/05_interactions", "07_changes"),
    "Technology": ("00_raw/02_technology_context",),
    "Design": ("00_raw/03_design_context",),
    "Quality": ("00_raw/04_quality_context",),
    "Delivery": ("07_changes",),
}

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
        "tokens": ("auth", "autenticacion", "autenticación", "authorization", "autorizacion", "autorización", "permission", "permiso", "role", "rol"),
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
        "tokens": ("backend", "service", "servicio", "worker", "job", "orchestration", "orquestacion", "orquestación", "domain layer", "capa de dominio", "use case", "caso de uso"),
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
        "tokens": ("frontend", "front", "component", "componente", "design system", "sistema de diseno", "sistema de diseño", "prototype", "prototipo", "screen shell", "layout", "state management", "estado compartido"),
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
        "tokens": ("api", "endpoint", "event", "evento", "integration", "integracion", "integración", "webhook", "contract", "contrato"),
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
        "tokens": ("audit", "auditoria", "auditoría", "log", "logging", "observability", "observabilidad", "trace", "traza"),
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


# IMP-324: an English project used to get Spanish story text ("so that la capacidad
# confirmada se puede planificar...") and Spanish acceptance criteria, because this module
# had no language at all. The Spanish strings below are the ones it always used, so a
# Spanish project's backlog is unchanged; an English project now gets the English set.
_EARS_LEAD = re.compile(r"^(When|While|If|Where|Cuando|Mientras|Si|Donde)\s+", re.I)

STORY_TEXT = {
    "es": {
        "description": "Entrega el comportamiento confirmado en `{unit}` como un slice vertical trazable.",
        "benefit": "la capacidad confirmada se puede planificar, implementar y validar sin reinterpretar el PRD o inventar alcance",
        "goal_fallback": "implementar el comportamiento confirmado en {unit}",
        "behavior_fallback": "el comportamiento confirmado en {unit}",
        "pending_goal": "confirmar Spec Units funcionales trazables antes de derivar historias de valor",
        "pending_benefit": "el backlog no inventa alcance y el BA puede resolver los gaps que desbloquean slicing",
    },
    "en": {
        "description": "Delivers the behavior confirmed in `{unit}` as a traceable vertical slice.",
        "benefit": "the confirmed capability can be planned, built and validated without reinterpreting the PRD or inventing scope",
        "goal_fallback": "implement the behavior confirmed in {unit}",
        "behavior_fallback": "the behavior confirmed in {unit}",
        "pending_goal": "confirm traceable functional Spec Units before deriving value stories",
        "pending_benefit": "the backlog invents no scope and the BA can resolve the gaps that unblock slicing",
    },
}

# (given, when, then) per criterion; {unit}, {behavior} and {ears} are filled in.
SPEC_UNIT_AC_TEXT = {
    "es": [
        ("`{unit}` esta confirmado y sus fuentes estan disponibles", "{behavior}",
         "el sistema produce el resultado observable indicado por la unidad y conserva la traza hacia la evidencia"),
        ("una precondicion, dato o regla requerida por `{unit}` no se cumple", "el usuario o sistema intenta completar el slice",
         "el avance riesgoso se bloquea o queda recuperable sin registrar exito falso"),
        ("una dependencia, dato, permiso o estado externo citado por la unidad no esta disponible", "el sistema intenta completar el slice",
         "la falla queda visible, no se oculta informacion parcial como definitiva y se preserva la auditabilidad"),
        ("existen comportamientos vigentes, contratos o pruebas relacionadas antes de implementar esta historia",
         "se valida el incremento junto con la regresion definida por Quality o el repositorio",
         "las capacidades existentes siguen pasando sin cambios colaterales fuera del blast radius declarado"),
        ("Quality revisa la historia para aceptacion o automatizacion", "consulta criterios, alcance, dependencias y trazas",
         "encuentra {unit}, {ears}, REQ-001, PRD-001, SPEC-001 y los criterios en formato verificable"),
    ],
    "en": [
        ("`{unit}` is confirmed and its sources are available", "{behavior}",
         "the system produces the observable result the unit states and keeps the trace to its evidence"),
        ("a precondition, data item or rule that `{unit}` requires is not met", "the user or the system tries to complete the slice",
         "the risky step is blocked or left recoverable, and no false success is recorded"),
        ("a dependency, data item, permission or external state the unit cites is not available", "the system tries to complete the slice",
         "the failure is visible, partial information is not shown as final, and auditability is preserved"),
        ("existing behavior, contracts or related tests are in place before this story is built",
         "the increment is validated together with the regression defined by Quality or the repository",
         "existing capabilities keep passing with no side effects outside the declared blast radius"),
        ("Quality reviews the story for acceptance or automation", "it reads the criteria, scope, dependencies and traces",
         "it finds {unit}, {ears}, REQ-001, PRD-001, SPEC-001 and the criteria in a verifiable form"),
    ],
}

PENDING_AC_TEXT = {
    "es": ("no existe una Spec Unit funcional confirmada", "Sentinel genera el backlog",
           "la historia permanece como `[PENDING INPUT]` y apunta a los gaps que desbloquean slicing, sin inventar alcance"),
    "en": ("no confirmed functional Spec Unit exists", "Sentinel generates the backlog",
           "the story stays `[PENDING INPUT]` and points to the gaps that unblock slicing, without inventing scope"),
}

ENABLER_AC_TEXT = {
    "es": [
        ("el enabler fue propuesto para el backlog", "Product, Technology y Quality revisan su alcance",
         "queda ligado a funcionalidad, FR, epica, historia o superficie de implementacion concreta dentro del boundary del proyecto y no a infraestructura generica"),
        ("las funcionalidades, historias o superficies dependientes estan identificadas", "el enabler se completa",
         "el scope funcional habilitado puede avanzar con menos incertidumbre, dependencia o riesgo verificable"),
        ("el enabler no produce valor usuario directo", "Quality valida su resultado",
         "existe una evidencia objetiva que demuestra que el riesgo o dependencia fue reducido"),
        ("aparece trabajo de setup, ambiente o infraestructura no especifica", "no habilita una historia, riesgo o contrato trazable",
         "se rechaza como backlog item y se trata como precondicion operacional o tarea externa al scope"),
    ],
    "en": [
        ("the enabler was proposed for the backlog", "Product, Technology and Quality review its scope",
         "it is tied to a concrete functionality, FR, epic, story or implementation surface inside the project boundary, not to generic infrastructure"),
        ("the dependent functionalities, stories or surfaces are identified", "the enabler is completed",
         "the enabled functional scope can move forward with less uncertainty, dependency or verifiable risk"),
        ("the enabler produces no direct user value", "Quality validates its result",
         "objective evidence shows that the risk or dependency was reduced"),
        ("setup, environment or non-specific infrastructure work appears", "it enables no traceable story, risk or contract",
         "it is rejected as a backlog item and treated as an operational precondition or a task outside the scope"),
    ],
}

ENABLER_TEXT_EN = {
    "auth": ("Align permissions and access for the flow's slices",
             "Defines the minimum access control the value stories need to run without exposing capabilities beyond the confirmed role.",
             "enable verifiable permissions strictly tied to the confirmed functional flow",
             "the value stories can be built without duplicating or inventing access rules"),
    "data_foundation": ("Prepare the flow's persistence and internal queries",
                        "Prepares the minimum persistence or internal query several stories need to deliver the confirmed functional behavior.",
                        "enable verifiable data for the dependent value stories",
                        "the functional slices can consume consistent information without turning each story into an infrastructure task"),
    "backend_foundation": ("Prepare shared backend support for the functionality",
                           "Builds the backend support several features in scope need to operate consistently.",
                           "enable shared backend services or logic inside the confirmed functional boundary",
                           "the value stories can be built on a common technical base without duplicating behavior or depending on unconfirmed decisions"),
    "frontend_foundation": ("Prepare shared frontend support for the functionality",
                            "Builds the frontend support several stories in scope need to share structure, states or interaction patterns.",
                            "enable shared frontend components, states or patterns inside the confirmed functional boundary",
                            "the value stories can be built with a consistent experience without creating generic visual or technical work"),
    "integration_contract": ("Stabilize the integration contract the flow uses",
                             "Aligns the minimum integration contract that unblocks several value stories inside the project boundary.",
                             "make a verifiable contract available to the slices that depend on external systems",
                             "frontend, backend and quality can work against a bounded, traceable contract"),
    "audit_observability": ("Ensure shared audit and observability evidence",
                            "Defines the minimum shared evidence required to accept and operate the flow's value stories.",
                            "produce verifiable evidence for the functional stories and their tests",
                            "quality and operations can validate the increment without adding ad hoc traces at the end"),
}


def story_language(project_id: str) -> str:
    """The project's language for generated story text: "es" or "en" (the default)."""
    from ..workspace import read_state

    configured = str(read_state(project_id).get("project_language", "")).lower()
    return "es" if configured.startswith("es") else "en"


def strip_ears_lead(statement: str) -> str:
    """IMP-324: "When X, the system shall Y" without its leading EARS word, so the story's
    goal does not read "I want when ..." and a criterion does not read "When When ..."."""
    return _EARS_LEAD.sub("", statement.strip(), count=1)


def build_backlog_story_specs(
    project_id: str,
    backlog_context: dict[str, Any],
    language: str | None = None,
    units: list[dict[str, Any]] | None = None,
    ids: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    language = language if language in STORY_TEXT else story_language(project_id)
    text = STORY_TEXT[language]
    specs: list[dict[str, Any]] = []
    global_domain_coverage = build_domain_context_coverage(backlog_context)
    backlog_context["domain_context_coverage"] = global_domain_coverage
    spec_units = read_spec_units(project_id) if units is None else units
    slicing_model = load_slicing_model()
    if not spec_units:
        story = pending_backlog_story(global_domain_coverage, backlog_context, slicing_model, language)
        story["context_pack"] = "08_context_packs/backlog_generation.json"
        story["context_pack_section"] = "sections"
        story["execution_contract"] = build_agent_execution_contract(story, backlog_context, global_domain_coverage)
        return [story]
    for index, unit in enumerate(spec_units, start=1):
        story_id = ids[str(unit.get("id", ""))] if ids is not None else f"US-{index:03d}"
        story_context = build_story_backlog_context(project_id, story_id, unit, backlog_context)
        domain_coverage = build_domain_context_coverage(story_context)
        backlog_context.setdefault("per_story", {})[story_id] = story_context
        source_context = context_row_for_spec_unit(unit)
        trace = trace_ids_for_spec_unit(unit)
        statement = str(unit.get("statement", "")).strip()
        title = title_for_spec_unit_story(unit)
        goal = goal_for_spec_unit(unit, language)
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
            "description": text["description"].format(unit=unit.get("id", "SPEC-U-PENDING")),
            "goal": goal,
            "benefit": text["benefit"],
            "domain": domain_for_spec_unit(unit),
            "trace": trace,
            "context": source_context,
            "domain_coverage": domain_coverage,
            "context_pack": "08_context_packs/backlog_generation.json",
            "context_pack_section": f"per_story.{story_id}",
            "dependencies": [],
            "enables": [],
            "acceptance": acceptance_criteria_for_spec_unit_story(story_id, unit, statement, language),
            "source_unit": str(unit.get("id", "")),
        }
        if unit.get("change"):
            story["change"] = str(unit["change"])
            story["delta"] = str(unit.get("delta", ""))
            if unit.get("surfaces"):
                story["surfaces"] = list(unit["surfaces"])
        story["execution_contract"] = build_agent_execution_contract(story, story_context, domain_coverage)
        specs.append(story)
    return specs


def build_story_backlog_context(
    project_id: str,
    story_id: str,
    unit: dict[str, Any],
    backlog_context: dict[str, Any],
) -> dict[str, Any]:
    broker = shared_broker(project_id)
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
            # The execution contract must pick surfaces/commands by relevance, not by
            # ingestion freshness; dropping the recency bonus also makes this
            # retrieval deterministic (recency was the only wall-clock-derived input).
            recency_weight=0.0,
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
                recency_weight=0.0,
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
    language: str = "en",
) -> dict[str, Any]:
    decision = slicing_fallback_decision(slicing_model or load_slicing_model())
    text = STORY_TEXT.get(language, STORY_TEXT["en"])
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
        "goal": text["pending_goal"],
        "benefit": text["pending_benefit"],
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
        "acceptance": acceptance_criteria_for_pending_story("US-001", language),
    }


def title_for_spec_unit_story(unit: dict[str, Any]) -> str:
    unit_id = str(unit.get("id", "SPEC-U-PENDING"))
    statement = str(unit.get("statement", "")).strip()
    if statement:
        cleaned = re.sub(r"^(When|While|If|Where|The system shall|Cuando|Mientras|Si|Donde)\s+", "", statement, flags=re.I)
        cleaned = cleaned.rstrip(".")
        return f"{unit_id} - {table_cell(cleaned, 96)}"
    raw_title = str(unit.get("title", unit_id)).strip()
    return f"{unit_id} - {table_cell(raw_title, 96)}"


def goal_for_spec_unit(unit: dict[str, Any], language: str = "en") -> str:
    statement = str(unit.get("statement", "")).strip()
    if statement:
        return strip_ears_lead(statement)
    return STORY_TEXT.get(language, STORY_TEXT["en"])["goal_fallback"].format(unit=unit.get("id", "SPEC-U-PENDING"))


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
        "summary": table_cell(str(unit.get("statement") or unit.get("title") or "[PENDING INPUT]"), 260),
    }


def trace_ids_for_spec_unit(unit: dict[str, Any]) -> list[str]:
    if unit.get("change"):  # IMP-393: a change's unit traces to its CHG and REQ-EARS, never to the project's REQ/PRD/SPEC
        trace = [str(unit["change"]), str(unit.get("id", "SPEC-U-PENDING"))]
    else:
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
    language: str | None = None,
    stable_ids: bool = False,
    *,
    surfaces: list[dict[str, Any]] | None = None,
    trace_ids: list[str] | None = None,
    preserved: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    language = language if language in STORY_TEXT else story_language(project_id)
    if surfaces is not None:  # IMP-416: the new surfaces a change accepted, not the project's evidence
        return build_new_surface_enabler_specs(
            project_id, value_stories, backlog_context, language, surfaces, trace_ids or [], preserved or [])
    # IMP-393: a change request is a value story too (it delivers a change to something already built).
    enabled_value_stories = [story for story in value_stories if story.get("type") in ("value_story", "change_request")]
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
        trace = ["REQ-001", *ears_ids, "PRD-001", "SPEC-001", candidate["fr"], candidate["jtbd"]]
        if language == "es":
            title, description, goal, benefit = (candidate[key] for key in ("title", "description", "goal", "benefit"))
        else:
            title, description, goal, benefit = ENABLER_TEXT_EN[candidate["key"]]
        if stable_ids:
            from .. import id_registry
            from ..story_ids import enabler_key

            key = enabler_key(title)
            story_id = id_registry.assign_ids(project_id, "US", [key])[key]
        else:
            story_id = f"US-{start + len(specs):03d}"
        story = {
            "id": story_id,
            "type": "cross_cutting_enabler",
            "title": title,
            "label": candidate["label"],
            "fr": candidate["fr"],
            "jtbd": candidate["jtbd"],
            "slicing": candidate["slicing"],
            "description": description,
            "goal": goal,
            "benefit": benefit,
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
            "acceptance": acceptance_criteria_for_enabler(story_id, candidate, language),
        }
        story["execution_contract"] = build_agent_execution_contract(story, backlog_context, domain_coverage)
        specs.append(story)
    return specs


ENABLER_SURFACE_TEXT = {
    "es": {
        "title": "Construir {type} «{name}» para las historias que la usan",
        "description": "La superficie «{name}» es nueva en el borde de {change}: las historias que la usan no pueden entregarse hasta que exista.",
        "goal": "tener disponible {type} «{name}» con el comportamiento que el cambio le pide",
        "benefit": "las historias que usan «{name}» se pueden implementar y probar",
        "summary": "La superficie «{name}» entró al borde de {change} por el cruce con las fuentes citadas.",
        "rationale": "Habilitador transversal por superficie nueva: {type} «{name}» es nueva en el borde de {change} y habilita las historias {enables}.",
        "types": {},
    },
    "en": {
        "title": "Build {type} «{name}» for the stories that use it",
        "description": "The surface «{name}» is new in the border of {change}: the stories that use it cannot be delivered until it exists.",
        "goal": "have the {type} «{name}» available with the behavior the change asks of it",
        "benefit": "the stories that use «{name}» can be implemented and tested",
        "summary": "The surface «{name}» joined the border of {change} through the cross-read of the cited sources.",
        "rationale": "Cross-cutting enabler for a new surface: the {type} «{name}» is new in the border of {change} and enables the stories {enables}.",
        "types": {"pantalla": "screen", "proceso": "process", "endpoint": "endpoint", "dato": "data item",
                  "rol": "role", "integracion": "integration", "regla": "rule"},
    },
}


def build_new_surface_enabler_specs(
    project_id: str,
    value_stories: list[dict[str, Any]],
    backlog_context: dict[str, Any],
    language: str,
    surfaces: list[dict[str, Any]],
    trace_ids: list[str],
    preserved: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """IMP-416: one enabler per new surface (origin `cross`, zone `nuevo`) that at least one value story uses."""
    from .. import id_registry
    from ..change_requirements import _fold_name
    from ..story_ids import enabler_key

    texts = ENABLER_SURFACE_TEXT["es" if language == "es" else "en"]
    change = trace_ids[0] if trace_ids else ""
    specs: list[dict[str, Any]] = []
    for surface in surfaces:
        name, kind = str(surface.get("name", "")), str(surface.get("type", ""))
        enabled = [s for s in value_stories if s.get("type") in ("value_story", "change_request")
                   and any(_fold_name(x) == _fold_name(name) for x in s.get("surfaces") or [])]
        if not enabled:
            continue
        shown = texts["types"].get(kind, kind)
        values = {"type": shown, "name": name, "change": change}
        title = texts["title"].format(**values)
        key = enabler_key(f"{change} {kind}:{name}")
        story_id = id_registry.assign_ids(project_id, "US", [key])[key]
        domain_coverage = enabled[0].get("domain_coverage", [])
        units = list(dict.fromkeys(u for s in enabled for u in s.get("source_units") or []))
        acceptance = acceptance_criteria_for_enabler(story_id, {}, language)
        acceptance += preserved_criteria(story_id.replace("US-", "AC-"), len(acceptance) + 1, change, preserved, language)
        story = {
            "id": story_id,
            "type": "cross_cutting_enabler",
            "title": title,
            "label": "Enabler",
            "fr": enabled[0].get("fr", ""),
            "jtbd": enabled[0].get("jtbd", ""),
            "slicing": "Cross-Cutting Enabler / New Surface",
            "slicing_rationale": texts["rationale"].format(**values, enables=", ".join(s["id"] for s in enabled)),
            "description": texts["description"].format(**values),
            "goal": texts["goal"].format(**values),
            "benefit": texts["benefit"].format(**values),
            "domain": "technical",
            "trace": [change, *units],
            "context": {"need": "cross_cutting_enabler", "artifact_id": change, "artifact_type": "change_border",
                        "summary": texts["summary"].format(**values)},
            "domain_coverage": domain_coverage,
            "dependencies": [],
            "enables": [s["id"] for s in enabled],
            "acceptance": acceptance,
            "source_unit": "",
            "source_units": [],
            "change": change,
            "delta": "ADDED",
            "surfaces": [name],
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


PRESERVED_AC_TEXT = {
    "es": (
        "el cambio {change} está aplicado",
        "se ejercita el comportamiento existente que el cambio no modifica",
        "el comportamiento preservado sigue igual: {statement} ({ears})",
    ),
    "en": (
        "the change {change} is applied",
        "the existing behavior that the change does not modify is exercised",
        "the preserved behavior stays the same: {statement} ({ears})",
    ),
}

_SPEC_UNIT_AC_META = (
    ("Spec Unit Happy Path", "fail-to-pass"),
    ("Spec Unit Validation Path", "fail-to-pass"),
    ("Failure And Recovery Path", "fail-to-pass"),
    ("Regression Path", "pass-to-pass"),
    ("Quality Evidence Path", "evidence"),
)
_ENABLER_AC_META = (
    ("Boundary Fit", "fail-to-pass"),
    ("Enables Project Functionality", "fail-to-pass"),
    ("Observable Validation", "evidence"),
    ("No Loose Infrastructure", "pass-to-pass"),
)


def acceptance_criteria_for_spec_unit_story(
    story_id: str,
    unit: dict[str, Any],
    statement: str,
    language: str = "en",
) -> list[dict[str, str]]:
    base = story_id.replace("US-", "AC-")
    unit_id = str(unit.get("id", "SPEC-U-PENDING"))
    ears_ids = ", ".join(str(item) for item in unit.get("ears", []) if str(item).strip()) or "[PENDING INPUT]"
    texts = SPEC_UNIT_AC_TEXT.get(language, SPEC_UNIT_AC_TEXT["en"])
    behavior = strip_ears_lead(statement) if statement else STORY_TEXT.get(language, STORY_TEXT["en"])["behavior_fallback"].format(unit=unit_id)
    values = {"unit": unit_id, "behavior": behavior, "ears": ears_ids}
    criteria = [
        {
            "id": f"{base}-{index:02d}",
            "name": name,
            "classification": classification,
            "given": given.format(**values),
            "when": when.format(**values),
            "then": then.format(**values),
        }
        for index, ((name, classification), (given, when, then)) in enumerate(zip(_SPEC_UNIT_AC_META, texts), start=1)
    ]
    if unit.get("change"):  # IMP-393: the evidence criterion cites the change, not the project's REQ/PRD/SPEC
        for criterion in criteria:
            criterion["then"] = criterion["then"].replace(", REQ-001, PRD-001, SPEC-001", f", {unit['change']}")
    # IMP-393: each UNCHANGED row of the change is behavior this story must not break (pass-to-pass).
    criteria.extend(
        preserved_criteria(base, len(criteria) + 1, str(unit.get("change", "")), unit.get("preserved", []) or [], language)
    )
    return criteria


def preserved_criteria(
    base: str,
    start: int,
    change: str,
    preserved: list[dict[str, Any]],
    language: str = "en",
) -> list[dict[str, str]]:
    """IMP-393: one pass-to-pass criterion per UNCHANGED row, numbered from ``start``."""
    given, when, then = PRESERVED_AC_TEXT.get(language, PRESERVED_AC_TEXT["en"])
    criteria: list[dict[str, str]] = []
    for offset, row in enumerate(preserved, start=start):
        statement_text = " ".join(str(row.get("statement", "")).split()).rstrip(".").replace("|", "\\|")
        row_values = {"change": change, "statement": statement_text, "ears": row.get("id", "")}
        criteria.append(
            {
                "id": f"{base}-{offset:02d}",
                "name": "Preserved Behavior",
                "classification": "pass-to-pass",
                "given": given.format(**row_values),
                "when": when.format(**row_values),
                "then": then.format(**row_values),
            }
        )
    return criteria


def acceptance_criteria_for_slice_story(
    story_id: str,
    units: list[dict[str, Any]],
    change: str,
    preserved: list[dict[str, Any]],
    language: str = "en",
) -> list[dict[str, str]]:
    """IMP-416: a happy path per unit, then validation, failure, regression and evidence once, then the preserved rows."""
    base = story_id.replace("US-", "AC-")
    texts = SPEC_UNIT_AC_TEXT.get(language, SPEC_UNIT_AC_TEXT["en"])
    fallback = STORY_TEXT.get(language, STORY_TEXT["en"])["behavior_fallback"]
    unit_ids = ", ".join(str(unit.get("id", "SPEC-U-PENDING")) for unit in units)
    ears_ids = ", ".join(
        str(item) for unit in units for item in unit.get("ears", []) if str(item).strip()
    ) or "[PENDING INPUT]"
    rows: list[tuple[str, str, tuple[str, str, str], dict[str, str]]] = []
    name, classification = _SPEC_UNIT_AC_META[0]
    for unit in units:
        unit_id = str(unit.get("id", "SPEC-U-PENDING"))
        statement = str(unit.get("statement", "")).strip()
        unit_ears = ", ".join(str(item) for item in unit.get("ears", []) if str(item).strip()) or "[PENDING INPUT]"
        behavior = strip_ears_lead(statement) if statement else fallback.format(unit=unit_id)
        rows.append((name, classification, texts[0], {"unit": unit_id, "behavior": behavior, "ears": unit_ears}))
    shared = {"unit": unit_ids, "behavior": "", "ears": ears_ids}
    for (name, classification), text in zip(_SPEC_UNIT_AC_META[1:], texts[1:]):
        rows.append((name, classification, text, shared))
    criteria = [
        {
            "id": f"{base}-{index:02d}",
            "name": name,
            "classification": classification,
            "given": given.format(**values),
            "when": when.format(**values),
            "then": then.format(**values).replace(", REQ-001, PRD-001, SPEC-001", f", {change}"),
        }
        for index, (name, classification, (given, when, then), values) in enumerate(rows, start=1)
    ]
    criteria.extend(preserved_criteria(base, len(criteria) + 1, change, preserved, language))
    return criteria


def build_slice_story_specs(
    project_id: str,
    backlog_context: dict[str, Any],
    language: str,
    slices: list[dict[str, Any]],
    units_by_id: dict[str, dict[str, Any]],
    ids: dict[str, str],
    preserved: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """IMP-416: one value story per slice (functionality x delta); the project path keeps build_backlog_story_specs."""
    language = language if language in STORY_TEXT else "en"
    text = STORY_TEXT[language]
    rationale_text = {
        "es": "{fun}: {n} unidad(es) de {name}; {rationale}",
        "en": "{fun}: {n} unit(s) of {name}; {rationale}",
    }[language]
    backlog_context["domain_context_coverage"] = build_domain_context_coverage(backlog_context)
    specs: list[dict[str, Any]] = []
    for item in slices:
        story_id = ids[item["key"]]
        units = [units_by_id[uid] for uid in item["units"]]
        first = units[0]
        change = str(first.get("change", ""))
        composite = {
            "id": str(first.get("id", "SPEC-U-PENDING")),
            "title": str(first.get("title", "")),
            "statement": " ".join(str(unit.get("statement", "")).strip() for unit in units).strip(),
            "ears": [str(e) for unit in units for e in unit.get("ears", [])],
            "surfaces": list(item.get("surfaces") or []),
        }
        story_context = build_story_backlog_context(project_id, story_id, composite, backlog_context)
        domain_coverage = build_domain_context_coverage(story_context)
        backlog_context.setdefault("per_story", {})[story_id] = story_context
        trace: list[str] = []
        for unit in units:
            for entry in trace_ids_for_spec_unit(unit):
                if entry not in trace:
                    trace.append(entry)
        extra = len(units) - 1
        statement = strip_ears_lead(str(first.get("statement", ""))).rstrip(".")
        title = f"{item['name']}: {table_cell(statement, 80)}" + (f" (+{extra})" if extra else "")
        story = {
            "id": story_id,
            "type": "value_story",
            "title": title,
            "label": "Spec Unit",
            "fr": item["functionality"],
            "jtbd": ", ".join(dict.fromkeys(e for unit in units for e in map(str, unit.get("ears", [])))) or "[PENDING INPUT]",
            "slicing": item["slicing"],
            "slicing_rationale": rationale_text.format(
                fun=item["functionality"], n=len(units), name=item["name"], rationale=item["rationale"]
            ),
            "description": text["description"].format(unit=", ".join(item["units"])),
            "goal": goal_for_spec_unit(first, language),
            "benefit": text["benefit"],
            "domain": domain_for_spec_unit(first),
            "trace": sorted(trace),
            "context": context_row_for_spec_unit(first),
            "domain_coverage": domain_coverage,
            "context_pack": "08_context_packs/backlog_generation.json",
            "context_pack_section": f"per_story.{story_id}",
            "dependencies": [],
            "enables": [],
            "acceptance": acceptance_criteria_for_slice_story(story_id, units, change, preserved, language),
            "source_unit": item["units"][0],
            "source_units": list(item["units"]),
            "change": change,
            "delta": item["delta"],
            "surfaces": list(item.get("surfaces") or []),
        }
        story["execution_contract"] = build_agent_execution_contract(story, story_context, domain_coverage)
        specs.append(story)
    return specs


def acceptance_criteria_for_pending_story(story_id: str, language: str = "en") -> list[dict[str, str]]:
    base = story_id.replace("US-", "AC-")
    given, when, then = PENDING_AC_TEXT.get(language, PENDING_AC_TEXT["en"])
    return [
        {
            "id": f"{base}-01",
            "name": "Pending Spec Unit Evidence",
            "classification": "evidence",
            "given": given,
            "when": when,
            "then": then,
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


def acceptance_criteria_for_enabler(story_id: str, seed: dict[str, str], language: str = "es") -> list[dict[str, str]]:
    base = story_id.replace("US-", "AC-")
    texts = ENABLER_AC_TEXT.get(language, ENABLER_AC_TEXT["en"])
    return [
        {"id": f"{base}-{index:02d}", "name": name, "classification": classification,
         "given": given, "when": when, "then": then}
        for index, ((name, classification), (given, when, then)) in enumerate(zip(_ENABLER_AC_META, texts), start=1)
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
