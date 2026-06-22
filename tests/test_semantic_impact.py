import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from sentinel.health import run_health
from sentinel.discovery import render_gaps
from sentinel.sync import semantic_change_analysis, sync_change
from sentinel.traceability import write_traceability_matrix
from sentinel.workspace import ensure_workspace, write_json


class SemanticImpactTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = Path(tempfile.mkdtemp())
        self.old_cwd = Path.cwd()
        os.chdir(self.temp)
        self.ws = ensure_workspace("IMPACT")
        (self.ws / "02_requirements" / "requirements.md").write_text("# Requirements\n\nREQ-001 baseline.\n", encoding="utf-8")
        (self.ws / "01_discovery" / "gaps.md").write_text(render_gaps("IMPACT", [], "REQ-001"), encoding="utf-8")
        (self.ws / "03_specs" / "prd.md").write_text("# PRD\n\nDashboard scope.\n", encoding="utf-8")
        (self.ws / "03_specs" / "specs.md").write_text("# Specs\n\nDashboard implementation.\n", encoding="utf-8")
        write_json(
            self.ws / "06_traceability" / "traceability_graph.json",
            {
                "nodes": [
                    {
                        "id": "REQ-001",
                        "type": "requirement",
                        "path": "workspaces/IMPACT/02_requirements/requirements.md",
                        "title": "Requirement",
                        "status": "active",
                        "domain": "product",
                    },
                    {
                        "id": "PRD-001",
                        "type": "prd",
                        "path": "workspaces/IMPACT/03_specs/prd.md",
                        "title": "PRD",
                        "status": "active",
                        "domain": "product",
                    },
                    {
                        "id": "SPEC-001",
                        "type": "spec",
                        "path": "workspaces/IMPACT/03_specs/specs.md",
                        "title": "Specs",
                        "status": "active",
                        "domain": "technical",
                    },
                ],
                "edges": [
                    {"from": "REQ-001", "to": "PRD-001", "relation": "derives"},
                    {"from": "PRD-001", "to": "SPEC-001", "relation": "derives"},
                ],
            },
        )

    def tearDown(self) -> None:
        os.chdir(self.old_cwd)
        shutil.rmtree(self.temp, ignore_errors=True)

    def test_semantic_change_cues_distinguish_cosmetic_change(self) -> None:
        self.assertFalse(semantic_change_analysis("Fix typo and formatting only.")["suspicious"])
        analysis = semantic_change_analysis("The dashboard is no longer in scope; use workflow export instead.")
        self.assertTrue(analysis["suspicious"])
        self.assertIn("instead", analysis["triggers"])

    def test_sync_marks_suspicious_trace_links_without_rewriting_downstream(self) -> None:
        change = self.temp / "semantic-change.md"
        change.write_text("The dashboard is no longer in scope; replace it with a workflow export instead.", encoding="utf-8")

        result = sync_change("IMPACT", change, "semantic scope change")

        links = result["suspicious_trace_links"]
        self.assertGreaterEqual(len(links), 2)
        graph = json.loads((self.ws / "06_traceability" / "traceability_graph.json").read_text(encoding="utf-8"))
        suspicious_edges = [edge for edge in graph["edges"] if edge.get("suspicious")]
        self.assertTrue(suspicious_edges)
        self.assertTrue(all(edge["review_status"] == "needs-ba-review" for edge in suspicious_edges))
        report = next((self.ws / "07_changes").rglob("*impact_report.md")).read_text(encoding="utf-8")
        self.assertIn("## Suspicious Trace Links", report)
        self.assertIn("semantic-change-cue", report)
        matrix = write_traceability_matrix("IMPACT").read_text(encoding="utf-8")
        self.assertIn("SUSPICIOUS: semantic-change-cue", matrix)

        health = run_health("IMPACT")
        self.assertIn("Semantic change may invalidate downstream trace links", "\n".join(health["findings"]))


if __name__ == "__main__":
    unittest.main()
