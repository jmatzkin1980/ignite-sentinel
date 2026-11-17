"""IMP-333: every MCP tool forwards each CLI option it accepts, and keeps the CLI's defaults.

`tests/test_command_registry.py` checks the parameter *names*. These tests call each
tool function (built against a fake `mcp` module, so `mcp` need not be installed) with
every parameter set, parse the argv it hands to `run_cli` with the real CLI parser, and
check each value arrived: a parameter is either forwarded or refused with an error,
never dropped in silence. A second test calls each tool with only its required
parameters and checks the CLI defaults hold, except the documented `MCP_DEFAULTS`.
"""
from __future__ import annotations

import argparse
import inspect
import os
import shutil
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from sentinel import mcp as sentinel_mcp
from sentinel.commands import REGISTRY, Command, build_parser


class _FakeServer:
    def __init__(self, name, **kwargs):
        self.tools: dict[str, object] = {}

    def tool(self, name=None, description=None, **_):
        def decorator(fn):
            self.tools[name or fn.__name__] = fn
            return fn

        return decorator


def _tools() -> dict[str, object]:
    mcp = types.ModuleType("mcp")
    server = types.ModuleType("mcp.server")
    mcpserver = types.ModuleType("mcp.server.mcpserver")
    mcpserver.MCPServer = type("MCPServer", (_FakeServer,), {})
    with patch.dict(sys.modules, {"mcp": mcp, "mcp.server": server, "mcp.server.mcpserver": mcpserver}):
        return sentinel_mcp.build_server().tools


def _actions(command: Command) -> dict[str, argparse.Action]:
    parser = argparse.ArgumentParser(add_help=False)
    command.configure(parser)
    if command.release:
        parser.add_argument("--release")
    return {action.dest: action for action in parser._actions}


def _probe(param: inspect.Parameter, action: argparse.Action) -> tuple[object, object]:
    """A non-default value for one parameter and the value the CLI namespace should then hold."""
    if action.nargs == 0:  # store_true
        return True, True
    if action.choices:
        choice = next(c for c in action.choices if c != action.default)
        return (str(choice) if param.annotation in (str, "str") else choice), choice
    if action.type is int:
        return 7, 7
    return f"probe-{param.name}", f"probe-{param.name}"


def _mode_param(command: Command) -> str:
    """The parameter that names a mutually exclusive group of store_true flags, if any."""
    return next((p for p, dests in command.mcp_params.items() if len(dests) > 1), "")


def _call(tool, kwargs: dict[str, object]) -> list[str] | Exception:
    captured: list[list[str]] = []
    with patch.object(sentinel_mcp, "run_cli", lambda arguments: captured.append(arguments) or {"exit_code": 0}):
        try:
            tool(**kwargs)
        except ValueError as exc:  # an explicit refusal is fine; a silent drop is not
            return exc
    return captured[0]


class McpForwardsEveryOption(unittest.TestCase):
    def test_every_set_parameter_reaches_the_cli_or_is_refused(self) -> None:
        tools = _tools()
        parser = build_parser()
        for command in REGISTRY:
            if not command.mcp:
                continue
            tool = tools[f"sentinel_{command.tool}"]
            actions = _actions(command)
            mode = _mode_param(command)
            params = inspect.signature(tool).parameters
            modes = command.mcp_params[mode] if mode else ("",)
            # Flags on and flags off: a value must not depend on a flag (e.g. `add`) to be forwarded.
            for mode_value, flags in [(m, f) for m in modes for f in (True, False)]:
                kwargs: dict[str, object] = {}
                expected: dict[str, object] = {}
                for name, param in params.items():
                    if name == mode:
                        kwargs[name] = mode_value
                        expected[mode_value] = True
                        continue
                    dest = command.mcp_params.get(name, (name,))[0]
                    kwargs[name], expected[dest] = _probe(param, actions[dest])
                    if expected[dest] is True and not flags:
                        kwargs[name] = expected[dest] = False
                if mode_value == "close":  # --close carries the release
                    expected["close"] = kwargs["release"]
                with self.subTest(command=command.name, mode=mode_value, flags=flags):
                    argv = _call(tool, kwargs)
                    if isinstance(argv, Exception):
                        continue
                    namespace = vars(parser.parse_args(argv))
                    for dest, value in expected.items():
                        self.assertEqual(namespace.get(dest), value, f"{dest} was dropped: {argv}")

    def test_a_parameter_the_mode_cannot_take_is_refused(self) -> None:
        tools = _tools()
        with patch.object(sentinel_mcp, "run_cli", lambda arguments: {"exit_code": 0}):
            with self.assertRaises(ValueError):
                tools["sentinel_split"](project_id="P", mode="assess", release="r1")

    def test_defaults_match_the_cli_except_the_documented_ones(self) -> None:
        tools = _tools()
        parser = build_parser()
        for command in REGISTRY:
            if not command.mcp:
                continue
            tool = tools[f"sentinel_{command.tool}"]
            actions = _actions(command)
            kwargs = {
                name: _probe(param, actions[command.mcp_params.get(name, (name,))[0]])[0]
                for name, param in inspect.signature(tool).parameters.items()
                if param.default is inspect.Parameter.empty
            }
            with self.subTest(command=command.name):
                argv = _call(tool, kwargs)
                self.assertNotIsInstance(argv, Exception)
                documented = {param for (name, param) in sentinel_mcp.MCP_DEFAULTS if name == command.tool}
                covered = {dest for param in documented for dest in command.mcp_params.get(param, (param,))}
                if covered:  # a documented default may fill a group the CLI requires
                    continue
                namespace = vars(parser.parse_args(argv))
                for dest, action in actions.items():
                    if dest in {command.mcp_params.get(n, (n,))[0] for n in kwargs} or dest in covered:
                        continue
                    if action.required or dest == "project_id":
                        continue
                    self.assertEqual(namespace.get(dest), action.default, f"{dest} default differs: {argv}")

    def test_documented_defaults_name_real_parameters(self) -> None:
        tools = _tools()
        for (tool, param), reason in sentinel_mcp.MCP_DEFAULTS.items():
            with self.subTest(tool=tool, param=param):
                self.assertIn(param, inspect.signature(tools[f"sentinel_{tool}"]).parameters)
                self.assertTrue(reason.strip())


class CliRefusesWhatItWouldIgnore(unittest.TestCase):
    """The MCP tools now forward everything, so the CLI refuses the options it used to ignore."""

    def setUp(self) -> None:
        self.old_cwd = Path.cwd()
        self.temp = Path(tempfile.mkdtemp())
        os.chdir(self.temp)
        from sentinel.cli import main

        self.main = main
        with patch("sys.stdout"), patch("sys.stderr"):
            self.assertEqual(main(["init", "PARITY"]), 0)

    def tearDown(self) -> None:
        os.chdir(self.old_cwd)
        shutil.rmtree(self.temp, ignore_errors=True)

    def _run(self, argv: list[str]) -> int:
        with patch("sys.stdout"), patch("sys.stderr"):
            return self.main(argv)

    def test_stakeholder_fields_without_add_are_refused(self) -> None:
        self.assertEqual(self._run(["stakeholders", "PARITY", "--name", "Ana"]), 3)
        self.assertEqual(self._run(["stakeholders", "PARITY"]), 0)

    def test_precedence_with_other_options_is_refused(self) -> None:
        self.assertEqual(self._run(["sources", "PARITY", "--precedence", "scope", "--between", "F-01,F-02",
                                    "--id", "F-01"]), 3)


class GapElicitationLanguage(unittest.TestCase):
    def setUp(self) -> None:
        self.old_cwd = Path.cwd()
        self.temp = Path(tempfile.mkdtemp())
        os.chdir(self.temp)

    def tearDown(self) -> None:
        os.chdir(self.old_cwd)
        shutil.rmtree(self.temp, ignore_errors=True)

    def test_a_project_without_a_language_gets_english(self) -> None:
        from sentinel.discovery import render_gaps, unblocks_for_gap
        from sentinel.workspace import state_path, workspace_path, write_json

        gaps_dir = workspace_path("LANG") / "01_discovery"
        gaps_dir.mkdir(parents=True)
        # IMP-331: a workspace with artifacts needs its state.json; it carries no language yet.
        write_json(state_path("LANG"), {})
        gaps_dir.joinpath("gaps.md").write_text(render_gaps("LANG", [{
            "id": "GAP-METRIC-SOURCE", "lens": "business", "severity": "high", "status": "OPEN",
            "description": "Metric source is not confirmed.", "question": "Which source owns uptime?",
            "evidence_mention": "uptime", "origin": "checklist",
        }], "REQ-001"), encoding="utf-8")

        self.assertNotEqual(unblocks_for_gap("GAP-METRIC-SOURCE", "en"), unblocks_for_gap("GAP-METRIC-SOURCE", "es"))
        with patch("sentinel.workspace.load_config", return_value={}):  # a config with no language at all
            result = sentinel_mcp.gap_elicitation("LANG", "GAP-METRIC-SOURCE", {"elicitation": {}})
        self.assertEqual(result["output"]["unblocks"], unblocks_for_gap("GAP-METRIC-SOURCE", "en"))

        write_json(state_path("LANG"), {"project_language": "es"})
        result = sentinel_mcp.gap_elicitation("LANG", "GAP-METRIC-SOURCE", {"elicitation": {}})
        self.assertEqual(result["output"]["unblocks"], unblocks_for_gap("GAP-METRIC-SOURCE", "es"))


if __name__ == "__main__":
    unittest.main()
