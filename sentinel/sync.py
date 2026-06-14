from __future__ import annotations

import shutil
from pathlib import Path

from .backlog_hooks import mark_stale_stories_for_spec_units, stale_spec_units_from_change
from .discovery import (
    count_gaps,
    detect_gaps,
    load_domain_context,
    parse_gap_rows,
    readiness_stage_for_counts,
    render_gaps,
)
from .memory import ContextBroker, reindex_workspace
from .sources import discover_pending_sources, mark_source_processed
from .traceability import add_edge, add_node, children_of, count_by_type, load_graph
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

    gaps = detect_gaps(sync_detection_text(base, text), load_domain_context(base))
    gap_merge = materialize_sync_gaps(project_id, gaps, change_id)
    reopened = reopened_closed_gap_ids(base, gaps)
    stale_units = stale_spec_units_from_change(source, text)
    stale_result = mark_stale_stories_for_spec_units(
        project_id,
        stale_units,
        f"/sync change {change_id} touched Spec Unit source.",
        change_id,
    )
    impact_path = unique_target(target_dir / f"{source.stem}_impact_report.md")
    impact_path.write_text(
        render_impact(project_id, change_id, affected, gaps, note, blast_radius, reopened, gap_merge["merged"]),
        encoding="utf-8",
    )
    impact_id = add_node(project_id, "DEC", "impact_report", impact_path, "Change impact report", status="pending")
    add_edge(project_id, change_id, impact_id, "produces")

    broker = ContextBroker(project_id)
    broker.index_artifact(change_id, "change", target, text, trace_ids=[change_id])
    broker.index_artifact(
        impact_id,
        "impact_report",
        impact_path,
        impact_path.read_text(encoding="utf-8"),
        trace_ids=[change_id, impact_id],
    )
    metabolism_path = append_metabolism_log(project_id, change_id, source, affected, gaps, note, reopened)
    broker.index_artifact(
        "METABOLISM-LOG",
        "metabolism_log",
        metabolism_path,
        metabolism_path.read_text(encoding="utf-8"),
        trace_ids=[change_id],
    )
    reindex_workspace(project_id)
    mark_source_processed(project_id, source, "synced", change_id)
    mark_source_processed(project_id, target, "change_copy", change_id)
    mark_source_processed(project_id, impact_path, "impact_report", impact_id)
    update_state(
        project_id,
        phase="change_synced",
        health="DIRTY" if gap_merge["merged"] or stale_result.get("stale_stories") else "CLEAN",
        last_change_id=change_id,
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
        "staleness": stale_result,
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
            health="DIRTY" if any(result.get("merged_gaps") or result.get("staleness", {}).get("stale_stories") for result in results) else "CLEAN",
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
    with path.open("a", encoding="utf-8") as handle:
        handle.write(f"| {utc_now()} | `{change_id}` | `{source.as_posix()}` | {event_type} | {health_signal} |\n")
        handle.write("\n")
        handle.write(f"## {change_id} Impact Detail\n\n")
        handle.write(f"- Operator note: {note or 'No operator note provided.'}\n")
        handle.write(f"- Affected nodes: {', '.join(f'`{node}`' for node in affected) if affected else 'None'}\n")
        if gaps:
            handle.write("- New or unresolved gaps:\n")
            for gap in gaps:
                handle.write(f"  - `{gap['id']}` ({gap['severity']}): {gap['description']}\n")
        else:
            handle.write("- New or unresolved gaps: None detected by deterministic scan.\n")
        handle.write(
            f"- Reopened closed gaps: {', '.join(f'`{gap_id}`' for gap_id in reopened) if reopened else 'None'}\n"
        )
        handle.write("- Required action: review impacted requirements, PRD/specs, backlog, quality, and traceability before marking the change applied.\n\n")
    return path


def render_impact(
    project_id: str,
    change_id: str,
    affected: list[str],
    gaps: list[dict[str, str]],
    note: str,
    blast_radius: dict[str, object] | None = None,
    reopened: list[str] | None = None,
    merged_gaps: list[str] | None = None,
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

## Required BA Action

Review impacted requirements, specs, backlog, acceptance criteria, context packs, and decisions. Regenerate backlog only when the change materially affects story scope, sequencing, acceptance, or execution contracts.
"""
