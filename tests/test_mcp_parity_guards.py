"""IMP-176: parity guard between the CLI surface and the MCP tool surface.

`sentinel/mcp.py` exposes the governed lifecycle to MCP clients (Claude Desktop,
Cowork, ...). The H6 audit found capabilities reachable from the CLI but not from
MCP — implementability-probe (F1), focus-first retrieve options (F2), the audited
export channel (F3) — so Desktop/Cowork users silently could not do things the CLI
could. This guard, in the mold of the router<->manifest guard (IMP-163), fails if
a CLI command gains no MCP tool and is not listed in an explicit exclusion.
"""

import unittest

from sentinel.adapters import runtime_command_names
from sentinel.mcp import TOOL_SPECS, TOOL_DESCRIPTIONS, describe_tools

# CLI commands intentionally NOT exposed as MCP tools, each with a reason.
# Empty today: every CLI command has a tool. A new unexposed command must either
# gain a tool or be added here with a justification, or this guard fails.
MCP_EXCLUDED_COMMANDS: dict[str, str] = {}

# MCP tools that intentionally have no 1:1 CLI command.
MCP_ONLY_TOOLS = {"gap_elicitation"}


def _tool_names() -> set[str]:
    return {name for name, _description, _required in TOOL_SPECS}


class McpCliParity(unittest.TestCase):
    def test_every_cli_command_has_a_tool_or_explicit_exclusion(self):
        tools = _tool_names()
        for command in runtime_command_names():
            tool_name = command.replace("-", "_")
            if tool_name in tools:
                continue
            self.assertIn(
                command,
                MCP_EXCLUDED_COMMANDS,
                f"CLI command '{command}' has no MCP tool 'sentinel_{tool_name}' and no "
                f"entry in MCP_EXCLUDED_COMMANDS — expose it or document the exclusion.",
            )

    def test_mcp_only_and_excluded_sets_stay_honest(self):
        cli = {command.replace("-", "_") for command in runtime_command_names()}
        # Anything mapped to a CLI command must not also be declared MCP-only.
        self.assertEqual(MCP_ONLY_TOOLS & cli, set())
        # Every declared MCP-only tool actually exists as a tool.
        self.assertTrue(MCP_ONLY_TOOLS <= _tool_names())
        # Exclusions must reference real CLI commands.
        for command in MCP_EXCLUDED_COMMANDS:
            self.assertIn(command.replace("-", "_"), cli, f"stale exclusion: {command}")

    def test_descriptions_lookup_matches_specs(self):
        # De-positionalized lookup (F4) must cover every spec, one-to-one.
        self.assertEqual(set(TOOL_DESCRIPTIONS), {name for name, _d, _r in TOOL_SPECS})
        for tool in describe_tools():
            bare = tool["name"].removeprefix("sentinel_")
            self.assertEqual(tool["description"], TOOL_DESCRIPTIONS[bare])


class NewCapabilitiesReachable(unittest.TestCase):
    def test_probe_export_and_focus_first_are_exposed(self):
        tools = _tool_names()
        for required in ("scrutinize", "retrieve", "export"):
            self.assertIn(required, tools)


if __name__ == "__main__":
    unittest.main()
