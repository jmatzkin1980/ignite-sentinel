"""IMP-382: the MCP tools forward `change` to the CLI as the same flag the command takes."""
from __future__ import annotations

import unittest
from unittest.mock import patch

from sentinel import mcp as sentinel_mcp
from tests.test_mcp_parity import _tools


def _argv(tool_name: str, **kwargs) -> list[str]:
    captured: list[list[str]] = []
    with patch.object(sentinel_mcp, "run_cli", lambda arguments: captured.append(arguments) or {"exit_code": 0}):
        _tools()[tool_name](**kwargs)
    return captured[0]


class McpForwardsChange(unittest.TestCase):
    def test_gaps_builds_change_argv(self) -> None:
        self.assertEqual(["gaps", "P", "--change", "CHG-001"], _argv("sentinel_gaps", project_id="P", change="CHG-001"))

    def test_resolve_gaps_builds_change_argv(self) -> None:
        self.assertEqual(
            ["resolve-gaps", "P", "--source", "a.md", "--change", "CHG-001"],
            _argv("sentinel_resolve_gaps", project_id="P", source="a.md", change="CHG-001"),
        )

    def test_ingest_builds_change_flag(self) -> None:
        self.assertEqual(
            ["ingest", "P", "--source", "n.md", "--change"],
            _argv("sentinel_ingest", project_id="P", source="n.md", change=True),
        )

    def test_without_change_no_flag(self) -> None:
        self.assertEqual(["gaps", "P"], _argv("sentinel_gaps", project_id="P"))


if __name__ == "__main__":
    unittest.main()
