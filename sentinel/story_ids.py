"""IMP-393: story ids stay stable once a workspace has changes; change stories are not the project's to touch."""
from __future__ import annotations

import re
from pathlib import Path

from .core.io import read_json
from .core.markdown import frontmatter_bounds, parse_frontmatter
from . import id_registry

_SPEC_UNIT = re.compile(r"^SPEC-U-\d{3}$")
_HEADING = re.compile(r"^#\s+\S+\s+-\s+(.+?)\s*$", re.MULTILINE)


def is_change_story(path: Path) -> bool:
    """A story written by a change (`change:` in its frontmatter), not by the project /backlog."""
    try:
        front = parse_frontmatter(path.read_text(encoding="utf-8"))
    except OSError:
        return False
    return bool(str(front.get("change", "")).strip())


def enabler_key(title: str) -> str:
    return f"ENABLER:{title.strip()}"


def ensure_story_ids_seeded(project_id: str, base: Path) -> None:
    """Seed the US family from the stories on disk, once, before any id is assigned."""
    if id_registry.family_seeded(project_id, "US"):
        return
    readiness = read_json(base / "08_context_packs" / "implementation_readiness.json", {})
    units_by_story = {
        str(item.get("story_id", "")): str(item.get("source_unit", ""))
        for item in (readiness.get("stories", []) if isinstance(readiness, dict) else [])
        if isinstance(item, dict)
    }
    issued: dict[str, str] = {}
    for path in sorted((base / "04_backlog").glob("US-*.md")):
        text = path.read_text(encoding="utf-8")
        front = parse_frontmatter(text)
        story_id = str(front.get("id", path.stem)).strip() or path.stem
        if str(front.get("type", "")).strip() == "cross_cutting_enabler":
            match = _HEADING.search(text)
            if match:
                issued.setdefault(enabler_key(match.group(1)), story_id)
            continue
        unit = str(front.get("source_unit", "")).strip()
        if not _SPEC_UNIT.match(unit):
            unit = units_by_story.get(story_id, "")
        if not _SPEC_UNIT.match(unit):
            unit = next((str(t) for t in front.get("trace", []) or [] if _SPEC_UNIT.match(str(t))), "")
        if _SPEC_UNIT.match(unit):
            issued.setdefault(unit, story_id)
    id_registry.seed_family(project_id, "US", issued)


def with_modificada_por(text: str, ids: list[str]) -> str:
    """The story's text with `modificada_por` set to `ids` (removed when empty); nothing else changes."""
    bounds = frontmatter_bounds(text)
    if bounds is None:
        return text
    start, end = bounds
    out: list[str] = []
    skipping = False
    for line in text[start:end].split("\n"):
        if line.startswith("modificada_por:"):
            skipping = True
            continue
        if skipping and line.startswith("  - "):
            continue
        skipping = False
        out.append(line)
    if ids:
        out += ["modificada_por:", *[f"  - {sid}" for sid in ids]]
    return text[:start] + "\n".join(out) + text[end:]


def carry_modificada_por(path: Path, rendered: str) -> str:
    """IMP-393: a project story re-rendered by /backlog keeps the `modificada_por` its file already had
    (the change stories that modify it). A story without that key renders byte-identical."""
    try:
        current = parse_frontmatter(path.read_text(encoding="utf-8")).get("modificada_por", [])
    except OSError:
        return rendered
    ids = [str(i) for i in current] if isinstance(current, list) else ([str(current)] if current else [])
    return with_modificada_por(rendered, ids) if ids else rendered
