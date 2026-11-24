"""IMP-412 (H27 inc 4): two closed decisions that clash go back to the BA as a `GAP-CHQ-*` question.

The inc 3 index compares a new question against the closed ones; nothing compared two closed
decisions with each other. Two decisions of the same family that picked different options over
the same request element (or the same quoted line) cannot both govern: the BA is asked which does.
"""
from __future__ import annotations

import hashlib

from .workspace import workspace_path

from .prior_decisions import _family, _linkable

CONFLICT_PREFIX = "GAP-CHQ-"


def shared_link(a: dict, b: dict) -> str:
    """What two decisions have in common: a linkable request element, else a cited source line ('' if none)."""
    mine = [e for e in a.get("elements") or [] if _linkable(e)]
    theirs = {e for e in b.get("elements") or [] if _linkable(e)}
    for element in mine:
        if element in theirs:
            return element
    lines = {(str(c.get("source_id", "")), c.get("line")) for c in b.get("citations") or []
             if c.get("source_id") and c.get("line")}
    for cite in a.get("citations") or []:
        key = (str(cite.get("source_id", "")), cite.get("line"))
        if key[0] and key[1] and key in lines:
            return f"{key[0]}:{key[1]}"
    return ""


def differ(a: dict, b: dict) -> bool:
    """Same family (a divergence's (B) is not a contradiction's (B)), both with an option, and not the same one."""
    ids = (str(a["id"]), str(b["id"]))
    if any(i.startswith(CONFLICT_PREFIX) for i in ids) or _family(ids[0]) != _family(ids[1]):
        return False
    if _family(ids[0]) == "GAP-CON":
        return False  # IMP-412 (M1): a contradiction's (A)/(B) point at its own two lines; the letters mean nothing across questions
    first, second = str(a.get("option", "")).strip(), str(b.get("option", "")).strip()
    return bool(first and second and first != second)


def conflicting_pairs(decisions: list[dict]) -> list[tuple[dict, dict, str]]:
    ordered = sorted(decisions, key=lambda d: str(d["id"]))
    found: list[tuple[dict, dict, str]] = []
    for index, a in enumerate(ordered):
        for b in ordered[index + 1:]:
            if differ(a, b):
                link = shared_link(a, b)
                if link:
                    found.append((a, b, link))
    return found


def clash_pairs(cited: list[dict], any_flag: bool = False) -> list[tuple[dict, dict, str]]:
    """The pairs among the decisions a proposal cites that clash; the block is the link, so none is demanded.

    With the BA's `choque` mark and no pair that differs by the rule, the first two cited are the pair."""
    ordered = sorted(cited, key=lambda d: str(d["id"]))
    found = [(a, b, shared_link(a, b)) for index, a in enumerate(ordered) for b in ordered[index + 1:] if differ(a, b)]
    if not found and any_flag and len(ordered) >= 2:
        found = [(ordered[0], ordered[1], shared_link(ordered[0], ordered[1]))]
    return found


def conflict_gap_id(a_id: str, b_id: str) -> str:
    digest = hashlib.sha256("|".join(sorted([a_id, b_id])).encode()).hexdigest()[:8].upper()
    return f"{CONFLICT_PREFIX}{digest}"


def conflict_gap(change_id: str, a: dict, b: dict, link: str, language: str) -> dict:
    a_id, b_id = str(a["id"]), str(b["id"])
    a_text, b_text = str(a.get("answer", ""))[:160], str(b.get("answer", ""))[:160]
    if language == "es":
        description = f"Estas dos decisiones chocan sobre {link}: {a_id} dice «{a_text}» y {b_id} dice «{b_text}»."
        question = f"¿Cuál rige? Opciones: (A) rige lo que decidió {a_id}; (B) rige lo que decidió {b_id}."
    else:
        description = f"These two decisions clash on {link}: {a_id} says “{a_text}” and {b_id} says “{b_text}”."
        question = f"Which one governs? Options: (A) what {a_id} decided governs; (B) what {b_id} decided governs."
    return {
        "id": conflict_gap_id(a_id, b_id), "lens": a.get("lens") or "product", "severity": "high", "status": "OPEN",
        "description": description, "question": question, "evidence_mention": f"{a_id} // {b_id}",
        "origin": "contradiction", "resolution_note": "",
    }


def supersede_losing_decisions(project_id: str, change_id: str, closed: list[dict]) -> list[str]:
    """A GAP-CHQ answered with Option A or B: the decision that does not govern closes as `superseded`.

    Its resolution note names the winner and the question; its EARS rows move to the superseded table. The brief, the
    export and the decisions view drop it as a fact (it is listed apart). Returns the ids of the replaced decisions."""
    from .change_requirements import _reconcile_groups
    from .changes import change_gaps_path
    from .crosses.record import _save_change_gaps
    from .gaps import SUPERSEDED_CLOSURE, parse_gap_rows

    answered = [g for g in closed if str(g["id"]).startswith(CONFLICT_PREFIX) and str(g.get("option", "")).strip().upper() in ("A", "B")]
    if not answered:
        return []
    path = change_gaps_path(workspace_path(project_id), change_id)
    rows = [g for g in parse_gap_rows(path.read_text(encoding="utf-8-sig")) if g.get("id") != "NONE"]
    by_id = {str(g["id"]).strip(): g for g in rows}
    language = _language(project_id, change_id)
    replaced: list[str] = []
    for gap in answered:
        pair = [part.strip() for part in str((by_id.get(gap["id"]) or {}).get("evidence_mention", "")).split("//")]
        if len(pair) != 2:
            continue
        winner, loser = (pair[0], pair[1]) if str(gap["option"]).strip().upper() == "A" else (pair[1], pair[0])
        target = by_id.get(loser)
        if (target is None or str(target.get("status", "")).strip("`").strip().upper() != "CLOSED"
                or str(target.get("closure_reason") or "").strip("`").strip().lower() == SUPERSEDED_CLOSURE):
            continue
        target["closure_reason"] = SUPERSEDED_CLOSURE
        target["resolution_note"] = (f"reemplazada por {winner} según {gap['id']}" if language == "es"
                                     else f"replaced by {winner} per {gap['id']}")
        replaced.append(loser)
    if replaced:
        _save_change_gaps(project_id, change_id, path, rows)
        _reconcile_groups(project_id, change_id, [(loser, "", []) for loser in replaced], language)
    return replaced


def _language(project_id: str, change_id: str) -> str:
    from .changes import change_language, get_change

    return "es" if change_language(project_id, get_change(project_id, change_id)) == "es" else "en"


def detect_decision_conflicts(project_id: str, change_id: str) -> list[str]:
    """Open the question of every pair of closed decisions that clash; ids already registered stay as they are."""
    from .crosses.record import add_change_gaps
    from .decision_memory import closed_decisions

    pairs = conflicting_pairs(closed_decisions(project_id, change_id))
    if not pairs:
        return []
    language = _language(project_id, change_id)
    return add_change_gaps(project_id, change_id, [conflict_gap(change_id, a, b, link, language) for a, b, link in pairs])


def open_conflict(project_id: str, change_id: str, a_id: str, b_id: str, link: str) -> str:
    """Open (or find) the question of one pair of decisions and return its id."""
    from .crosses.record import add_change_gaps
    from .decision_memory import closed_decisions

    by_id = {d["id"]: d for d in closed_decisions(project_id, change_id)}
    first, second = sorted([a_id, b_id])
    add_change_gaps(project_id, change_id,
                    [conflict_gap(change_id, by_id[first], by_id[second], link, _language(project_id, change_id))])
    return conflict_gap_id(a_id, b_id)
