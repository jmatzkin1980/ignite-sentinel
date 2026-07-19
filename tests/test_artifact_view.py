from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from sentinel.blocks import blocks_to_markdown
from sentinel.cli import main
from sentinel.view import collect_artifact_model, markdown_to_html


ROOT = Path(__file__).parent


class ArtifactViewTest(unittest.TestCase):
    def setUp(self) -> None:
        self.old_cwd = Path.cwd()
        self.temp = Path(tempfile.mkdtemp())
        os.chdir(self.temp)

    def tearDown(self) -> None:
        os.chdir(self.old_cwd)
        shutil.rmtree(self.temp)

    def test_view_model_reconstructs_prd_sections_and_signals(self) -> None:
        fixture = ROOT / "fixtures" / "complete_requirement.md"
        self.assertEqual(main(["init", "VIEW"]), 0)
        self.assertEqual(main(["ingest", "VIEW", "--source", str(fixture)]), 0)
        self.assertEqual(main(["maturity", "VIEW"]), 0)
        self.assertEqual(main(["specs", "VIEW"]), 0)

        model = collect_artifact_model("VIEW", "prd")
        source = (self.temp / model["source_path"]).read_text(encoding="utf-8")
        reconstructed = "\n".join(section["markdown"] for section in model["sections"])

        self.assertEqual(reconstructed, source)
        self.assertEqual(blocks_to_markdown(model["blocks"]), source)
        self.assertTrue(model["blocks"]["roundtrip"]["idempotent"])
        self.assertTrue(all("block_id" in section for section in model["sections"]))
        self.assertEqual(model["artifact"], "prd")
        self.assertGreater(model["summary"]["sections"], 1)
        self.assertGreater(model["summary"]["citations"], 0)
        self.assertTrue(any(node["type"] == "prd" for node in model["trace"]["nodes"]))

    def test_citations_resolve_source_fragments_and_real_trace_neighborhoods(self) -> None:
        fixture = ROOT / "fixtures" / "complete_requirement.md"
        self.assertEqual(main(["init", "EVIDENCE"]), 0)
        self.assertEqual(main(["ingest", "EVIDENCE", "--source", str(fixture)]), 0)
        self.assertEqual(main(["maturity", "EVIDENCE"]), 0)
        self.assertEqual(main(["specs", "EVIDENCE"]), 0)
        self.assertEqual(main(["view", "EVIDENCE", "--artifact", "prd"]), 0)

        model = collect_artifact_model("EVIDENCE", "prd")
        with_fragment = [citation for citation in model["citations"] if citation["source_fragment"].get("available")]
        with_edges = [citation for citation in model["citations"] if citation["mini_graph"]["edges"]]

        self.assertTrue(with_fragment)
        self.assertEqual(with_fragment[0]["trace_node"]["id"], with_fragment[0]["trace_id"])
        self.assertTrue(with_fragment[0]["source_fragment"]["text"].strip())
        self.assertTrue(with_edges)
        self.assertGreater(model["summary"]["trace_edges"], 0)

        html = (
            self.temp
            / "workspaces"
            / "EVIDENCE"
            / "08_context_packs"
            / "views"
            / "prd.html"
        ).read_text(encoding="utf-8")
        self.assertIn("Source Fragment", html)
        self.assertIn("Mini Trace", html)

    def test_view_command_generates_self_contained_html_for_gaps(self) -> None:
        fixture = ROOT / "fixtures" / "incomplete_requirement.md"
        self.assertEqual(main(["init", "GAPVIEW"]), 0)
        self.assertEqual(main(["ingest", "GAPVIEW", "--source", str(fixture)]), 0)
        self.assertEqual(main(["view", "GAPVIEW", "--artifact", "gaps"]), 0)

        view_path = self.temp / "workspaces" / "GAPVIEW" / "08_context_packs" / "views" / "gaps.html"
        self.assertTrue(view_path.exists())
        html = view_path.read_text(encoding="utf-8")
        self.assertIn("read-only derived view", html)
        self.assertIn("const model =", html)
        self.assertIn("GAPVIEW", html)
        self.assertIn("localStorage", html)
        self.assertIn("Export Markdown", html)
        self.assertIn("Decision status", html)
        self.assertIn("sentinel /resolve-gaps", html)
        self.assertIn("sentinel /sync", html)
        self.assertIn("Guided Response", html)
        self.assertIn("Client progress", html)
        self.assertIn("guided-answer", html)
        # IMP-211 (H10, H-JOSE-1): the mailto draft button and the guided-answer
        # export must both be present so the client feedback loop round-trips.
        self.assertIn("Draft Email To BA", html)
        self.assertIn("mailto:", html)
        self.assertIn("buildGuidedResponseExport", html)
        self.assertIn("## Guided Responses", html)
        self.assertNotIn("__ARTIFACT_DATA__", html)
        self.assertNotIn("<script src=", html)
        self.assertNotIn("http://", html)
        self.assertNotIn("https://", html)

        state = json.loads((self.temp / "workspaces" / "GAPVIEW" / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(state["last_command"], "view")

    def test_markdown_to_html_renders_ordered_lists(self) -> None:
        # IMP-211 (H10, F-VIEW-1): ordered-list markers used to collapse into a
        # <p>, losing their numbering; they must render as <ol>/<li>.
        html = markdown_to_html("1. first\n2. second\n3. third")
        self.assertIn("<ol>", html)
        self.assertIn("</ol>", html)
        self.assertEqual(html.count("<li>"), 3)
        self.assertIn("<li>first</li>", html)
        self.assertNotIn("<p>1. first", html)
        # Switching marker style closes the previous container: bullets stay <ul>.
        mixed = markdown_to_html("- bullet\n1. number")
        self.assertIn("<ul>", mixed)
        self.assertIn("</ul>", mixed)
        self.assertIn("<ol>", mixed)

    def test_feedback_export_shape_is_accepted_by_resolve_gaps_and_sync(self) -> None:
        fixture = ROOT / "fixtures" / "incomplete_requirement.md"
        self.assertEqual(main(["init", "FEEDBACK"]), 0)
        self.assertEqual(main(["ingest", "FEEDBACK", "--source", str(fixture)]), 0)

        gap_export = self.temp / "artifact-feedback-gap.md"
        gap_export.write_text(
            "# Artifact Review Feedback Export - FEEDBACK\n\n"
            "- Source artifact: workspaces/FEEDBACK/01_discovery/gaps.md\n"
            "- Resolve gaps command: sentinel /resolve-gaps FEEDBACK --source PATH\n\n"
            "### GAP-USERS\n"
            "- Answer: Primary users are support operations analysts reviewing queue risk before standup.\n"
            "- Owner / source: Artifact review comment\n"
            "- Evidence or reference: workspaces/FEEDBACK/01_discovery/gaps.md#marker-1 lines 1-12\n"
            "- Decision status: pending\n",
            encoding="utf-8",
        )
        self.assertEqual(main(["resolve-gaps", "FEEDBACK", "--source", str(gap_export)]), 0)
        gaps = (self.temp / "workspaces" / "FEEDBACK" / "01_discovery" / "gaps.md").read_text(encoding="utf-8")
        self.assertIn("ANSWERED", gaps)
        self.assertIn("awaiting-confirmation: substantive answer", gaps)

        sync_export = self.temp / "artifact-feedback-sync.md"
        sync_export.write_text(
            "# Artifact Review Feedback Export - FEEDBACK\n\n"
            "- Source artifact: workspaces/FEEDBACK/01_discovery/gaps.md\n"
            "- Sync command: sentinel /sync FEEDBACK --source PATH --note \"Artifact review feedback\"\n\n"
            "### Review Comment: FBC-1\n"
            "- Target: section `section-1`\n"
            "- Source artifact: `workspaces/FEEDBACK/01_discovery/gaps.md`\n"
            "- Section: Discovery Gaps\n"
            "- Comment: Please clarify whether the rollout owner is Product or Delivery.\n"
            "- Suggested command: `sentinel /sync FEEDBACK --source PATH --note \"Artifact review feedback\"`\n",
            encoding="utf-8",
        )
        self.assertEqual(
            main(["sync", "FEEDBACK", "--source", str(sync_export), "--note", "Artifact review feedback"]),
            0,
        )
        state = json.loads((self.temp / "workspaces" / "FEEDBACK" / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(state["last_command"], "sync")
        self.assertTrue(state.get("last_change_id", "").startswith("CHG-"))

    def test_gap_markers_include_elicitation_metadata_and_section_badges(self) -> None:
        fixture = ROOT / "fixtures" / "incomplete_requirement.md"
        self.assertEqual(main(["init", "GAPMETA"]), 0)
        self.assertEqual(main(["ingest", "GAPMETA", "--source", str(fixture)]), 0)

        model = collect_artifact_model("GAPMETA", "gaps")
        gap_marker = next(marker for marker in model["markers"] if marker["marker"] == "GAP-USERS")

        self.assertTrue(gap_marker["metadata"]["lens"])
        self.assertEqual(gap_marker["metadata"]["severity"], "high")
        self.assertIn("why", gap_marker["metadata"])
        self.assertIn("unblocks", gap_marker["metadata"])
        self.assertIn("expected_format", gap_marker["metadata"])
        self.assertGreater(model["summary"]["sections_pending"], 0)
        self.assertGreater(model["guided_response"]["summary"]["client"], 0)
        self.assertGreater(model["guided_response"]["summary"]["domain"], 0)

        guided = {item["id"]: item for item in model["guided_response"]["items"]}
        self.assertEqual(guided["GAP-USERS"]["audience"], "client")
        self.assertTrue(guided["GAP-USERS"]["response_needed"])
        self.assertEqual(guided["GAP-TECH-DATA-SOURCE"]["audience"], "domain")

    def test_assumption_markers_include_owner_risk_and_html_anchors(self) -> None:
        raw = self.temp / "raw.md"
        raw.write_text(
            "# Risk Dashboard\n\n"
            "We need a dashboard for operations leads to see queue risk before standup. "
            "The dashboard reads queue metrics from the existing support metrics service.",
            encoding="utf-8",
        )
        assumption_source = self.temp / "assumptions.json"
        assumption_source.write_text(
            json.dumps(
                {
                    "assumptions": [
                        {
                            "id": "ASM-TECH-METRICS-SOURCE",
                            "lens": "technical",
                            "statement": "The dashboard will provisionally use the existing support metrics service as the source for queue risk.",
                            "owner": "Technology Lead",
                            "risk": "med",
                            "justification": "The dashboard reads queue metrics from the existing support metrics service.",
                            "closes_gap": "GAP-TECH-DATA-SOURCE",
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        self.assertEqual(main(["init", "ASMMETA"]), 0)
        self.assertEqual(main(["ingest", "ASMMETA", "--source", str(raw)]), 0)
        self.assertEqual(main(["assume", "ASMMETA", "--source", str(assumption_source)]), 0)
        self.assertEqual(main(["maturity", "ASMMETA"]), 0)
        self.assertEqual(main(["brief", "ASMMETA"]), 0)
        self.assertEqual(main(["view", "ASMMETA", "--artifact", "brief"]), 0)

        model = collect_artifact_model("ASMMETA", "brief")
        assumption = next(marker for marker in model["markers"] if marker["marker"] == "ASM-TECH-METRICS-SOURCE")
        self.assertEqual(assumption["metadata"]["owner"], "Technology Lead")
        self.assertEqual(assumption["metadata"]["risk"], "med")
        self.assertTrue(assumption["metadata"]["readiness_cells"])
        self.assertGreater(model["summary"]["sections_assumed"], 0)
        guided = {item["id"]: item for item in model["guided_response"]["items"]}
        self.assertEqual(guided["ASM-TECH-METRICS-SOURCE"]["audience"], "ba_assumption")
        self.assertFalse(guided["ASM-TECH-METRICS-SOURCE"]["response_needed"])

        html = (
            self.temp
            / "workspaces"
            / "ASMMETA"
            / "08_context_packs"
            / "views"
            / "brief.html"
        ).read_text(encoding="utf-8")
        self.assertIn('"id": "marker-', html)
        self.assertIn("Owner/risk", html)
        self.assertIn("ASM-TECH-METRICS-SOURCE", html)


if __name__ == "__main__":
    unittest.main()
