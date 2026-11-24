"""IMP-402 task 5: what the extraction covers of the change request, and what the border preserves.

Read-only: it counts the inventory against the proposals and the confirmed rows. Nothing here writes.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from ..change_requirements import load_change_ears
from ..changes import change_language, get_change
from ..core.io import read_json
from ..core.paths import workspace_path
from . import extraction_dir
from .inventory import KINDS, _fold, inventory_state, load_inventory
from .proposals import extraction_orphans, load_proposals

_EXT_SOURCE = re.compile(r"`EXT:([^`]+)`")

KIND_LABELS = {
    "es": {"rule": "Reglas", "criterion": "Criterios", "story": "Historias", "decision": "Decisiones", "section": "Secciones"},
    "en": {"rule": "Rules", "criterion": "Criteria", "story": "Stories", "decision": "Decisions", "section": "Sections"},
}


def extraction_coverage(project_id: str, change_id: str) -> dict[str, Any]:
    base = workspace_path(project_id)
    language = change_language(project_id, get_change(project_id, change_id))
    lang = "es" if language == "es" else "en"
    state = inventory_state(project_id, change_id)
    inventory = load_inventory(base, change_id) or {}
    elements = inventory.get("elements", []) if state != "missing" else []
    items = load_proposals(base, change_id)["items"]
    by_id = {e["id"]: e for e in elements}
    by_kind = {kind: {"total": 0, "covered": 0} for kind in KINDS}
    covered = proposed = flagged = 0
    flagged_ids: list[str] = []
    partial_ids: list[dict[str, Any]] = []
    legacy_ids: list[str] = []
    for element in elements:
        kind = element.get("kind")
        if kind in by_kind:
            by_kind[kind]["total"] += 1
        item = items.get(element["id"])
        if not item or item.get("element_sha") != element.get("sha"):
            continue
        if item.get("status") == "confirmed":
            covered += 1
            if not item.get("lines"):
                legacy_ids.append(element["id"])  # confirmed before the line check existed: declared only
            if kind in by_kind:
                by_kind[kind]["covered"] += 1
        elif item.get("status") == "proposed":
            proposed += 1
            if item.get("flags"):
                flagged += 1
                flagged_ids.append(element["id"])
                marks = [f for f in item.get("flags", []) if f.get("origin") == "coverage"]
                if marks:
                    partial_ids.append({
                        "id": element["id"], "missing": item.get("missing_lines") or [],
                        "reading": item.get("reading") or "completa",
                    })
    stale = [
        element_id for element_id, item in items.items()
        if isinstance(item, dict) and (element_id not in by_id or item.get("element_sha") != by_id[element_id].get("sha"))
    ]
    total = len(elements)
    # a pedido source Sentinel could not read leaves part of the request out of the inventory
    unreadable = [str(s) for s in inventory.get("unreadable", []) or []] if state != "missing" else []
    orphans = extraction_orphans(project_id, change_id, elements) if state != "missing" else []
    if state == "missing":
        text = "sin inventario" if lang == "es" else "no inventory"
    else:
        joiner = "de" if lang == "es" else "of"
        parts = ", ".join(
            f"{KIND_LABELS[lang][kind]} {c['covered']} {joiner} {c['total']}" for kind, c in by_kind.items() if c["total"]
        )
        text = f"{covered} {joiner} {total}" + (f" ({parts})" if parts else "")
    return {
        "state": state, "total": total, "covered": covered, "pending": total - covered - proposed,
        "proposed": proposed, "flagged": flagged, "flagged_ids": flagged_ids, "partial_ids": partial_ids, "stale_items": stale,
        "legacy_ids": legacy_ids,
        "unreadable": unreadable, "orphans": orphans,
        "by_kind": {kind: c for kind, c in by_kind.items() if c["total"]},
        "complete": state in ("current", "empty") and covered == total and not unreadable and not orphans, "text": text,
    }


def legacy_confirmed_message(ids: list[str], language: str, run: str = "") -> str:
    """IMP-406: the confirmed items that were never line-checked, as one sentence (empty when there are none)."""
    if not ids:
        return ""
    shown = ", ".join(ids[:5]) + (f" (+{len(ids) - 5})" if len(ids) > 5 else "")
    if language == "es":
        return (f"{len(ids)} elemento(s) confirmado(s) sin control de líneas ({shown}): se confirmaron sin declarar Líneas; "
                "volvé a proponerlos con Líneas o verificalos con --verify")
    return (f"{len(ids)} confirmed element(s) without a line check ({shown}): they were confirmed without declared Lines; "
            "propose them again with Lines or check them with --verify")


def preserved_coverage(project_id: str, change_id: str) -> dict[str, Any]:
    """The border surfaces to preserve, and the UNCHANGED rows (extraction's or the answers') that name each one."""
    change = get_change(project_id, change_id)
    surfaces: list[str] = []
    for surface in change.get("border", []) or []:
        name = str(surface.get("name", "")).strip()
        if surface.get("zone") == "preservado" and name and name not in surfaces:
            surfaces.append(name)
    rows: dict[str, list[str]] = {name: [] for name in surfaces}
    folded = {_fold(name): name for name in surfaces}
    for row in load_change_ears(project_id, change_id):
        if str(row.get("delta", "")).strip().upper() != "UNCHANGED":
            continue
        for named in row.get("surfaces", []):
            name = folded.get(_fold(named))
            if name and row["id"] not in rows[name]:
                rows[name].append(row["id"])
    missing = [name for name in surfaces if not rows[name]]
    return {"surfaces": surfaces, "rows": rows, "missing": missing, "complete": not missing}


def extraction_fingerprint(base: Path, change_id: str) -> str:
    """Moves when something is confirmed, corrected or taken out; not when a proposal is only recorded."""
    inventory = load_inventory(base, change_id)
    if inventory is None:
        return ""
    items = load_proposals(base, change_id)["items"]
    confirmed = sorted(
        (str(i), str(item.get("treatment", "")), str(item.get("element_sha", "")), list(item.get("rows") or []))
        for i, item in items.items() if isinstance(item, dict) and item.get("status") == "confirmed"
    )
    sections = read_json(extraction_dir(base, change_id) / "sections.json", {})
    entries = sections.get("entries", []) if isinstance(sections, dict) else []
    payload = {"version": inventory.get("version", 1), "confirmed": confirmed, "sections": entries}
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()[:12]


def _in_workspace(base: Path, path: Any) -> str:
    """The path as the workspace cites it (`00_raw/pedido.md`), whatever the inventory recorded."""
    text = str(path or "")
    for root, target in ((base, Path(text)), (base.resolve(), Path(text).resolve())):
        try:
            return target.relative_to(root).as_posix()
        except ValueError:
            continue
    return text.replace("\\", "/")


def extraction_view(project_id: str, change_id: str) -> dict[str, Any]:
    """Everything the change brief needs from the extraction, read once (nothing here writes).

    `sections` holds only the confirmed section entries whose element is still in the inventory with the same text.
    """
    base = workspace_path(project_id)
    state = inventory_state(project_id, change_id)
    inventory = load_inventory(base, change_id) or {}
    elements = [{**e, "path": _in_workspace(base, e.get("path"))}
                for e in inventory.get("elements", [])] if state != "missing" else []
    items = load_proposals(base, change_id)["items"] if state != "missing" else {}
    by_id = {e["id"]: e for e in elements}
    rows: dict[str, list[dict[str, str]]] = {}
    sections: list[dict[str, Any]] = []
    if state != "missing":
        for row in load_change_ears(project_id, change_id):
            found = _EXT_SOURCE.match(str(row.get("source", "")))
            element = by_id.get(found.group(1)) if found else None
            item = items.get(found.group(1)) if found else None
            if element and isinstance(item, dict) and item.get("status") == "confirmed" \
                    and item.get("element_sha") == element.get("sha"):
                rows.setdefault(found.group(1), []).append(
                    {"id": row["id"], "statement": row["statement"], "delta": row["delta"]}
                )
        stored = read_json(extraction_dir(base, change_id) / "sections.json", {})
        for entry in stored.get("entries", []) if isinstance(stored, dict) else []:
            element = by_id.get(entry.get("element"))
            item = items.get(entry.get("element"))
            if element and isinstance(item, dict) and item.get("status") == "confirmed" \
                    and item.get("element_sha") == element.get("sha"):
                sections.append({**entry, "path": element["path"]})
    return {
        "state": state, "elements": elements, "items": items, "rows": rows, "sections": sections,
        "coverage": extraction_coverage(project_id, change_id),
        "preserved": preserved_coverage(project_id, change_id),
        "fingerprint": extraction_fingerprint(base, change_id),
    }
