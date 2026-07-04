from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from ..assumptions import load_assumptions, update_assumption_statuses
from ..development_readiness import compute_development_readiness
from ..discovery import refresh_knowledge_ledger
from ..workspace import read_json, update_state, workspace_path
from .ledger import record_superseded_units

INVALIDATION_TOKENS = (
    "invalid",
    "invalidated",
    "no longer valid",
    "cannot use",
    "must not use",
    "not use",
    "wrong",
    "replaced",
    "descart",
    "invalida",
    "no aplica",
    "no corresponde",
    "no se usara",
    "no se usará",
)

# IMP-125: associative metabolization. A change reworded without invalidation
# vocabulary impacts nothing through the deterministic token/link path. The
# associative step asks the retrieval broker for assumptions that look related
# by *meaning* and surfaces them as cited, BA-reviewable findings — never
# auto-applied. The graph stays the authority of propagation.
ASSOCIATIVE_SCORE_THRESHOLD = 0.15
ASSOCIATIVE_LIMIT = 5
ASSUMPTION_ID_RE = re.compile(r"\bASM-[A-Z0-9][A-Z0-9-]*\b", re.I)


def metabolize_knowledge(
    project_id: str,
    change_id: str,
    *,
    source_text: str = "",
    validated_gap_ids: set[str] | None = None,
    broker: Any = None,
) -> dict[str, Any]:
    """Refresh governed knowledge after a confirmed or invalidating change.

    The ledger remains compiled from source artifacts. This function updates the
    governed assumption register when evidence validates/invalidates a row, then
    rebuilds ledger and readiness and records downstream staleness.
    """
    base = workspace_path(project_id)
    before_units = read_ledger_units(base)
    validated_gap_ids = {gap_id.upper() for gap_id in (validated_gap_ids or set())}
    invalidated_assumptions = detect_invalidated_assumptions(project_id, source_text)
    associative_findings = associative_impact_candidates(
        broker,
        source_text,
        already_invalidated=invalidated_assumptions,
    )
    evidence = evidence_snippet(source_text)
    assumption_result = update_assumption_statuses(
        project_id,
        validated_gap_ids=validated_gap_ids,
        invalidated_assumption_ids=invalidated_assumptions,
        evidence=evidence,
        source_id=change_id,
    )
    ledger = refresh_knowledge_ledger(project_id, broker)
    readiness = compute_development_readiness(project_id, persist=True)
    after_units = ledger["payload"].get("units", [])
    # IMP-153: invalidate-not-delete. The rebuild replaced the invalidated
    # assumptions' units with their OPEN successors; preserve the pre-change
    # versions in the ledger's append-only history with a typed supersession edge.
    superseded = record_superseded_units(project_id, before_units, after_units, invalidated_assumptions)
    unit_ids = impacted_knowledge_units(before_units, after_units, validated_gap_ids, invalidated_assumptions)
    stale_artifacts = downstream_stale_artifacts(base) if unit_ids else []
    payload = {
        "change_id": change_id,
        "validated_gap_ids": sorted(validated_gap_ids),
        "validated_assumptions": assumption_result.get("validated", []),
        "invalidated_assumptions": assumption_result.get("invalidated", []),
        "impacted_knowledge_units": unit_ids,
        "superseded_units": [{"id": e.get("id"), "superseded_by": e.get("superseded_by")} for e in superseded],
        "associative_findings": associative_findings,
        "knowledge_state": str(ledger["md_path"].as_posix()),
        "development_readiness": str((base / "01_discovery" / "development_readiness.json").as_posix()),
        "readiness_summary": readiness.get("summary", {}),
        "downstream_stale_artifacts": stale_artifacts,
    }
    update_state(
        project_id,
        knowledge_ledger_summary=ledger["payload"].get("summary", {}),
        development_readiness=readiness.get("summary", {}),
        last_knowledge_metabolism=payload,
        knowledge_staleness={
            "change_id": change_id,
            "impacted_knowledge_units": unit_ids,
            "downstream_artifacts": stale_artifacts,
        },
    )
    return payload


def detect_invalidated_assumptions(project_id: str, text: str) -> set[str]:
    normalized = normalize(text)
    if not normalized or not any(token in normalized for token in INVALIDATION_TOKENS):
        return set()
    invalidated: set[str] = set()
    for row in load_assumptions(project_id):
        assumption_id = row.get("id", "").upper()
        closes_gap = row.get("closes_gap", "").upper()
        if assumption_id and normalize(assumption_id) in normalized:
            invalidated.add(assumption_id)
        elif closes_gap and normalize(closes_gap) in normalized and phrase_overlap(row.get("statement", ""), text):
            invalidated.add(assumption_id)
    return invalidated


def associative_impact_candidates(
    broker: Any,
    source_text: str,
    *,
    already_invalidated: set[str],
) -> list[dict[str, Any]]:
    """IMP-125: surface meaning-based impact candidates as cited findings.

    Complements the deterministic token/link metabolization without replacing it:
    when a change resembles a governed assumption by meaning (not by invalidation
    vocabulary), the retrieval broker proposes that assumption as a *candidate*
    impact. Findings are cited and BA-reviewable; nothing is auto-closed or
    auto-invalidated, and the graph remains the authority of propagation.

    Degrades to no findings (and no error) when there is no broker, no semantic
    embedder, or retrieval fails — preserving the current deterministic behavior.
    """
    if broker is None:
        return []
    status = getattr(broker, "embedder_status", None)
    if status is None or not getattr(status, "semantic", False):
        return []
    query = associative_query(source_text)
    if not query:
        return []
    try:
        rows = broker.retrieve(
            query,
            workflow="sync",
            artifact_type="assumption_register",
            limit=ASSOCIATIVE_LIMIT,
        )
    except Exception:
        # The associative step is advisory only; any retrieval failure degrades
        # to the deterministic path rather than breaking /sync.
        return []
    findings: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        score = float(row.get("score", 0.0) or 0.0)
        if score < ASSOCIATIVE_SCORE_THRESHOLD:
            continue
        text = str(row.get("text") or row.get("content") or "")
        read_plan = row.get("read_plan", {}) or {}
        citation = {
            "source_path": read_plan.get("source_path") or row.get("source_path", ""),
            "section_path": read_plan.get("section_path") or row.get("section_path", ""),
            "line_start": int(read_plan.get("line_start", 0) or 0),
            "line_end": int(read_plan.get("line_end", 0) or 0),
        }
        for match in ASSUMPTION_ID_RE.findall(text):
            assumption_id = match.upper()
            # Don't echo assumptions the deterministic path already flagged, and
            # report each candidate once even if it spans several chunks.
            if assumption_id in already_invalidated or assumption_id in seen:
                continue
            seen.add(assumption_id)
            findings.append(
                {
                    "kind": "associative",
                    "target": assumption_id,
                    "reason": "posible impacto por similitud semántica",
                    "score": round(score, 4),
                    "why_retrieved": row.get("why_retrieved", ""),
                    "chunk_id": row.get("chunk_id", ""),
                    "trace_ids": list(row.get("trace_ids", []) or []),
                    "citation": citation,
                }
            )
    return findings


def associative_query(text: str, limit: int = 600) -> str:
    return re.sub(r"\s+", " ", text).strip()[:limit]


def impacted_knowledge_units(
    before_units: list[dict[str, Any]],
    after_units: list[dict[str, Any]],
    gap_ids: set[str],
    assumption_ids: set[str],
) -> list[str]:
    impacted: set[str] = set()
    before_by_key = {unit_key(unit): unit for unit in before_units}
    for unit in after_units:
        links = unit.get("links", [])
        linked_gaps = {link.get("target", "").upper() for link in links if link.get("type") == "gap"}
        linked_assumptions = {link.get("target", "").upper() for link in links if link.get("type") == "assumption"}
        key = unit_key(unit)
        old = before_by_key.get(key, {})
        if linked_gaps & gap_ids or linked_assumptions & assumption_ids:
            impacted.add(unit["id"])
        elif old and old.get("status") != unit.get("status"):
            impacted.add(unit["id"])
    return sorted(impacted)


def downstream_stale_artifacts(base: Path) -> list[str]:
    candidates = [
        base / "02_requirements" / "project-brief.md",
        base / "03_specs" / "prd.md",
        base / "03_specs" / "specs.md",
        base / "04_backlog" / "BACKLOG.md",
        base / "08_context_packs" / "implementation_readiness.json",
    ]
    return [str(path.as_posix()) for path in candidates if path.exists()]


def read_ledger_units(base: Path) -> list[dict[str, Any]]:
    data = read_json(base / "01_discovery" / "knowledge_state.json", {})
    units = data.get("units", []) if isinstance(data, dict) else []
    return units if isinstance(units, list) else []


def evidence_snippet(text: str, limit: int = 180) -> str:
    clean = re.sub(r"\s+", " ", text).strip()
    return clean[:limit]


def phrase_overlap(statement: str, text: str) -> bool:
    words = {word for word in re.findall(r"[a-z0-9áéíóúñ]+", normalize(statement)) if len(word) >= 5}
    haystack = set(re.findall(r"[a-z0-9áéíóúñ]+", normalize(text)))
    return len(words & haystack) >= 3


def unit_key(unit: dict[str, Any]) -> tuple[str, str]:
    return (str(unit.get("statement", "")), ",".join(format_link(link) for link in unit.get("links", [])))


def format_link(link: dict[str, Any]) -> str:
    return f"{link.get('type')}={link.get('target')}"


def normalize(text: str) -> str:
    return " ".join(text.lower().replace("á", "a").replace("é", "e").replace("í", "i").replace("ó", "o").replace("ú", "u").split())
