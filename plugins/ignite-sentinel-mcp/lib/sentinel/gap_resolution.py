from __future__ import annotations

from .errors import GateRefusal, InputError  # IMP-302: typed errors

import re
import shutil
from pathlib import Path

from .change_requirements import next_ears_index
from .ears import classify_ears
from .gaps import CHANGE_CLOSURE_REASONS, gap_option_labels, option_markers, CLOSURE_CITES, CLOSURE_REASONS, DECISION_KIND, NON_GOAL_KIND, REOPEN_FALSE_PREMISE, brief_section_for_gap, count_gaps, parse_gap_responses, parse_gap_rows, prd_section_for_gap, readiness_stage_after_gap_change, render_gaps
from .knowledge.metabolism import metabolize_knowledge
from .memory import ContextBroker, reindex_workspace
from .secrets_scan import sanitize_text
from .source_conflicts import UNVALIDATED_SOURCE_NOTE, closing_block_note, unvalidated_trigger
from .sources import mark_source_processed, open_source_row, settle_answer_rerun, source_row
from .core.graph import add_edge, add_node, load_graph, save_graph
from .core.io import append_text, copy_file, write_text
from .core.text import project_language, unique_path
from .workspace import read_json, read_state, state_path, update_state, utc_now, workspace_path

# IMP-250b: the note on a confirmed answer that came from an example file.
EXAMPLE_SOURCE_NOTE = "example-source: an example never closes a rule; confirm it from a governing source"
CONFIRMED_STATUSES = {"confirmado", "confirmed", "no aplica", "not applicable", "n/a", "na"}
# IMP-185: the out-of-scope/not-applicable subset of confirmed closures. A gap
# closed with one of these is a governed Non-Goal (scope exclusion), not a
# positive answer.
NOT_APPLICABLE_STATUSES = {"no aplica", "not applicable", "n/a", "na"}
PENDING_STATUSES = {"pendiente", "pending", "en revision", "en revisión", "to confirm", "tbd"}
VAGUE_ANSWERS = {"tbd", "n/a", "na", "?", "no se", "no sé", "no sabemos", "depende", "to be defined", "pendiente", "lo vemos", "veremos"}
DOMAIN_SOURCE_TOKENS = {
    "architecture", "arquitectura", "backend", "delivery", "design", "diseño",
    "engineering", "frontend", "platform", "quality", "qa", "security",
    "seguridad", "technology", "tecnologia", "tecnología", "tech",
}
INFERENCE_SOURCE_TOKENS = {"agent", "analysis", "analisis", "análisis", "inference", "inferencia", "sentinel"}
# IMP-408: who is an agent (never the decision owner) and what a decision without a named BA is called.
AGENT_OWNER_TOKENS = INFERENCE_SOURCE_TOKENS | {"claude", "codex", "asistente", "assistant"}
UNNAMED_BA = {"es": "BA (sin nombre)", "en": "BA (unnamed)"}
# IMP-408: fields that belong at the same level as `Estado de decisión`, never under it.
MISPLACED_LABELS = ("Borde", "Border", "Opción", "Opcion", "Option", "Delta", "Superficie", "Surface", "Afecta", "Affects",
                    "Motivo de cierre", "Closure reason", "Redactado por", "Drafted by")
EARS_ELIGIBLE_GAP_IDS = {"GAP-ACCEPTANCE", "GAP-BUSINESS-RULES", "GAP-PRD-FR-AC"}
EARS_ELIGIBLE_NOTE = "EARS-eligible, not normalized: confirmed prose answer needs BA-approved EARS rewrite"


def is_substantive_answer(answer: str) -> bool:
    """An answer is substantive when it carries usable content, not a deferral."""
    normalized = re.sub(r"\s+", " ", answer.strip().lower()).strip(".")
    if not normalized or normalized in VAGUE_ANSWERS:
        return False
    return len(normalized) >= 15


def is_ears_eligible_gap(gap_id: str) -> bool:
    return gap_id in EARS_ELIGIBLE_GAP_IDS


def saved_response_files(base: Path) -> list[str]:
    """IMP-320: the answer files /resolve-gaps kept, so a replaced requirement can re-apply them."""
    folder = base / "07_changes" / "00_client_responses"
    if not folder.is_dir():
        return []
    return sorted(path.as_posix() for path in folder.iterdir() if path.is_file())


def resolve_gaps(project_id: str, source: Path, change_id: str | None = None) -> dict[str, object]:
    from .changes import without_border_block

    base = workspace_path(project_id)
    if not base.exists():
        raise GateRefusal(f"Workspace not found: {project_id}")
    if change_id:
        # IMP-382: a change keeps its own gaps; an unknown change is refused before anything is written.
        from .changes import change_gaps_path, get_change

        get_change(project_id, change_id)
        gaps_path = change_gaps_path(base, change_id)
        if not gaps_path.exists():
            raise GateRefusal(f"{change_id} has no gaps file yet.", next_step=f"Run /gaps {project_id} --change {change_id}.")
    else:
        gaps_path = base / "01_discovery" / "gaps.md"
        if not gaps_path.exists():
            raise GateRefusal("Cannot resolve gaps before /ingest creates 01_discovery/gaps.md.")

    # IMP-322: utf-8-sig, so a file saved with a BOM keeps its first `### GAP-` answer.
    # IMP-323: read before anything is written, so an unreadable file leaves no copy behind.
    try:
        text = source.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        raise InputError(f"{source.name} is not UTF-8 text.", next_step="Save it as UTF-8 and run /resolve-gaps again.") from None
    baseline_errors: dict[str, str | None] = {}
    scope_border: list[dict[str, str]] | None = None
    if change_id:
        # IMP-382: validate the border before the first write; an invalid one rejects the whole file.
        # IMP-384: every by_baseline citation is checked first (a finding, never an exception), so the dry run
        # sees a GAP-SCOPE closed by by_baseline as closed and validates its border too.
        baseline_errors = _check_baseline_citations(base, project_id, change_id, text)
        from .changes import change_language

        scope_border = _validate_change_border(
            gaps_path, text, baseline_errors, change_language(project_id, get_change(project_id, change_id), text)
        )
    source_id = open_source_row(project_id, source, "gap_resolved")  # IMP-250a
    target_dir = base / "07_changes" / "00_client_responses"
    target_dir.mkdir(parents=True, exist_ok=True)
    target = unique_path(target_dir / f"{source.stem}.md")
    # IMP-336: the same redaction as /ingest and /sync before the answers are stored or parsed.
    sanitized = sanitize_text(base, source.name, text)
    if sanitized.redactions:
        text = sanitized.text
        write_text(target, text)
    else:
        copy_file(source, target)
    responses = parse_gap_responses(text)
    _flag_baseline(responses, baseline_errors)
    delta_findings: list[dict[str, str]] = []
    affects_findings: list[dict[str, object]] = []
    surface_findings: list[dict[str, object]] = []
    change_lang = ""
    if change_id:
        from .changes import change_language

        change_lang = change_language(project_id, get_change(project_id, change_id), text)
        delta_findings = _flag_delta(responses, change_lang)
        affects_findings = _flag_affects(project_id, change_id, responses, change_lang)
        surface_findings = _flag_surface(project_id, change_id, responses, change_lang, scope_border)
    existing = parse_gap_rows(gaps_path.read_text(encoding="utf-8"))
    known_ids = {gap["id"] for gap in existing}
    unknown_gap_ids = sorted(gap_id for gap_id in responses if gap_id not in known_ids)
    req_id = change_id or (existing[0].get("parent", "REQ-001").strip("`") if existing else "REQ-001")

    record_id = add_node(project_id, "CHG", "change", target, source.stem, status="pending", domain="product")
    # IMP-250b / IMP-251: an example, an own artifact (echo) or a source that declares
    # itself not validated never closes a rule; its confirmed answers stay ANSWERED.
    # IMP-382: the border's surface names ("Guardar borrador") are not a claim that the source is a draft.
    note_text = without_border_block(text) if change_id else text
    block_note = closing_block_note(source_row(project_id, source_id), note_text)
    resolution_results = apply_gap_responses(existing, responses, can_close=block_note is None, block_note=block_note,
                                              language=change_lang or project_language(project_id))
    trigger = _unvalidated_trigger_in_file(text, note_text, block_note, change_lang or project_language(project_id))
    if trigger:
        resolution_results["findings"].insert(0, str(trigger.pop("finding")))
    # IMP-322: an answer under an id that is not in gaps.md used to vanish without a word.
    resolution_results["findings"].extend(
        f"{gap_id}: not in gaps.md, so its answer was not applied; check the id." for gap_id in unknown_gap_ids
    )
    resolution_results["findings"].extend(repeated_section_findings(responses))
    annotate_resolution_source_types(resolution_results, source)
    language = project_language(project_id)
    if change_id:
        language = change_lang
        write_text(gaps_path, render_gaps(project_id, resolution_results["gaps"], req_id, language, gaps_path.with_name("gap_elicitation.json")))
    else:
        write_text(gaps_path, render_gaps(project_id, resolution_results["gaps"], req_id, language))

    report_path = unique_path(target_dir / f"{source.stem}_gap_resolution_report.md")
    write_text(report_path, render_resolution_report(project_id, record_id, resolution_results))
    report_id = add_node(project_id, "DEC", "gap_resolution_report", report_path, "Gap resolution report", status="active")
    add_edge(project_id, record_id, report_id, "produces")

    if change_id:
        # IMP-382: seeds, decisions, EARS and the knowledge metabolism come in a later increment;
        # the project's gap report node is not the change's.
        return _finish_change_resolution(
            project_id, source, change_id, record_id, source_id, target, text, report_path, report_id,
            resolution_results, unknown_gap_ids, responses, delta_findings, language, affects_findings,
            surface_findings, trigger,
        )

    gap_report_ids = [node["id"] for node in load_graph(project_id).get("nodes", []) if node.get("type") == "gap_report"]
    for gap_report_id in gap_report_ids:
        add_edge(project_id, record_id, gap_report_id, "resolves")

    seed_ids = materialize_resolution_seeds(project_id, resolution_results["closed"], record_id)
    decision_ids = materialize_resolution_decisions(project_id, resolution_results["closed"], record_id)
    for node_id in seed_ids + decision_ids:
        add_edge(project_id, record_id, node_id, "confirms")

    # IMP-026: confirmed answers already written in EARS syntax are normalized
    # into requirements.md as testable statements. Prose answers stay as prose.
    ears_ids = materialize_ears_requirements(project_id, resolution_results["closed"], record_id)
    for node_id in ears_ids:
        add_edge(project_id, record_id, node_id, "normalizes")

    update_gap_report_node_status(project_id, resolution_results["counts"])

    broker = ContextBroker(project_id)
    # IMP-369: a file whose answers moved no gap (every id unknown, or every answer left
    # its gap where it was) changes nothing downstream; it must not mark the brief,
    # specs and backlog stale.
    before_status = {gap["id"]: str(gap.get("status", "")).upper() for gap in existing}
    moved = any(before_status.get(gap["id"]) != str(gap.get("status", "")).upper() for gap in resolution_results["gaps"])
    metabolism = metabolize_knowledge(
        project_id,
        record_id,
        source_text=text,
        validated_gap_ids={item["id"] for item in resolution_results["closed"]},
        broker=broker,
        record_staleness=moved,
    )
    write_text(report_path, render_resolution_report(project_id, record_id, resolution_results, metabolism))
    broker.index_artifact(record_id, "change", target, text, trace_ids=[record_id], client_source=True)
    broker.index_artifact(report_id, "gap_resolution_report", report_path, report_path.read_text(encoding="utf-8"), trace_ids=[record_id, report_id])
    reindex_workspace(project_id)
    mark_source_processed(project_id, source, "gap_resolved", record_id, source_id=source_id)
    rerun_of = settle_answer_rerun(project_id, source_id)
    mark_source_processed(project_id, target, "gap_response_copy", record_id, source_id=source_id)
    mark_source_processed(project_id, report_path, "gap_resolution_report", report_id)

    update_state(
        project_id,
        phase="gaps_resolved",
        health="DIRTY" if resolution_results["counts"].get("blocking_open", 0) else "CLEAN",
        last_gap_resolution_id=report_id,
        last_change_id=record_id,
        gap_counts=resolution_results["counts"],
        readiness_stage=readiness_stage_after_gap_change(project_id, resolution_results["counts"]),
    )
    append_gap_resolution_log(project_id, record_id, report_id, resolution_results)
    # IMP-253b: in a v2 project the answers rewrite their places in the brief now
    from .compilers.brief_v2 import rewrite_after_gap_close

    brief_path = base / "02_requirements" / "project-brief.md"
    brief_before = brief_path.read_bytes() if brief_path.exists() else b""
    brief_v2 = rewrite_after_gap_close(project_id, [item["id"] for item in resolution_results["closed"]])
    if brief_v2 and brief_path.exists() and brief_path.read_bytes() != brief_before:
        mark_downstream_of_rewritten_brief(project_id, record_id)
    result = {
        "change_id": record_id,
        "gap_resolution_report_id": report_id,
        "path": str(report_path.as_posix()),
        "closed": [item["id"] for item in resolution_results["closed"]],
        "answered": [item["id"] for item in resolution_results["answered"]],
        "partially_closed": [item["id"] for item in resolution_results["partially_closed"]],
        "open": [item["id"] for item in resolution_results["open"]],
        "gap_counts": resolution_results["counts"],
        "knowledge_metabolism": metabolism,
        "closure_findings": resolution_results["findings"],
        "unknown_gap_ids": unknown_gap_ids,
        "options": closed_options(resolution_results),
        "owners": gap_owners(resolution_results),
        "unvalidated_trigger": trigger,
        "rerun_of": rerun_of,
    }
    if brief_v2:
        result["brief_v2"] = brief_v2
    return result


def _gap_block(text: str, gap_id: str) -> str:
    pattern = re.compile(r"^###\s+(GAP-[A-Z0-9-]+).*?(?=^###\s+GAP-[A-Z0-9-]+|\Z)", re.M | re.S)
    return "\n".join(match.group(0) for match in pattern.finditer(text) if match.group(1) == gap_id)


def _flag_baseline(responses: dict[str, dict[str, str]], baseline_errors: dict[str, str | None]) -> None:
    for gap_id, error in baseline_errors.items():
        if gap_id in responses:
            responses[gap_id]["baseline_checked"] = True
            if error:
                responses[gap_id]["baseline_error"] = error


def _flag_delta(responses: dict[str, dict[str, str]], language: str) -> list[dict[str, str]]:
    """IMP-388: a confirmed EARS answer of a change needs a BA-declared Delta; without one it is not confirmed."""
    from .change_requirements import parse_delta, propose_delta

    findings: list[dict[str, str]] = []
    for gap_id, response in responses.items():
        if gap_id == "GAP-SCOPE":
            continue  # the border is exempt from Delta and from EARS rows
        answer = str(response.get("answer", "")).strip()
        if normalize_status(response.get("decision_status", "")) not in CONFIRMED_STATUSES or not is_substantive_answer(answer):
            continue
        statements = ears_statements(answer)
        if not statements or parse_delta(str(response.get("delta", ""))):
            continue
        proposed = propose_delta(statements[0][0])
        note = (f"falta un Delta válido (ADDED | MODIFIED | REMOVED | UNCHANGED); propuesta: {proposed}" if language == "es"
                else f"a valid Delta is missing (ADDED | MODIFIED | REMOVED | UNCHANGED); proposal: {proposed}")
        response["delta_error"] = note
        findings.append({"gap": gap_id, "proposed": proposed, "note": note})
    return findings


def _flag_affects(project_id: str, change_id: str, responses: dict[str, dict[str, str]], language: str) -> list[dict[str, object]]:
    """IMP-393: a confirmed MODIFIED/REMOVED EARS answer of a change names the stories it affects.

    Without stories in 04_backlog (a project not yet backlogged) the field is optional. With stories, a missing or
    unknown id keeps the answer unconfirmed; on ADDED/UNCHANGED the field is ignored with a note.
    """
    from .change_requirements import _AFFECTING_DELTAS, parse_affects, parse_delta, story_candidates, story_files

    from .core.markdown import parse_frontmatter

    known = {
        sid for sid, path in story_files(workspace_path(project_id)).items()
        if str(parse_frontmatter(path.read_text(encoding="utf-8")).get("change", "")).strip() != change_id
    }
    findings: list[dict[str, object]] = []
    for gap_id, response in responses.items():
        if gap_id == "GAP-SCOPE" or response.get("delta_error"):
            continue
        answer = str(response.get("answer", "")).strip()
        if normalize_status(response.get("decision_status", "")) not in CONFIRMED_STATUSES or not is_substantive_answer(answer):
            continue
        if not ears_statements(answer):
            continue
        delta = parse_delta(str(response.get("delta", "")))
        raw = str(response.get("affects", "")).strip()
        if delta not in _AFFECTING_DELTAS:
            if raw:
                note = (f"Afecta se ignora: el Delta es {delta}" if language == "es" else f"Affects is ignored: the Delta is {delta}")
                findings.append({"gap": gap_id, "candidates": [], "note": note})
            continue
        if not known:
            continue
        ids = parse_affects(raw)
        unknown = [item for item in (ids or []) if item not in known]
        if ids is not None and not unknown:
            continue
        candidates = story_candidates(project_id, change_id, str(response.get("evidence", "")))
        listed = ", ".join(candidates) or ("ninguna" if language == "es" else "none")
        if unknown:
            note = (f"Afecta nombra historias que no existen en 04_backlog: {', '.join(unknown)}; candidatas: {listed}" if language == "es"
                    else f"Affects names stories missing from 04_backlog: {', '.join(unknown)}; candidates: {listed}")
        else:
            note = (f"falta Afecta (historias US-nnn o `ninguna`) para un Delta {delta}; candidatas: {listed}" if language == "es"
                    else f"Affects is missing (US-nnn stories or `none`) for a {delta} Delta; candidates: {listed}")
        response["delta_error"] = note
        findings.append({"gap": gap_id, "candidates": candidates, "note": note})
    return findings


def _flag_surface(
    project_id: str,
    change_id: str,
    responses: dict[str, dict[str, str]],
    language: str,
    scope_border: list[dict[str, str]] | None = None,
) -> list[dict[str, object]]:
    """IMP-396: a confirmed EARS answer of a change (any Delta) names at least one valid surface of the confirmed border.

    The border is the one GAP-SCOPE closes with in this same file (`scope_border`), else the confirmed one.
    Without either (the scope round, GAP-SCOPE not closing) the check does not apply; GAP-SCOPE is exempt.
    """
    from .change_requirements import parse_surfaces, propose_surfaces
    from .changes import get_change

    change = get_change(project_id, change_id)
    if scope_border:
        border = scope_border
    else:
        border = change.get("border", []) or []
        if not change.get("border_confirmed_at") or not border:
            return []
    names = [str(item.get("name", "")) for item in border if item.get("name")]
    findings: list[dict[str, object]] = []
    for gap_id, response in responses.items():
        if gap_id == "GAP-SCOPE" or response.get("delta_error"):
            continue
        answer = str(response.get("answer", "")).strip()
        if normalize_status(response.get("decision_status", "")) not in CONFIRMED_STATUSES or not is_substantive_answer(answer):
            continue
        statements = ears_statements(answer)
        if not statements:
            continue
        valid, unknown = parse_surfaces(str(response.get("surface", "")), border)
        if valid and not unknown:
            continue
        proposed = propose_surfaces(" ".join(s for s, _ in statements), border)
        listed = "; ".join(names)
        if unknown:
            note = (f"Superficie nombra superficies que no están en el borde: {'; '.join(unknown)}; el borde: {listed}" if language == "es"
                    else f"Surface names surfaces missing from the border: {'; '.join(unknown)}; the border: {listed}")
        else:
            note = (f"falta Superficie (una o más del borde, separadas por `;`); propuesta: {'; '.join(proposed) or 'ninguna'}; el borde: {listed}"
                    if language == "es" else
                    f"Surface is missing (one or more of the border, separated by `;`); proposal: {'; '.join(proposed) or 'none'}; the border: {listed}")
        response["delta_error"] = note
        findings.append({"gap": gap_id, "proposed": proposed, "border": names, "note": note})
    return findings


def _validate_change_border(
    gaps_path: Path, text: str, baseline_errors: dict[str, str | None] | None = None, language: str = "es"
) -> list[dict[str, str]] | None:
    """IMP-382: a GAP-SCOPE answer that closes needs a valid border; checked before any write.

    Returns the border parsed from this file when GAP-SCOPE closes (IMP-396: the surface check of the same file uses it).
    """
    from .changes import parse_border

    existing = parse_gap_rows(gaps_path.read_text(encoding="utf-8"))
    dry_responses = parse_gap_responses(text)
    _flag_baseline(dry_responses, baseline_errors or {})
    dry = apply_gap_responses(existing, dry_responses)  # the same rules, writing nothing
    if any(gap["id"] == "GAP-SCOPE" for gap in dry["closed"]):
        return parse_border(_gap_block(text, "GAP-SCOPE"), "", language)
    return None


def _check_baseline_citations(base: Path, project_id: str, change_id: str, text: str) -> dict[str, str | None]:
    """IMP-384: gap id -> the finding of its by_baseline citation, or None when the citation holds."""
    from .changes import validate_baseline_citation

    errors: dict[str, str | None] = {}
    for gap_id, response in parse_gap_responses(text).items():
        if str(response.get("closure", "")).strip().strip("`").lower().replace(" ", "_") == "by_baseline":
            errors[gap_id] = validate_baseline_citation(base, project_id, change_id, str(response.get("evidence", "")))
    return errors


def _finish_change_resolution(
    project_id: str,
    source: Path,
    change_id: str,
    record_id: str,
    source_id: str,
    target: Path,
    text: str,
    report_path: Path,
    report_id: str,
    resolution_results: dict[str, object],
    unknown_gap_ids: list[str],
    responses: dict[str, dict[str, str]] | None = None,
    delta_findings: list[dict[str, str]] | None = None,
    language: str = "es",
    affects_findings: list[dict[str, object]] | None = None,
    surface_findings: list[dict[str, object]] | None = None,
    trigger: dict[str, object] | None = None,
) -> dict[str, object]:
    """IMP-382: the change side of /resolve-gaps: its responses, its border, its lens round."""
    from .changes import confirm_border, get_change, parse_border, regenerate_change_gaps
    from .readiness_verdict import change_next_step  # IMP-408

    base = workspace_path(project_id)
    saved = target.relative_to(base).as_posix()
    changes = {key: dict(value) for key, value in read_state(project_id).get("changes", {}).items()}
    changes[change_id]["responses"] = [*changes[change_id].get("responses", []), saved]
    update_state(project_id, changes=changes)
    scope_closed = any(gap["id"] == "GAP-SCOPE" for gap in resolution_results["closed"])
    if scope_closed:
        confirm_border(project_id, change_id, parse_border(_gap_block(text, "GAP-SCOPE"), f"{saved}#GAP-SCOPE"))
        regenerate_change_gaps(project_id, change_id)
    else:
        changes = {key: dict(value) for key, value in read_state(project_id).get("changes", {}).items()}
        changes[change_id]["gap_counts"] = resolution_results["counts"]
        update_state(project_id, changes=changes)
    # IMP-388: confirmed EARS answers with a declared Delta become the change's REQ-EARS rows.
    from .change_requirements import reconcile_change_ears

    reconciled = reconcile_change_ears(project_id, change_id, resolution_results["closed"], responses or {}, language, record_id)
    change = get_change(project_id, change_id)

    broker = ContextBroker(project_id)
    write_text(report_path, render_resolution_report(project_id, record_id, resolution_results))
    broker.index_artifact(record_id, "change", target, text, trace_ids=[record_id], client_source=True)
    broker.index_artifact(report_id, "gap_resolution_report", report_path, report_path.read_text(encoding="utf-8"), trace_ids=[record_id, report_id])
    reindex_workspace(project_id)
    mark_source_processed(project_id, source, "gap_resolved", record_id, source_id=source_id)
    rerun_of = settle_answer_rerun(project_id, source_id)
    mark_source_processed(project_id, target, "gap_response_copy", record_id, source_id=source_id)
    mark_source_processed(project_id, report_path, "gap_resolution_report", report_id)
    return {
        "change_id": change_id,
        "resolution_id": record_id,
        "round": change.get("round"),
        "border": change.get("border", []),
        "gap_resolution_report_id": report_id,
        "path": str(report_path.as_posix()),
        "closed": [item["id"] for item in resolution_results["closed"]],
        "answered": [item["id"] for item in resolution_results["answered"]],
        "partially_closed": [item["id"] for item in resolution_results["partially_closed"]],
        "open": [item["id"] for item in resolution_results["open"]],
        "gap_counts": change.get("gap_counts"),
        "closure_findings": resolution_results["findings"],
        "unknown_gap_ids": unknown_gap_ids,
        "options": closed_options(resolution_results),
        "owners": gap_owners(resolution_results),
        "unvalidated_trigger": trigger,
        "rerun_of": rerun_of,
        "delta_findings": delta_findings or [],
        "affects_findings": affects_findings or [],
        "surface_findings": surface_findings or [],
        "ears_rows": reconciled["added"],
        "delta_updated": reconciled["delta_updated"],
        "superseded_rows": reconciled["superseded"],
        "next_step": change_next_step(project_id, change_id),
    }


def mark_downstream_of_rewritten_brief(project_id: str, change_id: str) -> None:
    """IMP-369: the answers rewrote the brief v2, so what was generated from it is stale.

    The brief itself is fresh (this command just compiled it), so it leaves the
    marker; the PRD, specs and backlog stay until regenerated. Without a marker
    (no knowledge unit moved) /backlog used to run on specs older than the brief
    with only a foundation warning; now it refuses with "Run /specs, then /backlog."
    """
    from .health import pending_stale_artifacts
    from .knowledge.metabolism import downstream_stale_artifacts

    base = workspace_path(project_id)
    brief = (base / "02_requirements" / "project-brief.md").as_posix()
    state = read_json(state_path(project_id), {})
    marker = state.get("knowledge_staleness", {})
    marker = marker if isinstance(marker, dict) else {}
    artifacts = [str(item) for item in marker.get("downstream_artifacts", []) if item]
    if artifacts and marker.get("recorded_at") and pending_stale_artifacts(project_id):
        kept = [item for item in artifacts if Path(item).as_posix() != brief]
        if kept != artifacts:
            update_state(project_id, knowledge_staleness={**marker, "downstream_artifacts": kept})
        return
    downstream = [item for item in downstream_stale_artifacts(base) if Path(item).as_posix() != brief]
    if downstream:
        update_state(project_id, knowledge_staleness={
            "change_id": change_id,
            "impacted_knowledge_units": [],
            "downstream_artifacts": downstream,
            "recorded_at": utc_now(),
        })


def repeated_section_findings(responses: dict[str, dict[str, str]]) -> list[str]:
    """IMP-370: say when one gap was answered in several `### GAP-X` sections."""
    findings: list[str] = []
    for gap_id, response in responses.items():
        sections = response.get("sections")
        if not sections:
            continue
        if response.get("conflicting_status"):
            findings.append(
                f"{gap_id}: answered in {sections} sections with different decision statuses "
                f"({response.get('decision_status', '')}); the answers were merged and the gap does not close. "
                "Give one decision status for the whole answer."
            )
        else:
            findings.append(f"{gap_id}: answered in {sections} sections; the answers were merged into one.")
    return findings


_TBD_IN_ANSWER = re.compile(r"(?<![\w-])(TBD|TBC|a definir|por definir|to be defined)(?![\w-])", re.I)


def normalize_option(raw: str) -> str:
    """IMP-408: `(b)`, `B - text` and `b` all read as the letter `B`."""
    match = re.match(r"^\s*\(?([A-Za-z])\)?(?=\W|$)", raw)
    return match.group(1).upper() if match else raw.strip()


def option_choice(gap_id: str, response: dict[str, str], labels: list[str], language: str) -> tuple[str, str | None]:
    """IMP-408: the option a confirmed answer chose and the note when it cannot close.

    The `Option:` field wins over the markers in the answer; without it, one marker
    is the choice and several are refused. A gap without options ignores the field.
    """
    es = language == "es"
    raw = str(response.get("option", "")).strip()
    listed = ", ".join(labels)
    if not labels:
        if raw:
            return "", "Opción se ignora: la pregunta no tiene opciones" if es else "Option is ignored: the question has no options"
        return "", None
    if raw:
        chosen = normalize_option(raw)
        if chosen in labels:
            return chosen, None
        note = (f"`Opción: {raw}` no es una de las opciones ({listed}); elegí una en `Opción:`" if es
                else f"`Option: {raw}` is not one of the options ({listed}); choose one in `Option:`")
        return "", note
    named = [letter for letter in option_markers(str(response.get("answer", ""))) if letter in labels]
    if len(named) > 1:
        joined = ", ".join(named)
        note = (f"la respuesta confirmada nombra varias opciones ({joined}); elegí una opción en `Opción:` (una de {listed})" if es
                else f"the confirmed answer names several options ({joined}); choose one option in `Option:` (one of {listed})")
        return "", note
    return (named[0] if named else ""), None


def _unvalidated_trigger_in_file(text: str, note_text: str, block_note: str | None, language: str) -> dict[str, object] | None:
    """IMP-408: which line of the file made it count as not validated, with the finding that says how to fix it."""
    if block_note != UNVALIDATED_SOURCE_NOTE:
        return None
    trigger = unvalidated_trigger(note_text)
    if trigger is None:
        return None
    wanted = str(trigger["text"])
    line = next((n for n, raw in enumerate(text.splitlines(), start=1) if raw.lstrip("\ufeff").strip() == wanted), int(trigger["line"]))
    term = str(trigger["term"])
    if language == "es":
        finding = (f"el archivo se declara no validado por la línea {line} («{wanted[:80]}», palabra «{term}»): sus respuestas confirmadas quedan ANSWERED. "
                   "Si ya está validado, cambiá esa línea y volvé a correr /resolve-gaps; si no, que lo ratifique el BA.")
    else:
        finding = (f"the file declares itself not validated by line {line} («{wanted[:80]}», word «{term}»): its confirmed answers stay ANSWERED. "
                   "If it is already validated, change that line and run /resolve-gaps again; if not, the BA must ratify it.")
    return {"line": line, "text": wanted, "term": term, "finding": finding}


def gap_owners(result: dict[str, object]) -> dict[str, dict[str, str]]:
    """IMP-408: who decided and who drafted, for the gaps whose answer says an agent drafted it."""
    owners: dict[str, dict[str, str]] = {}
    for key in ("closed", "answered", "partially_closed"):
        for gap in result[key]:  # type: ignore[union-attr]
            if gap.get("drafted_by"):
                owners[gap["id"]] = {"decided_by": gap.get("decided_by", ""), "drafted_by": gap["drafted_by"]}
    return owners


def misplaced_field(decision_status: str) -> str | None:
    """IMP-408: a field written as a sub-line of `Estado de decisión` (the status then reads as several lines)."""
    segments = [part.strip() for part in str(decision_status or "").split("; ")]
    if not segments or normalize_status(segments[0]) not in CONFIRMED_STATUSES | PENDING_STATUSES:
        return None
    for segment in segments[1:]:
        for label in MISPLACED_LABELS:
            if re.match(rf"{re.escape(label)}\s*:", segment, re.I):
                return label
    return None


def misplaced_note(label: str, language: str) -> str:
    if label in ("Borde", "Border"):
        return ("el bloque Borde va debajo de Respuesta, no de Estado de decisión: movelo (con sus líneas) debajo de `- Respuesta:` y volvé a correr /resolve-gaps"
                if language == "es" else
                "the Border block goes under Answer, not under Decision status: move it (with its lines) under `- Answer:` and run /resolve-gaps again")
    return (f"el campo {label} va al mismo nivel que los demás campos, no debajo de Estado de decisión" if language == "es"
            else f"the {label} field goes at the same level as the other fields, not under Decision status")


def closed_options(result: dict[str, object]) -> dict[str, str]:
    return {gap["id"]: gap["option"] for gap in result["closed"] if gap.get("option")}  # type: ignore[index,union-attr]


_EXAMPLE_EVIDENCE = re.compile(r"\b(example|ejemplo|sample data|datos de ejemplo|current practice|pr[aá]ctica actual)\b", re.I)


def closure_for(gap_id: str, response: dict[str, str], decision: str) -> tuple[str, list[str]]:
    """IMP-257: the closure reason of a confirmed answer and the findings about its citation."""

    raw = str(response.get("closure", "")).strip().strip("`").lower().replace(" ", "_")
    findings: list[str] = []
    if raw in CHANGE_CLOSURE_REASONS:
        # IMP-384: the change path checked the citation before this runs; apply_gap_responses gates it
        return raw, findings
    if raw and raw not in CLOSURE_REASONS and raw != REOPEN_FALSE_PREMISE:
        findings.append(f"{gap_id}: unknown closure reason {raw!r}; use one of {', '.join(CLOSURE_REASONS)}.")
        raw = ""
    reason = raw or ("by_removal" if decision in NOT_APPLICABLE_STATUSES else "answered")
    evidence = str(response.get("evidence", "")).strip()
    if reason != REOPEN_FALSE_PREMISE and not evidence:
        findings.append(f"{gap_id}: closed without a citation; fill 'Evidence or reference'.")
    needed = CLOSURE_CITES.get(reason)
    if needed and needed not in evidence.upper():
        findings.append(f"{gap_id}: closure '{reason}' must cite a {needed}* id.")
    return reason, findings


def apply_gap_responses(
    gaps: list[dict[str, str]],
    responses: dict[str, dict[str, str]],
    can_close: bool = True,
    block_note: str | None = None,
    language: str = "en",
) -> dict[str, object]:
    findings: list[str] = []
    closed: list[dict[str, str]] = []
    answered: list[dict[str, str]] = []
    partially_closed: list[dict[str, str]] = []
    open_gaps: list[dict[str, str]] = []
    updated: list[dict[str, str]] = []
    for gap in gaps:
        gap = dict(gap)
        response = responses.get(gap["id"], {})
        answer = response.get("answer", "").strip()
        decision = normalize_status(response.get("decision_status", ""))
        gap["answer"] = answer
        gap["owner"] = response.get("owner", "")
        gap["evidence"] = response.get("evidence", "")
        gap["decision_status"] = response.get("decision_status", "")
        drafted_by = str(response.get("drafted_by", "")).strip()
        unnamed = UNNAMED_BA[language if language in UNNAMED_BA else "en"]
        if drafted_by:
            # IMP-408: an agent may draft; only a named person decides
            owner_name = gap["owner"].strip()
            named = bool(owner_name) and not _mentions_any(owner_name.lower(), AGENT_OWNER_TOKENS)
            gap["drafted_by"] = drafted_by
            gap["decided_by"] = owner_name if named else unnamed
        substantive = is_substantive_answer(answer)
        confirmed = bool(answer) and decision in CONFIRMED_STATUSES and substantive
        reason, closure_findings = closure_for(gap["id"], response, decision) if confirmed or response.get("closure") else ("", [])
        if str(response.get("closure", "")).strip().lower().replace(" ", "_") == "reopened_false_premise":
            # IMP-257: the premise of an earlier closure was false; the gap reopens and keeps that closure on record
            previous = f"{gap.get('closure_reason') or 'closed'}: {gap.get('resolution_note') or ''}".strip(": ")
            gap["status"] = "OPEN"
            gap["closure_reason"] = "reopened_false_premise"
            gap["resolution_note"] = f"reopened (false premise); previous closure kept: {previous}"
            open_gaps.append(gap)
            updated.append(gap)
            continue
        if confirmed:
            choice, option_note = option_choice(gap["id"], response, gap_option_labels(gap), language)
            if option_note and gap_option_labels(gap):
                # IMP-408: a confirmed answer that names several options, or an unknown one, is not confirmed yet
                findings.append(f"{gap['id']}: {option_note}")
                gap["status"] = "ANSWERED"
                gap["resolution_note"] = option_note
                answered.append(gap)
                updated.append(gap)
                continue
            if option_note:
                findings.append(f"{gap['id']}: {option_note}")
            gap["option"] = choice
        if confirmed and _EXAMPLE_EVIDENCE.search(gap["evidence"]):
            # example data or the current practice never closes a gap
            gap["status"] = "ANSWERED"
            gap["resolution_note"] = EXAMPLE_SOURCE_NOTE
            answered.append(gap)
            updated.append(gap)
            continue
        if confirmed and _TBD_IN_ANSWER.search(answer):
            gap["status"] = "PARTIALLY_CLOSED"
            gap["resolution_note"] = "confirmed-tbd: the confirmed answer still says TBD; ask for the value"
            partially_closed.append(gap)
            updated.append(gap)
            continue
        if confirmed and reason == "resolved_by_inference":
            # an inference never makes a gap ready: it stays visible until someone ratifies it
            findings.extend(closure_findings)
            gap["status"] = "PARTIALLY_CLOSED"
            gap["closure_reason"] = reason
            gap["resolution_note"] = f"resolved-by-inference: {gap['evidence']}; ratify to close"
            partially_closed.append(gap)
            updated.append(gap)
            continue
        if confirmed and response.get("delta_error"):
            # IMP-388: an EARS answer of a change without a declared Delta is not confirmed yet
            note = str(response["delta_error"])
            findings.append(f"{gap['id']}: {note}")
            gap["status"] = "ANSWERED"
            gap["resolution_note"] = note
            answered.append(gap)
            updated.append(gap)
            continue
        if confirmed and reason == "by_baseline":
            # IMP-384: nothing closes by itself; a confirmed answer AND a validated citation, on a change only
            if not response.get("baseline_checked"):
                note = ("by_baseline sólo vale en un cambio (--change)" if language == "es"
                        else "by_baseline only applies within a change (--change)")
            else:
                note = str(response.get("baseline_error") or "")
            if note:
                findings.append(f"{gap['id']}: {note}")
                gap["status"] = "ANSWERED"
                gap["resolution_note"] = note
                answered.append(gap)
                updated.append(gap)
                continue
        if confirmed and can_close:
            findings.extend(closure_findings)
            gap["closure_reason"] = reason
        if answer and decision in CONFIRMED_STATUSES and substantive and not can_close:
            gap["status"] = "ANSWERED"
            gap["resolution_note"] = block_note or EXAMPLE_SOURCE_NOTE
            answered.append(gap)
        elif answer and decision in CONFIRMED_STATUSES and substantive:
            gap["status"] = "CLOSED"
            if drafted_by and gap["decided_by"] == unnamed:
                findings.append(
                    f"{gap['id']}: lo redactó {drafted_by} y nadie lo firmó como decisión: se cierra como decidido por «{unnamed}»; nombrá al BA en `Owner / fuente:`"
                    if language == "es" else
                    f"{gap['id']}: drafted by {drafted_by} and nobody signed it as a decision: it closes as decided by «{unnamed}»; name the BA in `Owner / source:`")
            if is_ears_eligible_gap(gap["id"]) and not classify_ears(answer):
                gap["resolution_note"] = EARS_ELIGIBLE_NOTE
            closed.append(gap)
        elif answer and decision in CONFIRMED_STATUSES:
            # Confirmed but the answer itself is vague/deferred: do not close silently.
            gap["status"] = "PARTIALLY_CLOSED"
            gap["resolution_note"] = "confirmed-but-vague: answer lacks usable content; ask for specifics"
            partially_closed.append(gap)
        elif answer and decision in PENDING_STATUSES and substantive:
            # Clear answer awaiting confirmation: visible as ANSWERED, still blocking if severe.
            gap["status"] = "ANSWERED"
            gap["resolution_note"] = "awaiting-confirmation: substantive answer, decision still pending"
            answered.append(gap)
        elif answer:
            gap["status"] = "PARTIALLY_CLOSED"
            label = misplaced_field(response.get("decision_status", ""))
            if label:
                gap["resolution_note"] = misplaced_note(label, language)
                findings.append(f"{gap['id']}: {gap['resolution_note']}")
            else:
                gap["resolution_note"] = "ambiguous: answer present but no recognizable decision status"
            partially_closed.append(gap)
        else:
            gap["status"] = gap.get("status", "OPEN")
            open_gaps.append(gap)
        updated.append(gap)
    return {
        "gaps": updated,
        "closed": closed,
        "answered": answered,
        "partially_closed": partially_closed,
        "open": [gap for gap in updated if gap.get("status") == "OPEN"],
        "counts": count_gaps(updated),
        "findings": findings,
    }


def annotate_resolution_source_types(result: dict[str, object], source: Path) -> None:
    for key in ("closed", "answered", "partially_closed"):
        for gap in result.get(key, []):  # type: ignore[union-attr]
            if isinstance(gap, dict):
                gap["resolution_source_type"] = classify_resolution_source(
                    gap.get("owner", ""),
                    gap.get("evidence", ""),
                    source,
                )


def _mentions_any(text: str, tokens: set[str]) -> bool:
    # A token must start a word ("UX Designer" -> design, "QA lead" -> qa), never
    # sit inside one ("Aqua", "Fintech"). Underscores and hyphens separate words.
    return any(re.search(rf"(?<![^\W_]){re.escape(token)}", text) for token in tokens)


def classify_resolution_source(owner: str, evidence: str = "", source: Path | None = None) -> str:
    # Only the answer file's own name counts, never the folder it lives in: a
    # random temp dir such as /tmp/tmpqa3k_x9z must not turn a client into QA.
    text = f"{owner} {evidence} {source.stem if source else ''}".lower()
    if _mentions_any(text, INFERENCE_SOURCE_TOKENS):
        return "inference"
    if _mentions_any(text, DOMAIN_SOURCE_TOKENS):
        return "domain"
    return "client"


def closed_resolution_source_counts(result: dict[str, object]) -> dict[str, int]:
    counts = {"client": 0, "domain": 0, "inference": 0}
    for gap in result.get("closed", []):  # type: ignore[union-attr]
        if not isinstance(gap, dict):
            continue
        source_type = str(gap.get("resolution_source_type", "client"))
        if source_type not in counts:
            source_type = "client"
        counts[source_type] += 1
    return counts


def normalize_status(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def materialize_resolution_seeds(project_id: str, closed: list[dict[str, str]], change_id: str) -> list[str]:
    if not closed:
        return []
    path = workspace_path(project_id) / "01_discovery" / "identity_seeds.md"
    if not path.exists():
        write_text(path, "# Identity Seeds\n\n")
    rows = [
        "\n## Gap Resolution Seeds\n\n",
        "| Seed ID | Gap ID | Status | Statement | Source | Brief Section | PRD Section |\n",
        "| --- | --- | --- | --- | --- | --- | --- |\n",
    ]
    for index, gap in enumerate(closed, start=1):
        brief_section = brief_section_for_gap(gap["id"]) or "-"
        prd_section = prd_section_for_gap(gap["id"]) or "-"
        rows.append(
            f"| AUTO-SEED-{change_id}-{index:03d} | `{gap['id']}` | CONFIRMED | {gap['answer']} | `{change_id}` | {brief_section} | {prd_section} |\n"
        )
    append_text(path, "".join(rows))
    seed_ids = []
    for gap in closed:
        seed_id = add_node(project_id, "SEED", "identity_seed", path, f"Confirmed answer for {gap['id']}", status="confirmed", domain=gap.get("lens", "product"))
        seed_ids.append(seed_id)
    return seed_ids


def materialize_resolution_decisions(project_id: str, closed: list[dict[str, str]], change_id: str) -> list[str]:
    decisions = [gap for gap in closed if normalize_status(gap.get("decision_status", "")) in CONFIRMED_STATUSES]
    if not decisions:
        return []
    path = workspace_path(project_id) / "01_discovery" / "decisions.md"
    if not path.exists():
        write_text(path, "# Decision Log\n\n")
    rows = [
        "\n## Gap Resolution Decisions\n\n",
        "| Decision ID | Gap ID | Status | Decision | Source | Kind |\n",
        "| --- | --- | --- | --- | --- | --- |\n",
    ]
    for index, gap in enumerate(decisions, start=1):
        kind = NON_GOAL_KIND if normalize_status(gap.get("decision_status", "")) in NOT_APPLICABLE_STATUSES else DECISION_KIND
        rows.append(f"| AUTO-DEC-{change_id}-{index:03d} | `{gap['id']}` | CONFIRMED | {gap['answer']} | `{change_id}` | {kind} |\n")
    append_text(path, "".join(rows))
    decision_ids = []
    for gap in decisions:
        decision_id = add_node(project_id, "DEC", "decision", path, f"Confirmed decision for {gap['id']}", status="confirmed", domain=gap.get("lens", "product"))
        decision_ids.append(decision_id)
    return decision_ids


def _count_existing_ears(text: str) -> int:
    return len(re.findall(r"REQ-EARS-\d+", text))


_EARS_SENTENCE_BREAK = re.compile(
    r"(?<=[.;!?])\s+(?=(?:when|while|if|where|the|cuando|mientras|si|donde|el|la|los|las)\b)", re.I
)


def ears_statements(answer: str) -> list[tuple[str, str]]:
    """IMP-370: the EARS statements in one answer, each with its pattern.

    An answer may hold several "When ..., the system shall ..." sentences (or one
    per indented bullet, joined with "; "). When two or more sentences are EARS each
    becomes its own statement, and a non-EARS sentence stays attached to the EARS
    sentence before it (or the first one) so nothing written is dropped. With fewer
    than two, the whole answer is one statement, as before.
    """
    answer = answer.strip()
    pieces = [piece.strip() for piece in _EARS_SENTENCE_BREAK.split(answer) if piece.strip()]
    patterns = [classify_ears(piece.rstrip(";").strip()) for piece in pieces]
    if sum(1 for pattern in patterns if pattern) < 2:
        whole = classify_ears(answer)
        return [(answer, whole)] if whole else []
    statements: list[list[str]] = []
    leading: list[str] = []
    for piece, pattern in zip(pieces, patterns):
        text = piece.rstrip(";").strip()
        if pattern:
            statements.append([text, pattern])
        elif statements:
            statements[-1][0] = f"{statements[-1][0]} {text}"
        else:
            leading.append(text)
    if leading:
        statements[0][0] = f"{statements[0][0]} {' '.join(leading)}"
    return [(text, pattern) for text, pattern in statements]


def materialize_ears_requirements(project_id: str, closed: list[dict[str, str]], change_id: str) -> list[str]:
    """Normalize confirmed EARS-shaped answers into requirements.md (IMP-026).

    Only answers already written in valid EARS syntax are accumulated; prose
    answers stay as seeds/decisions. The agent proposes; the runtime validates
    structure (never invents). Returns the traceability node ids created.
    """
    candidates: list[tuple[dict[str, str], str, str]] = []
    for gap in closed:
        answer = (gap.get("answer") or "").strip()
        candidates.extend((gap, statement, pattern) for statement, pattern in ears_statements(answer))
    if not candidates:
        return []
    path = workspace_path(project_id) / "02_requirements" / "requirements.md"
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8")
    start_index = _count_existing_ears(text)
    if any(path.parent.glob("CHG-*/requirements.md")):
        # IMP-388: a change already took ids; never reuse one.
        start_index = next_ears_index(path.parent.parent) - 1
    lines: list[str] = []
    if "## Normalized Requirements (EARS)" not in text:
        lines.append("\n## Normalized Requirements (EARS)\n")
        lines.append(
            "Testable statements normalized from confirmed functional answers (IMP-026). "
            "Specs and backlog cite these by `REQ-EARS-*`; prose answers stay as seeds/decisions/gaps.\n"
        )
        lines.append("| ID | Pattern | Statement | Source |")
        lines.append("| --- | --- | --- | --- |")
    node_ids: list[str] = []
    for offset, (gap, answer, pattern) in enumerate(candidates, start=1):
        req_id = f"REQ-EARS-{start_index + offset:03d}"
        lines.append(f"| {req_id} | {pattern} | {answer} | `{gap['id']}` / `{change_id}` |")
        node_ids.append(
            add_node(
                project_id, "REQ", "ears_requirement", path,
                f"{req_id} ({pattern}) from {gap['id']}",
                status="confirmed", domain=gap.get("lens", "product"),
            )
        )
    append_text(path, "\n".join(lines) + "\n")
    return node_ids


def update_gap_report_node_status(project_id: str, counts: dict[str, int]) -> None:
    graph = load_graph(project_id)
    status = "closed" if not counts.get("open", 0) and not counts.get("partially_closed", 0) else "open"
    for node in graph.get("nodes", []):
        if node.get("type") == "gap_report":
            node["status"] = status
    save_graph(project_id, graph)


def render_resolution_report(
    project_id: str,
    change_id: str,
    result: dict[str, object],
    knowledge_metabolism: dict[str, object] | None = None,
) -> str:
    closed = result["closed"]
    answered = result.get("answered", [])
    partial = result["partially_closed"]
    open_gaps = result["open"]
    knowledge_metabolism = knowledge_metabolism or {}
    unit_rows = "\n".join(
        f"- `{unit_id}`" for unit_id in knowledge_metabolism.get("impacted_knowledge_units", [])
    ) or "- None."
    validated_rows = "\n".join(
        f"- `{item}`" for item in knowledge_metabolism.get("validated_assumptions", [])
    ) or "- None."
    stale_rows = "\n".join(
        f"- `{item}`" for item in knowledge_metabolism.get("downstream_stale_artifacts", [])
    ) or "- None."
    # IMP-322: the findings (a closure without a citation, an unknown gap id) were only
    # in the command's JSON; the stored report is what the BA reads later.
    findings_rows = "\n".join(f"- {item}" for item in result.get("findings", [])) or "- None."
    return f"""# Gap Resolution Report - {project_id}

- Change: `{change_id}`
- Generated at: {utc_now()}

## Closed Gaps

{render_resolution_rows(closed)}

## Answered (Awaiting Confirmation)

{render_resolution_rows(answered)}

## Partially Closed Gaps

{render_resolution_rows(partial)}

## Still Open

{render_resolution_rows(open_gaps)}

## Findings

{findings_rows}

## Knowledge Ledger Metabolism

- Knowledge state: `{knowledge_metabolism.get("knowledge_state", "N/A")}`
- Development readiness: `{knowledge_metabolism.get("development_readiness", "N/A")}`

Impacted knowledge units:

{unit_rows}

Validated assumptions:

{validated_rows}

Downstream stale artifacts:

{stale_rows}
"""


def render_resolution_rows(gaps: object) -> str:
    if not gaps:
        return "- None."
    return "\n".join(
        f"- `{gap['id']}`: {gap.get('answer') or gap.get('description', '')}"
        + (f" _[{gap['resolution_note']}]_" if gap.get("resolution_note") else "")
        + (f" _(source: {gap['resolution_source_type']})_" if gap.get("resolution_source_type") else "")
        + (f" _(option {gap['option']})_" if gap.get("option") else "")
        + (f" _(decided by: {gap.get('decided_by', '')}; drafted by: {gap['drafted_by']})_" if gap.get("drafted_by") else "")
        for gap in gaps
    )  # type: ignore[index]


def append_gap_resolution_log(project_id: str, change_id: str, report_id: str, result: dict[str, object]) -> Path:
    path = workspace_path(project_id) / "01_discovery" / "gap_resolution_log.md"
    if not path.exists():
        write_text(path, f"""# Gap Resolution Log - {project_id}

| Timestamp | Change ID | Report ID | Closed | Partial | Open | Client Closed | Domain Closed | Inference Closed |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
""")
    source_counts = closed_resolution_source_counts(result)
    append_text(
        path,
        f"| {utc_now()} | `{change_id}` | `{report_id}` | {len(result['closed'])} | {len(result['partially_closed'])} | {len(result['open'])} | {source_counts['client']} | {source_counts['domain']} | {source_counts['inference']} |\n",
    )
    return path
