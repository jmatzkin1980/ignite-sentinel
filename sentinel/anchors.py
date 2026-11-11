"""IMP-258: anchors that hold (deterministic part).

`/validate` already resolves each `[[doc § section # ID]]` citation (IMP-249). An
anchor can still fail to hold what it is attached to. For a brief v2 this module
reports, per line of the body:

- **unanchored:** a statement with no citation, outside the closed list of what is
  exempt (`templates/anchor_exempt.json`);
- **unresolved:** a `sources` citation whose F-NN row is not in the registry;
- **stale_source:** the cited source is superseded, retired or expired;
- **echo:** the cited source is an artifact Sentinel itself wrote (IMP-251), so it
  adds no facts;
- **two_subjects:** the line speaks of two gaps (A and B) but its anchors only hold
  one of them. One anchor per subject: split the line.

It also counts the sites: "n of n anchors hold". The agentic judgment (does the
cited passage say less, or the opposite?) is a `sentinel-scrutiny` mode in H16c.
"""
from __future__ import annotations

import re
from typing import Any

from .brief_model import V2_PENDING_RE, parse_brief
from .citations import CITATION_RE, parse_citations
from .resources import read_package_json

GAP_IN_PROSE_RE = re.compile(r"`(GAP-[A-Z0-9-]+)`")
GAP_IN_SUPPORTS_RE = re.compile(r"GAP-[A-Z0-9-]+")
STALE_VALIDITY = {"superseded", "retired", "expired"}


def exempt_data() -> dict[str, Any]:
    return read_package_json("templates/anchor_exempt.json")


def _line_kind(line: str) -> str | None:
    """The exempt kind of a line, or None when it states something."""
    stripped = line.strip()
    if not stripped or stripped.startswith("<!--"):
        return "blank"
    if stripped.startswith("#"):
        return "heading"
    if stripped.startswith("|"):
        return "table"
    body = stripped[2:].strip() if stripped.startswith("- ") else stripped
    if body.startswith("N/A"):
        return "na"
    if body.startswith("→"):
        return "reference"
    if re.match(r"\((inferred|inferido)\)", body):
        return "inferred"
    if V2_PENDING_RE.match(body) or body.startswith("⏳"):
        return "pending"
    if "OUT OF SCOPE" in body or "FUERA DE ALCANCE" in body:
        return "out_of_scope"
    if any(body.startswith(prefix) for prefix in exempt_data().get("verdict_prefixes", [])):
        return "verdict"
    return None


def anchor_report(text: str, registry: list[dict[str, Any]]) -> dict[str, Any]:
    """Structured findings ({code, place, line, detail}) and the site count of a v2 brief."""
    model = parse_brief(text)
    if model.version != 2:
        return {"findings": [], "sites": 0, "holding": 0}
    rows = {str(row.get("id")): row for row in registry if isinstance(row, dict)}
    exempt_places = set(exempt_data()["places"])
    findings: list[dict[str, Any]] = []
    sites = holding = 0
    for number, line in enumerate(text.splitlines(), start=1):
        place = model.section_id_at_line(number)
        if not place or place in exempt_places or place.split(".")[0] == "0":
            continue
        if _line_kind(line) is not None:
            continue
        citations = [c for c in parse_citations(line)]
        if not citations:
            findings.append({"code": "unanchored", "place": place, "line": number,
                             "detail": "states something with no citation of its source"})
            continue
        for citation in citations:
            sites += 1
            problem = None
            if citation.doc == "sources":
                row = rows.get(citation.id)
                if row is None:
                    problem = ("unresolved", f"{citation.id} is not in the source registry")
                elif str(row.get("validity", "current")) in STALE_VALIDITY:
                    problem = ("stale_source", f"{citation.id} is {row.get('validity')}; cite what replaced it")
                elif str(row.get("authority") or "") == "own_artifact":
                    problem = ("echo", f"{citation.id} is an artifact Sentinel wrote; it adds no facts")
            if problem:
                findings.append({"code": problem[0], "place": place, "line": number, "detail": problem[1]})
            else:
                holding += 1
        prose = CITATION_RE.sub("", line)
        subjects = set(GAP_IN_PROSE_RE.findall(prose))
        held = {gap for c in citations for gap in GAP_IN_SUPPORTS_RE.findall(c.supports)}
        if len(subjects) > 1 and subjects - held:
            findings.append({"code": "two_subjects", "place": place, "line": number,
                             "detail": f"speaks of {', '.join(sorted(subjects))} but its anchors hold "
                                       f"{', '.join(sorted(held)) or 'none of them'}; one anchor per subject"})
    return {"findings": findings, "sites": sites, "holding": holding}


def anchor_findings(text: str, registry: list[dict[str, Any]]) -> list[str]:
    return [f"brief v2 §{f['place']} line {f['line']}: anchor {f['code']}: {f['detail']}."
            for f in anchor_report(text, registry)["findings"]]
