"""IMP-299 (H18): one command at a time per workspace.

The first concurrency tests of the runtime: real processes against one workspace.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

from sentinel.core.io import UnconfinedWrite, read_json, read_json_cache_stats, remove, write_json, write_text
from sentinel.core.lock import command_scope, lock_path
from sentinel.errors import EXIT_BUSY, WorkspaceBusy

REPO_ROOT = Path(__file__).resolve().parents[1]
PROJECT = "LOCKTEST"

# Each worker increments a counter in state.json with a read-modify-write that
# leaves room for the other process to interleave (the sleep).
_WORKER = """
import sys, time
sys.path.insert(0, {repo!r})
from pathlib import Path
from sentinel.core.lock import command_scope
from sentinel.core.state import read_state, update_state
workspace = Path("workspaces") / {project!r}
for _ in range({rounds}):
    with command_scope("worker", workspace):
        counter = read_state({project!r})["counter"]
        time.sleep(0.01)
        update_state({project!r}, counter=counter + 1)
"""

_HOLDER = """
import sys, time
sys.path.insert(0, {repo!r})
from pathlib import Path
from sentinel.core.lock import command_scope
with command_scope("ingest", Path("workspaces") / {project!r}):
    print("held", flush=True)
    time.sleep({seconds})
"""

_CLI = """
import sys
sys.path.insert(0, {repo!r})
from sentinel.cli import main
sys.exit(main(sys.argv[1:]))
"""


class _Workspace(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.workspace = self.root / "workspaces" / PROJECT
        self.workspace.mkdir(parents=True)
        (self.workspace / "state.json").write_text(json.dumps({"counter": 0}), encoding="utf-8")
        self.env = {**os.environ, "SENTINEL_LOCK_TIMEOUT": "60", "PYTHONDONTWRITEBYTECODE": "1"}

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def spawn(self, code: str, *args: str, env: dict[str, str] | None = None) -> subprocess.Popen:
        return subprocess.Popen(
            [sys.executable, "-c", code, *args],
            cwd=self.root,
            env=env or self.env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

    def hold(self, seconds: float) -> subprocess.Popen:
        holder = self.spawn(_HOLDER.format(repo=str(REPO_ROOT), project=PROJECT, seconds=seconds))
        self.assertEqual(holder.stdout.readline().strip(), "held", holder.stderr.read() if holder.poll() is not None else "")
        return holder


class TwoProcessTests(_Workspace):
    def test_two_processes_lose_no_update(self) -> None:
        rounds = 15
        code = _WORKER.format(repo=str(REPO_ROOT), project=PROJECT, rounds=rounds)
        workers = [self.spawn(code) for _ in range(2)]
        for worker in workers:
            _, err = worker.communicate(timeout=120)
            self.assertEqual(worker.returncode, 0, err)
        state = json.loads((self.workspace / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(state["counter"], 2 * rounds)

    def test_a_command_on_a_busy_workspace_exits_6_naming_the_holder(self) -> None:
        holder = self.hold(seconds=20)
        try:
            env = {**self.env, "SENTINEL_LOCK_TIMEOUT": "0.5"}
            started = time.monotonic()
            cli = self.spawn(_CLI.format(repo=str(REPO_ROOT)), "status", PROJECT, env=env)
            _, err = cli.communicate(timeout=60)
            self.assertEqual(cli.returncode, EXIT_BUSY, err)
            self.assertIn("/ingest", err)
            self.assertIn("next step: Wait for /ingest to finish", err)
            self.assertLess(time.monotonic() - started, 30)
        finally:
            holder.kill()
            holder.communicate()

    def test_a_dead_holder_does_not_block_the_next_command(self) -> None:
        holder = self.hold(seconds=60)
        holder.kill()
        holder.communicate()
        started = time.monotonic()
        with command_scope("next", self.workspace, timeout=5):
            pass
        self.assertLess(time.monotonic() - started, 5)

    def test_the_holder_line_is_cleared_on_release(self) -> None:
        with command_scope("sync", self.workspace):
            self.assertIn("/sync (pid", lock_path(self.workspace).read_text(encoding="utf-8"))
        self.assertEqual(lock_path(self.workspace).read_text(encoding="utf-8"), "")


class InProcessTests(_Workspace):
    def test_nested_scopes_do_not_wait_for_themselves(self) -> None:
        with command_scope("export", self.workspace, timeout=0):
            with command_scope("export", self.workspace, timeout=0):
                with command_scope("export", self.root / "workspaces" / "OTHER", timeout=0):
                    pass

    def test_a_busy_workspace_raises_workspace_busy(self) -> None:
        holder = self.hold(seconds=20)
        try:
            with self.assertRaises(WorkspaceBusy) as caught:
                with command_scope("status", self.workspace, timeout=0.2):
                    pass
            self.assertIn("/ingest (pid", str(caught.exception))
        finally:
            holder.kill()
            holder.communicate()

    def test_entering_a_command_drops_the_read_caches(self) -> None:
        path = self.workspace / "state.json"
        read_json(path, {})
        read_json(path, {})
        self.assertGreater(read_json_cache_stats()["entries"], 0)
        with command_scope("status", self.workspace):
            self.assertEqual(read_json_cache_stats()["entries"], 0)

    def test_an_earlier_read_does_not_turn_into_a_false_conflict(self) -> None:
        path = self.workspace / "state.json"
        read_json(path, {})
        path.write_text(json.dumps({"counter": 5}), encoding="utf-8")  # another command, between two of ours
        with command_scope("sync", self.workspace):
            write_json(path, {"counter": 6})
        self.assertEqual(read_json(path, {})["counter"], 6)

    def test_an_append_after_an_outside_change_keeps_both(self) -> None:
        from sentinel.core.io import append_text, read_json as read

        log = self.workspace / "notes.json"
        write_json(log, {"a": 1})
        read(log, {})
        log.write_text('{"a": 2}\n', encoding="utf-8")
        append_text(log, "tail\n", newline="\n")
        self.assertEqual(log.read_text(encoding="utf-8"), '{"a": 2}\ntail\n')

    def test_no_workspace_runs_without_a_lock(self) -> None:
        missing = self.root / "workspaces" / "NOPE"
        with command_scope("init", missing, timeout=0):
            pass
        self.assertFalse(missing.exists())


class RemoveTests(_Workspace):
    def test_remove_is_confined_and_reports_missing_files(self) -> None:
        target = self.workspace / "04_backlog" / "US-001.md"
        write_text(target, "x")
        self.assertTrue(remove(target))
        self.assertFalse(target.exists())
        self.assertFalse(remove(target))
        self.assertTrue(remove(target.parent))
        outside = self.root / "outside.md"
        outside.write_text("x", encoding="utf-8")
        with self.assertRaises(UnconfinedWrite):
            remove(outside, root=self.workspace)
        self.assertTrue(outside.exists())


class McpSerializationTests(unittest.TestCase):
    def test_two_overlapping_tools_do_not_mix_their_output(self) -> None:
        from sentinel import mcp

        def fake_main(arguments: list[str]) -> int:
            for _ in range(5):
                print(arguments[0], end="", flush=True)
                time.sleep(0.01)
            return 0

        results: dict[str, object] = {}

        def call(tag: str) -> None:
            results[tag] = mcp.run_cli([tag])["output"]

        with mock.patch("sentinel.cli.main", fake_main):
            threads = [threading.Thread(target=call, args=(tag,)) for tag in ("a", "b")]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=30)
        self.assertEqual(results, {"a": "aaaaa", "b": "bbbbb"})


if __name__ == "__main__":
    unittest.main()
