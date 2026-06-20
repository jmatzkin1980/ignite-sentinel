from __future__ import annotations

from pathlib import Path


def repo_root() -> Path:
    return Path.cwd()


def workspace_path(project_id: str, root: Path | None = None) -> Path:
    return (root or repo_root()) / "workspaces" / project_id


def state_path(project_id: str, root: Path | None = None) -> Path:
    return workspace_path(project_id, root) / "state.json"


def graph_path(project_id: str, root: Path | None = None) -> Path:
    return workspace_path(project_id, root) / "06_traceability" / "traceability_graph.json"


def config_path(project_id: str, root: Path | None = None) -> Path:
    return workspace_path(project_id, root) / "sentinel.config.yaml"


def memory_path(project_id: str, root: Path | None = None) -> Path:
    return workspace_path(project_id, root) / "memory.lancedb" / "memory.json"


def source_manifest_path(project_id: str, root: Path | None = None) -> Path:
    return workspace_path(project_id, root) / "00_raw" / "source_manifest.json"
