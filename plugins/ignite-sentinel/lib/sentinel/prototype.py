"""IMP-274 (H17b): extraction of HTML prototypes, `/prototype --inventory`.

An HTML prototype is ingested like any source (F-NN, secrets redacted by IMP-285,
injection shielded by IMP-286) and its copy lives in `00_raw/`. Read as plain text,
it is one blob: screens, controls and the copy that lives in JavaScript literals
are mixed with markup and code.

This module turns that copy into an **inventory per screen**, deterministic and
stdlib only:

* **screens:** an element with `data-screen` is a screen; otherwise each `<section>`
  with an `id`; otherwise the whole page is one screen;
* **elements:** headings, labels, buttons, links, fields (placeholder, aria-label,
  value of a submit), options, table columns, images with alt text, messages
  (role alert or status, or a class naming an error, alert, message, toast, empty
  or status) and paragraphs or list items, each with its literal text, its line,
  and whether it starts hidden (a state another action reveals);
* **JavaScript literals:** the strings in `<script>` that read as user copy (state
  texts, error messages, options), with their line.

Each element gets a stable id (`S1-E01`) and each literal its own (`JS-01`): the
audit (IMP-275) and the manual (IMP-276) cite them, and an element that is not in
the inventory does not exist. The inventory is written to
`02_requirements/prototype/inventory.json` and `inventory.md`
(`/view --artifact prototype`).
"""
from __future__ import annotations

import json
import re
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

INVENTORY_DIR = ("02_requirements", "prototype")
INVENTORY_JSON = "inventory.json"
INVENTORY_MD = "inventory.md"
HTML_SUFFIXES = (".html", ".htm")
_VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}
_TEXT_KINDS = {"h1": "heading", "h2": "heading", "h3": "heading", "h4": "heading", "h5": "heading", "h6": "heading",
               "label": "label", "button": "button", "a": "link", "th": "column", "option": "option",
               "p": "text", "li": "text", "legend": "label", "caption": "heading", "summary": "button"}
_MESSAGE_CLASS = re.compile(r"\b(error|alert|message|toast|empty|status|warning|notice|banner)\b", re.I)
_HIDDEN_STYLE = re.compile(r"display\s*:\s*none|visibility\s*:\s*hidden", re.I)
_STRING = re.compile(r"\"((?:[^\"\\\n]|\\.){3,200})\"|'((?:[^'\\\n]|\\.){3,200})'|`([^`]{3,200})`")
_CODE_LIKE = re.compile(r"[{}<>;=]|=>|\$\{|^\s*[#.\[]|^https?://|^[\w./-]+$")


class PrototypeError(RuntimeError):
    pass


def _ui_copy(text: str) -> bool:
    """A JavaScript string that reads as text a user sees, not code."""
    text = text.strip()
    if re.fullmatch(r"[A-ZÁÉÍÓÚÑ][a-záéíóúñ]{3,}", text):
        return True  # a single capitalised word ("Submitted") is a state label; ALLCAPS or camelCase are code
    if len(text) < 3 or not re.search(r"[A-Za-zÁÉÍÓÚáéíóúñÑ]", text) or _CODE_LIKE.search(text):
        return False
    return " " in text or text[-1:] in ".!?:"


class _Inventory(HTMLParser):
    def __init__(self, data_screens: bool) -> None:
        super().__init__(convert_charrefs=True)
        self.screens: list[dict[str, Any]] = []
        self.current: dict[str, Any] | None = None
        self.stack: list[dict[str, Any]] = []
        self.capture: list[dict[str, Any]] = []
        self.scripts: list[tuple[int, str]] = []
        self.in_script = False
        self.script_line = 0
        self.data_screens = data_screens  # data-screen marks screens; otherwise <section id=...>

    # -- screens -----------------------------------------------------------------------
    def _screen(self, key: str, line: int) -> dict[str, Any]:
        screen = {"id": f"S{len(self.screens) + 1}", "key": key, "title": "", "line": line, "elements": []}
        self.screens.append(screen)
        return screen

    def _active_screen(self) -> dict[str, Any]:
        if self.current is None:
            self.current = self._screen("page", self.getpos()[0])
        return self.current

    def _add(self, kind: str, text: str, hidden: bool) -> None:
        text = " ".join(text.split())
        if not text:
            return
        screen = self._active_screen()
        screen["elements"].append({"id": f"{screen['id']}-E{len(screen['elements']) + 1:02d}", "kind": kind,
                                   "text": text, "line": self.getpos()[0], "hidden": hidden})
        if kind == "heading" and not screen["title"]:
            screen["title"] = text

    def _hidden(self, attrs: dict[str, str]) -> bool:
        own = "hidden" in attrs or bool(_HIDDEN_STYLE.search(attrs.get("style", ""))) \
            or "hidden" in attrs.get("class", "").split() or attrs.get("aria-hidden") == "true"
        return own or any(frame["hidden"] for frame in self.stack)

    # -- parser hooks ------------------------------------------------------------------
    def handle_starttag(self, tag: str, attrs_list: list[tuple[str, str | None]]) -> None:
        attrs = {k: (v or "") for k, v in attrs_list}
        if tag == "script":
            self.in_script, self.script_line = True, self.getpos()[0]
            return
        if tag == "style":
            self.in_script = True
            self.script_line = -1
            return
        opens_screen = ("data-screen" in attrs) if self.data_screens else (tag == "section" and bool(attrs.get("id")))
        hidden = self._hidden(attrs)
        frame = {"tag": tag, "hidden": hidden, "opened": False, "prev": None}
        if opens_screen:
            frame.update(opened=True, prev=self.current)
            self.current = self._screen(attrs.get("data-screen") or attrs.get("id") or tag, self.getpos()[0])
            if hidden:
                self.current["hidden"] = True
        if tag not in _VOID:
            self.stack.append(frame)
        if tag in ("input", "textarea", "select"):
            kind = "button" if attrs.get("type") in ("submit", "button") else "field"
            text = attrs.get("value") if kind == "button" else (attrs.get("aria-label") or attrs.get("placeholder") or attrs.get("name"))
            self._add(kind, text or "", hidden)
        elif tag == "img" and attrs.get("alt"):
            self._add("image", attrs["alt"], hidden)
        kind = _TEXT_KINDS.get(tag)
        if attrs.get("role") in ("alert", "status") or (tag in ("div", "span", "p") and _MESSAGE_CLASS.search(attrs.get("class", ""))):
            kind = "message"
        if kind and tag not in _VOID:
            self.capture.append({"tag": tag, "kind": kind, "text": [], "hidden": hidden, "depth": len(self.stack)})

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style"):
            self.in_script = False
            return
        if not any(frame["tag"] == tag for frame in self.stack):
            return  # a stray end tag
        while self.stack:
            frame = self.stack.pop()
            self._flush(len(self.stack))
            if frame["opened"]:
                self.current = frame["prev"]
            if frame["tag"] == tag:
                break

    def _flush(self, depth: int) -> None:
        """Emit the captured elements opened deeper than `depth` (closed, or left unclosed inside)."""
        while self.capture and self.capture[-1]["depth"] > depth:
            item = self.capture.pop()
            self._add(item["kind"], "".join(item["text"]), item["hidden"])

    def handle_data(self, data: str) -> None:
        if self.in_script:
            if self.script_line > 0:
                self.scripts.append((self.script_line, data))
            return
        if self.capture:
            self.capture[-1]["text"].append(data)


def extract_inventory(html_text: str) -> dict[str, Any]:
    """The inventory of one HTML prototype. Pure and deterministic."""
    parser = _Inventory(data_screens="data-screen" in html_text)
    parser.feed(html_text)
    parser.close()
    parser._flush(-1)  # unclosed tags at the end of the document
    screens = [s for s in parser.screens if s["elements"]] or parser.screens
    for index, screen in enumerate(screens, start=1):  # renumber after dropping empty screens
        old = screen["id"]
        screen["id"] = f"S{index}"
        for element in screen["elements"]:
            element["id"] = element["id"].replace(f"{old}-", f"S{index}-", 1)
        screen.setdefault("hidden", False)
        if not screen["title"]:
            screen["title"] = "Outside any screen" if screen["key"] == "page" else screen["key"]
    literals: list[dict[str, Any]] = []
    seen: set[str] = set()
    for start, code in parser.scripts:
        for number, line in enumerate(code.splitlines(), start=0):
            for match in _STRING.finditer(line):
                text = next(g for g in match.groups() if g is not None)
                text = " ".join(text.split())
                if _ui_copy(text) and text not in seen:
                    seen.add(text)
                    literals.append({"id": f"JS-{len(literals) + 1:02d}", "text": text, "line": start + number})
    return {"screens": screens, "js_literals": literals}


def _html_sources(project_id: str, only: str = "") -> list[dict[str, Any]]:
    from .core.io import read_json
    from .core.paths import workspace_path

    manifest = read_json(workspace_path(project_id) / "00_raw" / "source_manifest.json", {}) or {}
    rows = []
    for row in manifest.get("registry", []) if isinstance(manifest, dict) else []:
        if not isinstance(row, dict) or (only and row.get("id") != only):
            continue
        copies = [c for c in row.get("copies") or [] if str(c).lower().endswith(HTML_SUFFIXES)]
        if copies and (only or str(row.get("validity", "current")) == "current"):
            rows.append({"id": str(row["id"]), "copy": str(copies[0]), "validity": row.get("validity")})
    return sorted(rows, key=lambda r: r["id"])


def render_inventory_md(project_id: str, prototypes: list[dict[str, Any]]) -> str:
    out = [f"# Prototype inventory — {project_id}", "",
           "Every visible element and every JavaScript copy literal of the ingested HTML prototypes, by screen. "
           "The audit and the manual cite these ids; an element that is not here does not exist.", ""]
    for proto in prototypes:
        out += [f"## {proto['source']} — `{proto['path']}`", ""]
        for screen in proto["screens"]:
            hidden = " (starts hidden)" if screen.get("hidden") else ""
            out += [f"### {screen['id']} {screen['title']}{hidden}", "", f"Screen key: `{screen['key']}` · line {screen['line']}", "",
                    "| Id | Kind | Text | Line | Starts hidden |", "|---|---|---|---|---|"]
            for e in screen["elements"]:
                out.append(f"| {e['id']} | {e['kind']} | {e['text'].replace('|', '/')} | {e['line']} | {'yes' if e['hidden'] else 'no'} |")
            out.append("")
        out += ["### JavaScript copy", ""]
        if proto["js_literals"]:
            out += ["| Id | Text | Line |", "|---|---|---|"]
            out += [f"| {lit['id']} | {lit['text'].replace('|', '/')} | {lit['line']} |" for lit in proto["js_literals"]]
        else:
            out.append("No copy literals in the scripts.")
        out.append("")
    return "\n".join(out).rstrip() + "\n"


def build_inventory(project_id: str, source: str = "") -> dict[str, Any]:
    """Inventory every current HTML prototype of the workspace (or only `source`, an F-NN)."""
    from .core.io import write_text
    from .core.paths import repo_root, workspace_path

    sources = _html_sources(project_id, source)
    if not sources:
        raise PrototypeError(f"no HTML prototype {'for ' + source + ' ' if source else ''}among the ingested sources; "
                             "ingest it first (/ingest PROJECT_ID --source prototype.html)")
    base = workspace_path(project_id)
    prototypes = []
    for row in sources:
        copy = Path(row["copy"])
        path = copy if copy.is_absolute() else repo_root() / copy
        if not path.is_file():
            raise PrototypeError(f"{row['id']}: its copy {row['copy']} is missing; ingest it again")
        inventory = extract_inventory(path.read_text(encoding="utf-8", errors="replace"))
        relative = path.resolve().relative_to(base.resolve()).as_posix() if path.resolve().is_relative_to(base.resolve()) else row["copy"]
        prototypes.append({"source": row["id"], "path": relative, **inventory})
    target = base.joinpath(*INVENTORY_DIR)
    payload = {"project_id": project_id, "prototypes": prototypes}
    write_text(target / INVENTORY_JSON, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    write_text(target / INVENTORY_MD, render_inventory_md(project_id, prototypes))
    return {"status": "inventoried", "path": (target / INVENTORY_JSON).as_posix(), "view": (target / INVENTORY_MD).as_posix(),
            "prototypes": [{"source": p["source"], "screens": len(p["screens"]),
                            "elements": sum(len(s["elements"]) for s in p["screens"]), "js_literals": len(p["js_literals"])}
                           for p in prototypes]}


def load_inventory(project_id: str) -> dict[str, Any]:
    from .core.io import read_json
    from .core.paths import workspace_path

    data = read_json(workspace_path(project_id).joinpath(*INVENTORY_DIR, INVENTORY_JSON), None)
    if not isinstance(data, dict):
        raise PrototypeError("there is no prototype inventory yet; run /prototype PROJECT_ID --inventory")
    return data
