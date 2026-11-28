"""IMP-404 (H26 inc 4): registered cross-reads of a change request against the baseline and the new design.

Everything lives under `01_discovery/CHG-NNN/crosses/` of the project workspace. A cross-read is a
claims file the BA writes: every claim carries verbatim quotes, checked against the registered sources.
"""
from __future__ import annotations

from pathlib import Path

from ..errors import InputError

CROSS_KINDS = ("linea_de_base", "diseno", "contradicciones")

KIND_ALIASES = {
    "linea_de_base": "linea_de_base",
    "baseline": "linea_de_base",
    "diseno": "diseno",
    "diseño": "diseno",
    "design": "diseno",
    "contradicciones": "contradicciones",
    "contradictions": "contradicciones",
}


def normalize_kind(value: str, language: str) -> str:
    kind = KIND_ALIASES.get(str(value).strip().lower())
    if kind is None:
        if language == "es":
            raise InputError(f"Tipo de cruce desconocido «{value}»: linea_de_base, diseno o contradicciones")
        raise InputError(f"Unknown cross kind «{value}»: linea_de_base, diseno or contradicciones")
    return kind


def crosses_dir(base: Path, change_id: str | None) -> Path:
    """The folder that holds a change's registered cross-reads (the project's with None)."""
    if change_id is None:
        return base / "01_discovery" / "crosses"
    return base / "01_discovery" / change_id / "crosses"


def cross_path(base: Path, change_id: str | None, kind: str) -> Path:
    return crosses_dir(base, change_id) / f"{kind}.json"


def run_cross(
    project_id: str,
    change_id: str | None,
    kind: str | None = None,
    claims: str | None = None,
    skip: bool = False,
    reason: str | None = None,
    accept_new: str | None = None,
    surface_type: str | None = None,
    name: str | None = None,
    decline_new: str | None = None,
    delta: bool = False,
) -> dict:
    """The /cross command: record, waive or report the cross-reads of one change, and decide its new surfaces."""
    from ..changes import resolve_scope
    from ..readiness_verdict import change_next_step
    from .claims import TAG_NAMES
    from .record import record_cross, skip_cross
    from .state import KIND_LABELS, cross_status, write_cross_report
    from .surfaces import accept_new_surface, decline_new_surface, new_surface_candidates

    if change_id is None:  # the same guard as the CLI: no ids, change-only options, a workspace of changes only
        from ..changes import refuse_project_extraction

        refuse_project_extraction(project_id, "cross", {"--accept-new": accept_new, "--decline-new": decline_new})
    scope = resolve_scope(project_id, change_id)  # an unknown change is a GateRefusal; None is the project (IMP-420)
    lang = "es" if scope.language == "es" else "en"
    es = lang == "es"
    who = change_id or project_id
    if delta and not claims:
        raise ValueError("/cross --delta va con --claims" if es else "/cross --delta goes with --claims")
    label = ""
    if kind:
        kind = normalize_kind(kind, lang)
        label = KIND_LABELS[lang][kind]
    if claims:
        result = record_cross(project_id, change_id, str(kind), Path(claims), delta=delta)
    elif skip:
        result = skip_cross(project_id, change_id, str(kind), reason or "")
    elif accept_new:
        result = accept_new_surface(project_id, change_id, accept_new, surface_type or "", name or "")
    elif decline_new:
        result = decline_new_surface(project_id, change_id, decline_new, reason or "")
    else:
        report = write_cross_report(project_id, change_id)
        result = {"project_id": project_id, "change_id": change_id, "action": "status", "report_path": report.as_posix()}
    status = cross_status(project_id, change_id)
    action = result.get("action")
    if action == "claims":
        counts = ", ".join(f"{TAG_NAMES[lang][tag]} {n}" for tag, n in result["counts"].items())
        new = len(result.get("gaps_opened") or [])
        message = (f"{who}: cruce {label} registrado ({counts}); {new} pregunta(s) nueva(s)" if es
                   else f"{who}: cross-read {label} recorded ({counts}); {new} new question(s)")
        if result.get("mode") == "delta":
            message += f"; delta: {len(result.get('kept') or [])} " + ("afirmación(es) conservada(s)" if es else "claim(s) kept")
        retired = result.get("retired_gaps") or []
        if retired:
            message += (f"; {len(retired)} pregunta(s) retirada(s) ({', '.join(retired)})" if es
                        else f"; {len(retired)} question(s) withdrawn ({', '.join(retired)})")
    elif action == "skip":
        message = (f"{who}: cruce {label} descartado: {result['reason']}" if es
                   else f"{who}: cross-read {label} waived: {result['reason']}")
    elif action == "accept_new":
        surface = result["surface"]
        message = (f"{who}: «{surface['name']}» entra al borde como superficie nuevo ({surface['type']})" if es
                   else f"{who}: «{surface['name']}» joins the border as a new surface ({surface['type']})")
    elif action == "decline_new":
        message = (f"{who}: {result['candidate']} descartada: {result['reason']}" if es
                   else f"{who}: {result['candidate']} declined: {result['reason']}")
    else:
        message = f"{who}: cruces: {status['text']}" if es else f"{who}: cross-reads: {status['text']}"
    result["crosses"] = status
    result["message"] = message
    if change_id is None:  # IMP-420: the project has no new surfaces, coherence view or change decisions to refresh
        from ..extraction import project_next_step

        result["new_surface_candidates"] = []
        result["next_step"] = project_next_step(project_id, result)
        return result
    result["new_surface_candidates"] = new_surface_candidates(project_id, change_id)
    result["next_step"] = change_next_step(project_id, change_id)
    from ..change_coherence import refresh_coherence
    from ..decision_memory import index_change_decisions

    refresh_coherence(project_id, change_id, persist=True)  # IMP-410: the lens view follows what the cross-reads decided
    index_change_decisions(project_id, change_id)  # IMP-410: what the cross-reads decided is retrievable
    return result
