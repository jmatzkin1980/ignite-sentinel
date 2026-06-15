from __future__ import annotations

from pathlib import Path
from typing import Any

from .ids import next_id
from .workspace import graph_path, read_json, write_json


def load_graph(project_id: str) -> dict[str, list[dict[str, Any]]]:
    return read_json(graph_path(project_id), {"nodes": [], "edges": []})


def save_graph(project_id: str, graph: dict[str, list[dict[str, Any]]]) -> None:
    write_json(graph_path(project_id), graph)


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
        if node.get("type") == artifact_type and node.get("path") == str(path.as_posix()):
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
    if edge not in graph["edges"]:
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
        rows.append(
            f"| `{edge['from']}` | {source.get('type', 'unknown')} | `{edge['to']}` | {target.get('type', 'unknown')} | {edge['relation']} | {target.get('domain', 'n/a')} | {target.get('status', 'n/a')} |"
        )
    node_rows = [
        f"| `{node['id']}` | {node.get('type', 'artifact')} | {node.get('domain', 'n/a')} | {node.get('status', 'n/a')} | `{node.get('path', '')}` |"
        for node in graph.get("nodes", [])
    ]
    matrix_path = graph_path(project_id).parent / "traceability_matrix.md"
    matrix_path.write_text(
        """# Traceability Matrix - {project_id}

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
        ),
        encoding="utf-8",
    )
    return matrix_path


def write_mermaid_graph(project_id: str) -> Path:
    graph = load_graph(project_id)
    lines = ["flowchart TD"]
    for node in graph.get("nodes", []):
        safe_id = node["id"].replace("-", "_")
        label = f"{node['id']}\\n{node.get('type', 'artifact')}"
        lines.append(f'    {safe_id}["{label}"]')
        style = mermaid_style_for_node(node)
        if style:
            lines.append(f"    style {safe_id} {style}")
    for edge in graph.get("edges", []):
        source = edge["from"].replace("-", "_")
        target = edge["to"].replace("-", "_")
        relation = edge.get("relation", "relates")
        lines.append(f"    {source} -->|{relation}| {target}")
    mermaid_path = graph_path(project_id).parent / "traceability_graph.md"
    mermaid_path.write_text("# Traceability Graph\n\n```mermaid\n" + "\n".join(lines) + "\n```\n", encoding="utf-8")
    return mermaid_path


def mermaid_style_for_node(node: dict[str, Any]) -> str:
    node_type = node.get("type", "")
    status = str(node.get("status", "")).lower()
    if node_type == "gap_report" and status == "open":
        return "fill:#ffdfba,stroke:#c2410c,stroke-width:2px"
    if node_type == "change":
        return "fill:#dbeafe,stroke:#1d4ed8,stroke-width:2px"
    if node_type in {"identity_seed_bank", "discovery_log", "lens_review", "knowledge_ledger"}:
        return "fill:#dcfce7,stroke:#15803d"
    if node_type == "backlog_readiness_audit":
        return "fill:#fef9c3,stroke:#a16207"
    return ""
