"""IMP-185: governed Non-Goals projection in the brief and PRD.

A gap closed out-of-scope/not-applicable (or a scope decision) is projected as a
cited Non-Goal. No such governed data -> an explicit marker, never an invented
non-goal. Anchors are bilingual so `/validate` recognizes the section in ES/EN.
"""
from __future__ import annotations

import unittest

from sentinel.compilers.prd import render_prd_full
from sentinel.gap_resolution import materialize_resolution_decisions  # noqa: F401 (kind logic covered below)
from sentinel.gaps import (
    NON_GOAL_KIND,
    NON_GOAL_MARKER,
    parse_non_goals,
    render_non_goals_block,
)
from sentinel.gap_resolution import NOT_APPLICABLE_STATUSES, normalize_status
from sentinel.maturity import render_project_brief


DECISIONS_WITH_NON_GOAL = (
    "# Decision Log\n\n"
    "## Gap Resolution Decisions\n\n"
    "| Decision ID | Gap ID | Status | Decision | Source | Kind |\n"
    "| --- | --- | --- | --- | --- | --- |\n"
    "| AUTO-DEC-CHG-003-001 | `GAP-PRODUCT-ASIS-TOBE` | CONFIRMED | A native mobile app is out of scope this release. | `CHG-003` | non-goal |\n"
    "| AUTO-DEC-CHG-003-002 | `GAP-OBJECTIVE` | CONFIRMED | Cut missed SLAs by 20%. | `CHG-003` | decision |\n"
)


class NonGoalsProjectionTests(unittest.TestCase):
    def test_parse_non_goals_reads_only_non_goal_rows(self):
        non_goals = parse_non_goals(DECISIONS_WITH_NON_GOAL)
        self.assertEqual(len(non_goals), 1)
        self.assertEqual(non_goals[0]["gap_id"], "GAP-PRODUCT-ASIS-TOBE")
        self.assertEqual(non_goals[0]["source"], "CHG-003")
        self.assertIn("out of scope", non_goals[0]["statement"])

    def test_parse_non_goals_ignores_regular_decisions_and_legacy_tables(self):
        legacy = (
            "## Gap Resolution Decisions\n\n"
            "| Decision ID | Gap ID | Status | Decision | Source |\n"
            "| --- | --- | --- | --- | --- |\n"
            "| AUTO-DEC-CHG-001-001 | `GAP-OBJECTIVE` | CONFIRMED | Ship the dashboard. | `CHG-001` |\n"
        )
        # A pre-IMP-185 table (no Kind column) yields no non-goals, not a crash.
        self.assertEqual(parse_non_goals(legacy), [])

    def test_render_block_cites_each_non_goal(self):
        block = render_non_goals_block(
            [{"gap_id": "GAP-X", "statement": "No native app.", "source": "CHG-003"}], "en"
        )
        self.assertIn("No native app.", block)
        self.assertIn("`GAP-X`", block)
        self.assertIn("`CHG-003`", block)

    def test_render_block_empty_marker_is_bilingual(self):
        self.assertEqual(render_non_goals_block([], "en"), NON_GOAL_MARKER["en"])
        self.assertEqual(render_non_goals_block([], "es"), NON_GOAL_MARKER["es"])
        self.assertIn("never invented", render_non_goals_block([], "en"))
        self.assertIn("no se inventa", render_non_goals_block([], "es"))

    def test_not_applicable_family_is_the_non_goal_signal(self):
        for status in ("no aplica", "not applicable", "N/A", "na"):
            self.assertIn(normalize_status(status), NOT_APPLICABLE_STATUSES)
        # Confirmed (positive) answers must NOT be tagged as non-goals.
        self.assertNotIn(normalize_status("confirmed"), NOT_APPLICABLE_STATUSES)
        self.assertNotIn(normalize_status("confirmado"), NOT_APPLICABLE_STATUSES)


class NonGoalsInArtifactsTests(unittest.TestCase):
    def test_brief_projects_cited_non_goal(self):
        brief = render_project_brief(
            "DEMO", "req", "", "", DECISIONS_WITH_NON_GOAL, "", raw_text="", language="en"
        )
        self.assertIn("No-Objetivos (Non-Goals)", brief)
        self.assertIn("A native mobile app is out of scope", brief)
        self.assertIn("`GAP-PRODUCT-ASIS-TOBE`", brief)

    def test_brief_marker_when_no_non_goals(self):
        brief = render_project_brief("DEMO", "req", "", "", "# Decision Log\n", "", raw_text="", language="es")
        self.assertIn("No-Objetivos (Non-Goals)", brief)
        self.assertIn("Sin non-goals registrados", brief)

    def test_prd_projects_cited_non_goal_en(self):
        ctx = {"non_goals": [{"gap_id": "GAP-PRODUCT-ASIS-TOBE", "statement": "No native app.", "source": "CHG-003"}]}
        prd = render_prd_full("DEMO", "req", ctx, "project-brief.md", "en")
        self.assertIn("### Non-Goals", prd)
        self.assertIn("No native app.", prd)
        self.assertIn("`GAP-PRODUCT-ASIS-TOBE`", prd)

    def test_prd_marker_and_anchor_present_when_empty_es(self):
        prd = render_prd_full("DEMO", "req", {"non_goals": []}, "project-brief.md", "es")
        # Bilingual /validate anchor: ES title contains both tokens.
        self.assertIn("No-Objetivos", prd)
        self.assertIn("Non-Goals", prd)
        self.assertIn("Sin non-goals registrados", prd)


if __name__ == "__main__":
    unittest.main()
