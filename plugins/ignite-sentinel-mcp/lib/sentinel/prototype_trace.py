"""IMP-275 (H17b): audit and technical support of a prototype screen, `/prototype --trace`.

The agent (skill `sentinel-prototype-trace`) walks **one screen per pass** in the
surface's browser and writes a JSON trace; the runtime validates it against the
inventory (IMP-274) and the brief v2, and stores it. Without a browser the pass is
declared `executed: false` ("not executed"), never invented.

    {"prototype": "F-01", "screen": "S2", "executed": true, "mode": "existing|proposed|mixed",
     "elements": [{"element": "S2-E06", "element_quote": "Continue", "level": "established",
                   "data": "...", "contract": "...", "rule": "...", "reads_value": "...",
                   "anchor": {"place": "3.2", "quote": "<verbatim in the brief>"},
                   "gap": "GAP-...", "basis": "...", "demo_source": {"place": "6.2", "quote": "..."}}],
     "states": [{"state": "ideal|empty|loading|error", "status": "shown|unreachable|not_built", "element": "S3-E06"}],
     "checks": [{"check": "create_edit_symmetry", "finding": "...", "fix_side": "prototype|brief|both|none"}],
     "questions": ["...?"]}

Rules: the `element_quote` is literal and the element exists in the inventory of that
screen (or is a JavaScript literal `JS-NN`); `established` cites the brief verbatim,
`inferred` names its basis, `unsupported` names an open gap, `demo` cites the source
that says it is not built (without it, it is `unsupported`); the four states are all
there; at most four questions per pass; and the agent writes **no figures**: a number
in the agent's prose is refused (ids excepted), the generator injects real values.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .prototype import INVENTORY_DIR, PrototypeError, load_inventory

TRACE_DIR = "trace"
TRACE_MD = "trace.md"
LEVELS = ("established", "inferred", "unsupported", "demo")
STATES = ("ideal", "empty", "loading", "error")
STATE_STATUS = ("shown", "unreachable", "not_built")
MODES = ("existing", "proposed", "mixed")
CHECKS = ("four_states", "create_edit_symmetry", "fallback_domain_value", "who_reads_value", "dynamic_text", "contract_not_mapping")
FIX_SIDES = ("prototype", "brief", "both", "none")
MAX_QUESTIONS = 4
FINDING_CODES = (
    "payload_shape", "unknown_screen", "bad_mode", "invented_element", "quote_mismatch", "bad_level",
    "established_without_anchor", "inferred_without_basis", "unsupported_without_gap", "demo_without_source",
    "states_incomplete", "bad_state", "unknown_check", "too_many_questions", "written_figure",
)
_PROSE_FIELDS = ("data", "contract", "rule", "reads_value", "basis")
# ids the agent may write: elements, literals, gaps, sources, build items, releases, contracts, places
_IDS = re.compile(r"\b(?:S\d+-E\d+|JS-\d+|GAP-[A-Z0-9-]+|F-\d+|C-\d+|P-\d+|r\d+(?:\.\d+)?|K\d+|ASM-[A-Z0-9-]+|DEC-[A-Z0-9-]+|"
                  r"US-\d+|AC-\d+|RU-\d+|REQ-\d+|SPEC-U-\d+|§?\d+\.\d+)\b")
_DIGIT = re.compile(r"\d")


def _s(value: Any) -> str:
    return str(value if value is not None else "").strip()


def _norm(text: Any) -> str:
    return " ".join(str(text).split()).lower()


def _written_figure(text: str) -> bool:
    return bool(_DIGIT.search(_IDS.sub("", text)))


def validate_trace(inventory: dict[str, Any], brief_text: str, payload: dict[str, Any],
                   open_gaps: set[str] | None = None) -> dict[str, Any]:
    """Findings for one screen trace; none means valid. Pure."""
    from .split_proposal import _Checker

    findings: list[dict[str, str]] = []

    def add(code: str, where: str, reason: str) -> None:
        findings.append({"code": code, "where": where, "reason": reason})

    if not isinstance(payload, dict):
        add("payload_shape", "trace", "the trace is a JSON object")
        return {"findings": findings, "valid": False, "summary": {}}
    proto = next((p for p in inventory.get("prototypes", []) if p.get("source") == _s(payload.get("prototype"))), None)
    screen = next((s for s in (proto or {}).get("screens", []) if s.get("id") == _s(payload.get("screen"))), None)
    if screen is None:
        add("unknown_screen", f"{payload.get('prototype')} {payload.get('screen')}",
            "one screen per pass: name a prototype (F-NN) and a screen id (S1…) of the inventory")
        return {"findings": findings, "valid": False, "summary": {}}
    if _s(payload.get("mode")) not in MODES:
        add("bad_mode", "mode", f"the feasibility mode is one of {', '.join(MODES)}")
    known = {e["id"]: e["text"] for e in screen.get("elements", [])}
    known.update({lit["id"]: lit["text"] for lit in proto.get("js_literals", [])})
    checker = _Checker(brief_text, set(open_gaps or ()))
    counts = {level: 0 for level in LEVELS}
    elements = payload.get("elements") if isinstance(payload.get("elements"), list) else []
    if not isinstance(payload.get("elements"), list):
        add("payload_shape", "elements", "`elements` is a list (it may be empty only when nothing is visible)")
    for index, item in enumerate(elements, start=1):
        if not isinstance(item, dict):
            add("payload_shape", f"elements[{index}]", "an element trace is an object")
            continue
        eid, where = _s(item.get("element")), f"elements[{index}] {_s(item.get('element'))}".strip()
        if eid not in known:
            add("invented_element", where, f"{eid or '?'} is not an element of {screen['id']} nor a JS literal of the inventory")
            continue
        if _norm(item.get("element_quote", "")) != _norm(known[eid]):
            add("quote_mismatch", where, f"element_quote must be the literal text of {eid}: {known[eid]!r}")
        level = _s(item.get("level"))
        if level not in LEVELS:
            add("bad_level", where, f"level is one of {', '.join(LEVELS)}")
            continue
        if level == "established" and not checker.anchored(item.get("anchor")):
            add("established_without_anchor", where, "an established element cites the brief verbatim ({place, quote})")
        if level == "inferred" and not _s(item.get("basis")):
            add("inferred_without_basis", where, "an inferred element names its basis")
        if level == "unsupported" and _s(item.get("gap")) not in checker.open_gaps:
            add("unsupported_without_gap", where, "an unsupported element names the open gap that would support it")
        if level == "demo" and not checker.anchored(item.get("demo_source")):
            add("demo_without_source", where, "a demo element cites the source that says it is not built; without it, it is unsupported")
        for field in _PROSE_FIELDS:
            if _written_figure(_s(item.get(field))):
                add("written_figure", f"{where} {field}", "no figures in the agent's prose: the generator injects real values (ids are fine)")
        counts[level] += 1
    states = {(_s(s.get("state")) if isinstance(s, dict) else ""): s for s in payload.get("states") or []}
    for state in STATES:
        row = states.get(state)
        if row is None:
            add("states_incomplete", f"states.{state}", f"the four states ({', '.join(STATES)}) are all declared, as shown, unreachable or not_built")
            continue
        if _s(row.get("status")) not in STATE_STATUS:
            add("bad_state", f"states.{state}", f"status is one of {', '.join(STATE_STATUS)}: unreachable is not not_built")
        if _s(row.get("element")) and _s(row.get("element")) not in known:
            add("invented_element", f"states.{state}", f"{row.get('element')} is not in the inventory")
    for index, check in enumerate(payload.get("checks") or [], start=1):
        if not isinstance(check, dict) or _s(check.get("check")) not in CHECKS or _s(check.get("fix_side")) not in FIX_SIDES:
            add("unknown_check", f"checks[{index}]", f"a check is one of {', '.join(CHECKS)} with fix_side {', '.join(FIX_SIDES)}")
        elif _written_figure(_s(check.get("finding"))):
            add("written_figure", f"checks[{index}]", "no figures in the agent's prose: the generator injects real values")
    questions = [q for q in payload.get("questions") or [] if _s(q)]
    if len(questions) > MAX_QUESTIONS:
        add("too_many_questions", "questions", f"questions go in batches of 3 or 4 per pass, not {len(questions)}")
    executed = bool(payload.get("executed"))
    if not executed:
        verdict = "not_executed"
    elif counts["unsupported"]:
        verdict = "has_gaps"
    else:
        verdict = "supported"
    summary = {"prototype": proto["source"], "screen": screen["id"], "title": screen.get("title", ""), "executed": executed,
               "mode": _s(payload.get("mode")), "verdict": verdict, "levels": counts,
               "elements_traced": sum(counts.values()), "elements_in_screen": len(screen.get("elements", [])),
               "states": {s: _s((states.get(s) or {}).get("status")) for s in STATES}, "questions": len(questions)}
    return {"findings": findings, "valid": not findings, "summary": summary}


def _render_trace_md(project_id: str, traces: list[dict[str, Any]], inventory: dict[str, Any]) -> str:
    out = [f"# Prototype trace — {project_id}", "",
           "Element → data → contract → rule, one screen per pass, verified against the prototype inventory. "
           "Values come from the inventory, never from the agent.", ""]
    for trace in traces:
        s, p = trace["summary"], trace["payload"]
        texts = {e["id"]: e["text"] for proto in inventory.get("prototypes", []) if proto["source"] == s["prototype"]
                 for scr in proto["screens"] for e in scr["elements"]}
        texts.update({lit["id"]: lit["text"] for proto in inventory.get("prototypes", []) if proto["source"] == s["prototype"]
                      for lit in proto.get("js_literals", [])})
        levels = ", ".join(f"{k} {v}" for k, v in s["levels"].items())
        out += [f"## {s['prototype']} {s['screen']} {s['title']}", "",
                f"- Verdict: **{s['verdict']}** · mode {s['mode']} · {'executed in a browser' if s['executed'] else 'not executed (no browser)'}",
                f"- Elements traced: {s['elements_traced']} of {s['elements_in_screen']} ({levels})",
                f"- States: " + ", ".join(f"{k} {v or '—'}" for k, v in s["states"].items()), "",
                "| Element | Text (from the inventory) | Level | Data | Contract | Rule | Support |", "|---|---|---|---|---|---|---|"]
        for item in p.get("elements") or []:
            support = ""
            if isinstance(item.get("anchor"), dict):
                support = f"§{item['anchor'].get('place')} \"{item['anchor'].get('quote')}\""
            elif _s(item.get("gap")):
                support = f"`{item['gap']}`"
            elif isinstance(item.get("demo_source"), dict):
                support = f"demo: §{item['demo_source'].get('place')}"
            elif _s(item.get("basis")):
                support = f"(inferred) {item['basis']}"
            cells = [item.get("element", ""), texts.get(item.get("element", ""), ""), item.get("level", ""),
                     _s(item.get("data")), _s(item.get("contract")), _s(item.get("rule")), support]
            out.append("| " + " | ".join(str(c).replace("|", "/") for c in cells) + " |")
        checks = [c for c in p.get("checks") or [] if isinstance(c, dict)]
        if checks:
            out += ["", "Checks:", ""] + [f"- {c.get('check')}: {c.get('finding')} (fix: {c.get('fix_side')})" for c in checks]
        questions = [q for q in p.get("questions") or [] if _s(q)]
        if questions:
            out += ["", "Questions:", ""] + [f"- {q}" for q in questions]
        out.append("")
    return "\n".join(out).rstrip() + "\n"


def apply_trace(project_id: str, source: Path) -> dict[str, Any]:
    """Validate one screen trace and store it; every finding is reported and nothing is stored on a finding."""
    from .core.io import read_json, write_text
    from .core.paths import workspace_path
    from .discovery import parse_gap_rows

    base = workspace_path(project_id)
    inventory = load_inventory(project_id)
    payload = read_json(Path(source), None)
    brief = base / "02_requirements" / "project-brief.md"
    if not brief.is_file():
        raise PrototypeError("/prototype --trace needs the compiled brief v2 to check the anchors")
    gaps_path = base / "01_discovery" / "gaps.md"
    rows = parse_gap_rows(gaps_path.read_text(encoding="utf-8")) if gaps_path.is_file() else []
    open_gaps = {_s(g.get("id")).strip("`") for g in rows if _s(g.get("status")).upper() != "CLOSED"}
    result = validate_trace(inventory, brief.read_text(encoding="utf-8"), payload, open_gaps)
    if result["findings"]:
        reasons = "; ".join(f"[{f['code']}] {f['where']}: {f['reason']}" for f in result["findings"])
        raise PrototypeError(f"the trace was refused ({len(result['findings'])} finding(s)); nothing was stored: {reasons}")
    summary = result["summary"]
    folder = base.joinpath(*INVENTORY_DIR, TRACE_DIR)
    target = folder / f"{summary['prototype']}-{summary['screen']}.json"
    write_text(target, json.dumps({"summary": summary, "payload": payload}, ensure_ascii=False, indent=2) + "\n")
    traces = [read_json(p, {}) for p in sorted(folder.glob("*.json"))]
    view = base.joinpath(*INVENTORY_DIR, TRACE_MD)
    write_text(view, _render_trace_md(project_id, [t for t in traces if t.get("summary")], inventory))
    return {"status": "traced", "path": target.as_posix(), "view": view.as_posix(), **summary}
