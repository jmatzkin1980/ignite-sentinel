"""IMP-261: the governed glossary of the project's domain.

Each term carries a definition, its canonical name (the identifier used in code,
API or data, when the source gives one), what not to confuse it with, and the
source row that says it. A term the source only expands ("Service Level
Agreement (SLA)") is kept with its definition marked "(inferred)": the expansion
is not a definition. Nothing else is inferred.

Where terms come from, in order:
- confirmed answers of `GAP-PRD-GLOSSARY-GOVERNANCE` ("Term: definition; Term: ...");
- definitions in the raw input ("X means Y", "X significa Y", "X se define como Y",
  "X refers to Y", a "Glossary"/"Glosario" section with "- Term: definition" lines);
- expansions of acronyms ("Service Level Agreement (SLA)"), marked inferred.

The glossary is written to `01_discovery/glossary.json`. The brief v2 annex
`A.glossary` and PRD section 13 render it; neither invents a term.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

GLOSSARY_GAP = "GAP-PRD-GLOSSARY-GOVERNANCE"
_DEFINE_RE = re.compile(
    r"^\s*(?:[-*]\s*)?[\"'“]?(?P<term>[^\"'”:.;]{2,48}?)[\"'”]?\s+"
    r"(?:means|refers to|is defined as|stands for|significa|se refiere a|se define como|equivale a)\s+(?P<definition>.+?)\s*$",
    re.I,
)
_ITEM_RE = re.compile(r"^\s*[-*]\s*\**(?P<term>[^:*]{2,48})\**\s*:\s*(?P<definition>.{3,})$")
_ACRONYM_RE = re.compile(r"(?P<expansion>(?:[A-Z][a-zA-Záéíóú]+[ -]){1,5}[A-Z][a-zA-Záéíóú]+)\s*\((?P<acronym>[A-Z]{2,6})\)")
_CANONICAL_RE = re.compile(r"`([A-Za-z_][\w.-]{1,60})`")
_NOT_CONFUSE_RE = re.compile(r"(?:not to be confused with|do not confuse with|no confundir con|distinto de)\s+(?P<other>[^.;,]+)", re.I)
_GLOSSARY_HEADING_RE = re.compile(r"^#+\s*(glossary|glosario|definitions|definiciones)\b", re.I)


def _entry(term: str, definition: str, source: str, inferred: bool = False) -> dict[str, Any]:
    definition = " ".join(definition.split()).rstrip(".")
    canonical = _CANONICAL_RE.search(definition)
    other = _NOT_CONFUSE_RE.search(definition)
    if other:
        definition = definition[:other.start()].rstrip(" ,;(—-")
    term = re.sub(r"^(?:a|an|the|el|la|los|las|un|una)\s+", "", " ".join(term.split()).strip(" *`"), flags=re.I)
    return {
        "term": term[:1].upper() + term[1:],
        "definition": definition,
        "canonical": canonical.group(1) if canonical else "",
        "not_confuse": other.group("other").strip(" ()") if other else "",
        "source": source,
        "inferred": inferred,
    }


def terms_from_text(text: str, source: str) -> list[dict[str, Any]]:
    """Definitions, glossary-section items and acronym expansions in one source."""
    found: list[dict[str, Any]] = []
    in_glossary = False
    for line in text.splitlines():
        if line.lstrip().startswith("#"):
            in_glossary = bool(_GLOSSARY_HEADING_RE.match(line.strip()))
            continue
        item = _ITEM_RE.match(line) if in_glossary else None
        if item:
            found.append(_entry(item.group("term"), item.group("definition"), source))
            continue
        for sentence in re.split(r"(?<=[.!?])\s+", line):
            match = _DEFINE_RE.match(sentence)
            if match:
                found.append(_entry(match.group("term"), match.group("definition"), source))
    for match in _ACRONYM_RE.finditer(text):
        found.append(_entry(match.group("acronym"), match.group("expansion"), source, inferred=True))
    return found


def terms_from_answer(statement: str, source: str) -> list[dict[str, Any]]:
    """`Term: definition; Term: definition` from a confirmed glossary answer."""
    found = []
    statement = re.sub(r"^\s*(?:glossary|glosario)\s*[-—:]\s*", "", statement, flags=re.I)
    for part in re.split(r"[;\n]", statement):
        if ":" in part:
            term, definition = part.split(":", 1)
            term = term.strip()
            if term and definition.strip():
                found.append(_entry(term, definition, source))
    return found


def build_glossary(raw_sources: list[tuple[str, str, str]], answers: list[dict[str, str]]) -> list[dict[str, Any]]:
    """Answers first (they are confirmed), then the raw input; one row per term, sorted."""
    entries: list[dict[str, Any]] = []
    for answer in answers:
        if answer.get("gap") == GLOSSARY_GAP:
            entries.extend(terms_from_answer(answer.get("statement", ""), answer.get("source", "")))
    for source, _path, text in raw_sources:
        entries.extend(terms_from_text(text, source))
    by_term: dict[str, dict[str, Any]] = {}
    for entry in entries:
        key = entry["term"].lower()
        if not key:
            continue
        current = by_term.get(key)
        # a stated definition beats an inferred expansion; the first stated one wins
        if current is None or (current["inferred"] and not entry["inferred"]):
            by_term[key] = entry
    return sorted(by_term.values(), key=lambda e: e["term"].lower())


def write_glossary(project_id: str, glossary: list[dict[str, Any]]) -> Path:
    from .core.io import write_json
    from .workspace import workspace_path

    path = workspace_path(project_id) / "01_discovery" / "glossary.json"
    write_json(path, {"artifact": "glossary", "terms": glossary})
    return path


def load_glossary(project_id: str) -> list[dict[str, Any]]:
    from .core.io import read_json
    from .workspace import workspace_path

    data = read_json(workspace_path(project_id) / "01_discovery" / "glossary.json", {}) or {}
    terms = data.get("terms", []) if isinstance(data, dict) else []
    return [t for t in terms if isinstance(t, dict) and t.get("term")]


def refresh_glossary(project_id: str) -> list[dict[str, Any]]:
    """Rebuild the glossary from the workspace's raw input and confirmed answers."""
    from .compilers.brief_v2 import confirmed_answers
    from .core.io import read_json
    from .workspace import workspace_path

    base = workspace_path(project_id)
    manifest = read_json(base / "00_raw" / "source_manifest.json", {}) or {}
    registry = [row for row in manifest.get("registry", []) if isinstance(row, dict) and row.get("id")]
    raw_sources = []
    raw_dir = base / "00_raw"
    for pattern in ("*.md", "*.txt"):
        for path in sorted(raw_dir.glob(pattern)) if raw_dir.exists() else []:
            source = next((row["id"] for row in registry if path.name in [Path(p).name for p in row.get("paths", [])]), "")
            raw_sources.append((source, path.name, path.read_text(encoding="utf-8")))
    discovery = base / "01_discovery"
    answers_text = "\n".join((discovery / name).read_text(encoding="utf-8")
                             for name in ("identity_seeds.md", "decisions.md") if (discovery / name).exists())
    glossary = build_glossary(raw_sources, confirmed_answers(answers_text, registry))
    write_glossary(project_id, glossary)
    return glossary
