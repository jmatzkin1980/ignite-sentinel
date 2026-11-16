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
    if not discovered:
        blockers.append("Discovery has not run: there is no 01_discovery/gaps.md.")
    if blocking_open:
        blockers.append(f"{len(blocking_open)} blocking gap(s) open: {', '.join(blocking_open)}.")

    gate_matrix = [{"gate": "gaps", "state": "BLOCKING_OPEN" if blocking_open else ("CLEAR" if discovered else "NOT_RUN"), "blocks": bool(blocking_open) or not discovered}]

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
    return result


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
    "resolve_blocking": ("Waiting for client answers", "Share gaps.md with the client and run /resolve-gaps when answers return.", "/resolve-gaps {pid} --source PATH"),
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
    if key == "resolve_blocking" and assumed_blocking:
        text += ASSUMED_BLOCKING_NOTE.format(ids=", ".join(assumed_blocking))
    proposal = settings or {}
    return {"key": key, "title": title, "text": text,
            "command": command.format(pid=project_id, profiles=",".join(proposal.get("profiles", ["UI"])),
                                      genesis=proposal.get("genesis", "greenfield"))}


def unconfirmed_brief_settings(project_id: str) -> dict[str, Any] | None:
    """IMP-311: the proposed settings when the project is on brief v2 and has not confirmed them; else None."""
    from .brief_schema import brief_settings, settings_status
    from .discovery.workflow import raw_input_text

    if int(brief_settings(project_id).get("brief_version", 1) or 1) != 2:
        return None
    status = settings_status(project_id, raw_input_text(workspace_path(project_id)))
    return None if status["confirmed"] else status["proposal"]
