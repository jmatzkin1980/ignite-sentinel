"""IMP-388: the spec units of a change (CHG-nnn), built only from the change's REQ-EARS rows.

Units live in `03_specs/CHG-nnn/units/`, never in the project's `03_specs/units/`. IMP-414: the change's
PRD (`03_specs/CHG-nnn/prd.md`) is written from the consolidated final export by `change_prd.write_change_prd`. Ids come from the shared SPEC-U registry, keyed by the REQ-EARS id, so a
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
from ..extraction.coverage import extraction_view
from .change_deliverable import _EXT_SOURCE
from .specs import ensure_spec_unit_ids_seeded, render_spec_unit

UNIT_DELTAS = ("ADDED", "MODIFIED", "REMOVED")
EARS_ANCHOR = "02_requirements/{cid}/requirements.md#normalized-requirements-ears"
BRIEF_PATH = "02_requirements/{cid}/project-brief.md"

TEXT = {
    "es": {
        "next": "Revisá {path}; después /backlog --change deriva las historias.",
        "no_brief": "{cid} no tiene brief: /specs --change parte de {brief}",
        "blocking": "{cid} tiene {n} gap(s) bloqueante(s) abierto(s)",
        "prd_skipped": "prd.md pendiente: falta el export final vigente ({command})",
        "no_rows": "{cid} no tiene filas ADDED, MODIFIED ni REMOVED: no hay unidades para especificar",
        "no_rows_next": ("Respondé GAP-ACCEPTANCE en EARS con Delta (ADDED, MODIFIED o REMOVED) y corré "
                         "/resolve-gaps {pid} --change {cid}"),
    },
    "en": {
        "next": "Review {path}; then /backlog --change derives the stories.",
        "no_brief": "{cid} has no brief: /specs --change starts from {brief}",
        "blocking": "{cid} has {n} blocking gap(s) open",
        "prd_skipped": "prd.md pending: the current final export is missing ({command})",
        "no_rows": "{cid} has no ADDED, MODIFIED or REMOVED rows: there are no units to specify",
        "no_rows_next": ("Answer GAP-ACCEPTANCE in EARS with a Delta (ADDED, MODIFIED or REMOVED) and run "
                         "/resolve-gaps {pid} --change {cid}"),
    },
}


def unit_sources(row: dict, elements_by_id: dict[str, dict], change_id: str) -> list[str]:
    """Sources of a unit: a row from a request element cites its lines (`path:Lnn-Lmm`); a GAP answer keeps the brief."""
    found = _EXT_SOURCE.match(str(row.get("source", "")))
    element = elements_by_id.get(found.group(1)) if found else None
    anchors: list[str] = []
    for span in (element or {}).get("spans") or []:
        a, b = int(span[0]), int(span[-1])
        anchors.append(f"{element['path']}:L{a}" if a == b else f"{element['path']}:L{a}-L{b}")
    if not anchors:
        return [EARS_ANCHOR.format(cid=change_id), BRIEF_PATH.format(cid=change_id)]
    return [EARS_ANCHOR.format(cid=change_id), *anchors]


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
    elements_by_id = {e["id"]: e for e in extraction_view(project_id, change_id)["elements"]}
    units: list[dict[str, Any]] = []
    for row in unit_rows:
        unit_id = ids[row["id"]]
        unit = {
            "id": unit_id,
            "title": f"{unit_id} - {row['id']}",
            "status": "evidence-backed",
            "change": change_id,
            "delta": parse_delta(row["delta"]),
            "surfaces": list(row.get("surfaces") or []),
            "trace_ids": [change_id, row["id"]],
            "ears": [row["id"]],
            "sources": unit_sources(row, elements_by_id, change_id),
            "pattern": row["pattern"],
            "statement": row["statement"],
            "source": row["source"],
            "path": units_dir / f"{unit_id}.md",
        }
        write_text(unit["path"], render_spec_unit(project_id, unit, language))
        units.append(unit)
    active = {unit["path"] for unit in units}
    for stale in units_dir.glob("SPEC-U-*.md"):
        if stale not in active:
            remove(stale)

    from .change_functionalities import change_functionalities, functionalities_sha
    from .change_spec_doc import change_spec_context, render_change_spec_doc

    funs = change_functionalities(project_id, change_id, rows)
    specs_path = folder / "specs.md"
    write_text(specs_path, render_change_spec_doc(change_spec_context(project_id, change_id, units, funs), change_id))

    by_delta: dict[str, int] = {}
    for unit in units:
        by_delta[unit["delta"]] = by_delta.get(unit["delta"], 0) + 1
    unit_ids = [unit["id"] for unit in units]
    preserved = [row["id"] for row in preserved_rows]
    report = {"change_id": change_id, "units": unit_ids, "ears": [row["id"] for row in unit_rows],
              "deltas": {row["id"]: parse_delta(row["delta"]) for row in unit_rows},
              "preserved": preserved, "by_delta": by_delta}
    unit_of = {row["id"]: ids[row["id"]] for row in unit_rows}
    report["functionalities"] = {
        fun["id"]: {"key": fun["key"], "units": [unit_of[r] for r in fun["rows"] if r in unit_of]} for fun in funs}
    report["functionalities_sha"] = functionalities_sha(funs, unit_of)
    from .change_prd import write_change_prd

    prd = write_change_prd(project_id, change_id)
    if "skipped" in prd:
        report["prd_skipped"] = prd["skipped"]
    else:
        report["prd"] = prd
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

    result = {
        "project_id": project_id,
        "change_id": change_id,
        "path": specs_path.relative_to(base).as_posix(),
        "units": unit_ids,
        "functionalities": [fun["id"] for fun in funs],
        "preserved": preserved,
        "report": report,
        "next_step": text["next"].format(path=specs_path.relative_to(base).as_posix()),
    }
    if "skipped" in prd:
        result["prd_skipped"] = text["prd_skipped"].format(command=prd["skipped"])
    else:
        result["prd"] = prd["path"]
    return result
