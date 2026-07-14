"""IMP-198: optional JTBD-native ("job story") phrasing for the backlog.

`--story-format job` (or the `story_format` config field) rewords the story
statement to the JTBD shape without a persona; the default `user` output stays
byte-identical to the historical rendering. Only the wording changes — acceptance
criteria, slicing, and SPEC-U -> EPIC -> US -> AC traceability are unaffected, and
a missing outcome surfaces as [PENDING INPUT] rather than being invented.
"""
from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from pathlib import Path

from sentinel.cli import main
from sentinel.compilers.backlog import render_story_narrative
from sentinel.core.paths import config_path


RAW = """# Operations Risk Dashboard

Objective: let operations leads review risk queues before the daily meeting.

Users: operations leads.

In scope: read-only risk dashboard for open queues. Out of scope: editing cases.

Metric: reduce manual preparation by 30 percent in the first release month.
"""

EARS_STATEMENTS = [
    "When queue metrics are available, the system shall display open risk queues.",
    "When a case breaches SLA, the system shall flag the queue as high risk.",
    "When a queue has no open cases, the system shall hide risk indicators.",
    "While risk data is stale, the system shall show a stale data warning.",
    "If the metrics service is unavailable, then the system shall show risk status unknown.",
    "Where audit logging is enabled, the system shall record dashboard access.",
]


class StoryNarrativeUnitTests(unittest.TestCase):
    """Direct rendering guards that do not need a full workspace."""

    def test_user_format_is_byte_identical_to_history(self):
        story = {"goal": "Do The Thing", "benefit": "The Outcome Happens"}
        self.assertEqual(
            render_story_narrative(story, "user"),
            "As a target user,\nI want do the thing,\nSo that the outcome happens",
        )
        self.assertEqual(
            render_story_narrative(story, "user", inline=True),
            "As a target user, I want do the thing so that the outcome happens",
        )

    def test_job_format_leads_with_situation_not_a_persona(self):
        story = {"goal": "Review the queues", "benefit": "prepare before the meeting"}
        block = render_story_narrative(story, "job")
        self.assertTrue(block.startswith("When the target user faces the operational situation"))
        self.assertIn("I want review the queues", block)
        self.assertIn("So I can prepare before the meeting", block)
        self.assertNotIn("As a", block)

    def test_job_outcome_missing_stays_pending_input(self):
        story = {"goal": "Review the queues", "benefit": "   "}
        block = render_story_narrative(story, "job", inline=True)
        self.assertIn("so I can [PENDING INPUT]", block)
        self.assertNotIn("so I can  so", block)

    def test_unknown_format_is_not_accepted_by_renderer(self):
        # render_story_narrative only branches on "job"; anything else renders user.
        story = {"goal": "Do x", "benefit": "Get y"}
        self.assertEqual(render_story_narrative(story, "nonsense"), render_story_narrative(story, "user"))


class BacklogStoryFormatTests(unittest.TestCase):
    def setUp(self):
        self.old_cwd = Path.cwd()
        self.temp = Path(tempfile.mkdtemp())
        os.chdir(self.temp)
        self.raw = self.temp / "raw.md"
        self.raw.write_text(RAW, encoding="utf-8")

    def tearDown(self):
        os.chdir(self.old_cwd)
        shutil.rmtree(self.temp, ignore_errors=True)

    def _resolve_acceptance_with(self, pid: str, statement: str, index: int) -> None:
        answer = self.temp / f"answers-{index}.md"
        answer.write_text(
            "### GAP-ACCEPTANCE\n"
            f"- Answer: {statement}\n"
            "- Owner / source: Client workshop\n"
            f"- Evidence or reference: Synthetic EARS response {index}\n"
            "- Decision status: confirmed\n",
            encoding="utf-8",
        )
        self.assertEqual(main(["resolve-gaps", pid, "--source", str(answer)]), 0)

    def _mature(self, pid: str) -> Path:
        self.assertEqual(main(["init", pid]), 0)
        self.assertEqual(main(["ingest", pid, "--source", str(self.raw)]), 0)
        for index, statement in enumerate(EARS_STATEMENTS, start=1):
            self._resolve_acceptance_with(pid, statement, index)
        self.assertEqual(main(["brief", pid]), 0)
        self.assertEqual(main(["specs", pid]), 0)
        return self.temp / "workspaces" / pid

    def _epic(self, workspace: Path) -> str:
        return (workspace / "04_backlog" / "EPIC-001.md").read_text(encoding="utf-8")

    def _story(self, workspace: Path) -> str:
        return (workspace / "04_backlog" / "US-001.md").read_text(encoding="utf-8")

    def test_default_is_user_story_and_flag_switches_to_job(self):
        pid = "STORYFMT"
        workspace = self._mature(pid)

        # Default (no flag): persona-neutral user story, unchanged shape.
        self.assertEqual(main(["backlog", pid]), 0)
        epic_user = self._epic(workspace)
        story_user = self._story(workspace)
        self.assertIn("As a target user,", epic_user)
        self.assertNotIn("When the target user faces the operational situation", epic_user)
        self.assertIn("## User Story", story_user)
        self.assertIn("As a target user, I want", story_user)
        story_count_user = epic_user.count("**Narrative:**")
        self.assertEqual(story_count_user, len(EARS_STATEMENTS))

        # Job format: JTBD phrasing, no invented persona, same story set + traces.
        self.assertEqual(main(["backlog", pid, "--story-format", "job"]), 0)
        epic_job = self._epic(workspace)
        story_job = self._story(workspace)
        self.assertIn("When the target user faces the operational situation", epic_job)
        self.assertNotIn("As a target user,", epic_job)
        self.assertIn("## Job Story", story_job)
        self.assertIn("When the target user faces the operational situation", story_job)
        # No persona named in the raw ("operations leads") leaks into the statement.
        job_statement = story_job.split("## Job Story", 1)[1].split("##", 1)[0]
        self.assertNotIn("operations leads", job_statement.lower())
        # Wording is the only delta: story count and SPEC-U traceability are stable.
        self.assertEqual(epic_job.count("**Narrative:**"), story_count_user)
        self.assertIn("SPEC-U-001", story_job)
        self.assertIn("SPEC-U-001, REQ-EARS-001, REQ-001, PRD-001, SPEC-001", story_job)

    def test_config_field_selects_job_without_flag(self):
        pid = "STORYFMTCFG"
        workspace = self._mature(pid)
        cfg = config_path(pid)
        cfg.write_text(cfg.read_text(encoding="utf-8") + "\nstory_format: job\n", encoding="utf-8")
        self.assertEqual(main(["backlog", pid]), 0)
        self.assertIn("When the target user faces the operational situation", self._epic(workspace))

    def test_flag_overrides_config(self):
        pid = "STORYFMTOVR"
        workspace = self._mature(pid)
        cfg = config_path(pid)
        cfg.write_text(cfg.read_text(encoding="utf-8") + "\nstory_format: user\n", encoding="utf-8")
        # Config says user, flag says job -> flag wins.
        self.assertEqual(main(["backlog", pid, "--story-format", "job"]), 0)
        self.assertIn("When the target user faces the operational situation", self._epic(workspace))


if __name__ == "__main__":
    unittest.main()
