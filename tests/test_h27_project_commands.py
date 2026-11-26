"""IMP-420 (H27 inc 6b) task 6: /extract and /cross without --change work on the project's request."""
from __future__ import annotations

import inspect
import io
from contextlib import redirect_stderr, redirect_stdout
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import ProjectExtractionCase, run_ok  # noqa: E402
from test_golden_artifacts import RAW_ES  # noqa: E402

from sentinel.cli import main  # noqa: E402
from sentinel.core.io import forget_read_snapshots  # noqa: E402
from sentinel.crosses.claims import cross_sources  # noqa: E402
from sentinel.mcp import TOOL_DESCRIPTIONS  # noqa: E402
from sentinel.workspace import workspace_path  # noqa: E402

PID = ProjectExtractionCase.PID
PROJECT = ProjectExtractionCase.FIXTURES
NO_IDS = "no tiene reglas, criterios, historias ni decisiones con id"
CHANGE_ONLY = "es sólo del cambio: va con --change CHG-NNN"
INGEST_KEYS = sorted([  # sentinel/discovery/intake.py: the result of /ingest as of 0.33
    "raw_id", "secret_redactions", "injection_signals", "source_conflicts", "source_format", "secret_alerts",
    "requirement_id", "gap_id", "decision_id", "seed_id", "discovery_log_id", "lens_review_id", "knowledge_ledger_id",
    "source_synthesis_id", "requirement_unit_ids", "requirement_unit_deltas", "context_pack", "replaced"])


def run_cli(argv: list[str]) -> tuple[int, str]:
    """Like helpers.run_cli, but the refusal text (stderr) is kept."""
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = main(list(argv))
    return code, out.getvalue() + err.getvalue()


def tree(base: Path) -> set[str]:
    return {p.relative_to(base).as_posix() for p in base.rglob("*") if p.is_file()}


class ProjectCommands(ProjectExtractionCase):
    def test_extract_without_change_builds_project_inventory(self):
        result = json.loads(run_ok(["extract", PID]))
        self.assertEqual(result["scope"], "project")
        self.assertIsNone(result["change_id"])
        self.assertTrue((workspace_path(PID) / "02_requirements" / "extraction" / "inventory.json").is_file())
        self.assertTrue(result["message"].startswith(f"{PID}:"))
        self.assertEqual(result["next"]["key"], json.loads(run_ok(["next", PID]))["key"])
        self.assertEqual(result["next"], result["next_step"])

    def test_cross_without_change_records_project_cross(self):
        ids = cross_sources(PID, None)
        text = (PROJECT / "cruce_contradicciones.md").read_text(encoding="utf-8").replace("F-PED", sorted(ids["pedido"])[0])
        Path("claims.md").write_text(text, encoding="utf-8")
        result = json.loads(run_ok(["cross", PID, "--kind", "contradicciones", "--claims", "claims.md"]))
        self.assertTrue((workspace_path(PID) / "01_discovery" / "crosses" / "contradicciones.json").is_file())
        self.assertEqual(result["scope"], "project")
        self.assertIsNone(result["change_id"])
        self.assertIn("next", result)
        status = json.loads(run_ok(["cross", PID]))
        self.assertEqual(status["scope"], "project")

    def test_change_only_options_refused(self):
        before = tree(workspace_path(PID))
        for argv in (["cross", PID, "--accept-new", "X", "--type", "T", "--name", "N"],
                     ["cross", PID, "--decline-new", "X", "--reason", "no"],
                     ["extract", PID, "--consolidate", "f.md"],
                     ["extract", PID, "--confirm-replacement", "RN-01"],
                     ["extract", PID, "--keep-text", "RN-01", "--gap", "GAP-X", "--reason", "r"]):
            code, out = run_cli(argv)
            self.assertNotEqual(code, 0, argv)
            self.assertIn(CHANGE_ONLY, out, argv)
        self.assertEqual(tree(workspace_path(PID)), before)

    def test_mcp_change_optional(self):
        from test_mcp_parity import _tools

        tools = _tools()
        for name in ("sentinel_extract", "sentinel_cross"):
            self.assertEqual(inspect.signature(tools[name]).parameters["change"].default, "")
        self.assertIn("project", TOOL_DESCRIPTIONS["extract"])
        self.assertIn("project", TOOL_DESCRIPTIONS["cross"])


class WithoutIds(unittest.TestCase):
    def setUp(self):
        self.old = Path.cwd()
        self.dir = tempfile.TemporaryDirectory()
        os.chdir(self.dir.name)

    def tearDown(self):
        os.chdir(self.old)
        self.dir.cleanup()

    def test_refused_without_ids(self):
        Path("golden.md").write_text(RAW_ES, encoding="utf-8")
        run_ok(["init", "GLD"])
        run_ok(["ingest", "GLD", "--source", "golden.md"])
        before = tree(workspace_path("GLD"))
        for argv in (["extract", "GLD"], ["cross", "GLD"]):
            code, out = run_cli(argv)
            self.assertNotEqual(code, 0)
            self.assertIn(NO_IDS, out)
            self.assertIn("/next GLD", out)
        self.assertEqual(tree(workspace_path("GLD")), before)

    def test_change_only_workspace_names_change(self):
        shutil.copy(ProjectExtractionCase.FIXTURES / "brief_alta_proveedores.md", "pedido.md")
        run_ok(["init", "CHO"])
        run_ok(["ingest", "CHO", "--source", "pedido.md", "--change"])
        forget_read_snapshots()
        before = tree(workspace_path("CHO"))
        for argv in (["extract", "CHO"], ["cross", "CHO"]):
            code, out = run_cli(argv)
            self.assertNotEqual(code, 0)
            self.assertIn("--change CHG-001", out)
        self.assertEqual(tree(workspace_path("CHO")), before)

    def test_ingest_result_unchanged(self):
        shutil.copy(ProjectExtractionCase.FIXTURES / "brief_alta_proveedores.md", "pedido.md")
        run_ok(["init", "ING"])
        result = json.loads(run_ok(["ingest", "ING", "--source", "pedido.md"]))
        self.assertEqual(sorted(result), INGEST_KEYS)
        self.assertNotIn("scope", result)
        self.assertFalse((workspace_path("ING") / "02_requirements" / "extraction").exists())


if __name__ == "__main__":
    unittest.main()
