"""IMP-255: integrity of the brief v2 marks, forbidden values and residues.

Only a v2 brief (marker `<!-- sentinel-artifact: v2 -->`) is checked; a v1 brief is
left exactly as before. `/validate` adds these findings:

- **Marks:** every `⏳` points to a gap that exists in `gaps.md` and is still open
  (a closed gap leaves no live mark); every inline `⚠` points to an open
  contradiction gap.
- **Report:** the compile report's `fill_sites` match the marks in the body, place
  by place, and every `(inferred)` line has its `INFERRED` unit in the knowledge
  ledger.
- **Forbidden values,** as a value and not as a word: an empty cell, `-`, `—`,
  a bare `N/A` without its reason, the brief's own `TBD`, `ninguno`. An explicit
  `nada`, `ninguna` or `none` is allowed.
- **Residues:** chronology with the document as its subject and edit stamps
  ("last updated", "antes decía", "[edit]"...). A brief states what is meant now.

Lines that carry a `[[…]]` citation are quotes of a source and are not checked for
values or residues: a source may say TBD, and the brief transcribes it.
"""
from __future__ import annotations

import re
from collections import Counter
from pathlib import Path
from typing import Any

from .brief_model import V2_PENDING_RE, parse_brief
from .core.io import read_json

DIVERGENCE_RE = re.compile(r"^- ⚠ .*\(`(?P<gap>GAP-[A-Z0-9-]+)`\)")
INFERRED_RE = re.compile(r"^- \((?:inferred|inferido)\) .*\(`(?P<asm>ASM-[A-Z0-9-]+)`\)\s*$")
FORBIDDEN_VALUES = {"", "-", "—", "–", "n/a", "tbd", "tbc", "ninguno"}
OWN_TBD_RE = re.compile(r"(?<![\w-])(TBD|TBC)(?![\w-])")
RESIDUE_PATTERNS = [
    re.compile(p, re.I) for p in (
        r"\b(last updated|updated on|última actualización|actualizado el|modificado el|edited on|editado el)\b",
        r"\b(antes dec[ií]a|previously said|used to say|was changed to|se cambi[oó] a)\b",
        r"\[(edit|editado|edited)\b|\((edit|editado)\s*:",
        r"\b(this|the|este|el)\s+(document|brief|documento)\s+(was|fue)\s+(updated|modified|revised|actualizado|modificado|revisado)\b",
        r"\b(in the previous version|en la versi[oó]n anterior)\b",
    )
]


def _gap_rows(base: Path) -> dict[str, dict[str, str]]:
    from .discovery import parse_gap_rows

    path = base / "01_discovery" / "gaps.md"
    if not path.exists():
        return {}
    return {row.get("id", "").strip("`"): row for row in parse_gap_rows(path.read_text(encoding="utf-8"))}


def _is_open(row: dict[str, str] | None) -> bool:
    return row is not None and str(row.get("status", "")).upper() != "CLOSED"


def mark_findings(text: str, gaps: dict[str, dict[str, str]]) -> list[str]:
    model = parse_brief(text)
    findings: list[str] = []
    for number, line in enumerate(text.splitlines(), start=1):
        place = model.section_id_at_line(number) or "?"
        for match in V2_PENDING_RE.finditer(line):
            gap = (match.group("gap") or "").strip()
            if not gap:
                findings.append(f"brief v2 §{place}: a pending mark names no gap.")
            elif gap not in gaps:
                findings.append(f"brief v2 §{place}: the mark points to {gap}, which is not in gaps.md.")
            elif not _is_open(gaps[gap]):
                findings.append(f"brief v2 §{place}: {gap} is closed but its mark is still live.")
        divergence = DIVERGENCE_RE.match(line)
        if divergence:
            row = gaps.get(divergence.group("gap"))
            if not _is_open(row) or str((row or {}).get("origin", "")).strip("`") != "contradiction":
                findings.append(f"brief v2 §{place}: ⚠ points to {divergence.group('gap')}, which is not an open divergence.")
    return findings


def report_findings(text: str, report: dict[str, Any] | None, ledger: dict[str, Any] | None) -> list[str]:
    model = parse_brief(text)
    findings: list[str] = []
    marks: Counter[tuple[str, str]] = Counter()
    inferred: list[tuple[str, str]] = []
    for number, line in enumerate(text.splitlines(), start=1):
        place = model.section_id_at_line(number)
        for match in V2_PENDING_RE.finditer(line):
            marks[(place, (match.group("gap") or "").strip())] += 1
        found = INFERRED_RE.match(line)
        if found:
            inferred.append((place, found.group("asm")))
    if report is None:
        return ["brief v2: 02_requirements/brief_compile_report.json is missing; recompile with /brief."] if marks else []
    sites: Counter[tuple[str, str]] = Counter(
        (str(site.get("id", "")).split("/")[0], str(site.get("gap", ""))) for site in report.get("fill_sites", []))
    for (place, gap), count in sorted((marks - sites).items()):
        findings.append(f"brief v2 §{place}: mark for {gap} has no fill site in the compile report ({count}).")
    for (place, gap), count in sorted((sites - marks).items()):
        findings.append(f"brief v2 §{place}: fill site for {gap} has no mark in the body ({count}).")
    units = ledger.get("units", []) if isinstance(ledger, dict) else []
    rows = set()
    for unit in units:
        if not isinstance(unit, dict) or unit.get("status") != "INFERRED":
            continue
        links = {link.get("type"): link.get("target") for link in unit.get("links", []) if isinstance(link, dict)}
        rows.add((links.get("brief_place"), links.get("assumption")))
    for place, asm in inferred:
        if (place, asm) not in rows:
            findings.append(f"brief v2 §{place}: the inference from {asm} has no INFERRED row in the knowledge ledger.")
    return findings


def _value_of(line: str) -> str | None:
    """The value a list item states (after `Key:` when there is one), or None."""
    if not line.startswith("- "):
        return None
    item = line[2:].strip()
    if re.match(r"^[^:`]{1,40}:\s", item) or item.endswith(":"):
        return item.split(":", 1)[1].strip()
    return item


def value_findings(text: str) -> list[str]:
    model = parse_brief(text)
    findings: list[str] = []
    fenced = False
    lines = text.splitlines()
    separator = re.compile(r"\|(\s*:?-+:?\s*\|)+")
    for number, raw in enumerate(lines, start=1):
        line = raw.strip()
        if line.startswith("```"):
            fenced = not fenced
        if fenced or not line or line.startswith("#") or line.startswith("<!--") or "[[" in line:
            continue
        place = model.section_id_at_line(number) or "?"
        if place.startswith("0.1"):
            continue  # the legend names the vocabulary, it does not use it
        if line.startswith("|"):
            header = number < len(lines) and separator.fullmatch(lines[number].strip()) is not None
            if separator.fullmatch(line) or header:
                continue  # separators and header rows name columns, they hold no values
            for cell in line.strip("|").split("|"):
                if cell.strip().lower() in FORBIDDEN_VALUES:
                    findings.append(f"brief v2 §{place}: a table cell holds a forbidden value ({cell.strip() or 'empty'!r}).")
                    break
        else:
            value = _value_of(line)
            if value is not None and value.lower().rstrip(".") in FORBIDDEN_VALUES:
                findings.append(f"brief v2 §{place}: forbidden value {value or 'empty'!r}; say what is missing or why it does not apply.")
            elif re.fullmatch(r"N/A\.?", line) or (line.startswith("N/A") and " — " not in line):
                findings.append(f"brief v2 §{place}: N/A without its reason and counterfactual.")
        if not line.startswith("|") and OWN_TBD_RE.search(line):
            findings.append(f"brief v2 §{place}: the brief's own TBD; use a pending mark with its gap.")
        for pattern in RESIDUE_PATTERNS:
            if pattern.search(line):
                findings.append(f"brief v2 §{place}: edit residue ({pattern.search(line).group(0)!r}); state what is meant now.")
                break
    return findings


def brief_v2_integrity_findings(base: Path) -> list[str]:
    brief = base / "02_requirements" / "project-brief.md"
    if not brief.exists():
        return []
    text = brief.read_text(encoding="utf-8")
    if parse_brief(text).version != 2:
        return []
    report_path = base / "02_requirements" / "brief_compile_report.json"
    report = read_json(report_path, None) if report_path.exists() else None
    ledger = read_json(base / "01_discovery" / "knowledge_state.json", {})
    from .anchors import anchor_findings  # IMP-258: anchors that hold

    manifest = read_json(base / "00_raw" / "source_manifest.json", {}) or {}
    registry = manifest.get("registry", []) if isinstance(manifest, dict) else []
    return (mark_findings(text, _gap_rows(base)) + report_findings(text, report, ledger) + value_findings(text)
            + anchor_findings(text, registry))


# --- /doctor: the marker and the mark vocabulary in skills and mirrors -------------------------

MARKER_LIKE_RE = re.compile(r"<!--\s*sentinel-artifact\s*:?\s*v2\s*-->", re.I)
MARK_LIKE_RE = re.compile(r"⏳(\s*)(PENDING|PENDIENTE)(\s+(?:DOMAIN|DOMINIO))?", re.I)


def vocabulary_problems(text: str, canonical_marker: str) -> list[str]:
    problems = [f"marker variant {m.group(0)!r}" for m in MARKER_LIKE_RE.finditer(text) if m.group(0) != canonical_marker]
    for match in MARK_LIKE_RE.finditer(text):
        word = match.group(2) + (match.group(3) or "")
        if match.group(1) != " " or word != word.upper() or (match.group(3) and match.group(3) != " " + match.group(3).strip()):
            problems.append(f"mark variant {match.group(0)!r}")
    return problems


def skill_vocabulary_problems(root: Path) -> list[str]:
    from .ids import id_registry

    canonical = id_registry()["v2_marker"]
    problems: list[str] = []
    patterns = (".codex/skills/*/SKILL.md", ".claude/skills/*/SKILL.md", ".agents/skills/*/SKILL.md",
                "plugins/*/skills/*/SKILL.md", ".claude/commands/*.md")
    for pattern in patterns:
        for path in sorted(root.glob(pattern)):
            for problem in vocabulary_problems(path.read_text(encoding="utf-8"), canonical):
                problems.append(f"{path.relative_to(root).as_posix()}: {problem}")
    return problems
