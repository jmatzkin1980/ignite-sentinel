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
        # IMP-402: `done` means the request is fully extracted (its coverage is in the change's step), so a done
        # change adds no warning; a pending one blocks with its step
        pending = [item for item in overview if item["next_step"]["key"] != "done"]
        blockers[:0] = [_change_blocker(project_id, item) for item in pending]

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
        "crosses": ("Registrar los cruces del pedido",
                    "Faltan {n} cruce(s) de {cid}: {missing}. El agente escribe cada cruce con citas literales y Sentinel las valida y abre las "
                    "preguntas que salgan; si un cruce no aplica, descartalo con /cross {pid} --change {cid} --kind TIPO --skip --reason \"…\". "
                    "La extracción viene después, corregida con lo que salga de los cruces."),
        "cross_new_surfaces": ("Decidir las superficies nuevas",
                               "El harvest de {cid} no encontró en lo construido {n} cosa(s): {items}. Si hay que construirla en este cambio, "
                               "aceptala como superficie nuevo del borde con /cross {pid} --change {cid} --accept-new ID --type TIPO --name NOMBRE; "
                               "si no, descartala con /cross {pid} --change {cid} --decline-new ID --reason \"…\"."),
        "extract_inventory": ("Inventariar el pedido",
                              "Corré /extract {pid} --change {cid}: Sentinel lista cada regla, criterio, historia, decisión y sección del pedido de {cid}; "
                              "ese inventario es el denominador de la cobertura."),
        "extract_inventory_stale": ("Reinventariar el pedido",
                                    "El pedido de {cid} cambió desde el inventario: corré /extract {pid} --change {cid}. "
                                    "Los elementos que no cambiaron conservan su propuesta; los que cambiaron quedan para volver a proponer."),
        "extract_unreadable": ("Cargar una copia legible del pedido",
                               "Sentinel no pudo leer {unreadable} (pedido de {cid}): sin su texto no hay inventario ni cobertura de esa parte. "
                               "Cargá una copia legible (Markdown o texto) con /sources {pid} --load ARCHIVO --role pedido --change {cid}, "
                               "marcá la ilegible como superada (/sources {pid} --id {first_unreadable} --superseded-by F-NN --reason \"…\") "
                               "y corré /extract {pid} --change {cid}."),
        "extract_proposals": ("Proponer el tratamiento de cada elemento",
                              "{pending} de {total} elementos del pedido de {cid} no tienen propuesta. Copiá "
                              "`02_requirements/{cid}/extraction/proposals_template.md` fuera de 02_requirements, completá por elemento "
                              "requisito (EARS con Delta y Superficie por enunciado), sección o descarte, con una cita literal, y corré "
                              "/extract {pid} --change {cid} --proposals ARCHIVO."),
        "extract_confirm": ("Confirmar la extracción",
                            "{proposed} propuesta(s) de {cid} esperan la confirmación del BA, {flagged} marcada(s). Revisá "
                            "`02_requirements/{cid}/extraction/review.md`; confirmá por sección con /extract {pid} --change {cid} "
                            "--confirm SECCION, o todo lo no marcado con --confirm all. Lo marcado se confirma uno por uno con "
                            "--confirm-item ID o se rechaza con --reject-item ID --reason TEXTO."),
        "extract_confirm_flagged": ("Confirmar una por una lo marcado",
                                    "Las {proposed} propuesta(s) que quedan en {cid} están marcadas ({items}) y --confirm no las toma en bloque. "
                                    "Revisá `02_requirements/{cid}/extraction/review.md` y confirmá cada una con /extract {pid} --change {cid} "
                                    "--confirm-item ID, o rechazala con --reject-item ID --reason TEXTO."),
        "extract_orphans": ("Sacar los elementos huérfanos",
                            "Estos elementos ya no están en el pedido de {cid} pero sus filas EARS siguen en pie: {orphans}. "
                            "Sacá cada uno con /extract {pid} --change {cid} --reject-item ID --reason \"…\": sus filas quedan reemplazadas."),
        "preserved": ("Cubrir lo preservado",
                      "Estas superficies preservadas de {cid} no tienen ninguna fila UNCHANGED: {names}. Cada una necesita al menos un "
                      "requisito UNCHANGED, que pasa a ser un criterio pass-to-pass: proponelo en la extracción o respondelo en una "
                      "pregunta con Delta UNCHANGED y Superficie."),
        "preserved_answer": ("Cubrir lo preservado",
                             "Estas superficies preservadas de {cid} no tienen ninguna fila UNCHANGED: {names}. El pedido no trae elementos "
                             "que citar, así que respondé una pregunta EARS del cambio ({ids}) con un requisito Delta UNCHANGED y su "
                             "Superficie, y corré /resolve-gaps {pid} --source ARCHIVO --change {cid}."),
        "preserved_source": ("Cubrir lo preservado",
                             "Estas superficies preservadas de {cid} no tienen ninguna fila UNCHANGED: {names}. El pedido no trae "
                             "elementos que citar y no queda ninguna pregunta EARS abierta: cargá una nota que diga qué se preserva con "
                             "/sources {pid} --load ARCHIVO --role pedido --change {cid}, corré /extract {pid} --change {cid} y "
                             "proponé un requisito UNCHANGED con su Superficie."),
        "requirements": ("Responder los requisitos del cambio",
                         "{cid} no tiene filas EARS con Delta ADDED, MODIFIED o REMOVED: respondé {ids} en EARS con Delta y Superficie y corré /resolve-gaps "
                         "o proponé los requisitos desde la extracción (/extract {pid} --change {cid} --proposals ARCHIVO)."),
        "requirements_none": ("Proponer los requisitos del cambio",
                              "{cid} no tiene filas EARS con Delta ADDED, MODIFIED o REMOVED. Proponelas desde la extracción "
                              "(Tratamiento: requisito) con /extract {pid} --change {cid} --proposals ARCHIVO."),
        "specs": ("Preparar las specs del cambio", "Corré /specs --change {cid}: faltan o no están al día con sus filas EARS."),
        "backlog": ("Preparar el backlog del cambio", "Corré /backlog --change {cid}: falta o está atrasado respecto de las specs."),
        "validate": ("Validar el cambio", "Corré /validate --change {cid}: hay hallazgos por corregir."),
        "done": ("Cambio al día: pedido cubierto",
                 "Las piezas de {cid} están al día. La extracción cubre {coverage} y cada superficie preservada tiene su fila UNCHANGED."),
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
        "crosses": ("Record the cross-reads of the request",
                    "{n} cross-read(s) of {cid} are missing: {missing}. The agent writes each cross-read with verbatim quotes and Sentinel "
                    "validates them and opens the questions that come out; if a cross-read does not apply, waive it with "
                    "/cross {pid} --change {cid} --kind KIND --skip --reason \"…\". The extraction comes after, corrected with what the "
                    "cross-reads bring."),
        "cross_new_surfaces": ("Decide the new surfaces",
                               "The harvest of {cid} found {n} thing(s) not in what is built: {items}. If it has to be built in this change, "
                               "accept it as a new surface of the border with /cross {pid} --change {cid} --accept-new ID --type TYPE --name NAME; "
                               "otherwise decline it with /cross {pid} --change {cid} --decline-new ID --reason \"…\"."),
        "extract_inventory": ("Inventory the request",
                              "Run /extract {pid} --change {cid}: Sentinel lists each rule, criterion, story, decision and section of the request of {cid}; "
                              "that inventory is the denominator of the coverage."),
        "extract_inventory_stale": ("Re-inventory the request",
                                    "The request of {cid} changed since the inventory: run /extract {pid} --change {cid}. "
                                    "Elements that did not change keep their proposal; the ones that changed are left to propose again."),
        "extract_unreadable": ("Load a readable copy of the request",
                               "Sentinel could not read {unreadable} (request of {cid}): without its text that part has no inventory and no coverage. "
                               "Load a readable copy (Markdown or text) with /sources {pid} --load FILE --role pedido --change {cid}, "
                               "mark the unreadable one as superseded (/sources {pid} --id {first_unreadable} --superseded-by F-NN --reason \"…\") "
                               "and run /extract {pid} --change {cid}."),
        "extract_proposals": ("Propose the treatment of each element",
                              "{pending} of {total} request elements of {cid} have no proposal. Copy "
                              "`02_requirements/{cid}/extraction/proposals_template.md` outside 02_requirements, fill in per element "
                              "requirement (EARS with Delta and Surface per statement), section or discard, with a verbatim quote, and run "
                              "/extract {pid} --change {cid} --proposals FILE."),
        "extract_confirm": ("Confirm the extraction",
                            "{proposed} proposal(s) of {cid} await the BA's confirmation, {flagged} flagged. Review "
                            "`02_requirements/{cid}/extraction/review.md`; confirm by section with /extract {pid} --change {cid} "
                            "--confirm SECTION, or everything not flagged with --confirm all. Flagged ones are confirmed one by one with "
                            "--confirm-item ID or rejected with --reject-item ID --reason TEXT."),
        "extract_confirm_flagged": ("Confirm the flagged ones one by one",
                                    "The {proposed} proposal(s) left in {cid} are flagged ({items}) and --confirm does not take them in bulk. "
                                    "Review `02_requirements/{cid}/extraction/review.md` and confirm each one with /extract {pid} --change {cid} "
                                    "--confirm-item ID, or reject it with --reject-item ID --reason TEXT."),
        "extract_orphans": ("Take out the orphan elements",
                            "These elements are no longer in the request of {cid} but their EARS rows still stand: {orphans}. "
                            "Take each one out with /extract {pid} --change {cid} --reject-item ID --reason \"…\": its rows are superseded."),
        "preserved": ("Cover what is preserved",
                      "These preserved surfaces of {cid} have no UNCHANGED row: {names}. Each needs at least one UNCHANGED "
                      "requirement, which becomes a pass-to-pass criterion: propose it in the extraction or answer it in a "
                      "question with Delta UNCHANGED and Surface."),
        "preserved_answer": ("Cover what is preserved",
                             "These preserved surfaces of {cid} have no UNCHANGED row: {names}. The request brings no elements to "
                             "quote, so answer an EARS question of the change ({ids}) with a Delta UNCHANGED requirement and its "
                             "Surface, and run /resolve-gaps {pid} --source FILE --change {cid}."),
        "preserved_source": ("Cover what is preserved",
                             "These preserved surfaces of {cid} have no UNCHANGED row: {names}. The request brings no elements to "
                             "quote and no EARS question is left open: load a note saying what is preserved with "
                             "/sources {pid} --load FILE --role pedido --change {cid}, run /extract {pid} --change {cid} and "
                             "propose an UNCHANGED requirement with its Surface."),
        "requirements": ("Answer the change requirements",
                         "{cid} has no EARS rows with Delta ADDED, MODIFIED or REMOVED: answer {ids} in EARS with Delta and Superficie and run /resolve-gaps "
                         "or propose the requirements from the extraction (/extract {pid} --change {cid} --proposals FILE)."),
        "requirements_none": ("Propose the change requirements",
                              "{cid} has no EARS rows with Delta ADDED, MODIFIED or REMOVED. Propose them from the extraction "
                              "(Treatment: requirement) with /extract {pid} --change {cid} --proposals FILE."),
        "specs": ("Prepare the change specs", "Run /specs --change {cid}: they are missing or not current with its EARS rows."),
        "backlog": ("Prepare the change backlog", "Run /backlog --change {cid}: it is missing or behind the specs."),
        "validate": ("Validate the change", "Run /validate --change {cid}: there are findings to fix."),
        "done": ("Change up to date: request covered",
                 "The pieces of {cid} are up to date. The extraction covers {coverage} and each preserved surface has its UNCHANGED row."),
    },
}
CHANGE_COMMANDS = {
    "scope": "/resolve-gaps {pid} --source PATH --change {cid}",
    "baseline": "/sources {pid} --load PATH --role linea_de_base --change {cid}",
    "lenses": "/resolve-gaps {pid} --source PATH --change {cid}",
    "crosses": "{cross_command}",
    "cross_new_surfaces": "/cross {pid} --change {cid} --accept-new {first_candidate} --type TIPO --name NOMBRE",
    "extract_inventory": "/extract {pid} --change {cid}",
    "extract_unreadable": "/sources {pid} --load PATH --role pedido --change {cid}",
    "extract_proposals": "/extract {pid} --change {cid} --proposals PATH",
    "extract_confirm": "/extract {pid} --change {cid} --confirm all",
    "extract_confirm_flagged": "/extract {pid} --change {cid} --confirm-item {first_flagged}",
    "extract_orphans": "/extract {pid} --change {cid} --reject-item {first_orphan} --reason \"...\"",
    "preserved": "/extract {pid} --change {cid} --proposals PATH",
    "preserved_answer": "/resolve-gaps {pid} --source PATH --change {cid}",
    "preserved_source": "/sources {pid} --load PATH --role pedido --change {cid}",
    "brief": "/brief {pid} --change {cid}",
    "requirements": "/resolve-gaps {pid} --source PATH --change {cid}",
    "specs": "/specs {pid} --change {cid}",
    "backlog": "/backlog {pid} --change {cid}",
    "validate": "/validate {pid} --change {cid}",
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
    from .crosses.state import cross_status
    from .crosses.surfaces import new_surface_candidates

    if cross_status(project_id, change_id)["missing"]:
        return "crosses"
    if any(c["decision"] is None for c in new_surface_candidates(project_id, change_id)):
        return "cross_new_surfaces"
    from .extraction.coverage import extraction_coverage, preserved_coverage

    cover = extraction_coverage(project_id, change_id)
    if cover["state"] in ("missing", "stale"):
        return "extract_inventory"
    if cover.get("unreadable"):
        return "extract_unreadable"
    if cover["pending"] > 0:
        return "extract_proposals"
    if cover["proposed"] > 0:
        return "extract_confirm"
    if cover.get("orphans"):
        return "extract_orphans"
    if preserved_coverage(project_id, change_id)["missing"]:
        return "preserved"
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
    if recorded != int((change.get("gap_counts") or {}).get("blocking_open", 0) or 0):
        return True
    # IMP-402: something was confirmed, corrected or taken out of the extraction since the brief was compiled.
    from .extraction.coverage import extraction_fingerprint

    if str(report.get("extraction_fingerprint", "") or "") != extraction_fingerprint(base, change_id):
        return True
    # IMP-404: a cross-read was done, waived or decided (a new surface) since the brief was compiled.
    from .crosses.state import crosses_fingerprint

    return str(report.get("crosses_fingerprint", "") or "") != crosses_fingerprint(base.name, change_id)


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


CROSS_MISSING = {
    "es": {"linea_de_base": "línea de base", "diseno": "diseño nuevo", "contradicciones": "contradicciones internas del pedido",
           "no_design": " — no hay prototipo cargado: /sources {pid} --load ARCHIVO --role diseno_nuevo --change {cid}",
           "stale": " — las fuentes citadas cambiaron: {sources}"},
    "en": {"linea_de_base": "baseline", "diseno": "new design", "contradicciones": "internal contradictions of the request",
           "no_design": " — no prototype is loaded: /sources {pid} --load FILE --role diseno_nuevo --change {cid}",
           "stale": " — the cited sources changed: {sources}"},
}


def _cross_step_context(project_id: str, change_id: str, language: str) -> dict[str, str]:
    """The `{missing}` list and the first command of the `crosses` step."""
    from .crosses.state import cross_status

    labels = CROSS_MISSING["es" if language == "es" else "en"]
    status = cross_status(project_id, change_id)
    pid, cid = project_id, change_id
    commands = {
        "linea_de_base": f"/harvest {pid} --source ARCHIVO --change {cid}",
        "diseno": f"/cross {pid} --change {cid} --kind diseno --claims ARCHIVO",
        "contradicciones": f"/cross {pid} --change {cid} --kind contradicciones --claims ARCHIVO",
    }
    parts: list[str] = []
    first = ""
    for kind in status["missing"]:
        info = status["kinds"][kind]
        part = f"{labels[kind]} ({commands[kind]})"
        no_design = kind == "diseno" and not status["design_sources"]
        if no_design:
            part += labels["no_design"].format(pid=pid, cid=cid)
        if info["state"] == "stale":
            part += labels["stale"].format(sources=", ".join(info["stale_sources"]))
        parts.append(part)
        if not first:
            first = (f"/sources {pid} --load PATH --role diseno_nuevo --change {cid}" if no_design
                     else commands[kind].replace("ARCHIVO", "PATH"))
    return {"missing": "; ".join(parts), "n_missing": str(len(parts)), "cross_command": first}


def change_next_step(project_id: str, change_id: str) -> dict[str, str]:
    """IMP-396: the next step of one change, in the change's language."""
    from .changes import change_language, get_change
    from .extraction.coverage import extraction_coverage, preserved_coverage

    change = get_change(project_id, change_id)
    key = _change_step_key(project_id, change_id, change)
    texts = CHANGE_TEXT.get(change_language(project_id, change), CHANGE_TEXT["es"])
    base = workspace_path(project_id)
    stale = key == "brief" and (base / "02_requirements" / change_id / "project-brief.md").is_file()
    ears_gaps = _open_ears_gaps(base, change_id) if key in ("requirements", "preserved") else []
    text_key = "brief_stale" if stale else key
    if key == "requirements" and not ears_gaps:
        text_key = "requirements_none"
    cover = extraction_coverage(project_id, change_id)
    if key == "extract_inventory" and cover["state"] == "stale":
        text_key = "extract_inventory_stale"
    if key == "extract_confirm" and cover["proposed"] == cover["flagged"]:
        text_key = "extract_confirm_flagged"  # `--confirm all` would hold every one of them again
    if key == "preserved" and cover["total"] == 0:
        # nothing in the request to quote: the UNCHANGED row comes from an answer, or from a note loaded as a source
        text_key = "preserved_answer" if ears_gaps else "preserved_source"
    title, text = texts[text_key]
    orphans = cover.get("orphans", []) if key == "extract_orphans" else []
    ctx = {
        "cid": change_id, "pid": project_id,
        "ids": ", ".join(ears_gaps),
        "n": int((change.get("gap_counts") or {}).get("blocking_open", 0) or 0),
        "path": f"02_requirements/{change_id}/project-brief.md",
        "total": cover["total"], "pending": cover["pending"], "proposed": cover["proposed"],
        "flagged": cover["flagged"], "coverage": cover["text"],
        "names": ", ".join(preserved_coverage(project_id, change_id)["missing"]) if key == "preserved" else "",
        "unreadable": ", ".join(cover.get("unreadable", [])), "first_unreadable": (cover.get("unreadable") or ["F-NN"])[0],
        "items": ", ".join(cover.get("flagged_ids", [])), "first_flagged": (cover.get("flagged_ids") or ["ID"])[0],
        "orphans": "; ".join(f"{o['id']} ({', '.join(o['rows'])})" for o in orphans),
        "first_orphan": orphans[0]["id"] if orphans else "ID",
    }
    if text_key == "preserved_answer":
        ctx["ids"] = ", ".join(ears_gaps)
    ctx["missing"] = ctx["cross_command"] = ""
    ctx["first_candidate"] = "ID"
    language = change_language(project_id, change)
    if key == "crosses":
        found = _cross_step_context(project_id, change_id, language)
        ctx.update(missing=found["missing"], cross_command=found["cross_command"], n=int(found["n_missing"]))
    if key == "cross_new_surfaces":
        from .crosses.surfaces import new_surface_candidates

        pending = [c for c in new_surface_candidates(project_id, change_id) if c["decision"] is None]
        shown = "; ".join(f"{c['id']} «{c['text']}»" for c in pending[:5])
        if len(pending) > 5:
            shown += f"; {'y' if language == 'es' else 'and'} {len(pending) - 5} {'más' if language == 'es' else 'more'}"
        ctx.update(n=len(pending), items=shown, first_candidate=pending[0]["id"])
    command_key = text_key if text_key in ("extract_confirm_flagged", "preserved_answer", "preserved_source") else key
    command_key = "extract_proposals" if text_key == "requirements_none" else command_key
    return {"change_id": change_id, "key": key, "title": title, "text": text.format(**ctx),
            "command": CHANGE_COMMANDS[command_key].format(**ctx)}


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
