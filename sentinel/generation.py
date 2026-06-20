from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
from pathlib import Path
import re
from typing import Any

from .memory import ContextBroker, get_multi_domain_context
from .backlog_hooks import assert_backlog_privacy_clean
from .backlog_status import apply_lifecycle_to_stories
from .backlog_gates import evaluate_story_gates, update_story_gate_state
from .backlog_rollup import backlog_status
from .core.markdown import frontmatter_list, parse_frontmatter, parse_table_rows
from .discovery import extract_personas, extract_functional_signals, extract_metric_signals, prd_section_for_gap, split_evidence_sentences
from .maturity import evaluate, parse_gap_answers, prd_gate_warnings, prd_section_readiness
from .prd import render_prd_compositions
from .retrieval_plans import compose_plan_query, load_retrieval_plan, select_source_context
from .slicing_model import load_slicing_model
from .slice_plan import generate_slice_plan
from .traceability import add_edge, add_node, nodes_by_type, upsert_node
from .workspace import load_config, read_json, state_path, update_state, workspace_path, write_json


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


def record_regeneration_diff(project_id: str, artifact_label: str, old_text: str, new_text: str) -> str | None:
    """Record a human-readable summary of what changed when an artifact is regenerated (IMP-011).

    Returns the trace node id of the diff record, or None on first generation / no change.
    """
    if not old_text or old_text == new_text:
        return None
    import difflib

    def headings(text: str) -> list[str]:
        return [line.strip() for line in text.splitlines() if line.startswith("#")]

    old_sections, new_sections = headings(old_text), headings(new_text)
    added_sections = [s for s in new_sections if s not in old_sections]
    removed_sections = [s for s in old_sections if s not in new_sections]
    diff = list(difflib.unified_diff(old_text.splitlines(), new_text.splitlines(), lineterm=""))
    added_lines = sum(1 for line in diff if line.startswith("+") and not line.startswith("+++"))
    removed_lines = sum(1 for line in diff if line.startswith("-") and not line.startswith("---"))

    base = workspace_path(project_id)
    out_dir = base / "07_changes" / "04_regeneration"
    out_dir.mkdir(parents=True, exist_ok=True)
    state = read_json(state_path(project_id), {})
    change_id = state.get("last_change_id") or "N/A"
    existing = sorted(out_dir.glob("*.md"))
    out_path = out_dir / f"regen-{len(existing) + 1:03d}-{artifact_label.replace('.', '-')}.md"

    def section_rows(items: list[str]) -> str:
        return "\n".join(f"- {item}" for item in items) or "- None."

    out_path.write_text(
        f"""# Regeneration Diff - {artifact_label}

- Project: `{project_id}`
- Triggering change: `{change_id}`
- Lines added: {added_lines}
- Lines removed: {removed_lines}

## Sections Added

{section_rows(added_sections)}

## Sections Removed

{section_rows(removed_sections)}

Review this artifact against the triggering change before downstream handoff. The regenerated file is the source of truth; this diff is visibility, not authority.
""",
        encoding="utf-8",
    )
    diff_id = add_node(project_id, "DEC", "regeneration_diff", out_path, f"Regeneration diff for {artifact_label}", domain="product")
    if change_id != "N/A":
        add_edge(project_id, change_id, diff_id, "triggers_regeneration")
    ContextBroker(project_id).index_artifact(
        diff_id,
        "regeneration_diff",
        out_path,
        out_path.read_text(encoding="utf-8"),
        domain="product",
        trace_ids=[diff_id] if change_id == "N/A" else [change_id, diff_id],
    )
    return diff_id


def spec_unit_snapshot(base: Path) -> dict[str, dict[str, Any]]:
    units_dir = base / "03_specs" / "units"
    if not units_dir.exists():
        return {}
    snapshot: dict[str, dict[str, Any]] = {}
    for path in sorted(units_dir.glob("SPEC-U-*.md")):
        text = path.read_text(encoding="utf-8")
        unit_id = path.stem
        snapshot[unit_id] = {
            "id": unit_id,
            "path": path,
            "text": text,
            "frontmatter": parse_frontmatter(text),
        }
    return snapshot


def read_spec_units(project_id: str) -> list[dict[str, Any]]:
    base = workspace_path(project_id)
    units_dir = base / "03_specs" / "units"
    units: list[dict[str, Any]] = []
    for path in sorted(units_dir.glob("SPEC-U-*.md")) if units_dir.exists() else []:
        text = path.read_text(encoding="utf-8")
        frontmatter = parse_frontmatter(text)
        unit_id = str(frontmatter.get("id", path.stem)).strip()
        if not re.match(r"^SPEC-U-\d{3}$", unit_id):
            continue
        status = str(frontmatter.get("status", "")).strip().lower()
        if status and status not in {"evidence-backed", "confirmed", "ready"}:
            continue
        units.append(
            {
                "id": unit_id,
                "title": spec_unit_title(text, unit_id),
                "status": status or "evidence-backed",
                "path": path,
                "relative_path": path.relative_to(base).as_posix(),
                "trace_ids": [str(item) for item in frontmatter.get("trace_ids", []) if str(item).strip()],
                "ears": [str(item) for item in frontmatter.get("ears", []) if str(item).strip()],
                "sources": [str(item) for item in frontmatter.get("sources", []) if str(item).strip()],
                "statement": spec_unit_statement(text),
                "pattern": spec_unit_pattern(text),
            }
        )
    return units


def spec_unit_title(text: str, fallback: str) -> str:
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip() or fallback
    return fallback


def spec_unit_statement(text: str) -> str:
    in_requirement = False
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if line.startswith("## "):
            in_requirement = line == "## Normalized Requirement"
            continue
        if not in_requirement or not line.startswith("|"):
            continue
        cells = parse_table_rows(line)[0]
        if len(cells) < 2 or cells[0] in {"EARS ID", "---"}:
            continue
        return cells[1]
    return ""


def spec_unit_pattern(text: str) -> str:
    for line in text.splitlines():
        if line.startswith("- Pattern:"):
            return line.split(":", 1)[1].strip().strip("`")
    return ""


def record_spec_unit_delta(
    project_id: str,
    previous_units: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    if not previous_units:
        return None
    base = workspace_path(project_id)
    current_snapshot = spec_unit_snapshot(base)
    all_ids = sorted(set(previous_units) | set(current_snapshot))
    entries: list[dict[str, Any]] = []
    for unit_id in all_ids:
        previous = previous_units.get(unit_id)
        current = current_snapshot.get(unit_id)
        if previous and not current:
            status = "REMOVED"
        elif current and not previous:
            status = "ADDED"
        elif previous and current and previous["text"] != current["text"]:
            status = "MODIFIED"
        else:
            status = "UNCHANGED"
        entries.append(spec_unit_delta_entry(unit_id, status, previous, current))
    changed = [entry for entry in entries if entry["status"] != "UNCHANGED"]
    path, delta_id = write_spec_unit_delta_report(project_id, entries, changed)
    update_implementation_readiness_stale_units(project_id, changed, path)
    update_state(
        project_id,
        stale_spec_units=changed,
        last_spec_unit_delta_id=delta_id,
        last_spec_unit_delta_path=str(path.as_posix()),
    )
    return {"path": path, "delta_id": delta_id, "entries": entries, "changed": changed}


def spec_unit_delta_entry(
    unit_id: str,
    status: str,
    previous: dict[str, Any] | None,
    current: dict[str, Any] | None,
) -> dict[str, Any]:
    previous_fm = previous.get("frontmatter", {}) if previous else {}
    current_fm = current.get("frontmatter", {}) if current else {}
    frontmatter_changes = changed_frontmatter_fields(previous_fm, current_fm)
    return {
        "unit_id": unit_id,
        "status": status,
        "path": spec_unit_relative_path(current or previous),
        "frontmatter_changes": frontmatter_changes,
        "previous_ears": previous_fm.get("ears", []) if previous_fm else [],
        "current_ears": current_fm.get("ears", []) if current_fm else [],
        "previous_sources": previous_fm.get("sources", []) if previous_fm else [],
        "current_sources": current_fm.get("sources", []) if current_fm else [],
    }


def changed_frontmatter_fields(previous: dict[str, Any], current: dict[str, Any]) -> list[str]:
    keys = sorted(set(previous) | set(current))
    return [key for key in keys if previous.get(key) != current.get(key)]


def spec_unit_relative_path(unit: dict[str, Any] | None) -> str:
    if not unit:
        return ""
    path = Path(str(unit.get("path", ""))).as_posix()
    if "03_specs/" in path:
        return path[path.index("03_specs/") :]
    return path


def write_spec_unit_delta_report(
    project_id: str,
    entries: list[dict[str, Any]],
    changed: list[dict[str, Any]],
) -> tuple[Path, str]:
    base = workspace_path(project_id)
    out_dir = base / "07_changes" / "04_regeneration"
    out_dir.mkdir(parents=True, exist_ok=True)
    state = read_json(state_path(project_id), {})
    change_id = state.get("last_change_id") or "N/A"
    existing = sorted(out_dir.glob("*.md"))
    path = out_dir / f"regen-{len(existing) + 1:03d}-spec-units-delta.md"

    def rows(items: list[dict[str, Any]]) -> str:
        if not items:
            return "| N/A | N/A | N/A | N/A | N/A | N/A |"
        rendered = []
        for item in items:
            rendered.append(
                "| {unit} | {status} | {frontmatter} | {ears} | {sources} | `{path}` |".format(
                    unit=f"`{item['unit_id']}`",
                    status=item["status"],
                    frontmatter=", ".join(f"`{field}`" for field in item["frontmatter_changes"]) or "none",
                    ears=delta_value(item["previous_ears"], item["current_ears"]),
                    sources=delta_value(item["previous_sources"], item["current_sources"]),
                    path=item["path"],
                )
            )
        return "\n".join(rendered)

    path.write_text(
        f"""# Spec Unit Delta - {project_id}

- Project: `{project_id}`
- Triggering change: `{change_id}`
- Changed units: {len(changed)}
- Total units compared: {len(entries)}

## Changed Units

| Unit | Status | Frontmatter Changes | EARS Delta | Source Pointer Delta | Path |
| --- | --- | --- | --- | --- | --- |
{rows(changed)}

## Full Unit Status

| Unit | Status | Frontmatter Changes | EARS Delta | Source Pointer Delta | Path |
| --- | --- | --- | --- | --- | --- |
{rows(entries)}

Use this report to decide which backlog stories or implementation readiness entries need review after regenerating specs. Workspace artifacts remain the source of truth.
""",
        encoding="utf-8",
    )
    delta_id = add_node(project_id, "DEC", "regeneration_diff", path, "Spec unit regeneration delta", domain="product")
    if change_id != "N/A":
        add_edge(project_id, change_id, delta_id, "triggers_regeneration")
    ContextBroker(project_id).index_artifact(
        delta_id,
        "regeneration_diff",
        path,
        path.read_text(encoding="utf-8"),
        domain="product",
        trace_ids=[delta_id] if change_id == "N/A" else [change_id, delta_id],
    )
    return path, delta_id


def delta_value(previous: Any, current: Any) -> str:
    previous_values = previous if isinstance(previous, list) else ([] if previous in (None, "") else [str(previous)])
    current_values = current if isinstance(current, list) else ([] if current in (None, "") else [str(current)])
    if previous_values == current_values:
        return ", ".join(f"`{item}`" for item in current_values) or "none"
    old = ", ".join(f"`{item}`" for item in previous_values) or "none"
    new = ", ".join(f"`{item}`" for item in current_values) or "none"
    return f"{old} -> {new}"


def update_implementation_readiness_stale_units(project_id: str, changed: list[dict[str, Any]], delta_path: Path) -> None:
    path = workspace_path(project_id) / "08_context_packs" / "implementation_readiness.json"
    if not path.exists():
        return
    pack = read_json(path, {})
    if not isinstance(pack, dict):
        return
    pack["stale_spec_units"] = [
        {
            "unit_id": item["unit_id"],
            "status": item["status"],
            "path": item["path"],
            "delta_report": delta_path.relative_to(workspace_path(project_id)).as_posix(),
        }
        for item in changed
    ]
    write_json(path, pack)


def generate_specs(project_id: str) -> dict[str, object]:
    maturity = evaluate(project_id)
    if maturity["readiness"] == "BLOCKED":
        raise RuntimeError("Cannot generate specs while requirement maturity is BLOCKED.")
    base = workspace_path(project_id)
    config = load_config(project_id)
    req_path = base / "02_requirements" / "requirements.md"
    brief_path = base / "02_requirements" / "project-brief.md"
    source_path = brief_path if brief_path.exists() else req_path
    req_text = source_path.read_text(encoding="utf-8")
    raw_dir = base / "00_raw"
    raw_parts = []
    if raw_dir.exists():
        for raw_file in sorted(raw_dir.rglob("*")):
            if raw_file.is_file() and raw_file.suffix.lower() in {".md", ".txt"}:
                raw_parts.append(raw_file.read_text(encoding="utf-8", errors="ignore"))
    evidence_text = "\n\n".join(raw_parts) or req_text
    context = get_multi_domain_context(req_text, project_id)
    generation_context = build_specs_generation_context(project_id, req_text)
    context["prd_sections"] = generation_context["sections"]
    context["ears_requirements"] = load_ears_requirements(project_id)
    seed_text = read_artifact_text(base / "01_discovery" / "identity_seeds.md")
    decision_text = read_artifact_text(base / "01_discovery" / "decisions.md")
    context["gap_answers"] = parse_gap_answers(seed_text + "\n" + decision_text)
    context["raw_text"] = evidence_text
    state = read_json(state_path(project_id), {})
    language = str(state.get("project_language", "es")).lower()
    prd_path = base / "03_specs" / "prd.md"
    specs_path = base / "03_specs" / "specs.md"
    previous_prd = prd_path.read_text(encoding="utf-8") if prd_path.exists() else ""
    previous_specs = specs_path.read_text(encoding="utf-8") if specs_path.exists() else ""
    previous_spec_units = spec_unit_snapshot(base)
    prd_text = render_prd(project_id, req_text, context, source_path.name, language, evidence_text)
    prd_path.write_text(render_prd_compositions(project_id, prd_text), encoding="utf-8")
    prd_readiness = prd_section_readiness(prd_path.read_text(encoding="utf-8"))
    specs_gate = config.get("specs_gate", {}) if isinstance(config.get("specs_gate", {}), dict) else {}
    specs_threshold = float(specs_gate.get("threshold", 0.75))
    specs_strict = bool(specs_gate.get("strict", False))
    below_specs_threshold = float(prd_readiness["coverage_score"]) < specs_threshold
    specs_warnings = prd_gate_warnings(prd_readiness, language) if below_specs_threshold else []
    if specs_strict and below_specs_threshold:
        update_state(
            project_id,
            phase="specs_below_threshold",
            readiness_stage="SPECS_BELOW_THRESHOLD",
            health="DIRTY",
            prd_section_readiness=prd_readiness,
            specs_gate={"threshold": specs_threshold, "strict": specs_strict, "below_threshold": below_specs_threshold},
            specs_gate_warnings=specs_warnings,
        )
        raise RuntimeError("Cannot complete /specs while PRD section readiness is below specs_gate threshold.")
    spec_units = write_spec_units(project_id, context, source_path.name)
    spec_unit_delta = record_spec_unit_delta(project_id, previous_spec_units)
    specs_path.write_text(render_specs(project_id, req_text, context, source_path.name, spec_units), encoding="utf-8")
    record_regeneration_diff(project_id, "prd.md", previous_prd, prd_path.read_text(encoding="utf-8"))
    record_regeneration_diff(project_id, "specs.md", previous_specs, specs_path.read_text(encoding="utf-8"))
    prd_id = add_node(project_id, "PRD", "prd", prd_path, "Human-readable PRD", domain="product")
    spec_id = add_node(project_id, "SPEC", "spec", specs_path, "AI-friendly specification", domain="product")
    parent_trace_ids: list[str] = []
    for req in nodes_by_type(project_id, "requirement"):
        add_edge(project_id, req["id"], prd_id, "elaborates")
        parent_trace_ids.append(req["id"])
    for brief in nodes_by_type(project_id, "project_brief"):
        add_edge(project_id, brief["id"], prd_id, "elaborates")
        parent_trace_ids.append(brief["id"])
    add_edge(project_id, prd_id, spec_id, "agentizes")
    trace_ids = [*parent_trace_ids, prd_id, spec_id]
    broker = ContextBroker(project_id)
    broker.index_artifact(
        prd_id, "prd", prd_path, prd_path.read_text(encoding="utf-8"), trace_ids=trace_ids
    )
    broker.index_artifact(
        spec_id, "spec", specs_path, specs_path.read_text(encoding="utf-8"), trace_ids=trace_ids
    )
    req_path_for_units = base / "02_requirements" / "requirements.md"
    for unit in spec_units:
        unit_id = str(unit["id"])
        unit_path = Path(str(unit["path"]))
        unit_node = upsert_node(
            project_id,
            unit_id,
            "spec_unit",
            unit_path,
            str(unit["title"]),
            status=str(unit["status"]),
            domain="product",
        )
        add_edge(project_id, prd_id, unit_node, "decomposes")
        add_edge(project_id, spec_id, unit_node, "indexes")
        unit_trace_ids = [*trace_ids, unit_node]
        for ears_id in unit.get("ears", []):
            if isinstance(ears_id, str) and EARS_REQUIREMENT_ID_RE.match(ears_id):
                ears_node = upsert_node(
                    project_id,
                    ears_id,
                    "ears_requirement",
                    req_path_for_units,
                    f"{ears_id} normalized EARS requirement",
                    status="confirmed",
                    domain="product",
                )
                add_edge(project_id, unit_node, ears_node, "traces_to")
                unit_trace_ids.append(ears_node)
        broker.index_artifact(
            unit_node,
            "spec_unit",
            unit_path,
            unit_path.read_text(encoding="utf-8"),
            trace_ids=unit_trace_ids,
        )
    gate_result = {"threshold": specs_threshold, "strict": specs_strict, "below_threshold": below_specs_threshold}
    update_state(
        project_id,
        phase="specs_completed",
        health="CLEAN",
        readiness_stage="READY_FOR_BACKLOG",
        prd_section_readiness=prd_readiness,
        specs_gate=gate_result,
        specs_gate_warnings=specs_warnings,
    )
    return {
        "prd_id": prd_id,
        "spec_id": spec_id,
        "prd_path": str(prd_path),
        "path": str(specs_path),
        "prd_section_readiness": prd_readiness,
        "warnings": specs_warnings,
        "specs_gate": gate_result,
        "spec_unit_delta": {
            "path": str(spec_unit_delta["path"].as_posix()),
            "changed": spec_unit_delta["changed"],
        } if spec_unit_delta else None,
    }


def read_artifact_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def generate_backlog(project_id: str, with_task_seeds: bool = False) -> dict[str, str]:
    maturity = evaluate(project_id)
    if maturity["readiness"] == "BLOCKED":
        raise RuntimeError("Cannot generate backlog while requirement maturity is BLOCKED.")
    specs = nodes_by_type(project_id, "spec")
    if not specs:
        generate_specs(project_id)
        specs = nodes_by_type(project_id, "spec")
    base = workspace_path(project_id)
    spec_path = base / "03_specs" / "specs.md"
    prd_path = base / "03_specs" / "prd.md"
    spec_text = spec_path.read_text(encoding="utf-8") if spec_path.exists() else ""
    prd_text = prd_path.read_text(encoding="utf-8") if prd_path.exists() else ""
    backlog_context = build_backlog_generation_context(project_id, spec_text, prd_text)
    story_specs = build_backlog_story_specs(project_id, backlog_context)
    enabler_specs = build_cross_cutting_enabler_specs(project_id, story_specs, backlog_context)
    all_story_specs = [*story_specs, *enabler_specs]
    apply_lifecycle_to_stories(project_id, all_story_specs)
    if with_task_seeds:
        attach_task_seed_contracts(all_story_specs)
    readiness_pack = build_implementation_readiness_pack(project_id, all_story_specs, backlog_context)
    slice_plan = generate_slice_plan(project_id, all_story_specs, readiness_pack)
    backlog_context["implementation_readiness"] = {
        "path": "08_context_packs/implementation_readiness.json",
        "verdict": readiness_pack["verdict"],
    }
    backlog_context["slice_plan"] = {
        "path": "04_backlog/SLICE-PLAN.md",
        "json_path": "08_context_packs/slice_plan.json",
    }
    write_json(base / "08_context_packs" / "backlog_generation.json", backlog_context)

    epic_path = base / "04_backlog" / "EPIC-001.md"
    previous_epic = epic_path.read_text(encoding="utf-8") if epic_path.exists() else ""
    epic_path.write_text(render_epic(project_id, story_specs, backlog_context), encoding="utf-8")
    record_regeneration_diff(project_id, "EPIC-001.md", previous_epic, epic_path.read_text(encoding="utf-8"))
    epic_id = add_node(project_id, "EPIC", "epic", epic_path, "Deliver validated requirement value", domain="product")
    for spec in specs:
        add_edge(project_id, spec["id"], epic_id, "decomposes_to")

    story_ids: list[str] = []
    acceptance_ids: list[str] = []
    active_story_paths: set[Path] = set()
    for index, story_spec in enumerate(story_specs, start=1):
        story_path = base / "04_backlog" / f"US-{index:03d}.md"
        story_path.write_text(render_story(project_id, epic_id, story_spec), encoding="utf-8")
        active_story_paths.add(story_path)
        story_id = add_node(project_id, "US", "user_story", story_path, story_spec["title"], domain=story_spec["domain"])
        story_ids.append(story_id)
        add_edge(project_id, epic_id, story_id, "contains")
        for spec in specs:
            add_edge(project_id, spec["id"], story_id, "decomposes_to")
        for trace_id in story_spec.get("trace", []):
            if re.match(r"^SPEC-U-\d{3}$", str(trace_id)):
                add_edge(project_id, str(trace_id), story_id, "decomposes_to")

        ac_id = add_node(project_id, "AC", "acceptance_criteria", story_path, f"Acceptance criteria for {story_id}", domain="quality")
        acceptance_ids.append(ac_id)
        add_edge(project_id, story_id, ac_id, "validated_by")

    epic_ids = [epic_id]
    if enabler_specs:
        enabler_epic_path = base / "04_backlog" / "EPIC-002-cross-cutting-enablers.md"
        enabler_epic_path.write_text(
            render_enabler_epic(project_id, enabler_specs, story_specs, backlog_context),
            encoding="utf-8",
        )
        enabler_epic_id = add_node(
            project_id,
            "EPIC",
            "epic",
            enabler_epic_path,
            "Cross-cutting enablers for validated requirement value",
            domain="technical",
        )
        epic_ids.append(enabler_epic_id)
        for spec in specs:
            add_edge(project_id, spec["id"], enabler_epic_id, "decomposes_to")
        for index, enabler_spec in enumerate(enabler_specs, start=len(story_specs) + 1):
            story_path = base / "04_backlog" / f"US-{index:03d}.md"
            story_path.write_text(render_story(project_id, enabler_epic_id, enabler_spec), encoding="utf-8")
            active_story_paths.add(story_path)
            story_id = add_node(project_id, "US", "user_story", story_path, enabler_spec["title"], domain="technical")
            story_ids.append(story_id)
            add_edge(project_id, enabler_epic_id, story_id, "contains")
            for enabled in enabler_spec["enables"]:
                add_edge(project_id, story_id, enabled, "enables")
            for spec in specs:
                add_edge(project_id, spec["id"], story_id, "decomposes_to")
            ac_id = add_node(project_id, "AC", "acceptance_criteria", story_path, f"Acceptance criteria for {story_id}", domain="quality")
            acceptance_ids.append(ac_id)
            add_edge(project_id, story_id, ac_id, "validated_by")
        ContextBroker(project_id).index_artifact(
            enabler_epic_id,
            "epic",
            enabler_epic_path,
            enabler_epic_path.read_text(encoding="utf-8"),
            domain="technical",
            trace_ids=[enabler_epic_id, *[item["id"] for item in enabler_specs]],
        )

    for stale_story_path in (base / "04_backlog").glob("US-*.md"):
        if stale_story_path not in active_story_paths:
            stale_story_path.unlink()

    assert_backlog_privacy_clean(project_id)

    broker = ContextBroker(project_id)
    broker.index_artifact(epic_id, "epic", epic_path, epic_path.read_text(encoding="utf-8"), trace_ids=[epic_id, *story_ids])
    for story_id, ac_id, story_spec in zip(story_ids, acceptance_ids, all_story_specs):
        story_path = base / "04_backlog" / f"{story_id}.md"
        if not story_path.exists():
            numeric = int(story_id.split("-", 1)[1])
            story_path = base / "04_backlog" / f"US-{numeric:03d}.md"
        broker.index_artifact(
            story_id,
            "user_story",
            story_path,
            story_path.read_text(encoding="utf-8"),
            domain=story_spec["domain"],
            trace_ids=[epic_id, story_id, ac_id, *story_spec["trace"]],
        )
    board = backlog_status(project_id)
    update_state(
        project_id,
        phase="backlog_completed",
        health="CLEAN",
        metrics={"requirements": 1, "gaps_open": 0, "decisions_pending": 1, "user_stories": len(story_ids), "epics": len(epic_ids)},
    )
    return {
        "epic_id": epic_id,
        "story_id": story_ids[0],
        "acceptance_id": acceptance_ids[0],
        "path": str(epic_path),
        "story_count": str(len(story_ids)),
        "epic_count": str(len(epic_ids)),
        "implementation_readiness": str(base / "08_context_packs" / "implementation_readiness.json"),
        "backlog_board": board["path"],
        "slice_plan": slice_plan["path"],
        "slice_plan_json": slice_plan["json_path"],
        "task_seed_contracts": "enabled" if with_task_seeds else "disabled",
    }


def build_backlog_generation_context(
    project_id: str,
    spec_text: str,
    prd_text: str,
    retrieval_plans_dir: Path | str | None = None,
    plan_override: dict[str, Any] | None = None,
) -> dict[str, Any]:
    broker = ContextBroker(project_id)
    plan = load_retrieval_plan("backlog_generation", retrieval_plans_dir, plan_override)
    source_documents = {"specs.md": spec_text, "prd.md": prd_text}
    sections: dict[str, Any] = {}
    for section, retrieval in plan["sections"].items():
        query = str(retrieval["query"])
        domain = retrieval.get("domain")
        filters = dict(retrieval.get("filters", {}))
        source_context = select_source_context(source_documents, retrieval)
        results = broker.retrieve(
            compose_plan_query(retrieval, source_context),
            "backlog_generation",
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
            "domain": domain or "any",
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
    domain_snapshot = domain_context_snapshot(project_id)
    pack = {
        "project_id": project_id,
        "workflow": "backlog_generation",
        "retrieval_plan": {"workflow": plan["workflow"], "version": plan["version"]},
        "slicing_model": "vertical_value_slices_with_spidr_lawrence_invest",
        "domain_context_snapshot": domain_snapshot,
        "ears_requirements": load_ears_requirements(project_id),
        "sections": sections,
        "domain_context_coverage": [],
        "per_story": {},
    }
    pack["domain_context_coverage"] = build_domain_context_coverage(pack)
    write_json(workspace_path(project_id) / "08_context_packs" / "backlog_generation.json", pack)
    return pack


def build_implementation_readiness_pack(
    project_id: str,
    stories: list[dict[str, Any]],
    backlog_context: dict[str, Any],
) -> dict[str, Any]:
    readiness_items: list[dict[str, Any]] = []
    for story in stories:
        item = implementation_readiness_for_story(story)
        gate_result = evaluate_story_gates(project_id, story, item)
        item["dor"] = gate_result["dor"]
        item["dod"] = gate_result["dod"]
        item["backlog_gate"] = {"threshold": gate_result["threshold"], "strict": gate_result["strict"]}
        story["dor"] = gate_result["dor"]
        story["dod"] = gate_result["dod"]
        update_story_gate_state(project_id, str(story["id"]), gate_result)
        readiness_items.append(item)
    blocker_count = sum(1 for item in readiness_items if item["status"] != "ready")
    verdict = "READY" if blocker_count == 0 else "PARTIAL"
    pending_by_domain: dict[str, int] = {}
    for item in readiness_items:
        for blocker in item["pending"]:
            if blocker.startswith("Pending domain context: "):
                domain = blocker.split(": ", 1)[1]
                pending_by_domain[domain] = pending_by_domain.get(domain, 0) + 1
    summary = {
        "stories_total": len(readiness_items),
        "stories_ready": len(readiness_items) - blocker_count,
        "stories_needing_context": blocker_count,
        "avg_readiness_score": round(
            sum(item["readiness_score"] for item in readiness_items) / len(readiness_items), 3
        ) if readiness_items else 0.0,
        "pending_context_by_domain": pending_by_domain,
    }
    pack = {
        "project_id": project_id,
        "workflow": "implementation_readiness",
        "verdict": verdict,
        "summary": summary,
        "generated_from": {
            "backlog_context_pack": "08_context_packs/backlog_generation.json",
            "domain_context_snapshot": backlog_context.get("domain_context_snapshot", domain_context_snapshot(project_id)),
        },
        "retrieval_contract": {
            "rule": "Execution agents should use these queries before planning, implementing, or testing. Workspace files remain source of truth; memory is only retrieval evidence.",
            "freshness_rule": "If the current domain context snapshot differs from this pack, rerun /reindex and /backlog before implementation handoff.",
        },
        "stories": readiness_items,
    }
    state = read_json(state_path(project_id), {})
    pack["stale_spec_units"] = state.get("stale_spec_units", [])
    path = workspace_path(project_id) / "08_context_packs" / "implementation_readiness.json"
    write_json(path, pack)
    ContextBroker(project_id).index_artifact(
        "IMPL-READINESS",
        "implementation_readiness",
        path,
        path.read_text(encoding="utf-8"),
        domain="delivery",
        trace_ids=[story["id"] for story in stories] or ["IMPL-READINESS"],
    )
    return pack


def read_plan_for_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_path": row.get("source_path", row.get("file_path", "")),
        "section_path": row.get("section_path", ""),
        "line_start": int(row.get("line_start", 0) or 0),
        "line_end": int(row.get("line_end", 0) or 0),
    }


def implementation_readiness_for_story(story: dict[str, Any]) -> dict[str, Any]:
    execution = story.get("execution_contract", {})
    coverage = story.get("domain_coverage", [])
    pending_domains = [
        row.get("domain", "Unknown")
        for row in coverage
        if row.get("status") == "Pending" and row.get("domain") in required_domains_for_story(story)
    ]
    pending_contract = pending_execution_fields(execution)
    blockers = [f"Pending domain context: {domain}" for domain in pending_domains]
    blockers.extend(f"Pending execution field: {field}" for field in pending_contract)
    status = "ready" if not blockers else "needs-context"
    score_basis = len(required_domains_for_story(story)) + 3  # domains + execution contract fields
    readiness_score = round(max(0.0, 1.0 - len(blockers) / score_basis), 3)
    item = {
        "story_id": story["id"],
        "title": story["title"],
        "type": story["type"],
        "status": status,
        "story_status": story.get("status", "Draft"),
        "owner": story.get("owner", ""),
        "readiness_score": readiness_score,
        "readiness": execution.get("readiness", "Needs Domain Context"),
        "required_domains": required_domains_for_story(story),
        "pending": blockers,
        "dependencies": story.get("dependencies", []),
        "enables": story.get("enables", []),
        "parallelization": execution.get("parallelization", ""),
        "execution_contract": execution,
        "retrieval_plan": execution.get("retrieval_plan", []),
        "validation": execution.get("validation", {}),
        "blast_radius": execution.get("blast_radius", []),
        "trace": story.get("trace", []),
        "source_unit": story.get("source_unit", "[PENDING INPUT]"),
        "slicing": story.get("slicing", "[PENDING INPUT]"),
        "slicing_rationale": story.get("slicing_rationale", "[PENDING INPUT]"),
        "context_pack": story.get("context_pack", "08_context_packs/backlog_generation.json"),
        "context_pack_section": story.get("context_pack_section", ""),
    }
    if story.get("task_seed_contract"):
        item["task_seed_contract"] = story["task_seed_contract"]
    return item


TASK_SEED_BOUNDARY_NOTE = (
    "Task seeds are optional implementation intentions for downstream agents. "
    "Ignite does not execute, estimate, assign, schedule or manage these tasks; "
    "downstream planning may expand, reorder or discard them while preserving story scope and traceability."
)


def attach_task_seed_contracts(stories: list[dict[str, Any]]) -> None:
    for story in stories:
        story["task_seed_contract"] = task_seed_contract_for_story(story)


def task_seed_contract_for_story(story: dict[str, Any]) -> dict[str, Any]:
    ac_refs = [str(item.get("id", "")).strip() for item in story.get("acceptance", []) if item.get("id")]
    fail_to_pass = [
        str(item.get("id", "")).strip()
        for item in story.get("acceptance", [])
        if item.get("id") and item.get("classification") == "fail-to-pass"
    ]
    pass_to_pass = [
        str(item.get("id", "")).strip()
        for item in story.get("acceptance", [])
        if item.get("id") and item.get("classification") == "pass-to-pass"
    ]
    evidence = [
        str(item.get("id", "")).strip()
        for item in story.get("acceptance", [])
        if item.get("id") and item.get("classification") == "evidence"
    ]
    surfaces = task_seed_surfaces(story)
    story_id = str(story.get("id", "US-000"))
    seeds = [
        task_seed(
            story_id,
            1,
            "data-contract-intent",
            "Clarify the data, external dependency, or state contract needed before implementing the acceptance path.",
            fail_to_pass or ac_refs,
            surfaces,
            parallelizable=False,
            depends_on=[],
        ),
        task_seed(
            story_id,
            2,
            "service-behavior-intent",
            "Plan the smallest domain/service behavior that satisfies the fail-to-pass acceptance path without expanding scope.",
            fail_to_pass or ac_refs,
            surfaces,
            parallelizable=False,
            depends_on=[f"TSEED-{story_id}-01"],
        ),
        task_seed(
            story_id,
            3,
            "interface-or-workflow-intent",
            "Plan the smallest user-observable interface or workflow change needed for the story boundary.",
            pass_to_pass or fail_to_pass or ac_refs,
            surfaces,
            parallelizable=True,
            depends_on=[f"TSEED-{story_id}-01"],
        ),
        task_seed(
            story_id,
            4,
            "evidence-intent",
            "Prepare downstream test, regression, or acceptance evidence before proposing the story as Done.",
            evidence or ac_refs,
            surfaces,
            parallelizable=True,
            depends_on=[f"TSEED-{story_id}-02", f"TSEED-{story_id}-03"],
        ),
    ]
    return {
        "emitted": True,
        "scope_boundary": TASK_SEED_BOUNDARY_NOTE,
        "source": "Derived from acceptance criteria and Agent Execution Contract critical surfaces.",
        "seeds": seeds,
    }


def task_seed(
    story_id: str,
    order: int,
    kind: str,
    intention: str,
    ac_refs: list[str],
    surfaces: list[str],
    parallelizable: bool,
    depends_on: list[str],
) -> dict[str, Any]:
    return {
        "id": f"TSEED-{story_id}-{order:02d}",
        "order": order,
        "kind": kind,
        "intention": intention,
        "acceptance_criteria": ac_refs,
        "critical_surfaces": surfaces,
        "parallelizable": parallelizable,
        "depends_on": depends_on,
        "not_tasking": "No execution, estimates, assignment, scheduling, or project-task ownership is implied.",
    }


def task_seed_surfaces(story: dict[str, Any]) -> list[str]:
    signal = story.get("execution_contract", {}).get("critical_surfaces", {})
    if not isinstance(signal, dict):
        return ["[PENDING DOMAIN CONTEXT] Critical surfaces are not confirmed."]
    status = str(signal.get("status", "Pending"))
    summary = str(signal.get("summary", "")).strip()
    source = str(signal.get("source", "")).strip()
    if status == "Confirmed" and summary:
        return [safe_cell(f"{source}: {summary}" if source else summary, 220)]
    return ["[PENDING DOMAIN CONTEXT] Critical surfaces are not confirmed."]


def required_domains_for_story(story: dict[str, Any]) -> list[str]:
    required = ["Product", "Quality"]
    if story.get("domain") in {"technical"} or story.get("type") == "cross_cutting_enabler":
        required.append("Technology")
    if story.get("domain") == "design":
        required.append("Design")
    return required


def pending_execution_fields(execution: dict[str, Any]) -> list[str]:
    pending: list[str] = []
    for field in ("commands", "critical_surfaces", "engineering_practices"):
        signal = execution.get(field, {})
        if isinstance(signal, dict) and signal.get("status") == "Pending":
            pending.append(field)
    design_signal = execution.get("design_match", {})
    if isinstance(design_signal, dict) and design_signal.get("status") == "Pending":
        pending.append("design_match")
    return pending


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


def load_ears_requirements(project_id: str) -> list[dict[str, str]]:
    req_path = workspace_path(project_id) / "02_requirements" / "requirements.md"
    if not req_path.exists():
        return []
    return parse_ears_requirements(req_path.read_text(encoding="utf-8"))


def parse_ears_requirements(requirements_text: str) -> list[dict[str, str]]:
    in_section = False
    rows: list[dict[str, str]] = []
    for raw_line in requirements_text.splitlines():
        line = raw_line.strip()
        if line.startswith("## "):
            in_section = line == "## Normalized Requirements (EARS)"
            continue
        if not in_section or not line.startswith("|"):
            continue
        cells = parse_table_rows(line)[0]
        if len(cells) < 4 or cells[0] in {"ID", "---"} or not EARS_REQUIREMENT_ID_RE.match(cells[0]):
            continue
        rows.append(
            {
                "id": cells[0],
                "pattern": cells[1],
                "statement": cells[2],
                "source": cells[3],
            }
        )
    return rows


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
    story = {
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
    return story


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


def build_domain_context_coverage(backlog_context: dict[str, Any]) -> list[dict[str, str]]:
    sections = backlog_context.get("sections", {}) if isinstance(backlog_context, dict) else {}
    domain_specs = [
        ("Product", ("epic_value", "functional_slicing"), "Defines value, scope, slicing, FR/JTBD links and acceptance intent."),
        ("Technology", ("technical_dependencies", "execution_commands", "critical_surfaces", "engineering_practices"), "Defines architecture, commands, affected surfaces, constraints and implementation risks."),
        ("Design", ("ux_states", "design_match"), "Defines journeys, screens, states, components, tokens and interaction rules."),
        ("Quality", ("quality_risks", "regression_contract"), "Defines testability, regression, evidence, test data and quality gates."),
        ("Delivery", ("open_uncertainty",), "Defines blockers, sequencing, dependencies, roadmap and planning uncertainty."),
    ]
    coverage: list[dict[str, str]] = []
    for domain, keys, impact in domain_specs:
        evidence = first_context_result(sections, keys)
        status = "Confirmed" if evidence else "Pending"
        coverage.append(
            {
                "domain": domain,
                "evidence": evidence_label(evidence) if evidence else "[PENDING DOMAIN CONTEXT]",
                "status": status,
                "impact": impact,
            }
        )
    return coverage


def first_context_result(sections: dict[str, Any], keys: tuple[str, ...]) -> dict[str, Any] | None:
    for key in keys:
        section = sections.get(key, {}) if isinstance(sections, dict) else {}
        results = section.get("results", []) if isinstance(section, dict) else []
        if results:
            return results[0]
    return None


def evidence_label(row: dict[str, Any]) -> str:
    artifact_id = str(row.get("artifact_id", "N/A"))
    artifact_type = str(row.get("artifact_type", "artifact"))
    section = str(row.get("section_path", "")).strip()
    if section:
        return f"`{artifact_id}` ({artifact_type}, {section})"
    return f"`{artifact_id}` ({artifact_type})"


def build_agent_execution_contract(
    story: dict[str, Any],
    backlog_context: dict[str, Any],
    domain_coverage: list[dict[str, str]],
) -> dict[str, Any]:
    sections = backlog_context.get("sections", {}) if isinstance(backlog_context, dict) else {}
    technical_ready = coverage_status(domain_coverage, "Technology") == "Confirmed"
    design_ready = coverage_status(domain_coverage, "Design") == "Confirmed"
    quality_ready = coverage_status(domain_coverage, "Quality") == "Confirmed"
    execution_ready = technical_ready and quality_ready
    if story.get("domain") == "design":
        execution_ready = execution_ready and design_ready

    return {
        "readiness": "Ready With Domain Evidence" if execution_ready else "Needs Domain Context",
        "agent_profile": agent_profile_for_story(story),
        "decision_priority": "Business value > correctness > safety/privacy > test evidence > implementation elegance",
        "commands": context_signal(sections, ("execution_commands",), "[PENDING TECHNOLOGY CONTEXT] Provide build, lint, test, typecheck, migration or boot commands."),
        "critical_surfaces": context_signal(sections, ("critical_surfaces", "technical_dependencies"), "[PENDING TECHNOLOGY CONTEXT] Provide affected files, services, APIs, data stores, modules or shared surfaces."),
        "design_match": design_signal_for_story(story, sections),
        "engineering_practices": context_signal(sections, ("engineering_practices",), "[PENDING TECHNOLOGY CONTEXT] Provide engineering handbook, ADRs, style rules, logging/error patterns or repo conventions."),
        "validation": validation_contract_for_story(story),
        "autonomy": autonomy_contract_for_story(story),
        "blast_radius": blast_radius_for_story(story),
        "parallelization": parallelization_note_for_story(story),
        "retrieval_plan": retrieval_plan_for_story(story),
    }


def coverage_status(coverage: list[dict[str, str]], domain: str) -> str:
    for row in coverage:
        if row.get("domain") == domain:
            return row.get("status", "Pending")
    return "Pending"


def context_signal(sections: dict[str, Any], keys: tuple[str, ...], pending: str) -> dict[str, Any]:
    row = first_context_result(sections, keys)
    if not row:
        return {"status": "Pending", "source": "[PENDING DOMAIN CONTEXT]", "summary": pending}
    return {
        "status": "Confirmed",
        "source": evidence_label(row),
        "summary": str(row.get("summary", "Context retrieved"))[:320],
        "anchor": anchor_for_context_row(row),
    }


def anchor_for_context_row(row: dict[str, Any]) -> dict[str, Any]:
    read_plan = row.get("read_plan", {})
    if not isinstance(read_plan, dict):
        read_plan = read_plan_for_row(row)
    return {
        "source_path": str(read_plan.get("source_path", row.get("source_path", row.get("file_path", "")))),
        "section_path": str(read_plan.get("section_path", row.get("section_path", ""))),
        "line_start": int(read_plan.get("line_start", row.get("line_start", 0)) or 0),
        "line_end": int(read_plan.get("line_end", row.get("line_end", 0)) or 0),
    }


def design_signal_for_story(story: dict[str, Any], sections: dict[str, Any]) -> dict[str, Any]:
    if story.get("domain") != "design" and story.get("label") != "Enabler":
        return {"status": "Not Applicable", "source": "N/A", "summary": "No direct design execution contract is required for this story unless design context later marks it as impacted."}
    return context_signal(sections, ("design_match", "ux_states"), "[PENDING DESIGN CONTEXT] Provide prototype, UX states, components, tokens, accessibility or interaction rules.")


def agent_profile_for_story(story: dict[str, Any]) -> str:
    if story.get("type") == "cross_cutting_enabler":
        return "Implementation enabler agent with Technology and Quality review"
    domain = story.get("domain")
    if domain == "technical":
        return "Backend/integration planning agent with Quality verifier"
    if domain == "design":
        return "Frontend/design implementation agent with Quality verifier"
    if domain == "quality":
        return "Quality verifier agent with Product traceability review"
    return "Product-to-implementation planning agent"


def validation_contract_for_story(story: dict[str, Any]) -> dict[str, str]:
    fail_to_pass = [item["id"] for item in story.get("acceptance", []) if item.get("classification") == "fail-to-pass"]
    pass_to_pass = [item["id"] for item in story.get("acceptance", []) if item.get("classification") == "pass-to-pass"]
    evidence = [item["id"] for item in story.get("acceptance", []) if item.get("classification") == "evidence"]
    return {
        "fail_to_pass": ", ".join(fail_to_pass) or "[PENDING QUALITY CONTEXT]",
        "pass_to_pass": ", ".join(pass_to_pass) or "[PENDING QUALITY CONTEXT]",
        "evidence": ", ".join(evidence) or "[PENDING QUALITY CONTEXT]",
    }


def autonomy_contract_for_story(story: dict[str, Any]) -> dict[str, list[str]]:
    return {
        "always": [
            "Preserve trace IDs in implementation notes, tests or evidence.",
            "Write or update tests/evidence for the acceptance criteria before marking the story done.",
            "Use retrieved domain context and workspace source files as authority.",
        ],
        "ask_first": [
            "Changing database schemas, auth/permission behavior, external contracts, deployment settings or shared platform configuration.",
            "Adding new dependencies or expanding scope beyond the story boundary.",
            "Editing files or surfaces not cited by Technology/Design context when the blast radius is unclear.",
        ],
        "never": [
            "Invent missing Technology, Design or Quality context.",
            "Commit credentials, private URLs, raw payloads, account IDs or sensitive client facts.",
            "Modify unrelated flows to make the story pass.",
        ],
    }


def blast_radius_for_story(story: dict[str, Any]) -> list[str]:
    return [
        "Keep changes inside the confirmed capability boundary for this story.",
        "Do not alter upstream discovery, PRD or specs without a traced /sync or gap-resolution event.",
        "Treat unlisted shared systems, auth flows, data contracts, design system foundations and deployment settings as out of scope unless domain context explicitly includes them.",
    ]


def parallelization_note_for_story(story: dict[str, Any]) -> str:
    dependencies = story.get("dependencies", [])
    enables = story.get("enables", [])
    if enables:
        return f"Build before dependent stories when planning execution. Enables: {', '.join(enables)}."
    if dependencies:
        return f"Sequence after dependencies are accepted or stubbed with explicit contracts: {', '.join(dependencies)}."
    return "Can be planned as an early slice if domain context is sufficient and no shared-surface conflict is detected."


def retrieval_plan_for_story(story: dict[str, Any]) -> list[dict[str, str]]:
    story_id = story["id"]
    title = story["title"]
    plan = [
        {
            "agent": "Planner",
            "workflow": "planning",
            "query": f"{story_id} {title} dependencies sequencing parallelization blast radius",
            "domain": "any",
            "expected_evidence": "Dependencies, blockers, enables edges, sequencing and scope boundaries.",
            "required_before": "planning",
        },
        {
            "agent": "QA",
            "workflow": "quality",
            "query": f"{story_id} {title} fail-to-pass pass-to-pass regression evidence test data acceptance",
            "domain": "quality",
            "expected_evidence": "Acceptance criteria classifications, regression expectations, evidence and test data.",
            "required_before": "test design",
        },
    ]
    if story.get("domain") in {"technical"} or story.get("type") == "cross_cutting_enabler":
        plan.append(
            {
                "agent": "Technology",
                "workflow": "implementation",
                "query": f"{story_id} {title} architecture commands critical files api data contracts failure behavior",
                "domain": "technical",
                "expected_evidence": "Commands, affected surfaces, API/data contracts, engineering practices and failure behavior.",
                "required_before": "implementation",
            }
        )
    if story.get("domain") == "design":
        plan.append(
            {
                "agent": "Design/Frontend",
                "workflow": "frontend",
                "query": f"{story_id} {title} journey screens states components tokens validation accessibility",
                "domain": "design",
                "expected_evidence": "Screens, UX states, component mapping, tokens, accessibility and interaction rules.",
                "required_before": "frontend implementation",
            }
        )
    return plan


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


def build_specs_generation_context(
    project_id: str,
    req_text: str,
    retrieval_plans_dir: Path | str | None = None,
    plan_override: dict[str, Any] | None = None,
) -> dict[str, Any]:
    broker = ContextBroker(project_id)
    plan = load_retrieval_plan("specs_generation", retrieval_plans_dir, plan_override)
    source_documents = {"requirements-context": req_text}
    sections: dict[str, Any] = {}
    for section, retrieval in plan["sections"].items():
        query = str(retrieval["query"])
        filters = dict(retrieval.get("filters", {}))
        source_context = select_source_context(source_documents, retrieval)
        results = broker.retrieve(
            compose_plan_query(retrieval, source_context),
            "specs_generation",
            limit=int(retrieval["limit"]),
            domain=retrieval.get("domain"),
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
            "domain": retrieval.get("domain") or "any",
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
    coverage_map: dict[str, str] = {}
    for section, payload in sections.items():
        count = len(payload.get("results", []))
        payload["result_count"] = count
        payload["evidence_strength"] = "strong" if count >= 3 else ("weak" if count else "none")
        coverage_map[section] = payload["evidence_strength"]
    covered = sum(1 for strength in coverage_map.values() if strength != "none")
    pack = {
        "project_id": project_id,
        "workflow": "specs_generation",
        "retrieval_plan": {"workflow": plan["workflow"], "version": plan["version"]},
        "coverage_map": coverage_map,
        "coverage_score": round(covered / len(coverage_map), 3) if coverage_map else 0.0,
        "sections_total": len(coverage_map),
        "sections_with_evidence": covered,
        "sections": sections,
    }
    write_json(workspace_path(project_id) / "08_context_packs" / "specs_generation.json", pack)
    return pack


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
    from .assumptions import render_prd_assumption_rows

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


def write_spec_units(project_id: str, context: dict[str, object], source_name: str) -> list[dict[str, object]]:
    base = workspace_path(project_id)
    units_dir = base / "03_specs" / "units"
    units_dir.mkdir(parents=True, exist_ok=True)
    units = build_spec_units(context, source_name)
    active_paths: set[Path] = set()
    for unit in units:
        path = units_dir / f"{unit['id']}.md"
        unit["path"] = path
        path.write_text(render_spec_unit(project_id, unit), encoding="utf-8")
        active_paths.add(path)
    for stale in units_dir.glob("SPEC-U-*.md"):
        if stale not in active_paths:
            stale.unlink()
    return units


def build_spec_units(context: dict[str, object], source_name: str) -> list[dict[str, object]]:
    rows = context.get("ears_requirements", []) if isinstance(context, dict) else []
    if not isinstance(rows, list):
        return []
    units: list[dict[str, object]] = []
    for index, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            continue
        ears_id = str(row.get("id", "")).strip()
        statement = str(row.get("statement", "")).strip()
        if not EARS_REQUIREMENT_ID_RE.match(ears_id) or not statement:
            continue
        unit_id = f"SPEC-U-{len(units) + 1:03d}"
        units.append(
            {
                "id": unit_id,
                "title": f"{unit_id} - {ears_id}",
                "status": "evidence-backed",
                "trace_ids": ["REQ-001", "PRD-001", "SPEC-001", ears_id],
                "ears": [ears_id],
                "sources": [
                    "02_requirements/requirements.md#normalized-requirements-ears",
                    f"02_requirements/{source_name}",
                    "03_specs/prd.md#4-functional-requirements",
                ],
                "pattern": str(row.get("pattern", "")).strip(),
                "statement": statement,
                "source": str(row.get("source", "")).strip(),
            }
        )
    return units


def render_spec_unit(project_id: str, unit: dict[str, object]) -> str:
    trace_ids = [str(item) for item in unit.get("trace_ids", []) if str(item).strip()]
    ears_ids = [str(item) for item in unit.get("ears", []) if str(item).strip()]
    sources = [str(item) for item in unit.get("sources", []) if str(item).strip()]
    source_rows = "\n".join(f"| `{source}` | Pointer |" for source in sources)
    ears_rows = "\n".join(f"| `{ears_id}` | {safe_cell(str(unit.get('statement', '')), 280)} |" for ears_id in ears_ids)
    return f"""---
id: {unit['id']}
status: {unit['status']}
trace_ids:
{frontmatter_list(trace_ids)}
ears:
{frontmatter_list(ears_ids)}
sources:
{frontmatter_list(sources)}
---

# {unit['title']}

## Evidence Basis

| Source | Anchor |
| --- | --- |
{source_rows or "| `[PENDING INPUT]` | No source anchor was available. |"}

## Normalized Requirement

| EARS ID | Statement |
| --- | --- |
{ears_rows or "| `[PENDING INPUT]` | No confirmed EARS row was available. |"}

## Execution Pointer

- Project: `{project_id}`
- Pattern: `{unit.get('pattern', 'unknown')}`
- Source answer: {unit.get('source', '`02_requirements/requirements.md`')}
- Use this unit as the bounded execution context for backlog slicing. Retrieve domain context only for the surfaces, risks, and validation evidence needed by this statement.
- Missing implementation detail remains a `GAP-*` or `[PENDING DOMAIN CONTEXT]`; do not infer contracts, screens, data ownership, or rollout from this unit alone.
"""


def render_spec_units_index(spec_units: list[dict[str, object]] | None) -> str:
    if not spec_units:
        return "`[PENDING INPUT]` - no evidence-backed spec units exist yet. Confirm EARS rows or source-backed functional statements before treating specs as decomposed."
    rows = []
    for unit in spec_units:
        ears = ", ".join(f"`{item}`" for item in unit.get("ears", [])) or "`N/A`"
        path = Path(str(unit.get("path", ""))).as_posix()
        if "03_specs/" in path:
            path = path[path.index("03_specs/") :]
        rows.append(f"| `{unit['id']}` | {safe_cell(str(unit.get('statement', '')), 180)} | {ears} | `{path}` |")
    return "| Unit ID | Execution Slice | EARS Trace | File |\n| --- | --- | --- | --- |\n" + "\n".join(rows)


def render_backlog_seed_rows(spec_units: list[dict[str, object]] | None) -> str:
    if not spec_units:
        return "| `[PENDING INPUT]` | No evidence-backed unit exists yet. Resolve functional/acceptance evidence before deriving backlog items. | Follow-up | `GAP-PRD-FR-AC` |"
    rows = []
    for unit in spec_units:
        ears = ", ".join(f"`{item}`" for item in unit.get("ears", [])) or "`N/A`"
        rows.append(
            f"| `{unit['id']}` | Slice the behavior described by this unit into the smallest meaningful value story. | User Story Candidate | {ears} |"
        )
    return "\n".join(rows)


def render_specs(project_id: str, req_text: str, context: dict[str, object], source_name: str, spec_units: list[dict[str, object]] | None = None) -> str:
    ears_block = render_ears_requirements_table(context)
    ears_ids = ears_trace_ids(context)
    ears_trace = ", ".join(f"`{item}`" for item in ears_ids) or "`N/A`"
    unit_index = render_spec_units_index(spec_units)
    return f"""# Specs - {project_id}

## Spec Contract

- Purpose: provide an agent-friendly execution contract for backlog generation.
- Human PRD: `03_specs/prd.md`
- Mature source: `02_requirements/{source_name}`
- Trace anchors: `REQ-001`, `PRD-001`, `SPEC-001`
- Context pack: `08_context_packs/specs_generation.json`
- Rule: agents must retrieve focused context before expanding backlog slices. Do not reread the whole workspace unless the retrieval pack is insufficient.
- Unit rule: execution detail lives in `03_specs/units/SPEC-U-NNN.md`; this file is the index and handoff contract.

## Requirement Snapshot

The mature requirement remains authoritative in `02_requirements/{source_name}`. This spec keeps only the execution signals agents need before progressive disclosure.

{bounded_text(req_text, 2200)}

## Backlog-Relevant Contract

| Contract Item | Rule |
| --- | --- |
| Source hierarchy | Workspace files win over memory. PRD/specs summarize, they do not replace source evidence. |
| Traceability | Every epic/story/AC must cite `REQ-001`, `PRD-001`, `SPEC-001`, and at least one FR/JTBD/rule where applicable. When confirmed EARS rows exist, cite the relevant `REQ-EARS-*` IDs too. |
| Missing evidence | Keep `[PENDING INPUT]` or create/follow a `GAP-*`; do not invent. |
| Story size | `Small` means the smallest independently meaningful, testable, useful slice. Do not split into micro-stories that no longer produce value or reduce a named risk. |
| Cross-cutting enablers | Enablers may live in a separate epic only when they are implementation work built in advance to support confirmed functionality across stories, epics, FRs, or implementation surfaces. They must reduce concrete risk/dependency and have objective acceptance evidence. |
| Preconditions | Generic access, environment availability, broad infrastructure readiness, or vague setup are preconditions/external tasks unless tied to confirmed project functionality and implementation evidence. |
| Privacy | Do not include sensitive client data, credentials, URLs, account IDs, or raw payloads in backlog artifacts. |

## Spec Units

{unit_index}

## Confirmed EARS Requirements

These rows are parsed from `02_requirements/requirements.md` and remain source-of-truth there. Specs and backlog cite their `REQ-EARS-*` IDs so testable statements survive downstream handoff.

{ears_block or "`[PENDING INPUT]` - no confirmed EARS statements are present in `02_requirements/requirements.md`."}

## Progressive Disclosure Context Map

{render_prd_section_context(context)}

## Retrieval Plan For Backlog Agents

| Need | Suggested `/retrieve` Query | Filters | Use In Backlog |
| --- | --- | --- | --- |
| Epic value and MVP | `business outcome scope mvp kpi users` | `--workflow backlog --domain business --summary-only` | Epic outcome and priority |
| FR and AC slicing | `functional requirements acceptance criteria given when then business rules` | `--workflow backlog --domain product` | Story boundaries and ACs |
| Technical dependencies | `architecture integrations dependencies data ownership contracts failure behavior` | `--workflow backlog --domain technical` | Backend/technical stories and blockers |
| UX stories | `journey screens states validations copy accessibility unchanged behavior` | `--workflow backlog --domain design` | Frontend stories and UX acceptance |
| Quality coverage | `acceptance testability edge cases regression test data evidence` | `--workflow backlog --domain quality` | ACs, TC seeds, readiness audit |
| Open gaps | `pending input prd gaps dependencies roadmap nfr kpi` | `--workflow backlog --artifact-type gap_report` | Blockers, spikes, follow-up stories |
| Enabler boundary | `SAD architecture as-is to-be frontend backend prototype auth data integration audit observability enabler precondition` | `--workflow backlog --summary-only` | Decide whether a cross-cutting enabler epic is valid |

## Backlog Seeds

Backlog seeds are derived from evidence-backed spec units. If no unit exists, backlog agents must work from pending inputs and focused retrieval rather than fixed placeholder stories.

| Source Unit | Candidate Item | Type | Trace |
| --- | --- | --- | --- |
{render_backlog_seed_rows(spec_units)}

## Decision And Assumption Trail

| Source | Type | Statement | Risk If Wrong |
| --- | --- | --- | --- |
| Sentinel invariant | Rule | Any detail not present in seeds, source input, spec units, or domain context remains pending confirmation. | Downstream backlog may require rework after `/sync`. |
| PRD readiness | Rule | PRD-generated FR/JTBD/NFR structure must be checked against evidence before slicing. | Stories may need refinement if PRD readiness gaps remain. |

## Traceability

- Parent requirement: `REQ-001`
- EARS requirements: {ears_trace}
- Parent PRD: `PRD-001`
- Spec units: {", ".join(f"`{unit['id']}`" for unit in (spec_units or [])) or "`[PENDING INPUT]`"}
- Mature brief: `02_requirements/project-brief.md` when present
- Context pack: `08_context_packs/specs_generation.json`
- Downstream artifacts: epics, user stories, acceptance criteria, tests, and traceability matrix.
"""


def render_epic(project_id: str, stories: list[dict[str, Any]], backlog_context: dict[str, Any]) -> str:
    story_sections = "\n\n".join(render_story_section(story) for story in stories)
    story_rows = "\n".join(
        f"| `{story['id']}` | {story['type']} | {story['title']} | {story['label']} | {story['slicing']} | {', '.join(story['dependencies']) or 'None'} | {', '.join(story['trace'])} |"
        for story in stories
    )
    domain_coverage = stories[0].get("domain_coverage", build_domain_context_coverage(backlog_context)) if stories else build_domain_context_coverage(backlog_context)
    readiness = backlog_context.get("implementation_readiness", {})
    ears_block = render_ears_requirements_table(backlog_context)
    trace_frontmatter = frontmatter_list(["REQ-001", *ears_trace_ids(backlog_context), "PRD-001", "SPEC-001"])
    slicing_model = load_slicing_model()
    return f"""---
id: EPIC-001
project: {project_id}
status: draft
priority: Must Have
trace:
{trace_frontmatter}
context_pack: 08_context_packs/backlog_generation.json
slicing_model: vertical-value-slices
---

# EPIC-001 - Deliver Validated Requirement Value

## Outcome

Deliver the first ordered set of vertical slices derived from evidence-backed Spec Units, proving the mature requirement can create user and business value while preserving traceability for downstream AI planning, implementation, and testing agents.

## Source And Retrieval

| Field | Value |
| --- | --- |
| Project | `{project_id}` |
| Primary sources | `02_requirements/project-brief.md`, `03_specs/prd.md`, `03_specs/specs.md` |
| Context pack | `08_context_packs/backlog_generation.json` |
| Implementation readiness | `08_context_packs/implementation_readiness.json` ({readiness.get('verdict', 'PENDING')}) |
| Generation rule | Use focused local retrieval before slicing. Workspace files remain source of truth; memory is a retrieval aid. |
| Privacy | Do not copy credentials, private URLs, raw payloads, account IDs, or confidential client-specific facts into backlog artifacts. |

## Confirmed EARS Requirements

These normalized statements come from `02_requirements/requirements.md`. Stories and acceptance criteria should preserve applicable `REQ-EARS-*` IDs when planning or testing the backlog.

{ears_block or "`[PENDING INPUT]` - no confirmed EARS statements are present in `02_requirements/requirements.md`."}

## Domain Context Coverage

Backlog generation consumes living domain context when Technology, Design, Quality, Delivery or other roles add files to the workspace and those files are ingested or synced. The backlog cites retrieved evidence when available and leaves `[PENDING DOMAIN CONTEXT]` when a domain contract is still missing.

{render_domain_context_coverage(domain_coverage)}

## Epic Scope

### In Scope

- End-to-end functional slices derived from confirmed `SPEC-U-*` units.
- Acceptance criteria in declarative Given/When/Then form.
- Agent execution contracts derived from retrieved domain context, or explicit pending markers when context is missing.
- Dependencies, assumptions, readiness and done checks visible to humans and AI agents.
- Explicit `[PENDING INPUT]` markers when context was not retrieved or not confirmed.

### Out Of Scope

- Layer-only implementation tasks unless they are framed as spikes or scaffolding needed to unlock a value slice.
- Unconfirmed enhancements, inferred business rules, or low-level implementation contracts that belong in domain context packs.
- Rewriting upstream discovery, PRD, or specs without a `/sync` or gap-resolution event.

## Slicing Strategy

{render_slicing_strategy_table(slicing_model)}

## Story Map

| Story | Type | Title | Label | Slicing Pattern | Dependencies | Trace |
| --- | --- | --- | --- | --- | --- | --- |
{story_rows}

## Cross-Cutting Enabler Boundary

{render_enabler_boundary(slicing_model)}

## Retrieved Context Summary

{render_backlog_context_summary(backlog_context)}

## Stories

{story_sections}

## Epic Readiness Checklist

- [ ] Each story is traceable to `REQ-001`, `PRD-001`, `SPEC-001`, and at least one confirmed `SPEC-U-*` or explicit `[PENDING INPUT]` gap.
- [ ] Each story has declarative acceptance criteria with happy, validation, failure/recovery and quality evidence paths.
- [ ] Dependencies and pending context are explicit.
- [ ] No story is only a technical layer unless marked as a spike/scaffolding exception.
- [ ] The epic can be handed to planning, implementation and test agents without loading the entire workspace.
"""


def render_slicing_strategy_table(slicing_model: dict[str, Any]) -> str:
    rows = [
        f"| {row['heuristic']} | {row['applies']} |"
        for row in slicing_model.get("strategy_rows", [])
    ]
    return "| Heuristic | How Sentinel Applies It |\n| --- | --- |\n" + "\n".join(rows)


def render_enabler_boundary(slicing_model: dict[str, Any]) -> str:
    paragraphs = slicing_model.get("enabler_boundary", {}).get("paragraphs", [])
    return "\n\n".join(str(item) for item in paragraphs)


def render_enabler_epic(
    project_id: str,
    enablers: list[dict[str, Any]],
    value_stories: list[dict[str, Any]],
    backlog_context: dict[str, Any],
) -> str:
    story_sections = "\n\n".join(render_story_section(story) for story in enablers)
    rows = "\n".join(
        f"| `{story['id']}` | {story['title']} | {', '.join(story['enables'])} | {story['slicing']} | {', '.join(story['trace'])} |"
        for story in enablers
    )
    value_rows = "\n".join(f"| `{story['id']}` | {story['title']} |" for story in value_stories)
    domain_coverage = enablers[0].get("domain_coverage", build_domain_context_coverage(backlog_context)) if enablers else build_domain_context_coverage(backlog_context)
    ears_block = render_ears_requirements_table(backlog_context)
    trace_frontmatter = frontmatter_list(["REQ-001", *ears_trace_ids(backlog_context), "PRD-001", "SPEC-001"])
    return f"""---
id: EPIC-002
project: {project_id}
status: draft
priority: Must Have
type: cross_cutting_enabler_epic
trace:
{trace_frontmatter}
context_pack: 08_context_packs/backlog_generation.json
---

# EPIC-002 - Cross-Cutting Enablers For Validated Requirement Value

## Boundary Rule

This epic exists only for implementation enablers that must be built in advance to support the functionality being built in `EPIC-001` or the confirmed project scope. It must not collect generic infrastructure, vague setup, or broad platform aspirations.

## Domain Context Coverage

{render_domain_context_coverage(domain_coverage)}

## Confirmed EARS Requirements

{ears_block or "`[PENDING INPUT]` - no confirmed EARS statements are present in `02_requirements/requirements.md`."}

## Accepted Enabler Test

An item belongs here only when all checks pass:

- It supports a named story, epic, FR, capability, or implementation surface inside the confirmed project boundary.
- It reduces a concrete dependency, risk, contract uncertainty, permission concern, data need, UX foundation need, backend/frontend foundation need, or evidence need.
- It has objective acceptance criteria.
- It is inside the project boundary confirmed by discovery/specs.
- It is not merely a precondition such as "environment exists", "make an internal tool accessible", or "internal tool is accessible".

## Value Stories Enabled

| Story | Title |
| --- | --- |
{value_rows}

## Enabler Story Map

| Story | Title | Enables | Slicing Pattern | Trace |
| --- | --- | --- | --- | --- |
{rows}

## Retrieved Context Summary

{render_backlog_context_summary(backlog_context)}

## Stories

{story_sections}
"""


def render_story_section(story: dict[str, Any]) -> str:
    dependencies = ", ".join(story["dependencies"]) or "None"
    acceptance = "\n\n".join(render_gherkin_criterion(item) for item in story["acceptance"])
    owner = story.get("owner") or "[UNASSIGNED]"
    dor = story.get("dor", {})
    dod = story.get("dod", {})
    return f"""### {story['id']} - {story['title']} [Label: {story['label']}]

**Description:** {story['description']}

**Lifecycle:** {story.get('status', 'Draft')} / {owner}

**Narrative:**
As a target user,
I want {story['goal'].lower()},
So that {story['benefit'].lower()}

**Slicing Pattern:** {story['slicing']}

**Slicing Rationale:** {story.get('slicing_rationale', '[PENDING INPUT]')}

**Type:** {story['type']}

**Dependencies:** {dependencies}

**Enables:** {", ".join(story.get("enables", [])) or "N/A"}

**Context Used:**
| Need | Artifact | Signal |
| --- | --- | --- |
| {story['context']['need']} | `{story['context']['artifact_id']}` ({story['context']['artifact_type']}) | {safe_cell(story['context']['summary'], 220)} |

**Domain Context Coverage:**

{render_domain_context_coverage(story.get('domain_coverage', []))}

**Agent Execution Contract:**

{render_agent_execution_contract(story.get('execution_contract', {}))}

**Retrieval Plan For Execution Agents:**

{render_execution_retrieval_plan(story.get('execution_contract', {}).get('retrieval_plan', []))}

{render_task_seed_contract_section(story.get('task_seed_contract'), '**Task Seed Contract:**')}

**In Scope:**
- The smallest user-observable behavior that satisfies `{story['fr']}`.
- Required validation, recoverable failure behavior and trace evidence for this slice.
- Domain context cited above, or `[PENDING INPUT]` if the evidence is missing.

**Out Of Scope:**
- Unconfirmed variations, optimizations or implementation details not required for this slice.
- Sensitive raw data, credentials, private URLs or client-specific operational facts.

**Acceptance Criteria:**

{acceptance}

**Definition Of Ready:**
- {gate_checkbox(dor, 'readiness_score')} Product, design, technology and quality context is cited or explicitly pending.
- {gate_checkbox(dor, 'slicing_pattern_assigned')} Dependencies are known and do not hide a layer-only prerequisite.
- {gate_checkbox(dor, 'acceptance_criteria_classified')} Acceptance criteria are testable without reading the full workspace.
- {gate_checkbox(dor, 'no_blocking_trace_gaps')} Open gaps or assumptions are visible before planning.

{render_gate_missing_block('DoR', dor)}

**Definition Of Done:**
- {gate_checkbox(dod, 'acceptance_evidence_traced')} Code and artifact review completed.
- {gate_checkbox(dod, 'acceptance_evidence_traced')} Happy, validation and failure/recovery paths verified.
- {gate_checkbox(dod, 'acceptance_evidence_traced')} Trace IDs remain visible in implementation notes, tests or evidence.
- {gate_checkbox(dod, 'ready_gate_passed')} No unrelated scope was added during implementation.

{render_gate_missing_block('DoD', dod)}

**Traceability:** {", ".join(story['trace'])}
"""


def gate_checkbox(gate: dict[str, Any], key: str) -> str:
    for item in gate.get("items", []) if isinstance(gate, dict) else []:
        if item.get("key") == key:
            return "[x]" if item.get("passed") else "[ ]"
    return "[ ]"


def render_gate_missing_block(label: str, gate: dict[str, Any]) -> str:
    missing = gate.get("missing", []) if isinstance(gate, dict) else []
    if not missing:
        return f"**{label} Gate:** Passed."
    rows = "\n".join(f"- {item}" for item in missing)
    return f"**{label} Gate Missing Items:**\n{rows}"


def render_gherkin_criterion(criterion: dict[str, str]) -> str:
    classification = criterion.get("classification", "acceptance")
    return f"""> **{criterion['id']} - {criterion['name']} [{classification}]:**
> Given {criterion['given']},
> When {criterion['when']},
> Then {criterion['then']}."""


def render_domain_context_coverage(coverage: list[dict[str, str]]) -> str:
    if not coverage:
        return "| Domain | Evidence Used | Status | Impact |\n| --- | --- | --- | --- |\n| All | [PENDING DOMAIN CONTEXT] | Pending | No domain coverage was available at generation time. |"
    rows = "\n".join(
        f"| {row.get('domain', 'Unknown')} | {row.get('evidence', '[PENDING DOMAIN CONTEXT]')} | {row.get('status', 'Pending')} | {safe_cell(row.get('impact', ''), 180)} |"
        for row in coverage
    )
    return f"""| Domain | Evidence Used | Status | Impact |
| --- | --- | --- | --- |
{rows}"""


def render_agent_execution_contract(contract: dict[str, Any]) -> str:
    if not contract:
        return "[PENDING DOMAIN CONTEXT] Agent execution contract was not generated."
    commands = contract.get("commands", {})
    critical_surfaces = contract.get("critical_surfaces", {})
    design_match = contract.get("design_match", {})
    engineering_practices = contract.get("engineering_practices", {})
    validation = contract.get("validation", {})
    autonomy = contract.get("autonomy", {})
    return f"""| Field | Value |
| --- | --- |
| Readiness | {contract.get('readiness', 'Needs Domain Context')} |
| Agent profile | {contract.get('agent_profile', 'Planning agent')} |
| Decision priority | {contract.get('decision_priority', 'Business value > correctness > safety > evidence')} |
| Commands | {render_context_signal_inline(commands)} |
| Critical surfaces | {render_context_signal_inline(critical_surfaces)} |
| Design match | {render_context_signal_inline(design_match)} |
| Engineering practices | {render_context_signal_inline(engineering_practices)} |
| Fail-to-Pass | {validation.get('fail_to_pass', '[PENDING QUALITY CONTEXT]')} |
| Pass-to-Pass | {validation.get('pass_to_pass', '[PENDING QUALITY CONTEXT]')} |
| Evidence | {validation.get('evidence', '[PENDING QUALITY CONTEXT]')} |
| Parallelization | {safe_cell(contract.get('parallelization', ''), 220)} |

**Autonomy Limits**

- Always: {', '.join(autonomy.get('always', []))}
- Ask First: {', '.join(autonomy.get('ask_first', []))}
- Never: {', '.join(autonomy.get('never', []))}

**Blast Radius**

{render_bullet_list(contract.get('blast_radius', []))}
"""


def render_execution_retrieval_plan(plan: list[dict[str, str]]) -> str:
    if not plan:
        return "| Agent | Domain | Query | Expected Evidence | Required Before |\n| --- | --- | --- | --- | --- |\n| Planner | any | [PENDING CONTEXT QUERY] | [PENDING CONTEXT] | implementation |"
    rows = "\n".join(
        f"| {item.get('agent', 'Execution agent')} | {item.get('domain', 'any')} | `{safe_cell(item.get('query', ''), 220)}` | {safe_cell(item.get('expected_evidence', ''), 180)} | {item.get('required_before', 'implementation')} |"
        for item in plan
    )
    return f"""| Agent | Domain | Query | Expected Evidence | Required Before |
| --- | --- | --- | --- | --- |
{rows}"""


def render_task_seed_contract_section(contract: object, heading: str = "## Task Seed Contract") -> str:
    if not isinstance(contract, dict) or not contract.get("emitted"):
        return ""
    seeds = contract.get("seeds", [])
    rows = "\n".join(render_task_seed_row(seed) for seed in seeds if isinstance(seed, dict)) if isinstance(seeds, list) else ""
    rows = rows or "| N/A | N/A | N/A | N/A | N/A | N/A |"
    return f"""{heading}

> {contract.get('scope_boundary', TASK_SEED_BOUNDARY_NOTE)}

Source: {contract.get('source', 'Derived from acceptance criteria and critical surfaces.')}

| Seed | Kind | Intention | AC Trace | Critical Surfaces | Parallelizable |
| --- | --- | --- | --- | --- | --- |
{rows}
"""


def render_task_seed_row(seed: dict[str, Any]) -> str:
    ac_refs = ", ".join(f"`{item}`" for item in seed.get("acceptance_criteria", [])) or "`[PENDING AC]`"
    surfaces = "; ".join(str(item) for item in seed.get("critical_surfaces", [])) or "[PENDING DOMAIN CONTEXT]"
    parallelizable = "yes" if seed.get("parallelizable") else "no"
    return (
        f"| `{seed.get('id', 'TSEED-UNKNOWN')}` | {seed.get('kind', 'intent')} | "
        f"{safe_cell(seed.get('intention', ''), 220)} | {ac_refs} | {safe_cell(surfaces, 220)} | {parallelizable} |"
    )


def render_context_signal_inline(signal: dict[str, Any]) -> str:
    status = signal.get("status", "Pending")
    source = signal.get("source", "[PENDING DOMAIN CONTEXT]")
    summary = safe_cell(signal.get("summary", ""), 220)
    anchor = render_anchor_inline(signal.get("anchor", {}))
    if anchor:
        return f"{status}: {source} - {summary} ({anchor})"
    return f"{status}: {source} - {summary}"


def render_anchor_inline(anchor: object) -> str:
    if not isinstance(anchor, dict):
        return ""
    source_path = str(anchor.get("source_path", "")).strip()
    line_start = int(anchor.get("line_start", 0) or 0)
    line_end = int(anchor.get("line_end", 0) or 0)
    section_path = str(anchor.get("section_path", "")).strip()
    if not source_path or line_start <= 0 or line_end < line_start:
        return ""
    location = f"{source_path}:{line_start}-{line_end}"
    return f"Anchor: {location}; section: {safe_cell(section_path or 'N/A', 120)}"


def render_bullet_list(items: list[str]) -> str:
    if not items:
        return "- [PENDING DOMAIN CONTEXT]"
    return "\n".join(f"- {item}" for item in items)


def render_story(project_id: str, epic_id: str, story: dict[str, Any]) -> str:
    rows = "\n".join(
        f"| {criterion['id']} | {criterion.get('classification', 'acceptance')} | Given {criterion['given']}, When {criterion['when']}, Then {criterion['then']}. |"
        for criterion in story["acceptance"]
    )
    normalized_reqs = [item for item in story.get("trace", []) if EARS_REQUIREMENT_ID_RE.match(str(item))]
    normalized_req_text = ", ".join(f"`{item}`" for item in normalized_reqs) or "`N/A`"
    dor = story.get("dor", {})
    dod = story.get("dod", {})
    return f"""---
id: {story['id']}
project: {project_id}
parent_epic: {epic_id}
status: {story.get('status', 'Draft')}
owner: "{story.get('owner', '')}"
label: {story['label']}
type: {story['type']}
trace:
{frontmatter_list(story['trace'])}
---

# {story['id']} - {story['title']}

This file mirrors the story embedded in its parent epic so quality and traceability tooling can address the story as an individual node.

## User Story

As a target user, I want {story['goal'].lower()} so that {story['benefit'].lower()}

## Context References

| Context Type | Source |
| --- | --- |
| Product requirement | `REQ-001`, `PRD-001`, `SPEC-001`, `{story['fr']}`, `{story['jtbd']}` |
| Normalized EARS requirements | {normalized_req_text} |
| Backlog context pack | `08_context_packs/backlog_generation.json` |
| Retrieved signal | `{story['context']['artifact_id']}` ({story['context']['artifact_type']}) |

## Domain Context Coverage

{render_domain_context_coverage(story.get('domain_coverage', []))}

## Agent Execution Contract

{render_agent_execution_contract(story.get('execution_contract', {}))}

## Retrieval Plan For Execution Agents

{render_execution_retrieval_plan(story.get('execution_contract', {}).get('retrieval_plan', []))}

{render_task_seed_contract_section(story.get('task_seed_contract'))}

## Functional Slice

- Slicing pattern: {story['slicing']}.
- Slicing rationale: {story.get('slicing_rationale', '[PENDING INPUT]')}.
- Story type: {story['type']}.
- Dependencies: {', '.join(story['dependencies']) or 'None'}.
- Enables: {', '.join(story.get('enables', [])) or 'N/A'}.
- This story must deliver user-observable value or explicit quality evidence, not an isolated implementation layer.
- Missing context remains `[PENDING INPUT]` and should be resolved upstream through gaps, `/sync`, or domain context packs.

## Lifecycle

- Status: {story.get('status', 'Draft')}.
- Owner: {story.get('owner') or '[UNASSIGNED]'}.
- Update only via `/story-status {project_id} --story {story['id']} --set STATE [--owner NAME]`.

## Acceptance Criteria

| AC ID | Classification | Criterion |
| --- | --- | --- |
{rows}

## Readiness Checklist

- {gate_checkbox(dor, 'slicing_pattern_assigned')} JTBD link is present.
- {gate_checkbox(dor, 'no_blocking_trace_gaps')} Source requirement, PRD, spec, FR and context pack links are present.
- {gate_checkbox(dor, 'acceptance_criteria_classified')} Acceptance criteria are testable.
- {gate_checkbox(dor, 'readiness_score')} Required technology/design/quality context is cited or explicitly marked as pending.

{render_gate_missing_block('DoR', dor)}

## Done Checklist

- {gate_checkbox(dod, 'acceptance_evidence_traced')} Downstream acceptance evidence is traced.
- {gate_checkbox(dod, 'ready_gate_passed')} DoR remains satisfied at closure time.

{render_gate_missing_block('DoD', dod)}
"""


def render_context_summary(context: dict[str, object]) -> str:
    domains = context.get("domains", {}) if isinstance(context, dict) else {}
    rows: list[str] = []
    for domain, results in domains.items():
        if not results:
            rows.append(f"| {domain} | No focused context retrieved. | N/A |")
            continue
        top = results[0]
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


def render_backlog_context_summary(context: dict[str, object]) -> str:
    sections = context.get("sections", {}) if isinstance(context, dict) else {}
    if not isinstance(sections, dict) or not sections:
        return "| Need | Retrieved Signal | Artifact | Trace |\n| --- | --- | --- | --- |\n| backlog | No focused context retrieved. | N/A | N/A |"
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
    return "| Backlog Need | Retrieved Signal | Artifact | Trace |\n| --- | --- | --- | --- |\n" + "\n".join(rows)


def bounded_text(text: str, limit: int) -> str:
    cleaned = text.strip()
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[:limit].rstrip() + "\n\n[TRUNCATED IN GENERATED ARTIFACT - retrieve focused source context if needed]"


def safe_cell(value: Any, limit: int) -> str:
    text = str(value).replace("\n", " ").replace("|", "/").strip()
    return text[:limit]
