"""IMP-322: an answer is never dropped without a word.

The independent review found three answers that vanished with exit 0: an answer written
as indented bullets under `- Answer:` (the format the gap itself asks for), the first
answer of a file saved with a UTF-8 BOM, and an answer under a gap id that is not in
gaps.md. It also found that a gap closed without `Evidence or reference` was only flagged
in the command's JSON, not in the stored report.
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import SnapshotWorkspaceCase, run_ok  # noqa: E402

from sentinel.gaps import parse_gap_responses  # noqa: E402

PROJECT = "ANSW"

RAW = """# Operations Risk Dashboard

Objective: let operations leads review risk queues before the daily meeting.

Users: operations leads.

Scope: a read-only dashboard for the current quarter.
"""

ACCEPTANCE = (
    "### GAP-ACCEPTANCE\n"
    "- Answer: When a queue has cases above the SLA threshold, the dashboard shall mark the queue as high risk.\n"
    "- Owner / source: Client workshop\n"
    "- Evidence or reference: Synthetic workshop notes\n"
    "- Decision status: confirmed\n"
)


class ParserTests(unittest.TestCase):
    def test_bulleted_answer_is_read(self):
        block = (
            "### GAP-SCOPE\n"
            "- Answer:\n"
            "  - In scope: the read-only dashboard\n"
            "  - Out of scope: editing tickets\n"
            "- Owner / source: Product owner\n"
            "- Evidence or reference: Kickoff minutes\n"
            "- Decision status: confirmed\n"
        )
        answer = parse_gap_responses(block)["GAP-SCOPE"]["answer"]
        self.assertIn("In scope: the read-only dashboard", answer)
        self.assertIn("Out of scope: editing tickets", answer)

    def test_single_line_fields_are_unchanged(self):
        response = parse_gap_responses(ACCEPTANCE)["GAP-ACCEPTANCE"]
        self.assertEqual(response["owner"], "Client workshop")
        self.assertEqual(response["decision_status"], "confirmed")


class ResolveGapsTests(SnapshotWorkspaceCase):
    @classmethod
    def build_workspace(cls) -> None:
        root = Path.cwd()
        (root / "raw.md").write_text(RAW, encoding="utf-8")
        run_ok(["init", PROJECT, "--brief-version", "1"])
        run_ok(["ingest", PROJECT, "--source", str(root / "raw.md")])

    def resolve(self, name: str, text: str, encoding: str = "utf-8") -> dict:
        path = self.temp / name
        path.write_text(text, encoding=encoding)
        return json.loads(run_ok(["resolve-gaps", PROJECT, "--source", str(path)]))

    def test_bom_file_keeps_its_first_answer(self):
        result = self.resolve("bom.md", ACCEPTANCE, encoding="utf-8-sig")
        self.assertIn("GAP-ACCEPTANCE", result["closed"])

    def test_unknown_gap_id_is_reported(self):
        typo = ACCEPTANCE.replace("GAP-ACCEPTANCE", "GAP-ACCEPTANCES")
        result = self.resolve("typo.md", typo)
        self.assertEqual(result["unknown_gap_ids"], ["GAP-ACCEPTANCES"])
        self.assertTrue(any("GAP-ACCEPTANCES" in finding for finding in result["closure_findings"]))

    def test_findings_are_in_the_stored_report(self):
        no_evidence = ACCEPTANCE.replace("Synthetic workshop notes", "")
        result = self.resolve("noevidence.md", no_evidence)
        self.assertIn("GAP-ACCEPTANCE", result["closed"])
        report = Path(result["path"]).read_text(encoding="utf-8")
        self.assertIn("## Findings", report)
        self.assertIn("closed without a citation", report)


if __name__ == "__main__":
    unittest.main()
