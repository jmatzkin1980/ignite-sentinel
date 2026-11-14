"""IMP-299 (H18): one command at a time per workspace.

Every command that names a project with an existing workspace holds an exclusive
lock on ``workspaces/<id>/.sentinel/lock`` while it runs. The lock is the
operating system's (``msvcrt.locking`` on Windows, ``fcntl.flock`` elsewhere), so
it is released when the holder exits, even if it crashes or is killed: a dead
process never blocks the next one.

A second command waits up to ``SENTINEL_LOCK_TIMEOUT`` seconds (10 by default)
and then fails with ``WorkspaceBusy`` (exit code 6), naming the command that
holds the workspace and since when. The lock file carries that holder line; the
lock itself sits on a byte far past the end of the file, so reading the holder
never collides with the lock on Windows.

Nested acquisitions in the same thread (a release command runs the CLI again
inside its mirror) are free: the outer command already holds the workspace.
Entering the outermost scope also drops the in-memory read caches, so a command
never trusts what an earlier command in the same process (the MCP server) read.

Read-only commands take the lock too: every project command records itself in
``state.json`` (the command log), and ``/health``, ``/maturity`` and ``/view``
write files, so none of them is read-only on disk.
"""
from __future__ import annotations

import contextlib
import os
import threading
import time
from pathlib import Path
from typing import Iterator

from ..errors import WorkspaceBusy

DEFAULT_TIMEOUT = 10.0
POLL_SECONDS = 0.1
LOCK_DIR = ".sentinel"
LOCK_NAME = "lock"
_LOCK_OFFSET = 1 << 30  # the locked byte, past any holder line

_STATE = threading.local()


def lock_timeout() -> float:
    raw = os.environ.get("SENTINEL_LOCK_TIMEOUT", "")
    try:
        return max(0.0, float(raw)) if raw else DEFAULT_TIMEOUT
    except ValueError:
        return DEFAULT_TIMEOUT


def lock_path(workspace: Path) -> Path:
    return workspace / LOCK_DIR / LOCK_NAME


def _try_lock(descriptor: int) -> bool:
    if os.name == "nt":
        import msvcrt

        os.lseek(descriptor, _LOCK_OFFSET, os.SEEK_SET)
        try:
            msvcrt.locking(descriptor, msvcrt.LK_NBLCK, 1)
        except OSError:
            return False
        return True
    import fcntl

    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return False
    return True


def _unlock(descriptor: int) -> None:
    if os.name == "nt":
        import msvcrt

        os.lseek(descriptor, _LOCK_OFFSET, os.SEEK_SET)
        msvcrt.locking(descriptor, msvcrt.LK_UNLCK, 1)
        return
    import fcntl

    fcntl.flock(descriptor, fcntl.LOCK_UN)


def _write_holder(descriptor: int, command: str) -> None:
    since = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime())
    line = f"/{command} (pid {os.getpid()}) since {since}\n".encode("utf-8")
    os.ftruncate(descriptor, 0)
    os.lseek(descriptor, 0, os.SEEK_SET)
    os.write(descriptor, line)


def _read_holder(path: Path) -> str:
    try:
        return path.read_bytes()[:200].decode("utf-8", errors="replace").strip()
    except OSError:
        return ""


def clear_read_caches() -> None:
    from .io import forget_read_snapshots, clear_read_json_cache
    from .markdown import clear_markdown_parse_cache

    clear_read_json_cache()
    forget_read_snapshots()
    clear_markdown_parse_cache()


def holds_lock() -> bool:
    return getattr(_STATE, "depth", 0) > 0


@contextlib.contextmanager
def command_scope(command: str, workspace: Path | None, timeout: float | None = None) -> Iterator[None]:
    """Run one command: fresh read caches, and the workspace lock when there is a workspace."""
    if holds_lock():
        _STATE.depth += 1
        try:
            yield
        finally:
            _STATE.depth -= 1
        return
    clear_read_caches()
    if workspace is None or not workspace.is_dir():
        yield
        return
    path = lock_path(workspace)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_RDWR | os.O_CREAT, 0o666)
    try:
        wait = lock_timeout() if timeout is None else timeout
        deadline = time.monotonic() + wait
        while not _try_lock(descriptor):
            if time.monotonic() >= deadline:
                holder = _read_holder(path) or "another command"
                raise WorkspaceBusy(
                    f"Workspace {workspace.name} is busy: {holder} holds it "
                    f"(waited {wait:g} s).",
                    next_step=f"Wait for {holder.split(' ')[0]} to finish, then run this command again.",
                )
            time.sleep(POLL_SECONDS)
        _write_holder(descriptor, command)
        _STATE.depth = 1
        try:
            yield
        finally:
            _STATE.depth = 0
            with contextlib.suppress(OSError):
                os.ftruncate(descriptor, 0)
            _unlock(descriptor)
    finally:
        os.close(descriptor)
