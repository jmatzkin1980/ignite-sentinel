"""IMP-268 (H17a′): re-scope and cascade, `/split --move`.

A confirmed series changes while people work: a unit goes from one release to
another, or out of the horizon into a sketch. `/split --move` does it as a governed
change of the partition, never as an edit:

* the unit (`C-NN`, `P-N` or a quote of the brief) leaves `--from` and goes to `--to`
  (a release, or `sketch:<name>`);
* the whole partition validation (IMP-266) must stay green, and the move is
  confirmed again by the BA and the technical team (`--ba`, `--tech`), as a
  confirmation; the client's confirmation gap reopens if it was closed;
* the series recompiles (IMP-267a): both briefs, the tombstones in the neighbours
  (REATRIBUIDO) and the index. The derivations of the touched releases are not
  regenerated: their mirror's drift shows them stale until the BA runs them again;
* every move is recorded, dated, with its reason and the finding that motivated it,
  in `02_requirements/series/scope_changes.md` and its JSON;
* "excluded is not resolved": moving a unit to a sketch closes none of its gaps;
* a round trip (A→B→A) of the same unit is the finding "cut criterion not written"
  [A42]: the move is refused and `GAP-SPLIT-CRITERION` opens, until the move names
  the written criterion that decides it (`--criterion Cn`).
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

from .release_split import PARTITION_FILE, ReleaseSplitError, _dicts, _s, open_split_gap, validate_partition
from .split_proposal import PROPOSAL_DIR, PROPOSAL_FILE, _norm, _summary

CHANGES_JSON = "scope_changes.json"
CHANGES_MD = "scope_changes.md"
CRITERION_GAP_ID = "GAP-SPLIT-CRITERION"
SKETCH_PREFIX = "sketch:"


def unit_key(unit: dict[str, Any]) -> str:
    item = _s(unit.get("item"))
    return item if item else f"{_s(unit.get('place'))}:{_norm(unit.get('quote', ''))}"


def unit_label(unit: dict[str, Any]) -> str:
    return _s(unit.get("item")) or f"§{_s(unit.get('place'))} \"{_s(unit.get('quote'))}\""


def _holder(payload: dict[str, Any], name: str) -> dict[str, Any] | None:
    if name.startswith(SKETCH_PREFIX):
        wanted = name[len(SKETCH_PREFIX):]
        return next((s for s in _dicts(payload.get("sketches")) if _s(s.get("name")) == wanted), None)
    return next((r for r in _dicts(payload.get("releases")) if _s(r.get("id")) == name), None)


def _matches(unit: dict[str, Any], spec: str) -> bool:
    item = _s(unit.get("item"))
    if item:
        return item == spec.strip()
    quote = _norm(unit.get("quote", ""))
    wanted = _norm(spec)
    return bool(quote and wanted) and (quote == wanted or wanted in quote)


def round_trip(history: list[dict[str, Any]], key: str, source: str, target: str) -> dict[str, Any] | None:
    """The earlier move of the same unit from `target` to `source`, if this move undoes it."""
    return next((c for c in reversed(history) if c.get("unit_key") == key
                 and c.get("from") == target and c.get("to") == source), None)


def plan_move(payload: dict[str, Any], spec: str, source: str, target: str) -> tuple[dict[str, Any], dict[str, Any]]:
    """(moved payload, the unit). Pure; raises when the unit or a holder is not there."""
    if source == target:
        raise ReleaseSplitError("--from and --to are the same holder")
    moved = copy.deepcopy(payload)
    src, dst = _holder(moved, source), _holder(moved, target)
    if src is None:
        raise ReleaseSplitError(f"--from {source!r} is not a release or a sketch (sketch:<name>) of the proposal")
    if dst is None:
        raise ReleaseSplitError(f"--to {target!r} is not a release or a sketch (sketch:<name>) of the proposal")
    units = _dicts(src.get("contains"))
    found = [u for u in units if _matches(u, spec)]
    if not found:
        raise ReleaseSplitError(f"{spec!r} is not a unit of {source}: name a C-NN, a P-N or a quote of one of its units")
    if len(found) > 1:
        raise ReleaseSplitError(f"{spec!r} matches {len(found)} units of {source}; quote more of the one to move")
    unit = found[0]
    src["contains"] = [u for u in units if u is not unit]
    dst["contains"] = [*_dicts(dst.get("contains")), unit]
    return moved, unit


def _render_changes(project_id: str, history: list[dict[str, Any]]) -> str:
    lines = [f"# Scope changes — {project_id}", "",
             "Every move of a unit between releases of the confirmed series, dated, with its reason (IMP-268).", "",
             "| Date | Unit | From | To | Reason | Finding | Criterion | Confirmed by |",
             "|---|---|---|---|---|---|---|---|"]
    for change in history:
        who = change.get("confirmed_by") or {}
        lines.append("| {date} | {unit} | {src} | {dst} | {reason} | {finding} | {criterion} | {who} |".format(
            date=change.get("date", ""), unit=str(change.get("unit", "")).replace("|", "/"), src=change.get("from", ""),
            dst=change.get("to", ""), reason=str(change.get("reason", "")).replace("|", "/"),
            finding=change.get("finding") or "→", criterion=change.get("criterion") or "→",
            who=f"BA {who.get('ba', '')}; technical team {who.get('technical_team', '')}"))
    return "\n".join(lines) + "\n"


def move_unit(project_id: str, spec: str, source: str, target: str, reason: str, ba: str, tech: str,
              finding: str = "", criterion: str = "", today: str | None = None) -> dict[str, Any]:
    """Move one unit of the confirmed series and confirm the new partition. Every refusal leaves nothing changed."""
    from .core.io import read_json, write_text
    from .core.paths import workspace_path
    from .core.time import utc_now
    from .discovery import parse_gap_rows
    from .gap_resolution import project_language
    from .release_split import confirm_partition
    from .split import brief_hash

    if not _s(reason):
        raise ReleaseSplitError("/split --move records why: --reason is required")
    if not _s(ba) or not _s(tech):
        raise ReleaseSplitError("/split --move changes the partition: --ba NAME and --tech NAME confirm it, as in --confirm")
    base = workspace_path(project_id)
    series = base.joinpath(*PROPOSAL_DIR)
    partition = read_json(series / PARTITION_FILE, None)
    if not isinstance(partition, dict) or partition.get("status") != "confirmed":
        raise ReleaseSplitError("/split --move needs a confirmed series; run /split --confirm first")
    stored = read_json(series / PROPOSAL_FILE, None)
    if not isinstance(stored, dict) or stored.get("proposal_sha256") != partition.get("proposal_sha256"):
        raise ReleaseSplitError("the stored proposal is not the confirmed one; confirm it before moving units")
    brief_path = base / "02_requirements" / "project-brief.md"
    if brief_hash(brief_path) != stored.get("brief_sha256"):
        raise ReleaseSplitError("the brief changed since the series was confirmed; run /split --propose again")
    payload = stored["proposal"]
    moved, unit = plan_move(payload, spec, source, target)
    history = read_json(series / CHANGES_JSON, None)
    history = list(history.get("changes", [])) if isinstance(history, dict) else []
    key = unit_key(unit)
    language = project_language(project_id)
    previous = round_trip(history, key, source, target)
    written = {_s(c.get("id")) for c in _dicts(payload.get("criteria"))}
    if previous is not None:
        dst = _holder(moved, target) or {}
        allowed = criterion in written and (target.startswith(SKETCH_PREFIX) or criterion in (dst.get("criteria") or []))
        if not allowed:
            open_split_gap(project_id, {
                "id": CRITERION_GAP_ID, "lens": "product", "severity": "medium", "status": "OPEN",
                "description": f"{unit_label(unit)} went {target} → {source} ({previous.get('date', '')}) and is asked back to {target}: "
                               "a cut criterion is not written [A42].",
                "question": f"Which cut criterion decides where {unit_label(unit)} lives? Write it in the proposal and name it with --criterion.",
                "evidence_mention": "02_requirements/series/scope_changes.md", "origin": "split", "resolution_note": "",
            }, language)
            raise ReleaseSplitError(
                f"round trip: {unit_label(unit)} already went {target} → {source}; a cut criterion is not written [A42]. "
                f"{CRITERION_GAP_ID} is open: name the written criterion that decides it with --criterion Cn "
                f"(written in the proposal{'' if target.startswith(SKETCH_PREFIX) else f' and used by {target}'})")
    gaps_path = base / "01_discovery" / "gaps.md"
    rows = parse_gap_rows(gaps_path.read_text(encoding="utf-8")) if gaps_path.is_file() else []
    open_gaps = {_s(g.get("id")).strip("`") for g in rows if _s(g.get("status")).upper() != "CLOSED"}
    result = validate_partition(brief_path.read_text(encoding="utf-8"), moved, open_gaps, partition.get("contracts_frozen") or {})
    if result["findings"]:
        reasons = "; ".join(f"[{f['code']}] {f['where']}: {f['reason']}" for f in result["findings"])
        raise ReleaseSplitError(f"the move leaves the partition red ({len(result['findings'])} finding(s)); nothing changed: {reasons}")
    briefs_before = {rid: _brief_digest(base, rid) for rid in partition.get("releases") or []}
    new_stored = {**stored, "proposal": moved,
                  "proposal_sha256": hashlib.sha256(json.dumps(moved, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest(),
                  "summary": _summary(moved)}
    write_text(series / PROPOSAL_FILE, json.dumps(new_stored, ensure_ascii=False, indent=2) + "\n")
    confirmed = confirm_partition(project_id, ba, tech)
    change = {"date": today or utc_now()[:10], "unit": unit_label(unit), "unit_key": key, "from": source, "to": target,
              "reason": _s(reason), "finding": _s(finding), "criterion": _s(criterion) if previous is not None else "",
              "confirmed_by": {"ba": _s(ba), "technical_team": _s(tech)}}
    history.append(change)
    write_text(series / CHANGES_JSON, json.dumps({"changes": history}, ensure_ascii=False, indent=2) + "\n")
    write_text(series / CHANGES_MD, _render_changes(project_id, history))
    touched = sorted(rid for rid in confirmed["releases"] if _brief_digest(base, rid) != briefs_before.get(rid))
    return {"status": "moved", "change": change, "releases_changed": touched,
            "stale_derivations": [rid for rid in touched if (base / "03_specs" / rid).is_dir() or (base / "04_backlog" / rid).is_dir()],
            "confirmed_by": confirmed["confirmed_by"], "series": confirmed["series"],
            "next": "run /specs, /backlog and /quality with --release for each release in stale_derivations"}


def _brief_digest(base: Path, rid: str) -> str:
    path = base / "02_requirements" / rid / "project-brief.md"
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else ""
