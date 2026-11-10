from __future__ import annotations

from .backlog.rollup import backlog_status
from .assumptions import assumptions_projection
from .knowledge.ledger import knowledge_ledger_summary
from .maturity import maturity_metrics
from .readiness_verdict import build_readiness_verdict
from .gaps import parse_gap_table
from .workspace import read_json, state_path, workspace_path


def project_next(project_id: str) -> dict[str, object]:
    """`/next` (IMP-294): exactly the next step `/status` gives, and nothing else."""
    return {"project_id": project_id, **build_readiness_verdict(project_id)["next_step"]}


def project_status(project_id: str, full: bool = True) -> dict[str, object]:
    """`/status`. The verdict (IMP-248) is the summary; `full` adds the detailed dump.

    The Python API returns the full dump by default; the CLI prints the summary
    unless `--full` is passed.
    """
    state = read_json(state_path(project_id), {})
    verdict = build_readiness_verdict(project_id)
    summary: dict[str, object] = {
        "project_id": project_id,
        "phase": state.get("phase", "unknown"),
        "health": state.get("health", "UNKNOWN"),
        "project_language": state.get("project_language", "auto"),
        "privacy_mode": state.get("privacy_mode", "local-only"),
        "readiness_stage": state.get("readiness_stage", "DISCOVERY_RAW"),
        "verdict": verdict,
        "gap_counts": {**verdict["counts"], **gap_origin_counts(project_id)},
        "maturity_score": verdict["maturity_score"],
        "sources": verdict["sources"],
        "next_step": verdict["next_step"]["text"],
        "next_action": verdict["next_step"],
    }
    if not full:
        return summary
    metrics = maturity_metrics(project_id)
    # development_readiness used to appear twice (nested and top level).
    development = metrics.pop("development_readiness", {})
    return {
        **summary,
        "maturity_metrics": metrics,
        "development_readiness": development,
        "assumptions_projection": assumptions_projection(project_id)["summary"],
        "last_change_id": state.get("last_change_id"),
        "last_gap_resolution_id": state.get("last_gap_resolution_id"),
        "prd_composition_count": state.get("prd_composition_count", 0),
        "last_prd_composition_id": state.get("last_prd_composition_id"),
        "knowledge_ledger": knowledge_ledger_summary(project_id),
        "story_gates": summarize_story_gates(state.get("story_gates", {})),
        "backlog_rollup": backlog_status(project_id, write=False)["summary"],
    }


def gap_origin_counts(project_id: str) -> dict[str, int]:
    """`<origin>_origin` counts (agent, challenge, scrutiny, sync, self-review...) from gaps.md."""
    gaps_path = workspace_path(project_id) / "01_discovery" / "gaps.md"
    counts: dict[str, int] = {}
    if gaps_path.exists():
        for gap in parse_gap_table(gaps_path.read_text(encoding="utf-8")):
            origin = str(gap.get("origin", "")).strip()
            if origin:
                key = f"{origin.replace('-', '_')}_origin"
                counts[key] = counts.get(key, 0) + 1
    return counts


def summarize_story_gates(gates: object) -> dict[str, object]:
    if not isinstance(gates, dict):
        return {"stories": {}, "warnings": []}
    warnings: list[str] = []
    stories: dict[str, object] = {}
    for story_id, gate in sorted(gates.items()):
        if not isinstance(gate, dict):
            continue
        dor_missing = gate.get("dor", {}).get("missing", []) if isinstance(gate.get("dor"), dict) else []
        dod_missing = gate.get("dod", {}).get("missing", []) if isinstance(gate.get("dod"), dict) else []
        stories[story_id] = {
            "dor_passed": gate.get("dor", {}).get("passed", False) if isinstance(gate.get("dor"), dict) else False,
            "dod_passed": gate.get("dod", {}).get("passed", False) if isinstance(gate.get("dod"), dict) else False,
            "dor_missing": dor_missing,
            "dod_missing": dod_missing,
        }
        warnings.extend(f"{story_id} DoR: {item}" for item in dor_missing)
        warnings.extend(f"{story_id} DoD: {item}" for item in dod_missing)
    return {"stories": stories, "warnings": warnings}
