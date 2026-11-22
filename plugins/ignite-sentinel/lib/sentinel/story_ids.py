"""IMP-393: story ids stay stable once a workspace has changes; change stories are not the project's to touch."""
from __future__ import annotations

import re
from pathlib import Path

from .core.io import read_json
from .core.markdown import parse_frontmatter
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
            unit = next((str(t) for t in front.get("trace", []) or [] if _SPEC_UNIT.match(str(t))), "")
        if not _SPEC_UNIT.match(unit):
            unit = units_by_story.get(story_id, "")
        if _SPEC_UNIT.match(unit):
            issued.setdefault(unit, story_id)
    id_registry.seed_family(project_id, "US", issued)
