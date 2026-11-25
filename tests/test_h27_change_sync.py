"""H27 inc 6a task 5: /sync --change loads the change's new source by role, confirms the version and re-crosses what it touched."""
from __future__ import annotations

import contextlib
import inspect
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import SyncCase, run_ok  # noqa: E402

from sentinel.change_sync import sync_change_scope  # noqa: E402
from sentinel.changes import list_changes  # noqa: E402
from sentinel.cli import main  # noqa: E402
from sentinel.commands import skill_for_command  # noqa: E402
from sentinel.core.io import forget_read_snapshots  # noqa: E402
from sentinel.source_registry import mark_pending_version  # noqa: E402
from sentinel.sources import load_source_manifest  # noqa: E402
from sentinel.traceability import add_node  # noqa: E402
from sentinel.workspace import workspace_path  # noqa: E402

PID = "TCSY"
CID = "CHG-001"


def run_err(argv: list[str]) -> tuple[int, str]:
    """Run one command; return its exit code and what it wrote to stderr."""
    err = io.StringIO()
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
        code = main(list(argv))
    return code, err.getvalue()


class ChangeSyncCase(SyncCase):
    PID = PID

    def sync(self, *extra: str) -> dict:
        out = run_ok(["sync", PID, "--change", CID, *extra])
        forget_read_snapshots()
        return json.loads(out)

    def row(self, source_id: str) -> dict:
        return next(r for r in load_source_manifest(PID)["registry"] if r["id"] == source_id)

    def v2(self) -> Path:
        Path("v2").mkdir(exist_ok=True)
        return self.write_v2("v2/pedido.md")


class SyncChangeTests(ChangeSyncCase):
    def test_sync_new_version_with_supersedes(self):
        old = self.ids()["pedido"]
        result = self.sync("--source", str(self.v2()), "--role", "pedido", "--supersedes", old)
        loaded = result["loaded"][0]
        self.assertEqual(loaded["version_of"], old)
        self.assertIs(loaded["confirmed"], True)
        self.assertFalse(loaded["reused"])
        self.assertEqual(self.row(old)["validity"], "superseded")
        self.assertEqual(result["sync"][0]["crosses"]["diseno"]["touched"], [5])
        self.assertTrue(result["next_step"]["command"].endswith("--delta"))
        self.assertTrue((workspace_path(PID) / "01_discovery" / CID / "sync_report.md").is_file())

    def test_note_goes_to_the_report(self):
        old = self.ids()["pedido"]
        self.sync("--source", str(self.v2()), "--role", "pedido", "--supersedes", old, "--note", "llego la v2 del cliente")
        report = (workspace_path(PID) / "01_discovery" / CID / "sync_report.md").read_text(encoding="utf-8")
        self.assertIn("llego la v2 del cliente", report)

    def test_same_stem_is_candidate_without_supersedes(self):
        old = self.ids()["pedido"]
        result = self.sync("--source", str(self.v2()), "--role", "pedido")
        loaded = result["loaded"][0]
        self.assertEqual(loaded["version_of"], old)
        self.assertIs(loaded["confirmed"], False)
        self.assertEqual(result["sync"], [])
        new = loaded["source_id"]
        self.assertEqual(self.row(old)["validity"], "current")
        self.assertEqual(self.row(new)["pending_version_of"], old)
        version = result["next_step"]["versions"][0]
        self.assertEqual(version["command"], f"/sources {PID} --id {old} --superseded-by {new}")

    def test_unrelated_source_runs_touched_set(self):
        design = Path("otro-prototipo.html")
        text = (self.FIXTURES / "change_crosses" / "prototipo-aprobaciones.html").read_text(encoding="utf-8")
        design.write_text(text.replace("</body>", "<p>Pantalla de auditoria</p></body>"), encoding="utf-8")
        result = self.sync("--source", str(design), "--role", "diseno_nuevo")
        loaded = result["loaded"][0]
        self.assertIsNone(loaded["version_of"])
        self.assertEqual(result["sync"][0]["crosses"]["diseno"]["delta"], True)

    def test_same_content_is_nothing_new(self):
        pedido = self.FIXTURES / "change_crosses" / "pedido_contradiccion.md"
        result = self.sync("--source", str(pedido), "--role", "pedido")
        self.assertIs(result["loaded"][0]["reused"], True)
        self.assertEqual(result["sync"], [])

    def test_scan_role_folders(self):
        folder = workspace_path(PID) / "00_raw" / "08_new_design"
        before = sorted(p.name for p in folder.iterdir())
        hand = folder / "pantalla-extra.md"
        hand.write_text("# Pantalla extra\n\nLa bandeja muestra el estado de cada aprobacion.\n", encoding="utf-8")
        result = self.sync()
        self.assertEqual(len(result["loaded"]), 1)
        loaded = result["loaded"][0]
        self.assertEqual(loaded["role"], "diseno_nuevo")
        self.assertEqual(sorted(p.name for p in folder.iterdir()), sorted([*before, "pantalla-extra.md"]))
        forget_read_snapshots()
        self.assertIn(loaded["source_id"], list_changes(PID)[CID]["sources"])
        again = self.sync()
        self.assertEqual(again["loaded"], [])

    def test_sync_event_id_refused(self):
        forget_read_snapshots()
        node = add_node(PID, "CHG", "change", workspace_path(PID) / "07_changes" / "evento.md", "evento")
        code, err = run_err(["sync", PID, "--change", node])
        self.assertNotEqual(code, 0)
        self.assertIn("es un evento de /sync del proyecto", err)
        self.assertIn(CID, err)

    def test_unknown_change_is_the_usual_refusal(self):
        code, err = run_err(["sync", PID, "--change", "CHG-099"])
        self.assertNotEqual(code, 0)
        self.assertIn("no es un cambio abierto", err)

    def test_role_required_and_flags_refused(self):
        code, err = run_err(["sync", PID, "--change", CID, "--source", str(self.v2())])
        self.assertNotEqual(code, 0)
        self.assertIn("--role", err)
        code, err = run_err(["sync", PID, "--change", CID, "--digest"])
        self.assertNotEqual(code, 0)
        self.assertIn("/sync --change takes", err)
        code, err = run_err(["sync", PID, "--change", CID, "--analysis", "a.json"])
        self.assertNotEqual(code, 0)
        self.assertIn("/sync --change takes", err)

    def test_supersedes_must_be_a_row_of_the_change_with_that_role(self):
        ids = self.ids()
        code, err = run_err(["sync", PID, "--change", CID, "--source", str(self.v2()), "--role", "pedido",
                             "--supersedes", "F-99"])
        self.assertNotEqual(code, 0)
        self.assertIn("F-99", err)
        code, err = run_err(["sync", PID, "--change", CID, "--source", str(self.v2()), "--role", "pedido",
                             "--supersedes", ids["diseno"]])
        self.assertNotEqual(code, 0)
        self.assertIn(ids["diseno"], err)
        self.assertIn("pedido", err)

    def test_confirm_runs_touched_set_once(self):
        old = self.ids()["pedido"]
        result = self.sync("--source", str(self.v2()), "--role", "pedido", "--supersedes", old)
        self.assertEqual(len(result["sync"]), 1)

    def test_mark_pending_version_keeps_an_existing_one(self):
        manifest = {"registry": [{"id": "F-01"}, {"id": "F-02", "pending_version_of": "F-01"}, {"id": "F-03"}]}
        mark_pending_version(manifest, manifest["registry"][1], "F-03")
        self.assertEqual(manifest["registry"][1]["pending_version_of"], "F-01")
        mark_pending_version(manifest, manifest["registry"][2], "F-01")
        self.assertEqual(manifest["registry"][2]["pending_version_of"], "F-01")

    def test_scope_function_directly(self):
        forget_read_snapshots()
        result = sync_change_scope(PID, CID)
        self.assertEqual(result["loaded"], [])
        self.assertEqual(result["sync"], [])
        self.assertEqual(result["change_id"], CID)
        self.assertIn("next_step", result)


class ProjectSyncUnchanged(unittest.TestCase):
    """Review Focus 5: the project's /sync keeps its keys and writes no change sync report."""

    def setUp(self) -> None:
        self.previous = os.getcwd()
        self.folder = tempfile.mkdtemp()
        os.chdir(self.folder)

    def tearDown(self) -> None:
        os.chdir(self.previous)
        shutil.rmtree(self.folder, ignore_errors=True)

    def test_project_sync_unchanged(self):
        run_ok(["init", "TPSU"])
        Path("nota.md").write_text("# Nota\n\nPolicyholders file claims with photos.\n", encoding="utf-8")
        run_ok(["ingest", "TPSU", "--source", "nota.md"])
        Path("n2.md").write_text("# N2\n\nA claim accepts at most 10 photos.\n", encoding="utf-8")
        result = json.loads(run_ok(["sync", "TPSU", "--source", "n2.md"]))
        self.assertEqual(sorted(result), [
            "affected", "answered_context_requests", "change_id", "closed_gaps_detected_again", "context_pack", "gaps",
            "impact_report_id", "injection_signals", "interaction_digest", "knowledge_metabolism", "merged_gaps",
            "path", "prose_review", "secret_redactions", "skipped_existing_gaps", "source", "source_authority",
            "source_conflicts", "source_format", "source_id", "staleness", "suspicious_trace_links", "sync_closed_gaps"])
        self.assertFalse(list((workspace_path("TPSU") / "01_discovery").rglob("sync_report.md")))


class SyncSurface(unittest.TestCase):
    def test_mcp_and_registry(self):
        from tests.test_mcp_parity import _tools

        params = inspect.signature(_tools()["sentinel_sync"]).parameters
        for name in ("change", "role", "supersedes"):
            self.assertIn(name, params)
        self.assertEqual(skill_for_command(f"/sync {PID} --change {CID} --source X --role pedido"),
                         "sentinel-sync §Change sync")
        self.assertEqual(skill_for_command(f"/sync {PID} --source X"), "sentinel-sync")


if __name__ == "__main__":
    unittest.main()
