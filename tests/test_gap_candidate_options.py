import tempfile
import unittest
from pathlib import Path

from sentinel.context_requests import domain_gap_candidate_options_section
from sentinel.discovery import candidate_options_for_gap, render_gaps


class GapCandidateOptionsTest(unittest.TestCase):
    def test_candidate_options_require_local_evidence(self) -> None:
        gap = {
            "id": "GAP-METRIC-SOURCE",
            "lens": "quality",
            "severity": "high",
            "status": "OPEN",
            "description": "Metric source missing.",
            "question": "How is the metric measured?",
            "evidence_mention": "20%",
        }

        options = candidate_options_for_gap(gap)
        self.assertEqual([option["label"] for option in options], ["A", "B"])
        self.assertTrue(all(option["citation"] == "20%" for option in options))

        self.assertEqual(candidate_options_for_gap({**gap, "evidence_mention": ""}), [])
        self.assertEqual(candidate_options_for_gap({**gap, "status": "CLOSED"}), [])

    def test_gaps_render_cited_options_without_auto_closing(self) -> None:
        gap = {
            "id": "GAP-FRONTEND-SURFACE",
            "lens": "technical",
            "severity": "high",
            "status": "OPEN",
            "description": "Frontend surface detail missing.",
            "question": "Which UI details apply?",
            "evidence_mention": "dashboard",
        }

        rendered = render_gaps("ACME", [gap], "REQ-001")

        self.assertIn("Cited candidate options (not selected):", rendered)
        self.assertIn("Local citation: `dashboard`", rendered)
        self.assertIn("| GAP-FRONTEND-SURFACE | technical | high | OPEN |", rendered)
        self.assertNotIn("| GAP-FRONTEND-SURFACE | technical | high | CLOSED |", rendered)

    def test_context_request_reuses_gap_candidate_options_by_domain_lens(self) -> None:
        gap = {
            "id": "GAP-FRONTEND-SURFACE",
            "lens": "technical",
            "severity": "high",
            "status": "OPEN",
            "description": "Frontend surface detail missing.",
            "question": "Which UI details apply?",
            "evidence_mention": "dashboard",
        }
        with tempfile.TemporaryDirectory() as tmp:
            gaps_path = Path(tmp) / "gaps.md"
            gaps_path.write_text(render_gaps("ACME", [gap], "REQ-001"), encoding="utf-8")

            section = domain_gap_candidate_options_section("frontend", "en", gaps_path)

        self.assertIn("Cited Candidate Options For Open Gaps", section)
        self.assertIn("GAP-FRONTEND-SURFACE", section)
        self.assertIn("Local citation: `dashboard`", section)


if __name__ == "__main__":
    unittest.main()
