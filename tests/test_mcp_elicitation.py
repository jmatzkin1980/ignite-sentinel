from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from pathlib import Path

from sentinel.discovery import render_gaps
from sentinel.mcp import client_supports_elicitation, gap_elicitation
from sentinel.workspace import workspace_path


class McpGapElicitationTests(unittest.TestCase):
    def setUp(self):
        self.old_cwd = Path.cwd()
        self.temp = Path(tempfile.mkdtemp())
        os.chdir(self.temp)

    def tearDown(self):
        os.chdir(self.old_cwd)
        shutil.rmtree(self.temp, ignore_errors=True)

    def test_client_supports_elicitation_detects_declared_capability(self):
        self.assertTrue(client_supports_elicitation({"elicitation": {}}))
        self.assertTrue(client_supports_elicitation({"capabilities": {"elicitation": {}}}))
        self.assertTrue(client_supports_elicitation('{"capabilities": {"elicitation": {}}}'))
        self.assertFalse(client_supports_elicitation({}))
        self.assertFalse(client_supports_elicitation('{"capabilities": {}}'))

    def test_gap_elicitation_without_capability_returns_gaps_tool_result_exactly(self):
        from sentinel import mcp

        original = mcp.run_cli
        try:
            mcp.run_cli = lambda arguments: {"exit_code": 0, "output": {"arguments": arguments}}

            self.assertEqual(
                {"exit_code": 0, "output": {"arguments": ["gaps", "ELICIT"]}},
                gap_elicitation("ELICIT", "GAP-METRIC-SOURCE", {}),
            )
        finally:
            mcp.run_cli = original

    def test_gap_elicitation_with_capability_returns_structured_request(self):
        base = workspace_path("ELICIT")
        gaps_dir = base / "01_discovery"
        gaps_dir.mkdir(parents=True)
        gaps_dir.joinpath("gaps.md").write_text(
            render_gaps(
                "ELICIT",
                [
                    {
                        "id": "GAP-METRIC-SOURCE",
                        "lens": "business",
                        "severity": "high",
                        "status": "OPEN",
                        "description": "Metric source is not confirmed.",
                        "question": "Which source owns uptime?",
                        "evidence_mention": "uptime",
                        "origin": "checklist",
                    }
                ],
                "REQ-001",
            ),
            encoding="utf-8",
        )

        result = gap_elicitation("ELICIT", "gap-metric-source", {"elicitation": {}})

        self.assertEqual(0, result["exit_code"])
        payload = result["output"]
        self.assertEqual("mcp_elicitation_request", payload["type"])
        self.assertEqual("GAP-METRIC-SOURCE", payload["gap_id"])
        self.assertEqual("Which source owns uptime?", payload["question"])
        self.assertGreaterEqual(len(payload["candidate_options"]), 1)
        self.assertIn("selected_option", payload["schema"]["properties"])


if __name__ == "__main__":
    unittest.main()
