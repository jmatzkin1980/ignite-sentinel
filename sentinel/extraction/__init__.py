"""IMP-402 (H26 inc 3): extraction of a change request, element by element, with coverage.

Everything lives under `02_requirements/CHG-NNN/extraction/` of the project workspace.
"""
from __future__ import annotations

from pathlib import Path


def extraction_dir(base: Path, change_id: str) -> Path:
    """The folder that holds a change's inventory, proposals, review and submitted sheets."""
    return base / "02_requirements" / change_id / "extraction"


def run_extract(
    project_id: str,
    change_id: str,
    proposals: str | None = None,
    confirm: str | None = None,
    confirm_item: str | None = None,
    reject_item: str | None = None,
    reason: str | None = None,
) -> dict:
    """The /extract command: inventory, proposals, confirmation or rejection of one change."""
    from ..changes import change_language, get_change
    from ..readiness_verdict import change_next_step
    from .confirm import confirm_item as _confirm_item
    from .confirm import confirm_proposals, reject_item as _reject_item
    from .coverage import KIND_LABELS, extraction_coverage
    from .inventory import build_inventory
    from .proposals import record_proposals

    change = get_change(project_id, change_id)  # an unknown change is a GateRefusal
    lang = "es" if change_language(project_id, change) == "es" else "en"
    es = lang == "es"
    if proposals:
        result = record_proposals(project_id, change_id, Path(proposals))
    elif confirm:
        result = confirm_proposals(project_id, change_id, confirm)
    elif confirm_item:
        result = _confirm_item(project_id, change_id, confirm_item)
    elif reject_item:
        result = _reject_item(project_id, change_id, reject_item, reason or "")
    else:
        result = build_inventory(project_id, change_id)
    coverage = extraction_coverage(project_id, change_id)
    action = result.get("action")
    if action == "inventory":
        by_kind = ", ".join(
            f"{KIND_LABELS[lang].get(kind, kind)} {count}" for kind, count in (result.get("by_kind") or {}).items()
        )
        sheet = result["worksheet_path"]
        message = (
            f"{change_id}: {result['total']} elementos inventariados ({by_kind}). Planilla: `{sheet}`" if es
            else f"{change_id}: {result['total']} elements inventoried ({by_kind}). Worksheet: `{sheet}`"
        )
    elif action == "proposals":
        n, r, f = len(result["recorded"]), len(result["rejected"]), len(result["flagged"])
        message = (
            f"{change_id}: {n} propuesta(s) registrada(s), {r} rechazada(s), {f} marcada(s)" if es
            else f"{change_id}: {n} proposal(s) recorded, {r} rejected, {f} flagged"
        )
    elif action == "confirm":
        n, h = len(result["confirmed"]), len(result["held"])
        message = (
            f"{change_id}: {n} confirmada(s), {h} retenida(s) por marca; cobertura {coverage['text']}" if es
            else f"{change_id}: {n} confirmed, {h} held by flag; coverage {coverage['text']}"
        )
    else:
        message = f"{change_id}: {reject_item} volvió a pendiente" if es else f"{change_id}: {reject_item} back to pending"
    result["coverage"] = coverage
    result["next_step"] = change_next_step(project_id, change_id)
    result["message"] = message
    return result
