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

from .gaps import parse_gap_rows
from .core.markdown import table_cell
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
            date=change.get("date", ""), unit=table_cell(change.get("unit", "")), src=change.get("from", ""),
            dst=change.get("to", ""), reason=table_cell(change.get("reason", "")),
            finding=change.get("finding") or "→", criterion=change.get("criterion") or "→",
            who=f"BA {who.get('ba', '')}; technical team {who.get('technical_team', '')}"))
    return "\n".join(lines) + "\n"


def move_unit(project_id: str, spec: str, source: str, target: str, reason: str, ba: str, tech: str,
              finding: str = "", criterion: str = "", today: str | None = None,
              change_id: str | None = None) -> dict[str, Any]:
    """Move one unit of the confirmed series and confirm the new partition. Every refusal leaves nothing changed.

    With `change_id` (IMP-429) the series is the change's (`02_requirements/CHG-nnn/series/`): the same move, the same
    partition validation, a closed release is not touched, and the derivations of the releases it touches go stale."""
    from .core.io import read_json, write_text
    from .core.paths import workspace_path
    from .core.time import utc_now
    from .core.text import project_language
    from .release_split import confirm_partition
    from .split import brief_hash

    if not _s(reason):
        raise ReleaseSplitError("/split --move records why: --reason is required")
    if not _s(ba) or not _s(tech):
        raise ReleaseSplitError("/split --move changes the partition: --ba NAME and --tech NAME confirm it, as in --confirm")
    base = workspace_path(project_id)
    from .series_scope import series_dir, series_scope

    series = series_dir(base, change_id) if change_id else base.joinpath(*PROPOSAL_DIR)
    scope = series_scope(project_id, change_id) if change_id else None
    partition = read_json(series / PARTITION_FILE, None)
    if not isinstance(partition, dict) or partition.get("status") != "confirmed":
        raise ReleaseSplitError("/split --move needs a confirmed series; run /split --confirm first", gate=True)
    stored = read_json(series / PROPOSAL_FILE, None)
    if not isinstance(stored, dict) or stored.get("proposal_sha256") != partition.get("proposal_sha256"):
        raise ReleaseSplitError("the stored proposal is not the confirmed one; confirm it before moving units", gate=True)
    brief_path = base / "02_requirements" / "project-brief.md"
    brief_text = scope.brief_text if scope else (brief_path.read_text(encoding="utf-8") if brief_path.is_file() else "")
    if (scope.brief_sha256 if scope else brief_hash(brief_path)) != stored.get("brief_sha256"):
        scope_flag = f" --change {change_id}" if change_id else ""
        raise ReleaseSplitError(f"the brief changed since the series was confirmed; run /split{scope_flag} --propose again", gate=True)
    if change_id:
        shut = [name for name in (source, target) if name in (partition.get("closed") or {})]
        if shut:
            names = ", ".join(shut)
            raise ReleaseSplitError(
                f"{names} está cerrada en la serie de {change_id}: lo entregado no se mueve" if scope.language == "es"
                else f"{names} is closed in the series of {change_id}: what was delivered does not move", gate=True)
    payload = stored["proposal"]
    moved, unit = plan_move(payload, spec, source, target)
    history = read_json(series / CHANGES_JSON, None)
    history = list(history.get("changes", [])) if isinstance(history, dict) else []
    key = unit_key(unit)
    language = scope.language if scope else project_language(project_id)
    previous = round_trip(history, key, source, target)
    written = {_s(c.get("id")) for c in _dicts(payload.get("criteria"))}
    if previous is not None:
        dst = _holder(moved, target) or {}
        allowed = criterion in written and (target.startswith(SKETCH_PREFIX) or criterion in (dst.get("criteria") or []))
        if not allowed:
            _open_criterion_gap(project_id, change_id, {
                "id": CRITERION_GAP_ID, "lens": "product", "severity": "medium", "status": "OPEN",
                "description": f"{unit_label(unit)} went {target} → {source} ({previous.get('date', '')}) and is asked back to {target}: "
                               "a cut criterion is not written [A42].",
                "question": f"Which cut criterion decides where {unit_label(unit)} lives? Write it in the proposal and name it with --criterion.",
                "evidence_mention": (f"02_requirements/{change_id}/series/scope_changes.md" if change_id
                                     else "02_requirements/series/scope_changes.md"),
                "origin": "split", "resolution_note": "",
            }, language)
            raise ReleaseSplitError(
                f"round trip: {unit_label(unit)} already went {target} → {source}; a cut criterion is not written [A42]. "
                f"{CRITERION_GAP_ID} is open: name the written criterion that decides it with --criterion Cn "
                f"(written in the proposal{'' if target.startswith(SKETCH_PREFIX) else f' and used by {target}'})")
    gaps_path = scope.gaps_path if scope else base / "01_discovery" / "gaps.md"
    rows = parse_gap_rows(gaps_path.read_text(encoding="utf-8")) if gaps_path.is_file() else []
    open_gaps = {_s(g.get("id")).strip("`") for g in rows if _s(g.get("status")).upper() != "CLOSED"}
    result = validate_partition(brief_text, moved, open_gaps, partition.get("contracts_frozen") or {})
    if result["findings"]:
        reasons = "; ".join(f"[{f['code']}] {f['where']}: {f['reason']}" for f in result["findings"])
        raise ReleaseSplitError(f"the move leaves the partition red ({len(result['findings'])} finding(s)); nothing changed: {reasons}")
    briefs_before = {rid: _brief_digest(base, rid, change_id) for rid in partition.get("releases") or []}
    new_stored = {**stored, "proposal": moved,
                  "proposal_sha256": hashlib.sha256(json.dumps(moved, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest(),
                  "summary": _summary(moved)}
    write_text(series / PROPOSAL_FILE, json.dumps(new_stored, ensure_ascii=False, indent=2) + "\n")
    confirmed = confirm_partition(project_id, ba, tech, change_id)
    change = {"date": today or utc_now()[:10], "unit": unit_label(unit), "unit_key": key, "from": source, "to": target,
              "reason": _s(reason), "finding": _s(finding), "criterion": _s(criterion) if previous is not None else "",
              "confirmed_by": {"ba": _s(ba), "technical_team": _s(tech)}}
    history.append(change)
    write_text(series / CHANGES_JSON, json.dumps({"changes": history}, ensure_ascii=False, indent=2) + "\n")
    write_text(series / CHANGES_MD, _render_changes(project_id, history))
    touched = sorted(rid for rid in confirmed["releases"] if _brief_digest(base, rid, change_id) != briefs_before.get(rid))
    if change_id:
        return _moved_in_change(project_id, change_id, change, touched, confirmed, source, target)
    return {"status": "moved", "change": change, "releases_changed": touched,
            "stale_derivations": [rid for rid in touched if (base / "03_specs" / rid).is_dir() or (base / "04_backlog" / rid).is_dir()],
            "confirmed_by": confirmed["confirmed_by"], "series": confirmed["series"],
            "next": "run /specs, /backlog and /quality with --release for each release in stale_derivations"}


def _open_criterion_gap(project_id: str, change_id: str | None, row: dict[str, str], language: str) -> None:
    """GAP-SPLIT-CRITERION of the project goes in gaps.md; the one of a change goes through the change's own sink, once."""
    if change_id is None:
        open_split_gap(project_id, row, language)
        return
    from .changes import change_gaps_path, merge_change_gaps, reopen_change_gap
    from .core.paths import workspace_path

    path = change_gaps_path(workspace_path(project_id), change_id)
    current = next((r for r in parse_gap_rows(path.read_text(encoding="utf-8")) if _s(r.get("id")).strip("`") == row["id"]),
                   None) if path.is_file() else None
    if current is not None and _s(current.get("status")).upper() != "CLOSED":
        return
    if current is not None:
        reopen_change_gap(project_id, change_id, row["id"])
        return
    merge_change_gaps(project_id, change_id, [row], [])


def _moved_in_change(project_id: str, change_id: str, change: dict[str, Any], touched: list[str],
                     confirmed: dict[str, Any], source: str, target: str) -> dict[str, Any]:
    """The result of a move inside a change's series: which derivations of `03_specs/CHG/rN/` and `04_backlog/CHG/rN/` are old now."""
    from .change_release import ChangeReleaseError, release_dir, release_units

    try:
        owned: dict[str, list[str]] | None = release_units(project_id, change_id)
    except ChangeReleaseError:
        owned = None  # a unit with two owners or none: every derived release has to be derived again
    stale: list[str] = []
    for rid in (source, target):
        if rid.startswith(SKETCH_PREFIX) or rid in stale:
            continue
        if not any(release_dir(project_id, change_id, rid, layer).is_dir() for layer in ("03_specs", "04_backlog")):
            continue
        derived = release_dir(project_id, change_id, rid, "03_specs") / "units"
        held = sorted(p.stem for p in derived.glob("SPEC-U-*.md")) if derived.is_dir() else []
        if owned is None or held != sorted(owned.get(rid, [])):
            stale.append(rid)
    flag = f"--change {change_id}"
    if _language(project_id, change_id) == "es":
        advice = f"/next {project_id} {flag}: rehace con /specs y /backlog {flag} --release las releases de stale_derivations"
    else:
        advice = f"/next {project_id} {flag}: derive again with /specs and /backlog {flag} --release the releases in stale_derivations"
    return {"status": "moved", "change": change, "releases_changed": touched, "stale_derivations": sorted(stale),
            "confirmed_by": confirmed["confirmed_by"], "series": confirmed["series"], "next": advice}


def _language(project_id: str, change_id: str) -> str:
    from .changes import change_language, get_change

    return change_language(project_id, get_change(project_id, change_id))


def _brief_digest(base: Path, rid: str, change_id: str | None = None) -> str:
    path = (base / "02_requirements" / change_id / rid if change_id else base / "02_requirements" / rid) / "project-brief.md"
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else ""
