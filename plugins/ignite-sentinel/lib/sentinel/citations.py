"""IMP-249: structured citations and their validator.

A structured citation is `{doc, section[, subblock], id}` plus `supports` (what the
cited id holds up). Inside a Markdown artifact it is written inline:

    [[brief § 2.2 › Alta # RN-04 — sostiene: el alta exige doble firma]]

`›` can be written `>` and `—` can be written `--`. `sostiene`, `que_sostiene` and
`supports` are the same key. `doc` is a short name from the registry (`brief`,
`prd`, `specs`...) or a workspace-relative path.

The validator resolves the id **inside the cited section** (and sub-block): an id
that exists elsewhere in the document but not there is a finding. It also reports
an id of no registered family, a retired id, a citation without `supports`, and, in
a human v2 artifact, any citation by line number (`file.md:120`, `línea 12`),
because line numbers rot on the next edit.

Structured citations are required only in v2 artifacts, which carry the marker
`<!-- sentinel-artifact: v2 -->`. Brief v2 is born in H16 (IMP-252); until then no
artifact carries the marker, so v1 artifacts are validated exactly as before.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .ids import family_of, id_registry, load_retired_ids

CITATION_RE = re.compile(
    r"\[\[\s*(?P<doc>[^§\]\n]+?)\s*§\s*(?P<section>[^›>#\]\n]+?)\s*"
    r"(?:(?:›|>)\s*(?P<subblock>[^#\]\n]+?)\s*)?"
    r"#\s*(?P<id>[^\s—\]]+)\s*"
    r"(?:(?:—|--)\s*(?:que_sostiene|sostiene|supports)\s*:\s*(?P<supports>[^\]\n]*?)\s*)?\]\]"
)
LINE_CITATION_RE = re.compile(
    r"\b[\w./-]+\.(?:md|txt|html?|docx|json|ya?ml)(?::|#L)\d+\b"
    r"|\bl[ií]neas?\s+\d+\b|\blines?\s+\d+\b|\bL\d+(?:-L?\d+)?\b",
    re.I,
)
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")


@dataclass(frozen=True)
class Citation:
    doc: str
    section: str
    id: str
    supports: str = ""
    subblock: str = ""
    line: int = 0

    def label(self) -> str:
        sub = f" › {self.subblock}" if self.subblock else ""
        return f"[[{self.doc} § {self.section}{sub} # {self.id}]]"


def _fold(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    return " ".join("".join(ch for ch in decomposed if not unicodedata.combining(ch)).lower().split())


def is_v2_artifact(text: str) -> bool:
    return id_registry()["v2_marker"] in text[:2000]


def parse_citations(text: str) -> list[Citation]:
    found: list[Citation] = []
    for number, line in enumerate(text.splitlines(), start=1):
        for match in CITATION_RE.finditer(line):
            found.append(Citation(
                doc=match.group("doc").strip(), section=match.group("section").strip(), id=match.group("id").strip(),
                supports=(match.group("supports") or "").strip(), subblock=(match.group("subblock") or "").strip(),
                line=number,
            ))
    return found


def citation_from_dict(data: dict[str, Any]) -> Citation:
    """The JSON form: `{doc, seccion|section, subbloque|subblock?, id, que_sostiene|supports}`."""
    return Citation(
        doc=str(data.get("doc", "")).strip(),
        section=str(data.get("seccion", data.get("section", ""))).strip(),
        subblock=str(data.get("subbloque", data.get("subblock", "")) or "").strip(),
        id=str(data.get("id", "")).strip(),
        supports=str(data.get("que_sostiene", data.get("supports", "")) or "").strip(),
    )


# --- sections ------------------------------------------------------------------


def _headings(lines: list[str]) -> list[tuple[int, int, str]]:
    """(index, level, title) per Markdown heading, skipping fenced code."""
    found: list[tuple[int, int, str]] = []
    fenced = False
    for index, line in enumerate(lines):
        if line.lstrip().startswith("```"):
            fenced = not fenced
            continue
        match = None if fenced else _HEADING_RE.match(line)
        if match:
            found.append((index, len(match.group(1)), match.group(2).strip()))
    return found


def _title_matches(title: str, wanted: str) -> bool:
    """`2.2` matches `2.2 Reglas de negocio` and `§2.2 ...`; a title matches itself."""
    title_f, wanted_f = _fold(title).lstrip("§ "), _fold(wanted).lstrip("§ ")
    if title_f == wanted_f or re.sub(r"^[0-9]+(?:\.[0-9]+)*\.?\s+", "", title_f) == wanted_f:
        return True  # "Reglas de negocio" matches "2.2 Reglas de negocio"
    if re.fullmatch(r"[0-9]+(?:\.[0-9]+)*", wanted_f):
        return re.match(rf"{re.escape(wanted_f)}(?:\.(?![0-9]))?(?![0-9.])", title_f) is not None
    return False


def section_text(text: str, section: str, subblock: str = "") -> str | None:
    """The body of `section` (and of `subblock` inside it), or None when it is not there."""
    lines = text.splitlines()
    headings = _headings(lines)

    def body(candidates: list[tuple[int, int, str]], wanted: str, start: int, stop: int) -> tuple[int, int] | None:
        for position, (index, level, title) in enumerate(candidates):
            if start <= index < stop and _title_matches(title, wanted):
                end = next((i for i, lvl, _ in candidates[position + 1:] if lvl <= level and i < stop), stop)
                return index, end
        return None

    span = body(headings, section, 0, len(lines))
    if span is None:
        return None
    if subblock:
        span = body(headings, subblock, span[0] + 1, span[1])
        if span is None:
            return None
    return "\n".join(lines[span[0]:span[1]])


def _id_in(text: str, value: str) -> bool:
    return re.search(rf"(?<![\w-]){re.escape(value)}(?![\w-]|\.[0-9])", text) is not None


# --- validation ----------------------------------------------------------------


def resolve_doc(base: Path, doc: str) -> Path:
    mapped = id_registry()["citation_documents"].get(doc.strip().lower())
    return base / (mapped or doc.strip())


def validate_citation(citation: Citation, documents: dict[str, str], retired: dict[str, Any] | None = None) -> list[str]:
    """Findings for one citation. `documents` maps a doc name to its text."""
    where = f"{citation.label()}" + (f" (line {citation.line})" if citation.line else "")
    findings: list[str] = []
    if not citation.supports:
        findings.append(f"{where}: says nothing about what the id supports (add `— sostiene: ...`).")
    if family_of(citation.id) is None:
        findings.append(f"{where}: {citation.id} is not an id of any registered family.")
        return findings
    if citation.id in (retired or {}):
        findings.append(f"{where}: {citation.id} is retired; cite what replaced it.")
    text = documents.get(citation.doc)
    if text is None:
        findings.append(f"{where}: document {citation.doc!r} not found.")
        return findings
    body = section_text(text, citation.section, citation.subblock)
    if body is None:
        target = f"section {citation.section!r}" + (f" › {citation.subblock!r}" if citation.subblock else "")
        findings.append(f"{where}: {target} not found in {citation.doc}.")
    elif not _id_in(body, citation.id):
        elsewhere = " (it is elsewhere in the document)" if _id_in(text, citation.id) else ""
        findings.append(f"{where}: {citation.id} is not in the cited section{elsewhere}.")
    return findings


def line_citations(text: str) -> list[tuple[int, str]]:
    """Citations by line number, outside fenced code and outside structured citations."""
    found: list[tuple[int, str]] = []
    fenced = False
    for number, line in enumerate(text.splitlines(), start=1):
        if line.lstrip().startswith("```"):
            fenced = not fenced
            continue
        if fenced:
            continue
        stripped = CITATION_RE.sub("", line)
        for match in LINE_CITATION_RE.finditer(stripped):
            found.append((number, match.group(0)))
    return found


def validate_v2_artifact(name: str, text: str, documents: dict[str, str], retired: dict[str, Any] | None = None) -> list[str]:
    findings = [f"{name} line {number}: cites by line number ({quote}); a v2 artifact cites {{doc, section, id}}."
                for number, quote in line_citations(text)]
    for citation in parse_citations(text):
        findings.extend(f"{name}: {finding}" for finding in validate_citation(citation, documents, retired))
    return findings


def validate_structured_citations(base: Path) -> list[str]:
    """Validate every v2 artifact in the workspace. v1 artifacts are left untouched."""
    retired = load_retired_ids(base)
    findings: list[str] = []
    cache: dict[str, str | None] = {}

    def load(doc: str) -> str | None:
        if doc not in cache:
            path = resolve_doc(base, doc)
            try:
                cache[doc] = path.read_text(encoding="utf-8") if path.is_file() and path.resolve().is_relative_to(base.resolve()) else None
            except (OSError, UnicodeDecodeError):
                cache[doc] = None
        return cache[doc]

    for path in sorted(base.glob("0[1-6]_*/**/*.md")):
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if not is_v2_artifact(text):
            continue
        documents = {c.doc: t for c in parse_citations(text) if (t := load(c.doc)) is not None}
        findings.extend(validate_v2_artifact(path.relative_to(base).as_posix(), text, documents, retired))
    return findings
