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
        "series_stale": "La serie de releases de {change} está desactualizada: el cambio se movió desde que se compiló.",
        "series_next": "Proponé la serie de nuevo con /split {project} --change {change} --propose --source PROPUESTA.json y confirmala con --confirm.",
        "series_unit_next": "/split {project} --change {change} --move --unit <C-NN> --from <rA> --to <rB> --reason \"...\" --ba \"...\" --tech \"...\"",
        "release_specs_old": "Las unidades de {rid} en 03_specs/{change}/{rid}/ están viejas: cambió la serie o el cambio desde que se derivaron.",
        "release_specs_closed": "Las unidades de {rid} en 03_specs/{change}/{rid}/ se derivaron antes de que cerrara {closed}: lo que entregó no figura como preservado.",
        "release_backlog_old": "Las historias de {rid} (04_backlog/{change}/{rid}/stories.md) no salen de sus unidades actuales.",
        "release_specs_next": "/specs {project} --change {change} --release {rid} y después /backlog {project} --change {change} --release {rid}",
        "release_backlog_next": "/backlog {project} --change {change} --release {rid}",
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
        "series_stale": "The release series of {change} is stale: the change moved since it was compiled.",
        "series_next": "Propose the series again with /split {project} --change {change} --propose --source PROPOSAL.json and confirm it with --confirm.",
        "series_unit_next": "/split {project} --change {change} --move --unit <C-NN> --from <rA> --to <rB> --reason \"...\" --ba \"...\" --tech \"...\"",
        "release_specs_old": "The units of {rid} in 03_specs/{change}/{rid}/ are old: the series or the change moved since they were derived.",
        "release_specs_closed": "The units of {rid} in 03_specs/{change}/{rid}/ were derived before {closed} closed: what it delivered is not listed as preserved.",
        "release_backlog_old": "The stories of {rid} (04_backlog/{change}/{rid}/stories.md) do not come from its current units.",
        "release_specs_next": "/specs {project} --change {change} --release {rid}, then /backlog {project} --change {change} --release {rid}",
        "release_backlog_next": "/backlog {project} --change {change} --release {rid}",
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
_LINE_ANCHOR = re.compile(r":L\d+")


def _source_gap(row: dict) -> str:
    """The gap a row came from (its Fuente cell carries `GAP-X`, or `file#GAP-X`); an `EXT:` row names its element."""
    ext = _EXT_SOURCE.match(str(row.get("source", "")))
    if ext:
        return ext.group(1)
    found = re.search(r"GAP-[A-Z0-9-]+", str(row.get("source", "")))
    return found.group(0) if found else str(row["id"])


def _p2p_lines(text: str) -> list[str]:
    return [line for line in text.splitlines() if line.startswith("| AC-") and "pass-to-pass" in line]


def _series_findings(project_id: str, change_id: str, text: dict, has_units: bool) -> list[tuple[str, str, dict]] | None:
    """(message, next-step key, its fields) of what is wrong with the confirmed series of the change; None when it has none."""
    from .change_release import ChangeReleaseError, release_units, stale_derivations
    from .core.io import read_json
    from .release_series import MAP_FILE, series_validation_findings
    from .series_scope import series_dir, series_scope

    base = workspace_path(project_id)
    partition = read_json(series_dir(base, change_id) / "partition.json", None)
    if not isinstance(partition, dict) or partition.get("status") != "confirmed":
        return None
    found: list[tuple[str, str, dict]] = [(message, "series_next", {}) for message in series_validation_findings(base, change_id)]
    current = read_json(series_dir(base, change_id) / MAP_FILE, None)
    scope = series_scope(project_id, change_id)
    if scope.brief_text and not (isinstance(current, dict) and current.get("brief_sha256") == scope.brief_sha256):
        found.append((text["series_stale"].format(change=change_id), "series_next", {}))
    if has_units:
        try:
            release_units(project_id, change_id)
        except ChangeReleaseError as exc:
            found.append((str(exc), "series_unit_next", {}))
        # I1: an open release derived before another closed, or whose series or change moved, is old
        for row in stale_derivations(project_id, change_id):
            fields = {"rid": row["release"], "closed": row["closed_since"]}
            message = text[f"release_{row['layer']}_{row['why']}"].format(change=change_id, **fields)
            found.append((message, f"release_{row['layer']}_next", fields))
    return found


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
            if brief not in unit["sources"] and not any(_LINE_ANCHOR.search(src) for src in unit["sources"]):
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

    # 5. release_series (H27 inc 7d): only a change with a confirmed series has this check; the others keep their four
    series = _series_findings(project_id, change_id, text, bool(units))
    if series is not None:
        found = [f"{message} {text['next']}: {text[next_key].format(**ctx, **fields)}" for message, next_key, fields in series]
        findings.extend(found)
        checks.append({"id": "release_series", "status": "FAIL" if found else "PASS", "detail": "; ".join(found) or text["ok"]})

    return {
        "project_id": project_id,
        "change_id": change_id,
        "verdict": "INVALID" if findings else "VALID",
        "findings": findings,
        "checks": checks,
        "warnings": escalation_warnings(project_id, change_id),
    }
