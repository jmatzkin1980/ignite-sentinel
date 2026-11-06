"""IMP-246 (found by CI on Windows): the same folder reached by two spellings.

GitHub's Windows runner gives a temp dir as `C:/Users/RUNNER~1/...` (8.3 short
name) while `resolve()` returns `C:/Users/runneradmin/...`. Corporate machines
with long user names behave the same. Code that compares a resolved path with an
unresolved cwd (or the other way round) then fails. A directory junction (Windows,
no admin rights needed) or a symlink (POSIX) reproduces the situation anywhere.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


def make_alias(real: Path, alias: Path) -> bool:
    """Create `alias` pointing at `real`; False when the platform refuses."""
    try:
        if sys.platform == "win32":
            done = subprocess.run(["cmd", "/c", "mklink", "/J", str(alias), str(real)], capture_output=True)
            return done.returncode == 0 and alias.exists()
        os.symlink(real, alias, target_is_directory=True)
        return True
    except (OSError, NotImplementedError):
        return False


class _AliasedCwd(unittest.TestCase):
    def setUp(self) -> None:
        self.old = Path.cwd()
        self.outer = Path(tempfile.mkdtemp(prefix="sentinel_alias_")).resolve()
        self.real = self.outer / "real_root"
        self.real.mkdir()
        self.alias = self.outer / "alias_root"
        if not make_alias(self.real, self.alias):
            shutil.rmtree(self.outer, ignore_errors=True)
            self.skipTest("cannot create a junction/symlink here")
        os.chdir(self.alias)  # cwd is the alias; resolve() gives the real path
        self.addCleanup(self._cleanup)

    def _cleanup(self) -> None:
        os.chdir(self.old)
        if sys.platform == "win32":
            subprocess.run(["cmd", "/c", "rmdir", str(self.alias)], capture_output=True)
        else:
            self.alias.unlink(missing_ok=True)
        shutil.rmtree(self.outer, ignore_errors=True)


class SourceKeyTests(_AliasedCwd):
    def test_source_key_is_relative_when_cwd_is_an_alias(self) -> None:
        from sentinel.sources import source_key

        target = Path.cwd() / "input" / "interactions" / "note.md"
        target.parent.mkdir(parents=True)
        target.write_text("x", encoding="utf-8")
        self.assertEqual(source_key(target), "input/interactions/note.md")
        self.assertEqual(source_key(target.resolve()), "input/interactions/note.md")


class RelativizeTextTests(_AliasedCwd):
    def test_both_spellings_of_the_root_are_removed(self) -> None:
        from sentinel.view import relativize_text

        for root in (Path.cwd(), Path.cwd().resolve()):
            with self.subTest(root=str(root)):
                text = f"(Anchor: {root.as_posix()}/workspaces/P/03_specs/specs.md:1-4)"
                self.assertEqual(relativize_text("P", text), "(Anchor: workspaces/P/03_specs/specs.md:1-4)")


if __name__ == "__main__":
    unittest.main()
