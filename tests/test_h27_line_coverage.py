"""IMP-406 (H27 inc 1) task 4: coverage by lines, partial reading and the verbatim content of the sections."""
from __future__ import annotations

import json
import shutil
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import IDS_SCOPE_ANSWER, SnapshotWorkspaceCase, complete_extraction, run_ok, waive_crosses  # noqa: E402

from sentinel.changes import list_changes  # noqa: E402
from sentinel.core.io import forget_read_snapshots, read_json, write_json  # noqa: E402
from sentinel.errors import InputError  # noqa: E402
from sentinel.extraction import extraction_dir  # noqa: E402
from sentinel.extraction.confirm import confirm_item, confirm_proposals  # noqa: E402
from sentinel.extraction.coverage import extraction_coverage  # noqa: E402
from sentinel.extraction.inventory import build_inventory  # noqa: E402
from sentinel.extraction.lines import compress, content_lines, format_ranges, parse_line_ranges, quote_span  # noqa: E402
from sentinel.extraction.proposals import load_proposals, parse_proposals, record_proposals  # noqa: E402
from sentinel.readiness_verdict import change_next_step  # noqa: E402
from sentinel.workspace import update_state, workspace_path  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"
LARGO = FIXTURES / "change_extraction" / "pedido_largo.md"
PID = "FIN"
CID = "CHG-001"
SEC = "SEC-proceso-to-be-detallado"
P1, P2, P3, P4 = (f"{SEC}.p{n}" for n in range(1, 5))
Q2 = '- Cita: "El analista abre el alta en Borrador y completa los datos fiscales"'
Q4 = '- Cita: "Pendiente de aprobación | Aprobar | Habilitada"'


def source_lines() -> list[str]:
    return LARGO.read_text(encoding="utf-8").replace("\r\n", "\n").split("\n")


def block(element: str, *lines: str) -> str:
    return "\n".join([f"### {element}", *lines, ""])


class Arithmetic(unittest.TestCase):
    def test_parse_line_ranges(self):
        self.assertEqual(parse_line_ranges("59-68"), [[59, 68]])
        self.assertEqual(parse_line_ranges("70–78, 59-69"), [[59, 78]])
        self.assertEqual(parse_line_ranges("12"), [[12, 12]])
        self.assertEqual(parse_line_ranges(" 1 - 3 ;5-6"), [[1, 3], [5, 6]])
        for bad in ("a-b", "9-3", "", "0-3"):
            self.assertIsNone(parse_line_ranges(bad), bad)

    def test_content_lines_skip_markup(self):
        found = content_lines(source_lines(), [[84, 98]])
        self.assertEqual(len(found), 13)
        self.assertNotIn(84, found)
        self.assertNotIn(86, found)

    def test_compress_and_format(self):
        self.assertEqual(compress([70, 59, 60, 61]), [[59, 61], [70, 70]])
        self.assertEqual(format_ranges([[59, 68], [70, 70]]), "59-68, 70-70")

    def test_quote_span(self):
        self.assertEqual(quote_span(source_lines(), [[59, 78]], "tiene 3 días hábiles para reenviarla"), (71, 71))
        self.assertIsNone(quote_span(source_lines(), [[59, 68]], "tiene 3 días hábiles para reenviarla"))


class Lines(SnapshotWorkspaceCase):
    @classmethod
    def build_workspace(cls):
        root = Path.cwd()
        shutil.copy(LARGO, root / "pedido.md")
        (root / "scope.md").write_text(IDS_SCOPE_ANSWER, encoding="utf-8")
        run_ok(["init", PID])
        run_ok(["ingest", PID, "--source", "pedido.md", "--change"])
        run_ok(["resolve-gaps", PID, "--source", "scope.md", "--change", CID])
        run_ok(["sources", PID, "--load", str(FIXTURES / "change_baseline" / "sad-compras.md"),
                "--role", "linea_de_base", "--change", CID])
        waive_crosses(PID, CID)
        build_inventory(PID, CID)

    def submit(self, text: str) -> dict:
        path = Path.cwd() / "p.md"
        path.write_text(text, encoding="utf-8")
        return record_proposals(PID, CID, path)

    def items(self) -> dict:
        forget_read_snapshots()
        return load_proposals(workspace_path(PID), CID)["items"]

    def rejected(self, text: str) -> str:
        result = self.submit(text)
        self.assertEqual(result["recorded"], [], result)
        return " ".join(error for errors in result["rejected"].values() for error in errors)

    def set_language(self, language: str) -> None:
        changes = {k: dict(v) for k, v in list_changes(PID).items()}
        changes[CID]["language"] = language
        update_state(PID, changes=changes)
        forget_read_snapshots()

    def test_full_coverage_is_clean(self):
        result = self.submit(block(P4, "- Tratamiento: seccion", "- Líneas: 85-98", "- Seccion: proceso", Q4))
        self.assertEqual(result["recorded"], [P4], result)
        self.assertEqual(result["flagged"], [])
        item = self.items()[P4]
        self.assertEqual((item["flags"], item["lines"], item["reading"]), ([], [[85, 98]], "completa"))

    def test_uncovered_lines_flagged(self):
        result = self.submit(block(P2, "- Tratamiento: seccion", "- Líneas: 59-68", "- Seccion: proceso", Q2))
        self.assertEqual(result["flagged"], [P2])
        item = self.items()[P2]
        marks = [f for f in item["flags"] if f["kind"] == "lineas_sin_cubrir"]
        self.assertEqual([m["note"] for m in marks], ["faltan 69-78"])
        self.assertEqual(item["missing_lines"], [[69, 78]])
        self.assertEqual(extraction_coverage(PID, CID)["partial_ids"],
                         [{"id": P2, "missing": [[69, 78]], "reading": "completa"}])

    def test_partial_reading_flagged(self):
        quote = '- Cita: "Las transiciones posibles entre estados son las de la tabla siguiente"'
        self.submit(block(P3, "- Tratamiento: seccion", "- Líneas: 80-83", "- Lectura: parcial",
                          "- Seccion: proceso", quote))
        self.assertIn("lectura_parcial", [f["kind"] for f in self.items()[P3]["flags"]])

    def propose_partials(self) -> None:
        quote3 = '- Cita: "Las transiciones posibles entre estados son las de la tabla siguiente"'
        self.submit(
            block(P2, "- Tratamiento: seccion", "- Líneas: 59-68", "- Seccion: proceso", Q2)
            + block(P3, "- Tratamiento: seccion", "- Líneas: 80-83", "- Lectura: parcial", "- Seccion: proceso", quote3))

    def test_partial_never_confirmed(self):
        self.propose_partials()
        result = confirm_proposals(PID, CID, "all")
        self.assertEqual(sorted(result["held"]), sorted([P2, P3]))
        with self.assertRaises(InputError) as caught:
            confirm_item(PID, CID, P2)
        self.assertIn("69-78", str(caught.exception))
        with self.assertRaises(InputError) as caught:
            confirm_item(PID, CID, P3)
        self.assertIn("Lectura: parcial", str(caught.exception))
        self.assertEqual(self.items()[P2]["status"], "proposed")

    def test_partial_step_when_only_partials_remain(self):
        complete_extraction(PID, CID)
        self.propose_partials()
        forget_read_snapshots()
        step = change_next_step(PID, CID)
        self.assertEqual(step["key"], "extract_confirm")
        self.assertEqual(step["title"], "Completar las lecturas parciales")
        self.assertIn(P2, step["text"])
        self.assertTrue(step["command"].startswith(f"/extract {PID} --change {CID} --proposals "), step)

    def test_line_errors(self):
        self.assertIn("falta Líneas", self.rejected(block(
            P1, "- Tratamiento: seccion", "- Seccion: proceso",
            '- Cita: "El alta nace en estado Borrador cuando el analista guarda los datos"')))
        self.assertIn("55-57", self.rejected(block(
            P1, "- Tratamiento: seccion", "- Seccion: proceso",
            '- Cita: "El alta nace en estado Borrador cuando el analista guarda los datos"')))
        self.assertIn("fuera del elemento (líneas 85-98)", self.rejected(block(
            P4, "- Tratamiento: seccion", "- Líneas: 1-3", "- Seccion: proceso", Q4)))
        self.assertIn("la cita está en las líneas 71-71", self.rejected(block(
            P2, "- Tratamiento: seccion", "- Líneas: 59-68", "- Seccion: proceso",
            '- Cita: "tiene 3 días hábiles para reenviarla"')))
        self.assertIn("Lectura debe ser completa o parcial", self.rejected(block(
            P4, "- Tratamiento: seccion", "- Líneas: 85-98", "- Lectura: rara", "- Seccion: proceso", Q4)))
        self.assertIn("Líneas debe ser", self.rejected(block(
            P4, "- Tratamiento: seccion", "- Líneas: x", "- Seccion: proceso", Q4)))

    def test_line_errors_in_english(self):
        self.set_language("en")
        self.assertIn("Lines is missing", self.rejected(block(
            P4, "- Tratamiento: seccion", "- Seccion: proceso", Q4)))
        self.assertIn("Reading must be complete or partial", self.rejected(block(
            P4, "- Tratamiento: seccion", "- Líneas: 85-98", "- Reading: odd", "- Seccion: proceso", Q4)))
        self.submit(block(P2, "- Tratamiento: seccion", "- Lines: 59-68", "- Seccion: proceso", Q2))
        notes = [f["note"] for f in self.items()[P2]["flags"] if f["kind"] == "lineas_sin_cubrir"]
        self.assertEqual(notes, ["missing 69-78"])

    def test_discard_with_lines_covers(self):
        result = self.submit(block(
            "RN-06", "- Tratamiento: descarte", "- Líneas: 35-35", "- Motivo: se trata en otro cambio",
            '- Cita: "Los proveedores del exterior quedan fuera de este cambio."'))
        self.assertEqual((result["recorded"], result["flagged"]), (["RN-06"], []))
        confirm_proposals(PID, CID, "all")
        self.assertEqual(extraction_coverage(PID, CID)["covered"], 1)

    def test_section_keeps_verbatim_table(self):
        self.submit(block(P4, "- Tratamiento: seccion", "- Líneas: 85-98", "- Resumen: tabla de estados",
                          "- Seccion: proceso", Q4))
        confirm_item(PID, CID, P4)
        data = read_json(extraction_dir(workspace_path(PID), CID) / "sections.json", {})
        entry = data["entries"][0]
        self.assertEqual(entry["summary"], "tabla de estados")
        self.assertNotIn("text", entry)
        self.assertIn("| Observada | Vencer el plazo de corrección | Vencida | Sistema |", entry["content"])
        self.assertEqual(entry["lines"], [[85, 98]])

    def test_brief_holds_the_table_as_written(self):
        complete_extraction(PID, CID)
        run_ok(["brief", PID, "--change", CID])
        brief = (workspace_path(PID) / "02_requirements" / CID / "project-brief.md").read_text(encoding="utf-8")
        lines = source_lines()
        brief_lines = brief.splitlines()
        start = next(i for i, line in enumerate(brief_lines) if line.startswith("## 4."))
        end = next(i for i in range(start + 1, len(brief_lines)) if brief_lines[i].startswith("## "))
        body = brief_lines[start:end]
        for number in [85, *range(87, 99)]:
            self.assertIn(lines[number - 1], body, number)
        self.assertIn("texto literal del pedido", "\n".join(body))

    def test_texto_is_a_summary_alias(self):
        blocks, _ = parse_proposals("### A\n- Tratamiento: seccion\n- Texto: algo\n")
        self.assertEqual(blocks["A"]["summary"], "algo")
        self.submit(block(P4, "- Tratamiento: seccion", "- Líneas: 85-98", "- Texto: algo", "- Seccion: proceso", Q4))
        self.assertEqual(self.items()[P4]["summary"], "algo")

    def test_old_proposal_without_lines_is_invalid_at_confirm(self):
        self.submit(block(P4, "- Tratamiento: seccion", "- Líneas: 85-98", "- Seccion: proceso", Q4))
        path = extraction_dir(workspace_path(PID), CID) / "proposals.json"
        forget_read_snapshots()
        data = read_json(path, None)
        for key in ("lines", "reading", "missing_lines"):
            data["items"][P4].pop(key, None)
        write_json(path, data)
        forget_read_snapshots()
        result = confirm_proposals(PID, CID, "all")
        self.assertIn("falta Líneas", " ".join(result["invalid"][P4]))
        self.assertEqual(result["confirmed"], [])


if __name__ == "__main__":
    unittest.main()
