from __future__ import annotations

from .backlog.rollup import backlog_status
from .assumptions import assumptions_projection
from .knowledge.ledger import knowledge_ledger_summary
from .maturity import maturity_metrics
from .readiness_verdict import build_readiness_verdict
from .gaps import parse_gap_table
from .workspace import read_json, state_path, workspace_path


def project_next(project_id: str, change_id: str | None = None) -> dict[str, object]:
    """`/next` (IMP-294): exactly the next step `/status` gives, and nothing else.

    IMP-396: a workspace with changes adds `changes`; `change_id` answers for that change alone.
    """
    if change_id:
        from .change_escalation import escalation_warnings
        from .readiness_verdict import change_next_step

        return {"project_id": project_id, **change_next_step(project_id, change_id),
                "warnings": escalation_warnings(project_id, change_id)}
    verdict = build_readiness_verdict(project_id)
    result: dict[str, object] = {"project_id": project_id, **verdict["next_step"]}
    if "changes" in verdict:
        result["changes"] = verdict["changes"]
    return result


def project_status(project_id: str, full: bool = True, change_id: str | None = None) -> dict[str, object]:
    """`/status`. The verdict (IMP-248) is the summary; `full` adds the detailed dump.

    The Python API returns the full dump by default; the CLI prints the summary
    unless `--full` is passed.
    """
    if change_id:
        return change_status(project_id, change_id)
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
    if "changes" in verdict:  # IMP-396: only a workspace with changes grows the key
        summary["changes"] = verdict["changes"]
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


def change_status(project_id: str, change_id: str) -> dict[str, object]:
    """IMP-396: `/status --change`: where one change stands, its next step and its escalation warnings."""
    from .change_escalation import escalation_warnings
    from .changes import get_change
    from .readiness_verdict import change_next_step

    change = get_change(project_id, change_id)
    step = change_next_step(project_id, change_id)
    sources = change_sources(project_id, change_id)
    return {
        "project_id": project_id,
        "change_id": change_id,
        "round": change.get("round"),
        "border_confirmed": bool(change.get("border_confirmed_at")),
        "gap_counts": change.get("gap_counts", {}),
        "next_step": step["text"],
        "next_action": step,
        "sources": sources,
        "warnings": [*escalation_warnings(project_id, change_id), *_source_warnings(project_id, change_id, sources)],
    }


def change_sources(project_id: str, change_id: str) -> dict[str, object]:
    """IMP-400: the change's sources by role, the system's baseline, and what the request cites but nobody loaded."""
    from .changes import get_change
    from .source_registry import SOURCE_ROLES, row_role
    from .source_versions import check_change_versions
    from .sources import load_source_manifest

    change = get_change(project_id, change_id)
    rows = {str(r.get("id")): r for r in load_source_manifest(project_id).get("registry", [])}
    mine = [rows[i] for i in change.get("sources") or [] if i in rows]
    by_role: dict[str, list[str]] = {}
    for role in SOURCE_ROLES:
        ids = [str(r["id"]) for r in mine if row_role(r) == role]
        if ids:
            by_role[role] = ids
    baseline = [str(r["id"]) for r in rows.values()
                if r.get("validity", "current") == "current" and row_role(r) == "linea_de_base"]
    cited = check_change_versions(project_id, change_id, write=False)["not_loaded"]
    not_loaded = [str(item["cited"]) for item in cited if item.get("cited")]
    return {
        "by_role": by_role,
        "baseline": baseline,
        "baseline_waived": change.get("baseline_waived") or None,
        "not_loaded": list(dict.fromkeys(not_loaded)),
        "open_rows": [str(r["id"]) for r in mine if r.get("lifecycle") == "open"],
    }


def _source_warnings(project_id: str, change_id: str, sources: dict[str, object]) -> list[dict[str, object]]:
    """Same shape as the escalation warnings: a `trigger` and its `message`."""
    from .changes import change_language, get_change

    es = change_language(project_id, get_change(project_id, change_id)) == "es"
    warnings: list[dict[str, object]] = []
    if not sources["baseline"] and not sources["baseline_waived"]:
        warnings.append({"trigger": "no_baseline", "message": f"{change_id}: no hay línea de base registrada" if es
                         else f"{change_id}: no baseline is registered"})
    if sources["not_loaded"]:
        names = ", ".join(sources["not_loaded"])  # type: ignore[arg-type]
        warnings.append({"trigger": "cited_not_loaded", "message": (
            f"{change_id}: el pedido cita documentos que no se cargaron: {names}" if es
            else f"{change_id}: the request cites documents that were not loaded: {names}")})
    if sources["open_rows"]:
        ids = ", ".join(sources["open_rows"])  # type: ignore[arg-type]
        warnings.append({"trigger": "open_source_rows", "message": (
            f"{change_id}: fuentes con la carga sin cerrar: {ids}" if es
            else f"{change_id}: sources with an unfinished load: {ids}")})
    return warnings


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
