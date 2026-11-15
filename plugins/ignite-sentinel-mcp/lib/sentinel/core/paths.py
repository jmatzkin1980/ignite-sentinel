from __future__ import annotations

import os
import re
from contextlib import suppress
from functools import lru_cache
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


# A drive path (C:/ or C:\) or a UNC path (//server/share); a rooted path with no
# drive (\x) is relative on Windows, as PureWindowsPath says.
_WINDOWS_ABSOLUTE_RE = re.compile(r"[A-Za-z]:[\\/]|[\\/]{2}[^\\/]+[\\/][^\\/]+")
_CASE_INSENSITIVE_PATHS = os.name == "nt"


def is_absolute_path(value: str) -> bool:
    """True for an absolute path in either OS's form (a Windows path read on Linux too).

    The same answer as ``PurePosixPath(v).is_absolute() or PureWindowsPath(v).is_absolute()``,
    without building two path objects: it runs for every stored path (IMP-304).
    """
    return value.startswith("/") or _WINDOWS_ABSOLUTE_RE.match(value) is not None


@lru_cache(maxsize=256)
def _workspace_roots(project_id: str, root: str) -> tuple[str, tuple[str, ...]]:
    """The workspace folder as written, and every form of it to strip, longest first.

    IMP-304: resolving the folder is a filesystem call; doing it per stored path
    made path conversion a third of a whole flow on Windows. It is done once per
    workspace root and process.
    """
    base = Path(root) / "workspaces" / project_id
    forms = {base.as_posix()}
    with suppress(OSError):
        forms.add(base.resolve().as_posix())
    return base.as_posix(), tuple(sorted(forms, key=len, reverse=True))


def _roots(project_id: str, root: Path | None) -> tuple[str, tuple[str, ...]]:
    return _workspace_roots(project_id, str(root or repo_root()))


def _strip_prefix(text: str, head: str) -> str | None:
    start = text[: len(head)]
    if start == head or (_CASE_INSENSITIVE_PATHS and start.casefold() == head.casefold()):
        return text[len(head):]
    return None


def workspace_relative(project_id: str, value: object, root: Path | None = None) -> str:
    """IMP-301: ``value`` as a posix path relative to the workspace, when it lies inside it.

    A path written by another copy of the same workspace (moved or cloned: an
    absolute path with a ``workspaces/<id>/`` segment, or one relative to the repo
    root) maps too. Anything else comes back unchanged, in posix form.
    """
    text = str(value or "").replace("\\", "/")
    if not text:
        return text
    prefix = f"workspaces/{project_id}/"
    if not is_absolute_path(text):
        text = text[2:] if text.startswith("./") else text
        return text[len(prefix):] if text.startswith(prefix) else text
    for form in _roots(project_id, root)[1]:
        relative = _strip_prefix(text, form + "/")
        if relative is not None:
            return relative or "."
        if _strip_prefix(text, form) == "":
            return "."
    # The last segment wins: a release mirror nests `workspaces/<id>/` inside the workspace.
    matches = list(re.finditer("/" + re.escape(prefix), text, re.IGNORECASE))
    return text[matches[-1].end():] if matches else text


def workspace_absolute(project_id: str, value: object, root: Path | None = None) -> str:
    """The posix path ``value`` names, read against the workspace's current folder (IMP-304)."""
    relative = workspace_relative(project_id, value, root)
    if is_absolute_path(relative):
        return relative
    base = _roots(project_id, root)[0]
    return base if relative in ("", ".") else f"{base}/{relative}"


def workspace_citation(project_id: str, value: object, root: Path | None = None) -> str:
    """IMP-308: how an artifact cites a path: ``workspaces/<id>/<relative>``, from the repo root.

    The same text wherever the workspace lives, and openable from the repo root, where
    agents and people work. A path outside the workspace is kept as it is.
    """
    relative = workspace_relative(project_id, value, root)
    if not relative or is_absolute_path(relative):
        return relative
    base = f"workspaces/{project_id}"
    return base if relative == "." else f"{base}/{relative}"


def resolve_in_workspace(project_id: str, value: object, root: Path | None = None) -> Path:
    """IMP-301: the path ``value`` names, read against the workspace's current folder."""
    return Path(workspace_absolute(project_id, value, root))


def state_path(project_id: str, root: Path | None = None) -> Path:
    return workspace_path(project_id, root) / "state.json"


def derived_state_path(project_id: str, root: Path | None = None) -> Path:
    """IMP-300: the regenerable part of the state (counts, metrics, roll-ups)."""
    return workspace_path(project_id, root) / ".sentinel" / "derived" / "state.json"


def command_log_path(project_id: str, root: Path | None = None) -> Path:
    """IMP-300: one JSON line per command, append-only."""
    return workspace_path(project_id, root) / ".sentinel" / "command_log.jsonl"


def graph_path(project_id: str, root: Path | None = None) -> Path:
    return workspace_path(project_id, root) / "06_traceability" / "traceability_graph.json"


def config_path(project_id: str, root: Path | None = None) -> Path:
    return workspace_path(project_id, root) / "sentinel.config.yaml"


def memory_path(project_id: str, root: Path | None = None) -> Path:
    return workspace_path(project_id, root) / "memory.lancedb" / "memory.json"


def source_manifest_path(project_id: str, root: Path | None = None) -> Path:
    return workspace_path(project_id, root) / "00_raw" / "source_manifest.json"
