"""IMP-388: the EARS requirements of a change, with the BA-declared Delta, in the change's own file."""
from __future__ import annotations

import re
from pathlib import Path

from .core.graph import add_edge, add_node
from .core.io import write_text
from .workspace import workspace_path

DELTA_VALUES = ("ADDED", "MODIFIED", "REMOVED", "UNCHANGED")
_UNCHANGED_HINT = re.compile(
    r"\b(continue to|continuar\w*|seguir\w*|sigue|keep\w*|still|manten\w*|mantien\w*)\b", re.I
)
SUPERSEDED_HEADINGS = ("## Superseded requirements", "## Requisitos reemplazados")
TABLE_HEADER = ["| ID | Pattern | Delta | Statement | Source |", "| --- | --- | --- | --- | --- |"]
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
    superseded = False
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            superseded = line.strip() in SUPERSEDED_HEADINGS
        if superseded or not line.startswith("| REQ-EARS-"):
            continue
        cells = [cell.strip() for cell in _CELL_SPLIT.split(line.strip().strip("|"))]
        if len(cells) < 5:
            continue
        rows.append({
            "id": cells[0], "pattern": cells[1], "delta": cells[2],
            "statement": cells[3].replace(_ESCAPED_PIPE, "|"), "source": cells[4],
        })
    return rows


def _row_cells(line: str) -> list[str]:
    return [cell.strip() for cell in _CELL_SPLIT.split(line.strip().strip("|"))]


def _row_gap(line: str) -> str:
    cells = _row_cells(line)
    found = _SOURCE.search(cells[4]) if len(cells) >= 5 else None
    return found.group(1) if found else ""


def _split_file(text: str) -> tuple[list[str], list[str], list[str]]:
    """(head lines, active row lines, superseded row lines) of a change requirements file."""
    head: list[str] = []
    active: list[str] = []
    old: list[str] = []
    in_old = False
    for line in text.splitlines():
        if line.startswith("## "):
            in_old = line.strip() in SUPERSEDED_HEADINGS
        if line.startswith("| REQ-EARS-"):
            (old if in_old else active).append(line)
        elif not line.startswith("| ID |") and not line.startswith("| ---") and not in_old:
            head.append(line)
    return head, active, old


def reconcile_change_ears(project_id: str, change_id: str, closed: list[dict], responses: dict,
                          language: str = "es", record_id: str | None = None) -> dict[str, list[str]]:
    """Reconcile the REQ-EARS rows of each (re)closed answer of a change.

    A row whose (gap, statement) is still produced keeps its id and takes the declared Delta in place;
    a statement no longer produced moves to the Superseded table (its id is never reused); a new one
    takes the next id. GAP-SCOPE (the border) is exempt.
    """
    from .gap_resolution import ears_statements

    base = workspace_path(project_id)
    path = change_requirements_path(base, change_id)
    result: dict[str, list[str]] = {"added": [], "delta_updated": [], "superseded": []}
    exists = path.is_file()
    original = path.read_text(encoding="utf-8") if exists else ""
    head, active, old = _split_file(original) if exists else ([], [], [])
    next_index = next_ears_index(base)
    new_rows: list[tuple[str, dict, str, str, str]] = []
    for gap in closed:
        if gap["id"] == "GAP-SCOPE":
            continue
        answer = (gap.get("answer") or "").strip()
        statements = ears_statements(answer)
        delta = parse_delta(str(responses.get(gap["id"], {}).get("delta", "")))
        if statements and not delta:
            continue
        produced: dict[str, tuple[str, str]] = {}
        for statement, pattern in statements:
            produced.setdefault(_cell(statement), (statement, pattern))
        matched: set[str] = set()
        for position, line in enumerate(active):
            if _row_gap(line) != gap["id"]:
                continue
            cells = _row_cells(line)
            key = _cell(cells[3].replace(_ESCAPED_PIPE, "|"))
            if key in produced and key not in matched:
                matched.add(key)
                if cells[2] != delta:
                    cells[2] = delta or cells[2]
                    active[position] = "| " + " | ".join(cells) + " |"
                    result["delta_updated"].append(cells[0])
            else:
                active[position] = ""
                old.append(line)
                result["superseded"].append(cells[0])
        for key, (statement, pattern) in produced.items():
            if key not in matched:
                new_rows.append((f"REQ-EARS-{next_index:03d}", gap, statement, pattern, str(delta)))
                next_index += 1
    active = [line for line in active if line]
    for req_id, gap, statement, pattern, delta in new_rows:
        active.append(f"| {req_id} | {pattern} | {delta} | {_cell(statement)} | `{gap['id']}` / `{change_id}` |")
        node_id = add_node(
            project_id, "REQ", "ears_requirement", path, f"{req_id} ({pattern}, {delta}) from {gap['id']}",
            status="confirmed", domain=gap.get("lens", "product"),
        )
        if record_id:
            add_edge(project_id, record_id, node_id, "normalizes")
        result["added"].append(req_id)
    if not (new_rows or result["delta_updated"] or result["superseded"]):
        return result
    title = head[0] if head and head[0].startswith("# ") else (
        f"# Requisitos del cambio {change_id}" if language == "es" else f"# Change requirements {change_id}"
    )
    spanish = title.startswith("# Requisitos")
    lines = [title, "", "## Normalized Requirements (EARS)", "", *TABLE_HEADER, *active, ""]
    if old:
        lines += [SUPERSEDED_HEADINGS[1 if spanish else 0], "", *TABLE_HEADER, *old, ""]
    path.parent.mkdir(parents=True, exist_ok=True)
    write_text(path, chr(10).join(lines))
    return result


def materialize_change_ears(project_id: str, change_id: str, closed: list[dict], responses: dict,
                            language: str = "es", record_id: str | None = None) -> list[str]:
    """The ids of the rows a (re)closing added; see `reconcile_change_ears` for the full result."""
    return reconcile_change_ears(project_id, change_id, closed, responses, language, record_id)["added"]
