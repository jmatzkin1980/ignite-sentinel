"""IMP-303 (H18): every command surface agrees with the single command registry.

`sentinel/commands.py` declares each command once. The CLI parser and the protocol
sets are built from it; the rest is checked here against it: the CLI dispatch, the
MCP tools and their parameters, the commands manifest, the user guide and the view
artifacts the MCP `view` tool describes.
"""
from __future__ import annotations

import argparse
import ast
import re
import unittest
from pathlib import Path
from unittest.mock import patch

from sentinel import commands
from sentinel.adapters import manifest_command_names
from sentinel.commands import (
    BY_NAME,
    COMMANDS,
    EXEMPT,
    MCP_TOOLS,
    MUTATING,
    READ_ONLY,
    REGISTRY,
    RELEASE_COMMANDS,
    VIEW_ARTIFACTS,
    Command,
    build_parser,
    cli_destinations,
)
from sentinel.mcp import MCP_ONLY_TOOLS, TOOL_DESCRIPTIONS, TOOL_SPECS

ROOT = Path(__file__).resolve().parents[1]
CLI = (ROOT / "sentinel" / "cli.py").read_text(encoding="utf-8")
MCP = (ROOT / "sentinel" / "mcp.py").read_text(encoding="utf-8")
GUIDE = (ROOT / "user_guide" / "01-command-reference.md").read_text(encoding="utf-8")


def mcp_tool_parameters() -> dict[str, set[str]]:
    """The parameters of each `sentinel_<tool>` function in mcp.py, read without importing `mcp`."""
    tools: dict[str, set[str]] = {}
    for node in ast.walk(ast.parse(MCP)):
        if isinstance(node, ast.FunctionDef) and node.name.startswith("sentinel_"):
            tools[node.name.removeprefix("sentinel_")] = {arg.arg for arg in node.args.args}
    return tools


def expected_parameters(command: Command) -> set[str]:
    covering: dict[str, set[str]] = {}
    for param, dests in command.mcp_params.items():
        for dest in dests:
            covering.setdefault(dest, set()).add(param)
    expected: set[str] = set()
    for dest in cli_destinations(command.name) - set(command.mcp_omits):
        expected |= covering.get(dest, {dest})
    return expected


def subparsers(parser: argparse.ArgumentParser) -> dict[str, argparse.ArgumentParser]:
    action = next(a for a in parser._actions if isinstance(a, argparse._SubParsersAction))
    return dict(action.choices)


class RegistryShapeTests(unittest.TestCase):
    def test_names_are_unique_and_protocols_known(self) -> None:
        self.assertEqual(len(REGISTRY), len(BY_NAME))
        for command in REGISTRY:
            with self.subTest(command=command.name):
                self.assertIn(command.protocol, (READ_ONLY, MUTATING, EXEMPT))
                self.assertEqual(bool(command.exempt_reason.strip()), command.protocol == EXEMPT)
                for dest, reason in command.mcp_omits.items():
                    self.assertIn(dest, cli_destinations(command.name))
                    self.assertTrue(reason.strip())

    def test_protocol_classification(self) -> None:
        # IMP-244: only these three are outside the protocol; /stakeholders writes, so it is mutating.
        self.assertEqual({c.name for c in REGISTRY if c.protocol == EXEMPT}, {"doctor", "dashboard", "init"})
        self.assertEqual(BY_NAME["stakeholders"].protocol, MUTATING)
        from sentinel import protocols

        self.assertEqual(protocols.PROJECT_COMMANDS, {c.name for c in REGISTRY if c.protocol != EXEMPT})

    def test_the_parser_is_the_registry(self) -> None:
        parsers = subparsers(build_parser())
        self.assertEqual(set(parsers), set(COMMANDS))
        for name in RELEASE_COMMANDS:
            self.assertIn("--release", parsers[name]._option_string_actions, name)

    def test_a_command_added_to_the_registry_reaches_the_parser(self) -> None:
        extra = Command("probe-only", READ_ONLY, lambda p: p.add_argument("project_id"), release=True)
        with patch.object(commands, "REGISTRY", REGISTRY + (extra,)):
            parsers = subparsers(build_parser())
        self.assertIn("probe-only", parsers)
        self.assertIn("--release", parsers["probe-only"]._option_string_actions)

    def test_every_command_has_a_dispatch_branch(self) -> None:
        for name in COMMANDS:
            with self.subTest(command=name):
                self.assertIn(f'args.command == "{name}"', CLI)

    def test_release_scope_uses_the_registry(self) -> None:
        from sentinel import release_scope

        self.assertEqual(release_scope.RELEASE_COMMANDS, RELEASE_COMMANDS)


class McpTests(unittest.TestCase):
    def test_one_tool_per_command_plus_the_mcp_only_ones(self) -> None:
        self.assertEqual({name for name, _d, _r in TOOL_SPECS}, set(MCP_TOOLS) | set(MCP_ONLY_TOOLS))
        self.assertEqual(set(mcp_tool_parameters()), set(MCP_TOOLS) | set(MCP_ONLY_TOOLS))
        self.assertEqual(MCP_ONLY_TOOLS & {c.replace("-", "_") for c in COMMANDS}, set())

    def test_every_cli_option_has_its_mcp_parameter(self) -> None:
        tools = mcp_tool_parameters()
        for command in REGISTRY:
            if not command.mcp:
                continue
            with self.subTest(command=command.name):
                expected = expected_parameters(command)
                actual = tools[command.tool]
                self.assertEqual(expected - actual, set(), "CLI options with no MCP parameter")
                self.assertEqual(actual - expected, set(), "MCP parameters with no CLI option")

    def test_required_parameters_exist(self) -> None:
        tools = mcp_tool_parameters()
        for name, _description, required in TOOL_SPECS:
            with self.subTest(tool=name):
                self.assertEqual(set(required) - tools[name], set())

    def test_the_view_tool_names_every_artifact(self) -> None:
        for artifact in VIEW_ARTIFACTS:
            self.assertIn(artifact, TOOL_DESCRIPTIONS["view"].lower(), artifact)


class DocumentationTests(unittest.TestCase):
    def test_the_manifest_lists_exactly_the_registry(self) -> None:
        # `/sentinel` is the router entry point of the adapters, not a runtime command.
        self.assertEqual(set(manifest_command_names()) - {"sentinel"}, set(COMMANDS))

    def test_the_command_reference_has_one_section_per_command(self) -> None:
        sections = set(re.findall(r"^## `([a-z-]+)`", GUIDE, flags=re.M))
        self.assertEqual(sections, set(COMMANDS))


if __name__ == "__main__":
    unittest.main()
