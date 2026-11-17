"""IMP-337 (337b/337c): a late change in prose, read by an agent, confirmed by the BA.

The runtime cannot tell whether a line of prose confirms or reverses what was
confirmed: "is part of the first version" and "is out of scope" share no
negation. Deciding that polarity without a reader would be inventing. So:

1. **337b — the agent proposes.** After reading the note and the governed state
   it writes an analysis JSON of change candidates and runs
   ``/sync PROJECT_ID --source NOTE --analysis FILE``::

       {"candidates": [{"kind": "reopen_gap" | "invalidate_assumption" | "contradiction",
                        "target": "GAP-... | ASM-... | F-NN",
                        "note_quote": "<verbatim from the note>",
                        "target_quote": "<verbatim from the target>",
                        "question": "<optional question for the BA>"}]}

   The runtime validates both quotes verbatim (the same whitespace- and
   case-insensitive match ``/annotate`` uses) and the target's state, and refuses
   the whole file — exit 3, listing every reason, nothing written — when one does
   not hold. Each valid candidate opens **one** blocking ``GAP-CHG-<hash>``
   (severity high, origin ``agent``) with both quotes anchored and the target
   named. Nothing else moves.
2. **337c — the BA decides** through the existing disposition channel,
   ``/gaps PROJECT_ID --id GAP-CHG-x --disposition accepted|rejected``.
   ``accepted`` applies the candidate with the functions that already exist
   (reopen the gap keeping its previous closure, or invalidate the assumption
   and reopen the gap it held), closes the ``GAP-CHG`` and runs the knowledge
   metabolism, which marks the brief/PRD stale. ``rejected`` (or ``irrelevant``)
   closes the ``GAP-CHG`` as a false alarm and moves nothing else.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .gaps import count_gaps, parse_gap_rows, readiness_stage_after_gap_change, render_gaps
from .core.markdown import table_cell
from .core.io import copy_file, read_json, write_json, write_text
from .errors import GateRefusal, InputError
from .workspace import read_state, update_state, workspace_path

KINDS = ("reopen_gap", "invalidate_assumption", "contradiction")
CHANGE_GAP_PREFIX = "GAP-CHG-"
CANDIDATES_FILE = "01_discovery/change_candidates.json"
ANALYSES_DIR = "01_discovery/change_analyses"
REOPENABLE_GAP_STATUSES = {"CLOSED", "PARTIALLY_CLOSED"}
LIVE_ASSUMPTION_STATUSES = {"ASSUMED", "VALIDATED"}
CHANNEL = "sync-analysis"


class ChangeAnalysisError(InputError):
    """An analysis file the runtime refuses (exit 3)."""


def _normalize(text: str) -> str:
    from .discovery.channels import _normalize_for_match  # the /annotate matcher

    return _normalize_for_match(text)


def load_change_analysis(path: Path) -> dict[str, Any]:
    if not path.exists() or path.is_dir():
        raise ChangeAnalysisError(f"--analysis file not found: {path}")
    try:
        data = read_json(path, {})
    except (json.JSONDecodeError, ValueError) as exc:
        raise ChangeAnalysisError(f"--analysis is not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ChangeAnalysisError("--analysis must be a JSON object with a 'candidates' array.")
    return data


# --- what each target says ------------------------------------------------------


def _gaps(base: Path) -> list[dict[str, str]]:

    path = base / "01_discovery" / "gaps.md"
    if not path.exists():
        return []
    return [gap for gap in parse_gap_rows(path.read_text(encoding="utf-8")) if gap.get("id") != "NONE"]


def _source_text(project_id: str, source_id: str) -> tuple[dict[str, Any] | None, str]:
    """A registered source's own words: its anchored statements and its stored files."""
    from .source_conflicts import load_ledger
    from .sources import load_source_manifest
    from .source_registry import find_row

    base = workspace_path(project_id)
    row = find_row(load_source_manifest(project_id), source_id)
    if row is None:
        return None, ""
    chunks = [str(s.get("quote", "")) for s in load_ledger(project_id)["statements"] if s.get("source_id") == source_id]
    for key in [*row.get("paths", []), *row.get("copies", [])]:
        for path in (base / key, Path(key)):
            if path.is_file() and path.suffix.lower() in {".md", ".txt", ".json", ".html", ".htm"}:
                chunks.append(path.read_text(encoding="utf-8", errors="ignore"))
                break
    return row, "\n".join(chunks)


def target_context(project_id: str, kind: str, target: str) -> tuple[dict[str, Any] | None, str, str]:
    """(target record, the text its quote must sit in, why it cannot be a target or '')."""
    base = workspace_path(project_id)
    if kind == "reopen_gap":
        if not target.startswith("GAP-"):
            return None, "", f"reopen_gap needs a GAP-* target, not {target!r}"
        gap = next((g for g in _gaps(base) if g["id"] == target), None)
        if gap is None:
            return None, "", f"{target} is not in 01_discovery/gaps.md"
        if str(gap.get("status", "")).upper() not in REOPENABLE_GAP_STATUSES:
            return gap, "", f"{target} is {gap.get('status')}; only a CLOSED or PARTIALLY_CLOSED gap can be reopened"
        from .interaction_digest import closed_gap_answers

        text = "\n".join([*closed_gap_answers(base).get(target, []), gap.get("evidence_mention", ""),
                          gap.get("resolution_note", "")])
        return gap, text, ""
    if kind == "invalidate_assumption":
        if not target.startswith("ASM-"):
            return None, "", f"invalidate_assumption needs an ASM-* target, not {target!r}"
        from .assumptions import load_assumptions

        row = next((r for r in load_assumptions(project_id) if r["id"].upper() == target), None)
        if row is None:
            return None, "", f"{target} is not in 01_discovery/assumptions.md"
        if str(row.get("status", "")).upper() not in LIVE_ASSUMPTION_STATUSES:
            return row, "", f"{target} is {row.get('status')}; only an ASSUMED or VALIDATED assumption can be invalidated"
        return row, f"{row.get('statement', '')}\n{row.get('justification', '')}", ""
    if kind == "contradiction":
        if not target.startswith("F-"):
            return None, "", f"contradiction needs an F-NN target (a registered source), not {target!r}"
        row, text = _source_text(project_id, target)
        if row is None:
            return None, "", f"{target} is not in the source registry"
        return row, text, ""
    return None, "", f"kind must be one of {', '.join(KINDS)}"


# --- 337b: validate, then open GAP-CHG ------------------------------------------


def change_gap_id(kind: str, target: str, note_quote: str) -> str:
    digest = hashlib.sha1(f"{kind}|{target}|{_normalize(note_quote)}".encode("utf-8")).hexdigest()[:6].upper()
    return f"{CHANGE_GAP_PREFIX}{digest}"


def validate_change_analysis(project_id: str, data: dict[str, Any], note_text: str) -> list[dict[str, Any]]:
    """Every candidate checked; raise once with every reason when any fails."""
    from .agent_sweep import SweepProtocolError, validate_sweep_extras
    from .source_conflicts import declares_unvalidated

    reasons: list[str] = []
    candidates = data.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        raise ChangeAnalysisError("--analysis must contain a non-empty 'candidates' array.")
    note_haystack = _normalize(note_text)
    if declares_unvalidated(note_text):
        reasons.append("the note declares itself not validated; it cannot change what was confirmed")
    try:
        validate_sweep_extras({k: v for k, v in data.items() if k != "candidates"}, note_haystack, _normalize)
    except SweepProtocolError as exc:
        reasons.append(str(exc))
    valid: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for index, raw in enumerate(candidates, start=1):
        where = f"candidate #{index}"
        if not isinstance(raw, dict):
            reasons.append(f"{where}: must be an object")
            continue
        kind = str(raw.get("kind", "")).strip().lower()
        target = str(raw.get("target", "")).strip().upper()
        where = f"candidate #{index} ({kind or '?'} {target or '?'})"
        note_quote = str(raw.get("note_quote", "")).strip()
        target_quote = str(raw.get("target_quote", "")).strip()
        if kind not in KINDS:
            reasons.append(f"{where}: kind must be one of {', '.join(KINDS)}")
            continue
        if (kind, target) in seen:
            reasons.append(f"{where}: the same target appears twice in this analysis")
            continue
        seen.add((kind, target))
        if not note_quote:
            reasons.append(f"{where}: note_quote (verbatim from the note) is required")
        elif _normalize(note_quote) not in note_haystack:
            reasons.append(f"{where}: note_quote is not found verbatim in the note; cite real text, never invent it")
        record, target_text, refusal = target_context(project_id, kind, target)
        if refusal:
            reasons.append(f"{where}: {refusal}")
            continue
        if not target_quote:
            reasons.append(f"{where}: target_quote (verbatim from {target}) is required")
        elif _normalize(target_quote) not in _normalize(target_text):
            reasons.append(f"{where}: target_quote is not found verbatim in {target}")
        if reasons:
            continue
        valid.append({
            "kind": kind,
            "target": target,
            "note_quote": note_quote,
            "target_quote": target_quote,
            "question": str(raw.get("question", "")).strip(),
            "lens": _lens_for(kind, record),
        })
    if reasons:
        raise ChangeAnalysisError(
            f"--analysis refused ({len(reasons)} reason(s)); nothing was written:\n- " + "\n- ".join(reasons),
            next_step="Fix every reason above (copy each quote exactly from the note and the target) and run /sync again.",
        )
    return valid


def _lens_for(kind: str, record: dict[str, Any] | None) -> str:
    from .lens_registry import known_lenses

    lens = str((record or {}).get("lens", "")).strip("` ").lower() if kind != "contradiction" else ""
    lens = "technical" if lens == "technology" else lens
    return lens if lens in known_lenses() else "business"


def _note_line(note_text: str, quote: str) -> int:
    wanted = _normalize(quote)
    for number, line in enumerate(note_text.splitlines(), start=1):
        if wanted in _normalize(line):
            return number
    return 0


def _cell(text: str) -> str:
    return table_cell(text).strip()


def _change_gap(candidate: dict[str, Any], change_id: str, source_id: str, note_line: int) -> dict[str, str]:
    kind, target = candidate["kind"], candidate["target"]
    effect = {
        "reopen_gap": f"accepting reopens {target}",
        "invalidate_assumption": f"accepting invalidates {target} and reopens the gap it holds",
        "contradiction": f"accepting records that the note contradicts {target}; set which governs with /sources --precedence",
    }[kind]
    question = candidate["question"] or f"Does the change in {change_id} replace what {target} says? ({effect}; reject it if it does not.)"
    line = f" line {note_line}" if note_line else ""
    return {
        "id": candidate["gap_id"],
        "lens": candidate["lens"],
        "severity": "high",
        "status": "OPEN",
        "description": _cell(
            f"Late change on {target} ({kind}): {change_id}{line}: \"{candidate['note_quote']}\"; "
            f"{target}: \"{candidate['target_quote']}\""
        ),
        "question": _cell(question),
        "evidence_mention": ", ".join(item for item in (change_id, source_id) if item),
        "origin": "agent",
        "resolution_note": _cell(
            f"change-candidate {kind} {target}: confirm with /gaps --id {candidate['gap_id']} "
            "--disposition accepted|rejected"
        ),
    }


def _write_gaps(project_id: str, gaps: list[dict[str, str]]) -> dict[str, int]:

    base = workspace_path(project_id)
    state = read_state(project_id, {})
    language = state.get("project_language") if state.get("project_language") in {"es", "en"} else "en"
    req_id = gaps[0].get("parent", "REQ-001").strip("`") if gaps else "REQ-001"
    write_text(base / "01_discovery" / "gaps.md", render_gaps(project_id, gaps, req_id, language))
    counts = count_gaps(gaps)
    update_state(project_id, gap_counts=counts, readiness_stage=readiness_stage_after_gap_change(project_id, counts))
    return counts


def load_change_candidates(base: Path) -> dict[str, dict[str, Any]]:
    data = read_json(base / CANDIDATES_FILE, {})
    return dict(data.get("candidates", {})) if isinstance(data, dict) else {}


def _save_change_candidates(base: Path, candidates: dict[str, dict[str, Any]]) -> None:
    write_json(base / CANDIDATES_FILE, {"version": 1, "candidates": dict(sorted(candidates.items()))}, root=base)


def apply_change_analysis(
    project_id: str,
    analysis_path: Path,
    data: dict[str, Any],
    candidates: list[dict[str, Any]],
    *,
    change_id: str,
    source_id: str,
    note_text: str,
) -> dict[str, Any]:
    """Open one blocking GAP-CHG per validated candidate. Nothing else moves."""
    from .agent_sweep import record_sweep

    base = workspace_path(project_id)
    gaps = _gaps(base)
    existing = {gap["id"] for gap in gaps}
    known = load_change_candidates(base)
    opened: list[str] = []
    skipped: list[str] = []
    for candidate in candidates:
        candidate["gap_id"] = change_gap_id(candidate["kind"], candidate["target"], candidate["note_quote"])
        if candidate["gap_id"] in existing:
            skipped.append(candidate["gap_id"])
            continue
        note_line = _note_line(note_text, candidate["note_quote"])
        gaps.append(_change_gap(candidate, change_id, source_id, note_line))
        existing.add(candidate["gap_id"])
        known[candidate["gap_id"]] = {
            "kind": candidate["kind"], "target": candidate["target"], "note_quote": candidate["note_quote"],
            "target_quote": candidate["target_quote"], "change_id": change_id, "source_id": source_id,
            "note_line": note_line, "state": "open",
        }
        opened.append(candidate["gap_id"])
    stored = None
    if opened:
        counts = _write_gaps(project_id, gaps)
        _save_change_candidates(base, known)
        update_state(project_id, health="DIRTY")
        folder = base / ANALYSES_DIR
        folder.mkdir(parents=True, exist_ok=True)
        stored = folder / f"{change_id}-{analysis_path.stem}.json"
        copy_file(analysis_path, stored)
    else:
        counts = None
    record_sweep(base, CHANNEL, data, opened)
    return {
        "analysis": str(stored.as_posix()) if stored else None,
        "opened": opened,
        "skipped_existing": skipped,
        "gap_counts": counts,
        "next": (f"Ask the BA to confirm each one: /gaps {project_id} --id GAP-CHG-x --disposition accepted|rejected"
                 if opened else ""),
    }


# --- 337c: the BA's disposition applies or dismisses ----------------------------


def apply_change_disposition(project_id: str, gap: dict[str, str], disposition: str, reason: str) -> dict[str, Any] | None:
    """Apply (accepted) or dismiss (rejected / irrelevant) a GAP-CHG. None for any other gap.

    Raises before anything is written when the GAP-CHG was already disposed or its
    target moved since the candidate was opened.
    """
    gap_id = gap["id"]
    if not gap_id.startswith(CHANGE_GAP_PREFIX):
        return None
    base = workspace_path(project_id)
    known = load_change_candidates(base)
    candidate = known.get(gap_id)
    if candidate is None:
        return None
    if str(gap.get("status", "")).upper() == "CLOSED" or candidate.get("state") != "open":
        raise InputError(f"{gap_id} was already disposed ({candidate.get('state')}); a change applies once.")
    kind, target = candidate["kind"], candidate["target"]
    applied: dict[str, Any] = {"kind": kind, "target": target, "reopened_gaps": [], "invalidated_assumptions": []}
    if disposition == "accepted":
        if kind != "contradiction":
            _, _, refusal = target_context(project_id, kind, target)
            if refusal:
                raise GateRefusal(f"{gap_id} cannot be applied: {refusal}. Reject it with --reason, or re-run the analysis.")
        if kind == "reopen_gap":
            applied["reopened_gaps"] = _reopen_gap(project_id, target, gap_id)
        metabolism = _metabolize(project_id, gap_id, {target} if kind == "invalidate_assumption" else set())
        applied["invalidated_assumptions"] = metabolism.get("invalidated_assumptions", [])
        applied["reopened_gaps"] += [g for g in metabolism.get("_reopened_gaps", []) if g not in applied["reopened_gaps"]]
        metabolism.pop("_reopened_gaps", None)
        applied["knowledge_metabolism"] = metabolism
        if kind == "contradiction":
            applied["next"] = f"Record which source governs: /sources {project_id} --precedence SCOPE --between {target},{candidate.get('source_id') or 'F-NN'}"
        note = f"accepted by the BA: {kind} {target} applied from {candidate.get('change_id')}"
        closure = "answered"
    else:
        note = f"{disposition} by the BA (false alarm): {reason.strip()}"
        closure = "dissolved"
    gaps = _gaps(base)
    for row in gaps:
        if row["id"] == gap_id:
            row.update(status="CLOSED", closure_reason=closure, resolution_note=_cell(note))
    applied["gap_counts"] = _write_gaps(project_id, gaps)
    candidate["state"] = disposition
    _save_change_candidates(base, known)
    return applied


def _reopen_gap(project_id: str, target: str, change_gap: str) -> list[str]:
    """Reopen with the existing false-premise path: the previous closure stays on record."""
    from .gap_resolution import apply_gap_responses

    base = workspace_path(project_id)
    result = apply_gap_responses(_gaps(base), {target: {"closure": "reopened_false_premise"}})
    gaps = result["gaps"]  # type: ignore[assignment]
    for row in gaps:  # type: ignore[union-attr]
        if row["id"] == target:
            row["resolution_note"] = _cell(f"{row.get('resolution_note', '')} (accepted late change {change_gap})")
    _write_gaps(project_id, gaps)  # type: ignore[arg-type]
    return [target]


def _metabolize(project_id: str, change_gap: str, invalidate: set[str]) -> dict[str, Any]:
    from .knowledge.metabolism import metabolize_knowledge
    from .memory import ContextBroker

    before = {g["id"]: g.get("status") for g in _gaps(workspace_path(project_id))}
    payload = metabolize_knowledge(project_id, change_gap, invalidated_assumption_ids=invalidate,
                                   broker=ContextBroker(project_id))
    after = {g["id"]: g.get("status") for g in _gaps(workspace_path(project_id))}
    payload["_reopened_gaps"] = sorted(g for g, status in after.items() if status == "OPEN" and before.get(g) != "OPEN")
    return payload
