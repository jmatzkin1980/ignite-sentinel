"""IMP-252: the brief v2 schema as data, and the project's brief settings.

`sentinel/templates/brief_v2.json` defines §0–§9 and the annexes of the brief v2:
for every subsection and sub-block, a stable id, en/es titles, its applicability
per profile (UI, API, BAT, INT, MIG, REG, MT) and per genesis, and its writing
contract. This module reads it and answers one question: for a project with
these profiles and this genesis, which places are required, conditional or N/A,
and how is each N/A written.

Combination rules (framework structure §4 and §5.2):

* Several profiles: the strongest mark wins (● over ◐ over —).
* Genesis ● makes a place required; genesis — makes it N/A, whatever the profile.
* Genesis Δ leaves the decision to the profile and changes how it is filled.
* Genesis ◐ with profile — stays N/A unless the condition holds.
* A composite subsection takes the strongest mark of its sub-blocks; an N/A
  sub-block never switches its parent off.
* MIG implies brownfield-replacement: MIG with another declared genesis is a
  contradiction. An initial load in greenfield is not MIG.
* Mixed genesis: the most demanding one is declared and the others noted.

The brief settings (`brief_profile`, `genesis`, `validation_direction`) live in
the project state. Discovery proposes them; the BA confirms them with
`/brief --profile ... --genesis ...`. Nothing is inferred silently.
"""
from __future__ import annotations

import re
from functools import lru_cache
from typing import Any, Iterable

from .core.time import utc_now
from .resources import read_package_json
from .workspace import read_state, update_state

SCHEMA_FILE = "brief_v2.json"
IDS_LOCK_FILE = "brief_v2_ids.lock.json"
STRENGTH = {"●": 2, "◐": 1, "—": 0}
MARK_NAME = {"●": "required", "◐": "conditional", "—": "n/a"}
SETTINGS_KEY = "brief_settings"
SETTINGS_GAP_ID = "GAP-BRIEF-PROFILE"


@lru_cache(maxsize=1)
def load_brief_schema() -> dict[str, Any]:
    return read_package_json("templates", SCHEMA_FILE)


def load_ids_lock() -> dict[str, Any]:
    return read_package_json("templates", IDS_LOCK_FILE)


def profile_order(schema: dict[str, Any] | None = None) -> list[str]:
    return list((schema or load_brief_schema())["profiles"]["order"])


def genesis_order(schema: dict[str, Any] | None = None) -> list[str]:
    return list((schema or load_brief_schema())["genesis"]["order"])


def subsections(schema: dict[str, Any] | None = None, *, annexes: bool = True) -> list[dict[str, Any]]:
    """The 55 numbered subsections in order, then the annexes. The §5 opening is not counted."""
    schema = schema or load_brief_schema()
    items = [sub for section in schema["sections"] for sub in section["subsections"]]
    return items + (list(schema["annexes"]) if annexes else [])


def schema_ids(schema: dict[str, Any] | None = None) -> list[str]:
    """Every stable id: subsections, the §5 opening, annexes and `subsection/block` sub-blocks."""
    schema = schema or load_brief_schema()
    ids: list[str] = []
    for section in schema["sections"]:
        if section.get("opening"):
            ids.append(section["opening"]["id"])
        for sub in section["subsections"]:
            ids.append(sub["id"])
            ids.extend(f"{sub['id']}/{block['key']}" for block in sub.get("blocks", []))
    for annex in schema["annexes"]:
        ids.append(annex["id"])
    return ids


def _strongest(marks: Iterable[str]) -> str:
    marks = list(marks)
    return max(marks, key=lambda mark: STRENGTH[mark]) if marks else "—"


def profile_mark(profiles_string: str, profiles: list[str], order: list[str]) -> str:
    return _strongest(profiles_string[order.index(profile)] for profile in profiles)


def combine(profile: str, genesis: str | None) -> tuple[str, bool]:
    """(mark, fill_changes) after applying the genesis mark to the profile mark."""
    if genesis in (None, "·"):
        return profile, False
    if genesis == "●":
        return "●", False
    if genesis == "—":
        return "—", False
    if genesis == "Δ":
        return profile, profile != "—"
    # genesis ◐: the profile decides when it is ● or —; otherwise conditional
    return profile, False


def resolve_genesis(declared: list[str] | str, schema: dict[str, Any] | None = None) -> dict[str, Any]:
    """The most demanding declared genesis, with the others noted."""
    order = (schema or load_brief_schema())["genesis"]["demand"]
    values = [declared] if isinstance(declared, str) else list(declared)
    unknown = [value for value in values if value not in order]
    if unknown:
        raise ValueError(f"unknown genesis: {', '.join(unknown)}; use one of {', '.join(order)}")
    if not values:
        raise ValueError("declare a genesis")
    winner = max(values, key=order.index)
    return {"genesis": winner, "also": [value for value in dict.fromkeys(values) if value != winner]}


def settings_issues(profiles: list[str], genesis: str | None, validation_direction: str | None = None,
                    schema: dict[str, Any] | None = None) -> list[str]:
    schema = schema or load_brief_schema()
    issues: list[str] = []
    order = profile_order(schema)
    unknown = [profile for profile in profiles if profile not in order]
    if unknown:
        issues.append(f"unknown profile: {', '.join(unknown)}; use {', '.join(order)}")
    if not profiles:
        issues.append("declare at least one profile")
    if genesis is not None and genesis not in genesis_order(schema):
        issues.append(f"unknown genesis: {genesis}; use {', '.join(genesis_order(schema))}")
    implied = schema["genesis"]["implied_by_profile"]
    for profile, required in implied.items():
        if profile in profiles and genesis is not None and genesis != required:
            issues.append(f"contradiction: profile {profile} implies genesis {required}, declared {genesis} "
                          "(an initial load in greenfield is not MIG)")
    if validation_direction is not None and validation_direction not in schema["validation_directions"]:
        issues.append(f"unknown validation direction: {validation_direction}; use {', '.join(schema['validation_directions'])}")
    return issues


def applicability(profiles: list[str], genesis: str, schema: dict[str, Any] | None = None) -> dict[str, Any]:
    """Required / conditional / N/A for every subsection and sub-block, with the grouped N/A lines."""
    schema = schema or load_brief_schema()
    issues = settings_issues(profiles, genesis, schema=schema)
    if any(not issue.startswith("contradiction") for issue in issues):
        raise ValueError("; ".join(issues))
    order = profile_order(schema)
    gpos = genesis_order(schema).index(genesis)
    entries: dict[str, dict[str, Any]] = {}
    for sub in subsections(schema):
        blocks = {}
        for block in sub.get("blocks", []):
            mark, fill = combine(profile_mark(block["profiles"], profiles, order), (block.get("genesis") or "·" * 4)[gpos])
            blocks[block["key"]] = {"mark": MARK_NAME[mark], "symbol": mark,
                                    **({"fill_note": block["genesis_note"]} if fill else {})}
        if blocks:
            symbol = _strongest(item["symbol"] for item in blocks.values())
            fill = False
        else:
            symbol, fill = combine(profile_mark(sub["profiles"], profiles, order), (sub.get("genesis") or "·" * 4)[gpos])
        entry = {"mark": MARK_NAME[symbol], "symbol": symbol}
        if fill:
            entry["fill_note"] = sub["genesis_note"]
        if blocks:
            entry["blocks"] = blocks
        entries[sub["id"]] = entry
    na_ids = {sid for sid, entry in entries.items() if entry["symbol"] == "—"}
    na_ids |= {f"{sid}/{key}" for sid, entry in entries.items() for key, block in entry.get("blocks", {}).items()
               if block["symbol"] == "—" and entry["symbol"] != "—"}
    na_lines, grouped = [], set()
    for group in schema["na_groups"]:
        members = [member for member in group["members"] if member in na_ids and member not in grouped]
        if members:
            grouped.update(members)
            na_lines.append({"group": group["key"], "members": members, "line": group["line"]})
    ungrouped = sorted(na_ids - grouped)
    summary = {name: sum(1 for entry in entries.values() if entry["mark"] == name) for name in ("required", "conditional", "n/a")}
    return {"profiles": profiles, "genesis": genesis, "entries": entries, "summary": summary,
            "na_lines": na_lines, "na_ungrouped": ungrouped, "issues": issues}


def validate_schema(schema: dict[str, Any] | None = None) -> list[str]:
    """Structural problems in the schema: what /doctor and the tests guard."""
    schema = schema or load_brief_schema()
    problems: list[str] = []
    order, gorder = profile_order(schema), genesis_order(schema)
    ids = schema_ids(schema)
    if len(ids) != len(set(ids)):
        problems.append("duplicate ids")

    def check_marks(owner: str, item: dict[str, Any]) -> None:
        profiles = item.get("profiles", "")
        if len(profiles) != len(order) or any(mark not in STRENGTH for mark in profiles):
            problems.append(f"{owner}: profiles must be {len(order)} marks among ●◐—")
        genesis = item.get("genesis")
        if genesis is not None:
            if len(genesis) != len(gorder) or any(mark not in "●◐—Δ·" for mark in genesis):
                problems.append(f"{owner}: genesis must be {len(gorder)} marks among ●◐—Δ·")
            if not item.get("genesis_note"):
                problems.append(f"{owner}: a genesis effect needs its note")

    for section in schema["sections"]:
        previous = 0
        for sub in section["subsections"]:
            match = re.fullmatch(rf"{section['id']}\.(\d+)", sub["id"])
            if not match or int(match.group(1)) <= previous:
                problems.append(f"{sub['id']}: ids are numbered in order inside §{section['id']}")
            previous = int(match.group(1)) if match else previous
            for lang in ("es", "en"):
                if not sub["title"].get(lang):
                    problems.append(f"{sub['id']}: missing {lang} title")
            if sub.get("blocks"):
                if "profiles" in sub:
                    problems.append(f"{sub['id']}: a composite takes its marks from its blocks")
                for block in sub["blocks"]:
                    check_marks(f"{sub['id']}/{block['key']}", block)
            else:
                check_marks(sub["id"], sub)
            contract = sub.get("contract", {})
            if not contract.get("produces") or contract.get("missing") not in {"client", "domain"}:
                problems.append(f"{sub['id']}: the writing contract needs produces and missing (client|domain)")
    for annex in schema["annexes"]:
        check_marks(annex["id"], annex)
    known = set(ids)
    for group in schema["na_groups"]:
        for member in group["members"]:
            if member not in known:
                problems.append(f"na group {group['key']}: unknown member {member}")
        if not group["line"].get("es") or not group["line"].get("en"):
            problems.append(f"na group {group['key']}: needs the es and en counterfactual")
    return problems


def ids_lock_problems(schema: dict[str, Any] | None = None, lock: dict[str, Any] | None = None) -> list[str]:
    """The evolution policy: ids are never renumbered, renamed or reused (golden of ids)."""
    schema = schema or load_brief_schema()
    lock = lock or load_ids_lock()
    current = schema_ids(schema)
    tombstones = {item["id"] for item in schema["evolution"].get("tombstones", [])}
    problems = []
    for locked in lock["ids"]:
        if locked not in current and locked not in tombstones:
            problems.append(f"id {locked} disappeared: retire it with a tombstone, never delete or renumber")
    for retired in tombstones:
        if retired in current:
            problems.append(f"id {retired} is a tombstone and cannot be reused")
    new = [item for item in current if item not in lock["ids"]]
    if new:
        problems.append(f"new ids not in {IDS_LOCK_FILE}: {', '.join(new)} (append them; never insert or renumber)")
    return problems


# --- project brief settings -------------------------------------------------

_PROFILE_CUES = {
    "UI": r"\b(pantalla|pantallas|screen|screens|ui|dashboard|formulario|form|frontend|vista|portal)\b",
    "API": r"\b(api|endpoint|endpoints|rest|graphql|webhook)\b",
    "BAT": r"\b(batch|lote|lotes|archivo diario|nightly|job programado|scheduled job|pipeline|etl)\b",
    "INT": r"\b(integraci[oó]n|integration|tercero|terceros|third[- ]party|proveedor externo)\b",
    "MIG": r"\b(migraci[oó]n|migration|legado|legacy|reemplaza|replace[sd]?)\b",
    "REG": r"\b(normativa|regulat\w*|regulaci[oó]n|compliance|bcra|gdpr|ley)\b",
    "MT": r"\b(multi[- ]?tenant|tenant|tenants|multi[- ]?cliente)\b",
}
_GENESIS_CUES = [
    ("brownfield-replacement", r"\b(reemplaza\w*|replace\w*|migraci[oó]n|migration|legado|legacy)\b"),
    ("brownfield-extension", r"\b(extend\w*|ampl[ií]a\w*|agregar a|sistema existente|existing system)\b"),
    ("brownfield-integration", r"\b(consum\w+|integra\w*)\b.*\b(existente|existing)\b"),
]


def propose_brief_settings(text: str) -> dict[str, Any]:
    """A proposal from the raw input, never applied: the BA confirms it."""
    folded = text.lower()
    profiles = [profile for profile, cue in _PROFILE_CUES.items() if re.search(cue, folded)]
    genesis = next((value for value, cue in _GENESIS_CUES if re.search(cue, folded)), "greenfield")
    if "MIG" in profiles:
        genesis = "brownfield-replacement"
    return {"profiles": profiles or ["UI"], "genesis": genesis, "validation_direction": "to-build",
            "basis": "keyword cues in the raw input; a proposal to confirm, never applied"}


def brief_settings(project_id: str) -> dict[str, Any]:
    settings = read_state(project_id).get(SETTINGS_KEY)
    return settings if isinstance(settings, dict) else {}


def set_brief_settings(project_id: str, *, profiles: list[str] | None = None, genesis: list[str] | str | None = None,
                       validation_direction: str | None = None) -> dict[str, Any]:
    """Record what the BA confirmed. Missing values keep the previous confirmation."""
    current = brief_settings(project_id)
    new_profiles = [p.strip().upper() for p in profiles if p.strip()] if profiles is not None else current.get("profiles")
    resolved = resolve_genesis(genesis) if genesis is not None else None
    new_genesis = resolved["genesis"] if resolved else current.get("genesis")
    new_direction = validation_direction if validation_direction is not None else current.get("validation_direction", "to-build")
    issues = settings_issues(new_profiles or [], new_genesis, new_direction)
    blocking = [issue for issue in issues if not issue.startswith("contradiction")]
    if blocking:
        raise ValueError("; ".join(blocking))
    settings = {
        "profiles": new_profiles or [],
        "genesis": new_genesis,
        "genesis_also": resolved["also"] if resolved else current.get("genesis_also", []),
        "validation_direction": new_direction,
        "confirmed_by": "ba",
        "confirmed_at": utc_now(),
        "contradictions": [issue for issue in issues if issue.startswith("contradiction")],
        "release_overrides": current.get("release_overrides", {}),
    }
    update_state(project_id, **{SETTINGS_KEY: settings})
    return settings


def settings_status(project_id: str, raw_text: str = "") -> dict[str, Any]:
    """Whether profile and genesis are confirmed, and the blocking gap a v2 brief opens otherwise."""
    settings = brief_settings(project_id)
    missing = [key for key in ("profiles", "genesis") if not settings.get(key)]
    status: dict[str, Any] = {"confirmed": not missing and not settings.get("contradictions"), "settings": settings, "missing": missing}
    if settings.get("contradictions"):
        status["contradictions"] = settings["contradictions"]
    if not status["confirmed"]:
        status["proposal"] = propose_brief_settings(raw_text)
        status["gap"] = {
            "id": SETTINGS_GAP_ID, "severity": "critical", "blocking": True, "owner": "BA",
            "question": "Confirm the brief profile(s) and genesis: /brief PROJECT_ID --profile UI,REG --genesis greenfield",
            "reason": "contradiction between profile and genesis" if settings.get("contradictions") else f"not confirmed: {', '.join(missing)}",
        }
    else:
        status["applicability"] = applicability(settings["profiles"], settings["genesis"])["summary"]
    return status


def effective_validation_direction(project_id: str, config: dict[str, Any]) -> str:
    """The BA-confirmed direction wins over `validation_direction:` in sentinel.config.yaml."""
    confirmed = brief_settings(project_id).get("validation_direction")
    return str(confirmed or config.get("validation_direction") or "to-build")
