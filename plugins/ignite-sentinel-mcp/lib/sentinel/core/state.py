from __future__ import annotations

from typing import Any

from .io import read_json, write_json
from .paths import state_path
from .time import utc_now


def read_state(project_id: str, default: Any | None = None) -> Any:
    return read_json(state_path(project_id), {} if default is None else default)


def write_state(project_id: str, state: dict[str, Any]) -> None:
    write_json(state_path(project_id), state)


def update_state(project_id: str, **changes: Any) -> dict[str, Any]:
    state = read_state(project_id, {})
    state.update(changes)
    state["updated_at"] = utc_now()
    write_state(project_id, state)
    return state
