"""IMP-388: the EARS requirements of a change, with the BA-declared Delta, in the change's own file."""
from __future__ import annotations

import re
from pathlib import Path

from .core.graph import add_edge, add_node
from .core.io import append_text, write_text
from .workspace import workspace_path

DELTA_VALUES = ("ADDED", "MODIFIED", "REMOVED", "UNCHANGED")
_UNCHANGED_HINT = re.compile(r"\b(continue to|continuar\w*|seguir\w*|sigue)\b", re.I)
_EARS_ID = re.compile(r"REQ-EARS-(\d+)")
_ESCAPED_PIPE = "\\|"
_CELL_SPLIT = re.compile(r"(?<!\\)\|")
_SOURCE = re.compile(r"`([^`]+)`")


def parse_delta(value: str) -> str | None:
    """One of the four deltas (any case), or None when missing or anything else (no aliases)."""
    candidate = str(value or "").strip().strip("`").strip().upper()
    return candidate if candidate in DELTA_VALUES else None


def propose_delta(statement: str) -> str:
    """A proposal only; the BA declares the delta."""
    return "UNCHANGED" if _UNCHANGED_HINT.search(statement) else "ADDED"


def change_requirements_path(base: Path, change_id: str) -> Path:
    return base / "02_requirements" / change_id / "requirements.md"


def next_ears_index(base: Path) -> int:
    """The next REQ-EARS number: one past the highest in the project file and every change file."""
    requirements = base / "02_requirements"
    files = [requirements / "requirements.md", *sorted(requirements.glob("CHG-*/requirements.md"))]
    highest = 0
    for path in files:
        if path.is_file():
            numbers = [int(n) for n in _EARS_ID.findall(path.read_text(encoding="utf-8"))]
            highest = max([highest, *numbers])
    return highest + 1


def _cell(text: str) -> str:
    return " ".join(str(text).split()).replace("|", _ESCAPED_PIPE)


def load_change_ears(project_id: str, change_id: str) -> list[dict]:
    path = change_requirements_path(workspace_path(project_id), change_id)
    if not path.is_file():
        return []
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("| REQ-EARS-"):
            continue
        cells = [cell.strip() for cell in _CELL_SPLIT.split(line.strip().strip("|"))]
        if len(cells) < 5:
            continue
        rows.append({
            "id": cells[0], "pattern": cells[1], "delta": cells[2],
            "statement": cells[3].replace(_ESCAPED_PIPE, "|"), "source": cells[4],
        })
    return rows


def materialize_change_ears(project_id: str, change_id: str, closed: list[dict], responses: dict,
                            language: str = "es", record_id: str | None = None) -> list[str]:
    """Write a REQ-EARS row per EARS statement of each closed answer; a (gap, statement) already there adds nothing."""
    from .gap_resolution import ears_statements

    base = workspace_path(project_id)
    path = change_requirements_path(base, change_id)
    seen: set[tuple[str, str]] = set()
    for row in load_change_ears(project_id, change_id):
        gap = _SOURCE.search(row["source"])
        seen.add((gap.group(1) if gap else "", _cell(row["statement"])))
    candidates: list[tuple[dict, str, str, str]] = []
    for gap in closed:
        delta = parse_delta(str(responses.get(gap["id"], {}).get("delta", "")))
        if not delta:
            continue
        for statement, pattern in ears_statements((gap.get("answer") or "").strip()):
            key = (gap["id"], _cell(statement))
            if key in seen:
                continue
            seen.add(key)
            candidates.append((gap, statement, pattern, delta))
    if not candidates:
        return []
    lines: list[str] = []
    if not path.exists():
        title = f"# Requisitos del cambio {change_id}" if language == "es" else f"# Change requirements {change_id}"
        path.parent.mkdir(parents=True, exist_ok=True)
        write_text(path, "\n".join([
            title, "", "## Normalized Requirements (EARS)", "",
            "| ID | Pattern | Delta | Statement | Source |", "| --- | --- | --- | --- | --- |", "",
        ]))
    index = next_ears_index(base)
    node_ids: list[str] = []
    for offset, (gap, statement, pattern, delta) in enumerate(candidates):
        req_id = f"REQ-EARS-{index + offset:03d}"
        lines.append(f"| {req_id} | {pattern} | {delta} | {_cell(statement)} | `{gap['id']}` / `{change_id}` |")
        node_id = add_node(
            project_id, "REQ", "ears_requirement", path, f"{req_id} ({pattern}, {delta}) from {gap['id']}",
            status="confirmed", domain=gap.get("lens", "product"),
        )
        if record_id:
            add_edge(project_id, record_id, node_id, "normalizes")
        node_ids.append(req_id)
    append_text(path, "\n".join(lines) + "\n")
    return node_ids
