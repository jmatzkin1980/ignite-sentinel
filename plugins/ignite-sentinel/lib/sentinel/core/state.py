"""The project state, split in two (IMP-300, H18).

- ``state.json`` keeps what cannot be rebuilt: the phase, the health, the story
  lifecycle and gates, the language, privacy, ``artifact_hashes`` and the rest.
  It carries ``schema_version``.
- ``.sentinel/derived/state.json`` keeps what the runtime recomputes: gap
  counts, maturity metrics, PRD section readiness, the backlog roll-up. Deleting
  it loses nothing a command does not rebuild.
- ``.sentinel/command_log.jsonl`` keeps one line per command, append-only.

``read_state`` returns both halves merged, and ``write_state``/``update_state``
split them again, so callers see one dict as before. A 0.9.0 workspace
(``state.json`` with no ``schema_version``) is migrated once, by the first command
that opens it, after a backup to ``.sentinel/state.json.bak-0.9.0``. A
``state.json`` from a newer schema is refused (exit 3) and left untouched.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..errors import InputError
from .io import append_text, copy_file, parse_json, read_json, write_json
from .paths import command_log_path, derived_state_path, state_path, workspace_path, workspace_relative
from .time import utc_now

SCHEMA_VERSION = 1
DERIVED_KEYS = ("gap_counts", "maturity_metrics", "prd_section_readiness", "backlog_rollup")
BACKUP_NAME = "state.json.bak-0.9.0"
COMMAND_LOG_KEY = "command_log"  # 0.9.0 kept the last 25 commands inside state.json


STATE_BACKUP_NAME = "state.json.bak"  # IMP-331: the state before the last update
_ARTIFACT_DIRS = ("01_discovery", "02_requirements", "03_specs", "04_backlog", "05_quality")


def state_backup_path(workspace: Path) -> Path:
    return workspace / ".sentinel" / STATE_BACKUP_NAME


def workspace_has_artifacts(workspace: Path) -> bool:
    """IMP-331: a command has already worked in this workspace (beyond what /init creates)."""
    sentinel = workspace / ".sentinel"
    if (sentinel / "command_log.jsonl").is_file() or (sentinel / "derived" / "state.json").is_file():
        return True
    return any(
        (workspace / name).is_dir() and any(item.is_file() for item in (workspace / name).rglob("*"))
        for name in _ARTIFACT_DIRS
    )


def state_problem(workspace: Path) -> str | None:
    """IMP-331: why the state of `workspace` cannot be used, or None (also for a new workspace)."""
    path = workspace / "state.json"
    if not path.exists():
        if state_backup_path(workspace).is_file():
            return "state.json is missing; a backup is at .sentinel/state.json.bak"
        if workspace_has_artifacts(workspace):
            return "state.json is missing and there is no backup"
        return None
    try:
        data = read_json(path, None)
    except ValueError as exc:
        return f"state.json is not valid JSON ({getattr(exc, 'msg', exc)})"
    if not isinstance(data, dict):
        return "state.json is not a JSON object"
    return None


def load_durable_state(project_id: str, root: Path | None = None, *, require: bool = False) -> dict[str, Any] | None:
    """IMP-331: `state.json` as a dict, or None for a workspace that has none yet.

    A missing state is never rebuilt behind the user's back: with a backup, or on
    a workspace that already holds artifacts, it is refused (exit 3) with the way
    to restore it. A file that does not parse is refused the same way. With
    `require`, a missing state is refused even on an empty workspace.
    """
    workspace = workspace_path(project_id, root)
    path = workspace / "state.json"
    shown = f"workspaces/{project_id}/state.json"
    backup = state_backup_path(workspace)
    backup_shown = f"workspaces/{project_id}/.sentinel/{STATE_BACKUP_NAME}"
    restore = f"Copy {backup_shown} to {shown} (or restore {shown} from git), then run the command again."
    if not path.exists():
        if not workspace.is_dir():
            return None
        if backup.is_file():
            raise InputError(
                f"{shown} is missing. Sentinel will not rebuild it, because a new state would lose the "
                f"project's phase, settings and story lifecycle. The state before the last update is in {backup_shown}.",
                next_step=restore,
            )
        if workspace_has_artifacts(workspace):
            raise InputError(
                f"{shown} is missing and there is no backup ({backup_shown}). The workspace already has "
                "artifacts, so Sentinel will not invent a new state.",
                next_step=f"Restore {shown} from git or your own backup, then run the command again.",
            )
        if require:
            raise InputError(
                f"{shown} is missing and the workspace has no artifacts yet.",
                next_step=f"Run /init {project_id} to recreate it.",
            )
        return None
    try:
        data = read_json(path, None)
    except ValueError as exc:
        detail = f"{exc.msg} at line {exc.lineno}, column {exc.colno}" if hasattr(exc, "lineno") else str(exc)
        problem = f"{shown} is not valid JSON: {detail}."
    else:
        if isinstance(data, dict):
            return data
        problem = f"{shown} is not a JSON object."
    if backup.is_file():
        raise InputError(
            f"{problem} The state before the last update is in {backup_shown}.",
            next_step=f"Keep the broken file aside if you want to inspect it, then {restore[0].lower()}{restore[1:]}",
        )
    raise InputError(
        f"{problem} There is no backup ({backup_shown}).",
        next_step=f"Fix the JSON by hand or restore {shown} from git or your own backup.",
    )


def read_state(project_id: str, default: Any | None = None, root: Path | None = None) -> Any:
    durable = load_durable_state(project_id, root)
    if durable is None:
        return {} if default is None else default
    derived = read_json(derived_state_path(project_id, root), {})
    return {**durable, **derived} if isinstance(derived, dict) else durable


def read_workspace_state(workspace: Path) -> dict[str, Any]:
    """Both halves of the state of the workspace folder `workspace` (no project id or cwd needed)."""
    durable = read_json(workspace / "state.json", {})
    derived = read_json(workspace / ".sentinel" / "derived" / "state.json", {})
    durable = durable if isinstance(durable, dict) else {}
    return {**durable, **derived} if isinstance(derived, dict) else durable


def _check_version(state: dict[str, Any], path: Path) -> None:
    version = state.get("schema_version")
    if version is None or version == SCHEMA_VERSION:
        return
    if not isinstance(version, int) or isinstance(version, bool) or version < 1:
        raise InputError(f"{path.as_posix()} has an invalid schema_version: {version!r}.")
    if version > SCHEMA_VERSION:
        raise InputError(
            f"{path.as_posix()} uses state schema {version}; this Sentinel reads up to {SCHEMA_VERSION}. "
            "The file was left untouched.",
            next_step="Upgrade Sentinel to the version that wrote this workspace.",
        )


def write_state(project_id: str, state: dict[str, Any], root: Path | None = None) -> None:
    path = state_path(project_id, root)
    current = load_durable_state(project_id, root)
    if current is not None:
        _check_version(current, path)  # never overwrite a newer schema
        # IMP-331: one rolling copy of the state before this update, to restore from.
        copy_file(path, state_backup_path(workspace_path(project_id, root)))
    durable = {
        key: _relative_paths(project_id, key, value, root)
        for key, value in state.items()
        if key not in DERIVED_KEYS and key not in (COMMAND_LOG_KEY, "schema_version")
    }
    write_json(path, {"schema_version": SCHEMA_VERSION, **durable})
    derived = {key: state[key] for key in DERIVED_KEYS if key in state}
    derived_path = derived_state_path(project_id, root)
    if (derived or derived_path.exists()) and read_json(derived_path, None) != derived:
        write_json(derived_path, derived)


def _relative_paths(project_id: str, key: str, value: Any, root: Path | None) -> Any:
    """IMP-301: the artifact pointers in the state stay relative to the workspace."""
    if key == "artifacts" and isinstance(value, dict):
        return {name: workspace_relative(project_id, item, root) if isinstance(item, str) else item for name, item in value.items()}
    if key.startswith("last_") and key.endswith("_source") and isinstance(value, str):
        return workspace_relative(project_id, value, root)
    return value


def update_state(project_id: str, **changes: Any) -> dict[str, Any]:
    state = read_state(project_id, {})
    state.update(changes)
    state["updated_at"] = utc_now()
    write_state(project_id, state)
    return state


def append_command_log(project_id: str, entry: dict[str, Any], root: Path | None = None) -> None:
    path = command_log_path(project_id, root)
    line = json.dumps(entry, ensure_ascii=False) + "\n"
    if path.is_file() and path.stat().st_size and not path.read_bytes().endswith(b"\n"):
        line = "\n" + line  # close a line torn by a crash, so this entry stays whole
    append_text(path, line, newline="\n")


def read_command_log(project_id: str, limit: int | None = None, root: Path | None = None) -> list[dict[str, Any]]:
    path = command_log_path(project_id, root)
    if not path.is_file():
        return []
    entries: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            entry = parse_json(line)
        except ValueError:
            continue  # a torn last line from a crash; the rest stays readable
        if isinstance(entry, dict):
            entries.append(entry)
    return entries[-limit:] if limit else entries


def _relative_to_workspace(value: Any, workspace: Path) -> Any:
    if not isinstance(value, str) or not value:
        return value
    candidate = Path(value)
    if not candidate.is_absolute():
        return value
    for base in (workspace, workspace.resolve()):
        try:
            return candidate.relative_to(base).as_posix()
        except ValueError:
            continue
    return value


def migrate_state(project_id: str, root: Path | None = None) -> dict[str, Any] | None:
    """Bring a workspace's state to the current schema. Returns what was done, or None."""
    path = state_path(project_id, root)
    if not path.is_file():
        return None
    state = load_durable_state(project_id, root)  # IMP-331: a broken file is refused by name
    if state is None:
        return None
    _check_version(state, path)
    if state.get("schema_version") == SCHEMA_VERSION:
        return None
    workspace = workspace_path(project_id, root)
    backup = workspace / ".sentinel" / BACKUP_NAME
    if not backup.exists():
        copy_file(path, backup)
    log = state.pop(COMMAND_LOG_KEY, None)
    if isinstance(log, list) and not command_log_path(project_id, root).exists():
        for entry in log:
            if isinstance(entry, dict):
                append_command_log(project_id, entry, root)
    if "last_export" in state:
        state["last_export"] = _relative_to_workspace(state["last_export"], workspace)
    state["migrated_from"] = "0.9.0"
    write_state(project_id, state, root)
    migrate_paths(project_id, root)
    return {"migrated_from": "0.9.0", "backup": backup.as_posix()}


def migrate_paths(project_id: str, root: Path | None = None) -> list[str]:
    """IMP-301: rewrite the absolute paths of the graph and the memory relative to the workspace.

    Paths under the workspace's current folder, or under the folder it was moved
    or cloned from, become relative. Paths outside it stay as they are; /health
    reports them. Returns the files rewritten.
    """
    from ..traceability import flush_graph_saves

    flush_graph_saves()  # IMP-345: this rewrites the graph file directly; no deferred copy may hide it
    workspace = workspace_path(project_id, root)
    memory_dir = workspace / "memory.lancedb"
    targets = (
        (workspace / "06_traceability" / "traceability_graph.json", ("nodes",), ("path",)),
        (memory_dir / "memory.json", ("artifacts", "chunks"), ("source_path", "file_path")),
        (memory_dir / "artifact_manifest.json", ("artifacts",), ("source_path", "file_path")),
    )
    rewritten: list[str] = []
    for path, lists, keys in targets:
        data = read_json(path, None)
        if not isinstance(data, dict):
            continue
        changed = False
        for list_key in lists:
            for item in data.get(list_key) or []:
                if not isinstance(item, dict):
                    continue
                for key in keys:
                    value = item.get(key)
                    if isinstance(value, str) and value:
                        relative = workspace_relative(project_id, value, root)
                        if relative != value:
                            item[key] = relative
                            changed = True
        if changed:
            write_json(path, data)
            rewritten.append(path.relative_to(workspace).as_posix())
    return rewritten
