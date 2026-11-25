"""IMP-396: `/validate --change CHG-nnn` runs four structural checks over one change and writes nothing."""
from __future__ import annotations

import hashlib
import io
import json
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import SnapshotWorkspaceCase, build_matured_workspace, gap_acceptance_answer, run_cli, run_ok  # noqa: E402
from sentinel import mcp as sentinel_mcp  # noqa: E402
from sentinel.change_validation import validate_change  # noqa: E402
from sentinel.cli import main as cli_main  # noqa: E402
from sentinel.validation import validate_project  # noqa: E402
from sentinel.workspace import workspace_path  # noqa: E402
from test_change_specs import ALL_ANSWERS, PROJECT_EARS, PROJECT_RAW, answer, open_change, units_dir  # noqa: E402
from test_mcp_parity import _tools  # noqa: E402

CID = "CHG-001"
# What every command, /status included, records about itself; no artifact.
BOOKKEEPING = {"state.json", "state.json.bak", "command_log.jsonl", "command_protocol_log.md"}
BRIEF = f"02_requirements/{CID}/project-brief.md"


def edit(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    assert old in text, (path, old)
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def story_path(story_id: str = "US-001") -> Path:
    return workspace_path("BORR") / "04_backlog" / f"{story_id}.md"


def checks(result: dict) -> dict:
    return {c["id"]: c["status"] for c in result["checks"]}


def snapshot(project: str) -> dict:
    base = workspace_path(project)
    return {p.relative_to(base).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in base.rglob("*") if p.is_file() and p.name not in BOOKKEEPING}


class ChangeValidationSpecsOnly(SnapshotWorkspaceCase):
    @classmethod
    def build_workspace(cls):
        run_ok(["init", "BORR"])
        cid = open_change("BORR")
        answer("BORR", cid, "a.md", ALL_ANSWERS)
        run_ok(["brief", "BORR", "--change", cid])
        run_ok(["specs", "BORR", "--change", cid])

    def test_without_backlog_skips_the_story_checks(self):
        result = validate_change("BORR", CID)
        self.assertEqual(result["verdict"], "VALID")
        self.assertEqual(checks(result), {
            "unit_citations": "PASS", "preserved_pass_to_pass": "SKIP",
            "rows_have_surfaces": "PASS", "stories_inside_border": "PASS",
        })

    def test_without_units_skips_unit_checks(self):
        for path in units_dir("BORR").glob("SPEC-U-*.md"):
            path.unlink()
        result = validate_change("BORR", CID)
        self.assertEqual(checks(result)["unit_citations"], "SKIP")
        self.assertEqual(checks(result)["stories_inside_border"], "SKIP")


class ChangeValidation(SnapshotWorkspaceCase):
    @classmethod
    def build_workspace(cls):
        run_ok(["init", "BORR"])
        cid = open_change("BORR")
        answer("BORR", cid, "a.md", ALL_ANSWERS)
        run_ok(["brief", "BORR", "--change", cid])
        run_ok(["specs", "BORR", "--change", cid])
        run_ok(["backlog", "BORR", "--change", cid])

    def test_full_walk_is_valid_and_writes_nothing(self):
        before = snapshot("BORR")
        result = validate_change("BORR", CID)
        self.assertEqual(result["verdict"], "VALID")
        self.assertEqual(result["findings"], [])
        self.assertEqual(checks(result), {
            "unit_citations": "PASS", "preserved_pass_to_pass": "PASS",
            "rows_have_surfaces": "PASS", "stories_inside_border": "PASS",
        })
        self.assertEqual((result["project_id"], result["change_id"]), ("BORR", CID))
        self.assertIsInstance(result["warnings"], list)
        code, out = run_cli(["validate", "BORR", "--change", CID])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["verdict"], "VALID")
        self.assertEqual(snapshot("BORR"), before)

    def test_unit_without_brief_in_sources(self):
        edit(units_dir("BORR") / "SPEC-U-001.md", f"  - {BRIEF}\n", "")
        result = validate_change("BORR", CID)
        self.assertEqual(result["verdict"], "INVALID")
        self.assertEqual(checks(result)["unit_citations"], "FAIL")
        self.assertTrue(any("SPEC-U-001" in f and BRIEF in f and f"--change {CID}" in f for f in result["findings"]))
        code, _ = run_cli(["validate", "BORR", "--change", CID])
        self.assertEqual(code, 5)

    def test_unit_pointing_at_a_missing_row(self):
        edit(units_dir("BORR") / "SPEC-U-001.md", "ears:\n  - REQ-EARS-001", "ears:\n  - REQ-EARS-099")
        result = validate_change("BORR", CID)
        self.assertEqual(checks(result)["unit_citations"], "FAIL")
        self.assertTrue(any("REQ-EARS-099" in f for f in result["findings"]))

    def test_story_without_the_preserved_pass_to_pass(self):
        path = story_path("US-002")
        lines = [ln.replace("pass-to-pass", "regression") if ln.startswith("| AC-002-06 |") else ln
                 for ln in path.read_text(encoding="utf-8").splitlines()]
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        result = validate_change("BORR", CID)
        self.assertEqual(checks(result)["preserved_pass_to_pass"], "FAIL")
        self.assertTrue(any("US-002" in f and "REQ-EARS-002" in f for f in result["findings"]))
        self.assertFalse(any("US-001" in f and "REQ-EARS-002" in f for f in result["findings"]))

    def test_row_without_surface(self):
        path = workspace_path("BORR") / "02_requirements" / CID / "requirements.md"
        text = path.read_text(encoding="utf-8").replace("| - | Tabla de proveedores |", "| - |  |", 1)
        path.write_text(text, encoding="utf-8")
        result = validate_change("BORR", CID)
        self.assertEqual(checks(result)["rows_have_surfaces"], "FAIL")
        self.assertTrue(any("REQ-EARS-001" in f for f in result["findings"]))
        finding = next(f for f in result["findings"] if "REQ-EARS-001" in f)
        self.assertIn("--source", finding)
        self.assertRegex(finding, r"GAP-[A-Z-]+")

    def test_row_with_surface_outside_the_border(self):
        path = workspace_path("BORR") / "02_requirements" / CID / "requirements.md"
        text = path.read_text(encoding="utf-8").replace("| - | Tabla de proveedores |", "| - | Pantalla Fantasma |", 1)
        path.write_text(text, encoding="utf-8")
        result = validate_change("BORR", CID)
        self.assertEqual(checks(result)["rows_have_surfaces"], "FAIL")
        self.assertTrue(any("Pantalla Fantasma" in f for f in result["findings"]))

    def test_story_with_surface_outside_the_border(self):
        edit(story_path("US-002"), "surfaces:\n  - Tabla de proveedores", "surfaces:\n  - Pantalla Fantasma")
        result = validate_change("BORR", CID)
        self.assertEqual(result["verdict"], "INVALID")
        self.assertEqual(checks(result)["stories_inside_border"], "FAIL")
        self.assertTrue(any("US-002" in f and "Pantalla Fantasma" in f for f in result["findings"]))

    def test_unit_without_surfaces(self):
        edit(units_dir("BORR") / "SPEC-U-001.md", "surfaces:\n  - Tabla de proveedores\n", "")
        result = validate_change("BORR", CID)
        self.assertEqual(checks(result)["stories_inside_border"], "FAIL")
        self.assertTrue(any("SPEC-U-001" in f for f in result["findings"]))

    def test_escalation_warnings_are_reported(self):
        warning = {"trigger": "new_actors", "surfaces": ["X"], "rows": [], "message": "m"}
        with patch("sentinel.change_validation.escalation_warnings", lambda project, change: [warning]):
            result = validate_change("BORR", CID)
        self.assertEqual(result["warnings"], [warning])
        self.assertEqual(result["verdict"], "VALID")

    def test_cli_unknown_change_refused(self):
        code, _ = run_cli(["validate", "BORR", "--change", "CHG-009"])
        self.assertEqual(code, 4)

    def test_release_with_change_refused_in_the_change_language(self):
        err = io.StringIO()
        with redirect_stdout(io.StringIO()), redirect_stderr(err):
            code = cli_main(["validate", "BORR", "--change", CID, "--release", "r1"])
        self.assertEqual(code, 3)
        self.assertIn("--release", err.getvalue())
        self.assertIn(f"/validate BORR --change {CID}", err.getvalue())

    def test_mcp_accepts_change(self):
        captured: list = []
        with patch.object(sentinel_mcp, "run_cli", lambda arguments: captured.append(arguments) or {"exit_code": 0}):
            _tools()["sentinel_validate"](project_id="BORR", change=CID)
            _tools()["sentinel_validate"](project_id="BORR")
        self.assertEqual(captured[0], ["validate", "BORR", "--change", CID])
        self.assertEqual(captured[1], ["validate", "BORR"])

    def test_plain_validate_in_change_only_workspace_refuses(self):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = cli_main(["validate", "BORR"])
        self.assertEqual(code, 4)
        combined = err.getvalue() + out.getvalue()
        self.assertIn(f"--change {CID}", combined)
        self.assertNotIn("backlog_readiness_audit", combined)


class ChangeValidationPathA(SnapshotWorkspaceCase):
    @classmethod
    def build_workspace(cls):
        build_matured_workspace("PLAIN", PROJECT_RAW, gap_acceptance_answer(PROJECT_EARS), backlog=False)

    def test_project_validation_is_untouched_without_changes(self):
        code, out = run_cli(["validate", "PLAIN"])
        self.assertIn(code, (0, 3))
        self.assertEqual(json.loads(out), json.loads(json.dumps(validate_project("PLAIN"))))
        self.assertNotIn("checks", json.loads(out))


if __name__ == "__main__":
    unittest.main()
