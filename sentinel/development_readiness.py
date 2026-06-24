from __future__ import annotations

import re
from typing import Any

from .assumptions import load_assumptions
from .core.markdown import parse_table_rows
from .discovery import mature_requirement_rubric
from .gaps import parse_gap_table
from .lens_registry import LENS_ORDER, load_lens_checks
from .workspace import read_json, workspace_path, write_json

READINESS_STATUSES = ("CONFIRMED", "ASSUMED", "OPEN")
DEFAULT_THRESHOLD = 0.75
STATUS_WEIGHTS = {
    "CONFIRMED": 1.0,
    "ASSUMED": 0.65,
    "OPEN": 0.0,
}

# IMP-118: per Requirement Unit implementability statuses. A cell is OPEN only
# when the missing information is non-inferable and necessary to implement;
# DEFERRED_TO_CONTEXT marks unknowns that a domain context pack can still
# deepen later, so they do not count as OPEN and do not block small units.
IMPLEMENTABILITY_STATUSES = ("CONFIRMED", "DEFERRED_TO_CONTEXT", "OPEN")
# Lens checks whose evidence reads the client's own requirement text are
# non-inferable: only the client can answer them. Every other scope
# (technical/design/quality/frontend) is a domain dimension that a context pack
# is expected to deepen, hence discoverable rather than blocking.
NON_INFERABLE_SCOPE = "source"
_UNRESOLVED_GAP_STATUSES = {"OPEN", "ANSWERED", "PARTIALLY_CLOSED", "NEW_GAP"}


def compute_development_readiness(project_id: str, persist: bool = False) -> dict[str, Any]:
    """Compute the development certainty matrix from governed discovery knowledge.

    The matrix is derived only from local ledger/gap/assumption artifacts. It
    does not infer missing content: if an area cannot be grounded in a confirmed
    or assumed knowledge unit, the cell remains OPEN with explicit pending input.
    """
    base = workspace_path(project_id)
    ledger = read_json(base / "01_discovery" / "knowledge_state.json", {}) or {}
    units = [unit for unit in ledger.get("units", []) if isinstance(unit, dict)]
    assumptions = load_assumptions(project_id)
    matrix = build_readiness_matrix(project_id, units, assumptions)
    summary = summarize_matrix(matrix)
    payload = {
        "project_id": project_id,
        "artifact": "development_readiness",
        "version": 1,
        "threshold": DEFAULT_THRESHOLD,
        "statuses": list(READINESS_STATUSES),
        "summary": summary,
        "matrix": matrix,
        # IMP-118: maturity as agent implementability, scoped per Requirement
        # Unit × lens. Additive; the rubric matrix/summary above are unchanged.
        "unit_implementability": compute_unit_implementability(project_id),
    }
    if persist:
        out = base / "01_discovery" / "development_readiness.json"
        write_json(out, payload)
    return payload


def build_readiness_matrix(
    project_id: str,
    units: list[dict[str, Any]],
    assumptions: list[dict[str, str]],
) -> list[dict[str, Any]]:
    matrix: list[dict[str, Any]] = []
    for index, item in enumerate(mature_requirement_rubric(), start=1):
        area_id = f"DRA-{index:02d}"
        gap_ids = gap_ids_for(item.get("gap_when_missing", ""))
        lenses = lenses_for(item.get("lens", "product"))
        cells = [
            readiness_cell(project_id, area_id, item, lens, gap_ids, units, assumptions)
            for lens in lenses
        ]
        matrix.append(
            {
                "area_id": area_id,
                "area": item.get("area", ""),
                "mature_signal": item.get("mature_signal", ""),
                "gap_when_missing": item.get("gap_when_missing", ""),
                "lenses": cells,
                "status": aggregate_status([cell["status"] for cell in cells]),
                "score": round(sum(float(cell["score"]) for cell in cells) / len(cells), 3) if cells else 0.0,
            }
        )
    return matrix


def readiness_cell(
    project_id: str,
    area_id: str,
    item: dict[str, str],
    lens: str,
    gap_ids: list[str],
    units: list[dict[str, Any]],
    assumptions: list[dict[str, str]],
) -> dict[str, Any]:
    linked_assumptions = [
        row for row in assumptions
        if row.get("closes_gap") in gap_ids
        or (not gap_ids and normalize_lens(row.get("lens", "")) == lens)
    ]
    if linked_assumptions:
        assumption = linked_assumptions[0]
        status = "ASSUMED"
        evidence = {
            "trace_id": "assumption_register",
            "quote": assumption.get("justification", ""),
            "assumption_id": assumption.get("id", ""),
            "owner": assumption.get("owner", ""),
            "risk": assumption.get("risk", "med"),
        }
        links = compact_links(
            [
                {"type": "assumption", "target": assumption.get("id")},
                {"type": "gap", "target": assumption.get("closes_gap")},
                {"type": "area", "target": area_id},
            ]
        )
    else:
        gap_units = [unit for unit in units if unit_has_any_gap(unit, gap_ids)]
        open_gap = next((unit for unit in gap_units if unit.get("status") == "OPEN"), None)
        confirmed_gap = next((unit for unit in gap_units if unit.get("status") == "CONFIRMED"), None)
        lens_confirmed = next(
            (
                unit for unit in units
                if normalize_lens(str(unit.get("lens", ""))) == lens
                and unit.get("status") in {"CONFIRMED", "INFERRED"}
                and has_evidence(unit)
            ),
            None,
        )
        if open_gap:
            status = "OPEN"
            evidence = evidence_from_unit(open_gap)
            links = compact_links(
                [{"type": "gap", "target": gap} for gap in gap_ids]
                + [{"type": "area", "target": area_id}]
            )
        elif confirmed_gap:
            status = "CONFIRMED"
            evidence = evidence_from_unit(confirmed_gap)
            links = compact_links(confirmed_gap.get("links", []) + [{"type": "area", "target": area_id}])
        elif lens_confirmed:
            status = "CONFIRMED"
            evidence = evidence_from_unit(lens_confirmed)
            links = compact_links(lens_confirmed.get("links", []) + [{"type": "area", "target": area_id}])
        else:
            status = "OPEN"
            evidence = {"note": "[PENDING INPUT]"}
            links = compact_links(
                [{"type": "gap", "target": gap} for gap in gap_ids]
                + [{"type": "area", "target": area_id}]
            )

    risk = str(evidence.get("risk", "")) if isinstance(evidence, dict) else ""
    return {
        "project_id": project_id,
        "area_id": area_id,
        "area": item.get("area", ""),
        "lens": lens,
        "status": status,
        "score": STATUS_WEIGHTS[status],
        "evidence": evidence,
        "links": links,
        "counts_as_open": bool(status == "OPEN"),
        "risk": risk,
    }


def summarize_matrix(matrix: list[dict[str, Any]]) -> dict[str, Any]:
    cells = [cell for area in matrix for cell in area.get("lenses", []) if isinstance(cell, dict)]
    by_status = {status: 0 for status in READINESS_STATUSES}
    by_lens: dict[str, dict[str, int]] = {}
    high_risk_assumptions: list[str] = []
    for cell in cells:
        status = str(cell.get("status", "OPEN"))
        by_status[status] = by_status.get(status, 0) + 1
        lens = str(cell.get("lens", "product"))
        by_lens.setdefault(lens, {s: 0 for s in READINESS_STATUSES})
        by_lens[lens][status] = by_lens[lens].get(status, 0) + 1
        evidence = cell.get("evidence", {}) if isinstance(cell.get("evidence"), dict) else {}
        if status == "ASSUMED" and evidence.get("risk") == "high":
            high_risk_assumptions.append(str(evidence.get("assumption_id", "")))
    score = round(sum(float(cell.get("score", 0.0)) for cell in cells) / len(cells), 3) if cells else 0.0
    lens_scores: dict[str, float] = {}
    for lens in sorted(by_lens):
        lens_cells = [cell for cell in cells if cell.get("lens") == lens]
        lens_scores[lens] = round(sum(float(cell.get("score", 0.0)) for cell in lens_cells) / len(lens_cells), 3)
    open_cells = by_status.get("OPEN", 0)
    assumed_cells = by_status.get("ASSUMED", 0)
    verdict = crystallization_verdict(score, open_cells, assumed_cells)
    return {
        "areas_total": len(matrix),
        "cells_total": len(cells),
        "by_status": by_status,
        "by_lens": by_lens,
        "lens_scores": lens_scores,
        "global_score": score,
        "open_cells": open_cells,
        "assumed_cells": assumed_cells,
        "high_risk_assumption_ids": sorted(set(filter(None, high_risk_assumptions))),
        "crystallization_gate": verdict,
    }


def crystallization_verdict(score: float, open_cells: int, assumed_cells: int) -> dict[str, Any]:
    if open_cells > 0:
        state = "NOT_READY_OPEN_UNCERTAINTY"
        ready = False
        rationale = "Open matrix cells remain; keep gaps explicit before development handoff."
    elif score < DEFAULT_THRESHOLD:
        state = "NOT_READY_LOW_CERTAINTY"
        ready = False
        rationale = "The score is below the development certainty threshold."
    elif assumed_cells > 0:
        state = "READY_WITH_GOVERNED_ASSUMPTIONS"
        ready = True
        rationale = "No open cells remain, but governed assumptions must stay visible with owner and risk."
    else:
        state = "READY_LOW_UNCERTAINTY"
        ready = True
        rationale = "All matrix cells are confirmed above the development certainty threshold."
    return {
        "state": state,
        "ready_for_development": ready,
        "threshold": DEFAULT_THRESHOLD,
        "rationale": rationale,
    }


def gap_ids_for(text: str) -> list[str]:
    return sorted(set(re.findall(r"GAP-[A-Z0-9-]+", text)))


def lenses_for(text: str) -> list[str]:
    mapped = [normalize_lens(part) for part in re.split(r"[/,]", text) if part.strip()]
    mapped = [lens for lens in mapped if lens]
    return sorted(set(mapped)) or ["product"]


def normalize_lens(value: str) -> str:
    lens = value.strip().lower()
    aliases = {
        "technology": "technical",
        "frontend": "technical",
        "backend": "technical",
        "business": "business",
        "product": "product",
        "quality": "quality",
        "design": "design",
        "compliance": "compliance",
        "delivery": "delivery",
    }
    return aliases.get(lens, lens or "product")


def unit_has_any_gap(unit: dict[str, Any], gap_ids: list[str]) -> bool:
    links = unit.get("links", [])
    for link in links if isinstance(links, list) else []:
        if isinstance(link, dict) and link.get("type") == "gap" and link.get("target") in gap_ids:
            return True
    text = " ".join(str(unit.get(key, "")) for key in ("statement", "id"))
    return any(gap in text for gap in gap_ids)


def evidence_from_unit(unit: dict[str, Any]) -> dict[str, str]:
    evidence = unit.get("evidence", {}) if isinstance(unit.get("evidence"), dict) else {}
    if evidence.get("note"):
        return {"note": str(evidence["note"])}
    return {
        "trace_id": str(evidence.get("trace_id", "")),
        "quote": str(evidence.get("quote", "")),
    }


def has_evidence(unit: dict[str, Any]) -> bool:
    evidence = unit.get("evidence", {}) if isinstance(unit.get("evidence"), dict) else {}
    return bool(evidence.get("trace_id") and evidence.get("quote"))


def aggregate_status(statuses: list[str]) -> str:
    if any(status == "OPEN" for status in statuses):
        return "OPEN"
    if any(status == "ASSUMED" for status in statuses):
        return "ASSUMED"
    return "CONFIRMED"


def compact_links(links: list[dict[str, Any]]) -> list[dict[str, str]]:
    compacted: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for link in links:
        link_type = str(link.get("type", "")).strip()
        target = str(link.get("target", "")).strip()
        if not link_type or not target or target in {"-", "N/A"}:
            continue
        key = (link_type, target)
        if key in seen:
            continue
        seen.add(key)
        compacted.append({"type": link_type, "target": target})
    return compacted


# --- IMP-118: per Requirement Unit implementability matrix + soft gate --------
#
# Madurez = implementabilidad por agente. For each Requirement Unit (RU,
# IMP-115) the matrix answers, per lens, whether the unit can be implemented
# from current discovery evidence. The status of a cell is driven by the RU's
# anchored, still-open gaps (IMP-116 ``Unit`` column in ``gaps.md``):
#
#   OPEN                -> a non-inferable, client-owned gap blocks the lens
#                          (only the client can answer; the unit is not
#                          implementable on that lens yet).
#   DEFERRED_TO_CONTEXT -> the only remaining gaps are domain dimensions a
#                          context pack can deepen later; discoverable, not
#                          blocking — a small unit still advances.
#   CONFIRMED           -> no open gap anchored to the unit on that lens.
#
# The classification reuses each lens check's declarative ``evidence_scope``
# (``source`` == non-inferable; domain scopes == discoverable). Nothing here
# touches the rubric matrix or ``crystallization_gate``; it is additive.


def gap_scope_index() -> dict[str, str]:
    """Map each declarative gap id to its lens check ``evidence_scope``."""
    return {
        str(check["id"]): str(check.get("evidence_scope", "source"))
        for check in load_lens_checks()
    }


def classify_unit_gap(gap: dict[str, str], scope_index: dict[str, str]) -> str:
    """OPEN (non-inferable) vs DEFERRED_TO_CONTEXT (domain-discoverable)."""
    scope = scope_index.get(str(gap.get("id", "")).strip("`"), "")
    if not scope:
        # Unknown/agentic gap with no registry scope: business and product
        # findings are about the client requirement itself (non-inferable);
        # domain lenses are deepened by their context packs.
        lens = normalize_lens(str(gap.get("lens", "")))
        scope = NON_INFERABLE_SCOPE if lens in {"business", "product"} else "technical"
    return "OPEN" if scope == NON_INFERABLE_SCOPE else "DEFERRED_TO_CONTEXT"


def parse_requirement_units(path) -> list[dict[str, str]]:
    """Read the cited Requirement Units from ``requirement_units.md`` (IMP-115)."""
    if not path.exists():
        return []
    units: list[dict[str, str]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        rows = parse_table_rows(line)
        cells = rows[0] if rows else []
        if not cells or not cells[0].startswith("RU-"):
            continue
        units.append(
            {
                "id": cells[0],
                "label": cells[1] if len(cells) > 1 else "",
                "evidence_mention": cells[2] if len(cells) > 2 else "",
            }
        )
    return units


def unit_readiness(statuses: list[str]) -> str:
    if any(status == "OPEN" for status in statuses):
        return "NOT_IMPLEMENTABLE"
    if any(status == "DEFERRED_TO_CONTEXT" for status in statuses):
        return "DEFERRED_TO_CONTEXT"
    return "IMPLEMENTABLE"


def build_unit_implementability_matrix(
    units: list[dict[str, str]],
    gaps: list[dict[str, str]],
    scope_index: dict[str, str],
) -> list[dict[str, Any]]:
    """Per RU × lens implementability cells derived from anchored open gaps."""
    unresolved = [
        gap
        for gap in gaps
        if str(gap.get("status", "OPEN")).strip("`").upper() in _UNRESOLVED_GAP_STATUSES
    ]
    matrix: list[dict[str, Any]] = []
    for unit in units:
        unit_id = str(unit.get("id", "")).strip()
        unit_gaps = [
            gap for gap in unresolved
            if str(gap.get("unit", "")).strip().strip("`") == unit_id
        ]
        cells: list[dict[str, Any]] = []
        for lens in LENS_ORDER:
            lens_gaps = [
                gap for gap in unit_gaps
                if normalize_lens(str(gap.get("lens", ""))) == lens
            ]
            classes = [classify_unit_gap(gap, scope_index) for gap in lens_gaps]
            if "OPEN" in classes:
                status = "OPEN"
            elif "DEFERRED_TO_CONTEXT" in classes:
                status = "DEFERRED_TO_CONTEXT"
            else:
                status = "CONFIRMED"
            cells.append(
                {
                    "lens": lens,
                    "status": status,
                    "gaps": [str(gap.get("id", "")).strip("`") for gap in lens_gaps],
                }
            )
        matrix.append(
            {
                "unit_id": unit_id,
                "label": unit.get("label", ""),
                "evidence_mention": unit.get("evidence_mention", ""),
                "lenses": cells,
                "readiness": unit_readiness([cell["status"] for cell in cells]),
                "open_lenses": [cell["lens"] for cell in cells if cell["status"] == "OPEN"],
                "deferred_lenses": [
                    cell["lens"] for cell in cells if cell["status"] == "DEFERRED_TO_CONTEXT"
                ],
            }
        )
    return matrix


def summarize_unit_implementability(matrix: list[dict[str, Any]]) -> dict[str, Any]:
    implementable = [row["unit_id"] for row in matrix if row["readiness"] == "IMPLEMENTABLE"]
    deferred = [row["unit_id"] for row in matrix if row["readiness"] == "DEFERRED_TO_CONTEXT"]
    not_implementable = [row["unit_id"] for row in matrix if row["readiness"] == "NOT_IMPLEMENTABLE"]
    total = len(matrix)
    # A unit is "advanceable" when nothing non-inferable blocks it (implementable
    # or only deferred-to-context). Empty matrix (legacy/no RUs) scores 1.0.
    score = round((len(implementable) + len(deferred)) / total, 3) if total else 1.0
    return {
        "units_total": total,
        "implementable": implementable,
        "deferred_to_context": deferred,
        "not_implementable": not_implementable,
        "implementability_score": score,
        "gate": unit_implementability_gate(not_implementable, deferred),
    }


def unit_implementability_gate(not_implementable: list[str], deferred: list[str]) -> dict[str, Any]:
    """Soft governing verdict: warns by default, never hard-blocks here."""
    if not_implementable:
        state = "UNITS_NOT_IMPLEMENTABLE"
        rationale = (
            "Some requirement units have non-inferable open gaps; this warns by "
            "default. Opt-in strict mode can block READY_FOR_SPECS at /brief."
        )
    elif deferred:
        state = "READY_PENDING_DOMAIN_CONTEXT"
        rationale = (
            "No non-inferable gaps remain; the open unknowns are discoverable in "
            "domain context packs and do not block discovery handoff."
        )
    else:
        state = "ALL_UNITS_IMPLEMENTABLE"
        rationale = "Every requirement unit is implementable from discovery evidence."
    return {
        "state": state,
        "not_implementable_units": not_implementable,
        "deferred_units": deferred,
        "blocks_by_default": False,
    }


def compute_unit_implementability(project_id: str) -> dict[str, Any]:
    """Per-RU implementability view from cited units and anchored open gaps.

    Reads only local artifacts (``requirement_units.md`` + ``gaps.md``). Without
    Requirement Units (legacy workspaces) the matrix is empty and the gate is a
    no-op, so behavior for pre-IMP-115 workspaces is unchanged.
    """
    base = workspace_path(project_id)
    units = parse_requirement_units(base / "01_discovery" / "requirement_units.md")
    gaps_path = base / "01_discovery" / "gaps.md"
    gaps = parse_gap_table(gaps_path.read_text(encoding="utf-8")) if gaps_path.exists() else []
    scope_index = gap_scope_index()
    matrix = build_unit_implementability_matrix(units, gaps, scope_index)
    return {
        "statuses": list(IMPLEMENTABILITY_STATUSES),
        "non_inferable_scope": NON_INFERABLE_SCOPE,
        "summary": summarize_unit_implementability(matrix),
        "matrix": matrix,
    }
