from __future__ import annotations

from pathlib import Path

from .ids import prefix_for_node_type
from .traceability import load_graph
from .workspace import state_path, workspace_path


def validate_project(project_id: str) -> dict[str, object]:
    findings: list[str] = []
    base = workspace_path(project_id)
    if not base.exists():
        return {"verdict": "INVALID", "findings": [f"Workspace does not exist: {project_id}"]}
    if not state_path(project_id).exists():
        findings.append("Missing state.json.")
    config = base / "sentinel.config.yaml"
    if not config.exists():
        findings.append("Missing sentinel.config.yaml.")

    graph = load_graph(project_id)
    node_ids = set()
    for node in graph.get("nodes", []):
        node_id = node.get("id", "")
        node_type = node.get("type", "")
        expected_prefix = prefix_for_node_type(node_type)
        if expected_prefix and not node_id.startswith(f"{expected_prefix}-"):
            findings.append(f"{node_id} prefix does not match type {node_type}.")
        if node_id in node_ids:
            findings.append(f"Duplicate node id: {node_id}.")
        node_ids.add(node_id)
        path_value = node.get("path")
        if path_value and not resolve_path(base, path_value).exists():
            findings.append(f"{node_id} points to missing artifact: {path_value}.")

    for edge in graph.get("edges", []):
        if edge.get("from") not in node_ids:
            findings.append(f"Edge source missing: {edge.get('from')}.")
        if edge.get("to") not in node_ids:
            findings.append(f"Edge target missing: {edge.get('to')}.")

    verdict = "VALID" if not findings else "INVALID"
    return {"verdict": verdict, "findings": findings}


def resolve_path(base: Path, path_value: str) -> Path:
    path = Path(path_value)
    if path.is_absolute():
        return path
    candidate = Path.cwd() / path
    if candidate.exists():
        return candidate
    return base / path
