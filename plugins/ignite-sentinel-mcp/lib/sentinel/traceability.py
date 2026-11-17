from __future__ import annotations

import copy
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from .ids import next_id
from .workspace import graph_path, read_json, write_json
from .core.io import write_text
from .core.paths import workspace_absolute, workspace_citation, workspace_relative


# IMP-345: while > 0, save_graph() keeps the graph in memory and the outermost
# deferred_graph_saves() writes it once on exit. Keyed by the graph file's path.
_DEFER_DEPTH = 0
_DEFERRED: dict[str, dict[str, Any]] = {}  # stored form (relative paths) of each graph read or saved
_DIRTY: set[str] = set()


def _graph_key(project_id: str) -> str:
    return str(graph_path(project_id).resolve())


@contextmanager
def deferred_graph_saves() -> Iterator[None]:
    """IMP-345: write each changed graph once at the end of a command, not per node or edge.

    Reads inside the block see every change made in it. The graph is written on
    exit even when the block raises: artifacts written before the error keep
    their nodes, exactly as when every change was saved at once. Only a process
    killed mid-command leaves the graph behind its artifacts; rerunning the
    command restores the nodes (they are upserted by path).
    """
    global _DEFER_DEPTH
    _DEFER_DEPTH += 1
    try:
        yield
    finally:
        _DEFER_DEPTH -= 1
        if not _DEFER_DEPTH:
            flush_graph_saves()


def flush_graph_saves() -> None:
    """IMP-345: write every graph changed in a deferred block now and forget the cached copies.

    Called on exit of the outermost block, and by code that reads or rewrites the
    graph file directly while a block may be open.
    """
    try:
        for key in sorted(_DIRTY):
            write_json(Path(key), _DEFERRED[key])
    finally:
        _DIRTY.clear()
        _DEFERRED.clear()


def _read_stored_graph(project_id: str) -> dict[str, Any]:
    if not _DEFER_DEPTH:
        return read_json(graph_path(project_id), {"nodes": [], "edges": []})
    key = _graph_key(project_id)
    if key not in _DEFERRED:
        _DEFERRED[key] = read_json(graph_path(project_id), {"nodes": [], "edges": []})
    return copy.deepcopy(_DEFERRED[key])


def load_graph(project_id: str) -> dict[str, list[dict[str, Any]]]:
    """The graph, with each node path resolved against the workspace's current folder.

    IMP-301: the file stores paths relative to the workspace, so a moved or cloned
    workspace still finds its artifacts; callers keep seeing absolute paths.
    """
    graph = _read_stored_graph(project_id)
    nodes = []
    for node in graph.get("nodes", []):
        if node.get("path"):
            node = {**node, "path": workspace_absolute(project_id, node["path"])}
        nodes.append(node)
    return {**graph, "nodes": nodes, "edges": list(graph.get("edges", []))}


def save_graph(project_id: str, graph: dict[str, list[dict[str, Any]]]) -> None:
    stored = relative_graph(project_id, graph)
    if _DEFER_DEPTH:
        key = _graph_key(project_id)
        _DEFERRED[key] = copy.deepcopy(stored)
        _DIRTY.add(key)
        return
    write_json(graph_path(project_id), stored)


def relative_graph(project_id: str, graph: dict[str, Any]) -> dict[str, Any]:
    """IMP-301: `graph` as stored, each node path relative to the workspace when it lies inside."""
    nodes = []
    for node in graph.get("nodes", []):
        if node.get("path"):
            node = {**node, "path": workspace_relative(project_id, node["path"])}
        nodes.append(node)
    return {**graph, "nodes": nodes}


def _same_path(project_id: str, stored: object, path: Path) -> bool:
    return workspace_relative(project_id, stored) == workspace_relative(project_id, path.as_posix())


def existing_ids(graph: dict[str, list[dict[str, Any]]]) -> list[str]:
    return [node["id"] for node in graph.get("nodes", [])]


def add_node(
    project_id: str,
    prefix: str,
    artifact_type: str,
    path: Path,
    title: str,
    status: str = "active",
    domain: str = "product",
) -> str:
    graph = load_graph(project_id)
    # Upsert: regenerating an artifact at the same path with the same type keeps
    # its stable trace ID instead of accumulating duplicate nodes (IMP-009).
    for node in graph["nodes"]:
        if node.get("type") == artifact_type and _same_path(project_id, node.get("path"), path):
            # IMP-330: rewrite the graph only when the node actually changed.
            if (node.get("title"), node.get("status"), node.get("domain")) != (title, status, domain):
                node["title"] = title
                node["status"] = status
                node["domain"] = domain
                save_graph(project_id, graph)
            return node["id"]
    node_id = next_id(prefix, existing_ids(graph))
    graph["nodes"].append(
        {
            "id": node_id,
            "type": artifact_type,
            "path": str(path.as_posix()),
            "title": title,
            "status": status,
            "domain": domain,
        }
    )
    save_graph(project_id, graph)
    return node_id


def upsert_node(
    project_id: str,
    node_id: str,
    artifact_type: str,
    path: Path,
    title: str,
    status: str = "active",
    domain: str = "product",
) -> str:
    graph = load_graph(project_id)
    path_value = str(path.as_posix())
    for node in graph["nodes"]:
        if node.get("id") == node_id:
            # IMP-330: rewrite the graph only when the node actually changed.
            unchanged = (
                node.get("type") == artifact_type
                and _same_path(project_id, node.get("path"), path)
                and (node.get("title"), node.get("status"), node.get("domain")) == (title, status, domain)
            )
            if not unchanged:
                node["type"] = artifact_type
                node["path"] = path_value
                node["title"] = title
                node["status"] = status
                node["domain"] = domain
                save_graph(project_id, graph)
            return node_id
    graph["nodes"].append(
        {
            "id": node_id,
            "type": artifact_type,
            "path": path_value,
            "title": title,
            "status": status,
            "domain": domain,
        }
    )
    save_graph(project_id, graph)
    return node_id


def add_edge(project_id: str, source_id: str, target_id: str, relation: str) -> None:
    graph = load_graph(project_id)
    edge = {"from": source_id, "to": target_id, "relation": relation}
    if edge in graph["edges"]:
        return  # IMP-330: the edge is already there; do not rewrite the graph
    graph["edges"].append(edge)
    save_graph(project_id, graph)


def nodes_by_type(project_id: str, artifact_type: str) -> list[dict[str, Any]]:
    graph = load_graph(project_id)
    return [node for node in graph.get("nodes", []) if node.get("type") == artifact_type]


def parents_of(project_id: str, node_id: str) -> list[str]:
    graph = load_graph(project_id)
    return [edge["from"] for edge in graph.get("edges", []) if edge.get("to") == node_id]


def children_of(project_id: str, node_id: str) -> list[str]:
    graph = load_graph(project_id)
    return [edge["to"] for edge in graph.get("edges", []) if edge.get("from") == node_id]


def descendants_of(project_id: str, node_id: str) -> list[str]:
    graph = load_graph(project_id)
    seen: set[str] = set()

    def walk(current: str) -> None:
        for edge in graph.get("edges", []):
            if edge.get("from") != current:
                continue
            target = edge.get("to")
            if not target or target in seen:
                continue
            seen.add(target)
            walk(target)

    walk(node_id)
    return sorted(seen)


def impact_analysis(project_id: str, target_node: str) -> dict[str, object]:
    graph = load_graph(project_id)
    node_lookup = {node["id"]: node for node in graph.get("nodes", [])}
    impacted = descendants_of(project_id, target_node)
    return {
        "target": target_node,
        "impacted": impacted,
        "count": len(impacted),
        "by_type": count_by_type(impacted, node_lookup),
    }


def count_by_type(node_ids: list[str], node_lookup: dict[str, dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for node_id in node_ids:
        node_type = node_lookup.get(node_id, {}).get("type", "unknown")
        counts[node_type] = counts.get(node_type, 0) + 1
    return counts


def write_traceability_matrix(project_id: str) -> Path:
    graph = load_graph(project_id)
    node_lookup = {node["id"]: node for node in graph.get("nodes", [])}
    rows = []
    for edge in graph.get("edges", []):
        source = node_lookup.get(edge["from"], {})
        target = node_lookup.get(edge["to"], {})
        relation = edge["relation"]
        if edge.get("suspicious"):
            relation = f"{relation} (SUSPICIOUS: {edge.get('suspicion_reason', 'review required')})"
        rows.append(
            f"| `{edge['from']}` | {source.get('type', 'unknown')} | `{edge['to']}` | {target.get('type', 'unknown')} | {relation} | {target.get('domain', 'n/a')} | {target.get('status', 'n/a')} |"
        )
    node_rows = [
        f"| `{node['id']}` | {node.get('type', 'artifact')} | {node.get('domain', 'n/a')} | {node.get('status', 'n/a')} | `{workspace_citation(project_id, node.get('path', ''))}` |"
        for node in graph.get("nodes", [])
    ]
    matrix_path = graph_path(project_id).parent / "traceability_matrix.md"
    write_text(matrix_path, """# Traceability Matrix - {project_id}

This matrix supports the Sentinel vNext golden thread. Source files remain authoritative; LanceDB memory is retrieval only.

## Edge Matrix

| Source | Source Type | Target | Target Type | Relation | Target Domain | Target Status |
| --- | --- | --- | --- | --- | --- | --- |
{rows}

## Artifact Registry

| Node ID | Type | Domain | Status | Path |
| --- | --- | --- | --- | --- |
{node_rows}

## Coverage Review

- Requirements should connect to discovery, specs, backlog, acceptance criteria, tests, changes, and audits as applicable.
- User stories without requirement/spec ancestry should be treated as health risks.
- Changes should point to impacted downstream nodes.
""".format(
            project_id=project_id,
            rows="\n".join(rows) if rows else "| N/A | N/A | N/A | N/A | No trace edges found. | N/A | N/A |",
            node_rows="\n".join(node_rows) if node_rows else "| N/A | N/A | N/A | N/A | N/A |",
        ))
    return matrix_path


def write_mermaid_graph(project_id: str) -> Path:
    graph = load_graph(project_id)
    lines = ["flowchart TD"]
    for node in graph.get("nodes", []):
        safe_id = node["id"].replace("-", "_")
        # Mermaid does not interpret `\n` inside node labels; it needs `<br/>`
        # (rendered via htmlLabels) or the line break shows up literally.
        label = f"{node['id']}<br/>{node.get('type', 'artifact')}"
        lines.append(f'    {safe_id}["{label}"]')
        style = mermaid_style_for_node(node)
        if style:
            lines.append(f"    style {safe_id} {style}")
    for edge in graph.get("edges", []):
        source = edge["from"].replace("-", "_")
        target = edge["to"].replace("-", "_")
        relation = edge.get("relation", "relates")
        # Keep the mermaid edge label in parity with the matrix annotation
        # (write_traceability_matrix): a suspicious edge must carry its warning
        # here too, else the graph shows a plain arrow and loses the signal.
        # Quote the label so the parentheses/colon parse cleanly in mermaid.
        if edge.get("suspicious"):
            reason = edge.get("suspicion_reason", "review required")
            lines.append(f'    {source} -->|"{relation} (SUSPICIOUS: {reason})"| {target}')
        else:
            lines.append(f"    {source} -->|{relation}| {target}")
    mermaid_path = graph_path(project_id).parent / "traceability_graph.md"
    write_text(mermaid_path, "# Traceability Graph\n\n```mermaid\n" + "\n".join(lines) + "\n```\n")
    return mermaid_path


def mermaid_style_for_node(node: dict[str, Any]) -> str:
    node_type = node.get("type", "")
    status = str(node.get("status", "")).lower()
    if node_type == "gap_report" and status == "open":
        return "fill:#ffdfba,stroke:#c2410c,stroke-width:2px"
    if node_type == "change":
        return "fill:#dbeafe,stroke:#1d4ed8,stroke-width:2px"
    if node_type in {"identity_seed_bank", "discovery_log", "lens_review", "knowledge_ledger", "assumption_register", "scrutiny_report"}:
        return "fill:#dcfce7,stroke:#15803d"
    if node_type == "backlog_readiness_audit":
        return "fill:#fef9c3,stroke:#a16207"
    # F-TRACE-3 (H10 IMP-208 parity audit): the audit confirmed the residual was
    # the *core chain* rendering unstyled -- exactly these 8 node types, the most
    # important ones, showed as bare grey boxes while peripheral artifacts were
    # coloured. Give the spine a single calm fill so it reads at a glance; the
    # audit did not flag other types, so anything else keeps the mermaid default.
    if node_type in {
        "requirement",
        "requirement_unit",
        "prd",
        "spec",
        "epic",
        "user_story",
        "acceptance_criteria",
        "test_case",
    }:
        return "fill:#f1f5f9,stroke:#475569"
    return ""
