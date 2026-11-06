"""Safe local cleanup tool (tools/clean_local.py).

The tool lists (dry-run by default) and optionally deletes only regenerable
local residue: git-ignored build/cache outputs, eval reports beyond the
retention window, and leftover test tempdirs that match the exact shapes the
suite creates. Workspaces are never touched without an explicit flag and a
per-workspace confirmation; tracked files are never touched at all.
"""

from __future__ import annotations

import contextlib
import io
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "tools"))
import clean_local  # noqa: E402

GITIGNORE = """__pycache__/
dist/
build/
*.egg-info/
*.pyz
dashboard.html
PATHFINDER-*/
docs/
.venv/
tests/evals/reports/
workspaces/*
!workspaces/_template/
"""

OLD = time.time() - 3 * 24 * 3600


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def _touch(path: Path, text: str = "x") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


@unittest.skipUnless(shutil.which("git"), "git is required for the cleanup safety checks")
class CleanLocalRepoTests(unittest.TestCase):
    def setUp(self) -> None:
        holder = tempfile.TemporaryDirectory(prefix="sentinel_clean_")
        self.addCleanup(holder.cleanup)
        # resolve(): on Windows runners the temp dir is given with an 8.3 short name
        # (RUNNER~1) while clean_local reports resolved paths (IMP-246).
        self.repo = Path(holder.name).resolve() / "repo"
        self.temp_root = Path(holder.name) / "temp"
        self.temp_root.mkdir()
        self.repo.mkdir()
        _git(self.repo, "init", "-q")
        _touch(self.repo / ".gitignore", GITIGNORE)
        _touch(self.repo / "sentinel" / "core.py", "print('tracked')")
        _touch(self.repo / "workspaces" / "_template" / ".gitkeep", "")
        _git(self.repo, "add", ".")
        # Generated residue (all git-ignored).
        _touch(self.repo / "sentinel" / "__pycache__" / "core.cpython-314.pyc")
        _touch(self.repo / "dist" / "sentinel.pyz")
        _touch(self.repo / "ignite_sentinel.egg-info" / "PKG-INFO")
        _touch(self.repo / "dashboard.html", "<html>")
        _touch(self.repo / "PATHFINDER-2026-07-26" / "map.md")
        for day in ("2026-06-01", "2026-06-02", "2026-06-03"):
            _touch(self.repo / "tests" / "evals" / "reports" / f"discovery_eval_{day}.json", "{}")
        # Protected: never candidates.
        _touch(self.repo / ".venv" / "Lib" / "__pycache__" / "x.pyc")
        _touch(self.repo / "docs" / "evolution" / "notes.md")
        _touch(self.repo / "workspaces" / "ACME" / "01_discovery" / "gaps.md")

    def _plan(self, **kwargs):
        kwargs.setdefault("temp_root", self.temp_root)
        kwargs.setdefault("keep_reports", 1)
        return clean_local.plan(self.repo, **kwargs)

    def _rel(self, candidates):
        return sorted(c.path.relative_to(self.repo).as_posix() for c in candidates if c.group != "temp")

    def test_dry_run_lists_only_regenerable_residue(self) -> None:
        result = self._plan()
        self.assertEqual(
            self._rel(result.candidates),
            [
                "PATHFINDER-2026-07-26",
                "dashboard.html",
                "dist",
                "ignite_sentinel.egg-info",
                "sentinel/__pycache__",
                "tests/evals/reports/discovery_eval_2026-06-01.json",
                "tests/evals/reports/discovery_eval_2026-06-02.json",
            ],
        )
        self.assertTrue((self.repo / "dist").exists(), "plan() must not delete anything")

    def test_apply_deletes_candidates_and_nothing_else(self) -> None:
        result = self._plan()
        deleted, failed = clean_local.apply(result.candidates)
        self.assertEqual(failed, [])
        self.assertEqual(len(deleted), len(result.candidates))
        for kept in (
            "sentinel/core.py",
            ".venv/Lib/__pycache__/x.pyc",
            "docs/evolution/notes.md",
            "workspaces/ACME/01_discovery/gaps.md",
            "workspaces/_template/.gitkeep",
            "tests/evals/reports/discovery_eval_2026-06-03.json",
        ):
            self.assertTrue((self.repo / kept).exists(), kept)
        self.assertFalse((self.repo / "dist").exists())

    def test_directory_holding_a_tracked_file_is_never_a_candidate(self) -> None:
        _git(self.repo, "add", "-f", "dist/sentinel.pyz")
        self.assertNotIn("dist", self._rel(self._plan().candidates))

    def test_workspaces_need_flag_and_per_workspace_confirmation(self) -> None:
        listed = [c for c in self._plan(include_workspaces=True).candidates if c.group == "workspace"]
        self.assertEqual([c.path.name for c in listed], ["ACME"])
        clean_local.apply(listed, confirm=lambda candidate: False)
        self.assertTrue((self.repo / "workspaces" / "ACME").exists())
        clean_local.apply(listed, confirm=lambda candidate: True)
        self.assertFalse((self.repo / "workspaces" / "ACME").exists())
        self.assertTrue((self.repo / "workspaces" / "_template").exists())

    def test_workspaces_are_skipped_without_interactive_confirmation(self) -> None:
        listed = [c for c in self._plan(include_workspaces=True).candidates if c.group == "workspace"]
        # Default confirm refuses without a TTY (patched so the suite never blocks on input()).
        with patch.object(sys, "stdin", io.StringIO("ACME\n")), contextlib.redirect_stdout(io.StringIO()):
            deleted, _ = clean_local.apply(listed)
        self.assertEqual(deleted, [])
        self.assertTrue((self.repo / "workspaces" / "ACME").exists())

    def test_non_git_directory_yields_no_repo_candidates(self) -> None:
        plain = self.temp_root.parent / "plain"
        _touch(plain / "dist" / "x.pyz")
        result = clean_local.plan(plain, temp_root=self.temp_root, keep_reports=1)
        self.assertEqual([c for c in result.candidates if c.group == "repo"], [])
        self.assertTrue(any("git" in w for w in result.warnings))


class CleanLocalTempTests(unittest.TestCase):
    def setUp(self) -> None:
        holder = tempfile.TemporaryDirectory(prefix="sentinel_clean_tmp_")
        self.addCleanup(holder.cleanup)
        self.root = Path(holder.name)

    def _make(self, name: str, files: list[str], *, old: bool = True) -> Path:
        base = self.root / name
        for rel in files:
            _touch(base / rel)
        if old:
            os.utime(base, (OLD, OLD))
        return base

    def test_only_old_sentinel_shaped_tempdirs_are_candidates(self) -> None:
        self._make("tmpabc123", ["raw.md", "workspaces/ACME/00_raw/x.md", "workspaces/ACME/01_discovery/gaps.md"])
        self._make("sentinel_eval_xyz", ["workspaces/EVAL/00_raw/a.md", "workspaces/EVAL/01_discovery/b.md"])
        self._make("tmpmomtest", ["01_discovery/gaps.md"])
        (self.root / "tmpemptydisc" / "01_discovery").mkdir(parents=True)
        os.utime(self.root / "tmpemptydisc", (OLD, OLD))
        self._make("tmpdiscextra", ["01_discovery/gaps.md", "01_discovery/other.md"])
        self._make("tmpfresh", ["workspaces/NEW/00_raw/a.md", "workspaces/NEW/01_discovery/b.md"], old=False)
        self._make("tmpforeign", ["workspaces/X/00_raw/a.md", "workspaces/X/01_discovery/b.md", "node_modules/pkg/i.js"])
        self._make("tmpother", ["something.txt"])
        self._make("otherprefix", ["workspaces/X/00_raw/a.md", "workspaces/X/01_discovery/b.md"])
        names = sorted(c.path.name for c in clean_local.temp_candidates(self.root, min_age_hours=24))
        self.assertEqual(names, ["sentinel_eval_xyz", "tmpabc123", "tmpemptydisc", "tmpmomtest"])

    def test_report_format_mentions_dry_run_and_total(self) -> None:
        self._make("tmpmomtest", ["01_discovery/gaps.md"])
        result = clean_local.PlanResult(candidates=clean_local.temp_candidates(self.root, min_age_hours=24))
        text = clean_local.format_plan(result, apply=False)
        self.assertIn("dry-run", text)
        self.assertIn("Total", text)


if __name__ == "__main__":
    unittest.main()
