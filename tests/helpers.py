"""Shared test helpers (IMP-305).

- `run_cli` runs one command in-process and returns its exit code and output.
- `SnapshotWorkspaceCase` builds a workspace once per class and gives every test a
  fresh copy of it, at the same path, so a test can mutate it freely.
- `build_matured_workspace` is the chain most backlog tests start from:
  init, ingest, an answered GAP-ACCEPTANCE, brief, specs and backlog.
"""
from __future__ import annotations

import io
import os
import shutil
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from sentinel.cli import main


def run_cli(argv: list[str]) -> tuple[int, str]:
    """Run one command in-process; return (exit code, stdout). Stderr is discarded."""
    out = io.StringIO()
    with redirect_stdout(out), redirect_stderr(io.StringIO()):
        code = main(list(argv))
    return code, out.getvalue()


def run_ok(argv: list[str]) -> str:
    """Run one command and fail the test if it does not exit 0."""
    code, out = run_cli(argv)
    if code != 0:
        raise AssertionError(f"{' '.join(argv)} exited {code}:\n{out[-2000:]}")
    return out


def gap_acceptance_answer(ears: str, evidence_label: str = "Evidence or reference") -> str:
    """A confirmed answer to GAP-ACCEPTANCE carrying the given EARS statement(s)."""
    return (
        "### GAP-ACCEPTANCE\n"
        f"- Answer: {ears}\n"
        "- Owner / source: Client workshop\n"
        f"- {evidence_label}: Synthetic EARS response\n"
        "- Decision status: confirmed\n"
    )


def build_matured_workspace(project_id: str, raw: str, answers: str, *, backlog: bool = True) -> Path:
    """Run the matured-backlog chain in the current folder; return the workspace path.

    `raw` is written to raw.md and ingested; `answers` (see `gap_acceptance_answer`)
    is written to answers.md and resolved. The chain stops after specs when
    `backlog` is False, for tests that add context before generating the backlog.
    """
    root = Path.cwd()
    (root / "raw.md").write_text(raw, encoding="utf-8")
    (root / "answers.md").write_text(answers, encoding="utf-8")
    run_ok(["init", project_id, "--brief-version", "1"])
    run_ok(["ingest", project_id, "--source", str(root / "raw.md")])
    run_ok(["resolve-gaps", project_id, "--source", str(root / "answers.md")])
    run_ok(["brief", project_id])
    run_ok(["specs", project_id])
    if backlog:
        run_ok(["backlog", project_id])
    return root / "workspaces" / project_id


class SnapshotWorkspaceCase(unittest.TestCase):
    """Build the workspace once per class; each test gets a fresh copy at the same path.

    Subclasses implement `build_workspace()`, which runs with the working folder set
    to the class's work folder. Before each test the work folder is restored from a
    snapshot taken right after the build, so tests stay independent. The copy keeps
    the build's path because generated artifacts quote absolute paths.

    In each test, `self.temp` is the work folder and the current directory.
    """

    _class_dir: Path
    _work: Path
    _snapshot: Path

    @classmethod
    def build_workspace(cls) -> None:
        raise NotImplementedError

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls._class_dir = Path(tempfile.mkdtemp(prefix=f"sentinel_{cls.__name__}_"))
        cls._work = cls._class_dir / "work"
        cls._snapshot = cls._class_dir / "snapshot"
        cls._work.mkdir()
        old = Path.cwd()
        os.chdir(cls._work)
        try:
            cls.build_workspace()
        except BaseException:
            os.chdir(old)
            shutil.rmtree(cls._class_dir, ignore_errors=True)
            raise
        os.chdir(old)
        shutil.copytree(cls._work, cls._snapshot)

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls._class_dir, ignore_errors=True)
        super().tearDownClass()

    def setUp(self) -> None:
        super().setUp()
        self.old_cwd = Path.cwd()
        if self._work.exists():
            shutil.rmtree(self._work)
        shutil.copytree(self._snapshot, self._work)
        os.chdir(self._work)
        self.temp = self._work

    def tearDown(self) -> None:
        os.chdir(self.old_cwd)
        super().tearDown()
