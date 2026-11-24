"""IMP-402 task 3: what is flagged on an element (agent, open gap, harvest divergence).

A flagged element is confirmed one by one, never in bulk. Pure matching here; the
context (gap rows, harvest entries) is read by `change_flag_context`.
"""
from __future__ import annotations

import re

from ..changes import _squash, change_gaps_path
from ..core.paths import workspace_path
from ..gaps import parse_gap_rows
from ..harvest import load_harvest


# IMP-404: the gaps a cross-read opens quote the request: the element that holds the quote is flagged.
CROSS_FLAG_PREFIXES = {"GAP-DIS-": "divergencia", "GAP-SRD-": "sin_respaldo", "GAP-CON-": "contradiccion"}
MIN_CROSS_MENTION = 20
# the flags a re-check keeps: the agent's, the line coverage's and the verifier's (gap and harvest ones are recomputed)
PERSISTENT_FLAG_ORIGINS = ("agent", "coverage", "verify")


def _cross_kind(gap_id: str) -> str | None:
    return next((kind for prefix, kind in CROSS_FLAG_PREFIXES.items() if gap_id.startswith(prefix)), None)


def element_flags(
    element_id: str, element_text: str, quote: str, agent_flags: list[dict],
    open_gaps: list[dict], harvest_entries: list[dict],
) -> list[dict]:
    flags: list[dict] = [dict(flag) for flag in agent_flags]
    squashed_quote = _squash(quote or "")
    # `RN-1` is not inside `RN-1.2` (a dot followed by a word character continues the id)
    token = re.compile(r"(?<![\w-])" + re.escape(element_id) + r"(?![\w-])(?!\.\w)")
    flat_element = _squash(element_text or "")
    for gap in open_gaps:
        if str(gap.get("status", "OPEN")).strip().upper() == "CLOSED":
            continue
        description = str(gap.get("description", ""))
        gap_id = str(gap.get("id", ""))
        cross_kind = _cross_kind(gap_id)
        if token.search(description) or (squashed_quote and squashed_quote in _squash(description)):
            kind = cross_kind or ("divergencia" if gap_id.startswith(("GAP-HRV-", "GAP-VER-")) else "pregunta_abierta")
            flags.append({"origin": "gap", "kind": kind, "ref": gap_id, "note": ""})
        elif cross_kind:
            mention = str(gap.get("evidence_mention", ""))
            pieces = [_squash(piece) for piece in [*mention.split(" // "), mention]]
            if any(len(piece) >= MIN_CROSS_MENTION and piece in flat_element for piece in pieces):
                flags.append({"origin": "gap", "kind": cross_kind, "ref": gap_id, "note": ""})
    for entry in harvest_entries:
        if entry.get("kind") != "divergence":
            continue
        text = _squash(str(entry.get("text", "")))
        if not text:
            continue
        if (squashed_quote and squashed_quote in text) or (len(text) >= 20 and text in flat_element):
            flags.append({"origin": "harvest", "kind": "divergencia", "ref": f"harvest:{entry.get('line', '')}", "note": ""})
    return flags


def change_flag_context(project_id: str, change_id: str) -> tuple[list[dict], list[dict]]:
    base = workspace_path(project_id)
    path = change_gaps_path(base, change_id)
    gaps = parse_gap_rows(path.read_text(encoding="utf-8-sig")) if path.exists() else []
    gaps = [g for g in gaps if g.get("id") != "NONE"]
    entries = [e for e in load_harvest(base).get("entries", []) if isinstance(e, dict) and e.get("kind") == "divergence"]
    return gaps, entries


def refresh_flags(project_id: str, change_id: str, element_id: str, item: dict) -> list[dict]:
    """The flags with today's gaps and harvest, keeping the item's agent, coverage and verify flags."""
    from .inventory import load_inventory, element_text

    gaps, entries = change_flag_context(project_id, change_id)
    base = workspace_path(project_id)
    inventory = load_inventory(base, change_id) or {}
    element = next((e for e in inventory.get("elements", []) if e["id"] == element_id), None)
    text = (element_text(base, element) if element else None) or ""
    kept = [f for f in item.get("flags", []) or [] if f.get("origin") in PERSISTENT_FLAG_ORIGINS]
    return element_flags(element_id, text, str(item.get("quote", "")), kept, gaps, entries)
