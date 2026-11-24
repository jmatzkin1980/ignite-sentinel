"""IMP-402 (H26 inc 3) task 6: the change brief carries what the extraction confirmed."""
from __future__ import annotations

import json
import shutil
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import IDS_SCOPE_ANSWER, SnapshotWorkspaceCase, run_ok  # noqa: E402
from test_change_brief_cli import run_err  # noqa: E402
from test_h26_extract_proposals import CID, EXAMPLE, FIXTURES, PID, ProposalsCase, block  # noqa: E402

from sentinel.changes import get_change, list_changes  # noqa: E402
from sentinel.core.io import forget_read_snapshots  # noqa: E402
from sentinel.extraction.confirm import confirm_item  # noqa: E402
from sentinel.extraction.inventory import build_inventory  # noqa: E402
from sentinel.extraction.proposals import record_proposals  # noqa: E402
from sentinel.readiness_verdict import _brief_stale  # noqa: E402
from sentinel.workspace import update_state, workspace_path  # noqa: E402

PRESERVED_BLOCK = block(
    "SEC-se-preserva", "- Tratamiento: requisito", '- Cita: "sigue habilitándose en el acto, como hoy"',
    "- Enunciado: Cuando el analista guarda un alta con monto menor o igual al umbral, "
    "el sistema debe habilitarla en el acto.",
    "  - Delta: UNCHANGED", "  - Superficie: Alta de monto bajo",
)


def brief_text(project: str) -> str:
    return (workspace_path(project) / "02_requirements" / CID / "project-brief.md").read_text(encoding="utf-8")


def brief_report(project: str) -> dict:
    path = workspace_path(project) / "02_requirements" / CID / "change_brief_report.json"
    return json.loads(path.read_text(encoding="utf-8"))


def section(text: str, number: int) -> str:
    return text.split(f"## {number}.", 1)[1].split("\n## ", 1)[0]


class BriefWithExtraction(ProposalsCase):
    @classmethod
    def build_workspace(cls):
        super().build_workspace()
        root = Path.cwd()
        shutil.copy(FIXTURES / "pedido_ids.md", root / "otro.md")
        run_ok(["init", "SIN"])
        run_ok(["ingest", "SIN", "--source", "otro.md", "--change"])
        run_ok(["resolve-gaps", "SIN", "--source", "scope.md", "--change", CID])

    def setUp(self):
        super().setUp()
        forget_read_snapshots()
        record_proposals(PID, CID, EXAMPLE)

    def compile(self, project: str = PID) -> str:
        run_ok(["brief", project, "--change", CID])
        return brief_text(project)

    def test_confirmed_section_fills_brief(self):
        confirm_item(PID, CID, "SEC-objetivo")
        body = section(self.compile(), 2)
        self.assertIn("la jefatura aprueba las altas de monto alto dentro del sistema", body)
        self.assertIn("SEC-objetivo — texto literal del pedido (`00_raw/09_request/pedido.md`:4-4):", body)
        self.assertIn("Que el alta de proveedores de Compras deje de depender de firmas en papel", body)
        self.assertNotIn("Que la jefatura apruebe las altas de monto alto dentro del sistema", body)

    def test_marks_stay_where_elements_are_unconfirmed(self):
        confirm_item(PID, CID, "SEC-objetivo")
        text = self.compile()
        self.assertIn(
            "⏳ PENDIENTE DE EXTRACCIÓN: 1 elemento(s) del pedido sin confirmar (SEC-usuarios)", section(text, 2)
        )
        self.assertEqual(sorted(set(brief_report(PID)["extraction_pending"]) & {"2", "4", "7"}), ["2", "4", "7"])
        self.assertIn("(`02_requirements/CHG-001/extraction/inventory.json`)", section(text, 2))

    def test_marks_list_five_ids_then_ellipsis(self):
        text = self.compile()
        self.assertRegex(section(text, 7), r"sin confirmar \((?:[\w-]+, ){5}…\)")

    def test_rows_and_discards_in_brief(self):
        from sentinel.extraction.confirm import confirm_proposals

        confirm_proposals(PID, CID, "all")
        text = self.compile()
        body = section(text, 7)
        self.assertEqual(body.count(", RN-02, `00_raw/09_request/pedido.md`:"), 2, body)
        self.assertEqual(body.count("[ADDED] (REQ-EARS-"), 3, body)
        self.assertIn("el sistema debe dejarla Pendiente de aprobación. [ADDED] (REQ-EARS-", body)
        self.assertIn(", RN-02, `00_raw/09_request/pedido.md`:", body)
        rows = section(text, 9)
        self.assertIn("Descartado RN-06:", rows)
        self.assertIn("Cobertura de la extracción: ", rows)

    def test_preserved_line(self):
        text = self.compile()
        line = next(ln for ln in section(text, 6).splitlines() if "Alta de monto bajo" in ln)
        self.assertIn("sin fila UNCHANGED", line)
        self.assertEqual(brief_report(PID)["preserved_missing"], ["Alta de monto bajo", "Validación de CUIT"])
        path = Path.cwd() / "preserved.md"
        path.write_text(PRESERVED_BLOCK, encoding="utf-8")
        self.assertEqual(record_proposals(PID, CID, path)["recorded"], ["SEC-se-preserva"])
        confirm_item(PID, CID, "SEC-se-preserva")
        text = self.compile()
        body = section(text, 6)
        line = next(ln for ln in body.splitlines() if "Alta de monto bajo" in ln and "UNCHANGED:" in ln)
        self.assertRegex(line, r"UNCHANGED: REQ-EARS-\d+")
        self.assertIn("[UNCHANGED] (REQ-EARS-", body)
        self.assertNotIn("[UNCHANGED]", section(text, 7))
        self.assertEqual(brief_report(PID)["preserved_missing"], ["Validación de CUIT"])

    def test_brief_goes_stale_on_confirmation(self):
        self.compile()
        base = workspace_path(PID)
        change = get_change(PID, CID)
        self.assertFalse(_brief_stale(base, CID, change))
        confirm_item(PID, CID, "SEC-objetivo")
        self.assertTrue(_brief_stale(base, CID, get_change(PID, CID)))
        self.compile()
        self.assertFalse(_brief_stale(base, CID, get_change(PID, CID)))

    def test_without_inventory_brief_is_unchanged(self):
        text = self.compile("SIN")
        report = brief_report("SIN")
        self.assertNotIn("extracción", section(text, 9).replace("extracción pendiente", ""))
        self.assertNotIn("Cobertura de la extracción", text)
        self.assertNotIn("sin confirmar", text)
        self.assertIn("⏳ PENDIENTE DE EXTRACCIÓN: el pedido trata este tema y todavía no está en el brief", section(text, 2))
        self.assertEqual(report["extraction_pending"], ["2", "4"])
        self.assertEqual(
            (report["extraction"], report["extraction_fingerprint"], report["preserved_missing"]), (None, "", [])
        )
        self.assertFalse(_brief_stale(workspace_path("SIN"), CID, get_change("SIN", CID)))

    def test_english_copy(self):
        confirm_item(PID, CID, "SEC-objetivo")
        changes = {key: dict(value) for key, value in list_changes(PID).items()}
        changes[CID]["language"] = "en"
        update_state(PID, changes=changes)
        forget_read_snapshots()
        text = self.compile()
        self.assertIn("Extraction coverage: ", section(text, 9))
        self.assertIn("PENDING EXTRACTION: 1 request element(s) not confirmed (SEC-usuarios)", section(text, 2))

    def test_final_export_refuses_while_extraction_is_pending(self):
        self.compile()
        code, out = run_err(["export", PID, "--artifact", "brief", "--change", CID, "--final"])
        self.assertNotEqual(code, 0)
        self.assertIn("sin extraer del pedido", out)


class BriefComplete(SnapshotWorkspaceCase):
    """A request whose only element is a plain intro: once confirmed, nothing is left to extract."""

    @classmethod
    def build_workspace(cls):
        root = Path.cwd()
        shutil.copy(Path(__file__).resolve().parent / "fixtures" / "change_borrador.md", root / "borrador.md")
        (root / "scope.md").write_text(IDS_SCOPE_ANSWER, encoding="utf-8")
        run_ok(["init", "DRF"])
        run_ok(["ingest", "DRF", "--source", "borrador.md", "--change"])
        run_ok(["resolve-gaps", "DRF", "--source", "scope.md", "--change", CID])
        build_inventory("DRF", CID)

    def test_no_marks_when_complete(self):
        forget_read_snapshots()
        path = Path.cwd() / "intro.md"
        path.write_text(block(
            "SEC-intro", "- Tratamiento: seccion", "- Líneas: 3-7", "- Seccion: proceso",
            "- Texto: El formulario de alta se envía completo.",
            '- Cita: "el formulario de alta de proveedores es largo"',
        ), encoding="utf-8")
        self.assertEqual(record_proposals("DRF", CID, path)["recorded"], ["SEC-intro"])
        confirm_item("DRF", CID, "SEC-intro")
        run_ok(["brief", "DRF", "--change", CID])
        text = brief_text("DRF")
        self.assertNotIn("PENDIENTE DE EXTRACCIÓN", text)
        self.assertIn("el formulario de alta de proveedores es largo", section(text, 4))
        self.assertEqual(brief_report("DRF")["extraction_pending"], [])
        code, out = run_err(["export", "DRF", "--artifact", "brief", "--change", CID, "--final"])
        self.assertNotIn("sin extraer del pedido", out)

    def test_empty_section_without_elements_says_so(self):
        from sentinel.compilers.change_brief import collect_change_brief_inputs, render_change_brief

        inputs = collect_change_brief_inputs("DRF", CID)
        inputs["gaps"] = []
        text, report = render_change_brief(inputs)
        body = section(text, 2)
        self.assertIn("- El pedido no trae elementos para esta sección (`02_requirements/CHG-001/extraction/inventory.json`)", body)
        self.assertNotIn("⏳", body)
        self.assertNotIn("2", report["extraction_pending"])


if __name__ == "__main__":
    unittest.main()
