from __future__ import annotations

import html
import json
import os
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from .gaps import parse_gap_rows
from .core.paths import is_valid_project_id
from .core.local_browser import open_local_file
from .shell import (
    content_fingerprint, fill, json_for_script, provenance_section, render_shell, template_text, theme_argument_for_display,
)
from .status import project_status
from .themes import DEFAULT_THEME, legend_html, load_theme, user_theme_dirs
from .workspace import read_json
from .core.io import write_text


STEPS = [
    {"key": "ingest", "group": "Discovery", "label": "Ingesta", "desc": "Cargar el requerimiento crudo del cliente"},
    {"key": "gaps", "group": "Discovery", "label": "Gaps", "desc": "Detectar y resolver vacios e incognitas"},
    {"key": "brief", "group": "Discovery", "label": "Project Brief", "desc": "Consolidar objetivo, alcance y actores"},
    {"key": "prd", "group": "Specifications", "label": "PRD", "desc": "Documento de requerimientos del producto"},
    {"key": "specs", "group": "Specifications", "label": "Specs", "desc": "Especificaciones funcionales detalladas"},
    {"key": "backlog", "group": "Backlog", "label": "Backlog", "desc": "Historias de usuario derivadas de las specs"},
    {"key": "quality", "group": "Backlog", "label": "Calidad (AC/DoD)", "desc": "Criterios de aceptacion y gates de cada historia"},
]

LIFECYCLE_STAGES = {
    "DISCOVERY_RAW": {"step": "ingest", "index": 0, "blocked": False, "text": "Discovery - input cargado"},
    "CLIENT_RESPONSE_NEEDED": {"step": "gaps", "index": 1, "blocked": True, "text": "Discovery - esperando respuesta del cliente"},
    "DOMAIN_RESPONSE_NEEDED": {"step": "gaps", "index": 1, "blocked": True, "text": "Discovery - esperando contexto de dominio"},
    "READY_FOR_PROJECT_BRIEF": {"step": "brief", "index": 2, "blocked": False, "text": "Discovery - listo para el Project Brief"},
    "BRIEF_BELOW_THRESHOLD": {"step": "brief", "index": 2, "blocked": True, "text": "Discovery - brief por debajo del umbral"},
    "SELF_CORRECTION_FAILED": {"step": "brief", "index": 2, "blocked": True, "text": "Discovery - el brief no refleja un criterio confirmado"},
    "UNITS_NOT_IMPLEMENTABLE": {"step": "brief", "index": 2, "blocked": True, "text": "Discovery - unidades no implementables"},
    "READY_FOR_SPECS": {"step": "prd", "index": 3, "blocked": False, "text": "Specifications - listo para PRD y specs"},
    "SPECS_BELOW_THRESHOLD": {"step": "specs", "index": 4, "blocked": True, "text": "Specifications - specs por debajo del umbral"},
    "READY_FOR_BACKLOG": {"step": "backlog", "index": 5, "blocked": False, "text": "Backlog - listo para generar historias"},
}

# IMP-350: the dashboard speaks the project language. Each table below has a
# Spanish and an English side; the Spanish side keeps the strings the dashboard
# always printed. Data values (ids, file names, client text) are never translated.
STEPS_EN = [
    {**step, "label": label, "desc": desc}
    for step, (label, desc) in zip(
        STEPS,
        [
            ("Ingest", "Load the client's raw requirement"),
            ("Gaps", "Find and resolve gaps and unknowns"),
            ("Project Brief", "Consolidate goal, scope and actors"),
            ("PRD", "Product requirements document"),
            ("Specs", "Detailed functional specifications"),
            ("Backlog", "User stories derived from the specs"),
            ("Quality (AC/DoD)", "Acceptance criteria and gates for each story"),
        ],
    )
]

LIFECYCLE_TEXT_EN = {
    "DISCOVERY_RAW": "Discovery - input loaded",
    "CLIENT_RESPONSE_NEEDED": "Discovery - waiting for the client's answers",
    "DOMAIN_RESPONSE_NEEDED": "Discovery - waiting for domain context",
    "READY_FOR_PROJECT_BRIEF": "Discovery - ready for the Project Brief",
    "BRIEF_BELOW_THRESHOLD": "Discovery - brief below the threshold",
    "SELF_CORRECTION_FAILED": "Discovery - the brief does not reflect a confirmed criterion",
    "UNITS_NOT_IMPLEMENTABLE": "Discovery - units not implementable",
    "READY_FOR_SPECS": "Specifications - ready for PRD and specs",
    "SPECS_BELOW_THRESHOLD": "Specifications - specs below the threshold",
    "READY_FOR_BACKLOG": "Backlog - ready to generate stories",
}

SECTION_TITLES_EN = {
    "portfolio_kpis": "Indicators",
    "portfolio_cards": "Workspaces",
    "next_step": "Next step",
    "scenarios": "Actions by situation",
    "lifecycle": "Maturity lifecycle",
    "summary": "Summary",
    "gaps_copy": "Pending gaps",
    "documents": "Documents",
    "backlog": "Backlog",
    "gates": "Story gates (DoR / DoD)",
    "warnings": "Warnings",
}

SUMMARY_LABELS = {
    "es": {"state": "Estado actual", "maturity": "Madurez", "certainty": "Certeza desarrollo", "open_gaps": "Gaps abiertos",
           "blocking_gaps": "Gaps bloqueantes", "closed_gaps": "Gaps cerrados", "language": "Idioma"},
    "en": {"state": "Current state", "maturity": "Maturity", "certainty": "Development certainty", "open_gaps": "Open gaps",
           "blocking_gaps": "Blocking gaps", "closed_gaps": "Closed gaps", "language": "Language"},
}

# Strings Python writes into the page frame (dashboard-page.html, menu, legend).
# Trusted constants: `foot` carries markup. The provenance section has its own
# table (IMP-346 shell.provenance_section).
PAGE_TEXT = {
    "es": {
        "sub": "Madurez de requerimientos de un vistazo · sin abrir un solo .md",
        "snap": "Corte de fuentes:",
        "lock": "Local-first · datos embebidos en el HTML",
        "search": "Buscar workspace...",
        "all": "Todos",
        "portfolio": "Toda la cartera",
        "attention": "Requiere atencion",
        "foot": "Dashboard local read-only generado por <code>/dashboard</code>.<br>El HTML es un snapshot reconstruible; los archivos del workspace siguen siendo la fuente de verdad.",
        "copied": "Copiado",
        "nav_sections": "Secciones",
        "nav_kpis": "Indicadores",
        "nav_grid": "Workspaces",
        "nav_legend": "Leyenda",
        "nav_provenance": "Procedencia",
        "legend_title": "Leyenda de colores",
    },
    "en": {
        "sub": "Requirement maturity at a glance · without opening a single .md",
        "snap": "Sources cut-off:",
        "lock": "Local-first · data embedded in the HTML",
        "search": "Search workspace...",
        "all": "All",
        "portfolio": "Whole portfolio",
        "attention": "Needs attention",
        "foot": "Local read-only dashboard generated by <code>/dashboard</code>.<br>The HTML is a rebuildable snapshot; the workspace files remain the source of truth.",
        "copied": "Copied",
        "nav_sections": "Sections",
        "nav_kpis": "Indicators",
        "nav_grid": "Workspaces",
        "nav_legend": "Legend",
        "nav_provenance": "Provenance",
        "legend_title": "Colour legend",
    },
}

# Strings dashboard.js writes. Shipped in <script id="dashboard-i18n">, one table per
# language the page uses; `{n}` is filled by the script.
UI_TEXT = {
    "es": {
        "locale": "es",
        "kpi_workspaces": "Workspaces",
        "kpi_attention": "Requieren atencion",
        "kpi_blocking": "Gaps bloqueantes",
        "kpi_ready": "Listos para avanzar",
        "kpi_stories": "User stories totales",
        "empty": "No hay workspaces que coincidan con el filtro.",
        "open_gaps": "Gaps abiertos",
        "blocking_short": "bloq.",
        "stories": "Stories",
        "maturity": "Madurez",
        "blocked": "bloqueado",
        "current": "en curso",
        "suggested_prompt": "Prompt sugerido (pegalo en el chat de tu asistente):",
        "copy_prompt": "Copiar prompt",
        "terminal": "Comando de terminal (avanzado)",
        "missing": "Falta",
        "next_step": "Proximo paso",
        "copy_prompt_assistant": "Copiar prompt para tu asistente",
        "scenarios": "¿Cambio algo? Acciones segun la situacion",
        "lifecycle": "Lifecycle de maduracion",
        "summary": "Resumen",
        "see_gaps": "Ver y copiar los {n} gaps pendientes ->",
        "documents": "Documentos",
        "backlog": "Backlog",
        "total_stories": "Total stories",
        "ready": "Ready",
        "in_progress": "In progress",
        "done": "Done",
        "gates": "Story gates (DoR / DoD)",
        "warnings": "Warnings",
        "warnings_count": "{n} item(s) de readiness pendientes:",
        "origin": "Origen: snapshot de",
        "updated": "actualizado",
        "pending_gaps": "Gaps pendientes",
        "generated": "Generado: ",
        "gaps_instructions": "Por favor completa tu respuesta debajo de cada pregunta y devolve este documento.",
        "answer": "Respuesta:",
        "copy_all": "Copiar todo para el cliente",
        "gaps_count": "{n} gap(s) abiertos o parciales.",
        "copy_md": "Copiar markdown",
        "open_original": "Abrir archivo original",
        "today": "(hoy)",
        "day_one": "(hace {n} dia)",
        "day_many": "(hace {n} dias)",
    },
    "en": {
        "locale": "en",
        "kpi_workspaces": "Workspaces",
        "kpi_attention": "Need attention",
        "kpi_blocking": "Blocking gaps",
        "kpi_ready": "Ready to move on",
        "kpi_stories": "Total user stories",
        "empty": "No workspace matches the filter.",
        "open_gaps": "Open gaps",
        "blocking_short": "blocking",
        "stories": "Stories",
        "maturity": "Maturity",
        "blocked": "blocked",
        "current": "in progress",
        "suggested_prompt": "Suggested prompt (paste it in your assistant's chat):",
        "copy_prompt": "Copy prompt",
        "terminal": "Terminal command (advanced)",
        "missing": "Missing",
        "next_step": "Next step",
        "copy_prompt_assistant": "Copy prompt for your assistant",
        "scenarios": "Did something change? Actions by situation",
        "lifecycle": "Maturity lifecycle",
        "summary": "Summary",
        "see_gaps": "See and copy the {n} pending gaps ->",
        "documents": "Documents",
        "backlog": "Backlog",
        "total_stories": "Total stories",
        "ready": "Ready",
        "in_progress": "In progress",
        "done": "Done",
        "gates": "Story gates (DoR / DoD)",
        "warnings": "Warnings",
        "warnings_count": "{n} pending readiness item(s):",
        "origin": "Source: snapshot of",
        "updated": "updated",
        "pending_gaps": "Pending gaps",
        "generated": "Generated: ",
        "gaps_instructions": "Please write your answer under each question and send this document back.",
        "answer": "Answer:",
        "copy_all": "Copy all for the client",
        "gaps_count": "{n} open or partial gap(s).",
        "copy_md": "Copy markdown",
        "open_original": "Open the original file",
        "today": "(today)",
        "day_one": "({n} day ago)",
        "day_many": "({n} days ago)",
    },
}

DOCUMENT_SOURCES = [
    ("requirements", "Requirements", "02_requirements/requirements.md"),
    ("brief", "Project Brief", "02_requirements/project-brief.md"),
    ("prd", "PRD", "03_specs/prd.md"),
    ("specs", "Specs", "03_specs/specs.md"),
    ("backlog", "Backlog", "04_backlog/BACKLOG.md"),
]


@dataclass(frozen=True)
class Section:
    key: str
    title: str
    scope: str
    data: Callable[[dict[str, Any]], Any]
    visible_when: Callable[[Any], bool]
    render: str


def _truthy(value: Any) -> bool:
    if isinstance(value, dict):
        return any(_truthy(item) for item in value.values())
    if isinstance(value, list):
        return bool(value)
    return value not in (None, "", 0)


SECTION_REGISTRY = [
    Section("portfolio_kpis", "Indicadores", "portfolio", lambda model: model.get("kpis"), _truthy, "kpis"),
    Section("portfolio_cards", "Workspaces", "portfolio", lambda model: model.get("workspaces"), _truthy, "card"),
    Section("next_step", "Proximo paso", "workspace", lambda ws: ws.get("next_action"), _truthy, "next_step"),
    Section("scenarios", "Acciones segun la situacion", "workspace", lambda ws: ws.get("scenarios"), _truthy, "scenarios"),
    Section("lifecycle", "Lifecycle de maduracion", "workspace", lambda ws: ws.get("lifecycle"), _truthy, "lifecycle"),
    Section("summary", "Resumen", "workspace", lambda ws: ws.get("summary"), _truthy, "summary_kv"),
    Section("gaps_copy", "Gaps pendientes", "workspace", lambda ws: ws.get("gaps_detail"), _truthy, "gaps_copy"),
    Section("documents", "Documentos", "workspace", lambda ws: ws.get("documents"), _truthy, "documents"),
    Section("backlog", "Backlog", "workspace", lambda ws: ws.get("backlog_rollup"), lambda data: bool(data and data.get("total_stories")), "backlog_kv"),
    Section("gates", "Story gates (DoR / DoD)", "workspace", lambda ws: ws.get("story_gates", {}).get("stories"), _truthy, "gates_table"),
    Section("warnings", "Warnings", "workspace", lambda ws: ws.get("story_gates", {}).get("warnings"), _truthy, "warnings"),
]

SCENARIOS = [
    {
        "title": "El cliente respondio preguntas o gaps",
        "prompt": "Registra las respuestas del cliente en {project_id}, resolve los gaps correspondientes y volve a evaluar la madurez.",
        "command": "/resolve-gaps {project_id} --source PATH -> /maturity {project_id} -> /status {project_id}",
    },
    {
        "title": "Llego nueva informacion de contexto o dominio",
        "prompt": "Incorpora esta nueva informacion de contexto al dominio de {project_id} y re-indexa la memoria del proyecto.",
        "command": "/sync {project_id} --source PATH --note \"NOTE\" -> /reindex {project_id} -> /health {project_id}",
    },
    {
        "title": "Se agrego o cambio un requerimiento",
        "prompt": "Suma este nuevo requerimiento al workspace {project_id} y actualiza el estado de maduracion.",
        # IMP-361: /ingest refuses once the project has its primary requirement; a later one goes through /sync.
        "command": "/sync {project_id} --source PATH --note \"NOTE\" -> /maturity {project_id} -> /status {project_id}",
    },
    {
        "title": "Tuve una reunion o un mail con definiciones nuevas",
        "prompt": "Registra las definiciones de esta reunion o mail en {project_id} y propaga los cambios con trazabilidad.",
        "command": "/sync {project_id} --source PATH --note \"NOTE\" -> /reindex {project_id} -> /status {project_id}",
    },
    {
        "title": "Quiero preparar el handoff a desarrollo",
        "prompt": "Prepara el handoff de {project_id}: genera specs y backlog, y valida calidad y trazabilidad.",
        "command": "/specs {project_id} -> /backlog {project_id} -> /quality {project_id} -> /trace {project_id} -> /validate {project_id}",
    },
]

SCENARIOS_EN = [
    {**item, "title": title, "prompt": prompt}
    for item, (title, prompt) in zip(
        SCENARIOS,
        [
            ("The client answered questions or gaps", "Record the client's answers in {project_id}, resolve the matching gaps and evaluate maturity again."),
            ("New context or domain information arrived", "Add this new context information to the {project_id} domain and re-index the project memory."),
            ("A requirement was added or changed", "Add this new requirement to the {project_id} workspace and update the maturity status."),
            ("I had a meeting or an email with new decisions", "Record the decisions from this meeting or email in {project_id} and propagate the changes with traceability."),
            ("I want to prepare the handoff to development", "Prepare the handoff of {project_id}: generate specs and backlog, and check quality and traceability."),
        ],
    )
]

LANGUAGES = ("es", "en")
DEFAULT_LANGUAGE = "en"


def workspace_language(value: object) -> str:
    """A workspace's dashboard language: any Spanish tag (`es`, `es-AR`) is Spanish, anything else
    (`en`, `auto`, unset) English. Same rule as the view pages (IMP-346 ``shell.page_language``).
    """
    return "es" if str(value or "").strip().lower().startswith("es") else DEFAULT_LANGUAGE


def portfolio_language(languages: list[str]) -> str:
    """The language of the page frame: the one most workspaces use; a tie or no workspace gives English."""
    counts = Counter(languages).most_common()
    if not counts or (len(counts) > 1 and counts[0][1] == counts[1][1]):
        return DEFAULT_LANGUAGE
    return counts[0][0]


class DashboardModelError(ValueError):
    """The dashboard model is inconsistent; the HTML is not written."""


def collect_dashboard_model(root: str | Path = ".") -> dict[str, Any]:
    """Collect the portfolio model. Reproducible: no clock, no absolute paths.

    ``provenance.cutoff`` is the newest mtime among the files read (state.json,
    gaps.md, embedded documents), never the wall clock; every state.json is
    fingerprinted with the first 12 hex chars of its sha256 (IMP-239).
    """
    root_path = Path(root).resolve()
    workspaces_dir = root_path / "workspaces"
    workspaces: list[dict[str, Any]] = []
    if not workspaces_dir.exists():
        return _portfolio_model(root_path, [])

    old_cwd = Path.cwd()
    os.chdir(root_path)
    try:
        for candidate in sorted(workspaces_dir.iterdir(), key=lambda item: item.name.lower()):
            if candidate.name == "_template" or not candidate.is_dir() or not (candidate / "state.json").exists():
                continue
            if not is_valid_project_id(candidate.name) or candidate.resolve().parent != workspaces_dir.resolve():
                continue  # IMP-243: the dashboard shows what commands can act on (see /doctor "workspace ids")
            workspaces.append(_workspace_model(candidate.name, root_path))
    finally:
        os.chdir(old_cwd)
    return _portfolio_model(root_path, workspaces)


def _json_for_script(value: Any) -> str:
    return json_for_script(value)


def render_dashboard(model: dict[str, Any], theme: dict[str, Any], *, theme_arg: str | None = None) -> str:
    """Validate the model, then render it inside the common shell with ``theme``.

    Raises ``DashboardModelError`` when the model is inconsistent: an invalid
    snapshot is never written. Deterministic for a given model and theme.
    """
    errors = validate_dashboard_model(model)
    if errors:
        raise DashboardModelError("dashboard model is inconsistent: " + "; ".join(errors))
    language = model.get("language") if model.get("language") in LANGUAGES else DEFAULT_LANGUAGE
    titles = {s.key: s.title for s in SECTION_REGISTRY} if language == "es" else SECTION_TITLES_EN
    sections = [{"key": s.key, "title": titles[s.key], "scope": s.scope, "render": s.render} for s in SECTION_REGISTRY]
    used = sorted({language} | {workspace_language(ws.get("language")) for ws in model.get("workspaces") or []})
    page = fill(
        "dashboard-page.html",
        data_json=_json_for_script(model),
        sections_json=_json_for_script(sections),
        i18n_json=_json_for_script({lang: UI_TEXT[lang] for lang in used}),
        **{f"t_{key}": value for key, value in PAGE_TEXT[language].items() if not key.startswith(("nav_", "legend_"))},
    )
    content = page + _legend_section(theme, language) + _provenance_section(model["provenance"], theme_arg or str(theme.get("name") or DEFAULT_THEME), language)
    return render_shell(
        theme=theme,
        title="Ignite Sentinel - Workspaces Dashboard",
        heading="Workspaces",
        nav=_nav(model),
        content=content,
        page_css=template_text("dashboard.css"),
        page_js=template_text("dashboard.js"),
        language=language,
    )


def render_html(model: dict[str, Any]) -> str:
    """Backward-compatible entry point: render with the built-in neutral theme."""
    return render_dashboard(model, load_theme())


def generate_dashboard(root: str | Path = ".", open_browser: bool = False, theme: str | Path | None = None) -> dict[str, Any]:
    root_path = Path(root).resolve()
    loaded = load_theme(theme, search_dirs=user_theme_dirs())
    model = collect_dashboard_model(root_path)
    out = root_path / "dashboard.html"
    write_text(out, render_dashboard(model, loaded, theme_arg=str(theme) if theme else None), root=root_path, newline="\n")
    if open_browser:
        open_local_file(out)
    return {
        "path": str(out),
        "count": len(model["workspaces"]),
        "cutoff": model["provenance"]["cutoff"],
        "language": model["language"],
        "theme": loaded["name"],
        "workspaces": [workspace["project_id"] for workspace in model["workspaces"]],
    }


def _nav(model: dict[str, Any]) -> str:
    text = PAGE_TEXT[model.get("language") if model.get("language") in LANGUAGES else DEFAULT_LANGUAGE]
    links = [("kpis", text["nav_kpis"]), ("grid", text["nav_grid"]), ("legend", text["nav_legend"]), ("provenance", text["nav_provenance"])]
    parts = [f"<h2>{text['nav_sections']}</h2><ul>"]
    parts += [f'<li><a href="#{anchor}">{label}</a></li>' for anchor, label in links]
    parts.append("</ul>")
    if model["workspaces"]:
        parts.append("<h2>Workspaces</h2><ul>")
        for workspace in model["workspaces"]:
            pid = html.escape(str(workspace["project_id"]), quote=True)
            parts.append(f'<li><button type="button" data-open-ws="{pid}">{pid}</button></li>')
        parts.append("</ul>")
    return "".join(parts)


def _legend_section(theme: dict[str, Any], language: str = "es") -> str:
    title = PAGE_TEXT[language]["legend_title"]
    return f'<section class="dash-section" id="legend" aria-labelledby="legend-h"><h2 id="legend-h">{title}</h2>' + legend_html(theme, language) + "</section>"


def _provenance_section(provenance: dict[str, Any], theme_arg: str, language: str = "es") -> str:
    return provenance_section(
        language=language,
        command=f"python -m sentinel /dashboard --theme {theme_argument_for_display(theme_arg)}",
        cutoff=str(provenance.get("cutoff") or ""),
        sources=list(provenance.get("sources") or []),
        section_class="dash-section",
    )


def _portfolio_model(root: Path, workspaces: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "language": portfolio_language([str(ws.get("language")) for ws in workspaces]),
        "kpis": _kpis(workspaces),
        "workspaces": workspaces,
        "provenance": _provenance(root, workspaces),
    }


def _provenance(root: Path, workspaces: list[dict[str, Any]]) -> dict[str, Any]:
    newest = 0.0
    sources: list[dict[str, str]] = []
    for workspace in workspaces:
        project_id = workspace["project_id"]
        base = root / "workspaces" / project_id
        state = base / "state.json"
        sources.append({"path": f"workspaces/{project_id}/state.json", "sha256": content_fingerprint(state.read_bytes())})
        read = [state, base / "01_discovery" / "gaps.md"] + [root / doc["path"] for doc in workspace.get("documents", [])]
        for path in read:
            if path.is_file():
                newest = max(newest, path.stat().st_mtime)
    cutoff = datetime.fromtimestamp(int(newest), timezone.utc).isoformat() if newest else ""
    return {"cutoff": cutoff, "sources": sources}


def validate_dashboard_model(model: dict[str, Any]) -> list[str]:
    """Consistency checks before rendering: unique ids, counts derived, provenance complete."""
    errors: list[str] = []
    workspaces = model.get("workspaces") or []
    ids = [str(ws.get("project_id")) for ws in workspaces]
    for project_id in sorted({item for item in ids if ids.count(item) > 1}):
        errors.append(f"duplicate workspace id {project_id!r}")
    for ws in workspaces:
        gap_ids = [str(gap.get("id")) for gap in ws.get("gaps_detail") or []]
        for gap_id in sorted({item for item in gap_ids if gap_ids.count(item) > 1}):
            errors.append(f"{ws.get('project_id')}: duplicate gap id {gap_id!r}")
        summary = ws.get("summary") or {}
        expected_open = _gap_count(ws, "open") + _gap_count(ws, "partially_closed")
        for label in (SUMMARY_LABELS[lang]["open_gaps"] for lang in LANGUAGES):
            if label in summary and summary[label] != expected_open:
                errors.append(f"{ws.get('project_id')}: summary {label!r} is {summary[label]!r}, gap_counts say {expected_open}")
    expected_kpis = _kpis(workspaces)
    for key, value in expected_kpis.items():
        if (model.get("kpis") or {}).get(key) != value:
            errors.append(f"kpis.{key} is {(model.get('kpis') or {}).get(key)!r}, computed {value}")
    provenance = model.get("provenance")
    if not isinstance(provenance, dict) or "cutoff" not in provenance:
        errors.append("provenance with a cutoff is required")
    else:
        fingerprinted = {item.get("path") for item in provenance.get("sources") or []}
        for project_id in ids:
            if f"workspaces/{project_id}/state.json" not in fingerprinted:
                errors.append(f"provenance misses the state.json fingerprint of {project_id!r}")
    return errors


def _workspace_model(project_id: str, root: Path) -> dict[str, Any]:
    base = root / "workspaces" / project_id
    status = project_status(project_id)
    state = read_json(base / "state.json", {})
    language = workspace_language(state.get("project_language") if isinstance(state, dict) else None)
    stage = lifecycle_for(status.get("readiness_stage"), language)
    gaps_detail = _gaps_detail(base)
    documents = _documents(base, project_id)
    next_action = _next_action(project_id, status, stage, language)
    backlog_rollup = _normalize_backlog_rollup(status.get("backlog_rollup"))
    ledger = status.get("knowledge_ledger")
    if isinstance(ledger, dict) and ledger.get("path"):
        status = {**status, "knowledge_ledger": {**ledger, "path": f"workspaces/{project_id}/01_discovery/knowledge_state.json"}}
    model = {
        **status,
        "language": language,
        "backlog_rollup": backlog_rollup,
        "updated_at": state.get("updated_at") or _mtime_iso(base / "state.json"),
        "lifecycle": stage,
        "steps": STEPS if language == "es" else STEPS_EN,
        "gaps_detail": gaps_detail,
        "documents": documents,
        "next_action": next_action,
        "next_title": next_action["title"],
        "next_detail": next_action["detail"],
        "next_prompt": next_action["prompt"],
        "next_cmd": next_action["command"],
        "scenarios": _scenarios(project_id, language),
        "summary": _summary(status, stage, language),
    }
    return model


def lifecycle_for(readiness_stage: object, language: str = "es") -> dict[str, Any]:
    key = str(readiness_stage or "DISCOVERY_RAW")
    fallback = {"step": "ingest", "index": 0, "blocked": False, "text": key}
    stage = dict(LIFECYCLE_STAGES.get(key, fallback))
    if language != "es" and key in LIFECYCLE_TEXT_EN:
        stage["text"] = LIFECYCLE_TEXT_EN[key]
    stage["readiness_stage"] = key
    return stage


def _gaps_detail(base: Path) -> list[dict[str, str]]:
    gaps_path = base / "01_discovery" / "gaps.md"
    if not gaps_path.exists():
        return []
    rows = parse_gap_rows(gaps_path.read_text(encoding="utf-8"))
    pending = []
    for row in rows:
        status = row.get("status", "OPEN").upper()
        if status in {"OPEN", "PARTIALLY_CLOSED", "ANSWERED"}:
            pending.append(row)
    return pending


def _documents(base: Path, project_id: str) -> list[dict[str, str]]:
    docs: list[dict[str, str]] = []
    for key, label, relative in DOCUMENT_SOURCES:
        path = base / relative
        if path.exists():
            docs.append(
                {
                    "key": key,
                    "label": label,
                    "path": f"workspaces/{project_id}/{relative}",
                    "content": path.read_text(encoding="utf-8"),
                }
            )
    return docs


def _summary(status: dict[str, Any], stage: dict[str, Any], language: str = "es") -> dict[str, Any]:
    counts = status.get("gap_counts") if isinstance(status.get("gap_counts"), dict) else {}
    metrics = status.get("maturity_metrics") if isinstance(status.get("maturity_metrics"), dict) else {}
    label = SUMMARY_LABELS[language]
    return {
        label["state"]: stage["text"],
        label["maturity"]: _score(metrics),
        label["certainty"]: _development_readiness_label(status),
        label["open_gaps"]: int(counts.get("open", 0) or 0) + int(counts.get("partially_closed", 0) or 0),
        label["blocking_gaps"]: counts.get("blocking_open", 0),
        label["closed_gaps"]: f"{counts.get('closed', 0)}/{counts.get('total', 0)}",
        label["language"]: status.get("project_language", "auto"),
    }


def _score(metrics: dict[str, Any]) -> str:
    score = metrics.get("maturity_score", metrics.get("score"))
    threshold = metrics.get("threshold")
    if isinstance(score, (int, float)):
        if isinstance(threshold, (int, float)):
            return f"{round(score * 100)}% / {round(threshold * 100)}%"
        return f"{round(score * 100)}%"
    return "-"


def _development_readiness_label(status: dict[str, Any]) -> str:
    readiness = status.get("development_readiness") if isinstance(status.get("development_readiness"), dict) else {}
    summary = readiness.get("summary") if isinstance(readiness.get("summary"), dict) else {}
    score = summary.get("global_score")
    gate = summary.get("crystallization_gate") if isinstance(summary.get("crystallization_gate"), dict) else {}
    state = str(gate.get("state") or "-")
    if isinstance(score, (int, float)):
        return f"{round(score * 100)}% - {state}"
    return state


# IMP-248: the decision comes from build_readiness_verdict; this only words it
# for the dashboard. One key per next step, never a second decision tree.
NEXT_ACTION_COPY: dict[str, tuple[str, str, str]] = {
    "ingest": ("Cargar requerimiento inicial", "/ingest {pid} --source PATH -> /status {pid}", "Carga el requerimiento inicial de {pid}, ejecuta discovery y resumime gaps y proximo paso."),
    "resolve_blocking": ("Esperando respuestas del cliente", "/resolve-gaps {pid} --source PATH -> /maturity {pid} -> /status {pid}", "Registra las respuestas del cliente para {pid}, resolve los gaps bloqueantes y volve a evaluar la madurez."),
    "fix_brief": ("Corregir lo que freno el brief", "/brief {pid} -> /status {pid}", "Revisa por que /brief freno el cierre de fase de {pid} (umbral, autocorreccion o implementabilidad), resolvelo y volve a generar el brief."),
    "specs": ("Preparar PRD y specs", "/specs {pid} -> /status {pid}", "Genera PRD y specs para {pid} solo con evidencia disponible y marca cualquier pendiente explicito."),
    "fix_specs": ("Subir las specs sobre el umbral", "/specs {pid} -> /status {pid}", "Cierra los gaps que reporto la readiness de specs de {pid} y volve a generar las specs."),
    "backlog": ("Preparar backlog", "/backlog {pid} -> /backlog-status {pid} -> /quality {pid}", "Prepara el backlog gobernado de {pid}, verifica DoR/DoD y resume bloqueos para handoff."),
    "quality": ("Revisar el backlog", "/quality {pid} -> /backlog-status {pid}", "Revisa las historias de {pid} que no pasan el Definition of Ready y resume que falta y de quien."),
    "resolve_gaps": ("Resolver gaps pendientes", "/resolve-gaps {pid} --source PATH -> /maturity {pid} -> /status {pid}", "Revisa los gaps pendientes de {pid}, registra las respuestas disponibles y manten visibles los pendientes."),
    "brief": ("Generar Project Brief", "/brief {pid} -> /status {pid}", "Genera el Project Brief de {pid} desde evidencia madura y manten trazabilidad de lo pendiente."),
}


NEXT_ACTION_COPY_EN: dict[str, tuple[str, str, str]] = {
    key: (title, NEXT_ACTION_COPY[key][1], prompt)
    for key, (title, prompt) in {
        "ingest": ("Load the initial requirement", "Load the initial requirement of {pid}, run discovery and summarize the gaps and the next step."),
        "resolve_blocking": ("Waiting for client answers", "Record the client's answers for {pid}, resolve the blocking gaps and evaluate maturity again."),
        "fix_brief": ("Fix what stopped the brief", "Check why /brief stopped the phase close of {pid} (threshold, self-correction or implementability), fix it and generate the brief again."),
        "specs": ("Prepare PRD and specs", "Generate PRD and specs for {pid} only from the available evidence and mark every open item explicitly."),
        "fix_specs": ("Raise the specs above the threshold", "Close the gaps the specs readiness of {pid} reported and generate the specs again."),
        "backlog": ("Prepare the backlog", "Prepare the governed backlog of {pid}, check DoR/DoD and summarize the blockers for the handoff."),
        "quality": ("Review the backlog", "Review the stories of {pid} that do not pass the Definition of Ready and summarize what is missing and from whom."),
        "resolve_gaps": ("Resolve pending gaps", "Review the pending gaps of {pid}, record the available answers and keep the open items visible."),
        "brief": ("Generate the Project Brief", "Generate the Project Brief of {pid} from mature evidence and keep what is pending traceable."),
    }.items()
}

NEXT_ACTION_FALLBACK = {
    "es": ("Inspeccionar estado", "/status {pid} -> /health {pid}", "Inspecciona el estado de {pid}, explica blockers y recomienda el siguiente comando seguro."),
    "en": ("Inspect the status", "/status {pid} -> /health {pid}", "Inspect the status of {pid}, explain the blockers and recommend the next safe command."),
}


def _next_action(project_id: str, status: dict[str, Any], stage: dict[str, Any], language: str = "es") -> dict[str, str]:
    action = status.get("next_action") if isinstance(status.get("next_action"), dict) else {}
    key = str(action.get("key", ""))
    copy = NEXT_ACTION_COPY if language == "es" else NEXT_ACTION_COPY_EN
    title, command, prompt = copy.get(key, NEXT_ACTION_FALLBACK[language])
    return {
        "key": key,
        "title": title,
        "detail": str(status.get("next_step") or stage["text"]),
        "prompt": prompt.format(pid=project_id),
        "command": command.format(pid=project_id),
    }


def _scenarios(project_id: str, language: str = "es") -> list[dict[str, str]]:
    return [
        {
            "title": item["title"],
            "prompt": item["prompt"].format(project_id=project_id),
            "command": item["command"].format(project_id=project_id),
        }
        for item in (SCENARIOS if language == "es" else SCENARIOS_EN)
    ]


def _kpis(workspaces: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "total": len(workspaces),
        "attention": sum(1 for ws in workspaces if _needs_attention(ws)),
        "blocking_gaps": sum(_gap_count(ws, "blocking_open") for ws in workspaces),
        "ready": sum(1 for ws in workspaces if ws.get("readiness_stage") in {"READY_FOR_PROJECT_BRIEF", "READY_FOR_SPECS", "READY_FOR_BACKLOG"}),
        "stories": sum(int((ws.get("backlog_rollup") or {}).get("total_stories", 0) or 0) for ws in workspaces),
    }


def _normalize_backlog_rollup(value: object) -> dict[str, Any]:
    rollup = dict(value) if isinstance(value, dict) else {}
    status_counts = rollup.get("status_counts") if isinstance(rollup.get("status_counts"), dict) else {}
    if "total_stories" not in rollup:
        rollup["total_stories"] = int(rollup.get("stories_total", 0) or 0)
    rollup.setdefault("ready", int(status_counts.get("Ready", 0) or 0))
    rollup.setdefault("in_progress", int(status_counts.get("In Progress", 0) or 0))
    rollup.setdefault("done", int(status_counts.get("Done", 0) or 0))
    return rollup


def _needs_attention(workspace: dict[str, Any]) -> bool:
    gates = workspace.get("story_gates") if isinstance(workspace.get("story_gates"), dict) else {}
    return (
        str(workspace.get("health", "UNKNOWN")).upper() == "DIRTY"
        or _gap_count(workspace, "blocking_open") > 0
        or bool((workspace.get("lifecycle") or {}).get("blocked"))
        or bool(gates.get("warnings"))
    )


def _gap_count(workspace: dict[str, Any], key: str) -> int:
    counts = workspace.get("gap_counts") if isinstance(workspace.get("gap_counts"), dict) else {}
    return int(counts.get(key, 0) or 0)


def _mtime_iso(path: Path) -> str:
    if not path.exists():
        return ""
    return datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).replace(microsecond=0).isoformat()
