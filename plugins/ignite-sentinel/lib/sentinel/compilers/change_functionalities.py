"""IMP-416: the functionalities of a change, grouped by the border surface their rows name.

One owner of the grouping (FUN-nn), so specs, backlog and readiness do not each compute their own.
The id is positional per change and never goes to the global registry; the stable handle is ``key``.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

from ..change_requirements import _fold_name, load_change_ears, parse_delta, parse_surfaces
from ..changes import get_change
from ..slicing_model import load_slicing_model
from .change_deliverable import ROW_PLACES, _EXT_SOURCE, _FIRST_CODE, _template, row_lens
from .change_specs import UNIT_DELTAS


def _surface_item(border: list[dict], name: str) -> dict | None:
    return next((item for item in border if item.get("name") == name), None)


def _item_key(item: dict) -> str:
    return f"{item.get('type', '')}:{_fold_name(item.get('name', ''))}"


def functionality_key(row: dict, border: list[dict], template: dict) -> tuple[str, dict | None]:
    """(stable key, border item) of a row: its first valid surface; without one, its v2 place.

    A row with no valid surface has no surface type, so its lens is always `business` and its place `2.2`: every
    surface-less row of the change shares the one `lugar:2.2` functionality (it is split afterwards by delta, SPIDR axis
    and the size of the slicing model). Grouping them by the place of their request element is not done on purpose:
    it would change the grouping, ids and sha of every existing change."""
    valid, _unknown = parse_surfaces(";".join(row.get("surfaces") or []), border)
    for name in valid[:1]:
        item = _surface_item(border, name)
        if item is not None:
            return _item_key(item), item
    return f"lugar:{ROW_PLACES[row_lens(row, border, template)]}", None


def change_functionalities(project_id: str, change_id: str, rows: list[dict] | None = None) -> list[dict]:
    border = list(get_change(project_id, change_id).get("border") or [])
    template = _template()
    every = load_change_ears(project_id, change_id) if rows is None else list(rows)
    groups: dict[str, dict[str, Any]] = {}
    for row in every:
        if parse_delta(row["delta"]) not in UNIT_DELTAS:
            continue
        key, item = functionality_key(row, border, template)
        group = groups.setdefault(key, {"key": key, "item": item, "rows": []})
        group["rows"].append(row)

    def order(group: dict) -> tuple:
        item = group["item"]
        if item is None:
            return (1, False, "", "", group["key"])
        return (0, item.get("zone") != "nuevo", _fold_name(item.get("type", "")), _fold_name(item.get("name", "")), "")

    ordered = sorted(groups.values(), key=order)
    ids = {group["key"]: f"FUN-{n:02d}" for n, group in enumerate(ordered, 1)}
    funs: list[dict] = []
    for group in ordered:
        item = group["item"] or {}
        names: list[str] = []
        for row in group["rows"]:
            for name in parse_surfaces(";".join(row.get("surfaces") or []), border)[0]:
                if name not in names:
                    names.append(name)
        preserved = [
            other["id"] for other in every
            if parse_delta(other["delta"]) == "UNCHANGED"
            and set(parse_surfaces(";".join(other.get("surfaces") or []), border)[0]) & set(names)
        ]
        depends: list[str] = []
        for name in names:
            other = _surface_item(border, name)
            if other is None or other.get("zone") != "nuevo":
                continue
            other_key = _item_key(other)
            fun_id = ids.get(other_key)
            if fun_id and other_key != group["key"] and fun_id not in depends:
                depends.append(fun_id)
        elements: list[str] = []
        gaps: list[str] = []
        for row in group["rows"]:
            found = _EXT_SOURCE.match(str(row.get("source", "")))
            if found:
                if found.group(1) not in elements:
                    elements.append(found.group(1))
                continue
            code = _FIRST_CODE.search(str(row.get("source", "")))
            if code and code.group(1).startswith("GAP-") and code.group(1) not in gaps:
                gaps.append(code.group(1))
        funs.append({
            "id": ids[group["key"]], "key": group["key"],
            "type": str(item.get("type", "")), "name": str(item.get("name", "")),
            "zone": str(item.get("zone", "")), "origin": str(item.get("origin", "")),
            "place": ROW_PLACES[row_lens(group["rows"][0], border, template)],
            "rows": [row["id"] for row in group["rows"]], "preserved": preserved,
            "surfaces": names, "elements": elements, "gaps": gaps, "depends_on": depends,
        })
    return funs


def functionalities_sha(funs: list[dict], unit_of: dict[str, str]) -> str:
    """16 hex digits over [[FUN, key, [SPEC-U...]]...]: changes when the grouping or its units change."""
    payload = [[fun["id"], fun["key"], [unit_of[r] for r in fun["rows"] if r in unit_of]] for fun in funs]
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False).encode("utf-8")).hexdigest()[:16]


def story_size(model: dict | None = None) -> int:
    """The most units one change story carries (slicing model ``story_size.max_units``)."""
    return int((model if model is not None else load_slicing_model())["story_size"]["max_units"])
