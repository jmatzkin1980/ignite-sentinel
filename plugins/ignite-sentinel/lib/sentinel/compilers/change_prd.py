"""IMP-414 (H27 inc 5a) task 6: the PRD of a change, `03_specs/CHG-nnn/prd.md`.

The project PRD reads `02_requirements/project-brief.md`, `00_raw/` and the project's assumption register. This adapter
hands `render_prd_full` the data of the change instead (the consolidated final text, its EARS rows, its closed decisions,
its excluded elements and its open assumptions), so the PRD of a change has the sections, tables, glossary and governance
of the project PRD without touching the project's output.
"""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from typing import Any

from ..assumptions import escape_table
from ..change_assumptions import open_change_assumptions
from ..change_requirements import load_change_ears
from ..changes import change_language, get_change
from ..core.io import write_text
from ..workspace import workspace_path
from .prd import render_prd_full

PENDING = {"es": "sin dato registrado", "en": "no data recorded"}


def _final_file(project_id: str, change_id: str) -> Path | None:
    """The file of the change's current final export, or None (the milestone of `/export --final`)."""
    from ..readiness_verdict import _final_export_current

    base = workspace_path(project_id)
    change = get_change(project_id, change_id)
    if not _final_export_current(base, change_id, change):
        return None
    path = base / str((change.get("final_export") or {}).get("path", ""))
    return path if path.is_file() else None


def final_source_sha(project_id: str, change_id: str) -> str:
    """16 hex of the final export file the change records ("" when there is none)."""
    recorded = get_change(project_id, change_id).get("final_export")
    name = str(recorded.get("path", "")) if isinstance(recorded, dict) else ""
    path = workspace_path(project_id) / name
    if not name or not path.is_file():
        return ""
    return sha256(path.read_bytes()).hexdigest()[:16]


def change_prd_context(project_id: str, change_id: str) -> dict:
    from ..consolidation_control import consolidation_control
    from ..decision_memory import closed_decisions
    from ..extraction.coverage import extraction_view

    final = _final_file(project_id, change_id)
    raw_text = final.read_text(encoding="utf-8-sig") if final else ""
    gap_answers: dict[str, dict[str, str]] = {}
    for decision in closed_decisions(project_id, change_id):
        answer = str(decision.get("answer", "")).strip()
        if answer:
            sources = decision.get("sources") or []
            gap_answers[str(decision["id"])] = {"statement": answer, "source": str(sources[0]) if sources else ""}
    source_of = {str(e["id"]): str(e.get("source_id", "")) for e in extraction_view(project_id, change_id).get("elements", [])}
    non_goals = []
    for row in consolidation_control(project_id, change_id)["rows"]:
        if row["status"] != "excluido":
            continue
        non_goals.append({
            "gap_id": str(row["gaps"][0]) if row["gaps"] else "",
            "statement": f"{row['element']} — {row['reason']}".rstrip(" —"),
            "source": source_of.get(str(row["element"]), ""),
        })
    return {
        "raw_text": raw_text,
        "ears_requirements": [{k: row[k] for k in ("id", "pattern", "statement", "source", "delta")}
                              for row in load_change_ears(project_id, change_id)],
        "gap_answers": gap_answers,
        "non_goals": non_goals,
        "prd_sections": {},
    }


def change_assumption_rows(project_id: str, change_id: str) -> str:
    """The governed rows of the open assumptions of the change ("" when there are none)."""
    return "\n".join(
        f"| `{row['id']}` | {escape_table(row['statement'])} | {row['risk']} | {escape_table(row['owner'])} "
        f"| {escape_table(row['justification'])} | `{row.get('gap') or row.get('closes_gap') or 'N/A'}` "
        f"| {row.get('status', 'ASSUMED')} |"
        for row in open_change_assumptions(project_id, change_id)
    )


def render_change_prd(project_id: str, change_id: str) -> str | None:
    """None without a current final export; else the PRD in the change's language."""
    if _final_file(project_id, change_id) is None:
        return None
    language = "en" if change_language(project_id, get_change(project_id, change_id)) == "en" else "es"
    context = change_prd_context(project_id, change_id)
    text = render_prd_full(
        project_id, context["raw_text"], context, f"{change_id}/project-brief.md", language,
        pending=PENDING[language], assumption_rows=change_assumption_rows(project_id, change_id),
        source_path=f"02_requirements/{change_id}/",
    )
    _first, _, rest = text.partition("\n")
    return f"# PRD - {project_id} / {change_id}\n{rest}"


def write_change_prd(project_id: str, change_id: str) -> dict[str, Any]:
    text = render_change_prd(project_id, change_id)
    if text is None:
        return {"skipped": f"/export {project_id} --artifact brief --change {change_id} --final"}
    path = workspace_path(project_id) / "03_specs" / change_id / "prd.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    write_text(path, text)
    return {"path": path.relative_to(workspace_path(project_id)).as_posix(),
            "source_sha": final_source_sha(project_id, change_id)}
