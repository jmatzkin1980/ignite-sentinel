"""H27 inc 6b, task 1: `resolve_scope` reads the change or the project through one entry."""
from __future__ import annotations

import re
import unittest
from pathlib import Path

from sentinel.changes import Scope, change_gaps_path, change_language, get_change, project_request_rows, resolve_scope
from sentinel.change_requirements import change_requirements_path
from sentinel.crosses import cross_path, crosses_dir
from sentinel.errors import GateRefusal
from sentinel.extraction import extraction_dir
from sentinel.extraction.inventory import parse_request_elements
from sentinel.prior_decisions import prior_path
from sentinel.workspace import workspace_path
from tests.helpers import SnapshotWorkspaceCase, SyncCase, run_ok

FIXTURES = Path(__file__).resolve().parent / "fixtures"
PROJECT = FIXTURES / "project_extraction"
ROOT = Path(__file__).resolve().parents[1]


class ChangeScopeTest(SyncCase):
    PID = "SCOPECH"

    def test_change_entry_is_get_change(self) -> None:
        scope = resolve_scope(self.PID, self.CID)
        entry = get_change(self.PID, self.CID)
        self.assertIsInstance(scope, Scope)
        self.assertEqual(scope.entry, entry)
        self.assertEqual(scope.language, change_language(self.PID, entry))
        self.assertEqual((scope.project_id, scope.change_id), (self.PID, self.CID))
        self.assertFalse(scope.is_project)

    def test_unknown_change_refuses_like_get_change(self) -> None:
        with self.assertRaises(GateRefusal) as expected:
            get_change(self.PID, "CHG-999")
        with self.assertRaises(GateRefusal) as got:
            resolve_scope(self.PID, "CHG-999")
        self.assertEqual(str(got.exception), str(expected.exception))


class ProjectScopeTest(SnapshotWorkspaceCase):
    PID = "SCOPEPRJ"

    @classmethod
    def build_workspace(cls) -> None:
        root = Path.cwd()
        (root / "brief.md").write_text((PROJECT / "brief_alta_proveedores.md").read_text(encoding="utf-8"), encoding="utf-8")
        run_ok(["init", cls.PID])
        run_ok(["ingest", cls.PID, "--source", "brief.md"])

    def test_project_entry_shape(self) -> None:
        scope = resolve_scope(self.PID, None)
        self.assertTrue(scope.is_project)
        self.assertIsNone(scope.change_id)
        entry = scope.entry
        self.assertEqual(entry["sources"], ["F-01"])
        self.assertEqual(entry["border"], [])
        self.assertEqual(entry["round"], "project")
        self.assertEqual(entry["harvests"], [])
        self.assertEqual(entry["baseline_waived"], {"reason": "proyecto sin línea de base cargada"})
        self.assertEqual(scope.language, "es")

    def test_project_entry_excludes_change_rows(self) -> None:
        root = Path.cwd()
        (root / "pedido.md").write_text("# Pedido\n\nQue el alta tenga un estado visible para el analista.\n", encoding="utf-8")
        (root / "diseno.html").write_text((PROJECT / "prototipo-alta-proveedor.html").read_text(encoding="utf-8"), encoding="utf-8")
        run_ok(["ingest", self.PID, "--source", "pedido.md", "--change"])
        run_ok(["sources", self.PID, "--load", "diseno.html", "--role", "diseno_nuevo", "--change", "CHG-001"])
        self.assertEqual([r["id"] for r in project_request_rows(self.PID)], ["F-01"])
        self.assertEqual(resolve_scope(self.PID, None).entry["sources"], ["F-01"])
        self.assertIn("F-02", resolve_scope(self.PID, "CHG-001").entry["sources"])

    def test_project_paths(self) -> None:
        base = workspace_path(self.PID)
        self.assertEqual(extraction_dir(base, None), base / "02_requirements" / "extraction")
        self.assertEqual(crosses_dir(base, None), base / "01_discovery" / "crosses")
        self.assertEqual(cross_path(base, None, "diseno"), base / "01_discovery" / "crosses" / "diseno.json")
        self.assertEqual(change_gaps_path(base, None), base / "01_discovery" / "gaps.md")
        self.assertEqual(change_requirements_path(base, None), base / "02_requirements" / "requirements.md")
        self.assertEqual(prior_path(base, None), base / "01_discovery" / "prior_decisions.json")
        self.assertEqual(extraction_dir(base, "CHG-001"), base / "02_requirements" / "CHG-001" / "extraction")
        self.assertEqual(crosses_dir(base, "CHG-001"), base / "01_discovery" / "CHG-001" / "crosses")
        self.assertEqual(change_gaps_path(base, "CHG-001"), base / "01_discovery" / "CHG-001" / "gaps.md")
        self.assertEqual(change_requirements_path(base, "CHG-001"), base / "02_requirements" / "CHG-001" / "requirements.md")
        self.assertEqual(prior_path(base, "CHG-001"), base / "01_discovery" / "CHG-001" / "prior_decisions.json")


class ScopeSourceTest(unittest.TestCase):
    def test_extraction_and_crosses_read_scope_only(self) -> None:
        allowed = {Path("sentinel/crosses/surfaces.py"), Path("sentinel/extraction/consolidation.py")}
        found = set()
        for folder in ("extraction", "crosses"):
            for path in (ROOT / "sentinel" / folder).glob("*.py"):
                if re.search(r"(?<![\w.])get_change\(", path.read_text(encoding="utf-8")):
                    found.add(path.relative_to(ROOT))
        self.assertEqual({Path(str(p).replace("\\", "/")) for p in found}, allowed)

    def test_fixture_has_elements(self) -> None:
        from tests.test_golden_artifacts import RAW_EN, RAW_ES

        text = (PROJECT / "brief_alta_proveedores.md").read_text(encoding="utf-8")
        self.assertGreaterEqual(len(text.splitlines()), 70)
        ids = {e["id"] for e in parse_request_elements(text, "F-01", "brief.md") if e.get("kind") != "section"}
        wanted = {f"RN-0{i}" for i in range(1, 6)} | {f"CA-0{i}" for i in range(1, 5)} | {f"HU-0{i}" for i in range(1, 4)} | {"PD-01"}
        self.assertEqual(ids, wanted)
        for raw in (RAW_EN, RAW_ES):
            self.assertEqual([e for e in parse_request_elements(raw, "F-01", "x.md") if e.get("kind") != "section"], [])


if __name__ == "__main__":
    unittest.main()
