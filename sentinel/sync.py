from __future__ import annotations

import shutil
from pathlib import Path

from .discovery import detect_gaps, parse_gap_rows
from .memory import ContextBroker, reindex_workspace
from .sources import discover_pending_sources, mark_source_processed
from .traceability import add_edge, add_node, children_of, count_by_type, load_graph
from .workspace import update_state, utc_now, workspace_path


def sync_change(project_id: str, source: Path, note: str = "") -> dict[str, object]:
    base = workspace_path(project_id)
    if not base.exists():
        raise RuntimeError(f"Workspace not found: {project_id}")

    target_dir = change_target_dir(base, source)
    target = unique_target(target_dir / f"{source.stem}.md")
    shutil.copyfile(source, target)
    text = source.read_text(encoding="utf-8")
    change_id = add_node(project_id, "CHG", "change", target, source.stem, status="pending", domain="product")

    affected = impacted_nodes(project_id)
    blast_radius = summarize_impact(project_id, affected)
    for node_id in affected:
        add_edge(project_id, change_id, node_id, "may_impact")

    gaps = detect_gaps(text)
    reopened = reopened_closed_gap_ids(base, gaps)
    impact_path = unique_target(target_dir / f"{source.stem}_impact_report.md")
    impact_path.write_text(render_impact(project_id, change_id, affected, gaps, note, blast_radius, reopened), encoding="utf-8")
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
        health="DIRTY" if gaps else "CLEAN",
        last_change_id=change_id,
    )
    return {
        "change_id": change_id,
        "impact_report_id": impact_id,
        "source": str(source.as_posix()),
        "path": str(target.as_posix()),
        "affected": affected,
        "gaps": gaps,
        "reopened_gaps": reopened,
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
            health="DIRTY" if any(result.get("gaps") for result in results) else "CLEAN",
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
) -> str:
    affected_rows = "\n".join(f"- `{node_id}`" for node_id in affected) or "- No existing downstream nodes found."
    gap_rows = "\n".join(
        f"- `{gap['id']}` ({gap['severity']}): {gap['description']}" for gap in gaps
    ) or "- No new deterministic gaps detected."
    note_text = note or "No operator note provided."
    blast_radius = blast_radius or {"count": len(affected), "by_type": {}}
    reopened = reopened or []
    by_type = blast_radius.get("by_type", {})
    blast_rows = "\n".join(f"| {node_type} | {count} |" for node_type, count in by_type.items()) or "| none | 0 |"
    reopened_rows = "\n".join(f"- `{gap_id}`" for gap_id in reopened) or "- None."
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

## Required BA Action

Review impacted specs, backlog, acceptance criteria, and decisions before marking the change as applied.
"""
