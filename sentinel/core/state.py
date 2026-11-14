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
from .paths import command_log_path, derived_state_path, state_path, workspace_path
from .time import utc_now

SCHEMA_VERSION = 1
DERIVED_KEYS = ("gap_counts", "maturity_metrics", "prd_section_readiness", "backlog_rollup")
BACKUP_NAME = "state.json.bak-0.9.0"
COMMAND_LOG_KEY = "command_log"  # 0.9.0 kept the last 25 commands inside state.json


def read_state(project_id: str, default: Any | None = None, root: Path | None = None) -> Any:
    durable = read_json(state_path(project_id, root), None)
    if not isinstance(durable, dict):
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
    current = read_json(path, None)
    if isinstance(current, dict):
        _check_version(current, path)  # never overwrite a newer schema
    durable = {
        key: value
        for key, value in state.items()
        if key not in DERIVED_KEYS and key not in (COMMAND_LOG_KEY, "schema_version")
    }
    write_json(path, {"schema_version": SCHEMA_VERSION, **durable})
    derived = {key: state[key] for key in DERIVED_KEYS if key in state}
    derived_path = derived_state_path(project_id, root)
    if (derived or derived_path.exists()) and read_json(derived_path, None) != derived:
        write_json(derived_path, derived)


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
    state = read_json(path, None)
    if not isinstance(state, dict):
        raise InputError(f"{path.as_posix()} is not a JSON object.")
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
    return {"migrated_from": "0.9.0", "backup": backup.as_posix()}
