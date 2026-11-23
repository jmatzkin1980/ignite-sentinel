"""IMP-402 task 5: what the extraction covers of the change request, and what the border preserves.

Read-only: it counts the inventory against the proposals and the confirmed rows. Nothing here writes.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from ..change_requirements import load_change_ears
from ..changes import change_language, get_change
from ..core.io import read_json
from ..core.paths import workspace_path
from . import extraction_dir
from .inventory import KINDS, _fold, inventory_state, load_inventory
from .proposals import load_proposals

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
    for element in elements:
        kind = element.get("kind")
        if kind in by_kind:
            by_kind[kind]["total"] += 1
        item = items.get(element["id"])
        if not item or item.get("element_sha") != element.get("sha"):
            continue
        if item.get("status") == "confirmed":
            covered += 1
            if kind in by_kind:
                by_kind[kind]["covered"] += 1
        elif item.get("status") == "proposed":
            proposed += 1
            if item.get("flags"):
                flagged += 1
    stale = [
        element_id for element_id, item in items.items()
        if isinstance(item, dict) and (element_id not in by_id or item.get("element_sha") != by_id[element_id].get("sha"))
    ]
    total = len(elements)
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
        "proposed": proposed, "flagged": flagged, "stale_items": stale,
        "by_kind": {kind: c for kind, c in by_kind.items() if c["total"]},
        "complete": state in ("current", "empty") and covered == total, "text": text,
    }


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
