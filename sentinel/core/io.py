from __future__ import annotations

import json
import warnings
from hashlib import sha256
from pathlib import Path
from typing import Any


_READ_SNAPSHOTS: dict[Path, str | None] = {}


def _normalized_path(path: Path) -> Path:
    return path.expanduser().resolve(strict=False)


def _file_hash(path: Path) -> str | None:
    if not path.exists():
        return None
    return sha256(path.read_bytes()).hexdigest()


def _remember_snapshot(path: Path) -> None:
    _READ_SNAPSHOTS[_normalized_path(path)] = _file_hash(path)


def _warn_if_changed(path: Path) -> None:
    normalized = _normalized_path(path)
    if normalized not in _READ_SNAPSHOTS:
        return
    expected = _READ_SNAPSHOTS[normalized]
    actual = _file_hash(path)
    if expected != actual:
        warnings.warn(
            f"Optimistic write conflict detected for {path.as_posix()}: artifact changed since last read.",
            RuntimeWarning,
            stacklevel=2,
        )


def read_json(path: Path, default: Any | None = None) -> Any:
    if not path.exists():
        _remember_snapshot(path)
        return default
    data = json.loads(path.read_text(encoding="utf-8"))
    _remember_snapshot(path)
    return data


def read_json_resource(resource: Any, default: Any | None = None) -> Any:
    try:
        return json.loads(resource.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    _warn_if_changed(path)
    tmp_path = path.with_name(f".{path.name}.tmp")
    tmp_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp_path.replace(path)
    _remember_snapshot(path)


def append_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    _warn_if_changed(path)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(text)
    _remember_snapshot(path)
