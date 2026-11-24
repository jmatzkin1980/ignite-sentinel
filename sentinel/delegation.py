"""IMP-412 (H27 inc 4): who confirmed on behalf of the BA.

The BA may delegate a confirmation (an extraction element, an answer to a question). Nothing else changes
in how it is confirmed; this module only records the trace so that it is listed to be reviewed: the
elements keep it in their own item (`confirmed_by`), the questions here, in `delegations.json`.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .core.io import read_json, write_json
from .core.paths import workspace_path


def delegations_path(base: Path, change_id: str) -> Path:
    return base / "01_discovery" / change_id / "delegations.json"


def is_delegated(confirmed_by: str) -> bool:
    """Whether the `Confirmado por` / `Confirmed by` text says it was delegated (`delegación`, `delegated`)."""
    from .extraction.inventory import _fold

    return "deleg" in _fold(str(confirmed_by or ""))


def load_gap_delegations(base: Path, change_id: str) -> dict[str, dict[str, Any]]:
    data = read_json(delegations_path(base, change_id), {}) or {}
    return dict(data.get("gaps") or {})


def record_gap_delegations(
    project_id: str, change_id: str, closed: list[dict], responses: dict, saved: str,
) -> list[str]:
    """Keep the trace of every closed question whose answer says it was confirmed by delegation; returns their ids."""
    found = {}
    for gap in closed:
        note = str((responses.get(gap["id"]) or {}).get("confirmed_by", "")).strip()
        if note and is_delegated(note):
            found[gap["id"]] = {"at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                                "note": note, "response": saved}
    if not found:
        return []
    base = workspace_path(project_id)
    path = delegations_path(base, change_id)
    gaps = load_gap_delegations(base, change_id)
    gaps.update(found)
    write_json(path, {"schema_version": 1, "change_id": change_id, "gaps": gaps})
    return list(found)


def delegated_summary(project_id: str, change_id: str) -> dict[str, Any]:
    """The elements and questions confirmed on behalf of the BA, still to review."""
    from .extraction.proposals import load_proposals

    base = workspace_path(project_id)
    items = load_proposals(base, change_id)["items"]
    elements = [
        element_id for element_id, item in items.items()
        if item.get("status") == "confirmed" and item.get("confirmed_by") == "delegated"
    ]
    gaps = list(load_gap_delegations(base, change_id))
    return {"elements": elements, "gaps": gaps, "total": len(elements) + len(gaps)}
