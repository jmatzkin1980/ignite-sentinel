"""IMP-287: one writer — confinement and atomic writes.

Every file the runtime writes goes through `sentinel.core.io`. The destination is
resolved (links, junctions and 8.3 short names included) and must stay inside its
confinement root: the project workspace (`workspaces/<id>`) the path lives in, or
an explicit `root`. A write lands in a temporary file in the same folder, is
fsynced and then swapped in with `os.replace`, so a failure halfway never
truncates the previous content.
"""

from __future__ import annotations

import ast
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from sentinel.core import io as core_io
from sentinel.core.io import UnconfinedWrite, append_text, copy_file, write_bytes, write_text

from tests.test_path_aliases import make_alias

REPO_ROOT = Path(__file__).resolve().parents[1]


class _Tmp(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="sentinel_writer_")).resolve()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.workspace = self.tmp / "workspaces" / "DEMO"
        self.workspace.mkdir(parents=True)


class ConfinementTests(_Tmp):
    def test_write_inside_the_workspace(self) -> None:
        target = self.workspace / "01_discovery" / "gaps.md"
        write_text(target, "# Gaps\n")
        self.assertEqual(target.read_text(encoding="utf-8"), "# Gaps\n")

    def test_newline_follows_the_text_mode_rules(self) -> None:
        target = self.workspace / "a.md"
        write_text(target, "a\nb\n")
        self.assertEqual(target.read_bytes(), ("a" + os.linesep + "b" + os.linesep).encode())
        write_text(target, "a\nb\n", newline="\n")
        self.assertEqual(target.read_bytes(), b"a\nb\n")

    def test_parent_traversal_is_rejected(self) -> None:
        with self.assertRaises(UnconfinedWrite):
            write_text(self.workspace / ".." / "OTHER" / "x.md", "x")
        self.assertFalse((self.tmp / "workspaces" / "OTHER").exists())

    def test_path_outside_an_explicit_root_is_rejected(self) -> None:
        outside = self.tmp / "elsewhere" / "x.md"
        with self.assertRaises(UnconfinedWrite):
            write_text(outside, "x", root=self.workspace)
        self.assertFalse(outside.exists())

    def test_workspace_cannot_write_into_a_sibling_workspace(self) -> None:
        sibling = self.tmp / "workspaces" / "OTHER" / "x.md"
        with self.assertRaises(UnconfinedWrite):
            write_text(sibling, "x", root=self.workspace)

    def test_link_escaping_the_workspace_is_rejected(self) -> None:
        outside = self.tmp / "outside"
        outside.mkdir()
        if not make_alias(outside, self.workspace / "escape"):
            self.skipTest("cannot create a junction/symlink here")
        with self.assertRaises(UnconfinedWrite):
            write_text(self.workspace / "escape" / "x.md", "x")
        self.assertEqual(list(outside.iterdir()), [])

    def test_aliased_root_still_matches_itself(self) -> None:
        alias = self.tmp / "alias_ws"
        if not make_alias(self.workspace, alias):
            self.skipTest("cannot create a junction/symlink here")
        write_text(alias / "x.md", "x", root=self.workspace)
        write_text(self.workspace / "y.md", "y", root=alias)
        self.assertTrue((self.workspace / "x.md").exists())

    def test_unconfined_write_is_a_value_error_naming_the_path(self) -> None:
        with self.assertRaises(ValueError) as caught:
            write_text(self.tmp / "elsewhere.md", "x", root=self.workspace)
        self.assertIn("elsewhere.md", str(caught.exception))

    def test_append_and_bytes_and_copy_are_confined(self) -> None:
        outside = self.tmp / "out.md"
        source = self.tmp / "source.md"
        source.write_text("evidence", encoding="utf-8")
        for call in (
            lambda: append_text(outside, "x", root=self.workspace),
            lambda: write_bytes(outside, b"x", root=self.workspace),
            lambda: copy_file(source, outside, root=self.workspace),
        ):
            with self.assertRaises(UnconfinedWrite):
                call()
        self.assertFalse(outside.exists())

    def test_append_and_copy_inside(self) -> None:
        target = self.workspace / "log.md"
        append_text(target, "a\n", newline="\n")
        append_text(target, "b\n", newline="\n")
        self.assertEqual(target.read_bytes(), b"a\nb\n")
        source = self.tmp / "source.md"
        source.write_bytes(b"\x00raw")
        copy_file(source, self.workspace / "00_raw" / "source.md")
        self.assertEqual((self.workspace / "00_raw" / "source.md").read_bytes(), b"\x00raw")


class AtomicityTests(_Tmp):
    def test_failure_halfway_keeps_the_previous_content(self) -> None:
        target = self.workspace / "prd.md"
        write_text(target, "previous\n", newline="\n")
        with mock.patch.object(core_io.os, "replace", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                write_text(target, "new content that never lands\n")
        self.assertEqual(target.read_bytes(), b"previous\n")
        self.assertEqual(sorted(item.name for item in self.workspace.iterdir()), ["prd.md"])

    def test_content_is_fsynced_before_the_swap(self) -> None:
        with mock.patch.object(core_io.os, "fsync", wraps=os.fsync) as fsync:
            write_text(self.workspace / "x.md", "x")
        self.assertTrue(fsync.called)


# Modules allowed to write outside core/io.py, each with its reason.
WRITER_EXEMPT = {
    "sentinel/build.py": "builds dist/sentinel.pyz from a private staging tempdir (maintainer tool, not runtime)",
}
_WRITE_ATTRS = {"write_text", "write_bytes", "write_json_text"}
_COPY_FUNCS = {"copyfile", "copy", "copy2", "copytree", "move", "rmtree"}
_DELETE_ATTRS = {"unlink", "rmdir"}  # IMP-299: deletions go through core_io.remove too
_OS_DELETE_FUNCS = {"remove", "unlink", "rmdir", "removedirs"}


def _write_calls(tree: ast.AST) -> list[tuple[int, str]]:
    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Attribute) and func.attr in _WRITE_ATTRS and not (
            isinstance(func.value, ast.Name) and func.value.id in {"core_io", "io"}
        ):
            found.append((node.lineno, f".{func.attr}("))
        if isinstance(func, ast.Attribute) and func.attr in _COPY_FUNCS and isinstance(func.value, ast.Name) and func.value.id == "shutil":
            found.append((node.lineno, f"shutil.{func.attr}("))
        if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name) and func.value.id == "os":
            if func.attr in _OS_DELETE_FUNCS:
                found.append((node.lineno, f"os.{func.attr}("))
        elif isinstance(func, ast.Attribute) and func.attr in _DELETE_ATTRS:
            found.append((node.lineno, f".{func.attr}("))
        is_open = (isinstance(func, ast.Name) and func.id == "open") or (isinstance(func, ast.Attribute) and func.attr in {"open", "fdopen"})
        if is_open:
            mode = None
            positional = 1 if isinstance(func, ast.Name) or func.attr == "fdopen" else 0
            if len(node.args) > positional and isinstance(node.args[positional], ast.Constant):
                mode = node.args[positional].value
            for keyword in node.keywords:
                if keyword.arg == "mode" and isinstance(keyword.value, ast.Constant):
                    mode = keyword.value.value
            if isinstance(mode, str) and set(mode) & set("wax+"):
                found.append((node.lineno, f"open(mode={mode!r})"))
    return found


class WriterGuardTests(unittest.TestCase):
    def test_only_core_io_writes_files(self) -> None:
        offenders = []
        for path in sorted((REPO_ROOT / "sentinel").rglob("*.py")):
            relative = path.relative_to(REPO_ROOT).as_posix()
            if relative == "sentinel/core/io.py" or relative in WRITER_EXEMPT:
                continue
            for line, call in _write_calls(ast.parse(path.read_text(encoding="utf-8"))):
                offenders.append(f"{relative}:{line} {call}")
        self.assertEqual(offenders, [], "write and delete through sentinel.core.io (write_text/write_bytes/append_text/copy_file/remove)")

    def test_guard_detects_each_form(self) -> None:
        sample = (
            "p.write_text('x')\np.write_bytes(b'x')\nopen(p, 'w')\np.open('a')\nopen(p, mode='xb')\n"
            "shutil.copyfile(a, b)\nopen(p)\np.read_text()\n"
            "p.unlink()\nd.rmdir()\nos.remove(p)\nos.unlink(p)\nshutil.rmtree(d)\n"
        )
        self.assertEqual(len(_write_calls(ast.parse(sample))), 11)


if __name__ == "__main__":
    unittest.main()
