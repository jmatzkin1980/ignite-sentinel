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
    ratified = []
    base = workspace_path(project_id)
    gaps = load_gap_delegations(base, change_id)
    for gap in closed:
        note = str((responses.get(gap["id"]) or {}).get("confirmed_by", "")).strip()
        if note and is_delegated(note):
            found[gap["id"]] = {"at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                                "note": note, "response": saved}
        elif gap["id"] in gaps and (responses.get(gap["id"]) or {}).get("answer"):
            ratified.append(gap["id"])  # the BA answered again without delegating: that is the ratification
    if not found and not ratified:
        return []
    for gap_id in ratified:
        gaps.pop(gap_id, None)
    gaps.update(found)
    write_json(delegations_path(base, change_id), {"schema_version": 1, "change_id": change_id, "gaps": gaps})
    return list(found)


def _closed_gap_ids(base: Path, change_id: str) -> set[str]:
    from .changes import change_gaps_path
    from .gaps import parse_gap_rows

    path = change_gaps_path(base, change_id)
    if not path.exists():
        return set()
    return {str(row.get("id", "")).strip() for row in parse_gap_rows(path.read_text(encoding="utf-8-sig"))
            if str(row.get("status", "")).strip("`").strip().upper() == "CLOSED"}


def current_gap_delegations(base: Path, change_id: str) -> dict[str, dict[str, Any]]:
    """The delegated questions that are still closed: a reopened one is not 'confirmed by delegation' any more."""
    closed = _closed_gap_ids(base, change_id)
    return {gap_id: entry for gap_id, entry in load_gap_delegations(base, change_id).items() if gap_id in closed}


def delegated_summary(project_id: str, change_id: str) -> dict[str, Any]:
    """The elements and questions confirmed on behalf of the BA, still to review."""
    from .extraction.proposals import load_proposals

    base = workspace_path(project_id)
    items = load_proposals(base, change_id)["items"]
    elements = [
        element_id for element_id, item in items.items()
        if item.get("status") == "confirmed" and item.get("confirmed_by") == "delegated"
    ]
    gaps = list(current_gap_delegations(base, change_id))
    return {"elements": elements, "gaps": gaps, "total": len(elements) + len(gaps)}
