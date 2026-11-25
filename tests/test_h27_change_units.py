"""IMP-416 task 2: the units of a change cite the line of the request and use the language of the change."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import SnapshotWorkspaceCase, run_ok, waive_crosses  # noqa: E402
from test_change_specs import ALL_ANSWERS, answer, open_change  # noqa: E402
from test_h26_cross_record import set_language  # noqa: E402
from test_h27_consolidation import CID, PID, ConsolidationCase  # noqa: E402

from sentinel.change_validation import validate_change  # noqa: E402
from sentinel.compilers.change_backlog import read_change_units  # noqa: E402
from sentinel.compilers.change_specs import unit_sources  # noqa: E402
from sentinel.compilers.specs import render_spec_unit, spec_unit_pattern, spec_unit_statement  # noqa: E402
from sentinel.extraction.coverage import extraction_view  # noqa: E402
from sentinel.core.io import forget_read_snapshots  # noqa: E402
from sentinel.core.markdown import parse_frontmatter  # noqa: E402
from sentinel.workspace import workspace_path  # noqa: E402

BRIEF = f"02_requirements/{CID}/project-brief.md"
UNIT = {
    "id": "SPEC-U-001", "title": "SPEC-U-001 - REQ-EARS-001", "status": "evidence-backed",
    "trace_ids": ["REQ-EARS-001"], "ears": ["REQ-EARS-001"], "sources": ["02_requirements/requirements.md"],
    "pattern": "event-driven", "statement": "Cuando se da de alta un proveedor, el sistema debe validar el CUIT.",
    "source": "`02_requirements/requirements.md`",
}


class Pure(unittest.TestCase):
    def test_project_unit_unchanged(self):
        text = render_spec_unit("SUP", UNIT)
        self.assertEqual(text, render_spec_unit("SUP", UNIT, "en"))
        for label in ("## Evidence Basis", "## Normalized Requirement", "- Pattern:", "| Source | Anchor |", "| Pointer |"):
            self.assertIn(label, text)

    def test_spanish_headers_parse_back(self):
        text = render_spec_unit("SUP", UNIT, "es")
        for label in ("## Base de evidencia", "## Requisito normalizado", "## Puntero de ejecución", "- Patrón:"):
            self.assertIn(label, text)
        self.assertNotIn("Evidence Basis", text)
        self.assertEqual(spec_unit_statement(text), UNIT["statement"])
        self.assertEqual(spec_unit_pattern(text), "event-driven")
        self.assertEqual(spec_unit_statement(render_spec_unit("SUP", UNIT)), UNIT["statement"])

    def test_unit_sources_pure(self):
        element = {"path": "00_raw/pedido.md", "spans": [[31, 31], [40, 42]]}
        row = {"source": "`EXT:RN-02`"}
        self.assertEqual(unit_sources(row, {"RN-02": element}, CID),
                         [f"02_requirements/{CID}/requirements.md#normalized-requirements-ears",
                          "00_raw/pedido.md:L31", "00_raw/pedido.md:L40-L42"])
        for other in ({"source": "`GAP-ACCEPTANCE`"}, {"source": "`EXT:RN-09`"}):
            self.assertIn(BRIEF, unit_sources(other, {"RN-02": element}, CID))


class Anchored(ConsolidationCase):
    def build(self) -> dict:
        waive_crosses(PID, CID)
        run_ok(["brief", PID, "--change", CID])
        forget_read_snapshots()
        return json.loads(run_ok(["specs", PID, "--change", CID]))

    def units(self) -> list[dict]:
        forget_read_snapshots()
        return read_change_units(PID, CID)

    def test_unit_cites_element_lines(self):
        self.build()
        forget_read_snapshots()
        path = next(e for e in extraction_view(PID, CID)["elements"] if e["id"] == "RN-02")["path"]
        unit = next(u for u in self.units() if "RN-02" in u["statement"] or u["delta"] == "MODIFIED")
        self.assertIn(f"{path}:L31", unit["sources"])
        self.assertNotIn(BRIEF, unit["sources"])
        text = unit["path"].read_text(encoding="utf-8")
        self.assertIn("## Base de evidencia", text)
        self.assertRegex(text, r"\| `[^`]*:L31` \| Puntero \|")
        self.assertEqual(validate_change(PID, CID)["checks"][0]["id"], "unit_citations")
        self.assertEqual(validate_change(PID, CID)["checks"][0]["status"], "PASS")

    def test_unit_without_brief_or_anchor_fails(self):
        self.build()
        unit = self.units()[0]
        text = unit["path"].read_text(encoding="utf-8")
        front = parse_frontmatter(text)
        for source in front["sources"]:
            text = text.replace(f"  - {source}\n", "  - 00_raw/pedido.md\n")
        unit["path"].write_text(text, encoding="utf-8")
        forget_read_snapshots()
        check = next(c for c in validate_change(PID, CID)["checks"] if c["id"] == "unit_citations")
        self.assertEqual(check["status"], "FAIL")

    def test_english_change_units(self):
        set_language(PID, "en")
        self.build()
        text = self.units()[0]["path"].read_text(encoding="utf-8")
        self.assertIn("## Evidence Basis", text)
        self.assertNotIn("Base de evidencia", text)


class GapAnswer(SnapshotWorkspaceCase):
    @classmethod
    def build_workspace(cls):
        run_ok(["init", "GAPU"])
        cid = open_change("GAPU")
        answer("GAPU", cid, "a.md", ALL_ANSWERS)
        run_ok(["brief", "GAPU", "--change", cid])
        run_ok(["specs", "GAPU", "--change", cid])

    def test_gap_answer_unit_keeps_brief_path(self):
        units = read_change_units("GAPU", "CHG-001")
        self.assertTrue(units)
        for unit in units:
            self.assertIn("02_requirements/CHG-001/project-brief.md", unit["sources"])
            self.assertTrue(unit["statement"])
            self.assertIn("## Base de evidencia", unit["path"].read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
