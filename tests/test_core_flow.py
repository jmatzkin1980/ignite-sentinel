from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from pathlib import Path

from sentinel.cli import main
from sentinel.memory import ContextBroker


ROOT = Path(__file__).parent


class SentinelCoreFlowTest(unittest.TestCase):
    def setUp(self) -> None:
        self.old_cwd = Path.cwd()
        self.temp = Path(tempfile.mkdtemp())
        os.chdir(self.temp)

    def tearDown(self) -> None:
        os.chdir(self.old_cwd)
        shutil.rmtree(self.temp)

    def test_incomplete_requirement_blocks_maturity(self) -> None:
        fixture = ROOT / "fixtures" / "incomplete_requirement.md"
        self.assertEqual(main(["init", "ACME"]), 0)
        self.assertEqual(main(["ingest", "ACME", "--source", str(fixture)]), 0)
        self.assertEqual(main(["maturity", "ACME"]), 0)
        report = (self.temp / "workspaces" / "ACME" / "01_discovery" / "requirement_maturity_report.md").read_text(encoding="utf-8")
        self.assertIn("`BLOCKED`", report)
        self.assertNotEqual(main(["specs", "ACME"]), 0)

    def test_complete_requirement_generates_traceable_backlog(self) -> None:
        fixture = ROOT / "fixtures" / "complete_requirement.md"
        self.assertEqual(main(["init", "NOVA"]), 0)
        self.assertEqual(main(["ingest", "NOVA", "--source", str(fixture)]), 0)
        self.assertEqual(main(["maturity", "NOVA"]), 0)
        self.assertEqual(main(["specs", "NOVA"]), 0)
        self.assertEqual(main(["backlog", "NOVA"]), 0)
        self.assertEqual(main(["quality", "NOVA"]), 0)
        self.assertEqual(main(["health", "NOVA"]), 0)
        self.assertEqual(main(["validate", "NOVA"]), 0)
        self.assertEqual(main(["trace", "NOVA"]), 0)
        graph = (self.temp / "workspaces" / "NOVA" / "06_traceability" / "traceability_graph.json").read_text(encoding="utf-8")
        self.assertIn('"type": "user_story"', graph)
        self.assertIn('"type": "acceptance_criteria"', graph)
        self.assertIn('"type": "test_case"', graph)
        story = (self.temp / "workspaces" / "NOVA" / "04_backlog" / "US-001.md").read_text(encoding="utf-8")
        self.assertIn("Acceptance Criteria", story)
        mermaid = self.temp / "workspaces" / "NOVA" / "06_traceability" / "traceability_graph.md"
        self.assertTrue(mermaid.exists())

    def test_retrieval_is_project_scoped(self) -> None:
        complete = ROOT / "fixtures" / "complete_requirement.md"
        incomplete = ROOT / "fixtures" / "incomplete_requirement.md"
        self.assertEqual(main(["init", "NOVA"]), 0)
        self.assertEqual(main(["init", "ACME"]), 0)
        self.assertEqual(main(["ingest", "NOVA", "--source", str(complete)]), 0)
        self.assertEqual(main(["ingest", "ACME", "--source", str(incomplete)]), 0)
        results = ContextBroker("NOVA").retrieve("support leads SLA", "maturity")
        self.assertTrue(results)
        self.assertTrue(all(row["project_id"] == "NOVA" for row in results))

    def test_context_folders_are_indexed_for_hybrid_retrieval(self) -> None:
        complete = ROOT / "fixtures" / "complete_requirement.md"
        self.assertEqual(main(["init", "NOVA"]), 0)
        tech_context = self.temp / "workspaces" / "NOVA" / "00_raw" / "02_technology_context" / "integration.md"
        tech_context.write_text(
            "The support queue integration uses webhook retries and the Atlas CRM account identifier.",
            encoding="utf-8",
        )
        design_context = self.temp / "workspaces" / "NOVA" / "00_raw" / "03_design_context" / "states.md"
        design_context.write_text(
            "Queue screens must show loading, empty, and recoverable error states for SLA triage.",
            encoding="utf-8",
        )
        self.assertEqual(main(["ingest", "NOVA", "--source", str(complete)]), 0)
        tech_results = ContextBroker("NOVA").retrieve("Atlas CRM webhook retries", "discovery", domain="technical")
        design_results = ContextBroker("NOVA").retrieve("recoverable error state SLA triage", "discovery", domain="design")
        self.assertTrue(tech_results)
        self.assertTrue(design_results)
        self.assertEqual(tech_results[0]["artifact_type"], "technology_context")
        self.assertEqual(design_results[0]["artifact_type"], "design_context")

    def test_sync_creates_change_impact_and_context_pack(self) -> None:
        complete = ROOT / "fixtures" / "complete_requirement.md"
        change = ROOT / "fixtures" / "change_request.md"
        self.assertEqual(main(["init", "NOVA"]), 0)
        self.assertEqual(main(["ingest", "NOVA", "--source", str(complete)]), 0)
        self.assertEqual(main(["specs", "NOVA"]), 0)
        self.assertEqual(main(["backlog", "NOVA"]), 0)
        self.assertEqual(main(["sync", "NOVA", "--source", str(change), "--note", "client follow-up"]), 0)
        graph = (self.temp / "workspaces" / "NOVA" / "06_traceability" / "traceability_graph.json").read_text(encoding="utf-8")
        self.assertIn('"type": "change"', graph)
        self.assertIn('"relation": "may_impact"', graph)
        self.assertEqual(
            main(
                [
                    "retrieve",
                    "NOVA",
                    "--query",
                    "SLA breach risk queue",
                    "--workflow",
                    "sync",
                    "--write-pack",
                    "--artifact-type",
                    "change",
                ]
            ),
            0,
        )
        pack = self.temp / "workspaces" / "NOVA" / "08_context_packs" / "sync.json"
        self.assertTrue(pack.exists())

    def test_doctor_passes_for_repo_root(self) -> None:
        self.assertEqual(main(["doctor", "--root", str(ROOT.parent)]), 0)
        self.assertEqual(main(["/doctor", "--root", str(ROOT.parent)]), 0)

    def test_slash_command_aliases_work(self) -> None:
        self.assertEqual(main(["/init", "SLASH_DEMO"]), 0)
        workspace = self.temp / "workspaces" / "SLASH_DEMO"
        self.assertTrue((workspace / "state.json").exists())
        self.assertTrue((workspace / "00_raw" / "02_technology_context").is_dir())
        self.assertTrue((workspace / "00_raw" / "03_design_context").is_dir())
        self.assertTrue((workspace / "07_changes" / "03_domain_updates").is_dir())


if __name__ == "__main__":
    unittest.main()
