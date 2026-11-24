"""IMP-402 (H26 inc 3) task 4: confirmation by section and materialization of the EARS rows."""
from __future__ import annotations

import json
import re
import shutil
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import IDS_SCOPE_ANSWER, SnapshotWorkspaceCase, lines_field, run_ok  # noqa: E402
from test_h26_extract_proposals import (  # noqa: E402
    CID, EXAMPLE, FIXTURES, PID, RN02_QUOTE, ProposalsCase, block,
)

from sentinel.change_requirements import SUPERSEDED_HEADINGS, change_requirements_path, load_change_ears  # noqa: E402
from sentinel.change_validation import validate_change  # noqa: E402
from sentinel.changes import change_gaps_path, change_language, get_change, list_changes  # noqa: E402
from sentinel.core.io import forget_read_snapshots  # noqa: E402
from sentinel.errors import InputError  # noqa: E402
from sentinel.extraction import extraction_dir  # noqa: E402
from sentinel.extraction.confirm import confirm_item, confirm_proposals, reject_item  # noqa: E402
from sentinel.extraction.inventory import build_inventory  # noqa: E402
from sentinel.extraction.proposals import load_proposals, record_proposals  # noqa: E402
from sentinel.gaps import count_gaps, merge_gaps_by_topic, parse_gap_rows, render_gaps  # noqa: E402
from sentinel.workspace import update_state, workspace_path  # noqa: E402

RN02_FIRST = "Cuando el analista envía un alta con monto anual estimado mayor al umbral, el sistema debe dejarla Pendiente de aprobación."
SCOPE_WITHOUT_RULE = IDS_SCOPE_ANSWER.replace("  - nuevo | regla | Aprobación por monto\n", "")
ACCEPTANCE_ANSWER = "\n".join([
    "### GAP-ACCEPTANCE",
    "- Respuesta: Cuando el analista guarda el alta incompleta, el sistema debe conservar los datos cargados.",
    "- Owner / fuente: Jefa de Compras",
    "- Delta: ADDED",
    "- Superficie: Tabla de proveedores",
    "- Estado de decisión: confirmado",
    "",
])


def rn02_one_statement() -> str:
    return block(
        "RN-02", "- Tratamiento: requisito", RN02_QUOTE,
        f"- Enunciado: {RN02_FIRST}", "  - Delta: ADDED", "  - Superficie: Aprobación por monto",
    )


class Confirming(ProposalsCase):
    def setUp(self):
        super().setUp()
        forget_read_snapshots()  # a command starts from the disk; the snapshot restore changes files behind the cache
        record_proposals(PID, CID, EXAMPLE)

    def rows(self) -> list[dict]:
        return load_change_ears(PID, CID)

    def items(self) -> dict:
        return load_proposals(workspace_path(PID), CID)["items"]

    def resolve(self, name: str, text: str) -> None:
        Path(name).write_text(text, encoding="utf-8")
        run_ok(["resolve-gaps", PID, "--source", name, "--change", CID])

    def test_confirm_section_holds_flagged(self):
        result = confirm_proposals(PID, CID, "reglas-de-negocio")
        self.assertEqual(result["action"], "confirm")
        self.assertEqual(result["confirmed"], ["RN-02", "RN-06"])
        self.assertEqual(result["held"], ["RN-04"])
        self.assertEqual(result["invalid"], {})
        self.assertEqual(self.items()["RN-04"]["status"], "proposed")
        self.assertTrue(Path(result["review_path"]).is_file())
        with self.assertRaises(InputError) as caught:
            confirm_proposals(PID, CID, "no-existe")
        self.assertIn("reglas-de-negocio", str(caught.exception))
        # the heading, folded, names the section too
        self.assertEqual(confirm_proposals(PID, CID, "Reglas de Negocio")["confirmed"], [])

    def test_rows_carry_their_own_delta_and_surface(self):
        result = confirm_proposals(PID, CID, "reglas-de-negocio")
        rows = self.rows()
        self.assertEqual(len(rows), 2)
        self.assertEqual(result["rows_added"], [r["id"] for r in rows])
        self.assertTrue(all("`EXT:RN-02`" in r["source"] for r in rows))
        self.assertTrue(all(re.search(r"F-\d+:31", r["source"]) for r in rows))
        self.assertEqual([r["surfaces"] for r in rows], [["Aprobación por monto"], ["Tabla de proveedores"]])
        self.assertEqual(self.items()["RN-02"]["rows"], [r["id"] for r in rows])
        self.assertIsNotNone(self.items()["RN-02"]["confirmed_at"])

    def test_confirm_item_confirms_flagged(self):
        result = confirm_item(PID, CID, "RN-04")
        self.assertEqual((result["confirmed"], result["held"], len(result["rows_added"])), (["RN-04"], [], 1))
        self.assertEqual(len(self.rows()), 1)
        with self.assertRaises(InputError) as caught:
            confirm_item(PID, CID, "RN-04")
        self.assertIn("RN-04 no tiene una propuesta pendiente de confirmar", str(caught.exception))
        with self.assertRaises(InputError):
            confirm_item(PID, CID, "RN-01")

    def test_confirm_all_writes_sections(self):
        result = confirm_proposals(PID, CID, "all")
        self.assertEqual(sorted(result["confirmed"]), ["HU-01", "RN-02", "RN-06", "SEC-objetivo"])
        self.assertEqual(result["held"], ["RN-04"])
        data = json.loads((extraction_dir(workspace_path(PID), CID) / "sections.json").read_text(encoding="utf-8"))
        self.assertEqual((data["schema_version"], data["change_id"]), (1, CID))
        self.assertEqual([e["element"] for e in data["entries"]], ["SEC-objetivo"])
        entry = data["entries"][0]
        self.assertEqual((entry["brief_section"], entry["line"], entry["section"]), (2, 4, "objetivo"))
        self.assertIn("la jefatura aprueba las altas", entry["quote"])
        self.assertTrue(entry["content"].startswith("Que el alta"))
        self.assertTrue(entry["summary"].startswith("Que la jefatura"))
        self.assertEqual(entry["lines"], [[4, 4]])
        self.assertTrue(entry["path"] and entry["source_id"])

    def test_correction_keeps_ids_and_supersedes_dropped(self):
        confirm_proposals(PID, CID, "reglas-de-negocio")
        first, second = [r["id"] for r in self.rows()]
        self.assertEqual(record_proposals(PID, CID, self._write("fix.md", rn02_one_statement()))["recorded"], ["RN-02"])
        self.assertEqual(self.items()["RN-02"]["rows"], [first, second])
        result = confirm_item(PID, CID, "RN-02")
        self.assertEqual((result["rows_added"], result["rows_superseded"]), ([], [second]))
        self.assertEqual([r["id"] for r in self.rows()], [first])
        self.assertEqual(self.items()["RN-02"]["rows"], [first])
        text = change_requirements_path(workspace_path(PID), CID).read_text(encoding="utf-8")
        old = text.split(SUPERSEDED_HEADINGS[1])[1]
        self.assertIn(second, old)
        self.assertNotIn(first, old)

    def test_reject_confirmed_supersedes_rows(self):
        confirm_proposals(PID, CID, "all")
        row = self.rows()[0]["id"]
        result = reject_item(PID, CID, "HU-01", "no aplica")
        self.assertEqual((result["action"], result["rows_superseded"]), ("reject", [row]))
        store = load_proposals(workspace_path(PID), CID)
        self.assertNotIn("HU-01", store["items"])
        self.assertEqual([(r["id"], r["reason"]) for r in store["rejections"]], [("HU-01", "no aplica")])
        self.assertIn("at", store["rejections"][0])
        self.assertNotIn(row, [r["id"] for r in self.rows()])
        text = change_requirements_path(workspace_path(PID), CID).read_text(encoding="utf-8")
        self.assertIn(row, text.split(SUPERSEDED_HEADINGS[1])[1])
        for empty in ("", "   "):
            with self.assertRaises(InputError):
                reject_item(PID, CID, "RN-02", empty)

    def test_reject_proposed_without_rows(self):
        result = reject_item(PID, CID, "RN-06", "otra decisión")
        self.assertEqual(result["rows_superseded"], [])
        self.assertNotIn("RN-06", self.items())

    def test_gap_opened_after_proposal_holds_on_confirm(self):
        self.submit(block(
            "RN-03", "- Tratamiento: descarte", "- Motivo: x", '- Cita: "queda en estado Rechazada con su motivo"',
        ))
        self.assertEqual(self.items()["RN-03"]["flags"], [])
        self.open_gap("GAP-TEST-RN03", "La regla RN-03 sobre las altas rechazadas contradice el SAD")
        result = confirm_proposals(PID, CID, "reglas-de-negocio")
        self.assertIn("RN-03", result["held"])
        self.assertNotIn("RN-03", result["confirmed"])
        self.assertEqual(self.items()["RN-03"]["flags"][0]["ref"], "GAP-TEST-RN03")

    def test_confirm_revalidates_surfaces(self):
        self.resolve("scope2.md", SCOPE_WITHOUT_RULE)
        before = len(self.rows())
        result = confirm_item(PID, CID, "RN-04")
        self.assertEqual(result["confirmed"], [])
        self.assertIn("RN-04", result["invalid"])
        self.assertIn("Aprobación por monto", result["invalid"]["RN-04"][0])
        self.assertIn("no están en el borde", result["invalid"]["RN-04"][0])
        self.assertEqual((result["rows_added"], len(self.rows())), ([], before))
        self.assertEqual(self.items()["RN-04"]["status"], "proposed")

    def open_acceptance(self) -> None:
        """The request itemizes its criteria, so the lens round does not open GAP-ACCEPTANCE: open it by hand."""
        self.open_gap("GAP-ACCEPTANCE", "Falta el criterio del alta guardada incompleta")

    def test_gap_rows_untouched(self):
        self.open_acceptance()
        self.resolve("acceptance.md", ACCEPTANCE_ANSWER)
        before = self.rows()
        self.assertEqual(len(before), 1)
        self.assertIn("GAP-ACCEPTANCE", before[0]["source"])
        confirm_proposals(PID, CID, "all")
        confirm_item(PID, CID, "RN-04")
        reject_item(PID, CID, "HU-01", "no aplica")
        reject_item(PID, CID, "RN-02", "se decide aparte")
        self.assertEqual([r for r in self.rows() if "GAP-ACCEPTANCE" in r["source"]], before)

    def test_validate_points_ext_rows_to_extract(self):
        confirm_item(PID, CID, "RN-02")
        self.resolve("scope2.md", SCOPE_WITHOUT_RULE)
        detail = next(c["detail"] for c in validate_change(PID, CID)["checks"] if c["id"] == "rows_have_surfaces")
        self.assertIn("/extract", detail)
        self.assertIn("RN-02", detail)
        self.assertNotIn("/resolve-gaps", detail)

    def test_validate_keeps_gap_rows_on_resolve_gaps(self):
        self.open_acceptance()
        self.resolve("acceptance.md", ACCEPTANCE_ANSWER)
        self.resolve("scope2.md", SCOPE_WITHOUT_RULE.replace("  - adyacente | dato | Tabla de proveedores\n", ""))
        detail = next(c["detail"] for c in validate_change(PID, CID)["checks"] if c["id"] == "rows_have_surfaces")
        self.assertIn("/resolve-gaps", detail)
        self.assertNotIn("/extract", detail)

    @staticmethod
    def _write(name: str, text: str) -> Path:
        path = Path.cwd() / name
        path.write_text(text, encoding="utf-8")
        return path

    def open_gap(self, gap_id: str, description: str) -> None:
        base = workspace_path(PID)
        path = change_gaps_path(base, CID)
        existing = [g for g in parse_gap_rows(path.read_text(encoding="utf-8")) if g.get("id") != "NONE"]
        new = {"id": gap_id, "lens": "technical", "severity": "high", "status": "OPEN", "kind": "client",
               "description": description, "question": "¿Cuál rige?", "evidence_mention": "RN-03",
               "origin": "sources", "resolution_note": ""}
        rows = merge_gaps_by_topic(existing, [new])["gaps"]
        language = change_language(PID, get_change(PID, CID))
        path.write_text(render_gaps(PID, rows, CID, language, path.with_name("gap_elicitation.json")), encoding="utf-8")
        updated = {k: dict(v) for k, v in list_changes(PID).items()}
        updated[CID]["gap_counts"] = count_gaps(rows)
        update_state(PID, changes=updated)


class MatureIds(SnapshotWorkspaceCase):
    @classmethod
    def build_workspace(cls):
        root = Path.cwd()
        shutil.copy(FIXTURES.parent / "change_mature" / "pedido_maduro.md", root / "pedido.md")
        (root / "scope.md").write_text(IDS_SCOPE_ANSWER, encoding="utf-8")
        run_ok(["init", "MAD"])
        run_ok(["ingest", "MAD", "--source", "pedido.md", "--change"])
        run_ok(["resolve-gaps", "MAD", "--source", "scope.md", "--change", CID])
        build_inventory("MAD", CID)

    def test_mature_ids_with_spaces(self):
        text = block(
            "Regla 1", "- Tratamiento: requisito", lines_field("Regla 1", "../change_mature/pedido_maduro.md"),
            '- Cita: "un CUIT duplicado se rechaza con un mensaje que nombra el proveedor existente"',
            "- Enunciado: Cuando el analista envía un alta con un CUIT ya registrado, el sistema debe rechazarla nombrando al proveedor existente.",
            "  - Delta: ADDED", "  - Superficie: Alta de proveedores",
        )
        path = Path.cwd() / "mad.md"
        path.write_text(text, encoding="utf-8")
        self.assertEqual(record_proposals("MAD", CID, path)["recorded"], ["Regla 1"])
        result = confirm_item("MAD", CID, "Regla 1")
        self.assertEqual(result["confirmed"], ["Regla 1"], result)
        rows = load_change_ears("MAD", CID)
        self.assertEqual(len(rows), 1)
        self.assertIn("`EXT:Regla 1`", rows[0]["source"])
        self.assertEqual(load_proposals(workspace_path("MAD"), CID)["items"]["Regla 1"]["rows"], [rows[0]["id"]])


if __name__ == "__main__":
    unittest.main()
