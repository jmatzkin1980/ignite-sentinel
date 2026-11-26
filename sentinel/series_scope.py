"""IMP-427 (H27 inc 7c): where the release series of a project or of a change reads its brief and writes its files.

The chain of `/split` (`split`, `split_proposal`, `release_split`, `release_series`, `release_guide`) takes
the brief text, its hash, the series folder, the folder of each release brief, the gaps file and the language
from here instead of from fixed project paths. Without a change nothing moves: the paths are the project's own.
With a change the brief is pinned: the sealed final export while it is current, else the draft the change
compiles now (`render_change_deliverable(final=False)`).
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from .workspace import workspace_path

PROJECT_BRIEF_LABEL = "02_requirements/project-brief.md"


@dataclass(frozen=True)
class SeriesScope:
    project_id: str
    change_id: str | None
    base: Path
    brief_text: str
    brief_sha256: str
    brief_label: str
    series_dir: Path
    assessment_dir: Path
    gaps_path: Path
    language: str

    def release_brief(self, rid: str) -> Path:
        return self.series_dir.parent / rid / "project-brief.md"


def series_dir(base: Path, change_id: str | None = None) -> Path:
    """The folder of the series files (and the parent of each release folder) without reading any brief."""
    return base / "02_requirements" / change_id / "series" if change_id else base / "02_requirements" / "series"


def _project_scope(project_id: str, base: Path) -> SeriesScope:
    from .core.text import project_language
    from .split import brief_hash

    brief_path = base / "02_requirements" / "project-brief.md"
    found = brief_path.is_file()
    return SeriesScope(
        project_id=project_id, change_id=None, base=base,
        brief_text=brief_path.read_text(encoding="utf-8") if found else "",
        brief_sha256=brief_hash(brief_path) if found else "",
        brief_label=PROJECT_BRIEF_LABEL,
        series_dir=series_dir(base),
        assessment_dir=base / "01_discovery",
        gaps_path=base / "01_discovery" / "gaps.md",
        language=project_language(project_id),
    )


def _change_brief(project_id: str, change_id: str, base: Path, entry: dict) -> tuple[str, str, str]:
    """(text, sha256, label): the sealed final export while it is current, else today's draft of the change."""
    from .compilers.change_deliverable import render_change_deliverable
    from .readiness_verdict import _final_export_current

    recorded = entry.get("final_export")
    if isinstance(recorded, dict) and recorded.get("path") and _final_export_current(base, change_id, entry):
        path = base / str(recorded["path"])
        if path.is_file():
            return path.read_text(encoding="utf-8"), hashlib.sha256(path.read_bytes()).hexdigest(), str(recorded["path"])
    text = render_change_deliverable(project_id, change_id, final=False)
    return text, hashlib.sha256(text.encode("utf-8")).hexdigest(), f"02_requirements/{change_id}/project-brief.md"


def series_scope(project_id: str, change_id: str | None = None) -> SeriesScope:
    """The scope of the series of the project, or of one change (an unknown change refuses like `get_change`)."""
    from .changes import change_gaps_path, resolve_scope

    base = workspace_path(project_id)
    scope = resolve_scope(project_id, change_id)  # refuses an unknown change
    if change_id is None:
        return _project_scope(project_id, base)
    text, sha, label = _change_brief(project_id, change_id, base, scope.entry)
    return SeriesScope(
        project_id=project_id, change_id=change_id, base=base, brief_text=text, brief_sha256=sha, brief_label=label,
        series_dir=series_dir(base, change_id),
        assessment_dir=base / "01_discovery" / change_id,
        gaps_path=change_gaps_path(base, change_id),
        language=scope.language,
    )
