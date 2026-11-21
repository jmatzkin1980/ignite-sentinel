"""IMP-386: /brief --change compiles the brief of a change and never the project's."""
from __future__ import annotations

import io
import json
import shutil
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import SnapshotWorkspaceCase, run_ok  # noqa: E402

from sentinel.cli import main  # noqa: E402
from sentinel.workspace import workspace_path  # noqa: E402
from tests.test_mcp_change import _argv  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def run_err(argv: list[str]) -> tuple[int, str]:
    err = io.StringIO()
    with redirect_stdout(io.StringIO()), redirect_stderr(err):
        code = main(list(argv))
    return code, err.getvalue()


def tree(base: Path) -> dict[str, bytes]:
    return {str(p.relative_to(base)): p.read_bytes() for p in sorted(base.rglob("*")) if p.is_file()}


class ChangeBriefCli(SnapshotWorkspaceCase):
    change_id = "CHG-001"

    @classmethod
    def build_workspace(cls):
        shutil.copy(FIXTURES / "change_borrador.md", Path.cwd() / "pedido.md")
        run_ok(["init", "BORR"])
        run_ok(["ingest", "BORR", "--source", "pedido.md", "--change"])

    @property
    def base(self) -> Path:
        return workspace_path("BORR")

    def test_brief_change_writes_only_the_change_brief(self):
        out = json.loads(run_ok(["brief", "BORR", "--change", self.change_id]))
        self.assertEqual(self.change_id, out["change_id"])
        self.assertTrue((self.base / "02_requirements" / self.change_id / "project-brief.md").exists())
        self.assertFalse((self.base / "02_requirements" / "project-brief.md").exists())

    def test_unknown_change_is_refused(self):
        code, err = run_err(["brief", "BORR", "--change", "CHG-999"])
        self.assertNotEqual(code, 0)
        self.assertIn("CHG-999 no es un cambio abierto de BORR", err)
        self.assertIn(self.change_id, err)

    def test_plain_brief_on_change_only_workspace_refused(self):
        before = tree(self.base)
        code, err = run_err(["brief", "BORR"])
        self.assertNotEqual(code, 0)
        self.assertIn("sólo tiene cambios", err)
        self.assertIn(f"/brief BORR --change {self.change_id}", err)
        self.assertEqual(before, tree(self.base))

    def test_plain_brief_with_settings_on_change_only_workspace_writes_nothing(self):
        before = tree(self.base)
        code, _ = run_err(["brief", "BORR", "--profile", "UI"])
        self.assertNotEqual(code, 0)
        self.assertEqual(before, tree(self.base))

    def test_change_and_profile_flags_together_refused(self):
        before = tree(self.base)
        for flags in (["--profile", "UI"], ["--genesis", "greenfield"], ["--validation-direction", "built"],
                      ["--brief-version", "2"]):
            code, err = run_err(["brief", "BORR", "--change", self.change_id, *flags])
            self.assertEqual(3, code, flags)
            self.assertIn(flags[0], err)
        self.assertEqual(before, tree(self.base))

    def test_mcp_brief_change_argv(self):
        self.assertEqual(["brief", "P", "--change", "CHG-001"], _argv("sentinel_brief", project_id="P", change="CHG-001"))
        self.assertEqual(["brief", "P"], _argv("sentinel_brief", project_id="P"))


class ProjectBriefUnchanged(SnapshotWorkspaceCase):
    @classmethod
    def build_workspace(cls):
        shutil.copy(FIXTURES / "change_borrador.md", Path.cwd() / "pedido.md")
        run_ok(["init", "MIXTO"])
        run_ok(["ingest", "MIXTO", "--source", "pedido.md"])
        run_ok(["ingest", "MIXTO", "--source", "pedido.md", "--change"])
        run_ok(["init", "VACIO"])

    def test_project_with_requirements_and_open_change_compiles_plain_brief(self):
        base = workspace_path("MIXTO")
        self.assertTrue((base / "02_requirements" / "requirements.md").exists())
        out = json.loads(run_ok(["brief", "MIXTO"]))
        self.assertTrue(out["project_brief"].endswith("project-brief.md"))
        self.assertTrue((base / "02_requirements" / "project-brief.md").exists())

    def test_fresh_project_keeps_the_ingest_refusal(self):
        code, err = run_err(["brief", "VACIO"])
        self.assertNotEqual(code, 0)
        self.assertIn("Cannot generate project brief before /ingest", err)


if __name__ == "__main__":
    unittest.main()
