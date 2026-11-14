"""IMP-260b: semantic crosses of the brief v2 (`/self-review --crosses`).

IMP-260 runs the exit checks a rule can decide. The rest needs judgment: does
the scope match what the lenses describe, do the rules of §2 have their steps in
§3, does each screen of §4 have what §5 must provide? An agent reports each cross
against a rule of `templates/semantic_crosses.json`:

    {"crosses": [
      {"rule": "cross_b_business_product", "kind": "conflict",
       "a": {"place": "2.2", "quote": "<verbatim>"}, "b": {"place": "3.2", "quote": "<verbatim>"},
       "finding": "...", "question": "...?"},
      {"rule": "retention_has_job", "kind": "missing",
       "a": {"place": "5.4", "quote": "<verbatim>"}, "missing_in": "5.12",
       "finding": "...", "question": "...?"}]}

The runtime checks the rule exists and allows the kind, each quote sits verbatim
at its place, the places belong to the rule's sides (`from` for `a`, `to` for `b`
and `missing_in`), and each cross carries a finding and a question. Accepted
crosses open `GAP-XRV-*` gaps (`origin: cross-review`); the brief is never edited.
"""
from __future__ import annotations

from .errors import InputError  # IMP-302: typed errors

import hashlib
from pathlib import Path
from typing import Any

from .brief_model import lenses_for_v2_id, parse_brief
from .resources import read_package_json

LENS_NAMES = {"1": "business", "2": "business", "3": "product", "4": "design", "5": "technical", "6": "compliance"}


class CrossReviewError(InputError):
    pass


def rules() -> dict[str, dict[str, Any]]:
    return {rule["id"]: rule for rule in read_package_json("templates/semantic_crosses.json")["rules"]}


def _norm(text: str) -> str:
    return " ".join(str(text).split()).lower()


def _within(place: str, sides: list[str]) -> bool:
    return any(place == side or place.startswith(side + ".") or place.startswith(side + "/") for side in sides)


def _body(brief_text: str, place: str) -> str | None:
    model = parse_brief(brief_text)
    spans = [s for key, s in model.sections.items() if key == place or key.startswith(place + ".")]
    if not spans:
        return None
    lines = brief_text.splitlines()
    return "\n".join(lines[min(s.start for s in spans):max(s.end for s in spans)])


def validate_crosses(brief_text: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Accepted gaps, rejected crosses (with reasons) and counts per kind. Pure."""
    if parse_brief(brief_text).version != 2:
        raise CrossReviewError("Cross review reads a brief v2; compile one with /brief first.")
    crosses = payload.get("crosses")
    if not isinstance(crosses, list) or not crosses:
        raise CrossReviewError("The payload needs a non-empty `crosses` list.")
    catalog = rules()
    counts = {"conflict": 0, "missing": 0}
    accepted: list[dict[str, str]] = []
    rejected: list[dict[str, str]] = []
    for index, item in enumerate(crosses, start=1):
        if not isinstance(item, dict):
            rejected.append({"index": str(index), "reason": "not an object"})
            continue
        rule_id, kind = str(item.get("rule", "")).strip(), str(item.get("kind", "")).strip().lower()

        def reject(reason: str) -> None:
            rejected.append({"index": str(index), "rule": rule_id, "kind": kind, "reason": reason})

        rule = catalog.get(rule_id)
        if rule is None:
            reject("unknown rule; use an id of templates/semantic_crosses.json")
            continue
        if kind not in rule["kinds"]:
            reject(f"rule {rule_id} takes kind {' or '.join(rule['kinds'])}")
            continue
        a = item.get("a") if isinstance(item.get("a"), dict) else {}
        a_place, a_quote = str(a.get("place", "")).strip(), str(a.get("quote", "")).strip()
        if not _within(a_place, rule["from"]):
            reject(f"`a` must be in {', '.join(rule['from'])}")
            continue
        a_body = _body(brief_text, a_place)
        if a_body is None or not a_quote or _norm(a_quote) not in _norm(a_body):
            reject(f"the `a` quote is not verbatim at §{a_place}")
            continue
        if kind == "conflict":
            b = item.get("b") if isinstance(item.get("b"), dict) else {}
            b_place, b_quote = str(b.get("place", "")).strip(), str(b.get("quote", "")).strip()
            if not _within(b_place, rule["to"]):
                reject(f"`b` must be in {', '.join(rule['to'])}")
                continue
            b_body = _body(brief_text, b_place)
            if b_body is None or not b_quote or _norm(b_quote) not in _norm(b_body):
                reject(f"the `b` quote is not verbatim at §{b_place}")
                continue
            where, other = b_place, b_quote
        else:
            where = str(item.get("missing_in", "")).strip()
            if not _within(where, rule["to"]) or _body(brief_text, where) is None:
                reject(f"`missing_in` must be a place of the brief in {', '.join(rule['to'])}")
                continue
            other = ""
        finding, question = str(item.get("finding", "")).strip(), str(item.get("question", "")).strip()
        if not finding:
            reject("a cross needs its `finding`")
            continue
        if not question.endswith("?"):
            reject("a cross needs a `question` that ends with '?'")
            continue
        counts[kind] += 1
        digest = hashlib.sha256(f"{rule_id}|{a_place}|{_norm(a_quote)}|{where}|{_norm(other)}".encode("utf-8")).hexdigest()[:8].upper()
        lenses = lenses_for_v2_id(where) or lenses_for_v2_id(a_place)
        accepted.append({
            "id": f"GAP-XRV-{digest}",
            "lens": LENS_NAMES.get(lenses[0], "product") if lenses else "product",
            "severity": "high" if kind == "conflict" else "medium",
            "status": "OPEN",
            "description": f"Cross {rule_id} ({kind}) §{a_place} ↔ §{where}: {finding[:200]}",
            "question": question,
            "evidence_mention": a_quote[:160],
            "origin": "cross-review",
            "resolution_note": "",
        })
    return {"accepted": accepted, "rejected": rejected, "counts": counts}


def apply_cross_review(project_id: str, source: Path) -> dict[str, Any]:
    from .agent_sweep import record_sweep
    from .core.io import append_text, read_json, write_text
    from .discovery import count_gaps, parse_gap_rows, readiness_stage_after_gap_change, render_gaps
    from .gaps import merge_gaps_by_topic
    from .workspace import read_state, update_state, workspace_path

    base = workspace_path(project_id)
    brief_path = base / "02_requirements" / "project-brief.md"
    if not brief_path.exists():
        raise CrossReviewError("Cross review needs a compiled brief: run /brief first.")
    payload = read_json(source, None)
    if not isinstance(payload, dict):
        raise CrossReviewError("The cross review payload must be a JSON object.")
    result = validate_crosses(brief_path.read_text(encoding="utf-8"), payload)
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
    record_sweep(base, "cross-review", payload, [g["id"] for g in merged["added"]])
    log = base / "01_discovery" / "cross_review_log.md"
    if not log.exists():
        write_text(log, f"# Cross review log - {project_id}\n\nDo the lenses of the brief agree in substance?\n")
    c = result["counts"]
    entry = ["\n## Review", "", f"- conflicts {c['conflict']} · missing counterparts {c['missing']}",
             f"- gaps opened: {', '.join(g['id'] for g in merged['added']) or 'none'}",
             f"- rejected: {len(result['rejected'])}"]
    entry += [f"  - #{r['index']} {r.get('rule', '?')}: {r['reason']}" for r in result["rejected"]]
    append_text(log, "\n".join(entry) + "\n")
    return {"project_id": project_id, "counts": c, "gaps_opened": [g["id"] for g in merged["added"]],
            "extended": merged["extended"], "rejected": result["rejected"], "log": str(log.as_posix())}
