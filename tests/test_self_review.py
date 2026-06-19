from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from sentinel.cli import main


ROOT = Path(__file__).parent


class SelfReviewTest(unittest.TestCase):
    def setUp(self) -> None:
        self.old_cwd = Path.cwd()
        self.temp = Path(tempfile.mkdtemp())
        os.chdir(self.temp)

    def tearDown(self) -> None:
        os.chdir(self.old_cwd)
        shutil.rmtree(self.temp)

    def test_self_review_registers_cited_gap_and_hard_to_reverse_decision(self) -> None:
        fixture = ROOT / "fixtures" / "complete_requirement.md"
        self.assertEqual(main(["init", "SREV"]), 0)
        self.assertEqual(main(["ingest", "SREV", "--source", str(fixture)]), 0)
        self.assertEqual(main(["maturity", "SREV"]), 0)
        self.assertEqual(main(["specs", "SREV"]), 0)

        prd = self.temp / "workspaces" / "SREV" / "03_specs" / "prd.md"
        quote = next(line.strip() for line in prd.read_text(encoding="utf-8").splitlines() if "billing" in line.lower())
        source = self.temp / "self-review.json"
        source.write_text(
            json.dumps(
                {
                    "gaps": [
                        {
                            "id": "GAP-SELF-REVIEW-ROLLBACK",
                            "lens": "product",
                            "severity": "medium",
                            "question": "What rollback or reuse impact follows from the excluded scope decision?",
                            "evidence": quote,
                        }
                    ],
                    "decisions": [
                        {
                            "id": "DEC-SELF-REVIEW-SCOPE-LOCK",
                            "title": "Excluded scope treated as stable",
                            "lens": "product",
                            "risk": "high",
                            "reversibility": "hard-to-reverse",
                            "decision": "Treat billing and workforce scheduling as excluded from release scope until BA confirms downstream impact.",
                            "evidence": quote,
                            "consequence": "Changing this later can invalidate PRD scope, specs, backlog slices, and acceptance criteria.",
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )

        self.assertEqual(main(["self-review", "SREV", "--source", str(source)]), 0)

        base = self.temp / "workspaces" / "SREV"
        gaps = (base / "01_discovery" / "gaps.md").read_text(encoding="utf-8")
        self.assertIn("GAP-SELF-REVIEW-ROLLBACK", gaps)
        self.assertIn("self-review", gaps)

        report = (base / "03_specs" / "self_review" / "self_review_report.md").read_text(encoding="utf-8")
        register = (base / "03_specs" / "self_review" / "decision_register.md").read_text(encoding="utf-8")
        graph = (base / "06_traceability" / "traceability_graph.json").read_text(encoding="utf-8")
        state = json.loads((base / "state.json").read_text(encoding="utf-8"))

        self.assertIn("GAP-SELF-REVIEW-ROLLBACK", report)
        self.assertIn("DEC-SELF-REVIEW-SCOPE-LOCK", register)
        self.assertIn("hard-to-reverse", register)
        self.assertIn('"type": "self_review"', graph)
        self.assertIn('"type": "hard_to_reverse_decision"', graph)
        self.assertEqual(state["last_command"], "self-review")
        self.assertEqual(state["gap_counts"]["self_review_origin"], 1)


if __name__ == "__main__":
    unittest.main()
