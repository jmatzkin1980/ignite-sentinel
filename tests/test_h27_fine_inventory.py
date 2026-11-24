"""IMP-406 (H27 inc 1) task 3: the fine inventory, with a line range per element and long sections cut in parts."""
from __future__ import annotations

import json
import shutil
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import IDS_SCOPE_ANSWER, SnapshotWorkspaceCase, run_ok, waive_crosses  # noqa: E402

from sentinel.core.io import forget_read_snapshots, read_json, write_json  # noqa: E402
from sentinel.extraction import extraction_dir  # noqa: E402
from sentinel.extraction.confirm import confirm_item  # noqa: E402
from sentinel.extraction.coverage import extraction_coverage  # noqa: E402
from sentinel.extraction.inventory import (  # noqa: E402
    INVENTORY_SCHEMA,
    build_inventory,
    element_lines,
    load_inventory,
    parse_request_elements,
    section_parts,
)
from sentinel.extraction.proposals import load_proposals, record_proposals  # noqa: E402
from sentinel.workspace import workspace_path  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"
IDS = FIXTURES / "change_extraction" / "pedido_ids.md"
LARGO = FIXTURES / "change_extraction" / "pedido_largo.md"
PID = "FIN"
CID = "CHG-001"
SEC = "SEC-proceso-to-be-detallado"
PARTS = [f"{SEC}.p{n}" for n in range(1, 5)]


def lines_of(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8").replace("\r\n", "\n").split("\n")


class Parts(unittest.TestCase):
    def test_section_parts(self):
        self.assertEqual(section_parts(lines_of(LARGO), [[55, 98]]), [[55, 57], [59, 78], [80, 83], [85, 98]])

    def test_long_block_is_cut(self):
        lines = [f"- paso {i}: dato al final" for i in range(1, 46)]
        self.assertEqual(section_parts(lines, [[1, 45]]), [[1, 20], [21, 40], [41, 45]])

    def test_short_and_id_elements_not_split(self):
        ids = parse_request_elements(IDS.read_text(encoding="utf-8"), "F-01", "pedido.md")
        self.assertFalse([e["id"] for e in ids if ".p" in e["id"]])
        largo = parse_request_elements(LARGO.read_text(encoding="utf-8"), "F-01", "pedido.md")
        rest = [e["id"] for e in largo if not e["id"].startswith(SEC)]
        self.assertEqual(rest, [e["id"] for e in ids])
        self.assertEqual([e["id"] for e in largo if e["id"].startswith(SEC)], PARTS)

    def test_element_lines_reads_old_inventories(self):
        self.assertEqual(element_lines({"lines": [3, 5], "line": 1, "end_line": 9}), [3, 5])
        self.assertEqual(element_lines({"line": 4, "end_line": 6}), [4, 6])


class Fine(SnapshotWorkspaceCase):
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

    def extract(self) -> str:
        return run_ok(["extract", PID, "--change", CID])

    def inventory(self) -> dict:
        forget_read_snapshots()
        return load_inventory(workspace_path(PID), CID)

    def test_long_section_split_with_lines(self):
        out = self.extract()
        self.assertIn("1 sección(es) larga(s) partida(s) en 4 parte(s)", json.loads(out)["message"])
        inventory = self.inventory()
        self.assertEqual(inventory["schema_version"], 2)
        by_id = {e["id"]: e for e in inventory["elements"]}
        self.assertNotIn(SEC, by_id)
        for part in PARTS:
            self.assertIn(part, by_id)
        p4 = by_id[PARTS[3]]
        self.assertEqual(p4["lines"], [85, 98])
        self.assertEqual(p4["section_slug"], "proceso-to-be-detallado")
        self.assertEqual(p4["home"], 4)
        self.assertEqual(p4["parent"], SEC)
        self.assertEqual(by_id["RN-02"]["lines"], [31, 31])
        self.assertEqual(by_id["HU-03"]["lines"], [24, 25])
        self.assertTrue(all(e["chars"] > 0 for e in inventory["elements"]))
        self.assertEqual(inventory["split"], {SEC: PARTS})
        sheet = (extraction_dir(workspace_path(PID), CID) / "proposals_template.md").read_text(encoding="utf-8")
        self.assertIn("<!-- proceso-to-be-detallado · F-", sheet)
        self.assertIn(":85-98 · section -->", sheet)
        self.assertIn("- Líneas:", sheet)

    def test_old_inventory_upgrades(self):
        self.extract()
        path = extraction_dir(workspace_path(PID), CID) / "inventory.json"
        forget_read_snapshots()
        data = read_json(path, None)
        data["schema_version"] = 1
        for element in data["elements"]:
            element.pop("lines", None)
            element.pop("chars", None)
        write_json(path, data)
        forget_read_snapshots()
        result = build_inventory(PID, CID)
        inventory = self.inventory()
        self.assertEqual(inventory["schema_version"], INVENTORY_SCHEMA)
        self.assertTrue(all("lines" in e for e in inventory["elements"]))
        self.assertEqual(inventory["version"], data["version"])
        self.assertIs(result["changed"], False)

    def test_split_marks_only_that_section_stale(self):
        with patch("sentinel.extraction.inventory.SPLIT_MIN_LINES", 1000), \
                patch("sentinel.extraction.inventory.SPLIT_MIN_CHARS", 10 ** 6):
            build_inventory(PID, CID)
            blocks = "\n".join([
                f"### {SEC}", "- Tratamiento: seccion", "- Seccion: proceso", "- Líneas: 55-98",
                '- Cita: "El alta nace en estado Borrador"', "",
                "### RN-02", "- Tratamiento: descarte", "- Líneas: 31-31", "- Motivo: se trata en otro cambio",
                '- Cita: "requiere aprobación de la jefa de Compras"', "",
            ])
            proposals = Path.cwd() / "propuestas.md"
            proposals.write_text(blocks, encoding="utf-8")
            result = record_proposals(PID, CID, proposals)
            self.assertEqual(sorted(result["recorded"]), sorted([SEC, "RN-02"]), result)
            confirm_item(PID, CID, SEC)
            confirm_item(PID, CID, "RN-02")
        forget_read_snapshots()
        result = build_inventory(PID, CID)
        self.assertEqual(result["stale_proposals"], [SEC])
        items = load_proposals(workspace_path(PID), CID)["items"]
        self.assertEqual(items["RN-02"]["status"], "confirmed")
        coverage = extraction_coverage(PID, CID)
        self.assertEqual(coverage["stale_items"], [SEC])
        self.assertEqual(coverage["covered"], 1)


if __name__ == "__main__":
    unittest.main()
