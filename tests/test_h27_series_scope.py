"""IMP-427 (H27 inc 7c) task 1: `series_scope`, one place for the brief text and the series folder of a project or a change.

The project's series chain reads through it and writes the same bytes as before (RF 3).
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from helpers import SyncCase  # noqa: E402
from test_series_e2e import CHAIN, P, _cli  # noqa: E402

from sentinel.changes import change_gaps_path, get_change, list_changes  # noqa: E402
from sentinel.compilers.change_deliverable import render_change_deliverable_parts  # noqa: E402
from sentinel.core.io import forget_read_snapshots  # noqa: E402
from sentinel.errors import GateRefusal  # noqa: E402
from sentinel.memory import ContextBroker  # noqa: E402
from sentinel.series_scope import SeriesScope, normalized_change_text, series_scope  # noqa: E402
from sentinel.split import brief_hash  # noqa: E402
from sentinel.workspace import update_state, workspace_path  # noqa: E402

BASELINE = json.loads((ROOT / "fixtures" / "change_inc7" / "series_project_sha256.json").read_text(encoding="utf-8"))


def run_project_flow(work: Path) -> None:
    """The flow of tests/test_series_e2e.py up to `/split --confirm`."""
    fx = CHAIN.fixture
    old = os.getcwd()
    os.chdir(work)
    try:
        with patch.object(ContextBroker, "_connect_lancedb", lambda self: None):
            steps = [["init", P]]
            steps += [["ingest", P, "--source", str(fx / name)] + (["--replace"] if i else [])
                      for i, name in enumerate(CHAIN.sources)]
            steps += [["gaps", P], ["resolve-gaps", P, "--source", str(fx / "gap_responses.md")], ["maturity", P],
                      ["brief", P, "--profile", "UI", "--genesis", "greenfield"],
                      ["split", P, "--assess"], ["split", P, "--propose", "--source", str(fx / "proposal.json")],
                      ["split", P, "--confirm", "--ba", "Synthetic BA", "--tech", "Synthetic team"]]
            for argv in steps:
                code, text = _cli(argv)
                if code:
                    raise AssertionError(f"{argv}: {text[-500:]}")
    finally:
        os.chdir(old)


class ProjectScopeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tmp = tempfile.TemporaryDirectory()
        cls.work = Path(cls.tmp.name)
        run_project_flow(cls.work)
        cls.old = os.getcwd()
        os.chdir(cls.work)

    @classmethod
    def tearDownClass(cls) -> None:
        os.chdir(cls.old)
        cls.tmp.cleanup()

    def test_project_scope_is_todays_paths(self) -> None:
        base = workspace_path(P)
        scope = series_scope(P)
        self.assertIsInstance(scope, SeriesScope)
        self.assertIsNone(scope.change_id)
        self.assertEqual(scope.base, base)
        self.assertEqual(scope.series_dir, base / "02_requirements" / "series")
        self.assertEqual(scope.release_brief("r1"), base / "02_requirements" / "r1" / "project-brief.md")
        self.assertEqual(scope.assessment_dir, base / "01_discovery")
        self.assertEqual(scope.gaps_path, base / "01_discovery" / "gaps.md")
        self.assertEqual(scope.brief_sha256, brief_hash(base / "02_requirements" / "project-brief.md"))
        self.assertEqual(scope.brief_label, "02_requirements/project-brief.md")
        self.assertEqual(scope.brief_text, (base / "02_requirements" / "project-brief.md").read_text(encoding="utf-8"))
        self.assertEqual(scope.language, "en")

    def test_project_without_brief_gives_empty_text(self) -> None:
        with tempfile.TemporaryDirectory() as other:
            old = os.getcwd()
            os.chdir(other)
            try:
                _cli(["init", "NOBR"])
                scope = series_scope("NOBR")
                self.assertEqual(scope.brief_text, "")
                self.assertEqual(scope.brief_sha256, "")
            finally:
                os.chdir(old)

    def test_project_series_bytes_unchanged(self) -> None:
        """RF 3: the same run as Task 0 gives the sha256 recorded before the refactor."""
        base = workspace_path(P)
        found = {}
        files = list((base / "01_discovery").glob("split_assessment.*")) + list((base / "02_requirements" / "series").rglob("*")) \
            + list(base.glob("02_requirements/r*/project-brief.md"))
        for path in sorted(files):
            if path.is_file():
                found[path.relative_to(base).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
        self.assertEqual(found, BASELINE)


class ChangeScopeTest(SyncCase):
    PID = "SSCO"

    def test_change_scope_paths_and_text(self) -> None:
        base = workspace_path(self.PID)
        scope = series_scope(self.PID, "CHG-001")
        self.assertEqual(scope.change_id, "CHG-001")
        self.assertEqual(scope.series_dir, base / "02_requirements" / "CHG-001" / "series")
        self.assertEqual(scope.assessment_dir, base / "01_discovery" / "CHG-001")
        self.assertEqual(scope.release_brief("r2"), base / "02_requirements" / "CHG-001" / "r2" / "project-brief.md")
        self.assertEqual(scope.gaps_path, change_gaps_path(base, "CHG-001"))
        self.assertEqual(scope.brief_text, render_change_deliverable_parts(self.PID, "CHG-001", False, ("GAP-SPLIT-",))[0])
        self.assertEqual(scope.brief_sha256, hashlib.sha256(normalized_change_text(scope.brief_text).encode("utf-8")).hexdigest())
        self.assertIsInstance(scope.compile_report, dict)
        self.assertEqual(scope.language, "es")
        with self.assertRaises(GateRefusal) as caught:
            series_scope(self.PID, "CHG-999")
        with self.assertRaises(GateRefusal) as expected:
            get_change(self.PID, "CHG-999")
        self.assertEqual(str(caught.exception), str(expected.exception))

    def test_sealed_text_wins(self) -> None:
        base = workspace_path(self.PID)
        sealed = base / "08_context_packs" / "sealed-brief.md"
        sealed.parent.mkdir(parents=True, exist_ok=True)
        sealed.write_text("# Brief sellado de prueba\n", encoding="utf-8")
        forget_read_snapshots()
        changes = {key: dict(value) for key, value in list_changes(self.PID).items()}
        changes["CHG-001"]["final_export"] = {"path": "08_context_packs/sealed-brief.md", "brief_sha": "x"}
        update_state(self.PID, changes=changes)
        forget_read_snapshots()
        with patch("sentinel.readiness_verdict._final_export_current", return_value=True):
            scope = series_scope(self.PID, "CHG-001")
        self.assertEqual(scope.brief_text, "# Brief sellado de prueba\n")
        self.assertEqual(scope.brief_sha256, hashlib.sha256(normalized_change_text("# Brief sellado de prueba\n").encode("utf-8")).hexdigest())
        self.assertEqual(scope.compile_report, {})  # the sealed export has no compile report next to it: none, not the draft's
        self.assertEqual(scope.brief_label, "08_context_packs/sealed-brief.md")


if __name__ == "__main__":
    unittest.main()
