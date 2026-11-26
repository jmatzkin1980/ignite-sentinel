"""IMP-420 (H27 inc 6b) final review: the offer counts written ids only, stays out of projects with specs, API guards,
project flags, v1 briefs and exact cross gaps."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import ProjectExtractionCase, run_ok  # noqa: E402
from test_h27_project_commands import CHANGE_ONLY, NO_IDS, run_cli, tree  # noqa: E402
from test_h27_project_next import BLOCKING, NEW_KEYS, step  # noqa: E402

from sentinel.changes import project_extraction_offered  # noqa: E402
from sentinel.errors import GateRefusal, InputError  # noqa: E402
from sentinel.core.io import forget_read_snapshots, write_json, write_text  # noqa: E402
from sentinel.crosses import run_cross  # noqa: E402
from sentinel.extraction import run_extract  # noqa: E402
from sentinel.extraction.inventory import build_inventory  # noqa: E402
from sentinel.gaps.model import merge_gaps_by_topic  # noqa: E402
from sentinel.core.state import update_state  # noqa: E402
from sentinel.workspace import workspace_path  # noqa: E402

PID = ProjectExtractionCase.PID

ITEMIZED = "\n".join([
    "# Pedido de alta de proveedores", "", "## Objetivo", "Reducir el tiempo del alta.", "",
    "## Criterios de aceptación", "- El analista puede guardar el alta.", "- El analista puede borrarla.", "",
    "## Decisiones", "- Usamos correo para avisar.", ""])
LOOSE = "\n".join([
    "# Pedido de alta de proveedores", "", "Según la Regla 3 del manual y la Decisión 2 del comité, el alta pasa "
    "por la Jefa de Compras antes de publicarse.", ""])


class WrittenIdsOnly(unittest.TestCase):
    def setUp(self):
        self.old = Path.cwd()
        self.dir = tempfile.TemporaryDirectory()
        os.chdir(self.dir.name)

    def tearDown(self):
        os.chdir(self.old)
        self.dir.cleanup()

    def load(self, pid: str, text: str) -> None:
        Path("pedido.md").write_text(text, encoding="utf-8")
        run_ok(["init", pid])
        run_ok(["ingest", pid, "--source", "pedido.md"])
        forget_read_snapshots()

    def check_refused(self, pid: str) -> None:
        self.assertFalse(project_extraction_offered(pid))
        self.assertNotIn(step(pid)["key"], NEW_KEYS)
        before = tree(workspace_path(pid))
        for argv in (["extract", pid], ["cross", pid]):
            code, out = run_cli(argv)
            self.assertNotEqual(code, 0, argv)
            self.assertIn(NO_IDS, out)
        self.assertEqual(tree(workspace_path(pid)), before)

    def test_itemized_headings_without_ids_not_offered(self):
        self.load("ITM", ITEMIZED)
        self.check_refused("ITM")

    def test_loose_mentions_not_offered(self):
        self.load("LSE", LOOSE)
        self.check_refused("LSE")

    def test_written_ids_offered(self):
        self.load("IDS", "# Pedido\n\n## Reglas\n- RN-01 El alta exige CUIT válido.\n- RN-02 El monto alto exige aprobación.\n")
        self.assertTrue(project_extraction_offered("IDS"))


class OfferStopsAtSpecs(ProjectExtractionCase):
    def test_backlog_stage_with_ids_keeps_backlog(self):
        run_ok(["brief", PID, "--profile", "UI", "--genesis", "greenfield"])
        Path("blocking.md").write_text(BLOCKING, encoding="utf-8")
        run_ok(["resolve-gaps", PID, "--source", "blocking.md"])
        base = workspace_path(PID)
        write_text(base / "03_specs" / "specs.md", "# Specs\n")
        update_state(PID, readiness_stage="READY_FOR_BACKLOG")
        forget_read_snapshots()
        self.assertFalse(project_extraction_offered(PID))
        self.assertEqual(step()["key"], "backlog")

    def test_specs_with_inventory_still_offered(self):
        build_inventory(PID, None)
        write_text(workspace_path(PID) / "03_specs" / "specs.md", "# Specs\n")
        forget_read_snapshots()
        self.assertTrue(project_extraction_offered(PID))

    def test_brief_v1_not_offered(self):
        update_state(PID, brief_settings={"brief_version": 1})
        forget_read_snapshots()
        self.assertFalse(project_extraction_offered(PID))
        build_inventory(PID, None)
        self.assertTrue(project_extraction_offered(PID))  # an existing record keeps its steps


class ApiGuards(ProjectExtractionCase):
    def test_cross_none_change_only_options(self):
        before = tree(workspace_path(PID))
        with self.assertRaises(InputError) as caught:
            run_cross(PID, None, accept_new="NEW-1", surface_type="T", name="N")
        self.assertIn(CHANGE_ONLY, str(caught.exception))
        with self.assertRaises(InputError) as caught:
            run_cross(PID, None, decline_new="NEW-1", reason="no")
        self.assertIn(CHANGE_ONLY, str(caught.exception))
        self.assertEqual(tree(workspace_path(PID)), before)

    def test_extract_none_change_only_options(self):
        for kwargs in ({"consolidate": "f.md"}, {"confirm_replacement": "RN-01"}, {"keep_text": "RN-01", "gap": "GAP-X"}):
            with self.assertRaises(InputError) as caught:
                run_extract(PID, None, **kwargs)
            self.assertIn(CHANGE_ONLY, str(caught.exception))
            self.assertNotIn("None", str(caught.exception))

    def test_api_without_ids_refused(self):
        update_state(PID, brief_settings={"brief_version": 1})
        forget_read_snapshots()
        before = tree(workspace_path(PID))
        with self.assertRaises(GateRefusal):
            run_extract(PID, None)
        with self.assertRaises(GateRefusal):
            run_cross(PID, None, kind="contradicciones", claims="x.md")
        self.assertEqual(tree(workspace_path(PID)), before)

    def test_mcp_marks_change_optional(self):
        from sentinel.mcp import describe_tools

        described = describe_tools()
        tools = {t["name"]: t for t in described} if isinstance(described, list) else described
        for name in ("extract", "cross"):
            entry = tools.get(name) or tools.get(f"sentinel_{name}")
            self.assertEqual(entry["required"], ["project_id"], name)


class ProjectFlags(ProjectExtractionCase):
    def test_project_ignores_harvests_of_changes(self):
        from sentinel.extraction.flags import change_flag_context

        base = workspace_path(PID)
        write_json(base / "01_discovery" / "harvest.json", {"artifact": "harvest", "source_ids": ["F-90", "F-91"], "entries": [
            {"kind": "divergence", "text": "de cambio " * 4, "line": 1, "source_id": "F-90"},
            {"kind": "divergence", "text": "del proyecto " * 4, "line": 2, "source_id": "F-91"}]})
        update_state(PID, changes={"CHG-001": {"harvests": ["F-90"], "sources": [], "status": "open"}})
        forget_read_snapshots()
        _, entries = change_flag_context(PID, None)
        self.assertEqual([e["source_id"] for e in entries], ["F-91"])


class ExactCrossGaps(unittest.TestCase):
    def test_topic_merge_never_folds_into_cross_gap(self):
        text = "El monto de aprobación contradice el umbral del proveedor nuevo"
        question = "Cuál umbral aplica al monto de aprobación del proveedor nuevo?"
        cross = {"id": "GAP-CON-AB12CD34", "lens": "business", "status": "OPEN", "severity": "blocking",
                 "description": text, "question": question, "evidence_mention": "a"}
        harvest = {"id": "GAP-HRV-0001", "lens": "business", "status": "OPEN", "severity": "blocking",
                   "description": text, "question": question, "evidence_mention": "b"}
        merged = merge_gaps_by_topic([cross], [harvest])
        self.assertEqual([g["id"] for g in merged["added"]], ["GAP-HRV-0001"])
        self.assertEqual(merged["extended"], {})
        self.assertEqual(merged["gaps"][0]["evidence_mention"], "a")


if __name__ == "__main__":
    unittest.main()
