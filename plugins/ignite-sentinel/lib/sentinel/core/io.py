from __future__ import annotations

import json
import os
import stat
import tempfile
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
from typing import Any, Iterable, Iterator

from ..errors import InputError, WorkspaceBusy


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


def forget_read_snapshots() -> None:
    """Forget what earlier commands read (IMP-299: each command starts from the disk)."""
    _READ_SNAPSHOTS.clear()


class WriteConflict(WorkspaceBusy):
    """IMP-299: a file changed on disk between this command's read and its write."""


def _refuse_if_changed(path: Path) -> None:
    normalized = _normalized_path(path)
    if normalized not in _READ_SNAPSHOTS:
        return
    expected = _READ_SNAPSHOTS[normalized]
    actual = _file_hash(path)
    if expected != actual:
        # IMP-299: writing would silently drop the other change. Under the workspace
        # lock only a writer outside Sentinel can cause this.
        raise WriteConflict(
            f"Write conflict on {path.as_posix()}: it changed since this command read it.",
            next_step="Check who else edits the workspace, then run this command again.",
        )


def _workspace_location(path: Path) -> tuple[str, str] | None:
    """(project id, workspace-relative path) for a file under `workspaces/<id>/`, else None."""
    parts = Path(os.path.abspath(path)).parts
    for index in range(len(parts) - 3, -1, -1):
        if parts[index] == "workspaces":
            return parts[index + 1], Path(*parts[index + 2 :]).as_posix()
    return None


class InvalidJsonFile(InputError, json.JSONDecodeError):
    """IMP-331: a JSON file that does not parse, named, with a way out (exit 3).

    Still a ``json.JSONDecodeError`` (so a ``ValueError``) for the handlers that
    catch those around ``read_json``.
    """

    def __init__(self, path: Path, error: ValueError) -> None:
        self.path = path
        self.msg = getattr(error, "msg", str(error))
        self.doc = getattr(error, "doc", "")
        self.pos = getattr(error, "pos", 0)
        self.lineno = getattr(error, "lineno", 1)
        self.colno = getattr(error, "colno", 1)
        if isinstance(error, json.JSONDecodeError):
            detail = f"{error.msg} at line {error.lineno}, column {error.colno}"
        else:
            detail = "it is not UTF-8 text"
        location = _workspace_location(path)
        if location is None:
            shown = path.as_posix()
            next_step = f"Fix or replace {shown}, then run the command again."
        else:
            project_id, relative = location
            shown = f"{relative} in workspace {project_id}"
            if relative == "state.json":
                next_step = (
                    f"Copy .sentinel/state.json.bak over state.json in workspaces/{project_id}/ "
                    "(or restore state.json from git), then run the command again."
                )
            elif relative == ".sentinel/derived/state.json":
                next_step = "Delete that file; the next command rebuilds it."
            elif relative.startswith("memory.lancedb/"):
                next_step = f"Run /reindex {project_id} to rebuild the memory."
            else:
                next_step = (
                    f"Restore {relative} from git or a backup, or regenerate it by running "
                    "the command that writes it again."
                )
        # Not InputError.__init__: its super() call would land on JSONDecodeError.__init__.
        BaseException.__init__(self, f"{shown} is not valid JSON: {detail}.")
        self.next_step = next_step


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
    try:
        data = json.loads(raw.decode("utf-8"))
    except ValueError as exc:  # JSONDecodeError or UnicodeDecodeError
        raise InvalidJsonFile(path, exc) from None
    _JSON_READ_CACHE[normalized] = (signature[0], signature[1], digest, data)
    _remember_snapshot_hash(path, digest)
    return deepcopy(data)


def parse_json(text: str) -> Any:
    """Parse a JSON document already held in memory (e.g. JSONC text after its
    comments were stripped). Centralizes ``json.loads`` so domain code never
    imports ``json`` directly (enforced by test_core_architecture). Raises
    ``ValueError`` on malformed input, like the stdlib."""
    return json.loads(text)


def read_json_resource(resource: Any, default: Any | None = None) -> Any:
    try:
        return json.loads(resource.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default


# --- IMP-287: the single writer -------------------------------------------
#
# Every file the runtime writes goes through the functions below (a test walks
# the AST of `sentinel/` to keep it that way). Each destination is confined to
# a root: an explicit `root`, else the project workspace (`workspaces/<id>`)
# the path lives in, else the repo root. Both sides are compared *resolved*, so
# a symlink or junction that leaves the root is caught, and the two spellings
# of one folder (8.3 short names on Windows, IMP-246) compare equal. Writes go
# to a temporary file in the same folder, are fsynced and swapped in with
# `os.replace`: a failure halfway leaves the previous content intact.


class UnconfinedWrite(ValueError):
    """A write whose destination resolves outside its confinement root (IMP-287)."""


def _current_umask() -> int:
    if os.name == "nt":
        return 0
    mask = os.umask(0)
    os.umask(mask)
    return mask


_UMASK = _current_umask()


def _default_root(absolute: Path) -> Path:
    parts = absolute.parts
    for index in range(len(parts) - 3, -1, -1):
        if parts[index] == "workspaces":
            return Path(*parts[: index + 2])
    from .paths import repo_root

    return Path(os.path.abspath(repo_root()))


def confine(path: Path | str, root: Path | str | None = None) -> Path:
    """Return the absolute destination for `path`, or raise `UnconfinedWrite`."""
    candidate = Path(path)
    if ".." in candidate.parts:
        raise UnconfinedWrite(f"refusing to write {candidate.as_posix()}: '..' is not allowed in a destination")
    absolute = Path(os.path.abspath(candidate))
    base = Path(os.path.abspath(root)) if root is not None else _default_root(absolute)
    resolved_base = base.resolve(strict=False)
    resolved = absolute.resolve(strict=False)
    if resolved != resolved_base and resolved_base not in resolved.parents:
        raise UnconfinedWrite(
            f"refusing to write {absolute.as_posix()}: it resolves to {resolved.as_posix()}, "
            f"outside {resolved_base.as_posix()} (a link, junction or foreign path?)"
        )
    return absolute


def _translate_newlines(text: str, newline: str | None) -> str:
    # Same rules as text-mode open(): None -> os.linesep, "" or "\n" -> untouched.
    if newline is None:
        newline = os.linesep
    return text if newline in ("", "\n") else text.replace("\n", newline)


def _atomic_write(destination: Path, data: "bytes | Iterable[bytes]") -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        mode = stat.S_IMODE(destination.stat().st_mode)
    except FileNotFoundError:
        mode = 0o666 & ~_UMASK
    descriptor, temporary = tempfile.mkstemp(prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            for block in (data,) if isinstance(data, (bytes, bytearray)) else data:
                handle.write(block)
            handle.flush()
            os.fsync(handle.fileno())
        if os.name != "nt":
            os.chmod(temporary, mode)
        os.replace(temporary, destination)
    except BaseException:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def write_bytes(path: Path | str, data: bytes, *, root: Path | str | None = None) -> Path:
    destination = confine(path, root)
    _invalidate_json_cache(destination)
    _atomic_write(destination, data)
    _remember_snapshot(destination)
    return destination


def write_text(
    path: Path | str, text: str, *, root: Path | str | None = None, newline: str | None = None
) -> Path:
    return write_bytes(path, _translate_newlines(text, newline).encode("utf-8"), root=root)


def copy_file(source: Path | str, destination: Path | str, *, root: Path | str | None = None) -> Path:
    """Copy `source` byte for byte into a confined destination (the source may live anywhere).

    Streamed in blocks: a model file of hundreds of MB never sits whole in memory.
    """
    target = confine(destination, root)
    _invalidate_json_cache(target)
    _atomic_write(target, _read_blocks(Path(source)))
    _remember_snapshot(target)
    return target


def _read_blocks(source: Path, size: int = 1024 * 1024) -> "Iterator[bytes]":
    with open(source, "rb") as handle:
        while True:
            block = handle.read(size)
            if not block:
                return
            yield block


def write_json(path: Path, data: Any, *, root: Path | str | None = None) -> None:
    destination = confine(path, root)
    _refuse_if_changed(destination)
    _invalidate_json_cache(destination)
    _atomic_write(destination, (json.dumps(data, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    _remember_snapshot(destination)


def _holds(destination: Path, data: bytes) -> bool:
    try:
        return destination.is_file() and destination.stat().st_size == len(data) and destination.read_bytes() == data
    except OSError:
        return False


def write_text_if_changed(
    path: Path | str, text: str, *, root: Path | str | None = None, newline: str | None = None
) -> bool:
    """IMP-435 (C-15): `write_text` that leaves a file already holding these bytes untouched (same mtime). True if written."""
    data = _translate_newlines(text, newline).encode("utf-8")
    if _holds(confine(path, root), data):
        return False
    write_bytes(path, data, root=root)
    return True


def write_json_if_changed(path: Path, data: Any, *, root: Path | str | None = None) -> bool:
    """IMP-435 (C-15): `write_json` that leaves a file already holding these bytes untouched. True if written."""
    if _holds(confine(path, root), (json.dumps(data, indent=2, ensure_ascii=False) + "\n").encode("utf-8")):
        return False
    write_json(path, data, root=root)
    return True


def copy_file_if_changed(source: Path | str, destination: Path | str, *, root: Path | str | None = None) -> bool:
    """IMP-435 (C-15): `copy_file` after comparing the sha256 of both files; an equal copy is left untouched."""
    target = confine(destination, root)
    try:
        if target.is_file() and target.stat().st_size == Path(source).stat().st_size:
            digest = sha256()
            for block in _read_blocks(Path(source)):
                digest.update(block)
            if digest.hexdigest() == _file_hash(target):
                return False
    except OSError:
        pass
    copy_file(source, destination, root=root)
    return True


def append_bytes(path: Path | str, data: bytes, *, root: Path | str | None = None) -> Path:
    """Append-only write: existing bytes are never rewritten (fsynced, not atomic by nature)."""
    destination = confine(path, root)
    destination.parent.mkdir(parents=True, exist_ok=True)
    # IMP-299: no conflict check. An append keeps whatever another writer added.
    _invalidate_json_cache(destination)
    with open(destination, "ab") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    _remember_snapshot(destination)
    return destination


def append_text(path: Path | str, text: str, *, root: Path | str | None = None, newline: str | None = None) -> Path:
    return append_bytes(path, _translate_newlines(text, newline).encode("utf-8"), root=root)


def remove(path: Path | str, *, root: Path | str | None = None) -> bool:
    """IMP-299: delete a file, or an empty folder, confined like a write. False when it was already gone."""
    destination = confine(path, root)
    _invalidate_json_cache(destination)
    _READ_SNAPSHOTS.pop(_normalized_path(destination), None)
    try:
        if destination.is_dir() and not destination.is_symlink():
            destination.rmdir()
        else:
            destination.unlink()
    except FileNotFoundError:
        return False
    return True
