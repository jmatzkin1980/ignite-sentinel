"""IMP-386: /view and /export with --change name their files CHG-nnn-* and never touch the project's."""
from __future__ import annotations

import io
import json
import sys
import unittest
from unittest.mock import patch
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import SnapshotWorkspaceCase, class_deferred, complete_extraction, run_ok  # noqa: E402

from sentinel.cli import main  # noqa: E402
from sentinel.workspace import workspace_path  # noqa: E402
from tests.test_change_brief import _build  # noqa: E402
from tests.test_mcp_change import _argv  # noqa: E402

CHG = "CHG-001"


def run_err(argv: list[str]) -> tuple[int, str]:
    err = io.StringIO()
    with redirect_stdout(io.StringIO()), redirect_stderr(err):
        code = main(list(argv))
    return code, err.getvalue()


def tree(base: Path) -> dict[str, bytes]:
    return {str(p.relative_to(base)): p.read_bytes() for p in sorted(base.rglob("*")) if p.is_file()}


class ChangeViewExport(SnapshotWorkspaceCase):
    @classmethod
    def build_workspace(cls):
        _build()
        run_ok(["brief", "BORR", "--change", CHG])

    @property
    def base(self) -> Path:
        return workspace_path("BORR")

    def test_export_change_brief_is_a_draft_with_banner(self):
        out = json.loads(run_ok(["export", "BORR", "--artifact", "brief", "--change", CHG]))
        target = self.base / "08_context_packs" / "exports" / f"{CHG}-project-brief.md"
        self.assertTrue(target.exists())
        self.assertEqual(target.as_posix(), out["path"])
        self.assertEqual("draft", out["deliverable"])
        self.assertIn("BORRADOR", target.read_text(encoding="utf-8"))  # the change is in Spanish
        self.assertFalse((self.base / "08_context_packs" / "exports" / "project-brief.md").exists())

    def test_export_change_brief_final_refused_with_blocking(self):
        before = tree(self.base / "08_context_packs")
        code, err = run_err(["export", "BORR", "--artifact", "brief", "--change", CHG, "--final"])
        self.assertNotEqual(code, 0)
        self.assertIn("pending marks", err)
        self.assertEqual(before, tree(self.base / "08_context_packs"))

    def test_export_change_gaps_md_and_interview(self):
        run_ok(["export", "BORR", "--artifact", "gaps", "--change", CHG])
        exports = self.base / "08_context_packs" / "exports"
        self.assertTrue((exports / f"{CHG}-gaps.md").exists())
        out = json.loads(run_ok(["export", "BORR", "--artifact", "gaps", "--change", CHG, "--format", "interview"]))
        target = exports / f"{CHG}-gaps-interview.md"
        self.assertEqual(target.as_posix(), out["path"])
        text = target.read_text(encoding="utf-8")
        self.assertIn("GAP-", text)
        self.assertFalse((exports / "gaps-interview.md").exists())

    def test_spanish_change_exports_spanish_banner_and_interview(self):
        # The project language is "auto" (resolves to en); the change was ingested in Spanish.
        out = json.loads(run_ok(["export", "BORR", "--artifact", "brief", "--change", CHG]))
        self.assertIn("BORRADOR", Path(out["path"]).read_text(encoding="utf-8"))
        out = json.loads(run_ok(["export", "BORR", "--artifact", "gaps", "--change", CHG, "--format", "interview"]))
        text = Path(out["path"]).read_text(encoding="utf-8")
        self.assertIn("Guion de entrevista", text)
        self.assertNotIn("Interview script", text)

    def test_interview_refusal_names_the_change_gaps_path(self):
        from sentinel.discovery import build_interview_script
        from sentinel.errors import GateRefusal

        (self.base / "01_discovery" / CHG / "gaps.md").unlink()
        with self.assertRaises(GateRefusal) as caught:
            build_interview_script("BORR", change_id=CHG)
        self.assertIn(f"01_discovery/{CHG}/gaps.md", str(caught.exception))

    def test_export_change_faq_is_the_changes_own(self):
        # IMP-412: the FAQ takes --change (the decided questions of the change), into its own file
        out = json.loads(run_ok(["export", "BORR", "--artifact", "gaps", "--change", CHG, "--format", "faq"]))
        self.assertTrue(out["path"].endswith(f"exports/{CHG}-gaps-faq.md"))
        self.assertFalse((self.base / "08_context_packs" / "exports" / "gaps-faq.md").exists())

    def test_view_change_brief_html(self):
        out = json.loads(run_ok(["view", "BORR", "--artifact", "brief", "--change", CHG]))
        views = self.base / "08_context_packs" / "views"
        self.assertTrue((views / f"{CHG}-brief.html").exists())
        self.assertEqual(str(views / f"{CHG}-brief.html"), out["path"])
        self.assertFalse((views / "brief.html").exists())
        self.assertIn(f"{CHG}/project-brief.md", out["source_path"])

    def test_view_change_gaps_html(self):
        run_ok(["view", "BORR", "--artifact", "gaps", "--change", CHG])
        views = self.base / "08_context_packs" / "views"
        self.assertTrue((views / f"{CHG}-gaps.html").exists())
        self.assertFalse((views / "gaps.html").exists())

    def test_project_exports_untouched(self):
        exports = self.base / "08_context_packs" / "exports"
        exports.mkdir(parents=True, exist_ok=True)
        mine = exports / "project-brief.md"
        mine.write_bytes(b"project export\n")
        run_ok(["export", "BORR", "--artifact", "brief", "--change", CHG])
        self.assertEqual(b"project export\n", mine.read_bytes())

    def test_unsupported_artifact_with_change_refused(self):
        before = tree(self.base)
        for cmd in (["export", "BORR", "--artifact", "prd"], ["view", "BORR", "--artifact", "prd"]):
            code, err = run_err([*cmd, "--change", CHG])
            self.assertEqual(3, code, cmd)
            self.assertIn("--change", err)
        self.assertEqual(before, tree(self.base))

    def test_unknown_change_refused(self):
        code, err = run_err(["export", "BORR", "--artifact", "brief", "--change", "CHG-999"])
        self.assertNotEqual(code, 0)
        self.assertIn("CHG-999 no es un cambio abierto", err)

    def test_plain_view_and_export_on_change_only_workspace_refuse(self):
        before = tree(self.base)
        for cmd in (["view", "BORR", "--artifact", "brief"], ["view", "BORR", "--artifact", "gaps"],
                    ["export", "BORR", "--artifact", "brief"], ["export", "BORR", "--artifact", "gaps"]):
            code, err = run_err(cmd)
            self.assertNotEqual(code, 0, cmd)
            self.assertIn(f"--change {CHG}", err)
        self.assertEqual(before, tree(self.base))

    def test_mcp_argv(self):
        self.assertEqual(["view", "P", "--artifact", "brief", "--change", "CHG-001"],
                         _argv("sentinel_view", project_id="P", artifact="brief", change="CHG-001"))
        self.assertEqual(["export", "P", "--artifact", "brief", "--format", "md", "--change", "CHG-001"],
                         _argv("sentinel_export", project_id="P", artifact="brief", change="CHG-001"))
        self.assertEqual(["export", "P", "--artifact", "brief", "--format", "md"],
                         _argv("sentinel_export", project_id="P", artifact="brief"))


BLOCKING_ANSWERS = "\n".join(
    f"### {gap}\n- Respuesta: {text}\n- Owner / fuente: Jefa de Compras\n"
    f"- Evidencia o referencia: Acta de la reunión de relevamiento\n- Estado de decisión: confirmado\n- Motivo de cierre: answered\n"
    for gap, text in (("GAP-OBJECTIVE", "Que el analista retome el alta más tarde."), ("GAP-USERS", "Analistas de Compras."),
                      ("GAP-ACCEPTANCE", "Cuando el analista guarda, el sistema conserva lo cargado."))
)


class ChangeFinalWithDeferredMarks(SnapshotWorkspaceCase):
    @classmethod
    def build_workspace(cls):
        _build(extra=BLOCKING_ANSWERS)
        run_ok(["brief", "BORR", "--change", CHG])

    def test_final_export_with_only_deferred_marks_is_final(self):
        # IMP-406: `--final` also needs a verdict that is not NOT_READY: extraction done, crosses waived, questions classed
        complete_extraction("BORR", CHG)
        run_ok(["brief", "BORR", "--change", CHG])
        class_deferred("BORR", CHG)
        # what this test is about is the deferred marks; the requirement rows have their own tests
        with patch("sentinel.readiness_verdict._has_unit_rows", return_value=True):
            out = json.loads(run_ok(["export", "BORR", "--artifact", "brief", "--change", CHG, "--final"]))
        self.assertEqual("final", out["deliverable"])
        self.assertGreater(int(out["deferred_marks"]), 0)
        target = workspace_path("BORR") / "08_context_packs" / "exports" / f"{CHG}-project-brief.md"
        self.assertNotIn("BORRADOR", target.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
