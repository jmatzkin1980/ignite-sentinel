"""IMP-429 (H27 inc 7d): the units of a change split by the release that builds them.

The confirmed series of a change (`02_requirements/CHG-nnn/series/`) says which §6.1 surfaces and build items each
release holds; the `SPEC-U` units of the change (`03_specs/CHG-nnn/units/`) say which surfaces they touch. A release
owns the units whose surfaces fall in its surfaces (or whose `trace_ids` name one of its `C-NN`). A unit owned by two
releases, or by none, stops the derivation before anything is written: the series is the truth and no release is
picked in silence.
"""
from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Any

from .core.io import write_text
from .errors import InputError
from .workspace import workspace_path

LAYERS = ("03_specs", "04_backlog")
_ITEM = re.compile(r"^C-\d+$", re.IGNORECASE)

TEXT = {
    "es": {
        "twice": "{unit} tiene dueño en dos releases ({a} y {b}) en la serie de {cid}: no se eligió ninguna; nada se escribió.",
        "never": "{unit} no tiene dueño: ninguna release de la serie de {cid} contiene sus superficies; nada se escribió.",
        "not_release": "{rid} no es una release de la serie de {cid} (las releases son {releases}).",
        "closed": "{rid} está cerrada en la serie de {cid}: no se deriva de nuevo.",
        "next_move": "/split {pid} --change {cid} --move --unit <C-NN> --from <rA> --to <rB> --reason \"...\" --ba \"...\" --tech \"...\"",
        "next_pick": "Elegí una de las releases abiertas: {open}.",
        "next_done": "/next {pid} --change {cid}",
    },
    "en": {
        "twice": "{unit} has an owner in two releases ({a} and {b}) in the series of {cid}: none was picked; nothing was written.",
        "never": "{unit} has no owner: no release of the series of {cid} holds its surfaces; nothing was written.",
        "not_release": "{rid} is not a release of the series of {cid} (the releases are {releases}).",
        "closed": "{rid} is already closed in the series of {cid}: it is not derived again.",
        "next_move": "/split {pid} --change {cid} --move --unit <C-NN> --from <rA> --to <rB> --reason \"...\" --ba \"...\" --tech \"...\"",
        "next_pick": "Pick one of the open releases: {open}.",
        "next_done": "/next {pid} --change {cid}",
    },
}


class ChangeReleaseError(InputError):
    """A unit of the change with two owners or none, a release the series does not have, a closed release."""


def _fold(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return " ".join(text.casefold().split())


def _text(project_id: str, change_id: str) -> dict[str, str]:
    from .changes import change_language, get_change

    return TEXT.get(change_language(project_id, get_change(project_id, change_id)), TEXT["es"])


def _series(project_id: str, change_id: str) -> tuple[list[str], dict[str, dict[str, set[str]]], dict[str, Any]]:
    """(release ids in partition order, per release its folded surfaces and C-NN ids, the partition)."""
    from .release_guide import _series as read_series

    partition, payload = read_series(workspace_path(project_id), change_id)
    held: dict[str, dict[str, set[str]]] = {}
    for release in payload.get("releases") or []:
        if not isinstance(release, dict):
            continue
        rid = str(release.get("id", "")).strip()
        surfaces: set[str] = set()
        items: set[str] = set()
        for entry in release.get("contains") or []:
            if not isinstance(entry, dict):
                continue
            if entry.get("item"):
                items.add(str(entry["item"]).strip().upper())
            elif entry.get("quote"):
                surfaces.add(_fold(entry["quote"]))
        held[rid] = {"surfaces": surfaces, "items": items}
    releases = [str(rid) for rid in partition.get("releases") or []]
    return releases, held, partition


def _owners(unit: dict[str, Any], releases: list[str], held: dict[str, dict[str, set[str]]]) -> list[str]:
    surfaces = [_fold(s) for s in unit.get("surfaces") or [] if str(s).strip()]
    items = {str(t).strip().upper() for t in unit.get("trace_ids") or [] if _ITEM.match(str(t).strip())}
    found: list[str] = []
    for rid in releases:
        mine = held.get(rid, {"surfaces": set(), "items": set()})
        if items & mine["items"] or any(s in mine["surfaces"] for s in surfaces):
            found.append(rid)
    if found:
        return found
    # no exact surface: a quote that contains the surface (or the other way round)
    return [rid for rid in releases
            if any(s and q and (s in q or q in s) for s in surfaces for q in held.get(rid, {}).get("surfaces", set()))]


def release_units(project_id: str, change_id: str) -> dict[str, list[str]]:
    """rid -> the `SPEC-U` ids it builds, in the partition's order; refuses a unit with two owners or none."""
    from .compilers.change_backlog import read_change_units

    text = _text(project_id, change_id)
    releases, held, _partition = _series(project_id, change_id)
    result: dict[str, list[str]] = {rid: [] for rid in releases}
    for unit in read_change_units(project_id, change_id):
        owners = _owners(unit, releases, held)
        if len(owners) > 1:
            raise ChangeReleaseError(
                text["twice"].format(unit=unit["id"], a=owners[0], b=owners[1], cid=change_id),
                next_step=text["next_move"].format(pid=project_id, cid=change_id))
        if not owners:
            raise ChangeReleaseError(
                text["never"].format(unit=unit["id"], cid=change_id),
                next_step=text["next_move"].format(pid=project_id, cid=change_id))
        result[owners[0]].append(unit["id"])
    return result


def closed_releases(project_id: str, change_id: str) -> list[str]:
    """The releases of the change's series that are closed, in the partition's order."""
    releases, _held, partition = _series(project_id, change_id)
    closed = partition.get("closed") or {}
    return [rid for rid in releases if rid in closed]


def release_dir(project_id: str, change_id: str, rid: str, layer: str) -> Path:
    if layer not in LAYERS:
        raise ValueError(f"layer must be one of {LAYERS}: {layer}")
    return workspace_path(project_id) / layer / change_id / rid


def derive_release_specs(project_id: str, change_id: str, rid: str, whole: dict[str, Any]) -> dict[str, Any]:
    """Write `03_specs/CHG/rid/{specs.md,units/}` from the change's compiled units (`whole` is that compile's result)."""
    from .compilers.change_spec_doc import change_spec_context, render_change_spec_doc
    from .compilers.change_functionalities import change_functionalities
    from .compilers.change_backlog import read_change_units

    text = _text(project_id, change_id)
    releases, _held, _partition = _series(project_id, change_id)
    if rid not in releases:
        raise ChangeReleaseError(text["not_release"].format(rid=rid, cid=change_id, releases=", ".join(releases)),
                                 next_step=text["next_pick"].format(open=", ".join(releases)))
    if rid in closed_releases(project_id, change_id):
        open_ones = [r for r in releases if r not in closed_releases(project_id, change_id)]
        raise ChangeReleaseError(text["closed"].format(rid=rid, cid=change_id),
                                 next_step=text["next_pick"].format(open=", ".join(open_ones) or "-")
                                 if open_ones else text["next_done"].format(pid=project_id, cid=change_id))
    mine = release_units(project_id, change_id)[rid]  # refuses before anything is written
    base = workspace_path(project_id)
    folder = release_dir(project_id, change_id, rid, "03_specs")
    units_dir = folder / "units"
    units_dir.mkdir(parents=True, exist_ok=True)
    source = base / "03_specs" / change_id / "units"
    for uid in mine:
        write_text(units_dir / f"{uid}.md", (source / f"{uid}.md").read_text(encoding="utf-8"))
    for stale in units_dir.glob("SPEC-U-*.md"):
        if stale.stem not in mine:
            stale.unlink()
    units = [u for u in read_change_units(project_id, change_id) if u["id"] in mine]
    ears = {u["ears"][0] for u in units if u["ears"]}
    funs = [f for f in change_functionalities(project_id, change_id) if any(r in ears for r in f["rows"])]
    # what a closed release before this one already delivered reads as preserved behavior, never as new units
    earlier = releases[:releases.index(rid)]
    every = release_units(project_id, change_id)
    delivered = {r: every[r] for r in closed_releases(project_id, change_id) if r in earlier and every.get(r)}
    write_text(folder / "specs.md",
               render_change_spec_doc(change_spec_context(project_id, change_id, units, funs, delivered), change_id))
    return {
        "project_id": project_id, "change_id": change_id, "status": "derived", "release": rid, "units": mine,
        "path": (folder / "specs.md").relative_to(base).as_posix(),
        "functionalities": [f["id"] for f in funs],
        "next_step": whole.get("next_step", ""),
    }
