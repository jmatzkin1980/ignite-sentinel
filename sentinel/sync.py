from __future__ import annotations

from .errors import GateRefusal  # IMP-302: typed errors

import re
import shutil
from pathlib import Path

from .gaps import count_gaps, parse_gap_rows, readiness_stage_after_gap_change, render_gaps
from .backlog.hooks import mark_stale_stories_for_spec_units, stale_spec_units_from_change
from .discovery import detect_gaps, load_domain_context
from .gap_resolution import (
    annotate_resolution_source_types,
    apply_gap_responses,
    materialize_ears_requirements,
    materialize_resolution_decisions,
    materialize_resolution_seeds,
    parse_gap_responses,
    update_gap_report_node_status,
)
from .knowledge.metabolism import metabolize_knowledge
from .memory import ContextBroker, reindex_workspace
from .injection import shield_source
from .secrets_scan import ingest_source, pii_report_enabled
from .source_formats import read_source, target_suffix
from .source_conflicts import closing_block_note, scan_source_conflicts
from .sources import already_loaded_source, discover_source_novelty, mark_source_processed, open_source_row, record_duplicate_source, source_row
from .core.graph import add_edge, add_node, children_of, count_by_type, load_graph, save_graph
from .core.io import append_text, write_text
from .core.text import project_language, unique_path
from .workspace import load_config, read_json, update_state, utc_now, workspace_path


def sync_change(project_id: str, source: Path, note: str = "", digest: bool = False, reload: bool = False) -> dict[str, object]:
    base = workspace_path(project_id)
    if not base.exists():
        raise GateRefusal(f"Workspace not found: {project_id}")
    if not reload and source.is_file() and (loaded := already_loaded_source(project_id, source)):
        # IMP-435 (A-10): the same content again is the change it already was, not a second CHG that dirties the project again
        # The row it is: same `source_id`/`change_id` keys as a sync that wrote, so callers read one shape.
        return {"project_id": project_id, "already_loaded": loaded, "source_id": loaded["source_id"],
                "change_id": loaded["change_id"], "source": str(source.as_posix()),
                "message": f"{source.name} is already loaded as {loaded['source_id']} ({loaded['change_id']}); nothing was written."}

    target_dir = change_target_dir(base, source)
    target = unique_path(target_dir / f"{source.stem}{target_suffix(source)}")
    # IMP-270: read (and reject an unreadable format) before the F-NN row opens.
    extracted = read_source(source, media_stem=target.stem)
    # IMP-250a: the F-NN row opens before the cross and closes when it finishes.
    source_id = open_source_row(project_id, source, "synced", fallback_kind=routed_source_kind(source))
    # IMP-285: same redaction as /ingest before the change is analyzed or stored.
    text, sanitized = ingest_source(base, source, target, pii_report_enabled(load_config(project_id)), extracted)
    text, injection_ids = shield_source(base, source.name, text)  # IMP-286
    change_id = add_node(project_id, "CHG", "change", target, source.stem, status="pending", domain="product")

    affected = impacted_nodes(project_id)
    blast_radius = summarize_impact(project_id, affected)
    for node_id in affected:
        add_edge(project_id, change_id, node_id, "may_impact")
    suspicious_links = mark_suspicious_trace_links(
        project_id,
        change_id,
        affected,
        semantic_change_analysis(text, note),
    )

    gaps = detect_sync_gaps(base, text)
    gap_merge = materialize_sync_gaps(project_id, gaps, change_id)
    reopened = reopened_closed_gap_ids(base, gaps)
    sync_resolution = apply_structured_gap_responses(
        project_id, text, source, change_id, block_note=closing_block_note(source_row(project_id, source_id), text)
    )
    # IMP-294: an active CTX-NNN the change cites becomes answered.
    from .context_requests import answer_cited_context_requests

    answered_ctx = answer_cited_context_requests(project_id, text, change_id)
    # IMP-251: anchor statements, open contradiction / cited-not-delivered gaps.
    conflicts = scan_source_conflicts(project_id, source_id, text, project_language(project_id))
    conflicts.pop("new_gaps")
    stale_units = stale_spec_units_from_change(source, text)
    stale_result = mark_stale_stories_for_spec_units(
        project_id,
        stale_units,
        f"/sync change {change_id} touched Spec Unit source.",
        change_id,
    )
    broker = ContextBroker(project_id)
    metabolism = metabolize_knowledge(
        project_id,
        change_id,
        source_text=text,
        validated_gap_ids=set(sync_resolution["closed"]),
        broker=broker,
    )
    # IMP-337 (337a): say how much of the note was stored without being interpreted,
    # and hint (never apply) the confirmed items its decision lines talk about.
    prose = prose_review(project_id, text)
    impact_path = unique_path(target_dir / f"{source.stem}_impact_report.md")
    write_text(impact_path, render_impact(
            project_id,
            change_id,
            affected,
            gaps,
            note,
            blast_radius,
            reopened,
            gap_merge["merged"],
            sync_resolution,
            metabolism,
            stale_result,
            suspicious_links,
            prose,
        ))
    impact_id = add_node(project_id, "DEC", "impact_report", impact_path, "Change impact report", status="pending")
    add_edge(project_id, change_id, impact_id, "produces")

    broker.index_artifact(change_id, "change", target, text, trace_ids=[change_id])
    broker.index_artifact(
        impact_id,
        "impact_report",
        impact_path,
        impact_path.read_text(encoding="utf-8"),
        trace_ids=[change_id, impact_id],
    )
    metabolism_path = append_metabolism_log(project_id, change_id, source, affected, gaps, note, reopened, metabolism)
    broker.index_artifact(
        "METABOLISM-LOG",
        "metabolism_log",
        metabolism_path,
        metabolism_path.read_text(encoding="utf-8"),
        trace_ids=[change_id],
    )
    # IMP-191: opt-in analysis layer over the ingested interaction. Proposes and
    # routes (a) gap answers, (b) DEC-* candidates, (c) new gaps, (d) ASM
    # contradiction signals — all cited verbatim. It writes only the digest
    # artifacts; it never mutates governed gaps/decisions/assumptions.
    interaction_digest: dict[str, object] | None = None
    if digest:
        from .interaction_digest import build_interaction_digest

        interaction_digest = build_interaction_digest(
            project_id,
            change_id,
            target.as_posix(),
            text,
            target_dir=target_dir,
            stem=source.stem,
            metabolism=metabolism,
            new_gaps=gap_merge["merged"],
            source_row=source_row(project_id, source_id),
            hints=prose["hints"],
        )
        digest_path = Path(str(interaction_digest["digest_path"]))
        digest_id = add_node(project_id, "DEC", "interaction_digest", digest_path, "Interaction digest", status="pending")
        add_edge(project_id, change_id, digest_id, "produces")
        broker.index_artifact(
            digest_id,
            "interaction_digest",
            digest_path,
            digest_path.read_text(encoding="utf-8"),
            trace_ids=[change_id, digest_id],
        )
    reindex_workspace(project_id)
    # IMP-127: emit a focused, pointer-only context pack for the change instead of
    # expecting the BA to re-read whole artifacts. Read-only and degradation-safe.
    focus_pack = ContextBroker(project_id).build_focus_pack(
        "sync_focus",
        focus_query_for_change(note, text),
        limit=6,
        max_chars=1600,
        global_budget_chars=4000,
    )
    mark_source_processed(project_id, source, "synced", change_id, source_id=source_id, impacted=affected)
    mark_source_processed(project_id, target, "change_copy", change_id, source_id=source_id)
    mark_source_processed(project_id, impact_path, "impact_report", impact_id)
    if interaction_digest:
        # IMP-293: the digest outputs are Sentinel's own; record them so they are
        # never rescanned as client input.
        mark_source_processed(project_id, Path(str(interaction_digest["digest_path"])), "interaction_digest", change_id)
        if interaction_digest.get("proposed_response_path"):
            mark_source_processed(project_id, Path(str(interaction_digest["proposed_response_path"])), "gap_response_proposed", change_id)
    update_state(
        project_id,
        phase="change_synced",
        health=(
            "DIRTY"
            if gap_merge["merged"]
            or stale_result.get("stale_stories")
            or metabolism.get("downstream_stale_artifacts")
            or suspicious_links
            else "CLEAN"
        ),
        last_change_id=change_id,
        # IMP-435 (A-01): what this note changed nothing of, kept for /next until the next /sync
        prose_notice={"change_id": change_id, "notice": prose["notice"]} if prose["notice"] else {},
        **suspicious_links_state(project_id, change_id, suspicious_links),
    )
    return {
        "change_id": change_id,
        "source_id": source_id,
        "source_authority": source_authority_report(project_id, source_id),
        "secret_redactions": sanitized.redactions,
        "injection_signals": injection_ids,
        "source_format": {"kind": extracted.kind, "images": len(extracted.images),
                          "comments": extracted.comments, "warning": extracted.warning},
        "impact_report_id": impact_id,
        "source": str(source.as_posix()),
        "path": str(target.as_posix()),
        "affected": affected,
        "gaps": gaps,
        "merged_gaps": gap_merge["merged"],
        "skipped_existing_gaps": gap_merge["skipped_existing"],
        # IMP-370: was `reopened_gaps`, but /sync never reopens a gap; these stay CLOSED.
        "closed_gaps_detected_again": reopened,
        "sync_closed_gaps": sync_resolution["closed"],
        "source_conflicts": conflicts,
        "answered_context_requests": answered_ctx,
        "knowledge_metabolism": metabolism,
        "staleness": stale_result,
        "suspicious_trace_links": suspicious_links,
        "context_pack": focus_pack.get("path"),
        "interaction_digest": interaction_digest,
        "prose_review": prose,
    }


def sync_change_with_analysis(
    project_id: str, source: Path, analysis: Path, note: str = "", digest: bool = False
) -> dict[str, object]:
    """IMP-337 (337b): validate the agent's change analysis BEFORE anything is written,
    then run the normal /sync and open one blocking GAP-CHG per valid candidate."""
    from .errors import InputError
    from .sync_analysis import apply_change_analysis, load_change_analysis, validate_change_analysis

    if not workspace_path(project_id).exists():
        raise GateRefusal(f"Workspace not found: {project_id}")
    if source.is_dir():
        raise InputError("--analysis needs --source to be the one note it analyses, not a folder.")
    data = load_change_analysis(analysis)
    note_text = read_source(source).text
    candidates = validate_change_analysis(project_id, data, note_text)
    result = sync_change(project_id, source, note, digest=digest, reload=True)  # the analysis is new input on a note
    result["change_analysis"] = apply_change_analysis(
        project_id, analysis, data, candidates,
        change_id=str(result["change_id"]), source_id=str(result["source_id"]), note_text=note_text,
    )
    return result


PROSE_NOTICE = (
    "Prose is stored and indexed, not interpreted: {n} line(s) changed nothing. "
    "Rewrite them as gap answers (### GAP-...) or pass a cited analysis with "
    "/sync --source NOTE --analysis FILE."
)
_GAP_BLOCK_RE = re.compile(r"^#{2,4}\s+GAP-[A-Z0-9-]+")


def prose_review(project_id: str, text: str) -> dict[str, object]:
    """IMP-337 (337a): what /sync interpreted in the change and what it only stored.

    Interpreted lines are the `### GAP-` answer blocks and the `Subject: value`
    statements the contradiction pass anchors; headings are structure. Every
    other non-empty line is stored and indexed but moved nothing. Decision lines
    are counted and, when they share words with a closed gap or a live
    assumption, listed as hints. Read-only: nothing here opens, closes or
    rewrites anything.
    """
    from .interaction_digest import change_hints, decision_candidates, iter_citable_lines
    from .source_conflicts import extract_statements

    statement_lines = {int(item["line"]) for item in extract_statements(text)}
    gap_lines: set[int] = set()
    in_block = False
    content = 0
    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if line.startswith("#"):
            in_block = bool(_GAP_BLOCK_RE.match(line))
            continue
        if not line:
            continue
        content += 1
        if in_block:
            gap_lines.add(number)
    uninterpreted = content - len(gap_lines | statement_lines)
    decisions = decision_candidates(iter_citable_lines(text))
    return {
        "content_lines": content,
        "gap_response_lines": len(gap_lines),
        "statement_lines": len(statement_lines - gap_lines),
        "uninterpreted_lines": uninterpreted,
        "decision_candidates": len(decisions),
        "hints": change_hints(project_id, text) if decisions else [],
        "notice": PROSE_NOTICE.format(n=uninterpreted) if uninterpreted else "",
    }


def sync_pending_sources(project_id: str, note: str = "autonomous sync", digest: bool = False) -> dict[str, object]:
    base = workspace_path(project_id)
    if not base.exists():
        raise GateRefusal(f"Workspace not found: {project_id}")

    novelty = discover_source_novelty(project_id)
    pending = novelty["pending"]
    results = []
    source_ids: dict[str, str] = {}
    for item in pending:
        source = item["path"]
        result = sync_change(project_id, source, f"{note}; detected={item['reason']}", digest=digest, reload=True)
        result["detected_reason"] = item["reason"]
        results.append(result)
        source_ids[item["key"]] = str(result["source_id"])
    # IMP-250a: an unseen path whose content is already a row (or another path in
    # this scan) is that source again: it joins the row and is not crossed twice.
    duplicates = []
    for item in novelty["duplicates"]:
        source_id = item["source_id"] or source_ids.get(str(item["same_as"]))
        if source_id:
            record_duplicate_source(project_id, item["path"], source_id)
            duplicates.append({"path": item["key"], "source_id": source_id})

    if not results:
        reindex_workspace(project_id)
        update_state(project_id, phase="change_scan_completed", health="CLEAN")
    else:
        update_state(
            project_id,
            phase="change_batch_synced",
            health="DIRTY" if any(
                result.get("merged_gaps")
                or result.get("staleness", {}).get("stale_stories")
                or result.get("knowledge_metabolism", {}).get("downstream_stale_artifacts")
                for result in results
            ) else "CLEAN",
            metrics={"changes_processed": len(results)},
        )

    return {
        "project_id": project_id,
        "mode": "autonomous",
        "detected": len(pending),
        "processed": len(results),
        "duplicate_content": duplicates,
        "changes": results,
    }


def impacted_nodes(project_id: str) -> list[str]:
    graph = load_graph(project_id)
    roots = [node["id"] for node in graph.get("nodes", []) if node.get("type") == "requirement"]
    affected: list[str] = []
    stack = roots[:]
    while stack:
        node_id = stack.pop(0)
        for child in children_of(project_id, node_id):
            if child not in affected:
                affected.append(child)
                stack.append(child)
    return affected


SEMANTIC_CHANGE_RE = re.compile(
    r"\b("
    r"no longer|must not|shall not|instead|replace[sd]?|replacing|remove[sd]?|"
    r"exclude[sd]?|out of scope|deprecat(?:e|ed|es)|rename[sd]?|now|"
    r"changes? from|new target|different owner|"
    r"ya no|no debe|en vez de|reemplaza|reemplazar|elimina|excluye|"
    r"fuera de alcance|depreca|renombra|ahora|cambia de|nuevo objetivo"
    r")\b",
    re.I,
)
COSMETIC_CHANGE_RE = re.compile(
    r"\b(typo|spelling|copy edit|formatting|whitespace|grammar|cosmetic|"
    r"ortografia|ortograf[ií]a|redacci[oó]n|formato|espacios|cosmetico|cosm[eé]tico)\b",
    re.I,
)


def semantic_change_analysis(text: str, note: str = "") -> dict[str, object]:
    """Detect semantic change cues without inferring replacement facts."""
    combined = f"{note}\n{text}"
    triggers = sorted({match.group(0).lower() for match in SEMANTIC_CHANGE_RE.finditer(combined)})
    cosmetic_only = bool(COSMETIC_CHANGE_RE.search(combined)) and not triggers
    return {
        "suspicious": bool(triggers) and not cosmetic_only,
        "triggers": triggers,
        "reason": "semantic-change-cue" if triggers and not cosmetic_only else "",
    }


def mark_suspicious_trace_links(
    project_id: str,
    change_id: str,
    affected: list[str],
    analysis: dict[str, object],
) -> list[dict[str, object]]:
    if not analysis.get("suspicious") or not affected:
        return []
    graph = load_graph(project_id)
    affected_set = set(affected)
    node_lookup = {node["id"]: node for node in graph.get("nodes", [])}
    reason = str(analysis.get("reason") or "semantic-change-cue")
    triggers = [str(item) for item in analysis.get("triggers", []) if str(item)]
    suspicious: list[dict[str, object]] = []
    for edge in graph.get("edges", []):
        if edge.get("from") != change_id or edge.get("to") not in affected_set:
            continue
        edge["suspicious"] = True
        edge["suspicion_reason"] = reason
        edge["suspicion_triggers"] = triggers
        edge["review_status"] = "needs-ba-review"
        node = node_lookup.get(str(edge.get("to")), {})
        suspicious.append(
            {
                "from": change_id,
                "to": edge.get("to"),
                "relation": edge.get("relation"),
                "target_type": node.get("type", "unknown"),
                "target_title": node.get("title", ""),
                "reason": reason,
                "triggers": triggers,
            }
        )
    save_graph(project_id, graph)
    return suspicious


def suspicious_links_state(project_id: str, change_id: str, links: list[dict[str, object]]) -> dict[str, object]:
    """IMP-369: the semantic-change marker this /sync leaves in state.json.

    It records when the change happened and which downstream artifacts it
    feeds, so regenerating them afterwards (or `/trace --reviewed`) clears the
    /health finding. A neutral /sync no longer wipes a review still pending:
    only a review or a regeneration does.
    """
    from .health import pending_suspicious_links
    from .knowledge.metabolism import downstream_stale_artifacts

    if not links and pending_suspicious_links(project_id) is not None:
        return {}
    return {
        "suspicious_trace_links": {
            "change_id": change_id,
            "count": len(links),
            "links": links,
            "recorded_at": utc_now(),
            "downstream_artifacts": downstream_stale_artifacts(workspace_path(project_id)) if links else [],
        }
    }


def focus_query_for_change(note: str, change_text: str, limit: int = 600) -> str:
    """Compact query for the change focus pack (IMP-127): operator note first,
    then the head of the change text. Bounded so retrieval stays cheap."""
    combined = f"{note}\n{change_text}".strip()
    return combined[:limit]


def sync_detection_text(base: Path, change_text: str) -> str:
    """Evaluate a change against accumulated knowledge, not as an isolated note."""
    context_paths = [
        base / "01_discovery" / "gaps.md",
        base / "01_discovery" / "identity_seeds.md",
        base / "01_discovery" / "decisions.md",
        base / "02_requirements" / "requirements.md",
        base / "02_requirements" / "project-brief.md",
        base / "03_specs" / "prd.md",
        base / "03_specs" / "specs.md",
    ]
    chunks = [change_text]
    for path in context_paths:
        if path.exists():
            chunks.append(path.read_text(encoding="utf-8"))
    return "\n\n".join(chunks)


def detect_sync_gaps(base: Path, change_text: str) -> list[dict[str, str]]:
    """The gaps a change raises (IMP-370: anchored in the change itself).

    A gap that quotes a mention (`evidence_mention`: "auth", "batch process", a
    weak word...) fires only when the CHANGE says it: the workspace text holds the
    gap ledger, the brief and the specs, whose own wording ("auth method",
    "batch process") used to raise GAP-AUTH-MODEL and GAP-CTP-BATCH on every
    /sync. A gap about something missing everywhere (no mention to quote) is still
    judged against the accumulated knowledge, so a short note does not reopen every
    "nobody said who the users are" gap. A mention in the change whose detail the
    workspace already gives (the accumulated scan does not fire) stays quiet too.
    """
    context = load_domain_context(base)
    accumulated = detect_gaps(sync_detection_text(base, change_text), context)
    own = {gap["id"]: gap for gap in detect_gaps(change_text, context)}

    def quotes(gap: dict[str, str]) -> bool:
        return bool(str(gap.get("evidence_mention", "")).strip())

    result: list[dict[str, str]] = []
    for gap in accumulated:
        if not quotes(gap):
            result.append(gap)
        elif gap["id"] in own and quotes(own[gap["id"]]):
            result.append(own[gap["id"]])  # quoted from the change, not from the workspace
    return result


def materialize_sync_gaps(project_id: str, detected: list[dict[str, str]], change_id: str) -> dict[str, list[str]]:
    base = workspace_path(project_id)
    gaps_path = base / "01_discovery" / "gaps.md"
    if not gaps_path.exists() or not detected:
        return {"merged": [], "skipped_existing": []}

    existing = [gap for gap in parse_gap_rows(gaps_path.read_text(encoding="utf-8")) if gap.get("id") != "NONE"]
    existing_ids = {gap["id"] for gap in existing}
    req_id = existing[0].get("parent", "REQ-001").strip("`") if existing else "REQ-001"
    merged: list[dict[str, str]] = []
    skipped: list[str] = []
    for gap in detected:
        if gap["id"] in existing_ids:
            skipped.append(gap["id"])
            continue
        merged_gap = {
            **gap,
            "status": "OPEN",
            "origin": "sync",
            "evidence_mention": gap.get("evidence_mention") or change_id,
            "resolution_note": f"raised-by-sync: review change `{change_id}` before downstream execution",
        }
        merged.append(merged_gap)
        existing_ids.add(gap["id"])

    if not merged:
        return {"merged": [], "skipped_existing": skipped}

    language = project_language(project_id)
    all_gaps = existing + merged
    write_text(gaps_path, render_gaps(project_id, all_gaps, req_id, language))
    counts = count_gaps(all_gaps)
    counts["sync_origin"] = sum(1 for gap in all_gaps if gap.get("origin") == "sync")
    update_state(project_id, gap_counts=counts, readiness_stage=readiness_stage_after_gap_change(project_id, counts))
    return {"merged": [gap["id"] for gap in merged], "skipped_existing": skipped}


def apply_structured_gap_responses(
    project_id: str, text: str, source: Path, change_id: str, block_note: str | None = None
) -> dict[str, object]:
    responses = parse_gap_responses(text)
    if not responses:
        return {"closed": [], "answered": [], "partially_closed": [], "open": []}
    base = workspace_path(project_id)
    gaps_path = base / "01_discovery" / "gaps.md"
    if not gaps_path.exists():
        return {"closed": [], "answered": [], "partially_closed": [], "open": []}
    existing = parse_gap_rows(gaps_path.read_text(encoding="utf-8"))
    req_id = existing[0].get("parent", "REQ-001").strip("`") if existing else "REQ-001"
    result = apply_gap_responses(existing, responses, can_close=block_note is None, block_note=block_note)
    annotate_resolution_source_types(result, source)
    language = project_language(project_id)
    write_text(gaps_path, render_gaps(project_id, result["gaps"], req_id, language))
    seed_ids = materialize_resolution_seeds(project_id, result["closed"], change_id)  # type: ignore[arg-type]
    decision_ids = materialize_resolution_decisions(project_id, result["closed"], change_id)  # type: ignore[arg-type]
    ears_ids = materialize_ears_requirements(project_id, result["closed"], change_id)  # type: ignore[arg-type]
    for node_id in seed_ids + decision_ids:
        add_edge(project_id, change_id, node_id, "confirms")
    for node_id in ears_ids:
        add_edge(project_id, change_id, node_id, "normalizes")
    update_gap_report_node_status(project_id, result["counts"])  # type: ignore[arg-type]
    update_state(project_id, gap_counts=result["counts"], readiness_stage=readiness_stage_after_gap_change(project_id, result["counts"]))  # type: ignore[arg-type]
    return {
        "closed": [item["id"] for item in result["closed"]],  # type: ignore[index]
        "answered": [item["id"] for item in result["answered"]],  # type: ignore[index]
        "partially_closed": [item["id"] for item in result["partially_closed"]],  # type: ignore[index]
        "open": [item["id"] for item in result["open"]],  # type: ignore[index]
    }


def summarize_impact(project_id: str, affected: list[str]) -> dict[str, object]:
    graph = load_graph(project_id)
    node_lookup = {node["id"]: node for node in graph.get("nodes", [])}
    return {
        "impacted": affected,
        "count": len(affected),
        "by_type": count_by_type(affected, node_lookup),
    }


def reopened_closed_gap_ids(base: Path, detected_gaps: list[dict[str, str]]) -> list[str]:
    gaps_path = base / "01_discovery" / "gaps.md"
    if not gaps_path.exists() or not detected_gaps:
        return []
    existing = parse_gap_rows(gaps_path.read_text(encoding="utf-8"))
    closed = {gap["id"] for gap in existing if str(gap.get("status", "")).upper() == "CLOSED"}
    detected = {gap["id"] for gap in detected_gaps}
    return sorted(closed & detected)


def change_route(source: Path) -> tuple[str, bool]:
    """The 07_changes sub-folder a change goes to, and whether its path named it.

    False means no keyword matched and the change fell into the domain-updates
    folder by default, which says nothing about what kind of source it is.
    """
    normalized = source.as_posix().lower()
    if "technology_context" in normalized or "design_context" in normalized or "quality_context" in normalized:
        return "03_domain_updates", True
    if "meeting" in normalized or "minuta" in normalized or "minutes" in normalized:
        return "01_meetings", True
    if "mail" in normalized or "slack" in normalized:
        return "02_mail_slack", True
    if "interaction" in normalized or "client" in normalized or "response" in normalized:
        return "00_client_responses", True
    return "03_domain_updates", False


def change_target_dir(base: Path, source: Path) -> Path:
    target = base / "07_changes" / change_route(source)[0]
    target.mkdir(parents=True, exist_ok=True)
    return target


def routed_source_kind(source: Path) -> str | None:
    """IMP-370: the source kind the /sync routing implies (meeting, mail_slack...), or None.

    A file outside the known input folders used to stay `unclassified`, so no
    precedence rule could ever settle a contradiction it took part in. When its
    path named the routing (a "meeting" or "mail" file), that is its kind.
    """
    from .source_registry import KIND_BY_FOLDER
    from .sources import source_key

    # The path as the registry keys it (relative to the project root when it can be), so a
    # temp or home folder name ("tmpmail3x", "/home/client") never decides the kind.
    folder, matched = change_route(Path(source_key(source)))
    return KIND_BY_FOLDER.get(folder) if matched else None


AUTHORITY_HINT = (
    "{source_id} has no source kind (authority `unclassified`), so no precedence rule can settle a "
    "contradiction it takes part in. Set it: /sources {project_id} --id {source_id} --authority KIND "
    "(minutes, decision_record, client_document, interaction, tech_lead, spec, ...)."
)


def source_authority_report(project_id: str, source_id: str) -> dict[str, object]:
    row = source_row(project_id, source_id) or {}
    authority = str(row.get("authority") or "unclassified")
    report: dict[str, object] = {"source_id": source_id, "authority": authority}
    if authority == "unclassified":
        report["next_step"] = AUTHORITY_HINT.format(project_id=project_id, source_id=source_id)
    return report


def append_metabolism_log(
    project_id: str,
    change_id: str,
    source: Path,
    affected: list[str],
    gaps: list[dict[str, str]],
    note: str,
    reopened: list[str] | None = None,
    knowledge_metabolism: dict[str, object] | None = None,
) -> Path:
    path = workspace_path(project_id) / "07_changes" / "metabolism_log.md"
    if not path.exists():
        write_text(path, f"""# Metabolism Log - {project_id}

Every sync event records the evolution of project knowledge. Source files remain authoritative; LanceDB is retrieval memory.

| Timestamp | Change ID | Source | Event Type | Health Signal |
| --- | --- | --- | --- | --- |
""")
    health_signal = "DIRTY" if gaps else "CLEAN"
    event_type = "GAP_OR_CHANGE_INPUT"
    reopened = reopened or []
    lines = [
        f"| {utc_now()} | `{change_id}` | `{source.as_posix()}` | {event_type} | {health_signal} |\n",
        "\n",
        f"## {change_id} Impact Detail\n\n",
        f"- Operator note: {note or 'No operator note provided.'}\n",
        f"- Affected nodes: {', '.join(f'`{node}`' for node in affected) if affected else 'None'}\n",
    ]
    if gaps:
        lines.append("- New or unresolved gaps:\n")
        for gap in gaps:
            lines.append(f"  - `{gap['id']}` ({gap['severity']}): {gap['description']}\n")
    else:
        lines.append("- New or unresolved gaps: None detected by deterministic scan.\n")
    lines.append(
        "- Closed gaps detected again (not reopened): "
        f"{', '.join(f'`{gap_id}`' for gap_id in reopened) if reopened else 'None'}\n"
    )
    if knowledge_metabolism:
        units = knowledge_metabolism.get("impacted_knowledge_units", [])
        stale = knowledge_metabolism.get("downstream_stale_artifacts", [])
        associative = knowledge_metabolism.get("associative_findings", [])
        lines.append(f"- Impacted knowledge units: {', '.join(f'`{unit}`' for unit in units) if units else 'None'}\n")
        lines.append(f"- Downstream stale artifacts: {', '.join(f'`{item}`' for item in stale) if stale else 'None'}\n")
        associative_targets = [str(item.get("target")) for item in associative if item.get("target")]
        lines.append(
            f"- Associative impact candidates (BA review): {', '.join(f'`{target}`' for target in associative_targets) if associative_targets else 'None'}\n"
        )
    lines.append("- Required action: review impacted requirements, PRD/specs, backlog, quality, and traceability before marking the change applied.\n\n")
    append_text(path, "".join(lines))
    return path


def render_associative_findings(findings: list[dict[str, object]] | None) -> str:
    findings = findings or []
    if not findings:
        return "- None."
    rows = []
    for finding in findings:
        citation = finding.get("citation", {}) or {}
        source = citation.get("source_path", "") or "unknown source"
        section = citation.get("section_path", "")
        line_start = citation.get("line_start", 0)
        line_end = citation.get("line_end", 0)
        locator = f"`{source}`"
        if section:
            locator += f" §{section}"
        if line_start or line_end:
            locator += f" L{line_start}-{line_end}"
        rows.append(
            f"- `{finding.get('target')}` (sim {finding.get('score')}): "
            f"{finding.get('reason', 'posible impacto por similitud')} — cita {locator}"
        )
    return "\n".join(rows)


def render_impact(
    project_id: str,
    change_id: str,
    affected: list[str],
    gaps: list[dict[str, str]],
    note: str,
    blast_radius: dict[str, object] | None = None,
    reopened: list[str] | None = None,
    merged_gaps: list[str] | None = None,
    sync_resolution: dict[str, object] | None = None,
    knowledge_metabolism: dict[str, object] | None = None,
    story_staleness: dict[str, object] | None = None,
    suspicious_trace_links: list[dict[str, object]] | None = None,
    prose: dict[str, object] | None = None,
) -> str:
    prose = prose or {}
    hint_rows = "\n".join(
        f"- L{hint['line']} \"{hint['quote']}\" -> related: "
        + ", ".join(f"`{item['id']}`" for item in hint["related_gaps"] + hint["related_assumptions"])
        for hint in prose.get("hints", [])  # type: ignore[union-attr]
    ) or "- None."
    prose_block = (
        f"- Lines interpreted as gap answers: {prose.get('gap_response_lines', 0)}\n"
        f"- Lines anchored as statements: {prose.get('statement_lines', 0)}\n"
        f"- Lines stored but not interpreted: {prose.get('uninterpreted_lines', 0)}\n"
        f"- Decision lines: {prose.get('decision_candidates', 0)}\n"
        + (f"\n{prose['notice']}\n" if prose.get("notice") else "")
        + "\nDecision lines related to something confirmed (hint only; this does not claim a "
        "contradiction and nothing was applied):\n\n"
        + hint_rows
    )
    affected_rows = "\n".join(f"- `{node_id}`" for node_id in affected) or "- No existing downstream nodes found."
    gap_rows = "\n".join(
        f"- `{gap['id']}` ({gap['severity']}): {gap['description']}" for gap in gaps
    ) or "- No new deterministic gaps detected."
    note_text = note or "No operator note provided."
    blast_radius = blast_radius or {"count": len(affected), "by_type": {}}
    reopened = reopened or []
    merged_gaps = merged_gaps or []
    by_type = blast_radius.get("by_type", {})
    blast_rows = "\n".join(f"| {node_type} | {count} |" for node_type, count in by_type.items()) or "| none | 0 |"
    reopened_rows = "\n".join(f"- `{gap_id}`" for gap_id in reopened) or "- None."
    merged_gap_rows = "\n".join(f"- `{gap_id}`" for gap_id in merged_gaps) or "- None."
    sync_resolution = sync_resolution or {}
    knowledge_metabolism = knowledge_metabolism or {}
    story_staleness = story_staleness or {}
    suspicious_trace_links = suspicious_trace_links or []
    sync_closed_rows = "\n".join(f"- `{gap_id}`" for gap_id in sync_resolution.get("closed", [])) or "- None."
    unit_rows = "\n".join(f"- `{unit_id}`" for unit_id in knowledge_metabolism.get("impacted_knowledge_units", [])) or "- None."
    validated_rows = "\n".join(f"- `{item}`" for item in knowledge_metabolism.get("validated_assumptions", [])) or "- None."
    invalidated_rows = "\n".join(f"- `{item}`" for item in knowledge_metabolism.get("invalidated_assumptions", [])) or "- None."
    associative_rows = render_associative_findings(knowledge_metabolism.get("associative_findings", []))
    stale_rows = "\n".join(f"- `{item}`" for item in knowledge_metabolism.get("downstream_stale_artifacts", [])) or "- None."
    stale_story_rows = "\n".join(f"- `{item}`" for item in story_staleness.get("stale_stories", [])) or "- None."
    suspicious_rows = "\n".join(
        f"- `{item.get('from')}` -> `{item.get('to')}` ({item.get('target_type', 'unknown')}): {item.get('reason')} via {', '.join(str(trigger) for trigger in item.get('triggers', [])) or 'semantic cue'}"
        for item in suspicious_trace_links
    ) or "- None."
    return f"""# Change Impact Report - {project_id}

- Change: `{change_id}`
- Status: `pending_review`

## Operator Note

{note_text}

## Potentially Affected Nodes

{affected_rows}

## Blast Radius Summary

| Node Type | Count |
| --- | ---: |
{blast_rows}

## New Gaps Detected In Change Input

{gap_rows}

## Prose Review (IMP-337)

{prose_block}

## Closed Gaps Detected Again

_Report only (IMP-337): closed gaps whose trigger fired again in this change.
Nothing is reopened here; a change reopens a gap only through a cited analysis
(`/sync --analysis`) that the BA accepts (`/gaps --disposition accepted`)._

- Closed gaps detected again (not reopened): {len(reopened)}
{reopened_rows}

## Governed Gaps Added To gaps.md

{merged_gap_rows}

## Structured Gap Responses Applied By Sync

{sync_closed_rows}

## Knowledge Ledger Metabolism

- Knowledge state: `{knowledge_metabolism.get("knowledge_state", "N/A")}`
- Development readiness: `{knowledge_metabolism.get("development_readiness", "N/A")}`

Impacted knowledge units:

{unit_rows}

Validated assumptions:

{validated_rows}

Invalidated assumptions:

{invalidated_rows}

## Associative Impact Candidates (BA review)

_Suggested by meaning-based retrieval (IMP-125), not by deterministic invalidation. These are candidates for BA review — nothing is auto-invalidated; the graph remains the authority of propagation._

{associative_rows}

## Downstream Staleness

Knowledge-stale artifacts:

{stale_rows}

Stale stories:

{stale_story_rows}

## Suspicious Trace Links

{suspicious_rows}

## Required BA Action

Review impacted requirements, specs, backlog, acceptance criteria, context packs, and decisions. Regenerate backlog only when the change materially affects story scope, sequencing, acceptance, or execution contracts.
"""
