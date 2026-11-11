"""IMP-254: one normalized reading of the project brief, v1 or v2.

Every reader of the brief asks the same questions: which narrative lens is
populated, which marks are open, what does a section say. This module answers
them for both brief generations, so no reader parses section numbers itself.

The canonical keys are the six lenses of the v1 brief ("1".."6"), the keys the
gap map, the maturity metrics and the brief→PRD continuity check already use:

    1 Identidad y Valor       4 Lente de Diseño
    2 Lente de Negocio        5 Lente Técnico
    3 Lente de Producto       6 Gobernanza y Restricciones

A v1 brief maps one to one (`## N.` headings, read exactly as before). A v2 brief
(marker `<!-- sentinel-artifact: v2 -->`) maps through `V2_LENS_MAP`: §1–§4 feed
their lens, §5 feeds lens 5 except §5.11, and §5.11 plus §6 feed lens 6. §0 and
§7–§9 are header and closing material and feed no lens.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from .brief_schema import load_brief_schema, schema_ids
from .citations import Citation, is_v2_artifact, parse_citations, section_text

LENSES = ("1", "2", "3", "4", "5", "6")
LENS_TITLES = {
    "1": "Identidad y Valor",
    "2": "Lente de Negocio (actores)",
    "3": "Lente de Producto (proceso/journey)",
    "4": "Lente de Diseño",
    "5": "Lente Técnico",
    "6": "Gobernanza y Restricciones",
}
# lens -> (v2 ids it includes, v2 ids carved out of those)
V2_LENS_MAP: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "1": (("1",), ()),
    "2": (("2",), ()),
    "3": (("3",), ()),
    "4": (("4",), ()),
    "5": (("5",), ("5.11",)),
    "6": (("5.11", "6"), ()),
}

V1_SECTION_RE = re.compile(r"^## (\d+)\.", re.M)
V1_PENDING_MARKERS = ("[PENDING INPUT]", "TBD", "PENDING DOMAIN", "No structured evidence", "Documentar el", "Documentar la")
V2_PENDING_RE = re.compile(r"⏳\s*(?P<domain>PENDIENTE DOMINIO|PENDING DOMAIN|PENDIENTE|PENDING)\b(?:\s*\((?P<gap>[^)]*)\))?")
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")

# v1 heading terms the retrieval plans ask for -> the v2 section that holds them.
V2_HEADING_ALIASES = {
    "identidad": "1.1",
    "identity": "1.1",
    "executive summary": "1.1",
    "problem": "1.2",
    "kpi": "1.3",
    "metric": "1.3",
    "usuarios": "2.1",
    "users": "2.1",
    "personas": "2.1",
    "jobs": "2.4",
    "functional requirements": "3.2",
    "requerimientos funcionales": "3.2",
    "lente tecnico": "5",
    "governance": "5.11",
    "constraints": "5.11",
    "decisions": "6",
    "dependency": "7",
    "roadmap": "9",
    "delivery": "9",
    "backlog": "9",
    "acceptance": "1.5",
    "traceability": "A.provenance",
    "trazabilidad": "A.provenance",
}


@dataclass(frozen=True)
class BriefSection:
    id: str
    title: str
    level: int
    start: int  # 0-based index of the heading line
    end: int  # exclusive


@dataclass
class BriefModel:
    version: int
    text: str
    sections: dict[str, BriefSection] = field(default_factory=dict)
    lens_bodies: dict[str, str] = field(default_factory=dict)
    markers: list[dict[str, object]] = field(default_factory=list)
    citations: list[Citation] = field(default_factory=list)

    def lens_body(self, lens: str) -> str:
        return self.lens_bodies.get(lens, "")

    def is_pending(self, body: str) -> bool:
        if not body.strip():
            return True
        if self.version == 2:
            return V2_PENDING_RE.search(body) is not None
        return any(marker in body for marker in V1_PENDING_MARKERS)

    def citation_count(self, body: str) -> int:
        if self.version == 2:
            return len(parse_citations(body))
        return body.count("00_raw/") + body.count("`GAP-") + body.count("`CHG-")

    def section_id_at_line(self, line: int) -> str:
        """The innermost v2 section holding 1-based `line`, or ""."""
        index = line - 1
        best: BriefSection | None = None
        for section in self.sections.values():
            if section.start <= index < section.end and (best is None or section.level > best.level):
                best = section
        return best.id if best else ""


def parse_brief(text: str) -> BriefModel:
    if is_v2_artifact(text):
        return _parse_v2(text)
    return _parse_v1(text)


@lru_cache(maxsize=32)
def _load_cached(path: str, mtime_ns: int) -> BriefModel:
    return parse_brief(Path(path).read_text(encoding="utf-8"))


def load_brief_model(path: Path | str) -> BriefModel | None:
    target = Path(path)
    if not target.is_file():
        return None
    return _load_cached(str(target), target.stat().st_mtime_ns)


def _parse_v1(text: str) -> BriefModel:
    bodies: dict[str, list[str]] = {}
    sections: dict[str, BriefSection] = {}
    current = None
    lines = text.splitlines()
    for index, line in enumerate(lines):
        match = V1_SECTION_RE.match(line)
        if match:
            current = match.group(1)
            bodies.setdefault(current, [])
            if current not in sections:
                sections[current] = BriefSection(current, line[3:].strip(), 2, index, len(lines))
        elif current is not None:
            bodies[current].append(line)
    # close each section at the next numbered heading
    ordered = sorted(sections.values(), key=lambda s: s.start)
    for position, section in enumerate(ordered):
        end = ordered[position + 1].start if position + 1 < len(ordered) else len(lines)
        sections[section.id] = BriefSection(section.id, section.title, section.level, section.start, end)
    model = BriefModel(version=1, text=text, sections=sections)
    model.lens_bodies = {lens: "\n".join(bodies.get(lens, [])) for lens in LENSES}
    return model


@lru_cache(maxsize=1)
def _v2_known_ids() -> frozenset[str]:
    schema = load_brief_schema()
    ids = set(schema_ids())
    ids.update(str(section["id"]) for section in schema["sections"])
    return frozenset(ids)


def _heading_id(title: str) -> str:
    token = title.lstrip("§ ").split(" ", 1)[0].rstrip(".")
    return token if token in _v2_known_ids() else ""


def _parse_v2(text: str) -> BriefModel:
    lines = text.splitlines()
    headings: list[tuple[int, int, str]] = []
    fenced = False
    for index, line in enumerate(lines):
        if line.lstrip().startswith("```"):
            fenced = not fenced
            continue
        match = None if fenced else _HEADING_RE.match(line)
        if match:
            headings.append((index, len(match.group(1)), match.group(2).strip()))
    sections: dict[str, BriefSection] = {}
    for position, (index, level, title) in enumerate(headings):
        sid = _heading_id(title)
        if not sid or sid in sections:
            continue
        end = next((i for i, lvl, _ in headings[position + 1:] if lvl <= level), len(lines))
        sections[sid] = BriefSection(sid, title, level, index, end)
    model = BriefModel(version=2, text=text, sections=sections, citations=parse_citations(text))
    for lens in LENSES:
        include, exclude = V2_LENS_MAP[lens]
        covered: set[int] = set()
        for sid in include:
            if sid in sections:
                covered.update(range(sections[sid].start, sections[sid].end))
        for sid in exclude:
            if sid in sections:
                covered.difference_update(range(sections[sid].start, sections[sid].end))
        model.lens_bodies[lens] = "\n".join(lines[i] for i in sorted(covered))
    for number, line in enumerate(lines, start=1):
        for match in V2_PENDING_RE.finditer(line):
            domain = "DOM" in match.group("domain")
            model.markers.append({
                "kind": "pending_domain" if domain else "pending",
                "class": "domain" if domain else "client",
                "gap": (match.group("gap") or "").strip(),
                "line": number,
                "section_id": model.section_id_at_line(number),
            })
    return model


def lenses_for_v2_id(sid: str) -> list[str]:
    """Which lens a v2 section or subsection feeds ([] for §0, §7–§9 and annexes)."""
    found = []
    for lens in LENSES:
        include, exclude = V2_LENS_MAP[lens]
        if any(_within(sid, ex) for ex in exclude):
            continue
        if any(_within(sid, inc) for inc in include):
            found.append(lens)
    return found


def _within(sid: str, ancestor: str) -> bool:
    return sid == ancestor or sid.startswith(ancestor + ".") or sid.startswith(ancestor + "/")


def v2_sections_for_lens(lens: str) -> list[str]:
    include, _ = V2_LENS_MAP.get(lens, ((), ()))
    return list(include)


# IMP-253a: the v2 subsection a gap's confirmed answer feeds. Finer than the lens
# map: GAP-SCOPE lands in §6.1 (lens 6), GAP-BUSINESS-RULES in §2.2 (lens 2) and
# GAP-DELIVERY-READINESS in §9.1 (no lens); a test pins those exceptions.
V2_GAP_ROUTES = {
    "GAP-OBJECTIVE": "1.1",
    "GAP-METRIC-SOURCE": "1.3",
    "GAP-METRIC-DEFINITION": "1.3",
    "GAP-ACCEPTANCE": "1.5",
    "GAP-PRD-FR-AC": "1.5",
    "GAP-QUALITY": "1.5",
    "GAP-USERS": "2.1",
    "GAP-PRD-PERSONA-DETAIL": "2.1",
    "GAP-BUSINESS-RULES": "2.2",
    "GAP-PRODUCT-ASIS-TOBE": "3.2",
    "GAP-QUALITY-HANDOFF": "3.6",
    "GAP-DESIGN-FLOW": "4.1",
    "GAP-DESIGN-STATES": "4.1",
    "GAP-DESIGN-PROTOTYPE-INPUT": "4.3",
    "GAP-TECH-DEEP-DIVE-INPUT": "5.1",
    "GAP-FRONTEND-SURFACE": "5.1",
    "GAP-PRD-ROLLOUT-ENVIRONMENTS": "5.2",
    "GAP-TECH-DATA-SOURCE": "5.3",
    "GAP-GOVERNANCE-CONSTRAINTS": "5.11",
    "GAP-BACKEND-SURFACE": "5.12",
    "GAP-TECH-NFR": "5.16",
    "GAP-PRD-NFR-KPI": "5.16",
    "GAP-SCOPE": "6.1",
    "GAP-PRD-DEPENDENCIES-ROADMAP": "7.1",
    "GAP-DELIVERY-READINESS": "9.1",
    "GAP-BACKLOG-SLICING-READINESS": "9.1",
    "GAP-BACKLOG-ENABLERS": "9.1",
    "GAP-PRD-GLOSSARY-GOVERNANCE": "A.glossary",
    "GAP-PRD-GOVERNANCE": "5.11",
}
# IMP-26u: a counterpart answer (IMP-256) completes what the source already says at
# its place instead of replacing it: the exclusion stays and gains its decision.
V2_GAP_COMPLEMENTS = {
    "GAP-CTP-EXCLUSION": "6.2",
    "GAP-CTP-DEADLINE": "2.5",
    "GAP-CTP-PERSONAL-DATA": "5.11",
    "GAP-CTP-NORM": "5.11",
    "GAP-CTP-DESIGN-EXCLUSION": "4.2",
}
# The gap a pending mark points to when no gap is routed to that subsection.
LENS_DEFAULT_GAP = {
    "1": "GAP-OBJECTIVE",
    "2": "GAP-USERS",
    "3": "GAP-PRODUCT-ASIS-TOBE",
    "4": "GAP-DESIGN-FLOW",
    "5": "GAP-TECH-DEEP-DIVE-INPUT",
    "6": "GAP-GOVERNANCE-CONSTRAINTS",
}
NO_LENS_DEFAULT_GAP = "GAP-DELIVERY-READINESS"


def v2_sections_for_gap(gap_id: str) -> list[str]:
    """The v2 subsection a gap feeds: its route, else every section of its lens."""
    if gap_id in V2_GAP_ROUTES:
        return [V2_GAP_ROUTES[gap_id]]
    if gap_id in V2_GAP_COMPLEMENTS:
        return [V2_GAP_COMPLEMENTS[gap_id]]
    from .discovery import brief_section_for_gap

    lens = brief_section_for_gap(gap_id)
    return v2_sections_for_lens(lens) if lens else []


def default_gap_for(sid: str) -> str:
    routed = sorted(gap for gap, target in V2_GAP_ROUTES.items() if target == sid)
    if routed:
        return routed[0]
    lenses = lenses_for_v2_id(sid)
    return LENS_DEFAULT_GAP[lenses[0]] if lenses else NO_LENS_DEFAULT_GAP


def excerpt(text: str, wanted: str) -> str:
    """A v2 brief excerpt for a heading term, through the v1→v2 alias table."""
    folded = _fold(wanted)
    if not folded:
        return ""
    sid = V2_HEADING_ALIASES.get(folded)
    if sid:
        found = section_text(text, sid)
        if found:
            return found.strip()
    model = parse_brief(text)
    for section in sorted(model.sections.values(), key=lambda s: s.start):
        if folded in _fold(section.title):
            return "\n".join(text.splitlines()[section.start:section.end]).strip()
    return ""


def _fold(value: str) -> str:
    import unicodedata

    decomposed = unicodedata.normalize("NFKD", value)
    return " ".join("".join(ch for ch in decomposed if not unicodedata.combining(ch)).lower().split())
