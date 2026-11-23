"""IMP-402 task 1: the inventory of a change request, element by element.

A request is read by structure only (headings, list items, table rows). Nothing here
interprets the text: every element keeps the lines it came from, so a later citation
can be checked against them ("transcribe, don't draft").
"""
from __future__ import annotations

import re
import unicodedata
from collections import defaultdict, deque
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any

from ..changes import change_language, get_change
from ..core.io import read_json, write_json, write_text
from ..core.paths import workspace_path
from ..source_formats import read_source
from ..source_registry import row_role
from ..sources import load_source_manifest
from . import extraction_dir

KINDS = ("rule", "criterion", "story", "decision", "section")

_NUM = r"\d+(?:\.\d+)*"
# The id is not followed by a word character or hyphen, nor by a dot that continues
# a token (`RN-01.x`); a sentence-final dot (`Regla 10.2.`) is fine.
_END = r"(?![\w-])(?!\.\w)"


def _pattern(body: str) -> re.Pattern[str]:
    return re.compile(rf"(?P<id>{body}){_END}")


ID_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("rule", _pattern(rf"RN-{_NUM}")),
    ("rule", _pattern(rf"BR-{_NUM}")),
    ("rule", _pattern(rf"R-{_NUM}")),
    ("rule", _pattern(rf"[Rr]egla {_NUM}")),
    ("rule", _pattern(rf"[Rr]ule {_NUM}")),
    ("criterion", _pattern(rf"CA-{_NUM}")),
    ("criterion", _pattern(rf"AC-{_NUM}")),
    ("criterion", _pattern(rf"[Cc]riterio {_NUM}")),
    ("criterion", _pattern(rf"[Cc]riterion {_NUM}")),
    ("story", _pattern(rf"HU-{_NUM}")),
    ("story", _pattern(r"[Hh]istoria \d+")),
    ("story", _pattern(r"[Ss]tory \d+")),
    ("decision", _pattern(rf"PD-{_NUM}")),
    ("decision", _pattern(r"[Dd]ecisi[óo]n \d+")),
)

ITEMIZED_HEADINGS: dict[str, tuple[str, str]] = {
    "reglas": ("rule", "REGLAS"),
    "reglas de negocio": ("rule", "REGLAS"),
    "rules": ("rule", "RULES"),
    "business rules": ("rule", "RULES"),
    "criterios": ("criterion", "CRITERIOS"),
    "acceptance criteria": ("criterion", "CRITERIA"),
    "criteria": ("criterion", "CRITERIA"),
    "historias": ("story", "HISTORIAS"),
    "user stories": ("story", "STORIES"),
    "stories": ("story", "STORIES"),
    "decisiones": ("decision", "DECISIONES"),
    "decisions": ("decision", "DECISIONS"),
}

_SYNTHETIC_ID = re.compile(r"^(?:%s)-\d+$" % "|".join(sorted({p for _, p in ITEMIZED_HEADINGS.values()})))

_OPENERS = re.compile(r"^(?:\||\*\*|__|`|\[|\s+)")
_LIST_MARKER = re.compile(r"^(?:[-*+]|\d+[.)])\s+")
_LIST_ITEM = re.compile(r"^ {0,3}(?:[-*+]|\d+[.)])\s+")
_HEADING = re.compile(r"^ {0,3}(#{1,6})\s+(.*?)\s*#*\s*$")
_FENCE = re.compile(r"^ {0,3}```")
_TABLE_SEPARATOR = re.compile(r"^\s*\|?\s*:?-{2,}:?\s*(?:\|\s*:?-{2,}:?\s*)*\|?\s*$")
_NUMBERING = re.compile(r"^\d+(?:\.\d+)*[.)]?\s*")


def _fold(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch)).lower().strip()


def _squash(text: str) -> str:
    return " ".join(text.split())


def match_element_id(line: str) -> tuple[str, str] | None:
    """The id a line starts with (list marker, table pipe and emphasis aside), and its kind."""
    text = _LIST_MARKER.sub("", line.lstrip(), count=1)
    while True:
        stripped = _OPENERS.sub("", text, count=1)
        if stripped == text:
            break
        text = stripped
    for kind, pattern in ID_PATTERNS:
        found = pattern.match(text)
        if found:
            return found.group("id"), kind
    return None


def _heading_keyword(heading: str) -> str:
    return _NUMBERING.sub("", _fold(heading), count=1)


def _itemized(heading: str) -> tuple[str, str] | None:
    keyword = _heading_keyword(heading)
    for name in sorted(ITEMIZED_HEADINGS, key=len, reverse=True):
        if keyword.startswith(name):
            return ITEMIZED_HEADINGS[name]
    return None


def section_slug(heading: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", _heading_keyword(heading)).strip("-")
    if len(slug) > 40:
        cut = slug[:40]
        if slug[40] != "-" and "-" in cut:
            cut = cut.rsplit("-", 1)[0]
        slug = cut.strip("-")
    return slug or "seccion"


_HOME_WORDS: tuple[tuple[int, re.Pattern[str]], ...] = (
    (2, re.compile(r"\b(?:objetivo|objective|problema|problem|resultado|outcome|usuario|user|actor|rol|role)")),
    (4, re.compile(r"(?:\b(?:proceso|process|flujo|flow|situacion|as-is|to-be)|estado futuro)")),
    (3, re.compile(r"\b(?:alcance|scope)")),
    (6, re.compile(r"\b(?:preserva|preserved)|se mantiene")),
)


def home_section(kind: str, heading: str) -> int | None:
    """The brief section where an element of this kind belongs by default."""
    if kind in ("rule", "criterion", "decision"):
        return 7
    if kind == "story":
        return 4
    folded = _fold(heading)
    for number, pattern in _HOME_WORDS:
        if pattern.search(folded):
            return number
    return None


# --- parsing ---------------------------------------------------------------------


def _split_lines(text: str) -> list[str]:
    return text.replace("\r\n", "\n").replace("\r", "\n").split("\n")


def _segments(lines: list[str]) -> list[dict[str, Any]]:
    """Cut the text into sections: the intro, then one per `##`-`######` heading."""
    segments: list[dict[str, Any]] = [{"heading": "", "intro": True, "hline": None, "lines": []}]
    in_fence = False
    for number, raw in enumerate(lines, start=1):
        if _FENCE.match(raw):
            in_fence = not in_fence
            segments[-1]["lines"].append((number, raw, True))
            continue
        if in_fence:
            segments[-1]["lines"].append((number, raw, True))
            continue
        heading = _HEADING.match(raw)
        if heading:
            if len(heading.group(1)) == 1:
                continue  # the document title is neither a section nor text
            segments.append({"heading": heading.group(2), "intro": False, "hline": number, "lines": []})
            continue
        segments[-1]["lines"].append((number, raw, False))
    return segments


def _blocks(seg_lines: list[tuple[int, str, bool]]) -> list[dict[str, Any]]:
    """Candidates (list items, table rows) and plain text lines of a section, in order."""
    blocks: list[dict[str, Any]] = []
    index = 0
    total = len(seg_lines)

    def is_table_row(raw: str) -> bool:
        return raw.lstrip().startswith("|") and len(raw) - len(raw.lstrip()) <= 3

    while index < total:
        number, raw, fenced = seg_lines[index]
        if not raw.strip():
            index += 1
            continue
        if fenced or _FENCE.match(raw):
            blocks.append({"type": "text", "lines": [number]})
            index += 1
            continue
        if is_table_row(raw):
            rows: list[tuple[int, str]] = []
            while index < total and not seg_lines[index][2] and is_table_row(seg_lines[index][1]):
                rows.append((seg_lines[index][0], seg_lines[index][1]))
                index += 1
            skeleton: list[int] = []  # header and separator
            body: list[tuple[int, str]] = []
            for position, (row_number, row_raw) in enumerate(rows):
                following = rows[position + 1][1] if position + 1 < len(rows) else None
                if _TABLE_SEPARATOR.match(row_raw) or (following is not None and _TABLE_SEPARATOR.match(following) and not skeleton):
                    skeleton.append(row_number)
                else:
                    body.append((row_number, row_raw))
            blocks.append({"type": "table", "skeleton": skeleton, "rows": body})
            continue
        if _LIST_ITEM.match(raw):
            last = number
            index += 1
            while index < total:
                n2, r2, f2 = seg_lines[index]
                if not r2.strip() or f2 or _FENCE.match(r2) or _LIST_ITEM.match(r2) or is_table_row(r2):
                    break
                last = n2
                index += 1
            blocks.append({"type": "item", "first": number, "last": last})
            continue
        blocks.append({"type": "text", "lines": [number]})
        index += 1
    return blocks


def _element(
    element_id: str, kind: str, heading: str, source_id: str, path: str,
    spans: list[list[int]], lines: list[str], prefix: str | None = None,
) -> dict[str, Any]:
    flat = _squash(" ".join(" ".join(lines[start - 1 : end]) for start, end in spans))
    return {
        "id": element_id,
        "kind": kind,
        "section": heading or "intro",
        "section_slug": section_slug(heading) if heading else "intro",
        "source_id": source_id,
        "path": path,
        "line": spans[0][0],
        "end_line": spans[-1][1],
        "spans": spans,
        "excerpt": flat[:400],
        "sha": sha256(flat.encode("utf-8")).hexdigest()[:16],
        "home": home_section(kind, heading),
        "_prefix": prefix,
    }


def _nonblank_span(lines: list[str], first: int, last: int) -> list[int] | None:
    numbers = [n for n in range(first, last + 1) if lines[n - 1].strip()]
    return [numbers[0], numbers[-1]] if numbers else None


def _parse(text: str, source_id: str, path: str) -> list[dict[str, Any]]:
    lines = _split_lines(text)
    found: list[dict[str, Any]] = []
    counters: dict[str, int] = defaultdict(int)
    segments = _segments(lines)
    for position, segment in enumerate(segments):
        heading = segment["heading"]
        if not segment["intro"]:
            head_id = match_element_id(heading)
            if head_id:
                # a heading that starts with an id is one element, up to the next heading
                span = _nonblank_span(lines, segment["hline"], segment["lines"][-1][0] if segment["lines"] else segment["hline"])
                found.append(_element(head_id[0], head_id[1], heading, source_id, path, [span], lines))
                continue
        itemized = _itemized(heading) if heading else None
        text_runs: list[list[int]] = [[]]
        seen_element = False
        for block in _blocks(segment["lines"]):
            if block["type"] == "text":
                text_runs[-1].extend(block["lines"])
                continue
            if block["type"] == "item":
                candidates = [(block["first"], block["last"])]
            else:
                candidates = [(n, n) for n, _ in block["rows"]]
            made_any = False
            for first, last in candidates:
                matched = match_element_id(lines[first - 1])
                if matched:
                    element_id, kind = matched
                    prefix = None
                elif itemized:
                    kind, prefix = itemized
                    counters[prefix] += 1
                    element_id = f"{prefix}-{counters[prefix]}"
                else:
                    text_runs[-1].extend(n for n in range(first, last + 1))
                    continue
                if itemized and not seen_element and not made_any:
                    _drop_intro_line(text_runs, lines, first)
                made_any = True
                seen_element = True
                found.append(_element(element_id, kind, heading, source_id, path, [[first, last]], lines, prefix))
                text_runs.append([])
            if block["type"] == "table":
                if not made_any:
                    text_runs[-1].extend(block["skeleton"])
                else:
                    text_runs.append([])
        spans = [s for s in (_run_span(lines, run) for run in text_runs) if s]
        if spans:
            slug = section_slug(heading) if heading else "intro"
            found.append(_element(f"SEC-{slug}", "section", heading, source_id, path, spans, lines))
    found.sort(key=lambda e: (e["line"], e["end_line"]))
    seen: dict[str, int] = {}
    for item in found:
        count = seen.get(item["id"], 0) + 1
        seen[item["id"]] = count
        if count > 1:
            item["id"] = f"{item['id']}#{count}"
    return found


def _run_span(lines: list[str], run: list[int]) -> list[int] | None:
    numbers = sorted(n for n in run if lines[n - 1].strip())
    if not numbers:
        return None
    return [numbers[0], numbers[-1]]


def _drop_intro_line(text_runs: list[list[int]], lines: list[str], first_candidate: int) -> None:
    """An introducing line ending in `:` right before the first item of an itemized section is not text."""
    run = text_runs[-1]
    nonblank = [n for n in run if lines[n - 1].strip()]
    if not nonblank:
        return
    last = nonblank[-1]
    if lines[last - 1].rstrip().endswith(":") and all(not lines[n - 1].strip() for n in range(last + 1, first_candidate)):
        run.remove(last)


def parse_request_elements(text: str, source_id: str, path: str) -> list[dict]:
    elements = _parse(text, source_id, path)
    for item in elements:
        item.pop("_prefix", None)
    return elements


# --- inventory of a change ------------------------------------------------------------


def pedido_rows(project_id: str, change_id: str) -> list[dict]:
    change = get_change(project_id, change_id)
    registry = {row.get("id"): row for row in load_source_manifest(project_id).get("registry", [])}
    rows: list[dict] = []
    for source_id in change.get("sources", []) or []:
        row = registry.get(source_id)
        if row is not None and row_role(row) == "pedido":
            rows.append(row)
    return rows


def _row_path(row: dict) -> str:
    candidates = (row.get("copies") or []) or (row.get("paths") or [])
    return str(candidates[0]) if candidates else ""


def _resolve(base: Path, relative: str) -> Path | None:
    if not relative:
        return None
    for candidate in (base / relative, Path(relative)):
        if candidate.is_file():
            return candidate
    return None


def _read_text(base: Path, relative: str) -> str | None:
    path = _resolve(base, relative)
    if path is None:
        return None
    try:
        text = read_source(path, extracted_at="inventory").text
    except Exception:  # an unreadable or unsupported file is reported, not fatal
        return None
    return None if "\x00" in text else text


def inventory_path(base: Path, change_id: str) -> Path:
    return extraction_dir(base, change_id) / "inventory.json"


def worksheet_path(base: Path, change_id: str) -> Path:
    return extraction_dir(base, change_id) / "proposals_template.md"


def load_inventory(base: Path, change_id: str) -> dict | None:
    data = read_json(inventory_path(base, change_id), None)
    return data if isinstance(data, dict) else None


def _by_kind(elements: list[dict]) -> dict[str, int]:
    counts = {kind: sum(1 for e in elements if e["kind"] == kind) for kind in KINDS}
    return {kind: n for kind, n in counts.items() if n}


def _stale_proposals(base: Path, change_id: str, elements: list[dict]) -> list[str]:
    path = extraction_dir(base, change_id) / "proposals.json"
    data = read_json(path, None)
    if not isinstance(data, dict):
        return []
    items = data.get("items", data.get("proposals", data))  # proposals.json: {"items": {id: item}}
    if not isinstance(items, dict):
        return []
    by_id = {e["id"]: e["sha"] for e in elements}
    stale = []
    for element_id, item in items.items():
        if not isinstance(item, dict):
            continue
        sha = item.get("element_sha")
        if element_id not in by_id or (sha and by_id[element_id] != sha):
            stale.append(element_id)
    return stale


def _assign_synthetic(elements: list[dict], previous: dict | None) -> None:
    """Keep the ids of synthetic elements whose text did not change; number the new ones."""
    previous_elements = (previous or {}).get("elements", []) or []
    reusable: dict[str, deque[str]] = defaultdict(deque)
    used = {e["id"] for e in previous_elements}
    for old in previous_elements:
        if _SYNTHETIC_ID.match(old["id"]):
            reusable[old["sha"]].append(old["id"])
    pending = []
    taken: set[str] = set()
    for item in elements:
        if not item["_prefix"]:
            continue
        queue = reusable.get(item["sha"])
        if queue:
            item["id"] = queue.popleft()
            taken.add(item["id"])
        else:
            pending.append(item)
    used |= taken | {e["id"] for e in elements if not e["_prefix"]}
    for item in pending:
        number = 1
        while f"{item['_prefix']}-{number}" in used:
            number += 1
        item["id"] = f"{item['_prefix']}-{number}"
        used.add(item["id"])


def _worksheet(project_id: str, change_id: str, elements: list[dict], language: str) -> str:
    if language == "es":
        header = (
            f"# Planilla de propuestas — {change_id}\n\n"
            f"Copiá este archivo fuera de 02_requirements, completá un bloque por elemento y corré "
            f"/extract {project_id} --change {change_id} --proposals ARCHIVO. "
            "Un bloque con Tratamiento vacío no es una propuesta.\n"
        )
        labels = ("Tratamiento", "Cita", "Enunciado", "Delta", "Superficie", "Seccion", "Texto", "Motivo", "Marca")
    else:
        header = (
            f"# Proposals worksheet — {change_id}\n\n"
            f"Copy this file outside 02_requirements, fill in one block per element and run "
            f"/extract {project_id} --change {change_id} --proposals FILE. "
            "A block with an empty Treatment is not a proposal.\n"
        )
        labels = ("Treatment", "Quote", "Statement", "Delta", "Surface", "Section", "Text", "Reason", "Flag")
    treatment, quote, statement, delta, surface, section, text, reason, flag = labels
    parts = [header]
    for item in elements:
        parts.append(
            f"\n### {item['id']}\n"
            f"<!-- {item['section_slug']} · {item['source_id']}:{item['line']} · {item['kind']} -->\n"
            f"> {item['excerpt']}\n"
            f"- {treatment}:\n"
            f"- {quote}:\n"
            f"- {statement}:\n"
            f"  - {delta}:\n"
            f"  - {surface}:\n"
            f"- {section}:\n"
            f"- {text}:\n"
            f"- {reason}:\n"
            f"- {flag}:\n"
        )
    return "".join(parts)


def build_inventory(project_id: str, change_id: str) -> dict:
    change = get_change(project_id, change_id)
    base = workspace_path(project_id)
    rows = pedido_rows(project_id, change_id)
    previous = load_inventory(base, change_id)

    sources: list[dict] = []
    elements: list[dict] = []
    unreadable: list[str] = []
    seen_bases: set[str] = set()
    first_text = ""
    for row in rows:
        source_id = str(row["id"])
        path = _row_path(row)
        sources.append({"id": source_id, "path": path, "hash": str(row.get("hash", ""))})
        text = _read_text(base, path)
        if text is None:
            unreadable.append(source_id)
            continue
        first_text = first_text or text
        local = _parse(text, source_id, path)
        local_bases: set[str] = set()
        for item in local:
            if item["_prefix"]:
                continue
            id_base, _, repeat = item["id"].partition("#")
            if id_base in seen_bases:
                item["id"] = f"{id_base}@{source_id}" + (f"#{repeat}" if repeat else "")
            local_bases.add(id_base)
        seen_bases |= local_bases
        elements.extend(local)
    _assign_synthetic(elements, previous)
    for item in elements:
        item.pop("_prefix", None)

    key = sorted((e["id"], e["sha"]) for e in elements)
    previous_key = sorted((e["id"], e["sha"]) for e in (previous or {}).get("elements", []))
    changed = previous is None or key != previous_key
    version = 1 if previous is None else int(previous.get("version", 1)) + (1 if changed else 0)
    by_kind = _by_kind(elements)
    inv_path = inventory_path(base, change_id)
    sheet_path = worksheet_path(base, change_id)
    if changed or previous is None or previous.get("sources") != sources or not sheet_path.exists():
        language = change_language(project_id, change, first_text)
        write_json(inv_path, {
            "schema_version": 1,
            "change_id": change_id,
            "version": version,
            "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "sources": sources,
            "elements": elements,
            "total": len(elements),
            "by_kind": by_kind,
        })
        write_text(sheet_path, _worksheet(project_id, change_id, elements, language))
    return {
        "project_id": project_id,
        "change_id": change_id,
        "action": "inventory",
        "inventory_path": str(inv_path),
        "worksheet_path": str(sheet_path),
        "version": version,
        "total": len(elements),
        "by_kind": by_kind,
        "changed": changed,
        "unreadable": unreadable,
        "stale_proposals": _stale_proposals(base, change_id, elements),
    }


def inventory_state(project_id: str, change_id: str) -> str:
    base = workspace_path(project_id)
    inventory = load_inventory(base, change_id)
    if inventory is None:
        return "missing"
    current = [(str(row["id"]), str(row.get("hash", ""))) for row in pedido_rows(project_id, change_id)]
    recorded = [(str(s.get("id")), str(s.get("hash", ""))) for s in inventory.get("sources", [])]
    if current != recorded:
        return "stale"
    return "empty" if not inventory.get("total") else "current"


def element_text(base: Path, element: dict) -> str | None:
    """The text of the element's spans, read from its source file; None if it cannot be read."""
    text = _read_text(base, str(element.get("path", "")))
    if text is None:
        return None
    lines = _split_lines(text)
    chunks = []
    for start, end in element.get("spans", []):
        if start < 1 or end > len(lines):
            return None
        chunks.append("\n".join(lines[start - 1 : end]))
    return "\n".join(chunks)
