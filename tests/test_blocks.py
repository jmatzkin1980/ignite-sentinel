from __future__ import annotations

import unittest
from pathlib import Path

from sentinel.blocks import BLOCK_CATALOG, blocks_to_markdown, markdown_to_blocks


ROOT = Path(__file__).parent


class ArtifactBlocksTest(unittest.TestCase):
    def test_markdown_fixtures_round_trip_through_blocks(self) -> None:
        fixtures = [
            ROOT / "fixtures" / "complete_requirement.md",
            ROOT / "fixtures" / "incomplete_requirement.md",
            ROOT / "fixtures" / "evals" / "crm-billing-sync" / "requirement.md",
            ROOT / "fixtures" / "evals" / "support-dashboard" / "requirement.md",
        ]
        for fixture in fixtures:
            with self.subTest(fixture=fixture.name):
                source = fixture.read_text(encoding="utf-8")
                model = markdown_to_blocks(source, artifact="fixture")
                self.assertEqual(blocks_to_markdown(model), source)
                self.assertTrue(model["roundtrip"]["idempotent"])
                self.assertEqual(model["catalog"], list(BLOCK_CATALOG))
                self.assertTrue(model["blocks"])

    def test_block_catalog_classifies_governed_artifact_signals(self) -> None:
        source = (
            "# PRD\n\n"
            "| ID | Requirement |\n"
            "| --- | --- |\n"
            "| REQ-EARS-001 | When data exists, the system shall show it. |\n\n"
            "Persona: Operations analyst.\n\n"
            "When data changes, then Sentinel shall refresh the view.\n\n"
            "Decision: `DEC-001` keeps billing out of scope.\n\n"
            "Trace: `REQ-001` feeds `SPEC-U-001`.\n\n"
            "[PENDING INPUT] Clarify rollout owner.\n\n"
            "ASSUMED via `ASM-TECH-001` until Technology confirms the service.\n"
        )
        model = markdown_to_blocks(source, artifact="prd")
        child_types = {child["type"] for block in model["blocks"] for child in block["children"]}

        self.assertIn("requirement-table", child_types)
        self.assertIn("persona", child_types)
        self.assertIn("ears-statement", child_types)
        self.assertIn("decision", child_types)
        self.assertIn("traceability", child_types)
        self.assertIn("pending", child_types)
        self.assertIn("assumption", child_types)
        self.assertEqual(model["blocks"][0]["children"][0]["line_start"], 1)
        self.assertEqual(blocks_to_markdown(model), source)


if __name__ == "__main__":
    unittest.main()
