from __future__ import annotations

import json
import warnings
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
from typing import Any


_READ_SNAPSHOTS: dict[Path, str | None] = {}
_JSON_READ_CACHE: dict[Path, tuple[int, int, str, Any]] = {}
_JSON_READ_CACHE_HITS = 0
_JSON_READ_CACHE_MISSES = 0


def _normalized_path(path: Path) -> Path:
    return path.expanduser().resolve(strict=False)


def _file_hash(path: Path) -> str | None:
    if not path.exists():
        return None
    return sha256(path.read_bytes()).hexdigest()


def _remember_snapshot(path: Path) -> None:
    _READ_SNAPSHOTS[_normalized_path(path)] = _file_hash(path)


def _remember_snapshot_hash(path: Path, digest: str | None) -> None:
    _READ_SNAPSHOTS[_normalized_path(path)] = digest


def _json_cache_signature(path: Path) -> tuple[int, int] | None:
    if not path.exists():
        return None
    stat = path.stat()
    return stat.st_mtime_ns, stat.st_size


def clear_read_json_cache() -> None:
    global _JSON_READ_CACHE_HITS, _JSON_READ_CACHE_MISSES
    _JSON_READ_CACHE.clear()
    _JSON_READ_CACHE_HITS = 0
    _JSON_READ_CACHE_MISSES = 0


def read_json_cache_stats() -> dict[str, int]:
    return {
        "entries": len(_JSON_READ_CACHE),
        "hits": _JSON_READ_CACHE_HITS,
        "misses": _JSON_READ_CACHE_MISSES,
    }


def _invalidate_json_cache(path: Path) -> None:
    _JSON_READ_CACHE.pop(_normalized_path(path), None)


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
    global _JSON_READ_CACHE_HITS, _JSON_READ_CACHE_MISSES
    normalized = _normalized_path(path)
    signature = _json_cache_signature(path)
    cached = _JSON_READ_CACHE.get(normalized)
    if signature and cached and cached[0] == signature[0] and cached[1] == signature[1]:
        _JSON_READ_CACHE_HITS += 1
        _remember_snapshot_hash(path, cached[2])
        return deepcopy(cached[3])

    _JSON_READ_CACHE_MISSES += 1
    if not path.exists():
        _remember_snapshot(path)
        return deepcopy(default)
    raw = path.read_bytes()
    digest = sha256(raw).hexdigest()
    data = json.loads(raw.decode("utf-8"))
    _JSON_READ_CACHE[normalized] = (signature[0], signature[1], digest, data)
    _remember_snapshot_hash(path, digest)
    return deepcopy(data)


def read_json_resource(resource: Any, default: Any | None = None) -> Any:
    try:
        return json.loads(resource.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    _warn_if_changed(path)
    _invalidate_json_cache(path)
    tmp_path = path.with_name(f".{path.name}.tmp")
    tmp_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp_path.replace(path)
    _remember_snapshot(path)


def append_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    _warn_if_changed(path)
    _invalidate_json_cache(path)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(text)
    _remember_snapshot(path)
