"""IMP-416 task 3: specs.md of a change is the AI-ready document, one section per functionality."""
from __future__ import annotations

import json
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import SnapshotWorkspaceCase, run_ok, waive_crosses  # noqa: E402
from test_change_specs import ALL_ANSWERS, answer, open_change  # noqa: E402
from test_h26_cross_record import set_language  # noqa: E402
from test_h27_consolidation import CID, PID, ConsolidationCase  # noqa: E402

from sentinel.compilers.change_backlog import specs_currency  # noqa: E402
from sentinel.compilers.change_spec_doc import BLOCKS, NO_DATA  # noqa: E402
from sentinel.core.io import forget_read_snapshots  # noqa: E402
from sentinel.workspace import workspace_path  # noqa: E402

TABLE = "Tabla de proveedores"


def section(text: str, head: str) -> str:
    """The `## ` section that starts with `head`."""
    start = text.index(head)
    end = text.find("\n## ", start + 1)
    return text[start:end if end >= 0 else len(text)]


def block(text: str, title: str) -> str:
    start = text.index(f"### {title}")
    end = text.find("\n### ", start + 1)
    return text[start:end if end >= 0 else len(text)]


class Consolidated(ConsolidationCase):
    def setUp(self):
        super().setUp()
        self.submit_text(self.rep())
        forget_read_snapshots()
        run_ok(["extract", PID, "--change", CID, "--confirm-replacement", "RN-02"])
        waive_crosses(PID, CID)
        run_ok(["brief", PID, "--change", CID])
        forget_read_snapshots()
        run_ok(["specs", PID, "--change", CID])
        self.text = (workspace_path(PID) / "03_specs" / CID / "specs.md").read_text(encoding="utf-8")

    def fun(self) -> str:
        found = re.search(r"^## FUN-\d+ — Aprobación por monto \(", self.text, re.M)
        self.assertIsNotNone(found, self.text)
        return section(self.text, found.group(0))

    def test_one_section_per_functionality_with_eight_blocks(self):
        titles = re.findall(r"^### (.+)$", self.fun(), re.M)
        self.assertEqual(titles, BLOCKS["es"])

    def test_objective_quotes_consolidated_text(self):
        objective = block(self.fun(), BLOCKS["es"][0])
        self.assertIn("mayor a 1.000.000 requiere aprobación de la jefa de Compras", objective)
        self.assertRegex(objective, r":L\d+")
        self.assertIn(self.dis, objective)  # IMP-416 I-5: the quote names the GAP decision its text comes from
        self.assertNotIn("5.000.000", objective)

    def test_decisions_block_names_gap(self):
        decisions = block(self.fun(), BLOCKS["es"][5])
        self.assertTrue(any(line.startswith(f"| {self.dis} |") for line in decisions.splitlines()), decisions)

    def test_traceability_row(self):
        trace = self.text.split("## Trazabilidad", 1)[1]
        self.assertIn("| Unidad | REQ-EARS | Elemento | Cita | Superficie | GAP |", trace)
        row = next(line for line in trace.splitlines() if "| RN-02 |" in line)
        for part in (":L31", "Aprobación por monto", self.dis):
            self.assertIn(part, row)
        self.assertNotIn("## Unidades", self.text)


class Plain(SnapshotWorkspaceCase):
    cid = "CHG-001"

    @classmethod
    def build_workspace(cls):
        run_ok(["init", "DOCP"])
        cid = open_change("DOCP")
        answer("DOCP", cid, "a.md", ALL_ANSWERS)
        run_ok(["brief", "DOCP", "--change", cid])

    def specs(self) -> str:
        run_ok(["specs", "DOCP", "--change", self.cid])
        return (workspace_path("DOCP") / "03_specs" / self.cid / "specs.md").read_text(encoding="utf-8")

    def report_path(self) -> Path:
        return workspace_path("DOCP") / "03_specs" / self.cid / "change_specs_report.json"

    def test_empty_blocks_say_no_data(self):
        text = self.specs()
        body = section(text, f"## FUN-01 — {TABLE}")
        empty = f"_{NO_DATA['es']}_"
        self.assertIn(empty, block(body, BLOCKS["es"][1]))
        self.assertIn("existente", block(body, BLOCKS["es"][3]))
        self.assertIn(empty, block(body, BLOCKS["es"][6]))
        self.assertIn(empty, block(body, BLOCKS["es"][7]))
        to_be = block(body, BLOCKS["es"][2])
        self.assertEqual(len(re.findall(r"^- SPEC-U-\d+ ", to_be, re.M)), 3)
        self.assertIn("[ADDED]", to_be)
        self.assertIn("[MODIFIED]", to_be)
        regression = block(body, BLOCKS["es"][4])
        self.assertIn("pass-to-pass", regression)
        self.assertIn("continuar validando", regression)

    def test_report_keeps_deltas_and_adds_functionalities(self):
        self.specs()
        report = json.loads(self.report_path().read_text(encoding="utf-8"))
        self.assertEqual(len(report["deltas"]), 3)
        self.assertEqual(len(report["units"]), 3)
        self.assertEqual(report["functionalities"]["FUN-01"]["units"], report["units"])
        self.assertRegex(report["functionalities_sha"], r"^[0-9a-f]{16}$")
        self.assertEqual(specs_currency("DOCP", self.cid), "current")

    def test_old_report_is_old(self):
        self.specs()
        report = json.loads(self.report_path().read_text(encoding="utf-8"))
        del report["functionalities"]
        self.report_path().write_text(json.dumps(report), encoding="utf-8")
        forget_read_snapshots()
        self.assertEqual(specs_currency("DOCP", self.cid), "old")

    def test_border_change_makes_specs_stale(self):
        self.specs()
        self.assertEqual(specs_currency("DOCP", self.cid), "current")
        before = json.loads(self.report_path().read_text(encoding="utf-8"))
        moved = ALL_ANSWERS.replace(
            "- Delta: MODIFIED\n- Superficie: Tabla de proveedores", '- Delta: MODIFIED\n- Superficie: Listado "Mis borradores"')
        self.assertNotEqual(moved, ALL_ANSWERS)
        answer("DOCP", self.cid, "m.md", moved)
        forget_read_snapshots()
        self.assertEqual(json.loads(self.report_path().read_text(encoding="utf-8")), before)
        self.assertEqual(specs_currency("DOCP", self.cid), "stale")

    def test_english_doc(self):
        set_language("DOCP", "en")
        text = self.specs()
        self.assertIn("### Objective", text)
        self.assertIn(f"_{NO_DATA['en']}_", text)
        self.assertIn("| Unit | REQ-EARS | Element | Citation | Surface | GAP |", text)
        self.assertNotIn("sin dato registrado", text)
        # IMP-416 M-2: the types and zones of the header and of the interface lines follow the change language
        self.assertRegex(text, r"(?m)^## FUN-01 — .+ \(data item, adjacent\)$")
        self.assertRegex(text, r"(?m)^- data item — .+ — existing")


if __name__ == "__main__":
    unittest.main()
