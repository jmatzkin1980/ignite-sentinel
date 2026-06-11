from __future__ import annotations

from .discovery import parse_gap_rows
from .maturity import maturity_metrics
from .workspace import read_json, state_path, workspace_path


def project_status(project_id: str) -> dict[str, object]:
    base = workspace_path(project_id)
    state = read_json(state_path(project_id), {})
    gaps_path = base / "01_discovery" / "gaps.md"
    gaps = parse_gap_rows(gaps_path.read_text(encoding="utf-8")) if gaps_path.exists() else []
    counts = state.get("gap_counts") or count_gap_rows(gaps)
    next_step = recommend_next_step(state, counts)
    return {
        "project_id": project_id,
        "phase": state.get("phase", "unknown"),
        "health": state.get("health", "UNKNOWN"),
        "project_language": state.get("project_language", "auto"),
        "privacy_mode": state.get("privacy_mode", "local-only"),
        "readiness_stage": state.get("readiness_stage", "DISCOVERY_RAW"),
        "gap_counts": counts,
        "maturity_metrics": state.get("maturity_metrics") or maturity_metrics(project_id),
        "last_change_id": state.get("last_change_id"),
        "last_gap_resolution_id": state.get("last_gap_resolution_id"),
        "next_step": next_step,
    }


def count_gap_rows(gaps: list[dict[str, str]]) -> dict[str, int]:
    counts = {"open": 0, "closed": 0, "partially_closed": 0, "blocking_open": 0, "total": len(gaps)}
    for gap in gaps:
        status = gap.get("status", "OPEN").upper()
        severity = gap.get("severity", "").lower()
        if status == "OPEN":
            counts["open"] += 1
            if severity in {"critical", "high"}:
                counts["blocking_open"] += 1
        elif status in {"PARTIALLY_CLOSED", "ANSWERED"}:
            counts["partially_closed"] += 1
            if severity in {"critical", "high"}:
                counts["blocking_open"] += 1
        elif status == "CLOSED":
            counts["closed"] += 1
    return counts


def recommend_next_step(state: dict, counts: dict) -> str:
    if state.get("phase") == "initialized":
        return "Run /ingest PROJECT_ID --source PATH."
    if counts.get("blocking_open", 0):
        return "Share gaps.md with the client and run /resolve-gaps when answers return."
    if counts.get("open", 0) or counts.get("partially_closed", 0):
        return "Resolve remaining non-blocking/domain gaps or run /brief if acceptable."
    if not state.get("artifacts", {}).get("project_brief"):
        return "Run /brief PROJECT_ID."
    return "Run /specs PROJECT_ID or generate domain context requests."
