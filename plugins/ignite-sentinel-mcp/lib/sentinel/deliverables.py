"""IMP-272: work versus deliverable.

Views and working documents may carry pending marks and placeholders: that is
how a project shows what is missing. A *deliverable* (an `/export` of the brief,
the PRD or a context request, which is what leaves for a client, a domain team or
a handoff) either has zero pending marks or says plainly that it is a draft:

- `/export` stamps a DRAFT banner (and `draft: true` in MDX metadata) when the
  source still has pending marks, and reports `deliverable: draft` with the count;
- `/export --final` refuses to export while any pending mark remains.

Gap exports (`interview`, `faq`, or `--artifact gaps`) are elicitation instruments
whose whole content is what is pending, so they are working documents by nature.

Domain packs (IMP-272): a delivered context file declares `when_to_read:` in its
frontmatter and gives each fact a single owner. `domain_pack_warnings` reports
files that do not, as non-blocking warnings.
"""
from __future__ import annotations

import re
from pathlib import Path

PENDING_RE = re.compile(r"⏳\s*(?:PENDING|PENDIENTE)|\[PENDING[^\]]*\]|\[POR COMPLETAR\]")
WORKING_ARTIFACTS = {"gaps"}
WORKING_FORMATS = {"interview", "faq"}


class DeliverableNotReady(RuntimeError):
    pass


def pending_count(text: str) -> int:
    return len(PENDING_RE.findall(text))


def banner(count: int, language: str) -> str:
    if language == "es":
        return (f"> **BORRADOR** — quedan {count} marcas pendientes: es un documento de trabajo, no un entregable. "
                "Cuando no quede ninguna, regeneralo con `/export --final`.")
    return (f"> **DRAFT** — {count} pending marks remain: this is a working document, not a deliverable. "
            "Once none remain, regenerate it with `/export --final`.")


def gate(text: str, *, artifact: str, fmt: str, final: bool) -> dict[str, object]:
    """Decide what an export is. Raises when `final` is asked for and marks remain."""
    if artifact in WORKING_ARTIFACTS or fmt in WORKING_FORMATS:
        return {"deliverable": "working", "pending_marks": pending_count(text)}
    count = pending_count(text)
    if final and count:
        raise DeliverableNotReady(
            f"/export --final refused: {count} pending marks remain in the {artifact}. "
            "Close them (or export without --final to get a marked draft).")
    return {"deliverable": "draft" if count else "final", "pending_marks": count}


def with_banner(text: str, count: int, language: str) -> str:
    """Put the draft banner right under the first heading (after a v2 marker, if any)."""
    lines = text.splitlines()
    index = next((i for i, line in enumerate(lines) if line.startswith("# ")), -1)
    stamp = ["", banner(count, language)]
    if index < 0:
        return "\n".join([banner(count, language), ""] + lines) + ("\n" if text.endswith("\n") else "")
    return "\n".join(lines[:index + 1] + stamp + lines[index + 1:]) + ("\n" if text.endswith("\n") else "")


# --- domain packs ---------------------------------------------------------------

_FRONTMATTER_RE = re.compile(r"\A---\s*\n(?P<body>.*?)\n---\s*\n", re.S)
_OWNER_RE = re.compile(r"(?im)^\s*[-*]?\s*(?:owner|dueño|responsable)\s*:\s*(?P<owners>.+)$")
_DOMAIN_FOLDERS = ("01_business_context", "02_technology_context", "03_design_context", "04_quality_context")


def domain_pack_warnings(base: Path) -> list[str]:
    """Delivered domain context files without `when_to_read` or with a shared owner on a fact."""
    warnings: list[str] = []
    for folder in _DOMAIN_FOLDERS:
        root = base / "00_raw" / folder
        if not root.exists():
            continue
        for path in sorted(root.rglob("*.md")):
            text = path.read_text(encoding="utf-8", errors="ignore")
            rel = path.relative_to(base).as_posix()
            front = _FRONTMATTER_RE.match(text)
            if not front or not re.search(r"(?m)^when_to_read\s*:\s*\S", front.group("body")):
                warnings.append(f"{rel}: no `when_to_read:` in its frontmatter; say when an agent should read it.")
            for match in _OWNER_RE.finditer(text):
                owners = [o for o in re.split(r"\s*(?:,|/|&| y | and )\s*", match.group("owners").strip()) if o]
                if len(owners) > 1:
                    warnings.append(f"{rel}: a fact has {len(owners)} owners ({match.group('owners').strip()}); give it one.")
    return warnings
