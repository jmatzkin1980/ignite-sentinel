from __future__ import annotations

import re
from pathlib import Path

# IMP-243: one id grammar for every command (CLI, slash aliases and MCP tools).
PROJECT_ID_PATTERN = r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}"
_PROJECT_ID_RE = re.compile(PROJECT_ID_PATTERN, re.ASCII)
PROJECT_ID_EXAMPLE = "ACME_PORTAL"
# Windows device names cannot be used as folder names reliably (git, zip, Explorer).
_RESERVED_RE = re.compile(r"(CON|PRN|AUX|NUL|COM[0-9]|LPT[0-9])", re.IGNORECASE)


class InvalidProjectId(ValueError):
    """A PROJECT_ID that could escape workspaces/ or break file names (IMP-243)."""


def is_valid_project_id(project_id: object) -> bool:
    return (
        isinstance(project_id, str)
        and _PROJECT_ID_RE.fullmatch(project_id) is not None
        and _RESERVED_RE.fullmatch(project_id) is None
    )


def validate_project_id(project_id: object, root: Path | None = None) -> str:
    """Return ``project_id`` if it is safe, else raise ``InvalidProjectId``.

    Safe means: matches ``PROJECT_ID_PATTERN`` (letters, digits, ``_`` and ``-``,
    starting with a letter or digit, at most 64 characters) and resolves to a folder
    directly inside ``workspaces/``.
    """
    message = (
        f"invalid PROJECT_ID {project_id!r}: use 1-64 letters, digits, '_' or '-', "
        f"starting with a letter or digit (for example {PROJECT_ID_EXAMPLE})"
    )
    if not is_valid_project_id(project_id):
        raise InvalidProjectId(message)
    project_id = str(project_id)
    workspaces_dir = (root or repo_root()) / "workspaces"
    if workspace_path(project_id, root).resolve().parent != workspaces_dir.resolve():
        raise InvalidProjectId(
            f"workspace {project_id!r} resolves outside workspaces/ (a symlink or junction?); "
            "move it inside workspaces/ or remove the link"
        )
    if workspaces_dir.is_dir():
        for sibling in workspaces_dir.iterdir():
            if sibling.name != project_id and sibling.name.casefold() == project_id.casefold():
                raise InvalidProjectId(
                    f"PROJECT_ID {project_id!r} differs only in letter case from the existing workspace "
                    f"{sibling.name!r}; use {sibling.name!r} (ids are case-sensitive, Windows folders are not)"
                )
    return project_id


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
