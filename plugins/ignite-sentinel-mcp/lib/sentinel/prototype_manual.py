"""IMP-276 (H17b): the user manual of a prototype, `/prototype --manual`.

A `/compose`-like channel: the agent (skill `sentinel-prototype-manual`) writes the
prose of each screen and cites the inventory (IMP-274); the generator injects what
the screen actually says. The agent never types the interface's words or figures:
it writes `{{S2-E06}}` and the manual shows the button's literal text.

    {"prototype": "F-01",
     "screens": [{"screen": "S2", "purpose": "Sign in before filing a claim, using {{S2-E02}}.",
                  "steps": [{"text": "Type your email in {{S2-E03}} and press {{S2-E06}}."}],
                  "notes": ["If {{S2-E07}} appears, check the email and the password."]}]}

Rules: every placeholder is an element of that screen or a JavaScript literal of the
prototype; every paragraph (purpose, step, note) cites at least one; the prose has
no figures (values come through placeholders); one entry per screen. A new
submission replaces the screens it brings and keeps the others. The manual lists
every screen of the prototype in order: **a screen without manual is a visible
hole, not an omission.** The printable view is `/view --artifact prototype-manual`.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .prototype import INVENTORY_DIR, PrototypeError, load_inventory

MANUAL_DIR = "manual"
MANUAL_MD = "manual.md"
PLACEHOLDER = re.compile(r"\{\{\s*([A-Z0-9-]+)\s*\}\}")
_DIGIT = re.compile(r"\d")
FINDING_CODES = ("payload_shape", "unknown_prototype", "unknown_screen", "duplicate_screen", "unknown_element",
                 "paragraph_without_citation", "written_figure", "empty_screen")


def _s(value: Any) -> str:
    return str(value if value is not None else "").strip()


def _paragraphs(entry: dict[str, Any]) -> list[tuple[str, str]]:
    rows = [("purpose", _s(entry.get("purpose")))] if _s(entry.get("purpose")) else []
    rows += [(f"steps[{i}]", _s(step.get("text") if isinstance(step, dict) else step))
             for i, step in enumerate(entry.get("steps") or [], start=1)]
    rows += [(f"notes[{i}]", _s(note)) for i, note in enumerate(entry.get("notes") or [], start=1)]
    return rows


def validate_manual(inventory: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    """Findings for one manual submission; none means valid. Pure."""
    findings: list[dict[str, str]] = []

    def add(code: str, where: str, reason: str) -> None:
        findings.append({"code": code, "where": where, "reason": reason})

    if not isinstance(payload, dict) or not isinstance(payload.get("screens"), list) or not payload.get("screens"):
        add("payload_shape", "manual", "the manual is an object with a non-empty `screens` list")
        return {"findings": findings, "valid": False}
    proto = next((p for p in inventory.get("prototypes", []) if p.get("source") == _s(payload.get("prototype"))), None)
    if proto is None:
        add("unknown_prototype", "prototype", f"{payload.get('prototype')!r} is not an inventoried prototype (F-NN)")
        return {"findings": findings, "valid": False}
    screens = {s["id"]: s for s in proto.get("screens", [])}
    literals = {lit["id"] for lit in proto.get("js_literals", [])}
    seen: set[str] = set()
    for index, entry in enumerate(payload["screens"], start=1):
        sid = _s(entry.get("screen")) if isinstance(entry, dict) else ""
        where = f"screens[{index}] {sid}".strip()
        if sid not in screens:
            add("unknown_screen", where, f"{sid or '?'} is not a screen of {proto['source']}")
            continue
        if sid in seen:
            add("duplicate_screen", where, "one entry per screen")
        seen.add(sid)
        known = {e["id"] for e in screens[sid].get("elements", [])} | literals
        paragraphs = _paragraphs(entry)
        if not paragraphs:
            add("empty_screen", where, "a screen entry has a purpose, steps or notes")
        for field, text in paragraphs:
            ids = PLACEHOLDER.findall(text)
            if not ids:
                add("paragraph_without_citation", f"{where} {field}", "every paragraph cites at least one element as {{S1-E01}}")
            for eid in ids:
                if eid not in known:
                    add("unknown_element", f"{where} {field}", f"{eid} is not an element of {sid} nor a JS literal of the prototype")
            if _DIGIT.search(PLACEHOLDER.sub("", text)):
                add("written_figure", f"{where} {field}", "no figures in the prose: cite the element that holds the value")
    return {"findings": findings, "valid": not findings}


def render_manual(project_id: str, inventory: dict[str, Any], manuals: dict[str, dict[str, Any]]) -> str:
    """The printable manual: every screen of every prototype, in order; a missing screen is a visible hole."""
    out = [f"# Prototype user manual — {project_id}", "",
           "The prose is the agent's; the interface's words come from the prototype inventory, quoted as the screen shows them.", ""]
    holes = 0
    for proto in inventory.get("prototypes", []):
        texts = {e["id"]: e["text"] for s in proto["screens"] for e in s["elements"]}
        texts.update({lit["id"]: lit["text"] for lit in proto.get("js_literals", [])})
        entries = {_s(e.get("screen")): e for e in (manuals.get(proto["source"]) or {}).get("screens", [])}

        def fill(text: str) -> str:
            return PLACEHOLDER.sub(lambda m: f"**“{texts.get(m.group(1), m.group(1))}”**", text)

        out += [f"## {proto['source']} — `{proto['path']}`", ""]
        for screen in proto["screens"]:
            out += [f"### {screen['id']} {screen['title']}", ""]
            entry = entries.get(screen["id"])
            if entry is None:
                holes += 1
                out += ["> **Hole:** this screen has no manual yet. Write it with the `sentinel-prototype-manual` skill.", ""]
                continue
            if _s(entry.get("purpose")):
                out += [fill(_s(entry["purpose"])), ""]
            steps = [_s(s.get("text") if isinstance(s, dict) else s) for s in entry.get("steps") or []]
            out += [f"{i}. {fill(step)}" for i, step in enumerate(steps, start=1)]
            if steps:
                out.append("")
            for note in entry.get("notes") or []:
                out += [f"> {fill(_s(note))}", ""]
    out += ["---", "", f"Screens without manual: {holes}."]
    return "\n".join(out).rstrip() + "\n"


def apply_manual(project_id: str, source: Path) -> dict[str, Any]:
    """Validate a manual submission, merge it by screen and render the printable manual."""
    from .core.io import read_json, write_text
    from .core.paths import workspace_path

    inventory = load_inventory(project_id)
    payload = read_json(Path(source), None)
    result = validate_manual(inventory, payload)
    if result["findings"]:
        reasons = "; ".join(f"[{f['code']}] {f['where']}: {f['reason']}" for f in result["findings"])
        raise PrototypeError(f"the manual was refused ({len(result['findings'])} finding(s)); nothing was stored: {reasons}")
    base = workspace_path(project_id).joinpath(*INVENTORY_DIR)
    folder = base / MANUAL_DIR
    proto_id = _s(payload["prototype"])
    current = read_json(folder / f"{proto_id}.json", None)
    merged = {e["screen"]: e for e in (current or {}).get("screens", [])} if isinstance(current, dict) else {}
    merged.update({_s(e["screen"]): e for e in payload["screens"]})
    order = [s["id"] for p in inventory["prototypes"] if p["source"] == proto_id for s in p["screens"]]
    stored = {"prototype": proto_id, "screens": [merged[sid] for sid in order if sid in merged]}
    write_text(folder / f"{proto_id}.json", json.dumps(stored, ensure_ascii=False, indent=2) + "\n")
    manuals = {p.stem: read_json(p, {}) for p in sorted(folder.glob("*.json"))}
    write_text(base / MANUAL_MD, render_manual(project_id, inventory, manuals))
    written = len(stored["screens"])
    return {"status": "written", "prototype": proto_id, "screens_with_manual": written,
            "screens_without_manual": len(order) - written, "view": (base / MANUAL_MD).as_posix()}
