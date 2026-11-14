"""IMP-259: sufficiency of the brief v2 (`/self-review --sufficiency`).

A reader with a clean context (the skill fixes the protocol: only the brief and
the sources it cites, never the conversation) asks of each place, and of each
build item of §9, "what is missing to start tomorrow?". The agent returns a JSON
payload; the runtime validates it and never edits the brief:

    {"round": 1, "obstacles": [
      {"place": "3.2", "status": "missing", "would_resolve": "...", "question": "...?"},
      {"place": "C-01", "status": "ambiguous", "quote": "<verbatim from 9.1>", "question": "...?"},
      {"place": "2.2", "status": "contradictory", "quote": "...",
       "conflicts_with": {"place": "5.11", "quote": "..."}, "question": "...?"},
      {"place": "1.1", "status": "covered"}]}

- `place` is a section or subsection id of the brief, or a build item `C-NN` of §9.
- `missing`: the `would_resolve` text must not already be in the brief.
- `ambiguous` / `contradictory`: each quote must sit verbatim in its place.
- Every non-covered obstacle needs a `question`.

Accepted obstacles open gaps with `origin: sufficiency` (topic dedup, IMP-257);
rejected ones are counted with their reason. Each round is appended to
`01_discovery/sufficiency_log.md`; the brief is sufficient when a round reports
only "covered" and nothing was rejected.
"""
from __future__ import annotations

from .errors import InputError  # IMP-302: typed errors

import hashlib
import re
from pathlib import Path
from typing import Any

from .brief_model import lenses_for_v2_id, parse_brief

STATUSES = ("covered", "missing", "ambiguous", "contradictory")
SEVERITIES = ("critical", "high", "medium", "low")
LENS_NAMES = {"1": "business", "2": "business", "3": "product", "4": "design", "5": "technical", "6": "compliance"}
C_ITEM_RE = re.compile(r"^C-[0-9]{2,}$")


class SufficiencyError(InputError):
    pass


def _norm(text: str) -> str:
    return " ".join(str(text).split()).lower()


def _place_text(brief_text: str, place: str) -> str | None:
    model = parse_brief(brief_text)
    lines = brief_text.splitlines()
    if C_ITEM_RE.match(place):
        hit = [line for line in lines if f"`{place}`" in line]
        return "\n".join(hit) if hit else None
    spans = [s for key, s in model.sections.items() if key == place or key.startswith(place + ".")]
    if not spans:
        return None
    return "\n".join(lines[min(s.start for s in spans):max(s.end for s in spans)])


def _lens_for(place: str) -> str:
    target = "9.1" if C_ITEM_RE.match(place) else place
    lenses = lenses_for_v2_id(target) or lenses_for_v2_id(target.split(".")[0])
    return LENS_NAMES.get(lenses[0], "product") if lenses else "product"


def validate_obstacles(brief_text: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Accepted gaps, rejected obstacles (with reasons) and counts per status. Pure."""
    if parse_brief(brief_text).version != 2:
        raise SufficiencyError("Sufficiency reads a brief v2; compile one with /brief first.")
    obstacles = payload.get("obstacles")
    if not isinstance(obstacles, list) or not obstacles:
        raise SufficiencyError("The payload needs a non-empty `obstacles` list.")
    whole = _norm(brief_text)
    counts = {status: 0 for status in STATUSES}
    accepted: list[dict[str, str]] = []
    rejected: list[dict[str, str]] = []
    for index, item in enumerate(obstacles, start=1):
        if not isinstance(item, dict):
            rejected.append({"index": str(index), "reason": "not an object"})
            continue
        place = str(item.get("place", "")).strip()
        status = str(item.get("status", "")).strip().lower()

        def reject(reason: str) -> None:
            rejected.append({"index": str(index), "place": place, "status": status, "reason": reason})

        if status not in STATUSES:
            reject(f"status must be one of {', '.join(STATUSES)}")
            continue
        body = _place_text(brief_text, place) if place else None
        if body is None:
            reject("place is not a section, subsection or §9 item of the brief")
            continue
        if status == "covered":
            counts["covered"] += 1
            continue
        question = str(item.get("question", "")).strip()
        if not question.endswith("?"):
            reject("a non-covered obstacle needs a `question` that ends with '?'")
            continue
        if status == "missing":
            resolve = str(item.get("would_resolve", "")).strip()
            if not resolve:
                reject("`missing` needs the `would_resolve` text")
                continue
            if _norm(resolve) in whole:
                reject("the text that would resolve it is already in the brief")
                continue
            evidence = resolve
        else:
            quote = str(item.get("quote", "")).strip()
            if not quote or _norm(quote) not in _norm(body):
                reject("the quote is not verbatim in its place")
                continue
            evidence = quote
            if status == "contradictory":
                other = item.get("conflicts_with") or {}
                other_body = _place_text(brief_text, str(other.get("place", "")).strip()) if isinstance(other, dict) else None
                other_quote = str(other.get("quote", "")).strip() if isinstance(other, dict) else ""
                if other_body is None or not other_quote or _norm(other_quote) not in _norm(other_body):
                    reject("`contradictory` needs `conflicts_with` {place, quote} verbatim in that place")
                    continue
                evidence = f"{quote} ⟷ {other_quote} (§{other['place']})"
        severity = str(item.get("severity", "medium")).strip().lower()
        if severity not in SEVERITIES:
            reject(f"severity must be one of {', '.join(SEVERITIES)}")
            continue
        counts[status] += 1
        digest = hashlib.sha256(f"{place}|{status}|{_norm(evidence)}".encode("utf-8")).hexdigest()[:8].upper()
        accepted.append({
            "id": f"GAP-SUF-{digest}",
            "lens": _lens_for(place),
            "severity": severity,
            "status": "OPEN",
            "description": f"Sufficiency ({status}) at §{place}: {evidence[:200]}",
            "question": question,
            "evidence_mention": f"§{place}",
            "origin": "sufficiency",
            "resolution_note": "",
        })
    sufficient = not rejected and counts["covered"] > 0 and all(counts[s] == 0 for s in STATUSES if s != "covered")
    return {"accepted": accepted, "rejected": rejected, "counts": counts, "sufficient": sufficient}


def apply_sufficiency(project_id: str, source: Path) -> dict[str, Any]:
    from .agent_sweep import record_sweep
    from .core.io import append_text, write_text
    from .discovery import count_gaps, parse_gap_rows, readiness_stage_after_gap_change, render_gaps
    from .gaps import merge_gaps_by_topic
    from .workspace import read_state, update_state, workspace_path

    base = workspace_path(project_id)
    brief_path = base / "02_requirements" / "project-brief.md"
    if not brief_path.exists():
        raise SufficiencyError("Sufficiency needs a compiled brief: run /brief first.")
    from .core.io import read_json

    payload = read_json(source, None)
    if not isinstance(payload, dict):
        raise SufficiencyError("The sufficiency payload must be a JSON object.")
    result = validate_obstacles(brief_path.read_text(encoding="utf-8"), payload)
    gaps_path = base / "01_discovery" / "gaps.md"
    existing = [g for g in parse_gap_rows(gaps_path.read_text(encoding="utf-8")) if g.get("id") != "NONE"] if gaps_path.exists() else []
    merged = merge_gaps_by_topic(existing, result["accepted"])
    if gaps_path.exists() and (merged["added"] or merged["extended"]):
        state = read_state(project_id, {})
        language = state.get("project_language") if state.get("project_language") in {"es", "en"} else "en"
        req_id = existing[0].get("parent", "REQ-001").strip("`") if existing else "REQ-001"
        write_text(gaps_path, render_gaps(project_id, merged["gaps"], req_id, language))
        counts = count_gaps(merged["gaps"])
        update_state(project_id, gap_counts=counts, readiness_stage=readiness_stage_after_gap_change(project_id, counts))
    record_sweep(base, "sufficiency", payload, [g["id"] for g in merged["added"]])
    log = base / "01_discovery" / "sufficiency_log.md"
    previous = log.read_text(encoding="utf-8").count("\n## Round ") if log.exists() else 0
    round_number = int(payload.get("round") or previous + 1)
    if not log.exists():
        write_text(log, f"# Sufficiency log - {project_id}\n\nA clean-context reader asks of each place: what is missing to start tomorrow?\n")
    c = result["counts"]
    entry = [f"\n## Round {round_number}", "",
             f"- covered {c['covered']} · missing {c['missing']} · ambiguous {c['ambiguous']} · contradictory {c['contradictory']}",
             f"- gaps opened: {', '.join(g['id'] for g in merged['added']) or 'none'}",
             f"- extended (same topic): {', '.join(f'{k} → {v}' for k, v in merged['extended'].items()) or 'none'}",
             f"- rejected: {len(result['rejected'])}"]
    entry += [f"  - #{r['index']} §{r.get('place', '?')}: {r['reason']}" for r in result["rejected"]]
    entry.append(f"- verdict: {'SUFFICIENT' if result['sufficient'] else 'NOT YET'}")
    append_text(log, "\n".join(entry) + "\n")
    return {"project_id": project_id, "round": round_number, "counts": c, "sufficient": result["sufficient"],
            "gaps_opened": [g["id"] for g in merged["added"]], "extended": merged["extended"],
            "rejected": result["rejected"], "log": str(log.as_posix())}
