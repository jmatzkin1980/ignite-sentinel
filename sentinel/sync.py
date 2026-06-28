from __future__ import annotations

import re
import shutil
from pathlib import Path

from .backlog.hooks import mark_stale_stories_for_spec_units, stale_spec_units_from_change
from .discovery import (
    count_gaps,
    detect_gaps,
    load_domain_context,
    parse_gap_rows,
    readiness_stage_for_counts,
    render_gaps,
)
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
from .sources import discover_pending_sources, mark_source_processed
from .core.graph import add_edge, add_node, children_of, count_by_type, load_graph, save_graph
from .core.io import append_text
from .workspace import read_json, update_state, utc_now, workspace_path


def sync_change(project_id: str, source: Path, note: str = "") -> dict[str, object]:
    base = workspace_path(project_id)
    if not base.exists():
        raise RuntimeError(f"Workspace not found: {project_id}")

    target_dir = change_target_dir(base, source)
    target = unique_target(target_dir / f"{source.stem}{source.suffix.lower() if source.suffix.lower() in {'.md', '.txt', '.html', '.htm'} else '.md'}")
    shutil.copyfile(source, target)
    text = source.read_text(encoding="utf-8")
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

    gaps = detect_gaps(sync_detection_text(base, text), load_domain_context(base))
    gap_merge = materialize_sync_gaps(project_id, gaps, change_id)
    reopened = reopened_closed_gap_ids(base, gaps)
    sync_resolution = apply_structured_gap_responses(project_id, text, source, change_id)
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
    impact_path = unique_target(target_dir / f"{source.stem}_impact_report.md")
    impact_path.write_text(
        render_impact(
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
        ),
        encoding="utf-8",
    )
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
    mark_source_processed(project_id, source, "synced", change_id)
    mark_source_processed(project_id, target, "change_copy", change_id)
    mark_source_processed(project_id, impact_path, "impact_report", impact_id)
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
        suspicious_trace_links={
            "change_id": change_id,
            "count": len(suspicious_links),
            "links": suspicious_links,
        },
    )
    return {
        "change_id": change_id,
        "impact_report_id": impact_id,
        "source": str(source.as_posix()),
        "path": str(target.as_posix()),
        "affected": affected,
        "gaps": gaps,
        "merged_gaps": gap_merge["merged"],
        "skipped_existing_gaps": gap_merge["skipped_existing"],
        "reopened_gaps": reopened,
        "sync_closed_gaps": sync_resolution["closed"],
        "knowledge_metabolism": metabolism,
        "staleness": stale_result,
        "suspicious_trace_links": suspicious_links,
        "context_pack": focus_pack.get("path"),
    }


def sync_pending_sources(project_id: str, note: str = "autonomous sync") -> dict[str, object]:
    base = workspace_path(project_id)
    if not base.exists():
        raise RuntimeError(f"Workspace not found: {project_id}")

    pending = discover_pending_sources(project_id)
    results = []
    for item in pending:
        source = item["path"]
        result = sync_change(project_id, source, f"{note}; detected={item['reason']}")
        result["detected_reason"] = item["reason"]
        results.append(result)

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
    gaps_path.write_text(render_gaps(project_id, all_gaps, req_id, language), encoding="utf-8")
    counts = count_gaps(all_gaps)
    counts["sync_origin"] = sum(1 for gap in all_gaps if gap.get("origin") == "sync")
    update_state(project_id, gap_counts=counts, readiness_stage=readiness_stage_for_counts(counts))
    return {"merged": [gap["id"] for gap in merged], "skipped_existing": skipped}


def apply_structured_gap_responses(project_id: str, text: str, source: Path, change_id: str) -> dict[str, object]:
    responses = parse_gap_responses(text)
    if not responses:
        return {"closed": [], "answered": [], "partially_closed": [], "open": []}
    base = workspace_path(project_id)
    gaps_path = base / "01_discovery" / "gaps.md"
    if not gaps_path.exists():
        return {"closed": [], "answered": [], "partially_closed": [], "open": []}
    existing = parse_gap_rows(gaps_path.read_text(encoding="utf-8"))
    req_id = existing[0].get("parent", "REQ-001").strip("`") if existing else "REQ-001"
    result = apply_gap_responses(existing, responses)
    annotate_resolution_source_types(result, source)
    language = project_language(project_id)
    gaps_path.write_text(render_gaps(project_id, result["gaps"], req_id, language), encoding="utf-8")
    seed_ids = materialize_resolution_seeds(project_id, result["closed"], change_id)  # type: ignore[arg-type]
    decision_ids = materialize_resolution_decisions(project_id, result["closed"], change_id)  # type: ignore[arg-type]
    ears_ids = materialize_ears_requirements(project_id, result["closed"], change_id)  # type: ignore[arg-type]
    for node_id in seed_ids + decision_ids:
        add_edge(project_id, change_id, node_id, "confirms")
    for node_id in ears_ids:
        add_edge(project_id, change_id, node_id, "normalizes")
    update_gap_report_node_status(project_id, result["counts"])  # type: ignore[arg-type]
    update_state(project_id, gap_counts=result["counts"], readiness_stage=readiness_stage_for_counts(result["counts"]))  # type: ignore[arg-type]
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


def change_target_dir(base: Path, source: Path) -> Path:
    normalized = source.as_posix().lower()
    if "technology_context" in normalized or "design_context" in normalized or "quality_context" in normalized:
        target = base / "07_changes" / "03_domain_updates"
    elif "meeting" in normalized or "minuta" in normalized:
        target = base / "07_changes" / "01_meetings"
    elif "mail" in normalized or "slack" in normalized:
        target = base / "07_changes" / "02_mail_slack"
    elif "interaction" in normalized or "client" in normalized or "response" in normalized:
        target = base / "07_changes" / "00_client_responses"
    else:
        target = base / "07_changes" / "03_domain_updates"
    target.mkdir(parents=True, exist_ok=True)
    return target


def project_language(project_id: str) -> str:
    state = read_json(workspace_path(project_id) / "state.json", {})
    language = state.get("project_language", "en")
    return str(language if language in {"es", "en"} else "en")


def unique_target(path: Path) -> Path:
    if not path.exists():
        return path
    counter = 2
    while True:
        candidate = path.with_name(f"{path.stem}-{counter}{path.suffix}")
        if not candidate.exists():
            return candidate
        counter += 1


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
        path.write_text(
            f"""# Metabolism Log - {project_id}

Every sync event records the evolution of project knowledge. Source files remain authoritative; LanceDB is retrieval memory.

| Timestamp | Change ID | Source | Event Type | Health Signal |
| --- | --- | --- | --- | --- |
""",
            encoding="utf-8",
        )
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
    lines.append(f"- Reopened closed gaps: {', '.join(f'`{gap_id}`' for gap_id in reopened) if reopened else 'None'}\n")
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
) -> str:
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

## Reopened Closed Gaps

- Reopened closed gaps: {len(reopened)}
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
