"""IMP-420 (H27 inc 6b) task 7: the project brief v2 transcribes the confirmed extraction (no inventory: nothing changes)."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import ProjectExtractionCase  # noqa: E402
from test_h27_project_confirm import RN02, propose_everything  # noqa: E402

from sentinel.compilers.brief_v2 import collect_inputs, compile_brief_v2  # noqa: E402
from sentinel.core.io import forget_read_snapshots  # noqa: E402
from sentinel.extraction.confirm import confirm_proposals  # noqa: E402
from sentinel.extraction.coverage import extraction_fingerprint  # noqa: E402
from sentinel.extraction.inventory import build_inventory  # noqa: E402
from sentinel.readiness_verdict import build_readiness_verdict  # noqa: E402
from sentinel.workspace import workspace_path  # noqa: E402

PID = ProjectExtractionCase.PID
SETTINGS = {"profiles": ["UI"], "genesis": "greenfield", "validation_direction": "to-build"}
TAIL = "el alta queda en estado Observada"


def compile_brief() -> tuple[str, dict]:
    forget_read_snapshots()
    compile_brief_v2(PID, SETTINGS, "es")
    base = workspace_path(PID) / "02_requirements"
    text = (base / "project-brief.md").read_text(encoding="utf-8")
    return text, json.loads((base / "brief_compile_report.json").read_text(encoding="utf-8"))


class ProjectBriefExtraction(ProjectExtractionCase):
    def confirm(self) -> None:
        propose_everything()
        forget_read_snapshots()
        confirm_proposals(PID, None, "all")
        forget_read_snapshots()

    def test_brief_without_inventory_byte_identical(self):
        inputs = collect_inputs(PID, SETTINGS, "es")
        self.assertEqual(inputs.place_blocks, {})
        self.assertEqual(inputs.place_facts, {})
        self.assertEqual(inputs.empty_na, {})
        self.assertEqual(inputs.extra_annexes, [])
        _text, report = compile_brief()
        self.assertNotIn("extraction_fingerprint", report)

    def test_confirmed_sections_transcribed_verbatim(self):
        self.confirm()
        text, _report = compile_brief()
        self.assertTrue([l for l in text.splitlines() if l.strip() == TAIL or TAIL in l])
        self.assertIn("SEC-proceso", text)
        self.assertFalse([l for l in text.splitlines() if l.startswith("- [NUEVO]") or l.startswith("- [nuevo]")])

    def test_confirmed_rows_as_facts(self):
        self.confirm()
        text, _report = compile_brief()
        line = next(l for l in text.splitlines() if RN02 in l)
        self.assertIn("(REQ-EARS-", line)
        self.assertNotIn("[nuevo]", line)

    def test_report_has_fingerprint_only_with_inventory(self):
        _text, report = compile_brief()
        self.assertNotIn("extraction_fingerprint", report)
        build_inventory(PID, None)
        _text, report = compile_brief()
        self.assertEqual(report["extraction_fingerprint"], extraction_fingerprint(workspace_path(PID), None))

    def test_next_moves_past_brief_after_recompile(self):
        self.confirm()
        compile_brief()
        forget_read_snapshots()
        self.assertNotEqual(build_readiness_verdict(PID)["next_step"]["key"], "brief")


if __name__ == "__main__":
    unittest.main()
