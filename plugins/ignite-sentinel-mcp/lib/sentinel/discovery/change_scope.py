"""What the adversarial channels need to work on one change instead of the project (IMP-418, H27 inc 6a).

`/annotate`, `/challenge` and `/scrutinize` run the same skeleton on a project and on a change. Only
three things differ and none had a home: the text a finding may quote, the files the run leaves
behind, and the gate that says the change is ready for a review. They live here, not in
`channels.py`, so that file does not grow with change logic.
"""
from __future__ import annotations

from pathlib import Path

from ..changes import change_gaps_path, change_language, get_change
from ..errors import GateRefusal
from ..extraction.inventory import pedido_rows, row_text
from ..source_registry import row_role
from ..sources import load_source_manifest
from ..workspace import workspace_path

_GROUNDING_ROLES = ("linea_de_base", "diseno_nuevo")


def change_grounding_text(project_id: str, change_id: str) -> str:
    """The text a finding of the change may quote verbatim (H27 inc 6a, decision 16).

    The request (every current row, read whatever its format), the change's answers, its brief,
    the current baseline and new-design rows and the harvest readings. The project's domain
    context is not here: it belongs to the project.
    """
    change = get_change(project_id, change_id)
    base = workspace_path(project_id)
    parts: list[str] = [text for row in pedido_rows(project_id, change_id) if (text := row_text(base, row))]
    for rel in change.get("responses", []) or []:
        path = Path(rel)
        path = path if path.is_absolute() else base / path
        if path.is_file():
            parts.append(path.read_text(encoding="utf-8"))
    brief = base / "02_requirements" / change_id / "project-brief.md"
    if brief.is_file():
        parts.append(brief.read_text(encoding="utf-8"))
    registry = {str(row.get("id")): row for row in load_source_manifest(project_id).get("registry", [])}
    wanted = [str(i) for i in change.get("sources", []) or []]
    for source_id in wanted:
        row = registry.get(source_id)
        if row and row.get("validity", "current") == "current" and row_role(row) in _GROUNDING_ROLES:
            if text := row_text(base, row):
                parts.append(text)
    for source_id in [str(i) for i in change.get("harvests", []) or []]:
        row = registry.get(source_id)
        if row and source_id not in wanted and (text := row_text(base, row)):
            parts.append(text)
    return "\n\n".join(parts)


def change_channel_paths(base: Path, change_id: str) -> dict[str, Path]:
    """Where a run of an adversarial channel leaves its files, under `01_discovery/<CHG>/`."""
    folder = base / "01_discovery" / change_id
    return {
        "gaps": change_gaps_path(base, change_id),
        "challenge_report": folder / "challenge_report.md",
        "scrutiny_report": folder / "scrutiny_report.md",
        "annotation_log": folder / "agent_annotation_log.md",
        "annotations": folder / "annotations",
        "challenges": folder / "challenges",
        "scrutiny": folder / "scrutiny",
        "sweep_log": folder / "agent_sweep_log.md",
    }


def change_channel_gate(project_id: str, change_id: str, command: str) -> tuple[dict, Path, str]:
    """`(change, gaps_path, language)`, or the refusal that says what the change still lacks."""
    change = get_change(project_id, change_id)
    language = change_language(project_id, change)
    es = language == "es"
    base = workspace_path(project_id)
    gaps_path = change_gaps_path(base, change_id)
    if not gaps_path.is_file():
        raise GateRefusal(
            f"{change_id} todavía no tiene archivo de gaps" if es else f"{change_id} has no gaps file yet",
            next_step=f"/gaps {project_id} --change {change_id}",
        )
    if not change_grounding_text(project_id, change_id).strip():
        raise GateRefusal(
            f"{change_id} no tiene texto del pedido para fundamentar /{command}" if es
            else f"{change_id} has no request text to ground /{command} against",
            next_step=f"/ingest {project_id} --source NOTA --change" if es else f"/ingest {project_id} --source NOTE --change",
        )
    return change, gaps_path, language
