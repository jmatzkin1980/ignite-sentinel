"""IMP-396: `/validate --change CHG-nnn`. Four structural checks over the artifacts of one change; read-only."""
from __future__ import annotations

import re

from .change_escalation import escalation_warnings
from .change_requirements import load_change_ears, parse_surfaces
from .changes import change_language, get_change
from .compilers.change_backlog import read_change_units
from .core.markdown import parse_frontmatter
from .workspace import workspace_path

UNIT_DELTAS = ("ADDED", "MODIFIED", "REMOVED")

TEXT = {
    "es": {
        "unit_no_brief": "{unit} no cita el brief del cambio {brief} en sources.",
        "unit_no_ears": "{unit} apunta a {ears}, que no es una fila vigente del cambio con Delta de unidad.",
        "unit_citations_next": "Corré /specs {project} --change {change} para regenerar las unidades.",
        "story_missing_p2p": "{story} no lleva como criterio pass-to-pass la fila UNCHANGED {row}.",
        "p2p_next": "Corré /backlog {project} --change {change} para regenerar las historias.",
        "row_no_surface": "La fila {row} no declara superficie.",
        "row_unknown_surface": "La fila {row} nombra la superficie {surface}, que no está en el borde del cambio.",
        "rows_next": "/resolve-gaps {project} --source <respuestas> --change {change} — re-respondé {gap} con Superficie (una del borde).",
        "rows_next_ext": "/extract {project} --change {change} --proposals <propuestas> — re-proponé {gap} con Superficie (una del borde).",
        "artifact_no_surface": "{artifact} no declara superficies.",
        "artifact_unknown_surface": "{artifact} nombra la superficie {surface}, que no está en el borde del cambio.",
        "border_next": "Corré /specs {project} --change {change} y /backlog {project} --change {change} para regenerarlos desde las filas.",
        "no_units": "Sin unidades: corré /specs {project} --change {change}.",
        "no_backlog": "Sin backlog del cambio: corré /backlog {project} --change {change}.",
        "no_rows": "Sin filas EARS del cambio.",
        "ok": "Sin hallazgos.",
        "next": "Siguiente paso",
    },
    "en": {
        "unit_no_brief": "{unit} does not cite the change brief {brief} in sources.",
        "unit_no_ears": "{unit} points at {ears}, which is not a current row of the change with a unit Delta.",
        "unit_citations_next": "Run /specs {project} --change {change} to regenerate the units.",
        "story_missing_p2p": "{story} does not carry the UNCHANGED row {row} as a pass-to-pass criterion.",
        "p2p_next": "Run /backlog {project} --change {change} to regenerate the stories.",
        "row_no_surface": "Row {row} declares no surface.",
        "row_unknown_surface": "Row {row} names the surface {surface}, which is not in the change border.",
        "rows_next": "/resolve-gaps {project} --source <answers> --change {change} — answer {gap} again with a Surface (one of the border).",
        "rows_next_ext": "/extract {project} --change {change} --proposals <proposals> — propose {gap} again with a Surface (one of the border).",
        "artifact_no_surface": "{artifact} declares no surfaces.",
        "artifact_unknown_surface": "{artifact} names the surface {surface}, which is not in the change border.",
        "border_next": "Run /specs {project} --change {change} and /backlog {project} --change {change} to regenerate them from the rows.",
        "no_units": "No units: run /specs {project} --change {change}.",
        "no_backlog": "No backlog for the change: run /backlog {project} --change {change}.",
        "no_rows": "No EARS rows for the change.",
        "ok": "No findings.",
        "next": "Next step",
    },
}


def _change_stories(project_id: str, change_id: str) -> list[dict]:
    stories: list[dict] = []
    for path in sorted((workspace_path(project_id) / "04_backlog").glob("US-*.md")):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        front = parse_frontmatter(text)
        if str(front.get("change", "")).strip() == change_id:
            surfaces = front.get("surfaces")
            stories.append({
                "id": path.stem,
                "text": text,
                "surfaces": [str(s) for s in surfaces if str(s).strip()] if isinstance(surfaces, list) else [],
            })
    return stories


_EXT_SOURCE = re.compile(r"`EXT:([^`]+)`")


def _source_gap(row: dict) -> str:
    """The gap a row came from (its Fuente cell carries `GAP-X`, or `file#GAP-X`); an `EXT:` row names its element."""
    ext = _EXT_SOURCE.match(str(row.get("source", "")))
    if ext:
        return ext.group(1)
    found = re.search(r"GAP-[A-Z0-9-]+", str(row.get("source", "")))
    return found.group(0) if found else str(row["id"])


def _p2p_lines(text: str) -> list[str]:
    return [line for line in text.splitlines() if line.startswith("| AC-") and "pass-to-pass" in line]


def validate_change(project_id: str, change_id: str) -> dict:
    change = get_change(project_id, change_id)
    text = TEXT.get(change_language(project_id, change), TEXT["es"])
    ctx = {"project": project_id, "change": change_id}
    border = list(change.get("border", []) or [])
    rows = load_change_ears(project_id, change_id)
    units = read_change_units(project_id, change_id)
    stories = _change_stories(project_id, change_id)
    findings: list[str] = []
    checks: list[dict] = []

    def record(check_id: str, found: list, next_key: str) -> None:
        # an item is a message, or (message, source gap, is an extraction row) when the next step names the gap
        found = [
            f"{message} {text['next']}: {text[next_key + '_ext' if ext else next_key].format(**ctx, gap=gap)}"
            for message, gap, ext in ((i, "", False) if isinstance(i, str) else (i if len(i) == 3 else (*i, False)) for i in found)
        ]
        findings.extend(found)
        checks.append({"id": check_id, "status": "FAIL" if found else "PASS", "detail": "; ".join(found) or text["ok"]})

    def skip(check_id: str, key: str) -> None:
        checks.append({"id": check_id, "status": "SKIP", "detail": text[key].format(**ctx)})

    # 1. unit_citations
    if not units:
        skip("unit_citations", "no_units")
    else:
        brief = f"02_requirements/{change_id}/project-brief.md"
        unit_rows = {r["id"] for r in rows if r.get("delta") in UNIT_DELTAS}
        found = []
        for unit in units:
            if brief not in unit["sources"]:
                found.append(text["unit_no_brief"].format(unit=unit["id"], brief=brief))
            for ears in unit["ears"]:
                if ears not in unit_rows:
                    found.append(text["unit_no_ears"].format(unit=unit["id"], ears=ears))
        record("unit_citations", found, "unit_citations_next")

    # 2. preserved_pass_to_pass
    if not stories:
        skip("preserved_pass_to_pass", "no_backlog")
    else:
        found = []
        for row in rows:
            if row.get("delta") != "UNCHANGED":
                continue
            for story in stories:
                if not any(row["id"] in line for line in _p2p_lines(story["text"])):
                    found.append(text["story_missing_p2p"].format(story=story["id"], row=row["id"]))
        record("preserved_pass_to_pass", found, "p2p_next")

    # 3. rows_have_surfaces
    if not rows:
        skip("rows_have_surfaces", "no_rows")
    else:
        found = []
        for row in rows:
            surfaces = row.get("surfaces", [])
            gap = _source_gap(row)
            ext = bool(_EXT_SOURCE.match(str(row.get("source", ""))))
            if not surfaces:
                found.append((text["row_no_surface"].format(row=row["id"]), gap, ext))
            for surface in surfaces:
                if parse_surfaces(surface, border)[1]:
                    found.append((text["row_unknown_surface"].format(row=row["id"], surface=surface), gap, ext))
        record("rows_have_surfaces", found, "rows_next")

    # 4. stories_inside_border
    artifacts = [(u["id"], u["surfaces"]) for u in units] + [(s["id"], s["surfaces"]) for s in stories]
    if not artifacts:
        skip("stories_inside_border", "no_units")
    else:
        found = []
        for artifact, surfaces in artifacts:
            if not surfaces:
                found.append(text["artifact_no_surface"].format(artifact=artifact))
            for surface in surfaces:
                if parse_surfaces(surface, border)[1]:
                    found.append(text["artifact_unknown_surface"].format(artifact=artifact, surface=surface))
        record("stories_inside_border", found, "border_next")

    return {
        "project_id": project_id,
        "change_id": change_id,
        "verdict": "INVALID" if findings else "VALID",
        "findings": findings,
        "checks": checks,
        "warnings": escalation_warnings(project_id, change_id),
    }
