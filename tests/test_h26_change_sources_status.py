"""IMP-400 (H26 inc 2): /status --change shows sources by role; /next --change asks for the baseline."""
from __future__ import annotations

import json
import shutil
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import SnapshotWorkspaceCase, run_cli, run_ok  # noqa: E402

from sentinel.changes import list_changes  # noqa: E402
from sentinel.readiness_verdict import change_next_step  # noqa: E402
from sentinel.status import change_sources  # noqa: E402
from sentinel.workspace import workspace_path  # noqa: E402
from test_change_flow import SCOPE_ANSWER  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"
SAD = FIXTURES / "change_baseline" / "sad-compras.md"
SAD_V2 = FIXTURES / "change_versions" / "sad-compras-v2.md"
CID = "CHG-001"

def load(project_id: str, path: Path, role: str = "linea_de_base") -> dict:
    return json.loads(run_ok(["sources", project_id, "--load", str(path), "--role", role, "--change", CID]))


class ChangeSourcesStatus(SnapshotWorkspaceCase):
    @classmethod
    def build_workspace(cls):
        root = Path.cwd()
        shutil.copy(FIXTURES / "change_borrador.md", root / "pedido.md")
        (root / "scope.md").write_text(SCOPE_ANSWER, encoding="utf-8")
        run_ok(["init", "BORR"])
        run_ok(["ingest", "BORR", "--source", "pedido.md", "--change"])
        run_ok(["resolve-gaps", "BORR", "--source", "scope.md", "--change", CID])
        shutil.copy(FIXTURES / "change_versions" / "pedido_con_citas.md", root / "citas.md")
        run_ok(["init", "VER"])
        run_ok(["ingest", "VER", "--source", "citas.md", "--change"])
        run_ok(["init", "PROJ"])
        run_ok(["ingest", "PROJ", "--source", "pedido.md"])

    def test_next_asks_for_baseline_after_scope(self):
        s = change_next_step("BORR", CID)
        self.assertEqual(s["key"], "baseline")
        self.assertIn("--role linea_de_base", s["command"])
        self.assertIn(f"--change {CID}", s["command"])
        self.assertIn("--no-baseline", s["text"])

    def test_next_moves_on_after_load(self):
        load("BORR", SAD)
        self.assertNotEqual(change_next_step("BORR", CID)["key"], "baseline")
        self.assertEqual(change_next_step("BORR", CID)["key"], "lenses")

    def test_waiver_moves_on_and_needs_reason(self):
        code, _ = run_cli(["sources", "BORR", "--change", CID, "--no-baseline"])
        self.assertEqual(code, 3)
        self.assertEqual(change_next_step("BORR", CID)["key"], "baseline")
        code, _ = run_cli(["sources", "BORR", "--no-baseline", "--reason", "x"])
        self.assertEqual(code, 3)
        run_ok(["sources", "BORR", "--change", CID, "--no-baseline", "--reason", "Es un sistema nuevo"])
        self.assertNotEqual(change_next_step("BORR", CID)["key"], "baseline")
        waived = list_changes("BORR")[CID]["baseline_waived"]
        self.assertEqual(waived["reason"], "Es un sistema nuevo")
        self.assertTrue(waived["at"])
        status = json.loads(run_ok(["status", "BORR", "--change", CID]))
        self.assertEqual(status["sources"]["baseline_waived"]["reason"], "Es un sistema nuevo")
        self.assertFalse(any(w["trigger"] == "no_baseline" for w in status["warnings"]))

    def test_status_lists_sources_by_role_and_not_loaded(self):
        load("VER", SAD_V2)
        before = (workspace_path("VER") / "01_discovery" / CID / "gaps.md").read_text(encoding="utf-8")
        status = json.loads(run_ok(["status", "VER", "--change", CID]))
        sources = status["sources"]
        self.assertIn("pedido", sources["by_role"])
        self.assertIn("linea_de_base", sources["by_role"])
        self.assertIn("manual-compras.md", sources["not_loaded"])
        self.assertTrue(sources["baseline"])
        self.assertTrue(any("manual-compras.md" in w["message"] for w in status["warnings"]))
        after = (workspace_path("VER") / "01_discovery" / CID / "gaps.md").read_text(encoding="utf-8")
        self.assertEqual(before, after)  # /status reads: it never opens a gap
        self.assertEqual(change_sources("VER", CID)["open_rows"], [])

    def test_status_warns_without_baseline(self):
        status = json.loads(run_ok(["status", "BORR", "--change", CID]))
        self.assertEqual(status["sources"]["baseline"], [])
        self.assertTrue(any("no hay línea de base registrada" in w["message"] for w in status["warnings"]))

    def test_project_status_unchanged(self):
        status = json.loads(run_ok(["status", "PROJ"]))
        self.assertNotIn("by_role", json.dumps(status))
        self.assertNotIn("baseline_waived", json.dumps(status))
        self.assertFalse(any("línea de base" in str(w) for w in status.get("warnings", [])))
        self.assertEqual(sorted(status), EXPECTED_PROJECT_KEYS)


# Top-level keys of /status for a project workspace at commit bc2737b (before IMP-400 task 5).
EXPECTED_PROJECT_KEYS = ["gap_counts", "health", "maturity_score", "next_action", "next_step", "phase", "privacy_mode",
                         "project_id", "project_language", "readiness_stage", "sources", "verdict"]

if __name__ == "__main__":
    unittest.main()
