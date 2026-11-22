"""IMP-388: the spec units of a change (CHG-nnn), built only from the change's REQ-EARS rows.

Units live in `03_specs/CHG-nnn/units/`, never in the project's `03_specs/units/`, and a change
never writes `prd.md`. Ids come from the shared SPEC-U registry, keyed by the REQ-EARS id, so a
rerun keeps them and a new row takes the next number. `UNCHANGED` rows are not units: they are
listed as preserved behaviour.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from ..change_requirements import load_change_ears, parse_delta
from ..changes import change_language, get_change
from ..core.graph import add_edge, upsert_node
from ..core.io import remove, write_json, write_text
from ..core.time import utc_now
from ..errors import GateRefusal
from ..workspace import read_state, update_state, workspace_path
from .specs import ensure_spec_unit_ids_seeded, render_spec_unit

UNIT_DELTAS = ("ADDED", "MODIFIED", "REMOVED")
EARS_ANCHOR = "02_requirements/{cid}/requirements.md#normalized-requirements-ears"
BRIEF_PATH = "02_requirements/{cid}/project-brief.md"

TEXT = {
    "es": {
        "title": "# Especificación del cambio {cid}",
        "units": "## Unidades",
        "preserved": "## Comportamiento preservado",
        "no_units": "_Sin unidades._",
        "no_preserved": "_Sin filas UNCHANGED._",
        "header": ["Unidad", "Delta", "REQ-EARS", "Enunciado"],
        "preserved_header": ["REQ-EARS", "Enunciado"],
        "note": "Las historias del cambio salen de estas unidades con /backlog --change.",
        "next": "Revisá {path}; después /backlog --change deriva las historias.",
        "no_brief": "{cid} no tiene brief: /specs --change parte de {brief}",
        "blocking": "{cid} tiene {n} gap(s) bloqueante(s) abierto(s)",
        "no_rows": "{cid} no tiene filas ADDED, MODIFIED ni REMOVED: no hay unidades para especificar",
        "no_rows_next": ("Respondé GAP-ACCEPTANCE en EARS con Delta (ADDED, MODIFIED o REMOVED) y corré "
                         "/resolve-gaps {pid} --change {cid}"),
    },
    "en": {
        "title": "# Change specification {cid}",
        "units": "## Units",
        "preserved": "## Preserved behavior",
        "no_units": "_No units._",
        "no_preserved": "_No UNCHANGED rows._",
        "header": ["Unit", "Delta", "REQ-EARS", "Statement"],
        "preserved_header": ["REQ-EARS", "Statement"],
        "note": "The stories of the change come from these units with /backlog --change.",
        "next": "Review {path}; then /backlog --change derives the stories.",
        "no_brief": "{cid} has no brief: /specs --change starts from {brief}",
        "blocking": "{cid} has {n} blocking gap(s) open",
        "no_rows": "{cid} has no ADDED, MODIFIED or REMOVED rows: there are no units to specify",
        "no_rows_next": ("Answer GAP-ACCEPTANCE in EARS with a Delta (ADDED, MODIFIED or REMOVED) and run "
                         "/resolve-gaps {pid} --change {cid}"),
    },
}


def _cell(text: str) -> str:
    return " ".join(str(text).split()).replace("|", "\\|")


def _table(header: list[str], rows: list[list[str]]) -> str:
    lines = ["| " + " | ".join(header) + " |", "| " + " | ".join("---" for _ in header) + " |"]
    lines += ["| " + " | ".join(row) + " |" for row in rows]
    return "\n".join(lines)


def _gate(project_id: str, change_id: str) -> tuple[dict, list[dict]]:
    change = get_change(project_id, change_id)
    base = workspace_path(project_id)
    text = TEXT.get(change_language(project_id, change), TEXT["es"])
    brief = BRIEF_PATH.format(cid=change_id)
    if not (base / brief).is_file():
        raise GateRefusal(
            text["no_brief"].format(cid=change_id, brief=brief),
            next_step=f"/brief {project_id} --change {change_id}",
        )
    blocking = int((change.get("gap_counts") or {}).get("blocking_open", 0) or 0)
    if blocking > 0:
        raise GateRefusal(
            text["blocking"].format(cid=change_id, n=blocking),
            next_step=f"/resolve-gaps {project_id} --change {change_id}",
        )
    rows = load_change_ears(project_id, change_id)
    if not any(parse_delta(row["delta"]) in UNIT_DELTAS for row in rows):
        raise GateRefusal(
            text["no_rows"].format(cid=change_id),
            next_step=text["no_rows_next"].format(pid=project_id, cid=change_id),
        )
    return change, rows


def compile_change_specs(project_id: str, change_id: str) -> dict[str, Any]:
    change, rows = _gate(project_id, change_id)
    base = workspace_path(project_id)
    language = change_language(project_id, change)
    text = TEXT.get(language, TEXT["es"])
    unit_rows = [row for row in rows if parse_delta(row["delta"]) in UNIT_DELTAS]
    preserved_rows = [row for row in rows if parse_delta(row["delta"]) == "UNCHANGED"]

    from .. import id_registry

    ensure_spec_unit_ids_seeded(project_id, base)
    ids = id_registry.assign_ids(project_id, "SPEC-U", [row["id"] for row in unit_rows])

    folder = base / "03_specs" / change_id
    units_dir = folder / "units"
    units_dir.mkdir(parents=True, exist_ok=True)
    sources = [EARS_ANCHOR.format(cid=change_id), BRIEF_PATH.format(cid=change_id)]
    units: list[dict[str, Any]] = []
    for row in unit_rows:
        unit_id = ids[row["id"]]
        unit = {
            "id": unit_id,
            "title": f"{unit_id} - {row['id']}",
            "status": "evidence-backed",
            "change": change_id,
            "delta": parse_delta(row["delta"]),
            "trace_ids": [change_id, row["id"]],
            "ears": [row["id"]],
            "sources": sources,
            "pattern": row["pattern"],
            "statement": row["statement"],
            "source": row["source"],
            "path": units_dir / f"{unit_id}.md",
        }
        write_text(unit["path"], render_spec_unit(project_id, unit))
        units.append(unit)
    active = {unit["path"] for unit in units}
    for stale in units_dir.glob("SPEC-U-*.md"):
        if stale not in active:
            remove(stale)

    unit_table = _table(
        text["header"],
        [[f"`{u['id']}`", u["delta"], f"`{u['ears'][0]}`", _cell(u["statement"])] for u in units],
    ) if units else text["no_units"]
    preserved_table = _table(
        text["preserved_header"], [[f"`{r['id']}`", _cell(r["statement"])] for r in preserved_rows]
    ) if preserved_rows else text["no_preserved"]
    specs_path = folder / "specs.md"
    write_text(specs_path, "\n".join([
        text["title"].format(cid=change_id), "", text["units"], "", unit_table, "",
        text["preserved"], "", preserved_table, "", text["note"], "",
    ]))

    by_delta: dict[str, int] = {}
    for unit in units:
        by_delta[unit["delta"]] = by_delta.get(unit["delta"], 0) + 1
    unit_ids = [unit["id"] for unit in units]
    preserved = [row["id"] for row in preserved_rows]
    report = {"change_id": change_id, "units": unit_ids, "ears": [row["id"] for row in unit_rows],
              "deltas": {row["id"]: parse_delta(row["delta"]) for row in unit_rows},
              "preserved": preserved, "by_delta": by_delta}
    write_json(folder / "change_specs_report.json", report)

    requirements_path = base / EARS_ANCHOR.format(cid=change_id).split("#")[0]
    for unit in units:
        unit_node = upsert_node(
            project_id, unit["id"], "spec_unit", unit["path"], unit["title"], status=unit["status"], domain="product"
        )
        ears_node = upsert_node(
            project_id, unit["ears"][0], "ears_requirement", requirements_path,
            f"{unit['ears'][0]} normalized EARS requirement", status="confirmed", domain="product",
        )
        add_edge(project_id, unit_node, ears_node, "traces_to")

    changes = read_state(project_id).get("changes", {})
    changes[change_id]["specs"] = {"units": unit_ids, "generated_at": utc_now()}
    update_state(project_id, changes=changes)

    return {
        "project_id": project_id,
        "change_id": change_id,
        "path": specs_path.relative_to(base).as_posix(),
        "units": unit_ids,
        "preserved": preserved,
        "report": report,
        "next_step": text["next"].format(path=specs_path.relative_to(base).as_posix()),
    }
