from __future__ import annotations

import html
import json
import os
import webbrowser
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from .discovery import parse_gap_rows
from .status import project_status
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


def collect_dashboard_model(root: str | Path = ".") -> dict[str, Any]:
    root_path = Path(root).resolve()
    workspaces_dir = root_path / "workspaces"
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    workspaces: list[dict[str, Any]] = []
    if not workspaces_dir.exists():
        return _portfolio_model(root_path, generated_at, [])

    old_cwd = Path.cwd()
    os.chdir(root_path)
    try:
        for candidate in sorted(workspaces_dir.iterdir(), key=lambda item: item.name.lower()):
            if candidate.name == "_template" or not candidate.is_dir() or not (candidate / "state.json").exists():
                continue
            workspaces.append(_workspace_model(candidate.name, root_path))
    finally:
        os.chdir(old_cwd)
    return _portfolio_model(root_path, generated_at, workspaces)


def render_html(model: dict[str, Any]) -> str:
    data_json = json.dumps(model, ensure_ascii=False).replace("</", "<\\/")
    sections_json = json.dumps(
        [{"key": s.key, "title": s.title, "scope": s.scope, "render": s.render} for s in SECTION_REGISTRY],
        ensure_ascii=False,
    ).replace("</", "<\\/")
    return HTML_TEMPLATE.replace("__DASHBOARD_DATA__", data_json).replace("__SECTION_REGISTRY__", sections_json)


def generate_dashboard(root: str | Path = ".", open_browser: bool = False) -> dict[str, Any]:
    root_path = Path(root).resolve()
    model = collect_dashboard_model(root_path)
    out = root_path / "dashboard.html"
    out.write_text(render_html(model), encoding="utf-8")
    if open_browser:
        webbrowser.open(out.as_uri())
    return {
        "path": str(out),
        "count": len(model["workspaces"]),
        "generated_at": model["generated_at"],
        "workspaces": [workspace["project_id"] for workspace in model["workspaces"]],
    }


def _portfolio_model(root: Path, generated_at: str, workspaces: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "generated_at": generated_at,
        "root": str(root),
        "kpis": _kpis(workspaces),
        "workspaces": workspaces,
    }


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


HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Ignite Sentinel - Workspaces Dashboard</title>
<style>
:root{--bg:#0b0c0e;--panel:#141517;--panel-2:#1a1b1f;--line:#26282d;--line-2:#33363c;--txt:#e9eaec;--muted:#8a8f98;--muted-2:#5e636b;--accent:#828dff;--accent-soft:#1b1d33;--green:#4cb782;--green-soft:#13251d;--amber:#d6a531;--amber-soft:#272013;--red:#e5614f;--red-soft:#291715;--violet:#a9aeb8;--violet-soft:#1d1f24;--radius:9px;--shadow:0 1px 2px rgba(0,0,0,.22)}
@media (prefers-color-scheme:light){:root{--bg:#fbfbfc;--panel:#fff;--panel-2:#f5f6f8;--line:#e7e8ec;--line-2:#dcdee3;--txt:#16181d;--muted:#6b7280;--muted-2:#9aa0aa;--accent:#5e6ad2;--accent-soft:#edeefb;--green:#2f9e6f;--green-soft:#e7f4ee;--amber:#b7791f;--amber-soft:#fbf1da;--red:#d6453d;--red-soft:#fbe9e8;--violet:#5a6372;--violet-soft:#eef0f3;--shadow:0 1px 2px rgba(16,24,40,.04)}}
*{box-sizing:border-box}html,body{margin:0;background:var(--bg);color:var(--txt);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Inter,Helvetica,Arial,sans-serif;font-size:14px;line-height:1.45;-webkit-font-smoothing:antialiased}.wrap{max-width:1240px;margin:0 auto;padding:22px 22px 60px}a{color:var(--accent);text-decoration:none}
header.top{display:flex;align-items:flex-end;justify-content:space-between;gap:16px;flex-wrap:wrap;margin-bottom:18px}.brand{display:flex;align-items:center;gap:12px}.spark{width:26px;height:26px;border-radius:7px;background:var(--accent);display:grid;place-items:center;color:#fff;font-size:13px;font-weight:800}h1{font-size:18px;margin:0}.sub{color:var(--muted);font-size:12.5px;margin-top:2px}.snap{color:var(--muted);font-size:12px;text-align:right}.snap b{color:var(--txt);font-weight:600}
.kpis{display:grid;grid-template-columns:repeat(5,1fr);gap:12px;margin:8px 0 18px}.kpi{background:var(--panel);border:1px solid var(--line);border-radius:var(--radius);padding:14px 16px;box-shadow:var(--shadow)}.kpi .n{font-size:24px;font-weight:750}.kpi .l{color:var(--muted);font-size:12px;margin-top:2px}.kpi.warn .n{color:var(--red)}.kpi.ok .n{color:var(--green)}.kpi.mid .n{color:var(--amber)}
.controls{display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin-bottom:14px}.search{flex:1;min-width:220px}.search input{width:100%;background:var(--panel);border:1px solid var(--line);color:var(--txt);border-radius:10px;padding:10px 12px;font-size:13.5px;outline:none}.search input:focus{border-color:var(--accent)}.seg{display:flex;background:var(--panel);border:1px solid var(--line);border-radius:10px;overflow:hidden}.seg button{background:transparent;border:0;color:var(--muted);padding:9px 13px;font-size:12.5px;cursor:pointer}.seg button.active{background:var(--accent-soft);color:var(--accent);font-weight:600}.seg button:not(:last-child){border-right:1px solid var(--line)}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(360px,1fr));gap:14px}.card{background:var(--panel);border:1px solid var(--line);border-radius:var(--radius);padding:16px;box-shadow:var(--shadow);cursor:pointer;transition:transform .12s ease,border-color .12s ease}.card:hover{border-color:var(--line-2);background:var(--panel-2)}.card .row1{display:flex;justify-content:space-between;align-items:flex-start;gap:8px}.card .pid{font-weight:700;font-size:14.5px}.card .stage{color:var(--muted);font-size:11.5px;margin-top:1px}.pill{display:inline-flex;align-items:center;gap:5px;font-size:11px;font-weight:600;padding:3px 9px;border-radius:999px;white-space:nowrap}.pill .dot{width:7px;height:7px;border-radius:50%}.h-CLEAN{background:var(--green-soft);color:var(--green)}.h-CLEAN .dot{background:var(--green)}.h-DIRTY{background:var(--red-soft);color:var(--red)}.h-DIRTY .dot{background:var(--red)}.h-UNKNOWN{background:var(--panel-2);color:var(--muted)}.h-UNKNOWN .dot{background:var(--muted)}
.pipe{display:flex;gap:3px;margin:15px 0 0}.pipe .ph{flex-grow:var(--w,1);display:flex;gap:2px}.pipe .tick{flex:1;height:8px;border-radius:3px;background:var(--panel-2)}.pipe .tick.done{background:var(--green)}.pipe .tick.current{background:var(--accent)}.pipe .tick.blocked{background:var(--red)}.pipe-labels{display:flex;margin-top:6px;font-size:10px;color:var(--muted-2)}.pipe-labels span{text-align:center}.pipe-labels .cur{color:var(--accent);font-weight:700}.pipe-labels .curblk{color:var(--red);font-weight:700}.mini{display:flex;gap:14px;margin-top:13px;flex-wrap:wrap}.mini .m{font-size:12px;color:var(--muted)}.mini .m b{color:var(--txt);font-weight:650}.mini .m.bad b{color:var(--red)}.next{margin-top:14px;padding:11px 13px;background:var(--panel-2);border:1px solid var(--line);border-radius:8px;font-size:12.5px;line-height:1.5}.next .nh{font-weight:600;color:var(--accent);font-size:10.5px;text-transform:uppercase;letter-spacing:.4px;margin-bottom:5px}.next p{margin:0;color:var(--txt)}.bar{height:6px;background:var(--panel-2);border-radius:4px;overflow:hidden;margin-top:8px}.bar>i{display:block;height:100%;background:var(--accent)}
.scrim{position:fixed;inset:0;background:rgba(0,0,0,.5);opacity:0;pointer-events:none;transition:opacity .18s}.scrim.open{opacity:1;pointer-events:auto}.drawer{position:fixed;top:0;right:0;height:100%;width:min(580px,95vw);background:var(--bg);border-left:1px solid var(--line);box-shadow:-12px 0 40px rgba(0,0,0,.4);transform:translateX(100%);transition:transform .22s ease;overflow-y:auto;z-index:10}.drawer.open{transform:translateX(0)}.drawer .dh{position:sticky;top:0;background:var(--bg);padding:18px 20px 14px;border-bottom:1px solid var(--line);display:flex;justify-content:space-between;align-items:flex-start;gap:10px;z-index:2}.drawer .dh h2{margin:0;font-size:16px}.drawer .body{padding:18px 20px 50px}.close{background:var(--panel);border:1px solid var(--line);color:var(--muted);border-radius:8px;width:30px;height:30px;cursor:pointer;font-size:16px;line-height:1}.sec{margin-top:24px}.sec h3{font-size:12px;text-transform:uppercase;letter-spacing:.6px;color:var(--muted);margin:0 0 11px}.kv{display:grid;grid-template-columns:repeat(2,1fr);gap:10px}.kv .b{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:11px 13px}.kv .b .l{color:var(--muted);font-size:11px}.kv .b .v{font-size:14px;font-weight:650;margin-top:2px}
.actionbox{background:var(--panel-2);border:1px solid var(--line);border-left:2px solid var(--accent);border-radius:8px;padding:13px 15px}.actionbox .ah{font-weight:600;color:var(--accent);font-size:10.5px;text-transform:uppercase;letter-spacing:.4px;margin-bottom:7px}.actionbox p.detail{margin:0 0 10px;font-size:12.5px;color:var(--txt);line-height:1.5}.prompt{background:var(--panel);border:1px solid var(--line);border-radius:9px;padding:10px 12px;font-size:12.5px;color:var(--txt);line-height:1.45;font-style:italic}.prompt-row{display:flex;gap:8px;align-items:stretch;margin-top:8px}.copybtn{flex:1;background:var(--accent);color:#fff;border:0;border-radius:9px;padding:9px 12px;font-size:12.5px;font-weight:650;cursor:pointer;display:flex;align-items:center;justify-content:center;gap:6px}.copybtn.ghost{flex:0 0 auto;background:transparent;color:var(--muted);border:1px solid var(--line);font-weight:500}.adv{margin-top:9px}.adv summary{cursor:pointer;color:var(--muted);font-size:11.5px;list-style:none;user-select:none}.adv summary::-webkit-details-marker{display:none}.adv summary::before{content:"> ";color:var(--muted-2)}.cmd{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;background:var(--panel-2);border:1px solid var(--line);border-radius:8px;padding:9px 11px;font-size:11.5px;color:var(--muted);margin-top:7px;word-break:break-all}
table.gates{width:100%;border-collapse:collapse;font-size:12.5px}table.gates th{text-align:left;color:var(--muted);font-weight:600;font-size:11px;padding:6px 8px;border-bottom:1px solid var(--line)}table.gates td{padding:8px;border-bottom:1px solid var(--line);vertical-align:top}.chk{font-weight:700}.chk.ok{color:var(--green)}.chk.no{color:var(--red)}.miss{color:var(--muted);font-size:11px}.warnbox{background:var(--amber-soft);border:1px solid var(--amber);border-radius:10px;padding:11px 13px;color:var(--txt);font-size:12px}.warnbox ul{margin:6px 0 0;padding-left:18px}.stepflow{display:flex;flex-direction:column}.stepflow .grp{font-size:10.5px;text-transform:uppercase;letter-spacing:.5px;color:var(--muted-2);margin:10px 0 2px;font-weight:700}.stepflow .grp:first-child{margin-top:0}.stepflow .st{display:flex;gap:11px;align-items:flex-start;padding:8px 0}.stepflow .st .ic{width:22px;height:22px;border-radius:50%;flex-shrink:0;display:grid;place-items:center;font-size:11px;font-weight:700;border:2px solid var(--line);background:var(--panel);color:var(--muted)}.stepflow .st.done .ic{background:var(--green);border-color:var(--green);color:#fff}.stepflow .st.current .ic{background:var(--accent);border-color:var(--accent);color:#fff}.stepflow .st.blocked .ic{background:var(--red);border-color:var(--red);color:#fff}.stepflow .st .t{font-size:13px;font-weight:600}.stepflow .st .d{font-size:11.5px;color:var(--muted)}.stepflow .st .badge{font-size:10px;font-weight:700;padding:1px 7px;border-radius:999px;margin-left:6px;vertical-align:middle}.stepflow .st.current .badge{background:var(--accent-soft);color:var(--accent)}.stepflow .st.blocked .badge{background:var(--red-soft);color:var(--red)}
.scn{border:1px solid var(--line);border-radius:11px;background:var(--panel);margin-bottom:9px;overflow:hidden}.scn summary{cursor:pointer;list-style:none;padding:12px 14px;display:flex;gap:10px;align-items:center;font-size:13px;font-weight:600}.scn summary::-webkit-details-marker{display:none}.scn summary .chev{margin-left:auto;color:var(--muted-2);transition:transform .15s}.scn[open] summary .chev{transform:rotate(90deg)}.scn .inner{padding:0 14px 14px;border-top:1px solid var(--line)}.scn .inner p{font-size:12px;color:var(--muted);margin:10px 0 0}.docchips{display:flex;flex-wrap:wrap;gap:8px}.docchip{display:inline-flex;align-items:center;gap:7px;background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:9px 12px;font-size:12.5px;cursor:pointer;color:var(--txt);font-weight:600}.docchip:hover{border-color:var(--accent);color:var(--accent)}.docnote{color:var(--muted);font-size:12.5px}.gapbtn{background:var(--panel);border:1px solid var(--line);color:var(--txt);border-radius:10px;padding:10px 13px;font-size:12.5px;font-weight:600;cursor:pointer;margin-top:11px;width:100%;display:flex;align-items:center;justify-content:center;gap:7px}.gapbtn:hover{border-color:var(--accent);color:var(--accent)}.gaprow{border:1px solid var(--line);border-radius:10px;padding:11px 13px;margin-bottom:8px;background:var(--panel)}.gaprow .gh{display:flex;gap:8px;align-items:center;margin-bottom:5px}.gaprow .gid{font-weight:700;font-size:12px}.sev{font-size:10px;font-weight:700;padding:1px 7px;border-radius:999px;text-transform:uppercase;letter-spacing:.4px}.sev.critical,.sev.high{background:var(--red-soft);color:var(--red)}.sev.medium{background:var(--amber-soft);color:var(--amber)}.sev.low{background:var(--panel-2);color:var(--muted)}.stt{font-size:10px;color:var(--muted-2);margin-left:auto}.gaprow .gq{font-size:12.5px;color:var(--txt);line-height:1.45}.empty{grid-column:1/-1;text-align:center;color:var(--muted);padding:40px}.foot{margin-top:34px;color:var(--muted-2);font-size:11.5px;text-align:center;line-height:1.7}.lock{display:inline-flex;align-items:center;gap:5px;color:var(--muted);font-size:11px}.toast{position:fixed;bottom:24px;left:50%;transform:translateX(-50%) translateY(20px);background:var(--txt);color:var(--bg);padding:9px 16px;border-radius:999px;font-size:12.5px;font-weight:600;opacity:0;pointer-events:none;transition:all .2s;z-index:20}.toast.show{opacity:1;transform:translateX(-50%) translateY(0)}
.modal{position:fixed;inset:0;display:grid;place-items:center;padding:24px;z-index:30;opacity:0;pointer-events:none;transition:opacity .18s}.modal.open{opacity:1;pointer-events:auto}.modal .mbg{position:absolute;inset:0;background:rgba(0,0,0,.6)}.modal .mcard{position:relative;background:var(--bg);border:1px solid var(--line);border-radius:14px;width:min(820px,96vw);max-height:88vh;display:flex;flex-direction:column;box-shadow:0 20px 60px rgba(0,0,0,.5)}.modal .mh{display:flex;justify-content:space-between;align-items:center;gap:12px;padding:14px 18px;border-bottom:1px solid var(--line)}.modal .mh h2{margin:0;font-size:14.5px}.modal .mtools{display:flex;gap:8px;align-items:center;flex-shrink:0}.modal .mbody{padding:18px 22px 26px;overflow-y:auto}.md{font-size:13.5px;line-height:1.6;color:var(--txt)}.md h1{font-size:19px;margin:.1em 0 .5em}.md h2{font-size:15.5px;margin:1.1em 0 .4em;border-bottom:1px solid var(--line);padding-bottom:4px}.md h3{font-size:13.5px;margin:1em 0 .3em;text-transform:none;letter-spacing:0;color:var(--txt)}.md p{margin:.5em 0}.md ul,.md ol{margin:.4em 0 .4em 1.25em;padding:0}.md li{margin:.2em 0}.md code{font-family:ui-monospace,Menlo,Consolas,monospace;background:var(--panel-2);padding:1px 5px;border-radius:5px;font-size:12px}.md pre{background:var(--panel-2);border:1px solid var(--line);border-radius:8px;padding:12px;overflow:auto}.md pre code{background:none;padding:0}.md table{border-collapse:collapse;width:100%;margin:.7em 0;font-size:12.5px}.md th,.md td{border:1px solid var(--line);padding:6px 9px;text-align:left}.md th{background:var(--panel-2)}.md blockquote{border-left:3px solid var(--line);margin:.5em 0;padding:.2em 0 .2em 12px;color:var(--muted)}.mini-link{font-size:11.5px;color:var(--muted);margin-top:14px;display:inline-block}
</style>
</head>
<body>
<script id="dashboard-data" type="application/json">__DASHBOARD_DATA__</script>
<script id="section-registry" type="application/json">__SECTION_REGISTRY__</script>
<div class="wrap">
  <header class="top"><div class="brand"><div class="spark">◆</div><div><h1>Ignite Sentinel - Workspaces</h1><div class="sub">Madurez de requerimientos de un vistazo · sin abrir un solo .md</div></div></div><div class="snap">Snapshot: <b id="snapTime">-</b><br><span class="lock">Local-first · datos embebidos en el HTML</span></div></header>
  <div class="kpis" id="kpis"></div>
  <div class="controls"><div class="search"><input id="q" placeholder="Buscar workspace..."></div><div class="seg" id="fHealth"><button data-v="all" class="active">Todos</button><button data-v="CLEAN">Clean</button><button data-v="DIRTY">Dirty</button></div><div class="seg" id="fAttn"><button data-v="all" class="active">Toda la cartera</button><button data-v="attn">Requiere atencion</button></div></div>
  <div class="grid" id="grid"></div>
  <div class="foot">Dashboard local read-only generado por <code>/dashboard</code>.<br>El HTML es un snapshot reconstruible; los archivos del workspace siguen siendo la fuente de verdad.</div>
</div>
<div class="scrim" id="scrim" onclick="closeDrawer()"></div><aside class="drawer" id="drawer" aria-hidden="true"></aside><div class="toast" id="toast">Copiado</div>
<div class="modal" id="modal"><div class="mbg" onclick="closeModal()"></div><div class="mcard"><div class="mh"><h2 id="modalTitle"></h2><div class="mtools" id="modalTools"></div></div><div class="mbody" id="modalBody"></div></div></div>
<script>
const MODEL=JSON.parse(document.getElementById("dashboard-data").textContent);
const SECTIONS=JSON.parse(document.getElementById("section-registry").textContent);
const WORKSPACES=MODEL.workspaces||[];
const STEPS=[{key:"ingest",group:"Discovery",label:"Ingesta",desc:"Cargar el requerimiento crudo del cliente"},{key:"gaps",group:"Discovery",label:"Gaps",desc:"Detectar y resolver vacios e incognitas"},{key:"brief",group:"Discovery",label:"Project Brief",desc:"Consolidar objetivo, alcance y actores"},{key:"prd",group:"Specifications",label:"PRD",desc:"Documento de requerimientos del producto"},{key:"specs",group:"Specifications",label:"Specs",desc:"Especificaciones funcionales detalladas"},{key:"backlog",group:"Backlog",label:"Backlog",desc:"Historias de usuario derivadas de las specs"},{key:"quality",group:"Backlog",label:"Calidad (AC/DoD)",desc:"Criterios de aceptacion y gates de cada historia"}];
const GROUPS=["Discovery","Specifications","Backlog"];
const $=s=>document.querySelector(s), $$=s=>[...document.querySelectorAll(s)];
let state={q:"",health:"all",attn:"all"};
function esc(s){return String(s??"").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");}
function fmtTime(s){if(!s)return "-";return new Date(s).toLocaleString(undefined,{day:"2-digit",month:"short",hour:"2-digit",minute:"2-digit"});}
function stage(w){return w.lifecycle||{index:0,blocked:false,text:w.readiness_stage||"DISCOVERY_RAW"}}
function needsAttn(w){return w.health==="DIRTY"||(w.gap_counts?.blocking_open||0)>0||stage(w).blocked||((w.story_gates?.warnings||[]).length>0)}
function toast(){const t=$("#toast");t.classList.add("show");clearTimeout(window._tt);window._tt=setTimeout(()=>t.classList.remove("show"),1400)}
function copy(txt){if(navigator.clipboard&&window.isSecureContext){navigator.clipboard.writeText(txt).then(toast,()=>fallbackCopy(txt))}else fallbackCopy(txt)}
function fallbackCopy(txt){const t=document.createElement("textarea");t.value=txt;t.style.position="fixed";t.style.opacity="0";document.body.appendChild(t);t.focus();t.select();try{document.execCommand("copy");toast()}catch(e){}document.body.removeChild(t)}
function renderKpis(){const k=MODEL.kpis||{};$("#kpis").innerHTML=`<div class="kpi"><div class="n">${k.total||0}</div><div class="l">Workspaces</div></div><div class="kpi ${(k.attention||0)?"warn":"ok"}"><div class="n">${k.attention||0}</div><div class="l">Requieren atencion</div></div><div class="kpi ${(k.blocking_gaps||0)?"warn":""}"><div class="n">${k.blocking_gaps||0}</div><div class="l">Gaps bloqueantes</div></div><div class="kpi ok"><div class="n">${k.ready||0}</div><div class="l">Listos para avanzar</div></div><div class="kpi mid"><div class="n">${k.stories||0}</div><div class="l">User stories totales</div></div>`}
function pipeHtml(w){const st=stage(w);let html='<div class="pipe">';GROUPS.forEach(g=>{const idxs=STEPS.map((s,i)=>({s,i})).filter(o=>o.s.group===g);html+=`<div class="ph" style="--w:${idxs.length}">`;idxs.forEach(({i})=>{let cls="tick";if(i<st.index)cls+=" done";else if(i===st.index)cls+=st.blocked?" blocked":" current";html+=`<div class="${cls}"></div>`});html+="</div>"});html+='</div><div class="pipe-labels">';const cur=STEPS[st.index]?.group;GROUPS.forEach(g=>{const n=STEPS.filter(s=>s.group===g).length;const cls=g===cur?(st.blocked?"curblk":"cur"):"";html+=`<span class="${cls}" style="flex:${n}">${g}</span>`});return html+"</div>"}
function renderGrid(){const list=WORKSPACES.filter(w=>{if(state.q&&!w.project_id.toLowerCase().includes(state.q.toLowerCase()))return false;if(state.health!=="all"&&w.health!==state.health)return false;if(state.attn==="attn"&&!needsAttn(w))return false;return true});const g=$("#grid");if(!list.length){g.innerHTML='<div class="empty">No hay workspaces que coincidan con el filtro.</div>';return}g.innerHTML=list.map(w=>{const st=stage(w),gc=w.gap_counts||{},bl=w.backlog_rollup||{},prog=bl.total_stories?Math.round((bl.done/bl.total_stories)*100):0;return `<div class="card" onclick="openDrawer('${esc(w.project_id)}')"><div class="row1"><div><div class="pid">${esc(w.project_id)}</div><div class="stage">${esc(st.text)}</div></div><span class="pill h-${esc(w.health)}"><span class="dot"></span>${esc(w.health)}</span></div>${pipeHtml(w)}<div class="mini"><span class="m ${(gc.blocking_open||0)?"bad":""}">Gaps abiertos <b>${(gc.open||0)+(gc.partially_closed||0)}</b>${(gc.blocking_open||0)?` · <b>${gc.blocking_open} bloq.</b>`:""}</span>${bl.total_stories?`<span class="m">Stories <b>${bl.done||0}/${bl.total_stories}</b></span>`:`<span class="m">Madurez <b>${w.summary?.Madurez||"-"}</b></span>`}</div>${bl.total_stories?`<div class="bar"><i style="width:${prog}%"></i></div>`:""}<div class="next"><div class="nh">${esc(w.next_title)}</div><p>${esc(w.next_detail)}</p></div></div>`}).join("")}
function openDrawer(pid){const w=WORKSPACES.find(x=>x.project_id===pid);if(!w)return;const st=stage(w),gc=w.gap_counts||{},bl=w.backlog_rollup||{},gaps=w.gaps_detail||[],docs=w.documents||[],warnings=w.story_gates?.warnings||[],gateRows=Object.entries(w.story_gates?.stories||{});let flow="",last=null;STEPS.forEach((s,i)=>{if(s.group!==last){flow+=`<div class="grp">${s.group}</div>`;last=s.group}let cls="st",ic=i+1,badge="";if(i<st.index){cls+=" done";ic="✓"}else if(i===st.index){cls+=st.blocked?" blocked":" current";ic=st.blocked?"!":ic;badge=`<span class="badge">${st.blocked?"bloqueado":"en curso"}</span>`}flow+=`<div class="${cls}"><div class="ic">${ic}</div><div><div class="t">${esc(s.label)}${badge}</div><div class="d">${esc(s.desc)}</div></div></div>`});const scenarios=(w.scenarios||[]).map(s=>`<details class="scn"><summary>${esc(s.title)}<span class="chev">›</span></summary><div class="inner"><p>Prompt sugerido (pegalo en el chat de tu asistente):</p><div class="prompt">${esc(s.prompt)}</div><div class="prompt-row"><button class="copybtn" onclick="copy(this.dataset.p)" data-p="${esc(s.prompt)}">Copiar prompt</button></div><details class="adv"><summary>Comando de terminal (avanzado)</summary><div class="cmd">${esc(s.command)}</div></details></div></details>`).join("");const summary=Object.entries(w.summary||{}).map(([k,v])=>`<div class="b"><div class="l">${esc(k)}</div><div class="v">${esc(v)}</div></div>`).join("");const gates=gateRows.length?`<table class="gates"><thead><tr><th>Story</th><th>DoR</th><th>DoD</th><th>Falta</th></tr></thead><tbody>${gateRows.map(([id,g])=>`<tr><td><b>${esc(id)}</b></td><td class="chk ${g.dor_passed?"ok":"no"}">${g.dor_passed?"✓":"×"}</td><td class="chk ${g.dod_passed?"ok":"no"}">${g.dod_passed?"✓":"×"}</td><td class="miss">${esc([...(g.dor_missing||[]).map(m=>"DoR: "+m),...(g.dod_missing||[]).map(m=>"DoD: "+m)].join("\\n")||"-").replace(/\\n/g,"<br>")}</td></tr>`).join("")}</tbody></table>`:"";$("#drawer").innerHTML=`<div class="dh"><div><h2>${esc(w.project_id)}</h2><div style="margin-top:6px;display:flex;gap:8px;flex-wrap:wrap"><span class="pill h-${esc(w.health)}"><span class="dot"></span>${esc(w.health)}</span><span class="pill" style="background:var(--violet-soft);color:var(--violet)">${esc(st.text)}</span><span class="lock">${esc(w.privacy_mode)} · ${esc(w.project_language)}</span></div></div><button class="close" onclick="closeDrawer()">×</button></div><div class="body"><div class="actionbox"><div class="ah">Proximo paso · ${esc(w.next_title)}</div><p class="detail">${esc(w.next_detail)}</p><div class="prompt">${esc(w.next_prompt)}</div><div class="prompt-row"><button class="copybtn" onclick="copy(this.dataset.p)" data-p="${esc(w.next_prompt)}">Copiar prompt para tu asistente</button></div><details class="adv"><summary>Comando de terminal (avanzado)</summary><div class="cmd">${esc(w.next_cmd)}</div></details></div><div class="sec"><h3>¿Cambio algo? Acciones segun la situacion</h3>${scenarios}</div><div class="sec"><h3>Lifecycle de maduracion</h3><div class="stepflow">${flow}</div></div><div class="sec"><h3>Resumen</h3><div class="kv">${summary}</div>${gaps.length?`<button class="gapbtn" onclick="openGaps('${esc(pid)}')">Ver y copiar los ${gaps.length} gaps pendientes -></button>`:""}</div>${docs.length?`<div class="sec"><h3>Documentos</h3><div class="docchips">${docs.map(d=>`<button class="docchip" onclick="openDoc('${esc(pid)}','${esc(d.key)}')">${esc(d.label)}</button>`).join("")}</div></div>`:""}${bl.total_stories?`<div class="sec"><h3>Backlog</h3><div class="kv"><div class="b"><div class="l">Total stories</div><div class="v">${bl.total_stories}</div></div><div class="b"><div class="l">Ready</div><div class="v">${bl.ready||0}</div></div><div class="b"><div class="l">In progress</div><div class="v">${bl.in_progress||0}</div></div><div class="b"><div class="l">Done</div><div class="v">${bl.done||0}</div></div></div></div>`:""}${gateRows.length?`<div class="sec"><h3>Story gates (DoR / DoD)</h3>${gates}</div>`:""}${warnings.length?`<div class="sec"><h3>Warnings</h3><div class="warnbox">${warnings.length} item(s) de readiness pendientes:<ul>${warnings.map(x=>`<li>${esc(x)}</li>`).join("")}</ul></div></div>`:""}<div class="foot" style="text-align:left;margin-top:26px">Origen: snapshot de <code>/status ${esc(pid)}</code> · actualizado ${fmtTime(w.updated_at)}</div></div>`;$("#scrim").classList.add("open");$("#drawer").classList.add("open")}
function closeDrawer(){$("#scrim").classList.remove("open");$("#drawer").classList.remove("open")}
function showModal(){$("#modal").classList.add("open")}function closeModal(){$("#modal").classList.remove("open")}
function gapTemplate(pid){const gaps=(WORKSPACES.find(w=>w.project_id===pid)?.gaps_detail)||[];return "Gaps pendientes - "+pid+"\\nGenerado: "+new Date().toLocaleDateString()+"\\n\\nPor favor completa tu respuesta debajo de cada pregunta y devolve este documento.\\n"+gaps.map(g=>"\\n------------------------------\\n["+g.id+" · "+String(g.severity||'').toUpperCase()+" · "+g.status+"]\\n"+(g.question||g.description||"")+"\\n\\nRespuesta:\\n").join("")}
function openGaps(pid){const gaps=(WORKSPACES.find(w=>w.project_id===pid)?.gaps_detail)||[];$("#modalTitle").textContent="Gaps pendientes - "+pid;$("#modalTools").innerHTML=`<button class="copybtn" onclick="copy(gapTemplate('${esc(pid)}'))">Copiar todo para el cliente</button>`;$("#modalBody").innerHTML=`<p class="docnote" style="margin-top:0">${gaps.length} gap(s) abiertos o parciales.</p>`+gaps.map(g=>`<div class="gaprow"><div class="gh"><span class="gid">${esc(g.id)}</span><span class="sev ${esc(g.severity)}">${esc(g.severity)}</span><span class="stt">${esc(g.status)}${g.lens?" · "+esc(g.lens):""}</span></div><div class="gq">${esc(g.question||g.description||"")}</div></div>`).join("");showModal()}
function openDoc(pid,key){const w=WORKSPACES.find(x=>x.project_id===pid),d=(w?.documents||[]).find(x=>x.key===key);if(!d)return;$("#modalTitle").textContent=d.label+" - "+pid;$("#modalTools").innerHTML=`<button class="copybtn ghost" onclick="copyDoc('${esc(pid)}','${esc(key)}')">Copiar markdown</button>`;$("#modalBody").innerHTML=`<div class="md">${mdToHtml(d.content)}</div><a class="mini-link" href="${esc(d.path)}" target="_blank" rel="noopener">Abrir archivo original · ${esc(d.path)}</a>`;showModal()}
function copyDoc(pid,key){const w=WORKSPACES.find(x=>x.project_id===pid),d=(w?.documents||[]).find(x=>x.key===key);if(d)copy(d.content)}
function mdInline(s){return esc(s).replace(/`([^`]+)`/g,(m,c)=>"<code>"+esc(c)+"</code>").replace(/\*\*([^*]+)\*\*/g,"<strong>$1</strong>").replace(/\*([^*]+)\*/g,"<em>$1</em>").replace(/\[([^\]]+)\]\(([^)]+)\)/g,'<a href="$2" target="_blank" rel="noopener">$1</a>')}
function mdToHtml(md){const lines=String(md||"").replace(/\r/g,"").split("\n");let out="",list=null,i=0;const close=()=>{if(list){out+="</"+list+">";list=null}};while(i<lines.length){let ln=lines[i],m;if(/^\s*\|/.test(ln)){const tbl=[];while(i<lines.length&&/^\s*\|/.test(lines[i])){tbl.push(lines[i]);i++}close();const rows=tbl.map(r=>r.trim().replace(/^\||\|$/g,"").split("|").map(c=>c.trim()));const sep=rows[1]&&rows[1].every(c=>/^:?-+:?$/.test(c));const header=rows[0],body=rows.slice(sep?2:1);out+="<table><thead><tr>"+header.map(c=>"<th>"+mdInline(c)+"</th>").join("")+"</tr></thead><tbody>"+body.map(r=>"<tr>"+r.map(c=>"<td>"+mdInline(c)+"</td>").join("")+"</tr>").join("")+"</tbody></table>";continue}if(/^\s*$/.test(ln)){close();i++;continue}if(m=ln.match(/^(#{1,4})\s+(.*)$/)){close();const n=m[1].length;out+="<h"+n+">"+mdInline(m[2])+"</h"+n+">";i++;continue}if(m=ln.match(/^>\s?(.*)$/)){close();out+="<blockquote>"+mdInline(m[1])+"</blockquote>";i++;continue}if(m=ln.match(/^\s*[-*]\s+(.*)$/)){if(list!=="ul"){close();out+="<ul>";list="ul"}out+="<li>"+mdInline(m[1])+"</li>";i++;continue}if(m=ln.match(/^\s*\d+\.\s+(.*)$/)){if(list!=="ol"){close();out+="<ol>";list="ol"}out+="<li>"+mdInline(m[1])+"</li>";i++;continue}close();out+="<p>"+mdInline(ln)+"</p>";i++}close();return out}
document.addEventListener("keydown",e=>{if(e.key==="Escape"){if($("#modal").classList.contains("open"))closeModal();else closeDrawer()}});
$("#q").addEventListener("input",e=>{state.q=e.target.value;renderGrid()});$$("#fHealth button").forEach(b=>b.onclick=()=>{$$("#fHealth button").forEach(x=>x.classList.remove("active"));b.classList.add("active");state.health=b.dataset.v;renderGrid()});$$("#fAttn button").forEach(b=>b.onclick=()=>{$$("#fAttn button").forEach(x=>x.classList.remove("active"));b.classList.add("active");state.attn=b.dataset.v;renderGrid()});
$("#snapTime").textContent=fmtTime(MODEL.generated_at);renderKpis();renderGrid();
</script>
</body>
</html>"""
