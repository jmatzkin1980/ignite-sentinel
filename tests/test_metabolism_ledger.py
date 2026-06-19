from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from sentinel.assumptions import apply_assumptions
from sentinel.cli import main
from sentinel.discovery import parse_gap_rows
from sentinel.gap_resolution import resolve_gaps
from sentinel.health import run_health
from sentinel.sync import sync_change


RAW = (
    "# Operations Risk Board\n\n"
    "Support leads need a board for queue risk before the daily standup. "
    "The team currently uses the current queue risk taxonomy during manual triage."
)


class KnowledgeMetabolismTests(unittest.TestCase):
    def setUp(self) -> None:
        self.old_cwd = Path.cwd()
        self.temp = Path(tempfile.mkdtemp())
        os.chdir(self.temp)
        self.raw = self.temp / "risk-board.md"
        self.raw.write_text(RAW, encoding="utf-8")
        self.assertEqual(main(["init", "METAB"]), 0)
        self.assertEqual(main(["ingest", "METAB", "--source", str(self.raw)]), 0)
        self.ws = self.temp / "workspaces" / "METAB"
        self.gap_id = self._first_gap_id()

    def tearDown(self) -> None:
        os.chdir(self.old_cwd)
        shutil.rmtree(self.temp, ignore_errors=True)

    def _first_gap_id(self) -> str:
        gaps = parse_gap_rows((self.ws / "01_discovery" / "gaps.md").read_text(encoding="utf-8"))
        for gap in gaps:
            if gap.get("id") != "NONE":
                return gap["id"]
        self.fail("Synthetic fixture should produce at least one gap.")

    def _assume(self) -> None:
        source = self.temp / "assumptions.json"
        source.write_text(
            json.dumps(
                {
                    "assumptions": [
                        {
                            "id": "ASM-RISK-TAXONOMY",
                            "lens": "product",
                            "statement": "The board can provisionally use the current queue risk taxonomy.",
                            "owner": "Product Lead",
                            "risk": "med",
                            "justification": "The team currently uses the current queue risk taxonomy during manual triage.",
                            "closes_gap": self.gap_id,
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        apply_assumptions("METAB", source)

    def _answer(self, path_name: str = "answer.md") -> Path:
        path = self.temp / path_name
        path.write_text(
            f"### {self.gap_id}\n\n"
            "- Answer: Product confirms the current queue risk taxonomy is accepted for the first development slice.\n"
            "- Owner / source: Product Lead\n"
            "- Evidence or reference: Discovery workshop\n"
            "- Decision status: confirmed\n",
            encoding="utf-8",
        )
        return path

    def _ledger_unit_for_assumption(self) -> dict[str, object]:
        ledger = json.loads((self.ws / "01_discovery" / "knowledge_state.json").read_text(encoding="utf-8"))
        for unit in ledger["units"]:
            links = unit.get("links", [])
            if any(link.get("type") == "assumption" and link.get("target") == "ASM-RISK-TAXONOMY" for link in links):
                return unit
        self.fail("Assumption knowledge unit not found.")

    def test_resolve_gaps_validates_assumption_and_recomputes_readiness(self) -> None:
        self._assume()
        result = resolve_gaps("METAB", self._answer())

        self.assertIn("ASM-RISK-TAXONOMY", result["knowledge_metabolism"]["validated_assumptions"])
        self.assertTrue(result["knowledge_metabolism"]["impacted_knowledge_units"])
        self.assertTrue((self.ws / "01_discovery" / "development_readiness.json").exists())
        self.assertIn("VALIDATED", (self.ws / "01_discovery" / "assumptions.md").read_text(encoding="utf-8"))
        self.assertEqual(self._ledger_unit_for_assumption()["status"], "CONFIRMED")

    def test_sync_structured_response_confirms_gap_and_updates_ledger(self) -> None:
        self._assume()
        result = sync_change("METAB", self._answer("sync-answer.md"), "client sent structured answer")

        self.assertIn(self.gap_id, result["sync_closed_gaps"])
        self.assertIn("ASM-RISK-TAXONOMY", result["knowledge_metabolism"]["validated_assumptions"])
        gaps_text = (self.ws / "01_discovery" / "gaps.md").read_text(encoding="utf-8")
        self.assertIn(f"| {self.gap_id} |", gaps_text)
        self.assertIn("| CLOSED |", gaps_text)
        impact_reports = list((self.ws / "07_changes").rglob("*impact_report.md"))
        self.assertTrue(impact_reports)
        self.assertIn("Knowledge Ledger Metabolism", impact_reports[0].read_text(encoding="utf-8"))

    def test_sync_invalidates_assumption_and_flags_downstream_staleness(self) -> None:
        self._assume()
        self.assertEqual(main(["brief", "METAB"]), 0)
        change = self.temp / "invalidates-assumption.md"
        change.write_text(
            "ASM-RISK-TAXONOMY is invalidated: the current queue risk taxonomy cannot use the legacy manual labels.",
            encoding="utf-8",
        )
        result = sync_change("METAB", change, "taxonomy replacement")

        metabolism = result["knowledge_metabolism"]
        self.assertIn("ASM-RISK-TAXONOMY", metabolism["invalidated_assumptions"])
        self.assertTrue(metabolism["downstream_stale_artifacts"])
        self.assertIn("project-brief.md", "\n".join(metabolism["downstream_stale_artifacts"]))
        self.assertIn("INVALIDATED", (self.ws / "01_discovery" / "assumptions.md").read_text(encoding="utf-8"))
        self.assertEqual(self._ledger_unit_for_assumption()["status"], "OPEN")

        health = run_health("METAB")
        self.assertEqual(health["verdict"], "DIRTY")
        self.assertTrue(any("Knowledge changed after downstream artifacts" in item for item in health["findings"]))


if __name__ == "__main__":
    unittest.main()
