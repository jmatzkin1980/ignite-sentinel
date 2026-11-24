"""IMP-402 (H26 inc 3) task 2: proposals, format and validation."""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import IDS_SCOPE_ANSWER, SnapshotWorkspaceCase, lines_field, run_ok  # noqa: E402

from sentinel.errors import GateRefusal, InputError  # noqa: E402
from sentinel.extraction import extraction_dir  # noqa: E402
from sentinel.extraction.inventory import build_inventory, load_inventory  # noqa: E402
from sentinel.extraction.proposals import (  # noqa: E402
    load_proposals,
    parse_proposals,
    record_proposals,
    validate_proposal,
)
from sentinel.workspace import workspace_path  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "change_extraction"
EXAMPLE = FIXTURES / "propuestas_ejemplo.md"
PID = "EXP"
CID = "CHG-001"
RN02_QUOTE = '- Cita: "requiere aprobación de la jefa de Compras"'
GOOD_STATEMENT = "- Enunciado: Cuando el analista envía un alta, el sistema debe dejarla Pendiente de aprobación."
OK_FIELDS = ["  - Delta: ADDED", "  - Superficie: Tabla de proveedores"]
EXTERIOR = '- Cita: "Los proveedores del exterior quedan fuera"'


def block(element: str, *lines: str) -> str:
    """A block; the first line (Tratamiento) is followed by the full `Líneas` of the element (IMP-406)."""
    span = lines_field(element)
    body = [lines[0], span, *lines[1:]] if lines and span else list(lines)
    return "\n".join([f"### {element}", *body, ""])


class Parsing(unittest.TestCase):
    def test_parse_example(self):
        blocks, warnings = parse_proposals(EXAMPLE.read_text(encoding="utf-8"))
        self.assertEqual(list(blocks), ["HU-01", "RN-02", "RN-04", "SEC-objetivo", "RN-06"])
        self.assertEqual(warnings, [])
        statements = blocks["RN-02"]["statements"]
        self.assertEqual([s["surface"] for s in statements], ["Aprobación por monto", "Tabla de proveedores"])
        self.assertEqual(blocks["RN-04"]["flag"], "contradiccion")
        self.assertIn("SAD", blocks["RN-04"]["flag_note"])
        self.assertEqual(blocks["HU-01"]["quote"], "quiero enviar un alta a aprobación para no imprimir el resumen")

    def test_parse_english_labels(self):
        text = "\n".join([
            "### RN-02", "- Treatment: requirement", "- Quote: “requiere aprobación de la jefa de Compras”",
            "- Statement: When x, the system shall y.", "  - Delta: ADDED", "  - Surface: Aprobación por monto",
            "- Statement: While a, the system shall b.", "  - Delta: ADDED", "  - Surface: Tabla de proveedores",
            "- Flag: contradiction: algo", "",
        ])
        raw = parse_proposals(text)[0]["RN-02"]
        self.assertEqual(raw["treatment"], "requirement")
        self.assertEqual(raw["quote"], "requiere aprobación de la jefa de Compras")
        self.assertEqual([s["surface"] for s in raw["statements"]], ["Aprobación por monto", "Tabla de proveedores"])
        self.assertEqual((raw["flag"], raw["flag_note"]), ("contradiction", "algo"))

    def test_repeated_id_warns_and_last_wins(self):
        blocks, warnings = parse_proposals("### A\n- Tratamiento: descarte\n### A\n- Tratamiento: seccion\n")
        self.assertEqual((blocks["A"]["treatment"], warnings), ("seccion", ["A"]))

    def test_comments_and_quotes_ignored(self):
        blocks, _ = parse_proposals("### A\n<!-- x -->\n> - Tratamiento: seccion\n- Tratamiento: descarte\n")
        self.assertEqual(blocks["A"]["treatment"], "descarte")


class ProposalsCase(SnapshotWorkspaceCase):
    @classmethod
    def build_workspace(cls):
        root = Path.cwd()
        shutil.copy(FIXTURES / "pedido_ids.md", root / "pedido.md")
        (root / "scope.md").write_text(IDS_SCOPE_ANSWER, encoding="utf-8")
        run_ok(["init", PID])
        run_ok(["ingest", PID, "--source", "pedido.md", "--change"])
        run_ok(["resolve-gaps", PID, "--source", "scope.md", "--change", CID])
        build_inventory(PID, CID)

    def submit(self, text: str, name: str = "p.md") -> dict:
        path = Path.cwd() / name
        path.write_text(text, encoding="utf-8")
        return record_proposals(PID, CID, path)

    def rejected(self, text: str) -> list[str]:
        result = self.submit(text)
        self.assertEqual(result["recorded"], [], result)
        return [error for errors in result["rejected"].values() for error in errors]

    def requirement(self, *lines: str) -> str:
        return block("RN-02", "- Tratamiento: requisito", RN02_QUOTE, *lines)


class Recording(ProposalsCase):
    def test_record_example(self):
        result = record_proposals(PID, CID, EXAMPLE)
        self.assertEqual(result["action"], "proposals")
        self.assertEqual(result["rejected"], {})
        self.assertEqual(result["recorded"], ["HU-01", "RN-02", "RN-04", "SEC-objetivo", "RN-06"])
        self.assertEqual(result["flagged"], ["RN-04"])
        base = workspace_path(PID)
        stored = json.loads((extraction_dir(base, CID) / "proposals.json").read_text(encoding="utf-8"))
        rn02 = stored["items"]["RN-02"]
        self.assertEqual(rn02["status"], "proposed")
        self.assertEqual(rn02["statements"][1]["surfaces"], ["Tabla de proveedores"])
        self.assertEqual(rn02["statements"][0]["surfaces"], ["Aprobación por monto"])
        self.assertTrue((extraction_dir(base, CID) / "submitted" / "001-propuestas_ejemplo.md").is_file())
        self.assertEqual(stored["items"]["SEC-objetivo"]["brief_section"], 2)
        self.assertEqual(stored["items"]["RN-04"]["flags"][0]["kind"], "contradiccion")
        shas = {e["id"]: e["sha"] for e in load_inventory(base, CID)["elements"]}
        self.assertEqual(rn02["element_sha"], shas["RN-02"])
        # the inventory reads this shape: nothing is stale, and a changed sha is
        self.assertEqual(build_inventory(PID, CID)["stale_proposals"], [])
        stored["items"]["RN-02"]["element_sha"] = "0" * 16
        (extraction_dir(base, CID) / "proposals.json").write_text(json.dumps(stored), encoding="utf-8")
        self.assertEqual(build_inventory(PID, CID)["stale_proposals"], ["RN-02"])
        # a second submission gets the next number
        self.submit(block("RN-06", "- Tratamiento: descarte", "- Motivo: x", EXTERIOR))
        self.assertTrue((extraction_dir(base, CID) / "submitted" / "002-p.md").is_file())

    def test_quote_rules(self):
        short = block("RN-02", "- Tratamiento: descarte", "- Motivo: x", '- Cita: "requiere aprobación"')
        self.assertIn("menos de 20", self.rejected(short)[0])
        other = block("RN-02", "- Tratamiento: descarte", "- Motivo: x",
                      '- Cita: "Un alta rechazada no se elimina: queda en estado Rechazada"')
        found = self.rejected(other)[0]
        self.assertIn("no aparece literal", found)
        self.assertIn("pedido.md", found)
        crossing = block("SEC-usuarios", "- Tratamiento: seccion", "- Seccion: usuarios",
                         '- Cita: "carga el alta del proveedor. - Jefa de Compras"')
        self.assertEqual(self.submit(crossing)["recorded"], ["SEC-usuarios"])
        self.assertIn("falta Cita", self.rejected(block("RN-02", "- Tratamiento: descarte", "- Motivo: x"))[0])

    def test_statement_rules(self):
        self.assertIn("no es EARS", self.rejected(self.requirement("- Enunciado: El alta queda pendiente.", *OK_FIELDS))[0])
        two = ("- Enunciado: Cuando el analista envía un alta, el sistema debe dejarla pendiente. "
               "Mientras está pendiente, el sistema debe impedir órdenes de compra.")
        self.assertIn("más de un enunciado EARS", self.rejected(self.requirement(two, *OK_FIELDS))[0])
        self.assertIn("necesita Delta", self.rejected(self.requirement(GOOD_STATEMENT, OK_FIELDS[1]))[0])
        unknown = self.requirement(GOOD_STATEMENT, OK_FIELDS[0], "  - Superficie: Pantalla inexistente")
        self.assertIn("no están en el borde", self.rejected(unknown)[0])
        self.assertIn("necesita Superficie", self.rejected(self.requirement(GOOD_STATEMENT, OK_FIELDS[0]))[0])
        self.assertIn("necesita al menos un Enunciado", self.rejected(self.requirement())[0])
        orphan = self.requirement("  - Delta: ADDED", GOOD_STATEMENT, *OK_FIELDS)
        self.assertIn("sin un Enunciado antes", " ".join(self.rejected(orphan)))
        bad_affects = self.requirement(GOOD_STATEMENT, "  - Delta: MODIFIED", OK_FIELDS[1], "  - Afecta: algo")
        self.assertIn("Afecta", self.rejected(bad_affects)[0])

    def test_affects_kept_only_for_modified_or_removed(self):
        def submit(delta: str) -> dict:
            return self.submit(self.requirement(
                GOOD_STATEMENT, f"  - Delta: {delta}", OK_FIELDS[1], "  - Afecta: US-001"))

        self.assertEqual(submit("MODIFIED")["recorded"], ["RN-02"])
        base = workspace_path(PID)
        self.assertEqual(load_proposals(base, CID)["items"]["RN-02"]["statements"][0]["affects"], ["US-001"])
        submit("ADDED")
        self.assertEqual(load_proposals(base, CID)["items"]["RN-02"]["statements"][0]["affects"], [])

    def test_section_and_discard_rules(self):
        quote = '- Cita: "la jefatura aprueba las altas de monto alto"'
        bad = block("SEC-objetivo", "- Tratamiento: seccion", "- Seccion: glosario", quote)
        self.assertIn("Seccion debe ser", self.rejected(bad)[0])
        self.submit(block("SEC-objetivo", "- Treatment: section", "- Section: acceptance", quote))
        item = load_proposals(workspace_path(PID), CID)["items"]["SEC-objetivo"]
        self.assertEqual((item["section"], item["brief_section"]), ("aceptacion", 7))
        no_reason = block("RN-06", "- Tratamiento: descarte", EXTERIOR)
        self.assertIn("necesita Motivo", self.rejected(no_reason)[0])
        bad_flag = block("RN-06", "- Tratamiento: descarte", "- Motivo: x", "- Marca: rara — nota", EXTERIOR)
        self.assertIn("Marca debe ser", self.rejected(bad_flag)[0])

    def test_unknown_element_and_bad_treatment(self):
        errors = self.rejected(block("RN-99", "- Tratamiento: descarte") + block("RN-01", "- Tratamiento: quizas"))
        self.assertIn("no está en el inventario", errors[0])
        self.assertIn("Tratamiento debe ser", errors[1])

    def test_english_messages(self):
        element = next(e for e in load_inventory(workspace_path(PID), CID)["elements"] if e["id"] == "RN-06")
        raw = parse_proposals(block("RN-06", "- Treatment: discard", '- Quote: "short"'))[0]["RN-06"]
        item, errors = validate_proposal(element, "text", raw, [], "en", {"pid": PID, "cid": CID})
        self.assertIsNone(item)
        self.assertIn("RN-06: the text changed in the source", errors[0])

    def test_correction_replaces(self):
        record_proposals(PID, CID, EXAMPLE)
        self.submit(block("RN-02", "- Tratamiento: descarte", "- Motivo: se decide aparte", RN02_QUOTE))
        items = load_proposals(workspace_path(PID), CID)["items"]
        self.assertEqual(list(items).count("RN-02"), 1)
        self.assertEqual(items["RN-02"]["treatment"], "descarte")
        self.assertEqual(items["RN-02"]["statements"], [])
        self.assertTrue(items["RN-02"]["submitted"].endswith("002-p.md"))

    def test_rejected_keeps_previous_proposal(self):
        record_proposals(PID, CID, EXAMPLE)
        result = self.submit(block("RN-02", "- Tratamiento: descarte"))
        self.assertIn("RN-02", result["rejected"])
        store = load_proposals(workspace_path(PID), CID)
        self.assertEqual(store["items"]["RN-02"]["treatment"], "requisito")
        self.assertEqual(store["rejections"][0]["id"], "RN-02")

    def test_confirmed_rows_survive_a_correction(self):
        record_proposals(PID, CID, EXAMPLE)
        base = workspace_path(PID)
        path = extraction_dir(base, CID) / "proposals.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["items"]["RN-06"].update({"status": "confirmed", "rows": ["REQ-1"]})
        path.write_text(json.dumps(data), encoding="utf-8")
        self.submit(block("RN-06", "- Tratamiento: descarte", "- Motivo: otro", EXTERIOR))
        item = load_proposals(base, CID)["items"]["RN-06"]
        self.assertEqual((item["status"], item["rows"]), ("proposed", ["REQ-1"]))
        self.submit(block("RN-06", "- Tratamiento: descarte", "- Motivo: otra vez", EXTERIOR), name="q.md")
        item = load_proposals(base, CID)["items"]["RN-06"]
        self.assertEqual((item["status"], item["rows"], item["reason"]), ("proposed", ["REQ-1"], "otra vez"))

    def test_bom_file_keeps_first_block(self):
        path = Path.cwd() / "bom.md"
        path.write_bytes(b"\xef\xbb\xbf" + block("RN-06", "- Tratamiento: descarte", "- Motivo: x", EXTERIOR).encode("utf-8"))
        self.assertEqual(record_proposals(PID, CID, path)["recorded"], ["RN-06"])

    def test_empty_treatment_is_skipped(self):
        sheet = (extraction_dir(workspace_path(PID), CID) / "proposals_template.md").read_text(encoding="utf-8")
        result = self.submit(sheet + "\n" + block("RN-06", "- Tratamiento: descarte", "- Motivo: x", EXTERIOR))
        self.assertEqual(result["rejected"], {})
        self.assertIn("RN-01", result["skipped"])
        self.assertEqual(result["recorded"], ["RN-06"])

    def test_no_blocks_is_input_error(self):
        with self.assertRaises(InputError):
            self.submit("nada que ver\n")

    def test_changed_source_is_stale_element(self):
        changed = False
        for path in workspace_path(PID).rglob("pedido.md"):
            text = path.read_text(encoding="utf-8")
            path.write_text(text.replace("quedan fuera de este cambio", "quedan fuera del cambio"), encoding="utf-8")
            changed = True
        self.assertTrue(changed)
        found = self.rejected(block("RN-06", "- Tratamiento: descarte", "- Motivo: x", EXTERIOR))
        self.assertIn("el texto cambió", found[0])

    def test_review_groups_by_section(self):
        result = record_proposals(PID, CID, EXAMPLE)
        review = Path(result["review_path"]).read_text(encoding="utf-8")
        self.assertIn("--confirm reglas-de-negocio", review)
        flagged = review.split("## Marcadas")[1]
        line = next(line for line in flagged.splitlines() if "RN-04" in line)
        self.assertIn("contradiccion", line)
        self.assertIn("- RN-01 — — — pendiente", review)
        self.assertIn("- RN-02 — requisito — propuesta — «requiere aprobación de la jefa de Compras»", review)


class Refusals(ProposalsCase):
    def test_missing_inventory(self):
        (extraction_dir(workspace_path(PID), CID) / "inventory.json").unlink()
        with self.assertRaises(GateRefusal) as caught:
            record_proposals(PID, CID, EXAMPLE)
        self.assertIn("/extract", str(caught.exception))
        self.assertIn("falta", str(caught.exception))

    def test_stale_inventory(self):
        second = Path.cwd() / "pedido-2.md"
        second.write_text("## Reglas\n- RN-01: Otra regla del segundo pedido.\n", encoding="utf-8")
        run_ok(["sources", PID, "--load", str(second), "--role", "pedido", "--change", CID])
        with self.assertRaises(GateRefusal) as caught:
            record_proposals(PID, CID, EXAMPLE)
        self.assertIn("/extract", str(caught.exception))
        self.assertIn("quedó viejo", str(caught.exception))


class BeforeBorder(SnapshotWorkspaceCase):
    @classmethod
    def build_workspace(cls):
        shutil.copy(FIXTURES / "pedido_ids.md", Path.cwd() / "pedido.md")
        run_ok(["init", "EXR"])
        run_ok(["ingest", "EXR", "--source", "pedido.md", "--change"])

    def test_names_gap_scope(self):
        with self.assertRaises(GateRefusal) as caught:
            record_proposals("EXR", CID, EXAMPLE)
        self.assertIn("GAP-SCOPE", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
