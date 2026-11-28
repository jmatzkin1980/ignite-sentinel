"""IMP-198: optional JTBD-native ("job story") phrasing for the backlog.

`--story-format job` (or the `story_format` config field) rewords the story
statement to the JTBD shape without a persona; the default `user` output stays
byte-identical to the historical rendering. Only the wording changes — acceptance
criteria, slicing, and SPEC-U -> EPIC -> US -> AC traceability are unaffected, and
a missing outcome surfaces as [PENDING INPUT] rather than being invented.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

from sentinel.cli import main
from sentinel.compilers.backlog import render_story_narrative
from sentinel.core.paths import config_path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import SnapshotWorkspaceCase, run_ok  # noqa: E402


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

    def test_user_format_is_built_from_its_parts(self):
        # IMP-435 (A-08): actor, capability, benefit; no fixed persona, no lowercased names.
        story = {"goal": "Do The Thing", "benefit": "The Outcome Happens"}
        self.assertEqual(
            render_story_narrative(story, "user"),
            "As a user,\nI want to do The Thing,\nso that the Outcome Happens",
        )
        self.assertEqual(
            render_story_narrative(story, "user", inline=True),
            "As a user, I want to do The Thing, so that the Outcome Happens",
        )
        story = {"goal": "enviar el alta", "trigger": "el analista la carga", "actor": "los analistas", "benefit": "agilizar",
                 "benefit_is_goal": True, "language": "es"}
        self.assertEqual(render_story_narrative(story, "user"),
                         "Como los analistas,\nquiero enviar el alta cuando el analista la carga,\npara agilizar")

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


class BacklogStoryFormatTests(SnapshotWorkspaceCase):
    """IMP-305: the matured workspace (up to specs) is built once; each test gets a copy."""

    PID = "STORYFMT"

    @classmethod
    def build_workspace(cls) -> None:
        root = Path.cwd()
        (root / "raw.md").write_text(RAW, encoding="utf-8")
        run_ok(["init", cls.PID, "--brief-version", "1"])
        run_ok(["ingest", cls.PID, "--source", str(root / "raw.md")])
        for index, statement in enumerate(EARS_STATEMENTS, start=1):
            answer = root / f"answers-{index}.md"
            answer.write_text(
                "### GAP-ACCEPTANCE\n"
                f"- Answer: {statement}\n"
                "- Owner / source: Client workshop\n"
                f"- Evidence or reference: Synthetic EARS response {index}\n"
                "- Decision status: confirmed\n",
                encoding="utf-8",
            )
            run_ok(["resolve-gaps", cls.PID, "--source", str(answer)])
        run_ok(["brief", cls.PID])
        run_ok(["specs", cls.PID])

    def _mature(self, pid: str) -> Path:
        self.assertEqual(pid, self.PID)
        return self.temp / "workspaces" / pid

    def _epic(self, workspace: Path) -> str:
        return (workspace / "04_backlog" / "EPIC-001.md").read_text(encoding="utf-8")

    def _story(self, workspace: Path) -> str:
        return (workspace / "04_backlog" / "US-001.md").read_text(encoding="utf-8")

    def test_default_is_user_story_and_flag_switches_to_job(self):
        pid = self.PID
        workspace = self._mature(pid)

        # Default (no flag): persona-neutral user story, unchanged shape.
        self.assertEqual(main(["backlog", pid]), 0)
        epic_user = self._epic(workspace)
        story_user = self._story(workspace)
        self.assertIn("As a user,", epic_user)
        self.assertNotIn("When the target user faces the operational situation", epic_user)
        self.assertIn("## User Story", story_user)
        self.assertIn("As a user, I want to", story_user)
        story_count_user = epic_user.count("**Narrative:**")
        self.assertEqual(story_count_user, len(EARS_STATEMENTS))

        # Job format: JTBD phrasing, no invented persona, same story set + traces.
        self.assertEqual(main(["backlog", pid, "--story-format", "job"]), 0)
        epic_job = self._epic(workspace)
        story_job = self._story(workspace)
        self.assertIn("When the target user faces the operational situation", epic_job)
        self.assertNotIn("As a user,", epic_job)
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
        pid = self.PID
        workspace = self._mature(pid)
        cfg = config_path(pid)
        cfg.write_text(cfg.read_text(encoding="utf-8") + "\nstory_format: job\n", encoding="utf-8")
        self.assertEqual(main(["backlog", pid]), 0)
        self.assertIn("When the target user faces the operational situation", self._epic(workspace))

    def test_flag_overrides_config(self):
        pid = self.PID
        workspace = self._mature(pid)
        cfg = config_path(pid)
        cfg.write_text(cfg.read_text(encoding="utf-8") + "\nstory_format: user\n", encoding="utf-8")
        # Config says user, flag says job -> flag wins.
        self.assertEqual(main(["backlog", pid, "--story-format", "job"]), 0)
        self.assertIn("When the target user faces the operational situation", self._epic(workspace))


if __name__ == "__main__":
    unittest.main()
