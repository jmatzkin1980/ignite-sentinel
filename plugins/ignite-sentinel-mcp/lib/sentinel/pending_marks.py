"""IMP-334: one way to count the pending marks of an artifact.

`/validate` (semantic quality) and `/export` (the deliverable gate) both count
pending marks with `count_pending_marks`, so they report the same number for the
same artifact.

The rule:

- **Brief v2** (marker `<!-- sentinel-artifact: v2 -->`). A mark is
  `⏳ PENDING (GAP-X)` / `⏳ PENDIENTE (GAP-X)` (the client owes it: it *blocks*)
  or `⏳ PENDING DOMAIN (GAP-X)` / `⏳ PENDIENTE DOMINIO (GAP-X)` (domain context
  owes it: it is *deferred*) or `⏳ PENDING EXTRACTION` / `⏳ PENDIENTE DE EXTRACCIÓN`
  (IMP-398: the request covers the topic and a later extraction owes it: *deferred* too). When the compile report
  (`02_requirements/brief_compile_report.json`) is available its `fill_sites` are
  the count, one per place, by class: that is the number the brief's own
  "Ready to build" line states. Without the report the body is read, leaving out
  what names or indexes the marks rather than being one: the §0.1 legend, table
  rows (the §0.2 certainty table, the §7.2 seeded-marks table) and fenced code.
- **Any other artifact** (v1 brief, PRD, context request): every
  `[PENDING …]`, `[POR COMPLETAR]` and `⏳ PENDING`/`PENDIENTE` blocks.

`blocking` is the count a deliverable must bring to zero; `deferred` is reported
alongside and does not block (the brief says so in its legend).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

V1_MARK_RE = re.compile(r"⏳\s*(?:PENDING|PENDIENTE)|\[PENDING[^\]]*\]|\[POR COMPLETAR\]")
REPORT_NAME = "brief_compile_report.json"


@dataclass(frozen=True)
class PendingMarks:
    blocking: int
    deferred: int = 0
    source: str = "text"  # "text" or "compile_report"

    @property
    def total(self) -> int:
        return self.blocking + self.deferred


def count_pending_marks(text: str, report: dict[str, Any] | None = None) -> PendingMarks:
    """The pending marks of an artifact's text (and, for a brief v2, its compile report)."""
    from .citations import is_v2_artifact

    if not is_v2_artifact(text):
        return PendingMarks(len(V1_MARK_RE.findall(text)))
    sites = report.get("fill_sites") if isinstance(report, dict) else None
    if isinstance(sites, list):
        deferred = sum(1 for site in sites if isinstance(site, dict) and site.get("class") == "domain")
        return PendingMarks(len(sites) - deferred, deferred, "compile_report")
    return _count_v2_text(text)


def _count_v2_text(text: str) -> PendingMarks:
    from .brief_model import V2_PENDING_RE, is_deferred_mark, parse_brief

    model = parse_brief(text)
    blocking = deferred = 0
    fenced = False
    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if line.startswith("```"):
            fenced = not fenced
            continue
        if fenced or line.startswith("|"):
            continue  # tables index the marks; they are not marks
        if model.section_id_at_line(number).startswith("0.1"):
            continue  # the legend names the vocabulary, it does not use it
        for match in V2_PENDING_RE.finditer(line):
            if is_deferred_mark(match.group("domain")):
                deferred += 1
            else:
                blocking += 1
    return PendingMarks(blocking, deferred)


def compile_report_for(source: Path) -> dict[str, Any] | None:
    """The brief v2 compile report next to `source`, when `source` is the project brief."""
    from .core.io import read_json

    if source.name != "project-brief.md":
        return None
    path = source.parent / REPORT_NAME
    report = read_json(path, None) if path.exists() else None
    return report if isinstance(report, dict) else None
