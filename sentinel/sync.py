from __future__ import annotations

import shutil
from pathlib import Path

from .discovery import detect_gaps
from .memory import ContextBroker, reindex_workspace
from .traceability import add_edge, add_node, children_of, load_graph
from .workspace import update_state, workspace_path


def sync_change(project_id: str, source: Path, note: str = "") -> dict[str, object]:
    base = workspace_path(project_id)
    if not base.exists():
        raise RuntimeError(f"Workspace not found: {project_id}")

    target = base / "07_changes" / f"{source.stem}.md"
    shutil.copyfile(source, target)
    text = source.read_text(encoding="utf-8")
    change_id = add_node(project_id, "CHG", "change", target, source.stem, status="pending", domain="product")

    affected = impacted_nodes(project_id)
    for node_id in affected:
        add_edge(project_id, change_id, node_id, "may_impact")

    gaps = detect_gaps(text)
    impact_path = base / "07_changes" / f"{source.stem}_impact_report.md"
    impact_path.write_text(render_impact(project_id, change_id, affected, gaps, note), encoding="utf-8")
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
    reindex_workspace(project_id)
    update_state(
        project_id,
        phase="change_synced",
        health="DIRTY" if gaps else "CLEAN",
        last_change_id=change_id,
    )
    return {"change_id": change_id, "impact_report_id": impact_id, "affected": affected, "gaps": gaps}


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


def render_impact(project_id: str, change_id: str, affected: list[str], gaps: list[dict[str, str]], note: str) -> str:
    affected_rows = "\n".join(f"- `{node_id}`" for node_id in affected) or "- No existing downstream nodes found."
    gap_rows = "\n".join(
        f"- `{gap['id']}` ({gap['severity']}): {gap['description']}" for gap in gaps
    ) or "- No new deterministic gaps detected."
    note_text = note or "No operator note provided."
    return f"""# Change Impact Report - {project_id}

- Change: `{change_id}`
- Status: `pending_review`

## Operator Note

{note_text}

## Potentially Affected Nodes

{affected_rows}

## New Gaps Detected In Change Input

{gap_rows}

## Required BA Action

Review impacted specs, backlog, acceptance criteria, and decisions before marking the change as applied.
"""
