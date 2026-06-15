from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from sentinel.cli import main
from sentinel.dashboard import LIFECYCLE_STAGES, SECTION_REGISTRY, collect_dashboard_model, generate_dashboard, render_html
from sentinel.workspace import ensure_workspace, write_json


ROOT = Path(__file__).parent


class DashboardTest(unittest.TestCase):
    def setUp(self) -> None:
        self.old_cwd = Path.cwd()
        self.temp = Path(tempfile.mkdtemp())
        os.chdir(self.temp)
        self.fixture = json.loads((ROOT / "fixtures" / "dashboard" / "portfolio_snapshot.json").read_text(encoding="utf-8"))
        self._materialize_fixture()

    def tearDown(self) -> None:
        os.chdir(self.old_cwd)
        shutil.rmtree(self.temp)

    def test_collect_dashboard_model_reads_portfolio_without_template(self) -> None:
        model = collect_dashboard_model(self.temp)

        self.assertEqual([workspace["project_id"] for workspace in model["workspaces"]], ["DASH_BACKLOG_READY", "DASH_CLIENT_WAIT"])
        self.assertEqual(model["kpis"]["total"], 2)
        self.assertEqual(model["kpis"]["attention"], 2)
        self.assertEqual(model["kpis"]["blocking_gaps"], 1)
        self.assertEqual(model["kpis"]["ready"], 1)
        self.assertEqual(model["kpis"]["stories"], 2)

        waiting = next(workspace for workspace in model["workspaces"] if workspace["project_id"] == "DASH_CLIENT_WAIT")
        self.assertEqual(waiting["lifecycle"]["index"], LIFECYCLE_STAGES["CLIENT_RESPONSE_NEEDED"]["index"])
        self.assertTrue(waiting["lifecycle"]["blocked"])
        self.assertEqual(len(waiting["gaps_detail"]), 2)
        self.assertEqual(waiting["documents"][0]["path"], "workspaces/DASH_CLIENT_WAIT/02_requirements/requirements.md")

        ready = next(workspace for workspace in model["workspaces"] if workspace["project_id"] == "DASH_BACKLOG_READY")
        self.assertEqual(ready["backlog_rollup"]["total_stories"], 2)
        self.assertIn("US-001", ready["story_gates"]["stories"])
        self.assertTrue(any(section.key == "documents" and section.render == "documents" for section in SECTION_REGISTRY))

    def test_render_html_embeds_data_and_omits_empty_sections(self) -> None:
        model = collect_dashboard_model(self.temp)
        html = render_html(model)

        self.assertIn("Ignite Sentinel - Workspaces", html)
        self.assertIn("dashboard-data", html)
        self.assertIn("DASH_CLIENT_WAIT", html)
        self.assertIn("Project Brief", html)
        self.assertIn("mdToHtml", html)
        self.assertNotIn("https://", html)

    def test_generate_dashboard_cli_is_read_only_snapshot(self) -> None:
        before = (self.temp / "workspaces" / "DASH_CLIENT_WAIT" / "state.json").read_text(encoding="utf-8")

        self.assertEqual(main(["/dashboard"]), 0)

        dashboard = self.temp / "dashboard.html"
        self.assertTrue(dashboard.exists())
        html = dashboard.read_text(encoding="utf-8")
        self.assertIn("Local-first", html)
        self.assertIn("DASH_BACKLOG_READY", html)
        self.assertEqual(before, (self.temp / "workspaces" / "DASH_CLIENT_WAIT" / "state.json").read_text(encoding="utf-8"))
        self.assertFalse((self.temp / "workspaces" / "DASH_CLIENT_WAIT" / "06_traceability" / "command_protocol_log.md").exists())

        result = generate_dashboard(self.temp)
        self.assertEqual(result["count"], 2)
        self.assertIn("DASH_CLIENT_WAIT", result["workspaces"])

    def _materialize_fixture(self) -> None:
        ensure_workspace("_template")
        for workspace in self.fixture["workspaces"]:
            project_id = workspace["project_id"]
            base = ensure_workspace(project_id)
            state = workspace["state"]
            state.setdefault("project_id", project_id)
            state.setdefault("artifacts", {})
            state.setdefault("updated_at", "2026-06-14T12:00:00+00:00")
            write_json(base / "state.json", state)
            gaps = workspace.get("gaps")
            if gaps:
                (base / "01_discovery" / "gaps.md").write_text(gaps, encoding="utf-8")
            for relative, content in workspace.get("documents", {}).items():
                path = base / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")
            if project_id == "DASH_BACKLOG_READY":
                for story_id in ("US-001", "US-002"):
                    (base / "04_backlog" / f"{story_id}.md").write_text(
                        f"---\nparent_epic: EPIC-001\nstatus: Ready\n---\n# {story_id} - Synthetic story\n",
                        encoding="utf-8",
                    )
                graph = {
                    "nodes": [
                        {"id": "US-001", "type": "user_story", "title": "Ready story"},
                        {"id": "US-002", "type": "user_story", "title": "Second story"},
                    ],
                    "edges": [],
                }
                write_json(base / "06_traceability" / "traceability_graph.json", graph)


if __name__ == "__main__":
    unittest.main()
