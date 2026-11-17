"""Per-gap prose: titles, questions, why it matters, examples and section routing."""
from __future__ import annotations

from ..lens_registry import load_lens_checks


def lens_text(gap_id: str, key: str, language: str = "en") -> str:
    """IMP-256: a lens check can carry its own elicitation text (`text.<lang>.<key>`)."""
    for check in load_lens_checks():
        if check.get("id") == gap_id:
            texts = check.get("text") or {}
            chosen = texts.get("es" if language == "es" else "en") or {}
            return str(chosen.get(key, "") or "")
    return ""


def description_for_gap(gap: dict[str, str], language: str = "en") -> str:
    data_text = lens_text(gap["id"], "description", language)
    if data_text:
        return data_text
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
        "GAP-METRIC-DEFINITION": "Se nombra una métrica, KPI o indicador sin su definición, fórmula, unidad, fuente ni umbral.",
        "GAP-AUTH-MODEL": "Se mencionan autenticación, permisos o roles sin el método de autenticación, el modelo de permisos ni el catálogo de roles.",
    }
    return descriptions.get(gap["id"], gap["description"])


def human_title_for_gap(gap_id: str, language: str = "en") -> str:
    data_text = lens_text(gap_id, "title", language)
    if data_text:
        return data_text
    prd_titles_es = {
        "GAP-PRD-PERSONA-DETAIL": "Detalle de personas para PRD",
        "GAP-PRD-FR-AC": "Requerimientos funcionales y criterios de aceptacion",
        "GAP-PRD-NFR-KPI": "NFRs, KPIs y medicion",
        "GAP-PRD-DEPENDENCIES-ROADMAP": "Dependencias y roadmap",
        "GAP-PRD-ROLLOUT-ENVIRONMENTS": "Rollout y ambientes",
        "GAP-PRD-GLOSSARY-GOVERNANCE": "Glosario y gobernanza",
    }
    prd_titles_en = {
        "GAP-PRD-PERSONA-DETAIL": "PRD Persona Detail",
        "GAP-PRD-FR-AC": "Functional Requirements And ACs",
        "GAP-PRD-NFR-KPI": "NFRs, KPIs, And Measurement",
        "GAP-PRD-DEPENDENCIES-ROADMAP": "Dependencies And Roadmap",
        "GAP-PRD-ROLLOUT-ENVIRONMENTS": "Rollout And Environments",
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
            "GAP-METRIC-DEFINITION": "Definición de métrica",
            "GAP-AUTH-MODEL": "Modelo de auth y permisos",
            "GAP-BUSINESS-RULE-WEAK-WORD-SMELL": "Reglas de negocio vagas",
            "GAP-QUALITY-WEAK-WORD-SMELL": "Criterios de calidad vagos",
            "GAP-HYPOTHETICAL-ANCHOR": "Caso real detrás de la necesidad",
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
        "GAP-METRIC-DEFINITION": "Metric Definition",
        "GAP-AUTH-MODEL": "Auth And Permission Model",
        "GAP-BUSINESS-RULE-WEAK-WORD-SMELL": "Vague Business Rules",
        "GAP-QUALITY-WEAK-WORD-SMELL": "Vague Quality Criteria",
        "GAP-HYPOTHETICAL-ANCHOR": "Real Case Behind The Need",
    }
    return titles.get(gap_id, "Information Needed")


def why_gap_matters(gap_id: str, language: str = "en") -> str:
    data_text = lens_text(gap_id, "why", language)
    if data_text:
        return data_text
    prd_reasons_es = {
        "GAP-PRD-PERSONA-DETAIL": "El PRD necesita personas con objetivos, dolores, frecuencia y habilidad para orientar experiencia, adopcion y soporte.",
        "GAP-PRD-FR-AC": "El PRD debe listar requerimientos funcionales con criterios de aceptacion trazables para que backlog y QA no inventen alcance.",
        "GAP-PRD-NFR-KPI": "NFRs y KPIs con targets, metodo de medicion y ventana temporal permiten validar valor y calidad objetivamente.",
        "GAP-PRD-DEPENDENCIES-ROADMAP": "Dependencias, owners, MVP y roadmap sostienen la planificacion y evitan historias bloqueadas por supuestos.",
        "GAP-PRD-ROLLOUT-ENVIRONMENTS": "Rollout, ambientes y restricciones de release evitan que specs y backlog inventen secuencia o condiciones de salida.",
        "GAP-PRD-GLOSSARY-GOVERNANCE": "Glosario, restricciones mandatorias, pending inputs y audit trail preservan entendimiento compartido y trazabilidad.",
    }
    prd_reasons_en = {
        "GAP-PRD-PERSONA-DETAIL": "The PRD needs personas with goals, pain points, frequency, and proficiency to guide experience, adoption, and support decisions.",
        "GAP-PRD-FR-AC": "The PRD must list functional requirements with traceable acceptance criteria so backlog and QA do not invent scope.",
        "GAP-PRD-NFR-KPI": "NFRs and KPIs with targets, measurement method, and timeframe make value and quality objectively verifiable.",
        "GAP-PRD-DEPENDENCIES-ROADMAP": "Dependencies, owners, MVP, and roadmap support planning and prevent stories from being blocked by assumptions.",
        "GAP-PRD-ROLLOUT-ENVIRONMENTS": "Rollout, environments, and release constraints prevent specs and backlog from inventing sequencing or exit conditions.",
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
            "GAP-METRIC-DEFINITION": "Una métrica nombrada sin definición, fuente ni umbral no es medible ni comprometible y arrastra ambigüedad a KPIs y criterios de éxito.",
            "GAP-AUTH-MODEL": "Sin método de autenticación, modelo de permisos ni catálogo de roles, la superficie de acceso queda indefinida para diseño, backend y seguridad.",
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
        "GAP-METRIC-DEFINITION": "A metric named without a definition, source, or threshold is not measurable or commitable and drags ambiguity into KPIs and success criteria.",
        "GAP-AUTH-MODEL": "Without an auth method, permission model, or role catalog, the access surface stays undefined for design, backend, and security.",
    }
    return reasons.get(gap_id, "This information is needed to avoid assumptions in downstream artifacts.")


def example_response_for_gap(gap_id: str, language: str = "en") -> str:
    data_text = lens_text(gap_id, "example", language)
    if data_text:
        return data_text
    prd_examples_es = {
        "GAP-PRD-PERSONA-DETAIL": "Persona primaria: operador central. Objetivo: resolver casos sin TI. Dolor: proceso manual riesgoso. Frecuencia: diaria. Habilidad: herramienta interna avanzada.",
        "GAP-PRD-FR-AC": "FR-01: el sistema debe listar elementos pendientes. AC: Given existen pendientes, When el operador consulta, Then ve ID, estado, responsable y fecha con fuente trazable.",
        "GAP-PRD-NFR-KPI": "NFR: auditoria disponible por 2 anios. KPI: 0 operaciones incorrectas, medido por incidentes post-release diarios durante el primer mes.",
        "GAP-PRD-DEPENDENCIES-ROADMAP": "MVP: consulta, regla principal y auditoria. Dependencias: servicio X owner Equipo A, copy owner Diseno, credenciales owner Seguridad. Fase 2: reportes.",
        "GAP-PRD-ROLLOUT-ENVIRONMENTS": "Rollout: feature flag primero en ambiente staging, luego piloto con supervisores. Produccion requiere ventana aprobada y plan de rollback.",
        "GAP-PRD-GLOSSARY-GOVERNANCE": "Glosario: 'estado grisado' significa no operable. Restriccion: no exponer datos sensibles en logs. Pending input: owner de metrica.",
    }
    prd_examples_en = {
        "GAP-PRD-PERSONA-DETAIL": "Primary persona: central operator. Goal: resolve cases without IT. Pain: risky manual process. Frequency: daily. Proficiency: advanced internal tool.",
        "GAP-PRD-FR-AC": "FR-01: the system must list pending items. AC: Given pending items exist, When the operator opens the list, Then ID, status, owner, and date are visible with source trace.",
        "GAP-PRD-NFR-KPI": "NFR: audit records available for 2 years. KPI: 0 incorrect operations, measured through daily post-release incidents during month one.",
        "GAP-PRD-DEPENDENCIES-ROADMAP": "MVP: query, main rule, and audit. Dependencies: service X owner Team A, copy owner Design, credentials owner Security. Phase 2: reporting.",
        "GAP-PRD-ROLLOUT-ENVIRONMENTS": "Rollout: feature flag first in staging, then pilot with supervisors. Production requires approved window and rollback plan.",
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
            "GAP-METRIC-DEFINITION": "La métrica 'tiempo de resolución' se define como promedio de horas entre apertura y cierre, fuente Case Management, baseline 8h, umbral objetivo 6h.",
            "GAP-AUTH-MODEL": "Autenticación vía SSO corporativo (OIDC). Permisos por RBAC con roles 'lead' (lectura total) y 'agent' (solo su cola); catálogo de roles owner Seguridad.",
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
        "GAP-METRIC-DEFINITION": "The 'resolution time' metric is the average hours between open and close, source Case Management, baseline 8h, target threshold 6h.",
        "GAP-AUTH-MODEL": "Authentication via corporate SSO (OIDC). Permissions via RBAC with roles 'lead' (full read) and 'agent' (own queue only); role catalog owned by Security.",
    }
    return examples.get(gap_id, "A useful answer names the decision, owner/source, evidence, and whether the answer is confirmed or pending.")


# --- IMP-022: gaps as elicitation, not as statement ---------------------------
#
# A gap question is far more answerable when the client/domain also sees WHY it
# matters (risk if left open), WHAT it unblocks (the downstream brief/PRD/spec
# section that consumes the answer), and the EXPECTED FORMAT of a closing answer.
# `why_gap_matters` already covers the first factor; the two functions below add
# the other two. The gap->section mapping inverts what lived implicitly in the
# "PRD Coverage Readiness" and "Backlog Readiness Signals" tables (maturity.py)
# and moves it to the gap's origin. These render in both gaps.md response
# sections and the domain context-request packs. The trace table is unchanged,
# so render_gaps -> parse_gap_rows stays a clean roundtrip.


def unblocks_for_gap(gap_id: str, language: str = "en") -> str:
    """What downstream brief/PRD/spec section the gap's answer unblocks."""
    data_text = lens_text(gap_id, "unblocks", language)
    if data_text:
        return data_text
    if language == "es":
        unblocks = {
            "GAP-OBJECTIVE": "Sección 1 del brief (identidad y objetivo) y el problem statement del PRD; todo lo downstream optimiza hacia esto.",
            "GAP-USERS": "Sección 2 del brief (actores) y las personas del PRD; condiciona journeys, permisos y criterios de aceptación.",
            "GAP-SCOPE": "Los límites de alcance del brief y el alcance/no-objetivos del PRD; evita que specs y backlog absorban trabajo no previsto.",
            "GAP-ACCEPTANCE": "Los criterios de aceptación del PRD, las ACs de specs y los test cases de Calidad.",
            "GAP-QUALITY": "Los NFRs del PRD y la estrategia de handoff/testing de Calidad.",
            "GAP-METRIC-SOURCE": "Los KPIs del brief y la sección de NFRs/KPIs y medición del PRD.",
            "GAP-TECH-DATA-SOURCE": "La sección 5 del brief (técnica) y los boundaries de sistema y ownership de datos de specs.",
            "GAP-TECH-NFR": "Los NFRs del PRD y la sección de restricciones operativas de specs.",
            "GAP-DESIGN-FLOW": "La sección 4 del brief (diseño), los flujos UX de specs y el context pack de Diseño.",
            "GAP-DESIGN-STATES": "Los estados UX de specs y la cobertura de casos borde de Calidad.",
            "GAP-DESIGN-PROTOTYPE-INPUT": "El context pack de Diseño y el alcance del prototipo.",
            "GAP-PRODUCT-ASIS-TOBE": "La sección 3 del brief (as-is/to-be) y el slicing del backlog.",
            "GAP-BUSINESS-RULES": "Los FRs/ACs del PRD, las reglas de negocio de specs y los casos borde de Calidad.",
            "GAP-FRONTEND-SURFACE": "La superficie frontend de specs y el context pack Frontend / historias del backlog.",
            "GAP-BACKEND-SURFACE": "La superficie backend de specs y el context pack Backend / historias del backlog.",
            "GAP-TECH-DEEP-DIVE-INPUT": "El context pack de Tecnología y la arquitectura de solución (SAD).",
            "GAP-GOVERNANCE-CONSTRAINTS": "La sección 6 del brief (gobernanza) y la sección de gobernanza del PRD.",
            "GAP-DELIVERY-READINESS": "El plan de ejecución del PRD y la secuencia/rollout del backlog.",
            "GAP-BACKLOG-SLICING-READINESS": "El primer slice de valor y los límites de slicing del backlog.",
            "GAP-BACKLOG-ENABLERS": "Los enablers transversales del backlog.",
            "GAP-QUALITY-HANDOFF": "Los test cases y el coverage map de Calidad.",
            "GAP-PRD-PERSONA-DETAIL": "La sección de Personas del PRD.",
            "GAP-PRD-FR-AC": "La sección de Requerimientos Funcionales del PRD (FRs con criterios de aceptación).",
            "GAP-PRD-NFR-KPI": "La sección de NFRs y KPIs del PRD.",
            "GAP-PRD-DEPENDENCIES-ROADMAP": "El plan de ejecución del PRD (dependencias, MVP, roadmap).",
            "GAP-PRD-ROLLOUT-ENVIRONMENTS": "El plan de ejecución del PRD (rollout, ambientes y restricciones de release).",
            "GAP-PRD-GLOSSARY-GOVERNANCE": "La sección de Gobernanza del PRD (glosario, restricciones, audit trail).",
            "GAP-METRIC-DEFINITION": "Los KPIs del brief y la sección de NFRs/KPIs y medición del PRD.",
            "GAP-AUTH-MODEL": "Los actores/permisos del brief, la sección de gobernanza/seguridad del PRD y la superficie de acceso de specs.",
        }
        return unblocks.get(gap_id, "Una sección downstream de brief/PRD/spec que hoy no tiene evidencia confirmada para consumir.")
    unblocks = {
        "GAP-OBJECTIVE": "Brief section 1 (identity & objective) and the PRD problem statement; everything downstream optimizes toward this.",
        "GAP-USERS": "Brief section 2 (actors) and PRD personas; it drives journeys, permissions, and acceptance criteria.",
        "GAP-SCOPE": "Brief scope boundaries and PRD scope/non-goals; it keeps specs and backlog from absorbing unintended work.",
        "GAP-ACCEPTANCE": "PRD acceptance criteria, specs ACs, and Quality test cases.",
        "GAP-QUALITY": "PRD NFRs and the Quality handoff/test strategy.",
        "GAP-METRIC-SOURCE": "Brief KPIs and the PRD NFRs/KPIs and measurement section.",
        "GAP-TECH-DATA-SOURCE": "Brief section 5 (technical) and the specs system boundaries and data ownership.",
        "GAP-TECH-NFR": "PRD NFRs and the specs operational-constraints section.",
        "GAP-DESIGN-FLOW": "Brief section 4 (design), specs UX flows, and the Design context pack.",
        "GAP-DESIGN-STATES": "Specs UX states and Quality edge-case coverage.",
        "GAP-DESIGN-PROTOTYPE-INPUT": "The Design context pack and the prototype scope.",
        "GAP-PRODUCT-ASIS-TOBE": "Brief section 3 (as-is/to-be) and backlog slicing.",
        "GAP-BUSINESS-RULES": "PRD functional requirements/ACs, specs business rules, and Quality edge cases.",
        "GAP-FRONTEND-SURFACE": "The specs frontend surface and the Frontend context pack / backlog stories.",
        "GAP-BACKEND-SURFACE": "The specs backend surface and the Backend context pack / backlog stories.",
        "GAP-TECH-DEEP-DIVE-INPUT": "The Technology context pack and the solution architecture (SAD).",
        "GAP-GOVERNANCE-CONSTRAINTS": "Brief section 6 (governance) and the PRD governance section.",
        "GAP-DELIVERY-READINESS": "The PRD execution plan and backlog sequencing/rollout.",
        "GAP-BACKLOG-SLICING-READINESS": "The backlog's first value slice and slice boundaries.",
        "GAP-BACKLOG-ENABLERS": "The backlog's cross-cutting enablers.",
        "GAP-QUALITY-HANDOFF": "Quality test cases and the coverage map.",
        "GAP-PRD-PERSONA-DETAIL": "The PRD Personas section.",
        "GAP-PRD-FR-AC": "The PRD Functional Requirements section (FRs with acceptance criteria).",
        "GAP-PRD-NFR-KPI": "The PRD NFRs and KPIs section.",
        "GAP-PRD-DEPENDENCIES-ROADMAP": "The PRD Execution Plan (dependencies, MVP, roadmap).",
        "GAP-PRD-ROLLOUT-ENVIRONMENTS": "The PRD Execution Plan (rollout, environments, and release constraints).",
        "GAP-PRD-GLOSSARY-GOVERNANCE": "The PRD Governance section (glossary, constraints, audit trail).",
        "GAP-METRIC-DEFINITION": "Brief KPIs and the PRD NFRs/KPIs and measurement section.",
        "GAP-AUTH-MODEL": "Brief actors/permissions, the PRD governance/security section, and the specs access surface.",
    }
    return unblocks.get(gap_id, "A downstream brief/PRD/spec section that currently has no confirmed evidence to consume.")


def expected_format_for_gap(gap_id: str, language: str = "en") -> str:
    """The shape of an answer that closes the gap (distinct from a worked example)."""
    data_text = lens_text(gap_id, "expected_format", language)
    if data_text:
        return data_text
    if language == "es":
        formats = {
            "GAP-OBJECTIVE": "Una frase que nombre el resultado de negocio (no la feature) y cómo se reconoce el éxito.",
            "GAP-USERS": "Lista de actores primarios/secundarios con rol e indicando si usan u operan la capacidad.",
            "GAP-SCOPE": "Bullets de in-scope vs out-of-scope y qué debe seguir funcionando.",
            "GAP-ACCEPTANCE": "Uno o más enunciados EARS o Dado/Cuando/Entonces con condiciones observables. Ejemplo EARS: Cuando ocurre <disparador>, el sistema debe <respuesta observable>.",
            "GAP-QUALITY": "Expectativas de calidad como bullets: áreas de riesgo, profundidad de pruebas y evidencia requerida.",
            "GAP-METRIC-SOURCE": "Nombre de la métrica + fuente/owner del baseline + valor objetivo + ventana de medición.",
            "GAP-TECH-DATA-SOURCE": "Sistemas/endpoints involucrados, source of truth y equipo owner.",
            "GAP-TECH-NFR": "NFRs nombrados con umbrales concretos (latencia, retención, disponibilidad) y cómo se observan.",
            "GAP-DESIGN-FLOW": "Punto de entrada y journey paso a paso hasta la(s) pantalla(s) afectada(s).",
            "GAP-DESIGN-STATES": "Los estados de carga, vacío, error y recuperación de la superficie.",
            "GAP-DESIGN-PROTOTYPE-INPUT": "La decisión/flujo/interacción que el prototipo debe validar.",
            "GAP-PRODUCT-ASIS-TOBE": "Comportamiento actual vs objetivo, expresado como delta.",
            "GAP-BUSINESS-RULES": "Reglas en formato EARS cuando describen comportamiento: Si <condición/regla>, entonces el sistema debe <respuesta>; incluir umbrales y excepciones.",
            "GAP-FRONTEND-SURFACE": "Superficie(s) afectada(s), estados, validaciones, copy y eventos de analytics.",
            "GAP-BACKEND-SURFACE": "Capacidades, contratos, persistencia/source of truth y comportamiento ante fallas.",
            "GAP-TECH-DEEP-DIVE-INPUT": "Repositorios/componentes, endpoints y source of truth a inspeccionar.",
            "GAP-GOVERNANCE-CONSTRAINTS": "Restricciones nombradas de seguridad/privacidad/compliance/auditoría que aplican.",
            "GAP-DELIVERY-READINESS": "Dependencias con owners, ambientes, fechas y enfoque de rollout.",
            "GAP-BACKLOG-SLICING-READINESS": "El primer slice de valor más qué se difiere y dónde no conviene cortar.",
            "GAP-BACKLOG-ENABLERS": "Cada enabler con el boundary de capacidad que soporta y la evidencia objetiva de completitud.",
            "GAP-QUALITY-HANDOFF": "Flujos críticos, casos borde, datos de prueba y expectativas de evidencia.",
            "GAP-PRD-PERSONA-DETAIL": "Por persona: objetivo, dolores, frecuencia y habilidad.",
            "GAP-PRD-FR-AC": "FR-NN con statement EARS trazable (Cuando/Si/Mientras/Donde/El sistema debe...) más criterio de aceptación y prioridad.",
            "GAP-PRD-NFR-KPI": "NFR/KPI con target, método de medición y ventana temporal.",
            "GAP-PRD-DEPENDENCIES-ROADMAP": "MVP, dependencias con owner y fases del roadmap.",
            "GAP-PRD-ROLLOUT-ENVIRONMENTS": "Ambientes objetivo, estrategia de rollout, restricciones de release y criterio de rollback.",
            "GAP-PRD-GLOSSARY-GOVERNANCE": "Términos de glosario, restricciones mandatorias y pending inputs con owner.",
            "GAP-METRIC-DEFINITION": "Por métrica: definición/fórmula, unidad, fuente/owner del dato, baseline y umbral objetivo.",
            "GAP-AUTH-MODEL": "Método de autenticación, modelo de permisos (p. ej. RBAC) y catálogo de roles con sus alcances.",
        }
        return formats.get(gap_id, "Una decisión más owner/fuente, evidencia y si está confirmada o pendiente.")
    formats = {
        "GAP-OBJECTIVE": "One sentence naming the business outcome (not the feature) and how success is recognized.",
        "GAP-USERS": "List of primary/secondary actors with role and whether they use or operate the capability.",
        "GAP-SCOPE": "In-scope vs out-of-scope bullets and what must keep working.",
        "GAP-ACCEPTANCE": "One or more EARS or Given/When/Then statements with observable conditions. EARS example: When <trigger>, the system shall <observable response>.",
        "GAP-QUALITY": "Quality expectations as bullets: risk areas, test depth, and required evidence.",
        "GAP-METRIC-SOURCE": "Metric name + baseline source/owner + target value + measurement window.",
        "GAP-TECH-DATA-SOURCE": "Systems/endpoints involved, source of truth, and owning team.",
        "GAP-TECH-NFR": "Named NFRs with concrete thresholds (latency, retention, availability) and how they are observed.",
        "GAP-DESIGN-FLOW": "Entry point and step-by-step journey to the affected screen(s).",
        "GAP-DESIGN-STATES": "The loading, empty, error, and recovery states for the surface.",
        "GAP-DESIGN-PROTOTYPE-INPUT": "The decision/flow/interaction the prototype must validate.",
        "GAP-PRODUCT-ASIS-TOBE": "Current behavior vs target behavior, stated as a delta.",
        "GAP-BUSINESS-RULES": "Rules in EARS form when they describe behavior: If <condition/rule>, then the system shall <response>; include thresholds and exceptions.",
        "GAP-FRONTEND-SURFACE": "Affected surface(s), states, validations, copy, and analytics events.",
        "GAP-BACKEND-SURFACE": "Capabilities, contracts, persistence/source of truth, and failure behavior.",
        "GAP-TECH-DEEP-DIVE-INPUT": "Repositories/components, endpoints, and source of truth to inspect.",
        "GAP-GOVERNANCE-CONSTRAINTS": "Named security/privacy/compliance/audit constraints that apply.",
        "GAP-DELIVERY-READINESS": "Dependencies with owners, environments, dates, and rollout approach.",
        "GAP-BACKLOG-SLICING-READINESS": "The first value slice plus what can be deferred and where not to split.",
        "GAP-BACKLOG-ENABLERS": "Each enabler with the capability boundary it supports and objective completion evidence.",
        "GAP-QUALITY-HANDOFF": "Critical flows, edge cases, test data, and evidence expectations.",
        "GAP-PRD-PERSONA-DETAIL": "Per persona: goal, pains, usage frequency, and proficiency.",
        "GAP-PRD-FR-AC": "FR-NN with a traceable EARS statement (When/If/While/Where/The system shall...) plus acceptance criterion and priority.",
        "GAP-PRD-NFR-KPI": "NFR/KPI with target, measurement method, and timeframe.",
        "GAP-PRD-DEPENDENCIES-ROADMAP": "MVP, dependencies with owner, and roadmap phases.",
        "GAP-PRD-ROLLOUT-ENVIRONMENTS": "Target environments, rollout strategy, release constraints, and rollback criterion.",
        "GAP-PRD-GLOSSARY-GOVERNANCE": "Glossary terms, mandatory constraints, and pending inputs with owner.",
        "GAP-METRIC-DEFINITION": "Per metric: definition/formula, unit, data source/owner, baseline, and target threshold.",
        "GAP-AUTH-MODEL": "Authentication method, permission model (e.g. RBAC), and role catalog with their scopes.",
    }
    return formats.get(gap_id, "A decision plus owner/source, evidence, and whether it is confirmed or pending.")


# --- IMP-024: gap -> brief narrative section map ------------------------------
#
# Structured inverse of the IMP-022 prose mapping: which of the project brief's
# narrative sections (1-6) a gap's confirmed answer feeds. The brief compiler
# (maturity.py) uses it to route closed-gap answers into the right section, and
# /resolve-gaps tags resolution seeds with it. Gaps that feed PRD/specs/quality
# rather than a brief 1-6 anchor map to None.
#
#   1 Identidad y Valor       4 Lente de Diseño
#   2 Lente de Negocio        5 Lente Técnico
#   3 Lente de Producto       6 Gobernanza y Restricciones
#
# IMP-254: the values are the canonical lens keys of `sentinel.brief_model`, not
# literal headings. A v2 brief maps them onto its sections through
# `brief_model.v2_sections_for_gap` (lens 6 = §5.11 + §6).

BRIEF_SECTION_FOR_GAP = {
    "GAP-OBJECTIVE": "1",
    "GAP-METRIC-SOURCE": "1",
    "GAP-USERS": "2",
    "GAP-SCOPE": "3",
    "GAP-PRODUCT-ASIS-TOBE": "3",
    "GAP-BUSINESS-RULES": "3",
    "GAP-DESIGN-FLOW": "4",
    "GAP-DESIGN-STATES": "4",
    "GAP-DESIGN-PROTOTYPE-INPUT": "4",
    "GAP-TECH-DATA-SOURCE": "5",
    "GAP-TECH-NFR": "5",
    "GAP-TECH-DEEP-DIVE-INPUT": "5",
    "GAP-FRONTEND-SURFACE": "5",
    "GAP-BACKEND-SURFACE": "5",
    "GAP-GOVERNANCE-CONSTRAINTS": "6",
    "GAP-DELIVERY-READINESS": "6",
}


def brief_section_for_gap(gap_id: str) -> str | None:
    """Which brief narrative section (1-6) a gap's confirmed answer feeds, or None."""
    return BRIEF_SECTION_FOR_GAP.get(gap_id)


# --- IMP-039: gap -> PRD narrative section map --------------------------------
#
# PRD sections are broader than the brief sections and consume both discovery
# signals and confirmed gap answers. The PRD compiler uses this map to route
# closed-gap answers without inventing missing content.

PRD_SECTION_FOR_GAP = {
    "GAP-OBJECTIVE": "1",
    "GAP-METRIC-SOURCE": "6",
    "GAP-USERS": "3",
    "GAP-PRD-PERSONA-DETAIL": "3",
    "GAP-SCOPE": "2",
    "GAP-PRODUCT-ASIS-TOBE": "2",
    "GAP-BUSINESS-RULES": "4",
    "GAP-ACCEPTANCE": "4",
    "GAP-PRD-FR-AC": "4",
    "GAP-QUALITY": "5",
    "GAP-QUALITY-HANDOFF": "5",
    "GAP-TECH-NFR": "5",
    "GAP-PRD-NFR-KPI": "5",
    "GAP-GOVERNANCE-CONSTRAINTS": "11",
    "GAP-PRD-GLOSSARY-GOVERNANCE": "13",
    "GAP-PRD-GOVERNANCE": "11",  # IMP-261: governance split out of the glossary gap
    "GAP-DELIVERY-READINESS": "10",
    "GAP-PRD-DEPENDENCIES-ROADMAP": "10",
    "GAP-PRD-ROLLOUT-ENVIRONMENTS": "10",
}


def prd_section_for_gap(gap_id: str) -> str | None:
    """Which PRD section (1-13) a gap's confirmed answer feeds, or None."""
    return PRD_SECTION_FOR_GAP.get(gap_id)


def lens_for_gap(gap_id: str) -> str:
    if "TECH" in gap_id or "AUTH" in gap_id:
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
    data_text = lens_text(gap_id, "question", language)
    if data_text:
        return data_text
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
            "GAP-PRD-ROLLOUT-ENVIRONMENTS": "¿Qué ambientes, estrategia de rollout, restricciones de release y criterio de rollback deben quedar confirmados en el PRD?",
            "GAP-BACKLOG-SLICING-READINESS": "¿Cuál es el primer slice de valor observable, qué variantes o reglas pueden diferirse y dónde cortar más pequeño dejaría de aportar valor?",
            "GAP-BACKLOG-ENABLERS": "¿Qué enablers transversales de implementación frontend/backend o arquitectura deben construirse antes para soportar esta funcionalidad, qué scope habilitan y cómo se distinguen de una precondición operacional genérica?",
            "GAP-QUALITY-HANDOFF": "¿Qué flujos críticos, casos borde, datos de prueba, riesgos de regresión y evidencia esperada debería usar Calidad para profundizar cobertura?",
            "GAP-METRIC-DEFINITION": "¿Cómo se define cada métrica/KPI (fórmula, unidad), de qué fuente sale y cuál es su baseline y umbral objetivo?",
            "GAP-AUTH-MODEL": "¿Qué método de autenticación, modelo de permisos y catálogo de roles aplican para esta capacidad?",
            # IMP-344: a specific question instead of the generic fallback
            "GAP-PRD-PERSONA-DETAIL": "Para cada tipo de usuario: ¿qué objetivos y problemas tiene, qué tan familiarizado está con este tipo de herramienta y con qué frecuencia la va a usar?",
            "GAP-PRD-FR-AC": "¿Qué funciones debe ofrecer la solución y, para cada una, qué resultado observable demuestra que funciona?",
            "GAP-PRD-NFR-KPI": "¿Qué objetivos de calidad y KPIs aplican, con su valor objetivo, cómo se mide cada uno y para cuándo?",
            "GAP-PRD-DEPENDENCIES-ROADMAP": "¿Qué necesita la primera versión, qué puede esperar, de qué depende y quién es responsable de cada dependencia?",
            # IMP-349: every lens check has its own question
            "GAP-BUSINESS-RULE-WEAK-WORD-SMELL": "Para cada regla de negocio: ¿qué condición o valor exacto la dispara, qué excepciones tiene y qué debe pasar en cada caso?",
            "GAP-QUALITY-WEAK-WORD-SMELL": "¿Cómo se va a comprobar que la solución funciona bien: qué resultados o valores concretos se esperan?",
            "GAP-HYPOTHETICAL-ANCHOR": "¿Esta necesidad viene de algo que ya pasó? Describir un caso real reciente: cuándo ocurrió, quiénes participaron y qué pasó.",
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
        "GAP-PRD-ROLLOUT-ENVIRONMENTS": "Which environments, rollout strategy, release constraints, and rollback criterion must be confirmed in the PRD?",
        "GAP-BACKLOG-SLICING-READINESS": "What is the first observable value slice, which variants or rules can be deferred, and where would a smaller split stop producing value?",
        "GAP-BACKLOG-ENABLERS": "Which frontend/backend or architecture implementation enablers must be built in advance to support this functionality, what scope do they enable, and how are they different from a generic operational precondition?",
        "GAP-QUALITY-HANDOFF": "Which critical flows, edge cases, test data, regression risks, and evidence expectations should Quality use for deeper coverage?",
        "GAP-METRIC-DEFINITION": "How is each metric/KPI defined (formula, unit), what source does it come from, and what is its baseline and target threshold?",
        "GAP-AUTH-MODEL": "Which authentication method, permission model, and role catalog apply to this capability?",
        # IMP-344: a specific question instead of the generic fallback
        "GAP-PRD-PERSONA-DETAIL": "For each type of user: what are their goals and pain points, how familiar are they with this kind of tool, and how often will they use it?",
        "GAP-PRD-FR-AC": "Which functions must the solution provide, and for each one, what observable result shows it works?",
        "GAP-PRD-NFR-KPI": "Which quality targets and KPIs apply, with their target value, how each one is measured, and by when?",
        "GAP-PRD-DEPENDENCIES-ROADMAP": "What does the first version need, what can wait, what does it depend on, and who owns each dependency?",
        # IMP-349: every lens check has its own question
        "GAP-BUSINESS-RULE-WEAK-WORD-SMELL": "For each business rule: what exact condition or value triggers it, what are the exceptions, and what should happen in each case?",
        "GAP-QUALITY-WEAK-WORD-SMELL": "How will you check that the solution works well: which concrete results or values do you expect?",
        "GAP-HYPOTHETICAL-ANCHOR": "Does this need come from something that has already happened? Please describe a recent real case: when it happened, who was involved, and what happened.",
    }
    return questions.get(gap_id, "What confirmed information resolves this uncertainty?")
