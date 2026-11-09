"""Build-readiness view (IMP-247): what is missing, per item, and from whom.

`/view PROJECT_ID --artifact readiness`. One card per item (the workspace, each
backlog story, each SLICE-PLAN wave) with the governed verdict of IMP-248, and
every open request grouped by recipient with "copy request". This view is the
only owner of the per-recipient request (doc 49 [C19]).

model -> validate -> render, inside the common shell (CSP, themes). Read-only:
local marks live in the reader's browser (localStorage), never in the workspace.
"""
from __future__ import annotations

import html
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .core.io import write_text
from .core.local_browser import open_local_file
from .discovery import lens_for_gap
from .gaps import BLOCKING_GAP_STATUSES, parse_gap_table
from .readiness_verdict import VERDICTS, build_readiness_verdict
from .secrets_scan import assert_no_leaks
from .shell import content_fingerprint, fill, json_for_script, render_shell, template_text, theme_argument_for_display
from .stakeholders import load_stakeholders, owner_for_lens, registry_path
from .themes import DEFAULT_THEME, legend_html
from .workspace import read_json, workspace_path

SEVERITY = {"READY": 0, "READY_WITH_WARNINGS": 1, "NOT_READY": 2}
BLOCKS = ("start", "slice", "no")
CLIENT_LENSES = {"business", "product"}

LABELS = {
    "en": {
        "label": "Build Readiness",
        "client": "Client (unassigned)",
        "domain": "Domain: {lens} (unassigned)",
        "ba": "BA",
        "workspace": "Workspace",
        "wave": "Wave {n}",
        "dor": "Definition of Ready: {missing}",
    },
    "es": {
        "label": "Readiness de construcción",
        "client": "Cliente (sin asignar)",
        "domain": "Dominio: {lens} (sin asignar)",
        "ba": "BA",
        "workspace": "Workspace",
        "wave": "Ola {n}",
        "dor": "Definition of Ready: {missing}",
    },
}


class ReadinessModelError(ValueError):
    """The readiness model is inconsistent; the HTML is not written."""


def merge_verdicts(verdicts: list[str]) -> str:
    """The most severe verdict. Nothing to merge is never green."""
    if not verdicts:
        return "READY_WITH_WARNINGS"
    return max(verdicts, key=lambda v: SEVERITY.get(v, 2))


def collect_readiness_model(project_id: str) -> dict[str, Any]:
    base = workspace_path(project_id)
    state = read_json(base / "state.json", {})
    language = "es" if str(state.get("project_language", "")).lower().startswith("es") else "en"
    text = LABELS[language]
    verdict = build_readiness_verdict(project_id)
    stakeholders = load_stakeholders(project_id)

    items: list[dict[str, Any]] = [{
        "id": "workspace",
        "kind": "workspace",
        "label": text["workspace"],
        "verdict": verdict["verdict"],
        "empty": False,
        "stories": [],
    }]
    requests: list[dict[str, Any]] = []
    recipients: dict[str, dict[str, Any]] = {}

    def recipient_for(lens: str) -> tuple[str, str, bool]:
        owner = owner_for_lens(lens, stakeholders) if lens else None
        if owner:
            return f"stk:{owner['id']}", f"{owner['name']} ({owner['domain']})", True
        if lens in CLIENT_LENSES:
            return "client", text["client"], False
        return f"domain:{lens or 'general'}", text["domain"].format(lens=lens or "general"), False

    def add_request(request: dict[str, Any], key: str, label: str, assigned: bool) -> None:
        request["recipient"] = key
        requests.append(request)
        entry = recipients.setdefault(key, {"key": key, "label": label, "assigned": assigned, "request_ids": []})
        entry["request_ids"].append(request["id"])

    gaps_path = base / "01_discovery" / "gaps.md"
    gaps = parse_gap_table(gaps_path.read_text(encoding="utf-8")) if gaps_path.exists() else []
    blocking = set(verdict["blocking_open"])
    for gap in gaps:
        status = str(gap.get("status", "OPEN")).strip("`").upper()
        if status not in BLOCKING_GAP_STATUSES:
            continue
        gap_id = str(gap["id"]).strip("`")
        lens = str(gap.get("lens") or lens_for_gap(gap_id)).strip().lower()
        key, label, assigned = recipient_for(lens)
        add_request({
            "id": f"gap:{gap_id}",
            "kind": "gap",
            "source_id": gap_id,
            "item": "workspace",
            "blocks": "start" if gap_id in blocking else "no",
            "severity": str(gap.get("severity", "")).lower(),
            "status": status,
            "lens": lens,
            "text": str(gap.get("question") or gap.get("description") or gap_id),
        }, key, label, assigned)

    story_items = {k: v for k, v in verdict["by_item"].items() if k != "workspace"}
    for story_id, story in sorted(story_items.items()):
        items.append({"id": story_id, "kind": "story", "label": story_id, "verdict": story["verdict"], "empty": False, "stories": []})
        if story["verdict"] == "READY":
            continue
        for index, missing in enumerate(story.get("missing", []), start=1):
            add_request({
                "id": f"dor:{story_id}:{index}",
                "kind": "dor",
                "source_id": story_id,
                "item": story_id,
                "blocks": "slice",
                "severity": "",
                "status": "OPEN",
                "lens": "",
                "text": text["dor"].format(missing=missing),
            }, "ba", text["ba"], True)

    plan = read_json(base / "08_context_packs" / "slice_plan.json", {})
    for checkpoint in plan.get("checkpoints", []) if isinstance(plan, dict) else []:
        wave_id = str(checkpoint.get("id", ""))
        if not wave_id.startswith("CHK-WAVE-"):
            continue
        stories = [str(s) for s in checkpoint.get("stories", [])]
        items.append({
            "id": wave_id,
            "kind": "wave",
            "label": text["wave"].format(n=wave_id.rsplit("-", 1)[-1]),
            "verdict": merge_verdicts([story_items.get(s, {}).get("verdict", "NOT_READY") for s in stories]),
            "empty": not stories,
            "stories": stories,
        })

    ordered_recipients = sorted(recipients.values(), key=lambda r: (not r["assigned"], r["key"]))
    sources = _sources(project_id, base, [
        "state.json",
        "01_discovery/gaps.md",
        "08_context_packs/slice_plan.json",
        registry_path(project_id).relative_to(base).as_posix(),
    ])
    model = {
        "project_id": project_id,
        "artifact": "readiness",
        "label": text["label"],
        "language": language,
        "verdict": {k: verdict[k] for k in ("verdict", "blockers", "warnings", "partial_coverage", "counts", "gate_matrix", "maturity_score", "next_step")},
        "items": items,
        "requests": requests,
        "recipients": ordered_recipients,
        "summary": {
            "items": len(items),
            "requests": len(requests),
            "recipients": len(ordered_recipients),
            "blocks_start": sum(1 for r in requests if r["blocks"] == "start"),
            "blocks_slice": sum(1 for r in requests if r["blocks"] == "slice"),
        },
        "provenance": {
            "cutoff": max((s["mtime"] for s in sources), default="1970-01-01T00:00:00+00:00"),
            "source_sha256": content_fingerprint("\n".join(f"{s['path']}:{s['sha256']}" for s in sources).encode("utf-8")),
            "sources": [{"path": s["path"], "sha256": s["sha256"]} for s in sources],
        },
    }
    return model


# state.json and slice_plan.json also carry timestamps and caches; the view reads
# only these fields, so their fingerprints cover only them and stay reproducible.
STATE_FIELDS = ("phase", "readiness_stage", "story_gates", "project_language")


def _sources(project_id: str, base: Path, relatives: list[str]) -> list[dict[str, str]]:
    found = []
    for rel in relatives:
        path = base / rel
        if path.is_file():
            data = path.read_bytes()
            if rel == "state.json":
                state = read_json(path, {})
                data = json.dumps({k: state.get(k) for k in STATE_FIELDS}, sort_keys=True).encode("utf-8")
                rel = "state.json#" + ",".join(STATE_FIELDS)
            elif rel.endswith("slice_plan.json"):
                plan = read_json(path, {})
                checkpoints = [
                    {"id": c.get("id"), "stories": c.get("stories", [])}
                    for c in (plan.get("checkpoints", []) if isinstance(plan, dict) else [])
                ]
                data = json.dumps(checkpoints, sort_keys=True).encode("utf-8")
                rel = rel + "#checkpoints"
            found.append({
                "path": f"workspaces/{project_id}/{rel}",
                "sha256": content_fingerprint(data),
                "mtime": datetime.fromtimestamp(int(path.stat().st_mtime), timezone.utc).isoformat(),
            })
    return found


def validate_readiness_model(model: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    items = model.get("items") or []
    requests = model.get("requests") or []
    recipients = model.get("recipients") or []
    item_ids = [str(i.get("id")) for i in items]
    request_ids = [str(r.get("id")) for r in requests]
    for label, ids in (("item", item_ids), ("request", request_ids), ("recipient", [str(r.get("key")) for r in recipients])):
        for dup in sorted({v for v in ids if ids.count(v) > 1}):
            errors.append(f"duplicate {label} id {dup!r}")
    known_items = set(item_ids)
    for request in requests:
        if request.get("item") not in known_items:
            errors.append(f"{request.get('id')}: item {request.get('item')!r} is not in the model")
        if request.get("blocks") not in BLOCKS:
            errors.append(f"{request.get('id')}: blocks {request.get('blocks')!r} is not one of {', '.join(BLOCKS)}")
    known_requests = set(request_ids)
    routed = [rid for r in recipients for rid in r.get("request_ids", [])]
    for rid in routed:
        if rid not in known_requests:
            errors.append(f"recipient lists unknown request {rid!r}")
    for rid in sorted(known_requests - set(routed)):
        errors.append(f"request {rid!r} has no recipient")
    for item in items:
        if item.get("verdict") not in VERDICTS:
            errors.append(f"{item.get('id')}: verdict {item.get('verdict')!r} is not one of {', '.join(VERDICTS)}")
        if item.get("kind") == "wave" and item.get("empty") and item.get("verdict") == "READY":
            errors.append(f"{item.get('id')}: a wave without stories cannot be green")
    summary = model.get("summary") or {}
    for key, actual in (
        ("items", len(items)),
        ("requests", len(requests)),
        ("recipients", len(recipients)),
        ("blocks_start", sum(1 for r in requests if r.get("blocks") == "start")),
        ("blocks_slice", sum(1 for r in requests if r.get("blocks") == "slice")),
    ):
        if summary.get(key) != actual:
            errors.append(f"summary.{key} is {summary.get(key)!r}, the model has {actual}")
    provenance = model.get("provenance")
    if not isinstance(provenance, dict) or not provenance.get("cutoff") or not provenance.get("source_sha256"):
        errors.append("provenance with cutoff and source_sha256 is required")
    return errors


def render_readiness_view(model: dict[str, Any], theme: dict[str, Any], *, theme_arg: str | None = None) -> str:
    errors = validate_readiness_model(model)
    if errors:
        raise ReadinessModelError("readiness model is inconsistent: " + "; ".join(errors))
    language = model.get("language", "en")
    legend_title = "Leyenda de colores" if language == "es" else "Colour legend"
    content = (
        fill("readiness-page.html", data_json=json_for_script(model))
        + f'<section class="view-section" id="legend"><h2>{legend_title}</h2>{legend_html(theme, language)}</section>'
        + _provenance_section(model, theme_arg or str(theme.get("name") or DEFAULT_THEME))
    )
    return render_shell(
        theme=theme,
        title=f"{model['project_id']} · {model['label']} — Ignite Artifact View",
        heading=str(model["label"]),
        nav=template_text("readiness-nav.html"),
        content=content,
        page_css=template_text("readiness.css"),
        page_js=template_text("readiness.js"),
        language=language,
    )


def _provenance_section(model: dict[str, Any], theme_arg: str) -> str:
    provenance = model["provenance"]
    heading = "Procedencia" if model.get("language") == "es" else "Provenance"
    command = html.escape(f"python -m sentinel /view {model['project_id']} --artifact readiness --theme {theme_argument_for_display(theme_arg)}")
    sources = ", ".join(f"<code>{html.escape(s['path'])}</code>" for s in provenance.get("sources", []))
    return (
        f'<section class="view-section" id="provenance"><h2>{heading}</h2>'
        f"<p>Sources: {sources} · sha256 <code>{html.escape(provenance['source_sha256'])}</code> · "
        f'cut-off <time datetime="{html.escape(provenance["cutoff"])}">{html.escape(provenance["cutoff"])}</time> '
        "(the newest source modification time, not the build time).</p>"
        f"<p>Regenerate: <code>{command}</code></p></section>"
    )


def generate_readiness_view(project_id: str, open_browser: bool = False, theme: str | Path | None = None) -> dict[str, Any]:
    from .view import resolve_view_theme

    loaded, theme_arg, theme_warning = resolve_view_theme(project_id, theme)
    if theme_warning:
        print(f"sentinel warning: {theme_warning}", file=sys.stderr)
    model = collect_readiness_model(project_id)
    rendered = render_readiness_view(model, loaded, theme_arg=theme_arg)
    out_dir = workspace_path(project_id) / "08_context_packs" / "views"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / "readiness.html"
    assert_no_leaks(project_id, rendered, workspace_path(project_id), "/view readiness")
    write_text(out, rendered, newline="\n")
    if open_browser:
        open_local_file(out)
    return {
        "path": str(out),
        "artifact": "readiness",
        "verdict": model["verdict"]["verdict"],
        "items": model["summary"]["items"],
        "requests": model["summary"]["requests"],
        "recipients": model["summary"]["recipients"],
        "cutoff": model["provenance"]["cutoff"],
        "source_sha256": model["provenance"]["source_sha256"],
        "theme": loaded["name"],
        **({"theme_warning": theme_warning} if theme_warning else {}),
    }
