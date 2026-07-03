import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from sentinel.cli import main
from sentinel.core.state import read_state
from sentinel.maturity import generate_project_brief, spec_self_correction_findings


class SpecSelfCorrectionFindingsTests(unittest.TestCase):
    def test_carried_criterion_produces_no_findings(self):
        answers = {"GAP-OBJECTIVE": {"statement": "Reduce churn by giving leads a queue-risk view.", "source": "client"}}
        brief = "## 1. Business\n- Reduce churn by giving leads a queue-risk view. _(`GAP-OBJECTIVE` / `client`)_\n"
        self.assertEqual(spec_self_correction_findings(brief, answers), [])

    def test_dropped_statement_is_detected_and_cited(self):
        answers = {"GAP-OBJECTIVE": {"statement": "Reduce churn by giving leads a queue-risk view.", "source": "client"}}
        brief = "## 1. Business\n- A different summary that lost the confirmed criterion. _(`GAP-OBJECTIVE`)_\n"
        findings = spec_self_correction_findings(brief, answers)
        self.assertEqual(len(findings), 1)
        self.assertIn("GAP-OBJECTIVE", findings[0])
        self.assertIn("Reduce churn", findings[0])

    def test_missing_gap_id_is_detected(self):
        answers = {"GAP-SCOPE": {"statement": "Only the support module is in scope.", "source": "client"}}
        brief = "## 2. Scope\n- Only the support module is in scope.\n"
        findings = spec_self_correction_findings(brief, answers)
        self.assertEqual(len(findings), 1)
        self.assertIn("GAP-SCOPE", findings[0])

    def test_answers_without_a_brief_section_route_are_out_of_scope(self):
        answers = {"GAP-UNROUTED-CUSTOM": {"statement": "Handled by a downstream artifact.", "source": "domain"}}
        self.assertEqual(spec_self_correction_findings("empty brief", answers), [])


class SpecSelfCorrectionPhaseCloseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.old_cwd = Path.cwd()
        self.temp = Path(tempfile.mkdtemp())
        os.chdir(self.temp)
        source = self.temp / "request.md"
        source.write_text(
            "Need a read-only dashboard for support leads. Acceptance: leads see queue risk before standup.",
            encoding="utf-8",
        )
        self.assertEqual(main(["init", "SSC"]), 0)
        self.assertEqual(main(["ingest", "SSC", "--source", str(source)]), 0)

    def tearDown(self) -> None:
        os.chdir(self.old_cwd)
        shutil.rmtree(self.temp)

    def write_confirmed_answer(self) -> None:
        seeds = self.temp / "workspaces" / "SSC" / "01_discovery" / "identity_seeds.md"
        seeds.write_text(
            "# Seeds\n\n"
            "| Seed | Gap | Status | Statement | Source |\n"
            "| --- | --- | --- | --- | --- |\n"
            "| SEED-001 | GAP-OBJECTIVE | CONFIRMED | Reduce churn by giving leads a queue-risk view. | client |\n",
            encoding="utf-8",
        )

    def test_normal_close_is_unchanged_and_reports_criteria_checked(self):
        self.write_confirmed_answer()
        result = generate_project_brief("SSC")
        self.assertFalse(result["blocked"])
        self.assertEqual(result["self_correction"]["findings"], [])
        self.assertEqual(result["self_correction"]["criteria_checked"], 1)

    def clear_blocking_gaps(self) -> None:
        # SSC only guards the actual phase close (the advance to READY_FOR_SPECS),
        # so the discrepancy scenario needs a workspace without blocking gaps.
        gaps = self.temp / "workspaces" / "SSC" / "01_discovery" / "gaps.md"
        gaps.write_text("# Gaps\n\n| ID | Title | Lens | Severity | Status |\n| --- | --- | --- | --- | --- |\n", encoding="utf-8")

    def test_discrepant_brief_aborts_the_phase_close(self):
        self.write_confirmed_answer()
        self.clear_blocking_gaps()
        # Simulate a compiler regression that silently drops the confirmed
        # criterion: the rendered brief no longer carries the answer.
        with mock.patch(
            "sentinel.maturity.render_project_brief",
            return_value="# Project Brief\n\n## 1. Business\n- Unrelated narrative without the criterion.\n",
        ):
            result = generate_project_brief("SSC")
        self.assertTrue(result["blocked"])
        self.assertEqual(len(result["self_correction"]["findings"]), 1)
        self.assertIn("GAP-OBJECTIVE", result["self_correction"]["findings"][0])
        state = read_state("SSC")
        self.assertEqual(state.get("readiness_stage"), "SELF_CORRECTION_FAILED")
        self.assertEqual(state.get("phase"), "brief_self_correction_failed")

    def test_findings_do_not_hijack_an_already_blocked_phase(self):
        self.write_confirmed_answer()
        # Blocking gaps keep the phase open: findings are reported but the
        # normal blocked stage is preserved (the close is not happening).
        with mock.patch(
            "sentinel.maturity.render_project_brief",
            return_value="# Project Brief\n\n## 1. Business\n- Unrelated narrative without the criterion.\n",
        ):
            result = generate_project_brief("SSC")
        self.assertEqual(len(result["self_correction"]["findings"]), 1)
        state = read_state("SSC")
        self.assertNotEqual(state.get("readiness_stage"), "SELF_CORRECTION_FAILED")


if __name__ == "__main__":
    unittest.main()
