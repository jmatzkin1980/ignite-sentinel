"""Counts-based "ready to build" verdict and the single next step (IMP-248).

`build_readiness_verdict` is the only place that decides, for a workspace:
- the gap counts (one counter, configured blocking severities);
- the verdict: READY / READY_WITH_WARNINGS / NOT_READY;
- what blocks it, what only warns, and which checks could not run;
- the gate matrix (gaps, brief, implementability, crystallization, drift, story DoR);
- the next step.

`/status`, `/dashboard` and MCP (through `/status`) read it; skills cite it. It
reads governed artifacts only and writes nothing. The maturity score is
published next to the verdict, never instead of it: the gates do not change.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .assumptions import assumptions_projection
from .core.state import read_state
from .development_readiness import compute_development_readiness, compute_unit_implementability
from .drift import derived_drift_warnings
from .source_registry import registry_warnings
from .sources import source_registry_summary
from .gaps import BLOCKING_GAP_STATUSES, blocking_severities, count_gaps, is_blocking, parse_gap_table
from .pending_marks import change_extraction_pending as _extraction_pending
from .workspace import load_config, workspace_path

VERDICTS = ("READY", "READY_WITH_WARNINGS", "NOT_READY")
BRIEF_BLOCK_STAGES = {"BRIEF_BELOW_THRESHOLD", "SELF_CORRECTION_FAILED", "UNITS_NOT_IMPLEMENTABLE"}


def build_readiness_verdict(project_id: str, release: str | None = None) -> dict[str, Any]:
    base = workspace_path(project_id)
    state = read_state(project_id, {})
    config = load_config(project_id)
    severities = blocking_severities(config)
    gaps_path = base / "01_discovery" / "gaps.md"
    discovered = gaps_path.exists()
    gaps = parse_gap_table(gaps_path.read_text(encoding="utf-8")) if discovered else []
    counts = count_gaps(gaps, severities)
    blocking_open = sorted(str(g["id"]).strip("`") for g in gaps if is_blocking(g, severities, BLOCKING_GAP_STATUSES))

    blockers: list[str] = []
    warnings: list[str] = []
    partial: list[dict[str, str]] = []
    # IMP-398: a workspace that only holds changes has no project discovery to run; its changes answer for it.
    overview: list[dict[str, Any]] | None = None
    if state.get("changes") and (release if release is not None else _active_release()) is None:
        overview = changes_overview(project_id)
    change_only = overview is not None and not (base / "02_requirements" / "requirements.md").exists()
    if not discovered and not change_only:
        blockers.append("Discovery has not run: there is no 01_discovery/gaps.md.")
    if blocking_open:
        blockers.append(f"{len(blocking_open)} blocking gap(s) open: {', '.join(blocking_open)}.")

    if change_only and not discovered:
        # no project discovery to run: the changes' own steps answer for it, so this gate does not apply (and does not block)
        gaps_gate = {"gate": "gaps", "state": "NOT_APPLICABLE", "blocks": False}
    else:
        gaps_gate = {"gate": "gaps", "state": "BLOCKING_OPEN" if blocking_open else ("CLEAR" if discovered else "NOT_RUN"), "blocks": bool(blocking_open) or not discovered}
    gate_matrix = [gaps_gate]

    stage = str(state.get("readiness_stage", "DISCOVERY_RAW"))
    brief_exists = (base / "02_requirements" / "project-brief.md").exists()
    brief_state = stage if stage in BRIEF_BLOCK_STAGES else ("PASSED" if brief_exists else "NOT_RUN")
    gate_matrix.append({"gate": "brief_gate", "state": brief_state, "blocks": stage in BRIEF_BLOCK_STAGES})
    if stage in BRIEF_BLOCK_STAGES:
        blockers.append(f"/brief stopped the phase close: {stage}.")
    elif not brief_exists:
        partial.append({"check": "brief_gate", "reason": "No project brief yet; the brief gate has not run."})
    # IMP-325: the brief v2 states its own "Ready to build" line. A PM saw /status say
    # READY_WITH_WARNINGS while the brief said "Ready to build: no. 15 pending marks block";
    # both answer the same question, so the brief's "no" now blocks the verdict too.
    ready_to_build = brief_ready_to_build(base) if brief_exists else None
    if ready_to_build and ready_to_build["ready"] is False:
        blockers.append(f"The project brief says: {ready_to_build['line']} Close the gaps its pending marks name.")

    impl = compute_unit_implementability(project_id)
    impl_summary = impl.get("summary", {}) if isinstance(impl, dict) else {}
    impl_gate = impl_summary.get("gate", {}) if isinstance(impl_summary.get("gate"), dict) else {}
    impl_cfg = config.get("implementability_gate", {}) if isinstance(config.get("implementability_gate"), dict) else {}
    not_implementable = list(impl_summary.get("not_implementable", []))
    deferred = list(impl_summary.get("deferred_to_context", []))
    impl_blocks = bool(impl_cfg.get("strict", False)) and bool(not_implementable)
    gate_matrix.append({"gate": "implementability_gate", "state": str(impl_gate.get("state", "NOT_RUN")), "blocks": impl_blocks})
    if not impl_summary.get("units_total"):
        partial.append({"check": "implementability_gate", "reason": "No requirement units; implementability was not measured."})
    if not_implementable:
        (blockers if impl_blocks else warnings).append(f"Not implementable from discovery evidence: {', '.join(not_implementable)}.")
    if deferred:
        warnings.append(f"DEFERRED_TO_CONTEXT (reported, not blocking): {', '.join(deferred)}.")

    development = compute_development_readiness(project_id)
    dev_summary = development.get("summary", {}) if isinstance(development, dict) else {}
    crystallization = dev_summary.get("crystallization_gate", {}) if isinstance(dev_summary.get("crystallization_gate"), dict) else {}
    gate_matrix.append({"gate": "crystallization_gate", "state": str(crystallization.get("state", "NOT_RUN")), "blocks": False})
    if not dev_summary.get("cells_total"):
        partial.append({"check": "crystallization_gate", "reason": "No knowledge units; development certainty was not measured."})
    elif crystallization and not crystallization.get("ready_for_development", False):
        warnings.append(f"Development certainty: {crystallization.get('state')}.")

    drift = derived_drift_warnings(project_id)
    drift_cfg = config.get("drift_gate", {}) if isinstance(config.get("drift_gate"), dict) else {}
    drift_blocks = bool(drift) and bool(drift_cfg.get("strict", False))
    gate_matrix.append({"gate": "drift", "state": "STALE" if drift else "CLEAN", "blocks": drift_blocks})
    (blockers if drift_blocks else warnings).extend(drift)

    # IMP-250a: an open F-NN row is a cross that never finished; an unconfirmed new
    # version waits for a person to say which one governs. Both warn, neither blocks.
    sources = source_registry_summary(project_id)
    source_findings = registry_warnings(sources)
    gate_matrix.append({"gate": "sources", "state": "OPEN" if source_findings else "CLEAN", "blocks": False})
    warnings.extend(source_findings)

    projection = assumptions_projection(project_id)
    risky = list((projection.get("summary") or {}).get("test_before_advancing_ids", []))
    if risky:
        warnings.append(f"Test before advancing (high risk, high uncertainty): {', '.join(risky)}.")

    stories = _story_items(base, state)
    failed_dor = sorted(sid for sid, item in stories.items() if item["verdict"] != "READY")
    gate_matrix.append({"gate": "story_dor", "state": ("FAILING" if failed_dor else "PASSED") if stories else "NOT_RUN", "blocks": False})
    if not stories:
        partial.append({"check": "story_dor", "reason": "No backlog stories; Definition of Ready was not checked."})

    from .release_scope import active_main, active_release  # IMP-267b: the verdict knows the release it covers

    scoped = active_release()
    if release is None:
        release = scoped
    if scoped and release == scoped and active_main() is not None:
        from .release_guide import inherited_blockers  # IMP-269 [A38]: a hard dependency not closed blocks

        inherited = inherited_blockers(active_main(), scoped)
        blockers.extend(inherited)
        gate_matrix.append({"gate": "series_dependencies", "state": "WAITING" if inherited else "CLEAR", "blocks": bool(inherited)})
    elif release is not None and release != scoped:
        partial.append({"check": "release", "reason": f"Release {release} was named outside its scope; run the command with --release {release} for a verdict over that release's brief and backlog. This verdict covers the whole workspace."})

    if change_only and overview is not None:
        pending = [item for item in overview if item["next_step"]["key"] != "done"]
        blockers[:0] = [_change_blocker(project_id, item) for item in pending]
        if not pending:
            # existing value on purpose (views switch on it): the pieces are up to date, the request coverage is not measured
            warnings.append(COVERAGE_NOT_MEASURED)

    if blockers:
        verdict = "NOT_READY"
    elif warnings or partial:
        verdict = "READY_WITH_WARNINGS"
    else:
        verdict = "READY"

    metrics_score = _maturity_score(project_id)
    result: dict[str, Any] = {
        "project_id": project_id,
        "release": release,
        "verdict": verdict,
        "blocking_open": blocking_open,
        "blockers": blockers,
        "warnings": warnings,
        "partial_coverage": partial,
        "counts": counts,
        "gate_matrix": gate_matrix,
        "by_item": {"workspace": {"verdict": verdict, "blocking_open": len(blocking_open)}, **stories},
        "maturity_score": metrics_score,
        "sources": sources,
        "ready_to_build": ready_to_build,
    }
    assumed_blocking = sorted(
        {str(row.get("closes_gap", "")).upper() for row in projection.get("assumptions", [])} & set(blocking_open)
    )
    result["next_step"] = next_step(project_id, state, result, has_stories=bool(stories), has_brief=brief_exists,
                                    assumed_blocking=assumed_blocking)
    # IMP-396: only a workspace with changes grows the key (path A stays as it was), and never inside a
    # release scope: changes are project-level, a release verdict covers the release only.
    if overview is not None and release is None:
        result["changes"] = overview
        if not (base / "02_requirements" / "requirements.md").exists():
            # a change-only workspace has no project to ingest or write a PRD for: the next step is the change's
            result["next_step"] = _first_change_step(result["changes"])
    return result


COVERAGE_NOT_MEASURED = ("Request coverage is not measured yet: the registered pieces of the changes are up to date, "
                         "but Sentinel does not check that each rule and criterion of the request has its requirement or its discard.")


def _active_release() -> str | None:
    from .release_scope import active_release

    return active_release()


def _change_blocker(project_id: str, item: dict[str, Any]) -> str:
    """IMP-398: one blocker per pending change, in the change's language: its id, pending step and (lenses) blocking count."""
    from .changes import change_language, get_change

    step = item["next_step"]
    change = get_change(project_id, item["change_id"])
    n = int((change.get("gap_counts") or {}).get("blocking_open", 0) or 0)
    es = change_language(project_id, change) == "es"
    detail = f" ({n} bloqueante/s)" if es and step["key"] == "lenses" else (f" ({n} blocking)" if step["key"] == "lenses" else "")
    return f"{item['change_id']}: {step['key']}{detail}. {step['title']}."


_READY_LINE_PREFIXES = ("Ready to build:", "Listo para construir:")


def brief_ready_to_build(base: Path) -> dict[str, Any] | None:
    """IMP-325: the brief v2's own "Ready to build" line, or None when the brief has none (v1)."""
    path = base / "02_requirements" / "project-brief.md"
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip().lstrip(">*- ").strip()
        for prefix in _READY_LINE_PREFIXES:
            if line.startswith(prefix):
                answer = line[len(prefix):].strip().lower()
                return {"ready": not answer.startswith("no"), "line": line}
    return None


def _story_items(base: Path, state: dict[str, Any]) -> dict[str, dict[str, Any]]:
    gates = state.get("story_gates", {}) if isinstance(state.get("story_gates"), dict) else {}
    items: dict[str, dict[str, Any]] = {}
    for path in sorted((base / "04_backlog").glob("US-*.md")):
        story_id = path.stem
        gate = gates.get(story_id, {}) if isinstance(gates.get(story_id), dict) else {}
        dor = gate.get("dor", {}) if isinstance(gate.get("dor"), dict) else {}
        missing = list(dor.get("missing", [])) if dor else ["Definition of Ready not evaluated"]
        items[story_id] = {"verdict": "READY" if dor.get("passed") else "NOT_READY", "missing": missing}
    return items


def _maturity_score(project_id: str) -> float:
    from .maturity import maturity_metrics

    score = maturity_metrics(project_id, include_development_readiness=False).get("maturity_score", 0.0)
    return float(score) if isinstance(score, (int, float)) else 0.0


NEXT_STEPS: dict[str, tuple[str, str, str]] = {
    # key: (title, text, command)
    "ingest": ("Load the initial requirement", "Run /ingest PROJECT_ID --source PATH.", "/ingest {pid} --source PATH"),
    # IMP-311: the brief v2 needs its profile and genesis confirmed once; the values are a proposal.
    "brief_settings": ("Confirm the brief settings",
                       "This project compiles the brief v2. Confirm its profile and genesis once with /brief; "
                       "the suggested values come from the raw input, so check them first.",
                       "/brief {pid} --profile {profiles} --genesis {genesis}"),
    "resolve_blocking": ("Waiting for client answers", "Send the client the interview script (/export --artifact gaps --format interview) and run /resolve-gaps when answers return.", "/resolve-gaps {pid} --source PATH"),
    "fix_brief": ("Fix what stopped the brief", "Resolve what /brief reported (threshold, self-correction or implementability) and run /brief again.", "/brief {pid}"),
    "specs": ("Prepare PRD and specs", "Run /specs PROJECT_ID.", "/specs {pid}"),
    "fix_specs": ("Raise the specs above the threshold", "Close the gaps the specs readiness reported and run /specs again.", "/specs {pid}"),
    "backlog": ("Prepare the backlog", "Run /backlog PROJECT_ID.", "/backlog {pid}"),
    "quality": ("Check the backlog", "Run /quality PROJECT_ID and fix the stories that fail Definition of Ready.", "/quality {pid}"),
    "resolve_gaps": ("Resolve pending gaps",
                     "No blocking gap is open. Close the remaining ones if you can, or move on: run /brief, then /specs.",
                     "/resolve-gaps {pid} --source PATH"),
    "brief": ("Generate the Project Brief", "Run /brief PROJECT_ID.", "/brief {pid}"),
    # IMP-325: the steps /next never gave.
    "brief_missing": ("Regenerate the project brief",
                      "The project brief is missing although the project is past it; regenerate it before going on.",
                      "/brief {pid}"),
    "health": ("Fix what makes the project unhealthy",
               "Health is DIRTY, so /backlog and /quality refuse. Run /health to see why, fix it with the owning "
               "command (never by hand), then continue.",
               "/health {pid}"),
    "handoff": ("Validate and hand off",
                "The backlog and its quality check are done. Run /validate, export what you hand off with /export, "
                "and track each story with /story-status.",
                "/validate {pid}"),
}

ASSUMED_BLOCKING_NOTE = (
    " An assumption is registered for {ids}: it keeps the work visible but never unblocks. To move on without "
    "the client, confirm the answer in your own name with /resolve-gaps (Decision status: confirmed, Owner / "
    "source: you)."
)
CHANGE_CONFIRMATION_STEP = (
    "Confirm a late change",
    "A late change waits for your decision: {ids}. Read each one in gaps.md (the note and the item it "
    "changes are both quoted), then accept it to apply the change or reject it as a false alarm.",
    "/gaps {pid} --id {gap} --disposition accepted|rejected",
)
POST_BRIEF_STAGES = {"READY_FOR_SPECS", "SPECS_BELOW_THRESHOLD", "READY_FOR_BACKLOG"}


def next_step(
    project_id: str,
    state: dict[str, Any],
    verdict: dict[str, Any],
    *,
    has_stories: bool,
    has_brief: bool,
    assumed_blocking: list[str] | None = None,
) -> dict[str, str]:
    """The one next-step decision, derived from the verdict and the stage."""
    counts = verdict["counts"]
    stage = str(state.get("readiness_stage", "DISCOVERY_RAW"))
    dirty = str(state.get("health", "")).upper() == "DIRTY"
    settings: dict[str, Any] | None = None
    if state.get("phase") == "initialized" or not counts.get("total") and not (workspace_path(project_id) / "01_discovery" / "gaps.md").exists():
        key = "ingest"
    elif (settings := unconfirmed_brief_settings(project_id)) is not None:
        key = "brief_settings"
    elif verdict["blocking_open"]:
        key = "resolve_blocking"
    elif stage in BRIEF_BLOCK_STAGES:
        key = "fix_brief"
    elif stage in POST_BRIEF_STAGES and not has_brief:
        key = "brief_missing"  # IMP-325: a deleted brief used to be ignored past /brief
    elif (dirty or _refresh_pending(project_id)) and (fixes := _health_fixes(project_id)):
        # IMP-369: the same classification as the DIRTY gate of /backlog, so /next names the
        # concrete command ("Run /specs, then /backlog.") instead of "fix what is unhealthy".
        return health_fix_step(project_id, fixes)
    elif stage == "READY_FOR_SPECS":
        key = "specs"
    elif stage == "SPECS_BELOW_THRESHOLD":
        key = "fix_specs"
    elif stage == "READY_FOR_BACKLOG":
        # IMP-325: /quality never moves the stage, so /next repeated /quality forever, and a
        # DIRTY project was sent to /backlog or /quality, which refuse it.
        if dirty:
            key = "health"
        elif has_stories and state.get("phase") == "quality_completed":
            key = "handoff"
        else:
            key = "quality" if has_stories else "backlog"
    elif counts.get("open") or counts.get("answered") or counts.get("partially_closed"):
        key = "resolve_gaps"
    elif not has_brief:
        key = "brief"
    else:
        key = "specs"
    title, text, command = NEXT_STEPS[key]
    changes = [gap_id for gap_id in verdict.get("blocking_open", []) if str(gap_id).startswith("GAP-CHG-")]
    if key == "resolve_blocking" and changes:
        # IMP-337: a late change waits for the BA, not for the client.
        title, text, command = CHANGE_CONFIRMATION_STEP
        text = text.format(ids=", ".join(changes))
        command = command.replace("{gap}", changes[0])
    if key == "resolve_blocking" and assumed_blocking:
        text += ASSUMED_BLOCKING_NOTE.format(ids=", ".join(assumed_blocking))
    proposal = settings or {}
    command = command.format(pid=project_id, profiles=",".join(proposal.get("profiles", ["UI"])),
                             genesis=proposal.get("genesis", "greenfield"))
    return {"key": key, "title": title, "text": text, "command": release_scoped_command(command)}


CHANGE_TEXT = {
    "es": {
        "scope": ("Cerrar el borde del cambio",
                  "Respondé GAP-SCOPE con el borde del cambio (una línea por superficie: zona | tipo | nombre) y corré /resolve-gaps."),
        "baseline": ("Registrar la línea de base",
                     "{cid} no tiene ninguna fuente de lo construido registrada. Cargá el relevamiento, el SAD o el manual con "
                     "/sources {pid} --load ARCHIVO --role linea_de_base --change {cid}. Si el cambio no tiene línea de base, "
                     "decilo con /sources {pid} --change {cid} --no-baseline --reason \"…\""),
        "lenses": ("Cerrar las preguntas bloqueantes del cambio",
                   "{cid} tiene {n} gap(s) bloqueante(s) abierto(s): respondelos en un archivo de respuestas "
                   "(no en gaps.md, que lo genera Sentinel) y corré /resolve-gaps --change {cid}."),
        "brief": ("Compilar el brief del cambio", "Corré /brief --change {cid}: todavía no hay {path}."),
        "brief_stale": ("Recompilar el brief del cambio",
                        "Recompilá el brief del cambio ({cid}): cambió el estado de los gaps. Corré /brief --change {cid}."),
        "requirements": ("Responder los requisitos del cambio",
                         "{cid} no tiene filas EARS con Delta ADDED, MODIFIED o REMOVED: respondé {ids} en EARS con Delta y Superficie y corré /resolve-gaps."),
        "requirements_none": ("Responder los requisitos del cambio",
                              "{cid} no tiene ninguna pregunta funcional abierta donde responder los requisitos; el pedido los trae "
                              "pero Sentinel todavía no los extrae solo (llega en un próximo incremento). Mientras tanto el cambio se queda en este paso y el BA revisa el pedido a mano."),
        "specs": ("Preparar las specs del cambio", "Corré /specs --change {cid}: faltan o no están al día con sus filas EARS."),
        "backlog": ("Preparar el backlog del cambio", "Corré /backlog --change {cid}: falta o está atrasado respecto de las specs."),
        "validate": ("Validar el cambio", "Corré /validate --change {cid}: hay hallazgos por corregir."),
        "pending_extraction": ("Pasar el contenido del pedido al brief",
                               "{cid}: el brief no tiene todavía el contenido del pedido en {sections}. Sentinel todavía no lo extrae solo "
                               "(llega en un próximo incremento). La marca se limpia solo cuando se responde una pregunta de esa sección; "
                               "si el cambio no tiene ninguna abierta, la marca queda hasta el incremento de extracción, el cambio sigue "
                               "en este paso, /export --final se rechaza y el BA revisa el pedido a mano."),
        "done": ("Piezas del cambio al día",
                 "Las piezas registradas de {cid} están al día. Sentinel todavía no mide qué parte del pedido quedó cubierta: "
                 "verificá que cada regla y criterio del pedido tenga su requisito o su descarte."),
    },
    "en": {
        "scope": ("Close the change border",
                  "Answer GAP-SCOPE with the change border (one line per surface: zone | type | name) and run /resolve-gaps."),
        "baseline": ("Register the baseline",
                     "{cid} has no source of what is built registered. Load the survey, the SAD or the manual with "
                     "/sources {pid} --load FILE --role linea_de_base --change {cid}. If the change has no baseline, "
                     "say so with /sources {pid} --change {cid} --no-baseline --reason \"…\""),
        "lenses": ("Close the change's blocking questions",
                   "{cid} has {n} blocking gap(s) open: answer them in a responses file "
                   "(not in gaps.md, which Sentinel generates) and run /resolve-gaps --change {cid}."),
        "brief": ("Compile the change brief", "Run /brief --change {cid}: there is no {path} yet."),
        "brief_stale": ("Recompile the change brief",
                        "Recompile the change brief ({cid}): the state of the gaps changed. Run /brief --change {cid}."),
        "requirements": ("Answer the change requirements",
                         "{cid} has no EARS rows with Delta ADDED, MODIFIED or REMOVED: answer {ids} in EARS with Delta and Superficie and run /resolve-gaps."),
        "requirements_none": ("Answer the change requirements",
                              "{cid} has no open functional question where the requirements can be answered; the request brings them "
                              "but Sentinel does not extract them on its own yet (coming in a later increment). Meanwhile the change stays at this step and the BA checks the request by hand."),
        "specs": ("Prepare the change specs", "Run /specs --change {cid}: they are missing or not current with its EARS rows."),
        "backlog": ("Prepare the change backlog", "Run /backlog --change {cid}: it is missing or behind the specs."),
        "validate": ("Validate the change", "Run /validate --change {cid}: there are findings to fix."),
        "pending_extraction": ("Move the request content into the brief",
                               "{cid}: the brief does not hold the request content yet in {sections}. Sentinel does not extract it on its own "
                               "yet (coming in a later increment). The mark clears only when a question of that section is answered; "
                               "if the change has no such open question, the mark stays until the extraction increment, the change stays "
                               "at this step, /export --final is refused and the BA checks the request by hand."),
        "done": ("Change pieces up to date",
                 "The registered pieces of {cid} are up to date. Sentinel does not yet measure how much of the request is covered: "
                 "check that each rule and criterion of the request has its requirement or its discard."),
    },
}
CHANGE_COMMANDS = {
    "scope": "/resolve-gaps {pid} --source PATH --change {cid}",
    "baseline": "/sources {pid} --load PATH --role linea_de_base --change {cid}",
    "lenses": "/resolve-gaps {pid} --source PATH --change {cid}",
    "brief": "/brief {pid} --change {cid}",
    "requirements": "/resolve-gaps {pid} --source PATH --change {cid}",
    "specs": "/specs {pid} --change {cid}",
    "backlog": "/backlog {pid} --change {cid}",
    "validate": "/validate {pid} --change {cid}",
    "pending_extraction": "",
    "done": "",
}


def _change_step_key(project_id: str, change_id: str, change: dict[str, Any]) -> str:
    """IMP-396: the first step of the change's sequence that is still pending (none ever suggests the PRD)."""
    from .change_requirements import load_change_ears, parse_delta
    from .change_validation import validate_change
    from .compilers.change_backlog import read_change_units, specs_currency
    from .compilers.change_specs import UNIT_DELTAS

    base = workspace_path(project_id)
    if change.get("round") == "scope":
        return "scope"
    if not change.get("baseline_waived") and not _has_baseline(project_id):
        return "baseline"
    if int((change.get("gap_counts") or {}).get("blocking_open", 0) or 0) > 0:
        return "lenses"
    if not (base / "02_requirements" / change_id / "project-brief.md").is_file() or _brief_stale(base, change_id, change):
        return "brief"
    if not any(parse_delta(row["delta"]) in UNIT_DELTAS for row in load_change_ears(project_id, change_id)):
        return "requirements"
    if (not change.get("specs") or not (base / "03_specs" / change_id / "specs.md").is_file()
            or specs_currency(project_id, change_id) != "current"):
        return "specs"
    if not change.get("backlog") or _backlog_behind(
            base, change_id, read_change_units(project_id, change_id), list(change["backlog"].get("dropped_units") or [])):
        return "backlog"
    if validate_change(project_id, change_id)["verdict"] != "VALID":
        return "validate"
    if _extraction_pending(base, change_id):
        return "pending_extraction"
    return "done"


def _has_baseline(project_id: str) -> bool:
    """IMP-400: some current registered row of the workspace plays the baseline role (the baseline belongs to the system)."""
    from .source_registry import row_role
    from .sources import load_source_manifest

    return any(r.get("validity", "current") == "current" and row_role(r) == "linea_de_base"
               for r in load_source_manifest(project_id).get("registry", []))


def _open_ears_gaps(base: Path, change_id: str) -> list[str]:
    """IMP-398: the open gaps of the change where EARS requirements can be answered (only ones that exist)."""
    from .changes import change_gaps_path
    from .gap_resolution import EARS_ELIGIBLE_GAP_IDS
    from .gaps import parse_gap_rows

    path = change_gaps_path(base, change_id)
    if not path.exists():
        return []
    rows = parse_gap_rows(path.read_text(encoding="utf-8"))
    return [row["id"] for row in rows
            if row["id"] in EARS_ELIGIBLE_GAP_IDS and str(row.get("status", "OPEN")).strip("`").upper() != "CLOSED"]


def _brief_stale(base: Path, change_id: str, change: dict[str, Any]) -> bool:
    """IMP-396: the compiled brief's report no longer matches the change's blocking gaps (or has no report)."""
    from .core.io import read_json

    report = read_json(base / "02_requirements" / change_id / "change_brief_report.json", None)
    if not isinstance(report, dict):
        return True
    try:
        recorded = int(report.get("blocking_open", 0) or 0)
    except (TypeError, ValueError):
        return True
    return recorded != int((change.get("gap_counts") or {}).get("blocking_open", 0) or 0)


def _backlog_behind(base: Path, change_id: str, units: list[dict[str, Any]], dropped_units: list[str]) -> bool:
    """The units the change's stories came from differ from the current units of its specs.

    Units `/backlog --change` deliberately dropped (a REMOVED row over only not-implemented stories) have no story and are not counted;
    a dropped unit no longer in the specs is ignored."""
    from .core.markdown import parse_frontmatter

    sources: set[str] = set()
    for path in sorted((base / "04_backlog").glob("US-*.md")):
        try:
            front = parse_frontmatter(path.read_text(encoding="utf-8"))
        except OSError:
            continue
        if str(front.get("change", "")).strip() == change_id:
            sources.add(str(front.get("source_unit", "")).strip())
    return sources != {unit["id"] for unit in units} - set(dropped_units)


def change_next_step(project_id: str, change_id: str) -> dict[str, str]:
    """IMP-396: the next step of one change, in the change's language."""
    from .changes import change_language, get_change

    change = get_change(project_id, change_id)
    key = _change_step_key(project_id, change_id, change)
    texts = CHANGE_TEXT.get(change_language(project_id, change), CHANGE_TEXT["es"])
    stale = key == "brief" and (workspace_path(project_id) / "02_requirements" / change_id / "project-brief.md").is_file()
    base = workspace_path(project_id)
    ears_gaps = _open_ears_gaps(base, change_id) if key == "requirements" else []
    text_key = "brief_stale" if stale else key
    if key == "requirements" and not ears_gaps:
        text_key = "requirements_none"
    title, text = texts[text_key]
    ctx = {
        "cid": change_id, "pid": project_id,
        "ids": ", ".join(ears_gaps),
        "sections": ", ".join(f"§{n}" for n in _extraction_pending(base, change_id)),
        "n": int((change.get("gap_counts") or {}).get("blocking_open", 0) or 0),
        "path": f"02_requirements/{change_id}/project-brief.md",
    }
    return {"change_id": change_id, "key": key, "title": title, "text": text.format(**ctx),
            "command": CHANGE_COMMANDS[key].format(**ctx)}


def changes_overview(project_id: str) -> list[dict[str, Any]]:
    """IMP-396: per change, its next step and its escalation warnings."""
    from .change_escalation import escalation_warnings
    from .changes import list_changes

    return [
        {"change_id": change_id, "next_step": change_next_step(project_id, change_id),
         "warnings": escalation_warnings(project_id, change_id)}
        for change_id in sorted(list_changes(project_id))
    ]


def _first_change_step(overview: list[dict[str, Any]]) -> dict[str, str]:
    """The first change with a pending step (or the first change when all are done).

    Its `change_id` is exposed at top level only in a change-only workspace, where this replaces the project step."""
    pending = [item["next_step"] for item in overview if item["next_step"]["key"] != "done"]
    return dict((pending or [overview[0]["next_step"]])[0])


def release_scoped_command(command: str) -> str:
    """IMP-370: inside a release scope, a suggested release command keeps `--release rN`.

    `/next --release r1` used to suggest `/validate ACME_CLAIMS`, which runs over the
    whole workspace. Commands that take no `--release` (/resolve-gaps, /gaps...) stay as they are.
    """
    from .commands import RELEASE_COMMANDS
    from .release_scope import active_release

    release = active_release()
    if not release or "--release" in command:
        return command
    verb = command.split(" ", 1)[0].lstrip("/")
    return f"{command} --release {release}" if verb in RELEASE_COMMANDS else command


HEALTH_FIX_TITLES = {
    "reindex": "Index what the last commands recorded",
    "gaps": "Close the blocking questions",
    "feedback": "Settle the open implementation feedback",
    "stale": "Review the Stale stories",
    "chain": "Regenerate what the change made stale",
    "review": "Review the semantic change",
    "other": "Fix what makes the project unhealthy",
}


def _refresh_pending(project_id: str) -> bool:
    from .protocols import downstream_refresh_pending

    return downstream_refresh_pending(project_id)


def _health_fixes(project_id: str) -> list[dict[str, Any]]:
    from .health import health_fixes

    return health_fixes(project_id)


def health_fix_step(project_id: str, fixes: list[dict[str, Any]]) -> dict[str, str]:
    """IMP-369: the next step while health is DIRTY: each fix in order, the first command to run."""
    first = fixes[0]
    command = first["steps"][0]
    if " " not in command:  # the regeneration chain names bare commands (/brief, /specs, /backlog)
        command = f"{command} {project_id}"
    steps = " ".join(f"{number}. {fix['label']} {fix['fix']}" for number, fix in enumerate(fixes, start=1))
    text = ("Health is DIRTY, so /backlog, /quality and /refine-backlog refuse until this is done. "
            + (steps if len(fixes) > 1 else f"{first['label']} {first['fix']}"))
    return {"key": "health", "title": HEALTH_FIX_TITLES.get(first["kind"], HEALTH_FIX_TITLES["other"]),
            "text": text, "command": command}


def unconfirmed_brief_settings(project_id: str) -> dict[str, Any] | None:
    """IMP-311: the proposed settings when the project is on brief v2 and has not confirmed them; else None."""
    from .brief_schema import brief_settings, settings_status
    from .discovery.channels import raw_input_text

    if int(brief_settings(project_id).get("brief_version", 1) or 1) != 2:
        return None
    status = settings_status(project_id, raw_input_text(workspace_path(project_id)))
    return None if status["confirmed"] else status["proposal"]
