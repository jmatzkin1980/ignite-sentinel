from __future__ import annotations

from pathlib import Path
from typing import Any

from .. import traceability


def load_graph(project_id: str) -> dict[str, list[dict[str, Any]]]:
    return traceability.load_graph(project_id)


def save_graph(project_id: str, graph: dict[str, list[dict[str, Any]]]) -> None:
    traceability.save_graph(project_id, graph)


def add_node(
    project_id: str,
    prefix: str,
    artifact_type: str,
    path: Path,
    title: str,
    status: str = "active",
    domain: str = "product",
) -> str:
    return traceability.add_node(project_id, prefix, artifact_type, path, title, status=status, domain=domain)


def upsert_node(
    project_id: str,
    node_id: str,
    artifact_type: str,
    path: Path,
    title: str,
    status: str = "active",
    domain: str = "product",
) -> str:
    return traceability.upsert_node(project_id, node_id, artifact_type, path, title, status=status, domain=domain)


def add_edge(project_id: str, source_id: str, target_id: str, relation: str) -> None:
    traceability.add_edge(project_id, source_id, target_id, relation)


def nodes_by_type(project_id: str, artifact_type: str) -> list[dict[str, Any]]:
    return traceability.nodes_by_type(project_id, artifact_type)


def parents_of(project_id: str, node_id: str) -> list[str]:
    return traceability.parents_of(project_id, node_id)


def children_of(project_id: str, node_id: str) -> list[str]:
    return traceability.children_of(project_id, node_id)


def descendants_of(project_id: str, node_id: str) -> list[str]:
    return traceability.descendants_of(project_id, node_id)


def count_by_type(node_ids: list[str], node_lookup: dict[str, dict[str, Any]]) -> dict[str, int]:
    return traceability.count_by_type(node_ids, node_lookup)
