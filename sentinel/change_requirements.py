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
TABLE_HEADER = [
    "| ID | Pattern | Delta | Statement | Source | Afecta | Superficie |",
    "| --- | --- | --- | --- | --- | --- | --- |",
]
_STORY_ID = re.compile(r"\bUS-\d{3}\b")
_NO_AFFECTS = ("ninguna", "ninguno", "none")
_SPEC_UNIT = re.compile(r"\bSPEC-U-\d+\b")
_AFFECTING_DELTAS = ("MODIFIED", "REMOVED")
_EARS_ID = re.compile(r"REQ-EARS-(\d+)")
_EARS_FULL = re.compile(r"\bREQ-EARS-\d+\b")
_ESCAPED_PIPE = "\\|"
_CELL_SPLIT = re.compile(r"(?<!\\)\|")
_SOURCE = re.compile(r"`([^`]+)`")


def parse_delta(value: str) -> str | None:
    """One of the four deltas (any case), or None when missing or anything else (no aliases)."""
    candidate = str(value or "").strip().strip("`").strip().upper()
    return candidate if candidate in DELTA_VALUES else None


def parse_affects(value: str) -> list[str] | None:
    """IMP-393: the story ids a MODIFIED/REMOVED requirement affects; [] for `ninguna`; None when missing or unreadable."""
    text = str(value or "").strip().strip("`").strip()
    if text.lower() in _NO_AFFECTS:
        return []
    ids = list(dict.fromkeys(_STORY_ID.findall(text.upper())))
    return ids or None


def _affects_cell(ids: list[str]) -> str:
    return ", ".join(ids) if ids else "-"


def _fold_name(text: str) -> str:
    """Case, accent and spacing folded, so a surface name matches however the BA typed it."""
    from .source_conflicts import _fold

    return " ".join(_fold(str(text or "")).split())


def parse_surfaces(value: str, border: list[dict]) -> tuple[list[str], list[str]]:
    """IMP-396: (valid, unknown) surfaces of a `Superficie` value against the border; valid ones as the border spells them."""
    by_name = {_fold_name(item.get("name", "")): str(item.get("name", "")) for item in border if item.get("name")}
    valid: list[str] = []
    unknown: list[str] = []
    for part in str(value or "").split(";"):
        part = part.strip().strip("`").strip()
        if not part or part == "-":
            continue
        canonical = by_name.get(_fold_name(part))
        target, name = (valid, canonical) if canonical else (unknown, part)
        if name not in target:
            target.append(name)
    return valid, unknown


def propose_surfaces(statement: str, border: list[dict]) -> list[str]:
    """IMP-396: the border surfaces whose name appears in the statement (a proposal; the BA declares)."""
    folded = _fold_name(statement)
    found: list[str] = []
    for item in border:
        name = str(item.get("name", ""))
        if name and _fold_name(name) in folded and name not in found:
            found.append(name)
    return found


def _surfaces_cell(names: list[str]) -> str:
    return "; ".join(names) if names else "-"


def _padded(cells: list[str]) -> list[str]:
    """A 0.20.0 row (5 columns) gets Afecta, a 0.21.0 row (6) gets Superficie."""
    return [*cells, *["-"] * max(0, 7 - len(cells))]


def story_files(base: Path) -> dict[str, Path]:
    return {path.stem: path for path in sorted((base / "04_backlog").glob("US-*.md")) if _STORY_ID.fullmatch(path.stem)}


def story_candidates(project_id: str, change_id: str, evidence: str) -> list[str]:
    """IMP-393: the stories (not the change's own) that the evidence or an adjacent/preserved border surface points at."""
    from .changes import get_change
    from .core.io import read_json
    from .core.markdown import parse_frontmatter

    base = workspace_path(project_id)
    text = str(evidence or "")
    for surface in get_change(project_id, change_id).get("border", []) or []:
        if surface.get("zone") in ("adyacente", "preservado"):
            text += f" {surface.get('name', '')} {surface.get('cite', '')}"
    mentioned = set(_STORY_ID.findall(text))
    units = set(_SPEC_UNIT.findall(text)) | set(_EARS_FULL.findall(text))
    readiness = read_json(base / "08_context_packs" / "implementation_readiness.json", {})
    by_story = {
        str(item.get("story_id")): item for item in (readiness.get("stories", []) if isinstance(readiness, dict) else [])
        if isinstance(item, dict)
    }
    found: list[str] = []
    for story_id, path in story_files(base).items():
        front = parse_frontmatter(path.read_text(encoding="utf-8"))
        if str(front.get("change", "")).strip() == change_id:
            continue
        item = by_story.get(story_id, {})
        front_trace = front.get("trace") if isinstance(front.get("trace"), list) else []
        refs = {str(item.get("source_unit", "")), *map(str, item.get("trace", []) or []), *map(str, front_trace)}
        if story_id in mentioned or refs & units:
            found.append(story_id)
    return found


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
            "affects": _STORY_ID.findall(cells[5]) if len(cells) >= 6 else [],
            "surfaces": [s.strip() for s in cells[6].replace(_ESCAPED_PIPE, "|").split(";") if s.strip() and s.strip() != "-"]
            if len(cells) >= 7 else [],
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
    from .changes import get_change

    border = get_change(project_id, change_id).get("border", []) or []
    new_rows: list[tuple[str, dict, str, str, str, str, str]] = []
    for gap in closed:
        if gap["id"] == "GAP-SCOPE":
            continue
        answer = (gap.get("answer") or "").strip()
        statements = ears_statements(answer)
        delta = parse_delta(str(responses.get(gap["id"], {}).get("delta", "")))
        if statements and not delta:
            continue
        affects = _affects_cell(
            (parse_affects(str(responses.get(gap["id"], {}).get("affects", ""))) or []) if delta in _AFFECTING_DELTAS else []
        )
        surfaces = _surfaces_cell(parse_surfaces(str(responses.get(gap["id"], {}).get("surface", "")), border)[0])
        produced: dict[str, tuple[str, str]] = {}
        for statement, pattern in statements:
            produced.setdefault(_cell(statement), (statement, pattern))
        matched: set[str] = set()
        for position, line in enumerate(active):
            if _row_gap(line) != gap["id"]:
                continue
            cells = _padded(_row_cells(line))
            key = _cell(cells[3].replace(_ESCAPED_PIPE, "|"))
            if key in produced and key not in matched:
                matched.add(key)
                if cells[2] != delta or cells[5] != affects or cells[6] != surfaces:
                    cells[2] = delta or cells[2]
                    cells[5] = affects
                    cells[6] = surfaces
                    active[position] = "| " + " | ".join(cells) + " |"
                    result["delta_updated"].append(cells[0])
            else:
                active[position] = ""
                old.append(line)
                result["superseded"].append(cells[0])
        for key, (statement, pattern) in produced.items():
            if key not in matched:
                new_rows.append((f"REQ-EARS-{next_index:03d}", gap, statement, pattern, str(delta), affects, surfaces))
                next_index += 1
    active = [line for line in active if line]
    for req_id, gap, statement, pattern, delta, affects, surfaces in new_rows:
        active.append(
            f"| {req_id} | {pattern} | {delta} | {_cell(statement)} | `{gap['id']}` / `{change_id}` | {affects} | {_cell(surfaces)} |"
        )
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
    def full(line: str) -> str:
        return line if len(_row_cells(line)) >= 7 else "| " + " | ".join(_padded(_row_cells(line))) + " |"

    active = [full(line) for line in active]
    old = [full(line) for line in old]
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
