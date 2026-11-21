"""IMP-388: a persistent id registry so SPEC-U ids stay stable once a workspace has changes.

Inactive (no `state["changes"]`): nothing is read or written and ids stay positional.
"""
from __future__ import annotations

import re

from .core.io import read_json, write_json
from .core.state import read_state
from .workspace import workspace_path

SCHEMA_VERSION = 1
_NUMBER = re.compile(r"-(\d+)$")


def registry_path(project_id: str):
    return workspace_path(project_id) / "06_traceability" / "id_registry.json"


def registry_active(project_id: str) -> bool:
    return bool(read_state(project_id).get("changes"))


def _load(project_id: str) -> dict:
    data = read_json(registry_path(project_id), {})
    if not isinstance(data, dict) or not isinstance(data.get("families"), dict):
        data = {"schema_version": SCHEMA_VERSION, "families": {}}
    return data


def _entry(data: dict, family: str) -> dict:
    entry = data["families"].setdefault(family, {"issued": {}, "last": 0})
    entry.setdefault("issued", {})
    try:
        last = int(entry.get("last", 0))
    except (TypeError, ValueError):
        last = 0  # a non-numeric value falls back to the highest issued number
    entry["last"] = max(last, _max_number(entry["issued"].values()))
    return entry


def _max_number(ids) -> int:
    numbers = [int(m.group(1)) for value in ids if (m := _NUMBER.search(str(value)))]
    return max(numbers, default=0)


def family_seeded(project_id: str, family: str) -> bool:
    return family in _load(project_id)["families"]


def assign_ids(project_id: str, family: str, keys: list[str]) -> dict[str, str]:
    data = _load(project_id)
    entry = _entry(data, family)
    result: dict[str, str] = {}
    for key in keys:
        if key not in entry["issued"]:
            entry["last"] += 1
            entry["issued"][key] = f"{family}-{entry['last']:03d}"
        result[key] = entry["issued"][key]
    write_json(registry_path(project_id), data)
    return result


def seed_family(project_id: str, family: str, issued: dict[str, str]) -> None:
    data = _load(project_id)
    entry = _entry(data, family)
    for key, value in issued.items():
        entry["issued"].setdefault(key, value)
    entry["last"] = max(entry["last"], _max_number(entry["issued"].values()))
    write_json(registry_path(project_id), data)
