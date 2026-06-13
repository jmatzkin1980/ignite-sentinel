"""Tests for IMP-048 dynamic backlog derivation from Spec Units."""
from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from sentinel.cli import main
from sentinel.traceability import load_graph


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


class DynamicBacklogDerivationTests(unittest.TestCase):
    def setUp(self):
        self.old_cwd = Path.cwd()
        self.temp = Path(tempfile.mkdtemp())
        os.chdir(self.temp)
        self.raw = self.temp / "raw.md"
        self.raw.write_text(RAW, encoding="utf-8")

    def tearDown(self):
        os.chdir(self.old_cwd)
        shutil.rmtree(self.temp, ignore_errors=True)

    def _resolve_acceptance_with(self, project_id: str, statement: str, index: int) -> None:
        answer = self.temp / f"answers-{index}.md"
        answer.write_text(
            "### GAP-ACCEPTANCE\n"
            f"- Answer: {statement}\n"
            "- Owner / source: Client workshop\n"
            f"- Evidence or reference: Synthetic EARS response {index}\n"
            "- Decision status: confirmed\n",
            encoding="utf-8",
        )
        self.assertEqual(main(["resolve-gaps", project_id, "--source", str(answer)]), 0)

    def test_backlog_derives_one_story_per_confirmed_spec_unit(self):
        project_id = "DYNBACKLOG"
        self.assertEqual(main(["init", project_id]), 0)
        self.assertEqual(main(["ingest", project_id, "--source", str(self.raw)]), 0)
        for index, statement in enumerate(EARS_STATEMENTS, start=1):
            self._resolve_acceptance_with(project_id, statement, index)
        self.assertEqual(main(["brief", project_id]), 0)
        self.assertEqual(main(["specs", project_id]), 0)
        self.assertEqual(main(["backlog", project_id]), 0)
        self.assertEqual(main(["backlog", project_id]), 0)

        workspace = self.temp / "workspaces" / project_id
        story_files = sorted((workspace / "04_backlog").glob("US-*.md"))
        self.assertEqual(len(story_files), len(EARS_STATEMENTS))
        self.assertEqual(story_files[-1].name, "US-006.md")
        self.assertFalse((workspace / "04_backlog" / "US-007.md").exists())

        epic = (workspace / "04_backlog" / "EPIC-001.md").read_text(encoding="utf-8")
        self.assertIn("`US-006`", epic)
        self.assertIn("`SPEC-U-006`", epic)
        self.assertNotIn("Habilitar el flujo principal de valor", epic)

        first_story = (workspace / "04_backlog" / "US-001.md").read_text(encoding="utf-8")
        self.assertIn("SPEC-U-001", first_story)
        self.assertIn("REQ-EARS-001", first_story)
        self.assertIn("When queue metrics are available", first_story)
        self.assertIn("AC-001-05 | evidence", first_story)
        self.assertIn("SPEC-U-001, REQ-EARS-001, REQ-001, PRD-001, SPEC-001", first_story)

        readiness = json.loads((workspace / "08_context_packs" / "implementation_readiness.json").read_text(encoding="utf-8"))
        value_stories = [story for story in readiness["stories"] if story["type"] == "value_story"]
        self.assertEqual(len(value_stories), len(EARS_STATEMENTS))
        self.assertEqual(value_stories[0]["source_unit"], "SPEC-U-001")
        self.assertIn("SPEC-U-006", value_stories[-1]["trace"])

        graph = load_graph(project_id)
        self.assertIn({"from": "SPEC-U-001", "to": "US-001", "relation": "decomposes_to"}, graph["edges"])
        self.assertIn({"from": "SPEC-U-006", "to": "US-006", "relation": "decomposes_to"}, graph["edges"])

    def test_backlog_execution_context_is_retrieved_per_story(self):
        project_id = "STORYCTX"
        self.assertEqual(main(["init", project_id]), 0)
        workspace = self.temp / "workspaces" / project_id
        tech_context = workspace / "00_raw" / "02_technology_context"
        tech_context.mkdir(parents=True, exist_ok=True)
        (tech_context / "stale-data.md").write_text(
            "# Stale Data Context\n\n"
            "Spec Unit: SPEC-U-004\n\n"
            "While risk data is stale, the critical surfaces are "
            "`src/risk/StaleDataBanner.tsx` and `RiskMetricsFreshnessService`.\n",
            encoding="utf-8",
        )
        (tech_context / "metrics-service-unavailable.md").write_text(
            "# Metrics Service Unavailable Context\n\n"
            "Spec Unit: SPEC-U-005\n\n"
            "If the metrics service is unavailable, the critical surfaces are "
            "`src/risk/MetricsGateway.ts` and `RiskStatusFallback`.\n",
            encoding="utf-8",
        )
        self.assertEqual(main(["ingest", project_id, "--source", str(self.raw)]), 0)
        for index, statement in enumerate(EARS_STATEMENTS, start=1):
            self._resolve_acceptance_with(project_id, statement, index)
        self.assertEqual(main(["brief", project_id]), 0)
        self.assertEqual(main(["specs", project_id]), 0)
        self.assertEqual(main(["backlog", project_id]), 0)

        backlog_context = json.loads(
            (workspace / "08_context_packs" / "backlog_generation.json").read_text(encoding="utf-8")
        )
        self.assertIn("US-004", backlog_context["per_story"])
        self.assertIn("US-005", backlog_context["per_story"])
        self.assertIn("domain_context_coverage", backlog_context)

        readiness = json.loads(
            (workspace / "08_context_packs" / "implementation_readiness.json").read_text(encoding="utf-8")
        )
        stories = {story["story_id"]: story for story in readiness["stories"] if story["type"] == "value_story"}
        stale_surface = stories["US-004"]["execution_contract"]["critical_surfaces"]["summary"]
        outage_surface = stories["US-005"]["execution_contract"]["critical_surfaces"]["summary"]
        self.assertIn("StaleDataBanner", stale_surface)
        self.assertIn("MetricsGateway", outage_surface)
        self.assertNotEqual(
            stories["US-004"]["execution_contract"]["critical_surfaces"],
            stories["US-005"]["execution_contract"]["critical_surfaces"],
        )
        self.assertEqual(stories["US-004"]["context_pack_section"], "per_story.US-004")
        self.assertEqual(stories["US-005"]["context_pack_section"], "per_story.US-005")

    def test_backlog_without_spec_units_keeps_pending_stub_instead_of_fixed_seeds(self):
        project_id = "PENDINGBACKLOG"
        self.assertEqual(main(["init", project_id]), 0)
        self.assertEqual(main(["ingest", project_id, "--source", str(self.raw)]), 0)
        answer = self.temp / "pending-answers.md"
        answer.write_text(
            "### GAP-ACCEPTANCE\n"
            "- Answer: Given an operations lead opens the dashboard, when risk data is available, then queues are visible for review.\n"
            "- Owner / source: Client workshop\n"
            "- Evidence or reference: Synthetic non-EARS response\n"
            "- Decision status: confirmed\n",
            encoding="utf-8",
        )
        self.assertEqual(main(["resolve-gaps", project_id, "--source", str(answer)]), 0)
        self.assertEqual(main(["brief", project_id]), 0)
        self.assertEqual(main(["specs", project_id]), 0)
        self.assertEqual(main(["backlog", project_id]), 0)

        workspace = self.temp / "workspaces" / project_id
        story_files = sorted((workspace / "04_backlog").glob("US-*.md"))
        self.assertEqual([path.name for path in story_files], ["US-001.md"])
        story = story_files[0].read_text(encoding="utf-8")
        self.assertIn("[PENDING INPUT] Confirm evidence-backed Spec Units", story)
        self.assertIn("GAP-PRD-FR-AC", story)
        self.assertNotIn("Habilitar el flujo principal de valor", story)


if __name__ == "__main__":
    unittest.main()
