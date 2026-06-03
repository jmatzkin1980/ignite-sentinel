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


def write_traceability_matrix(project_id: str) -> Path:
    graph = load_graph(project_id)
    rows = [
        f"| `{edge['from']}` | `{edge['to']}` | {edge['relation']} |"
        for edge in graph.get("edges", [])
    ]
    matrix_path = graph_path(project_id).parent / "traceability_matrix.md"
    matrix_path.write_text(
        "# Traceability Matrix - {project_id}\n\n| Source | Target | Relation |\n| --- | --- | --- |\n{rows}\n".format(
            project_id=project_id,
            rows="\n".join(rows) if rows else "| N/A | N/A | No trace edges found. |",
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
    for edge in graph.get("edges", []):
        source = edge["from"].replace("-", "_")
        target = edge["to"].replace("-", "_")
        relation = edge.get("relation", "relates")
        lines.append(f"    {source} -->|{relation}| {target}")
    mermaid_path = graph_path(project_id).parent / "traceability_graph.md"
    mermaid_path.write_text("# Traceability Graph\n\n```mermaid\n" + "\n".join(lines) + "\n```\n", encoding="utf-8")
    return mermaid_path
