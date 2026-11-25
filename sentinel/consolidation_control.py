"""IMP-414 (H27 inc 5a) task 3: the control table of the consolidation, element by element.

The coverage of the extraction counts treatments, not whether a decision that touches an element was applied to its text.
This module crosses every element of the request with the closed decisions that link to it and says, for each one,
whether it is included as it stands, modified (its replacement text is confirmed), excluded (a discard) or pending.
Nothing here decides: it reads the extraction, the closed decisions and `extraction/consolidation.json`.
"""
from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path
from typing import Any

from .changes import change_language, get_change
from .core.io import write_json, write_text
from .core.paths import workspace_path
from .extraction.consolidation import (
    KEEPS_REQUEST, RETIRES, decisions_moved, keeps_request, linked, load_consolidation, retires,
)
from .extraction.inventory import element_lines
from .extraction.lines import format_ranges

__all__ = [
    "KEEPS_REQUEST", "RETIRES", "keeps_request", "retires", "consolidation_control", "consolidation_sha",
    "write_consolidation_control", "control_dir",
]

STATUSES = ("incluido", "modificado", "excluido", "pendiente")
ENGLISH = {"incluido": "included", "modificado": "modified", "excluido": "excluded", "pendiente": "pending"}

_TEXT = {
    "unconfirmed": ("sin confirmar en la extracción", "not confirmed in the extraction"),
    "retired": ("{gap} lo saca del cambio: proponelo como descarte", "{gap} takes it out of the change: propose it as a discard"),
    "proposed": ("reemplazo sin confirmar", "replacement not confirmed"),
    "moved": ("la decisión {gaps} cambió: reconfirmá el reemplazo", "the decision {gaps} changed: confirm the replacement again"),
    "missing": ("falta reemplazo o --keep-text para {gaps}", "a replacement or --keep-text is missing for {gaps}"),
    "kept": ("se conserva el texto del pedido: {reason}", "the request text stays: {reason}"),
    "head": ("# Control de consolidación — {cid}", "# Consolidation control — {cid}"),
    "internal": ("> Interno: no forma parte del entregable.", "> Internal: not part of the deliverable."),
    "table": ("| Elemento | Estado | GAP | Reemplazo | Motivo |", "| Element | Status | GAP | Replacement | Reason |"),
    "to_do": ("## Para consolidar", "## To consolidate"),
    "decision": ("- Decisión: {gaps}", "- Decision: {gaps}"),
    "lines": ("- Líneas: {lines}", "- Lines: {lines}"),
    "text": ("- Texto:", "- Text:"),
}


def _t(code: str, language: str, **values: Any) -> str:
    spanish, english = _TEXT[code]
    return (spanish if language == "es" else english).format(**values)


def control_dir(project_id: str, change_id: str) -> Path:
    return workspace_path(project_id) / "01_discovery" / change_id


def _confirmed(items: dict, element: dict) -> bool:
    item = items.get(element["id"]) or {}
    return item.get("status") == "confirmed" and item.get("element_sha") == element.get("sha")


def _sha_text(text: str) -> str:
    return sha256(str(text).encode("utf-8")).hexdigest()[:16]


def _build(project_id: str, change_id: str) -> tuple[dict, dict[str, dict]]:
    """The control and, per pending element that needs a replacement, `{"gaps", "lines"}` for the worksheet."""
    from .decision_memory import closed_decisions
    from .extraction.coverage import extraction_view

    change = get_change(project_id, change_id)
    language = "es" if change_language(project_id, change) == "es" else "en"
    view = extraction_view(project_id, change_id)
    empty = {"rows": [], "counts": {k: 0 for k in STATUSES}, "pending": [], "unconfirmed": [], "state": view["state"]}
    if view["state"] == "missing":
        return empty, {}
    store = load_consolidation(workspace_path(project_id), change_id)
    decisions = closed_decisions(project_id, change_id)
    rows: list[dict] = []
    needs: dict[str, dict] = {}
    unconfirmed: list[str] = []
    shas: dict[str, str] = {}
    for element in view["elements"]:
        element_id = str(element["id"])
        row = {"element": element_id, "status": "pendiente", "gaps": [], "replacement": "", "reason": ""}
        rows.append(row)
        item = view["items"].get(element_id) or {}
        mine = [d for d in decisions if linked(d, element)]
        if not _confirmed(view["items"], element):
            row["reason"] = _t("unconfirmed", language)
            continue
        retiring = [d["id"] for d in mine if retires(d)]
        if item.get("treatment") == "descarte":
            row.update(status="excluido", gaps=retiring, reason=str(item.get("reason") or ""))
            continue
        if retiring:
            row.update(gaps=retiring, reason=_t("retired", language, gap=retiring[0]))
            continue
        changing = [str(d["id"]) for d in mine if not keeps_request(d, element) and not retires(d)]
        row["gaps"] = changing
        replacement = store["replacements"].get(element_id) or {}
        current = replacement.get("element_sha") == element.get("sha")
        if current and replacement.get("status") == "proposed":
            row["reason"] = _t("proposed", language)
            row["replacement"] = str(replacement.get("id") or f"REP-{element_id}")
            unconfirmed.append(element_id)
            continue
        moved = decisions_moved(replacement, {str(d["id"]): d for d in decisions}) if current else []
        if current and replacement.get("status") == "confirmed" and moved:
            row["reason"] = _t("moved", language, gaps=", ".join(moved))
            row["replacement"] = str(replacement.get("id") or f"REP-{element_id}")
            unconfirmed.append(element_id)
            continue
        covered = set(replacement.get("decisions") or []) if current and replacement.get("status") == "confirmed" else set()
        kept = {g: v for g, v in (store["kept"].get(element_id) or {}).items() if isinstance(v, dict)}
        missing = [g for g in changing if g not in covered and g not in kept]
        if missing:
            row["reason"] = _t("missing", language, gaps=", ".join(missing))
            needs[element_id] = {"gaps": changing, "lines": format_ranges([element_lines(element)])}
            continue
        if covered & set(changing):
            row.update(status="modificado", replacement=str(replacement.get("id") or f"REP-{element_id}"))
            shas[element_id] = _sha_text(
                f"{replacement.get('text', '')}|{json.dumps(replacement.get('decision_shas') or {}, sort_keys=True)}")
        else:
            row["status"] = "incluido"
            if changing:
                first = next(g for g in changing if g in kept)
                row["reason"] = _t("kept", language, reason=str(kept[first].get("reason") or ""))
    counts = {k: sum(1 for r in rows if r["status"] == k) for k in STATUSES}
    pending = [r["element"] for r in rows if r["status"] == "pendiente"]
    return {"rows": rows, "counts": counts, "pending": pending, "unconfirmed": unconfirmed, "state": view["state"],
            "_shas": shas}, needs


def consolidation_control(project_id: str, change_id: str) -> dict:
    """Per element of the request: `incluido`, `modificado`, `excluido` or `pendiente` (read, never written)."""
    result, _needs = _build(project_id, change_id)
    result.pop("_shas", None)
    return result


def consolidation_sha(project_id: str, change_id: str) -> str:
    """16 hex that move when an element changes status, its decisions or the text of its replacement."""
    result, _needs = _build(project_id, change_id)
    shas = result.get("_shas", {})
    payload = [(r["element"], r["status"], r["gaps"], shas.get(r["element"], "")) for r in result["rows"]]
    return sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()[:16]


def _cell(value: str) -> str:
    return " ".join(str(value).replace("|", "/").split())


def write_consolidation_control(project_id: str, change_id: str) -> Path:
    """`01_discovery/CHG-nnn/consolidation_control.md` (internal worksheet) and its `.json`; returns the `.md` path."""
    change = get_change(project_id, change_id)
    language = "es" if change_language(project_id, change) == "es" else "en"
    result, needs = _build(project_id, change_id)
    result.pop("_shas", None)
    lines = [_t("head", language, cid=change_id), "", _t("internal", language), "", _t("table", language),
             "|---|---|---|---|---|"]
    for row in result["rows"]:
        status = row["status"] if language == "es" else ENGLISH[row["status"]]
        lines.append(f"| {row['element']} | {status} | {_cell(', '.join(row['gaps']))} | {_cell(row['replacement'])} "
                     f"| {_cell(row['reason'])} |")
    if needs:
        lines += ["", _t("to_do", language), ""]
        for element_id, need in needs.items():
            lines += [f"### {element_id}", _t("decision", language, gaps=", ".join(need["gaps"])),
                      _t("lines", language, lines=need["lines"]), _t("text", language), ""]
    folder = control_dir(project_id, change_id)
    path = folder / "consolidation_control.md"
    write_text(path, "\n".join(lines).rstrip("\n") + "\n")
    write_json(folder / "consolidation_control.json", result)
    return path
