"""IMP-412 (H27 inc 4): two closed decisions that clash go back to the BA as a `GAP-CHQ-*` question.

The inc 3 index compares a new question against the closed ones; nothing compared two closed
decisions with each other. Two decisions of the same family that picked different options over
the same request element (or the same quoted line) cannot both govern: the BA is asked which does.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from .core.time import utc_now
from .workspace import workspace_path

from .prior_decisions import _family, _linkable

CONFLICT_PREFIX = "GAP-CHQ-"
CONFLICT_RETIRED_CLOSURE = "retired"  # IMP-414: a GAP-CHQ whose two decisions no longer clash


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


def superseded_path(base: Path, change_id: str) -> Path:
    return base / "01_discovery" / change_id / "superseded.json"


def _closure_of(row: dict) -> str:
    return str(row.get("closure_reason") or "").strip("`").strip().lower()


def _restore(row: dict | None, winner: str, chq: str, entries: dict[str, dict], language: str) -> bool:
    """The winner of a flipped GAP-CHQ was replaced by this same question before: it governs again, as it closed."""
    from .gaps import SUPERSEDED_CLOSURE

    if row is None or _closure_of(row) != SUPERSEDED_CLOSURE:
        return False
    entry = entries.get(winner)
    if entry is not None and entry.get("by") != chq:
        return False  # replaced by another question: this one does not bring it back
    if entry is not None:
        if str(entry.get("closure_reason") or ""):
            row["closure_reason"] = str(entry["closure_reason"])
        else:
            row.pop("closure_reason", None)
        row["resolution_note"] = str(entry.get("resolution_note") or "")
        entries.pop(winner, None)
    else:
        row["closure_reason"] = "answered"
        row["resolution_note"] = f"restituida por {chq}" if language == "es" else f"restored by {chq}"
    return True


def supersede_and_restore(project_id: str, change_id: str, closed: list[dict]) -> tuple[list[str], list[str]]:
    """`(replaced, restored)`: see `supersede_losing_decisions`; a winner an earlier answer replaced governs again."""
    from .change_requirements import _reconcile_groups, reconcile_change_ears
    from .changes import change_gaps_path, get_change
    from .compilers.change_brief import _answers
    from .core.io import read_json, write_json
    from .crosses.record import _save_change_gaps
    from .gaps import SUPERSEDED_CLOSURE, parse_gap_rows

    answered = [g for g in closed if str(g["id"]).startswith(CONFLICT_PREFIX) and str(g.get("option", "")).strip().upper() in ("A", "B")]
    if not answered:
        return [], []
    base = workspace_path(project_id)
    path = change_gaps_path(base, change_id)
    rows = [g for g in parse_gap_rows(path.read_text(encoding="utf-8-sig")) if g.get("id") != "NONE"]
    by_id = {str(g["id"]).strip(): g for g in rows}
    language = _language(project_id, change_id)
    stored = read_json(superseded_path(base, change_id), {})
    entries: dict[str, dict] = ({str(k): v for k, v in (stored.get("decisions") or {}).items() if isinstance(v, dict)}
                                if isinstance(stored, dict) else {})
    replaced: list[str] = []
    restored: list[str] = []
    for gap in answered:
        pair = [part.strip() for part in str((by_id.get(gap["id"]) or {}).get("evidence_mention", "")).split("//")]
        if len(pair) != 2:
            continue
        winner, loser = (pair[0], pair[1]) if str(gap["option"]).strip().upper() == "A" else (pair[1], pair[0])
        if _restore(by_id.get(winner), winner, gap["id"], entries, language):
            restored.append(winner)
        target = by_id.get(loser)
        if (target is None or str(target.get("status", "")).strip("`").strip().upper() != "CLOSED"
                or _closure_of(target) == SUPERSEDED_CLOSURE):
            continue
        entries[loser] = {"by": gap["id"], "winner": winner, "closure_reason": str(target.get("closure_reason") or ""),
                          "resolution_note": str(target.get("resolution_note") or ""), "at": utc_now()}
        target["closure_reason"] = SUPERSEDED_CLOSURE
        target["resolution_note"] = (f"reemplazada por {winner} según {gap['id']}" if language == "es"
                                     else f"replaced by {winner} per {gap['id']}")
        replaced.append(loser)
    if replaced or restored:
        _save_change_gaps(project_id, change_id, path, rows)
        write_json(superseded_path(base, change_id), {"schema_version": 1, "decisions": entries})
        if replaced:
            _reconcile_groups(project_id, change_id, [(loser, "", []) for loser in replaced], language)
        if restored:
            answers = _answers(base, get_change(project_id, change_id))
            back = [{"id": g, "answer": str(answers[g].get("answer", "")), "lens": str(by_id[g].get("lens", "")).strip()}
                    for g in restored if g in answers]
            if back:
                reconcile_change_ears(project_id, change_id, back, {g["id"]: answers[g["id"]] for g in back}, language)
    return replaced, restored


def supersede_losing_decisions(project_id: str, change_id: str, closed: list[dict]) -> list[str]:
    """A GAP-CHQ answered with Option A or B: the decision that does not govern closes as `superseded`.

    Its resolution note names the winner and the question; its EARS rows move to the superseded table. The brief, the
    export and the decisions view drop it as a fact (it is listed apart). The closure it had is kept in
    `superseded.json` so a flipped answer restores it. Returns the ids of the replaced decisions."""
    return supersede_and_restore(project_id, change_id, closed)[0]


def _language(project_id: str, change_id: str) -> str:
    from .changes import change_language, get_change

    return "es" if change_language(project_id, get_change(project_id, change_id)) == "es" else "en"


def detect_decision_conflicts(project_id: str, change_id: str) -> list[str]:
    """Open the question of every pair of closed decisions that clash; ids already registered stay as they are."""
    from .crosses.record import add_change_gaps, reopen_retired_gaps
    from .decision_memory import closed_decisions

    pairs = conflicting_pairs(closed_decisions(project_id, change_id))
    if not pairs:
        return []
    language = _language(project_id, change_id)
    opened = add_change_gaps(project_id, change_id, [conflict_gap(change_id, a, b, link, language) for a, b, link in pairs])
    # the same pair clashing again: its retired question comes back (the id is deterministic, so nothing else would open it)
    back = reopen_retired_gaps(project_id, change_id, [conflict_gap_id(a["id"], b["id"]) for a, b, _link in pairs])
    return [*opened, *back]


def open_conflict(project_id: str, change_id: str, a_id: str, b_id: str, link: str) -> str:
    """Open (or find) the question of one pair of decisions and return its id."""
    from .crosses.record import add_change_gaps
    from .decision_memory import closed_decisions

    by_id = {d["id"]: d for d in closed_decisions(project_id, change_id)}
    first, second = sorted([a_id, b_id])
    add_change_gaps(project_id, change_id,
                    [conflict_gap(change_id, by_id[first], by_id[second], link, _language(project_id, change_id))])
    return conflict_gap_id(a_id, b_id)


def refresh_decision_conflicts(project_id: str, change_id: str) -> dict[str, list[str]]:
    """Open the clashes there are and retire the open `GAP-CHQ` whose pair no longer is two closed decisions that differ."""
    from .changes import change_gaps_path
    from .crosses.record import _save_change_gaps
    from .decision_memory import closed_decisions
    from .gaps import parse_gap_rows

    path = change_gaps_path(workspace_path(project_id), change_id)
    retired: list[str] = []
    if path.exists():
        rows = [g for g in parse_gap_rows(path.read_text(encoding="utf-8-sig")) if g.get("id") != "NONE"]
        by_decision = {str(d["id"]): d for d in closed_decisions(project_id, change_id)}
        language = _language(project_id, change_id)
        for row in rows:
            gap_id = str(row.get("id", "")).strip()
            if not gap_id.startswith(CONFLICT_PREFIX) or str(row.get("status", "")).strip("`").strip().upper() == "CLOSED":
                continue
            pair = [part.strip() for part in str(row.get("evidence_mention", "")).split("//")]
            if len(pair) != 2:
                continue
            first, second = by_decision.get(pair[0]), by_decision.get(pair[1])
            if first is not None and second is not None and differ(first, second):
                continue
            row["status"] = "CLOSED"
            row["closure_reason"] = CONFLICT_RETIRED_CLOSURE
            row["resolution_note"] = (f"choque retirado: {pair[0]} y {pair[1]} ya no chocan" if language == "es"
                                      else f"conflict withdrawn: {pair[0]} and {pair[1]} no longer clash")
            retired.append(gap_id)
        if retired:
            _save_change_gaps(project_id, change_id, path, rows)
    return {"opened": detect_decision_conflicts(project_id, change_id), "retired": retired}
