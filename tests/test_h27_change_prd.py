"""IMP-414 (H27 inc 5a) task 6: `/specs --change` writes the PRD of the change from the consolidated final export."""
from __future__ import annotations

import json
import shutil
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import (  # noqa: E402
    SnapshotWorkspaceCase, run_cli, class_deferred, complete_extraction, export_final_brief, run_ok, waive_coherence, waive_crosses,
)
from test_change_flow import SCOPE_ANSWER  # noqa: E402
from test_change_next import FIXTURES, load_baseline, step  # noqa: E402
from test_change_specs import ALL_ANSWERS, answer  # noqa: E402
from test_h26_cross_record import set_language  # noqa: E402

from sentinel.compilers.change_backlog import specs_currency  # noqa: E402
from sentinel.compilers.prd import render_prd_full  # noqa: E402
from sentinel.core.io import forget_read_snapshots  # noqa: E402
from sentinel.workspace import workspace_path  # noqa: E402

PID = "BORR"
CID = "CHG-001"
RAW = """# Client Request: Support Operations Dashboard

We want a dashboard for our customer support operation. The goal is to reduce the time team leads spend preparing the weekly review meeting.

The main users are the support team leads. They want to see ticket volume, resolution time, and backlog ageing in one screen.

In scope: a read-only dashboard for the current quarter. Out of scope: editing tickets or managing agents from this screen.
"""
ASSUMED = "\n".join([
    "### GAP-TECH-NFR", "- Respuesta: El tiempo de respuesta se mide sobre la lista de borradores del analista.",
    "- Owner / fuente: BA de Compras", '- Evidencia o referencia: "el formulario de alta de proveedores es largo"',
    "- Estado de decisión: supuesto", "- Valida: Diseño", ""])


class Pure(unittest.TestCase):
    def test_project_prd_unchanged(self):
        base = render_prd_full("SUP", "Support dashboard", {"raw_text": RAW}, "project-brief.md", "en", RAW)
        again = render_prd_full("SUP", "Support dashboard", {"raw_text": RAW}, "project-brief.md", "en", RAW,
                                pending="[PENDING INPUT]", assumption_rows=None, source_path="00_raw/")
        self.assertEqual(base, again)
        self.assertIn("00_raw/", base)

    def test_new_kwargs_replace(self):
        text = render_prd_full("SUP", "Support dashboard", {"raw_text": RAW}, "project-brief.md", "en", RAW,
                               pending="no data recorded", assumption_rows="", source_path="02_requirements/CHG-001/")
        self.assertNotIn("PENDING INPUT", text)
        self.assertNotIn("00_raw/", text)
        self.assertIn("02_requirements/CHG-001/", text)
        self.assertIn("no data recorded", text)


class PrdCase(SnapshotWorkspaceCase):
    @classmethod
    def build_workspace(cls):
        root = Path.cwd()
        shutil.copy(FIXTURES / "change_borrador.md", root / "pedido.md")
        run_ok(["init", PID])
        run_ok(["ingest", PID, "--source", "pedido.md", "--change"])
        (root / "scope.md").write_text(SCOPE_ANSWER, encoding="utf-8")
        run_ok(["resolve-gaps", PID, "--source", "scope.md", "--change", CID])
        waive_crosses(PID, CID)
        load_baseline(PID)
        answer(PID, CID, "a.md", ALL_ANSWERS)
        waive_coherence(PID, CID)
        complete_extraction(PID, CID)
        run_ok(["brief", PID, "--change", CID])

    def folder(self) -> Path:
        return workspace_path(PID) / "03_specs" / CID

    def prd(self) -> str:
        return (self.folder() / "prd.md").read_text(encoding="utf-8")

    def report(self) -> dict:
        return json.loads((self.folder() / "change_specs_report.json").read_text(encoding="utf-8"))

    def specs(self) -> dict:
        forget_read_snapshots()
        code, out = run_cli(["specs", PID, "--change", CID])
        self.assertEqual(code, 0, out)
        return json.loads(out)


class Prd(PrdCase):
    def test_specs_writes_prd(self):
        export_final_brief(PID, CID)
        out = self.specs()
        self.assertEqual(out["prd"], f"03_specs/{CID}/prd.md")
        text = self.prd()
        self.assertTrue(text.startswith("# PRD - "))
        self.assertTrue(text.splitlines()[0].endswith(f" / {CID}"), text.splitlines()[0])
        self.assertIn("## 4. Requerimientos funcionales", text)
        self.assertIn("| `REQ-EARS-", text)
        self.assertIn("Requerimientos EARS confirmados", text)
        self.assertIn("sin dato registrado", text)
        self.assertNotIn("[PENDING INPUT]", text)
        self.assertNotIn("`00_raw/`", text)
        sha = self.report()["prd"]["source_sha"]
        self.assertRegex(sha, r"^[0-9a-f]{16}$")

    def test_prd_skipped_without_final(self):
        class_deferred(PID, CID)
        out = self.specs()
        self.assertIn("--final", out["prd_skipped"])
        self.assertIn("prd.md pendiente", out["prd_skipped"])
        self.assertFalse((self.folder() / "prd.md").exists())
        self.assertIn("--final", self.report()["prd_skipped"])
        self.assertEqual(specs_currency(PID, CID), "current")
        run_ok(["export", PID, "--artifact", "brief", "--change", CID, "--final"])
        forget_read_snapshots()
        self.assertEqual(specs_currency(PID, CID), "stale")
        self.assertEqual(step(PID, CID)["key"], "specs")

    def test_prd_goes_stale_with_final(self):
        export_final_brief(PID, CID)
        self.specs()
        self.assertEqual(specs_currency(PID, CID), "current")
        final = workspace_path(PID) / json.loads(
            (workspace_path(PID) / "state.json").read_text(encoding="utf-8"))["changes"][CID]["final_export"]["path"]
        final.write_text(final.read_text(encoding="utf-8") + "\nOtra línea del final.\n", encoding="utf-8")
        forget_read_snapshots()
        self.assertEqual(specs_currency(PID, CID), "stale")

    def test_old_report_reads_as_before(self):
        export_final_brief(PID, CID)
        self.specs()
        path = self.folder() / "change_specs_report.json"
        report = self.report()
        report.pop("prd")
        path.write_text(json.dumps(report), encoding="utf-8")
        forget_read_snapshots()
        self.assertEqual(specs_currency(PID, CID), "current")

    def test_change_assumptions_in_prd(self):
        out = json.loads(run_ok(["resolve-gaps", PID, "--source", self._write("sup.md", ASSUMED), "--change", CID]))
        self.assertEqual(out["assumed"], ["GAP-TECH-NFR"])
        run_ok(["brief", PID, "--change", CID])
        export_final_brief(PID, CID)
        self.specs()
        text = self.prd()
        table = text.split("### 9a. Assumption Register", 1)[1].split("### 9b.", 1)[0]
        self.assertIn("ASM-TECH-NFR", table)
        self.assertNotIn("ASM-01", table)
        self.assertNotIn("ASM-02", table)

    def test_english_prd(self):
        set_language(PID, "en")
        waive_coherence(PID, CID)
        run_ok(["brief", PID, "--change", CID])
        export_final_brief(PID, CID)
        self.specs()
        text = self.prd()
        self.assertIn("no data recorded", text)
        self.assertIn("## 4. Functional Requirements", text)

    def _write(self, name: str, text: str) -> str:
        Path(name).write_text(text, encoding="utf-8")
        return name


if __name__ == "__main__":
    unittest.main()
