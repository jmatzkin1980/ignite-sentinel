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
RETIRED_EARS = Path("extraction") / "retired_ears.md"  # IMP-420: ids the project's extractor retired; never reused
PROJECT_TABLE_HEADER = ["| ID | Pattern | Statement | Source |", "| --- | --- | --- | --- |"]


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
    """IMP-396: (valid, unknown) surfaces of a `Superficie` value against the border; valid ones as the border spells them (name or alias in, canonical name out)."""
    by_name = {_fold_name(item.get("name", "")): str(item.get("name", "")) for item in border if item.get("name")}
    for item in border:
        if item.get("alias") and item.get("name"):
            by_name.setdefault(_fold_name(item["alias"]), str(item["name"]))
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


def change_requirements_path(base: Path, change_id: str | None) -> Path:
    if change_id is None:
        return base / "02_requirements" / "requirements.md"
    return base / "02_requirements" / change_id / "requirements.md"


def next_ears_index(base: Path) -> int:
    """The next REQ-EARS number: one past the highest in the project file and every change file."""
    requirements = base / "02_requirements"
    files = [requirements / "requirements.md", requirements / RETIRED_EARS,
             *sorted(requirements.glob("CHG-*/requirements.md"))]
    highest = 0
    for path in files:
        if path.is_file():
            numbers = [int(n) for n in _EARS_ID.findall(path.read_text(encoding="utf-8"))]
            highest = max([highest, *numbers])
    return highest + 1


def _cell(text: str) -> str:
    return " ".join(str(text).split()).replace("|", _ESCAPED_PIPE)


A_CONFIRMAR_TAIL = " / `a_confirmar`"  # IMP-412: ends the Source cell of the rows of an element the request left to confirm


def _project_ears(project_id: str) -> list[dict]:
    """IMP-420: the rows of the project's 4-column table (backticks kept, so `EXT:` is found), everything ADDED."""
    path = change_requirements_path(workspace_path(project_id), None)
    if not path.is_file():
        return []
    rows: list[dict] = []
    in_table = False
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            in_table = line.strip() == "## Normalized Requirements (EARS)"
        cells = _row_cells(line) if in_table and line.startswith("| REQ-EARS-") else []
        if len(cells) < 4:
            continue
        rows.append({
            **({"a_confirmar": True} if cells[3].endswith(A_CONFIRMAR_TAIL) else {}),
            "id": cells[0], "pattern": cells[1], "delta": "ADDED",
            "statement": cells[2].replace(_ESCAPED_PIPE, "|"), "source": cells[3],
            "affects": [], "surfaces": [],
        })
    return rows


def load_change_ears(project_id: str, change_id: str | None) -> list[dict]:
    if change_id is None:
        return _project_ears(project_id)
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
            **({"a_confirmar": True} if cells[4].endswith(A_CONFIRMAR_TAIL) else {}),
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


Statement = tuple[str, str, str, str, str]  # (statement, pattern, delta, affects cell, surface cell)
Group = tuple[str, str, list[Statement]]  # (key `_row_gap` returns, Source cell, statements)


def _reconcile_groups(project_id: str, change_id: str, groups: list[Group], language: str = "es",
                      record_id: str | None = None, lenses: dict[str, str] | None = None) -> dict[str, list[str]]:
    """Reconcile the REQ-EARS rows of each group (a gap, or an extracted element) of a change.

    A row whose (key, statement) is still produced keeps its id and takes the declared Delta, Afecta and
    Superficie in place; a statement no longer produced moves to the Superseded table (its id is never
    reused); a new one takes the next id. An empty group supersedes every row of its key.
    """
    base = workspace_path(project_id)
    path = change_requirements_path(base, change_id)
    result: dict[str, list[str]] = {"added": [], "delta_updated": [], "superseded": []}
    exists = path.is_file()
    original = path.read_text(encoding="utf-8") if exists else ""
    head, active, old = _split_file(original) if exists else ([], [], [])
    next_index = next_ears_index(base)
    new_rows: list[tuple[str, str, str, str, str, str, str, str]] = []
    for key_id, source_cell, statements in groups:
        produced: dict[str, Statement] = {}
        for entry in statements:
            produced.setdefault(_cell(entry[0]), entry)
        matched: set[str] = set()
        for position, line in enumerate(active):
            if _row_gap(line) != key_id:
                continue
            cells = _padded(_row_cells(line))
            key = _cell(cells[3].replace(_ESCAPED_PIPE, "|"))
            if key in produced and key not in matched:
                matched.add(key)
                _, _, delta, affects, surfaces = produced[key]
                want_tail, has_tail = source_cell.endswith(A_CONFIRMAR_TAIL), cells[4].endswith(A_CONFIRMAR_TAIL)
                if cells[2] != delta or cells[5] != affects or cells[6] != surfaces or want_tail != has_tail:
                    cells[2] = delta or cells[2]
                    cells[5] = affects
                    cells[6] = surfaces
                    if want_tail != has_tail:  # IMP-412 (P2): the mark follows the request, both ways, on rows that already exist
                        cells[4] = cells[4] + A_CONFIRMAR_TAIL if want_tail else cells[4][: -len(A_CONFIRMAR_TAIL)]
                    active[position] = "| " + " | ".join(cells) + " |"
                    result["delta_updated"].append(cells[0])
            else:
                active[position] = ""
                old.append(line)
                result["superseded"].append(cells[0])
        for key, (statement, pattern, delta, affects, surfaces) in produced.items():
            if key not in matched:
                new_rows.append((f"REQ-EARS-{next_index:03d}", key_id, source_cell, statement, pattern, delta, affects, surfaces))
                next_index += 1
    active = [line for line in active if line]
    for req_id, key_id, source_cell, statement, pattern, delta, affects, surfaces in new_rows:
        active.append(f"| {req_id} | {pattern} | {delta} | {_cell(statement)} | {source_cell} | {affects} | {_cell(surfaces)} |")
        node_id = add_node(
            project_id, "REQ", "ears_requirement", path, f"{req_id} ({pattern}, {delta}) from {key_id}",
            status="confirmed", domain=(lenses or {}).get(key_id, "product"),
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


def reconcile_change_ears(project_id: str, change_id: str, closed: list[dict], responses: dict,
                          language: str = "es", record_id: str | None = None) -> dict[str, list[str]]:
    """Reconcile the REQ-EARS rows of each (re)closed answer of a change.

    A row whose (gap, statement) is still produced keeps its id and takes the declared Delta in place;
    a statement no longer produced moves to the Superseded table (its id is never reused); a new one
    takes the next id. GAP-SCOPE (the border) is exempt.
    """
    from .changes import get_change
    from .gap_resolution import ears_statements

    border = get_change(project_id, change_id).get("border", []) or []
    groups: list[Group] = []
    lenses: dict[str, str] = {}
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
        groups.append((
            gap["id"], f"`{gap['id']}` / `{change_id}`",
            [(statement, pattern, str(delta), affects, surfaces) for statement, pattern in statements],
        ))
        lenses[gap["id"]] = gap.get("lens", "product")
    return _reconcile_groups(project_id, change_id, groups, language, record_id, lenses)


def reconcile_extraction_ears(project_id: str, change_id: str, element_id: str, statements: list[dict], cite: str,
                              language: str = "es", a_confirmar: bool = False) -> dict[str, list[str]]:
    """IMP-402: the rows of one extracted element; each statement carries its own Delta, Afecta and Superficie.

    IMP-412: `a_confirmar` marks the new rows (the request calls the element to be confirmed; the BA gave a reason)."""
    entries: list[Statement] = [
        (
            str(s["text"]), str(s["pattern"]), str(s["delta"]),
            _affects_cell(list(s.get("affects") or []) if s["delta"] in _AFFECTING_DELTAS else []),
            _surfaces_cell(list(s.get("surfaces") or [])),
        )
        for s in statements
    ]
    source = f"`EXT:{element_id}` / `{cite}` / `{change_id}`" + (" / `a_confirmar`" if a_confirmar else "")
    group: Group = (f"EXT:{element_id}", source, entries)
    return _reconcile_groups(project_id, change_id, [group], language)


def materialize_change_ears(project_id: str, change_id: str, closed: list[dict], responses: dict,
                            language: str = "es", record_id: str | None = None) -> list[str]:
    """The ids of the rows a (re)closing added; see `reconcile_change_ears` for the full result."""
    return reconcile_change_ears(project_id, change_id, closed, responses, language, record_id)["added"]


_EXT_CELL = re.compile(r"`EXT:([^`]+)`")
_PROJECT_HEADING = "## Normalized Requirements (EARS)"
_PROJECT_INTRO = (
    "Testable statements normalized from confirmed functional answers (IMP-026) and from the request elements "
    "the extraction confirmed (IMP-420). Specs and backlog cite these by `REQ-EARS-*`."
)


def reconcile_project_extraction_ears(project_id: str, element_id: str, statements: list[dict], cite: str,
                                      a_confirmar: bool = False) -> dict[str, list[str]]:
    """IMP-420: the rows of one extracted element of the project request, in the 4-column table of requirements.md.

    A row whose (element, statement) is still produced stays in place (keeping its id); a statement no longer
    produced leaves the table and is noted in `extraction/retired_ears.md`, so its id is never reused; a new one
    takes the next global id (`next_ears_index`). An empty list retires every row of the element."""
    base = workspace_path(project_id)
    path = change_requirements_path(base, None)
    result: dict[str, list[str]] = {"added": [], "kept": [], "retired": []}
    text = path.read_text(encoding="utf-8") if path.is_file() else ""
    lines = text.split("\n") if text else []
    source_cell = f"`EXT:{element_id}` / `{cite}`" + (A_CONFIRMAR_TAIL if a_confirmar else "")
    produced: dict[str, dict] = {}
    for entry in statements:
        produced.setdefault(_cell(entry["text"]), entry)
    matched: set[str] = set()
    retired: list[str] = []
    in_table = False
    kept_lines: list[str] = []
    for line in lines:
        if line.startswith("## "):
            in_table = line.strip() == _PROJECT_HEADING
        cells = _row_cells(line) if in_table and line.startswith("| REQ-EARS-") else []
        found = _EXT_CELL.match(cells[3]) if len(cells) >= 4 else None
        if not found or found.group(1) != element_id:
            kept_lines.append(line)
            continue
        key = _cell(cells[2].replace(_ESCAPED_PIPE, "|"))
        if key in produced and key not in matched:
            matched.add(key)
            result["kept"].append(cells[0])
            want_tail, has_tail = source_cell.endswith(A_CONFIRMAR_TAIL), cells[3].endswith(A_CONFIRMAR_TAIL)
            if want_tail != has_tail:  # the mark follows the request, both ways
                cells[3] = cells[3] + A_CONFIRMAR_TAIL if want_tail else cells[3][: -len(A_CONFIRMAR_TAIL)]
                line = "| " + " | ".join(cells[:4]) + " |"
            kept_lines.append(line)
        else:
            retired.append(line)
            result["retired"].append(cells[0])
    next_index = next_ears_index(base)
    new_rows: list[str] = []
    for key, entry in produced.items():
        if key in matched:
            continue
        req_id = f"REQ-EARS-{next_index:03d}"
        next_index += 1
        new_rows.append(f"| {req_id} | {entry['pattern']} | {key} | {source_cell} |")
        add_node(project_id, "REQ", "ears_requirement", path, f"{req_id} ({entry['pattern']}) from EXT:{element_id}",
                 status="confirmed", domain="product")
        result["added"].append(req_id)
    if not (new_rows or retired):
        return result
    lines = kept_lines
    if new_rows:
        heading = next((n for n, line in enumerate(lines) if line.strip() == _PROJECT_HEADING), None)
        if heading is None:
            while lines and not lines[-1].strip():
                lines.pop()
            lines += ["", _PROJECT_HEADING, "", _PROJECT_INTRO, "", *PROJECT_TABLE_HEADER, *new_rows, ""]
        else:
            end = next((n for n in range(heading + 1, len(lines)) if lines[n].startswith("## ")), len(lines))
            last = max((n for n in range(heading + 1, end) if lines[n].startswith("|")), default=None)
            if last is None:
                lines[heading + 1:heading + 1] = ["", _PROJECT_INTRO, "", *PROJECT_TABLE_HEADER, *new_rows]
            else:
                lines[last + 1:last + 1] = new_rows
    write_text(path, "\n".join(lines))
    if retired:
        old_path = base / "02_requirements" / RETIRED_EARS
        old = old_path.read_text(encoding="utf-8").rstrip("\n").split("\n") if old_path.is_file() else [
            "# Retired EARS rows of the project (IMP-420)", "",
            "Rows the extraction replaced or retired; their ids are never reused.", "", *PROJECT_TABLE_HEADER,
        ]
        old_path.parent.mkdir(parents=True, exist_ok=True)
        write_text(old_path, "\n".join([*old, *retired, ""]))
    return result
