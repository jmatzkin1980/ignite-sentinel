"""Sentinel ids: graph prefixes and the central registry of id families (IMP-249).

Every id family lives in `templates/id_families.json`: its pattern, an example, who
owns it and whether it is kept, new for v2 artifacts, or a view of another family
(`D-N.M` is a view of `DEC`). `/validate` consults the registry to resolve the ids
of structured citations (`citations.py`), and the schemas are tested against it.

Retired ids are recorded in `06_traceability/retired_ids.json` and never reused:
`next_id` skips them, and a citation to one is a finding.
"""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from .resources import read_package_json


@lru_cache(maxsize=1)
def id_registry() -> dict[str, Any]:
    return read_package_json("templates", "id_families.json")


ID_PREFIXES = tuple(id_registry()["graph_node_prefixes"])


def family_pattern(family: str) -> str:
    return str(id_registry()["families"][family]["pattern"])


@lru_cache(maxsize=1)
def _family_matchers() -> tuple[tuple[str, re.Pattern[str]], ...]:
    families = id_registry()["families"]
    # Longest pattern first, so SPEC-U wins over a shorter prefix that could also match.
    ordered = sorted(families, key=lambda name: len(families[name]["pattern"]), reverse=True)
    return tuple((name, re.compile(rf"^{families[name]['pattern']}$")) for name in ordered)


def split_release(value: str) -> tuple[int | None, str]:
    """`r2-RN-04` -> (2, "RN-04"); an id without the prefix -> (None, id)."""
    match = re.match(id_registry()["release_prefix"]["pattern"], value)
    if not match:
        return None, value
    return int(match.group("release")), value[match.end():]


def family_of(value: str) -> str | None:
    """The registered family of an id, or None. A release prefix is only valid on RN, CA and HU."""
    release, bare = split_release(value.strip())
    for name, matcher in _family_matchers():
        if matcher.match(bare):
            if release is not None and name not in id_registry()["release_prefix"]["families"]:
                return None
            return name
    return None


def catalog_key_kind(value: str) -> str | None:
    """error_code, event, flag or route, when `value` is a well-formed catalog key."""
    for kind, spec in id_registry()["catalog_keys"].items():
        if re.fullmatch(spec["pattern"], value):
            return kind
    return None


def graph_node_id_pattern() -> str:
    """The node id pattern the traceability schema must carry."""
    registry = id_registry()
    prefixes = "|".join(registry["graph_node_prefixes"])
    upserted = "|".join(family_pattern(name) for name in registry["graph_upserted_families"])
    return f"^(?:(?:{prefixes})-[0-9]{{3,}}|{upserted})$"


# --- retired ids ---------------------------------------------------------------


def retired_ids_path(base: Path) -> Path:
    return base / id_registry()["retired_ids_file"]


def load_retired_ids(base: Path) -> dict[str, dict[str, str]]:
    from .core.io import read_json

    data = read_json(retired_ids_path(base), {})
    return dict(data.get("retired", {})) if isinstance(data, dict) else {}


def retire_id(base: Path, value: str, reason: str, replacement: str | None = None) -> dict[str, str]:
    """Record a retired id. It stays retired: retiring it again keeps the first record."""
    from .core.io import write_json
    from .core.time import utc_now

    if family_of(value) is None:
        raise ValueError(f"{value!r} is not an id of a registered family.")
    if not reason.strip():
        raise ValueError("Retiring an id needs a reason.")
    retired = load_retired_ids(base)
    if value not in retired:
        retired[value] = {"reason": reason.strip(), "replacement": replacement or "", "retired_at": utc_now()}
        write_json(retired_ids_path(base), {"version": 1, "retired": dict(sorted(retired.items()))}, root=base)
    return retired[value]


def next_id(prefix: str, existing: list[str], retired: list[str] | set[str] | None = None) -> str:
    """Next `PREFIX-NNN`, above every existing and retired number: a retired id is never reused."""
    if prefix not in ID_PREFIXES:
        raise ValueError(f"Unsupported Sentinel id prefix: {prefix}")
    highest = 0
    marker = f"{prefix}-"
    for value in [*existing, *(retired or ())]:
        if value.startswith(marker):
            try:
                highest = max(highest, int(value.split("-", 1)[1]))
            except ValueError:
                continue
    return f"{prefix}-{highest + 1:03d}"


def workspace_id_from_path(path: Path) -> str:
    return path.name


def prefix_for_node_type(node_type: str) -> str:
    mapping = {
        "raw_input": "RAW",
        "requirement": "REQ",
        "gap_report": "GAP",
        "decision_log": "DEC",
        "decision": "DEC",
        "impact_report": "DEC",
        "gap_resolution_report": "DEC",
        "regeneration_diff": "DEC",
        "identity_seed_bank": "SEED",
        "identity_seed": "SEED",
        "discovery_log": "DISC",
        "lens_review": "DISC",
        "knowledge_ledger": "DISC",
        "assumption_register": "DISC",
        "agent_annotation": "DISC",
        "scrutiny_report": "DISC",
        "project_brief": "REQ",
        "ears_requirement": "REQ",
        "prd": "PRD",
        "prd_composition": "PRD",
        "backlog_refinement": "CHG",
        "story_status_change": "CHG",
        "story_acceptance_evidence": "EV",
        "spec": "SPEC",
        "spec_unit": "SPEC",
        "epic": "EPIC",
        "user_story": "US",
        "acceptance_criteria": "AC",
        "test_case": "TC",
        "backlog_readiness_audit": "QA",
        "change": "CHG",
        "context_request": "CTX",
    }
    return mapping.get(node_type, "")
