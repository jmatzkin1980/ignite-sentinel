"""IMP-267b (H17a): derivations by release (`--release rN`).

The pipeline runs unchanged inside a mirror workspace whose brief is the release
brief, and its outputs land in `03_specs/<rN>/`, `04_backlog/<rN>/`,
`06_traceability/<rN>/` and `08_context_packs/<rN>/`. The project's state and its
own derived artifacts are never touched; without `--release` nothing changes.
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path

from sentinel.cli import main
from sentinel.release_scope import remap, scoped_argv

ROOT = Path(__file__).resolve().parent
VALID = json.loads((ROOT / "fixtures" / "evals" / "partition" / "valid-partition.json").read_text(encoding="utf-8"))


class PureTests(unittest.TestCase):
    def test_scoped_argv_drops_release_and_absolutizes_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            evidence = Path(tmp) / "e.md"
            evidence.write_text("x", encoding="utf-8")
            old = os.getcwd()
            os.chdir(tmp)
            try:
                release, argv = scoped_argv(["story-status", "P", "--release", "r2", "--story", "US-001",
                                             "--set", "Ready", "--evidence", "e.md"])
            finally:
                os.chdir(old)
        self.assertEqual(release, "r2")
        self.assertNotIn("--release", argv)
        self.assertTrue(Path(argv[argv.index("--evidence") + 1]).is_absolute())
        self.assertEqual(scoped_argv(["specs", "P", "--release=r2.1"])[0], "r2.1")

    def test_remap_points_to_the_release_folders(self) -> None:
        root = Path("C:/repo") if os.name == "nt" else Path("/repo")
        mirror = (root / "workspaces" / "P" / ".series_work" / "r2" / "workspaces" / "P").resolve()
        text = f"{mirror.as_posix()}/03_specs/prd.md · `03_specs/specs.md` · 04_backlog/US-001.md · 02_requirements/project-brief.md"
        out = remap(text, "P", "r2", root)
        self.assertIn((root / "workspaces" / "P").resolve().as_posix() + "/03_specs/r2/prd.md", out)
        self.assertIn("`03_specs/r2/specs.md`", out)
        self.assertIn("04_backlog/r2/US-001.md", out)
        self.assertIn("02_requirements/r2/project-brief.md", out)
        self.assertEqual(remap(out, "P", "r2", root), out)  # idempotent


class ReleaseScopeFlow(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.old = os.getcwd()
        cls.tmp = tempfile.TemporaryDirectory()
        os.chdir(cls.tmp.name)
        cls.base = Path("workspaces") / "NOVA"
        cls.out = {}
        cls.cli("init", "NOVA", "--brief-version", "1")
        cls.cli("ingest", "NOVA", "--source", str(ROOT / "fixtures" / "complete_requirement.md"))
        cls.cli("maturity", "NOVA")
        (cls.base / "02_requirements" / "project-brief.md").write_text(VALID["brief"], encoding="utf-8")
        from sentinel.discovery import parse_gap_rows, render_gaps

        gaps = cls.base / "01_discovery" / "gaps.md"
        rows = [r for r in parse_gap_rows(gaps.read_text(encoding="utf-8")) if r.get("id") != "NONE"]
        rows += [{"id": g, "lens": "business", "severity": "low", "status": "OPEN", "description": "synthetic gap",
                  "question": "Which?", "evidence_mention": "x", "origin": "agent", "resolution_note": ""}
                 for g in VALID["open_gaps"]]
        gaps.write_text(render_gaps("NOVA", rows, "REQ-001", "en"), encoding="utf-8")
        Path("proposal.json").write_text(json.dumps(VALID["payload"]), encoding="utf-8")
        cls.cli("split", "NOVA", "--propose", "--source", "proposal.json")
        cls.cli("split", "NOVA", "--confirm", "--ba", "Ana", "--tech", "Core")
        cls.state_before = (cls.base / "state.json").read_bytes()
        cls.codes = {name: cls.cli(*argv) for name, argv in {
            "specs": ("specs", "NOVA", "--release", "r1"),
            "backlog": ("backlog", "NOVA", "--release", "r1"),
            "status": ("status", "NOVA", "--release", "r1"),
            "view": ("view", "NOVA", "--release", "r1", "--artifact", "prd"),
            "trace": ("trace", "NOVA", "--release", "r1"),
        }.items()}
        cls.state_after = (cls.base / "state.json").read_bytes()

    @classmethod
    def tearDownClass(cls) -> None:
        os.chdir(cls.old)
        cls.tmp.cleanup()

    @classmethod
    def cli(cls, *argv: str) -> int:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            code = main(list(argv))
        cls.out[" ".join(argv[:1] + argv[2:])] = buf.getvalue()
        return code

    def test_commands_succeed(self) -> None:
        self.assertEqual(self.codes, {"specs": 0, "backlog": 0, "status": 0, "view": 0, "trace": 0}, self.out)

    def test_outputs_land_in_the_release_folders(self) -> None:
        for rel in ("03_specs/r1/prd.md", "03_specs/r1/specs.md", "04_backlog/r1/EPIC-001.md", "04_backlog/r1/US-001.md",
                    "04_backlog/r1/SLICE-PLAN.md", "08_context_packs/r1/slice_plan.json", "08_context_packs/r1/views/prd.html",
                    "06_traceability/r1/traceability_matrix.md"):
            self.assertTrue((self.base / rel).is_file(), rel)
        prd = (self.base / "03_specs" / "r1" / "prd.md").read_text(encoding="utf-8")
        self.assertIn("`02_requirements/r1/project-brief.md`", prd)
        self.assertIn("`08_context_packs/r1/specs_generation.json`", prd)
        self.assertNotIn(".series_work", prd)

    def test_the_project_is_untouched(self) -> None:
        self.assertEqual(self.state_before, self.state_after)
        self.assertFalse((self.base / "03_specs" / "prd.md").exists())
        self.assertFalse((self.base / "04_backlog" / "EPIC-001.md").exists())

    def test_the_verdict_covers_the_release(self) -> None:
        status = json.loads(self.out["status --release r1"])
        verdict = status.get("readiness_verdict") or status.get("verdict") or {}
        text = json.dumps(status)
        self.assertIn('"release": "r1"', text)
        self.assertNotIn("named outside its scope", text)
        self.assertIsInstance(verdict, (dict, str))

    def test_printed_paths_point_to_the_release(self) -> None:
        self.assertIn("04_backlog", self.out["backlog --release r1"])
        self.assertNotIn(".series_work", self.out["backlog --release r1"])

    def test_acceptance_freeze_stays_in_the_release(self) -> None:
        code = self.cli("story-status", "NOVA", "--release", "r1", "--story", "US-001", "--set", "Ready")
        mirror_state = json.loads((self.base / ".series_work" / "r1" / "workspaces" / "NOVA" / "state.json").read_text(encoding="utf-8"))
        main_state = json.loads((self.base / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(code, 0, self.out["story-status --release r1 --story US-001 --set Ready"])
        self.assertNotIn("US-001", main_state.get("acceptance_criteria_freezes", {}))
        self.assertIn("US-001", mirror_state.get("acceptance_criteria_freezes", {}))

    def test_unknown_release_and_no_series_are_refused(self) -> None:
        self.assertNotEqual(self.cli("specs", "NOVA", "--release", "r9"), 0)
        self.assertIn("not a release of the confirmed series", self.out["specs --release r9"])
        self.cli("init", "BARE", "--brief-version", "1")
        self.assertNotEqual(self.cli("specs", "BARE", "--release", "r1"), 0)
        self.assertIn("confirmed release series", self.out["specs --release r1"])


if __name__ == "__main__":
    unittest.main()
