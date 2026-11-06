from __future__ import annotations

import hashlib
import html
import json
import os
import webbrowser
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from .discovery import parse_gap_rows
from .shell import fill, render_shell, template_text
from .status import project_status
from .themes import DEFAULT_THEME, legend_html, load_theme
from .workspace import read_json


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
    "READY_FOR_SPECS": {"step": "prd", "index": 3, "blocked": False, "text": "Specifications - listo para PRD y specs"},
    "SPECS_BELOW_THRESHOLD": {"step": "specs", "index": 4, "blocked": True, "text": "Specifications - specs por debajo del umbral"},
    "READY_FOR_BACKLOG": {"step": "backlog", "index": 5, "blocked": False, "text": "Backlog - listo para generar historias"},
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
        "command": "/ingest {project_id} --source PATH -> /status {project_id}",
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
            workspaces.append(_workspace_model(candidate.name, root_path))
    finally:
        os.chdir(old_cwd)
    return _portfolio_model(root_path, workspaces)


def _json_for_script(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False).replace("</", "<\\/")


def render_dashboard(model: dict[str, Any], theme: dict[str, Any], *, theme_arg: str | None = None) -> str:
    """Validate the model, then render it inside the common shell with ``theme``.

    Raises ``DashboardModelError`` when the model is inconsistent: an invalid
    snapshot is never written. Deterministic for a given model and theme.
    """
    errors = validate_dashboard_model(model)
    if errors:
        raise DashboardModelError("dashboard model is inconsistent: " + "; ".join(errors))
    sections = [{"key": s.key, "title": s.title, "scope": s.scope, "render": s.render} for s in SECTION_REGISTRY]
    page = fill("dashboard.html", data_json=_json_for_script(model), sections_json=_json_for_script(sections))
    content = page + _legend_section(theme) + _provenance_section(model["provenance"], theme_arg or str(theme.get("name") or DEFAULT_THEME))
    return render_shell(
        theme=theme,
        title="Ignite Sentinel - Workspaces Dashboard",
        heading="Workspaces",
        nav=_nav(model),
        content=content,
        page_css=template_text("dashboard.css"),
        page_js=template_text("dashboard.js"),
        language="es",
    )


def render_html(model: dict[str, Any]) -> str:
    """Backward-compatible entry point: render with the built-in neutral theme."""
    return render_dashboard(model, load_theme())


def generate_dashboard(root: str | Path = ".", open_browser: bool = False, theme: str | Path | None = None) -> dict[str, Any]:
    root_path = Path(root).resolve()
    loaded = load_theme(theme)
    model = collect_dashboard_model(root_path)
    out = root_path / "dashboard.html"
    out.write_text(render_dashboard(model, loaded, theme_arg=str(theme) if theme else None), encoding="utf-8")
    if open_browser:
        webbrowser.open(out.as_uri())
    return {
        "path": str(out),
        "count": len(model["workspaces"]),
        "cutoff": model["provenance"]["cutoff"],
        "theme": loaded["name"],
        "workspaces": [workspace["project_id"] for workspace in model["workspaces"]],
    }


def _nav(model: dict[str, Any]) -> str:
    links = [("kpis", "Indicadores"), ("grid", "Workspaces"), ("legend", "Leyenda"), ("provenance", "Procedencia")]
    parts = ["<h2>Secciones</h2><ul>"]
    parts += [f'<li><a href="#{anchor}">{label}</a></li>' for anchor, label in links]
    parts.append("</ul>")
    if model["workspaces"]:
        parts.append("<h2>Workspaces</h2><ul>")
        for workspace in model["workspaces"]:
            pid = html.escape(str(workspace["project_id"]), quote=True)
            parts.append(f'<li><button type="button" data-open-ws="{pid}">{pid}</button></li>')
        parts.append("</ul>")
    return "".join(parts)


def _legend_section(theme: dict[str, Any]) -> str:
    return '<section class="dash-section" id="legend" aria-labelledby="legend-h"><h2 id="legend-h">Leyenda de colores</h2>' + legend_html(theme, "es") + "</section>"


def _provenance_section(provenance: dict[str, Any], theme_arg: str) -> str:
    cutoff = html.escape(provenance.get("cutoff") or "-")
    rows = "".join(
        f"<tr><td><code>{html.escape(item['path'])}</code></td><td><code>{html.escape(item['sha256'])}</code></td></tr>"
        for item in provenance.get("sources") or []
    )
    table = f'<table class="prov"><thead><tr><th>Fuente</th><th>sha256 (12)</th></tr></thead><tbody>{rows}</tbody></table>' if rows else "<p>Sin workspaces.</p>"
    command = html.escape(f"python -m sentinel /dashboard --theme {theme_arg}")
    return (
        '<section class="dash-section" id="provenance" aria-labelledby="provenance-h"><h2 id="provenance-h">Procedencia</h2>'
        f'<p>Fecha de corte: <time datetime="{cutoff}">{cutoff}</time> <span id="provAge"></span>. Es el mtime mas reciente de las fuentes leidas, no la hora de generacion.</p>'
        f"{table}<p>Regenerar: <code>{command}</code></p></section>"
    )


def _portfolio_model(root: Path, workspaces: list[dict[str, Any]]) -> dict[str, Any]:
    return {
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
        sources.append({"path": f"workspaces/{project_id}/state.json", "sha256": hashlib.sha256(state.read_bytes()).hexdigest()[:12]})
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
        if "Gaps abiertos" in summary and summary["Gaps abiertos"] != expected_open:
            errors.append(f"{ws.get('project_id')}: summary 'Gaps abiertos' is {summary['Gaps abiertos']!r}, gap_counts say {expected_open}")
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
    stage = lifecycle_for(status.get("readiness_stage"))
    gaps_detail = _gaps_detail(base)
    documents = _documents(base, project_id)
    next_action = _next_action(project_id, status, stage)
    backlog_rollup = _normalize_backlog_rollup(status.get("backlog_rollup"))
    model = {
        **status,
        "backlog_rollup": backlog_rollup,
        "updated_at": state.get("updated_at") or _mtime_iso(base / "state.json"),
        "lifecycle": stage,
        "steps": STEPS,
        "gaps_detail": gaps_detail,
        "documents": documents,
        "next_action": next_action,
        "next_title": next_action["title"],
        "next_detail": next_action["detail"],
        "next_prompt": next_action["prompt"],
        "next_cmd": next_action["command"],
        "scenarios": _scenarios(project_id),
        "summary": _summary(status, stage),
    }
    return model


def lifecycle_for(readiness_stage: object) -> dict[str, Any]:
    key = str(readiness_stage or "DISCOVERY_RAW")
    fallback = {"step": "ingest", "index": 0, "blocked": False, "text": key}
    stage = dict(LIFECYCLE_STAGES.get(key, fallback))
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


def _summary(status: dict[str, Any], stage: dict[str, Any]) -> dict[str, Any]:
    counts = status.get("gap_counts") if isinstance(status.get("gap_counts"), dict) else {}
    metrics = status.get("maturity_metrics") if isinstance(status.get("maturity_metrics"), dict) else {}
    return {
        "Estado actual": stage["text"],
        "Madurez": _score(metrics),
        "Certeza desarrollo": _development_readiness_label(status),
        "Gaps abiertos": int(counts.get("open", 0) or 0) + int(counts.get("partially_closed", 0) or 0),
        "Gaps bloqueantes": counts.get("blocking_open", 0),
        "Gaps cerrados": f"{counts.get('closed', 0)}/{counts.get('total', 0)}",
        "Idioma": status.get("project_language", "auto"),
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


def _next_action(project_id: str, status: dict[str, Any], stage: dict[str, Any]) -> dict[str, str]:
    counts = status.get("gap_counts") if isinstance(status.get("gap_counts"), dict) else {}
    blocking = int(counts.get("blocking_open", 0) or 0)
    open_gaps = int(counts.get("open", 0) or 0) + int(counts.get("partially_closed", 0) or 0)
    readiness = str(status.get("readiness_stage", "DISCOVERY_RAW"))
    if status.get("phase") == "initialized":
        title = "Cargar requerimiento inicial"
        command = f"/ingest {project_id} --source PATH -> /status {project_id}"
        prompt = f"Carga el requerimiento inicial de {project_id}, ejecuta discovery y resumime gaps y proximo paso."
    elif blocking:
        title = "Esperando respuestas del cliente"
        command = f"/resolve-gaps {project_id} --source PATH -> /maturity {project_id} -> /status {project_id}"
        prompt = f"Registra las respuestas del cliente para {project_id}, resolve los gaps bloqueantes y volve a evaluar la madurez."
    elif open_gaps:
        title = "Resolver gaps pendientes"
        command = f"/resolve-gaps {project_id} --source PATH -> /maturity {project_id} -> /status {project_id}"
        prompt = f"Revisa los gaps pendientes de {project_id}, registra las respuestas disponibles y manten visibles los pendientes."
    elif readiness == "READY_FOR_PROJECT_BRIEF":
        title = "Generar Project Brief"
        command = f"/brief {project_id} -> /status {project_id}"
        prompt = f"Genera el Project Brief de {project_id} desde evidencia madura y manten trazabilidad de lo pendiente."
    elif readiness in {"READY_FOR_SPECS", "BRIEF_BELOW_THRESHOLD"}:
        title = "Preparar PRD y specs"
        command = f"/specs {project_id} -> /status {project_id}"
        prompt = f"Genera PRD y specs para {project_id} solo con evidencia disponible y marca cualquier pendiente explicito."
    elif readiness in {"READY_FOR_BACKLOG", "SPECS_BELOW_THRESHOLD"}:
        title = "Preparar backlog"
        command = f"/backlog {project_id} -> /backlog-status {project_id} -> /quality {project_id}"
        prompt = f"Prepara el backlog gobernado de {project_id}, verifica DoR/DoD y resume bloqueos para handoff."
    else:
        title = "Inspeccionar estado"
        command = f"/status {project_id} -> /health {project_id}"
        prompt = f"Inspecciona el estado de {project_id}, explica blockers y recomienda el siguiente comando seguro."
    return {"title": title, "detail": str(status.get("next_step") or stage["text"]), "prompt": prompt, "command": command}


def _scenarios(project_id: str) -> list[dict[str, str]]:
    return [
        {
            "title": item["title"],
            "prompt": item["prompt"].format(project_id=project_id),
            "command": item["command"].format(project_id=project_id),
        }
        for item in SCENARIOS
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
