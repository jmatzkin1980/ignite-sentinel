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
    from .extraction.coverage import extraction_coverage, preserved_coverage
    from .readiness_verdict import change_next_step

    change = get_change(project_id, change_id)
    step = change_next_step(project_id, change_id)
    sources = change_sources(project_id, change_id)
    extraction = extraction_coverage(project_id, change_id)
    preserved = preserved_coverage(project_id, change_id)
    from .crosses.state import cross_status
    from .crosses.surfaces import new_surface_candidates

    crosses = cross_status(project_id, change_id)
    candidates = new_surface_candidates(project_id, change_id)
    from .health import health_explanation

    health = str(read_json(state_path(project_id), {}).get("health", ""))
    detail = health_explanation(project_id)
    return {
        "project_id": project_id,
        "change_id": change_id,
        "health": health,
        **({"health_detail": detail} if detail else {}),
        "round": change.get("round"),
        "border_confirmed": bool(change.get("border_confirmed_at")),
        "gap_counts": change.get("gap_counts", {}),
        "next_step": step["text"],
        "next_action": step,
        "sources": sources,
        "extraction": extraction,
        "preserved": preserved,
        "crosses": crosses,
        "new_surface_candidates": candidates,
        "warnings": [
            *escalation_warnings(project_id, change_id),
            *_source_warnings(project_id, change_id, sources),
            *_extraction_warnings(project_id, change_id, change, extraction, preserved),
            *_cross_warnings(project_id, change_id, change, crosses, candidates),
        ],
    }


def _cross_warnings(project_id: str, change_id: str, change: dict, crosses: dict, candidates: list) -> list[dict[str, object]]:
    """IMP-404: the cross-reads still missing and the new-surface candidates nobody decided, same `trigger` + `message` shape."""
    from .changes import change_language
    from .crosses.state import KIND_LABELS

    if change.get("round") == "scope":
        return []
    lang = "es" if change_language(project_id, change) == "es" else "en"
    warnings: list[dict[str, object]] = []
    if crosses["missing"]:
        labels = ", ".join(KIND_LABELS[lang][kind] for kind in crosses["missing"])
        warnings.append({"trigger": "crosses_missing", "message": (
            f"{change_id}: faltan cruces: {labels}" if lang == "es" else f"{change_id}: cross-reads missing: {labels}")})
    pending = [c["id"] for c in candidates if c["decision"] is None]
    if pending:
        ids = ", ".join(pending)
        warnings.append({"trigger": "new_surfaces_pending", "message": (
            f"{change_id}: {len(pending)} candidata(s) a superficie nueva sin decidir: {ids}" if lang == "es"
            else f"{change_id}: {len(pending)} new-surface candidate(s) undecided: {ids}")})
    return warnings


def _extraction_warnings(
    project_id: str, change_id: str, change: dict, extraction: dict, preserved: dict,
) -> list[dict[str, object]]:
    """IMP-402: the extraction of the request and the preserved surfaces, same `trigger` + `message` shape."""
    from .changes import change_language

    es = change_language(project_id, change) == "es"
    run = f"/extract {project_id} --change {change_id}"
    warnings: list[dict[str, object]] = []
    state = extraction["state"]
    if state == "missing":
        if change.get("round") == "lenses":
            warnings.append({"trigger": "extraction_missing", "message": (
                f"{change_id}: el pedido no se inventarió todavía ({run})" if es
                else f"{change_id}: the request has not been inventoried yet ({run})")})
    elif state == "stale":
        warnings.append({"trigger": "extraction_stale", "message": (
            f"{change_id}: el pedido cambió desde el inventario; corré {run}" if es
            else f"{change_id}: the request changed since the inventory; run {run}")})
    elif not extraction["complete"] and not (
        extraction.get("orphans") and extraction["covered"] == extraction["total"] and not extraction.get("unreadable")
    ):  # orphans alone have their own warning below: "covers N of N" would be a false report
        warnings.append({"trigger": "extraction_incomplete", "message": (
            f"{change_id}: la extracción cubre {extraction['text']}" if es
            else f"{change_id}: the extraction covers {extraction['text']}")})
    if extraction.get("unreadable"):
        names = ", ".join(extraction["unreadable"])
        warnings.append({"trigger": "extraction_unreadable", "message": (
            f"{change_id}: Sentinel no pudo leer el pedido {names}; cargá una copia legible" if es
            else f"{change_id}: Sentinel could not read the request {names}; load a readable copy")})
    if extraction.get("orphans"):
        names = ", ".join(o["id"] for o in extraction["orphans"])
        warnings.append({"trigger": "extraction_orphans", "message": (
            f"{change_id}: elementos que ya no están en el pedido conservan filas EARS: {names} ({run} --reject-item ID --reason \"…\")" if es
            else f"{change_id}: elements no longer in the request keep EARS rows: {names} ({run} --reject-item ID --reason \"…\")")})
    if preserved["missing"]:
        names = ", ".join(preserved["missing"])
        warnings.append({"trigger": "preserved_missing", "message": (
            f"{change_id}: superficies preservadas sin fila UNCHANGED: {names}" if es
            else f"{change_id}: preserved surfaces without an UNCHANGED row: {names}")})
    return warnings


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
