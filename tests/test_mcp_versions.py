"""IMP-245: the MCP server works with `mcp` 1.x (FastMCP) and 2.x (MCPServer).

`mcp` 2.x renamed `mcp.server.fastmcp.FastMCP` to `MCPServer` (documented at
`mcp.server.mcpserver`, also re-exported from `mcp.server`) and changed the
positional order of the constructor, so only the name is positional. These tests
inject fake modules shaped like each version, so they do not need `mcp` installed.
"""

from __future__ import annotations

import sys
import types
import unittest
from unittest.mock import patch


class _FakeServer:
    instances: list["_FakeServer"] = []

    def __init__(self, name, **kwargs):
        self.name = name
        self.kwargs = kwargs
        self.tools: dict[str, dict] = {}
        self.run_calls: list[dict] = []
        _FakeServer.instances.append(self)

    def tool(self, name=None, description=None, **_):
        def decorator(fn):
            self.tools[name or fn.__name__] = {"description": description, "fn": fn}
            return fn

        return decorator

    def run(self, **kwargs):
        self.run_calls.append(kwargs)


def _modules_v2(where: str) -> dict[str, types.ModuleType]:
    mcp = types.ModuleType("mcp")
    server = types.ModuleType("mcp.server")
    mods = {"mcp": mcp, "mcp.server": server}
    if where == "mcpserver":
        mcpserver = types.ModuleType("mcp.server.mcpserver")
        mcpserver.MCPServer = type("MCPServer", (_FakeServer,), {})
        mods["mcp.server.mcpserver"] = mcpserver
    else:
        server.MCPServer = type("MCPServer", (_FakeServer,), {})
    return mods


def _modules_v1() -> dict[str, types.ModuleType]:
    mcp = types.ModuleType("mcp")
    server = types.ModuleType("mcp.server")
    fastmcp = types.ModuleType("mcp.server.fastmcp")
    fastmcp.FastMCP = type("FastMCP", (_FakeServer,), {})
    return {"mcp": mcp, "mcp.server": server, "mcp.server.fastmcp": fastmcp}


class McpVersionTests(unittest.TestCase):
    def setUp(self) -> None:
        _FakeServer.instances.clear()
        # Make sure no real `mcp` (or a previous fake) leaks between cases.
        self.cleared = patch.dict(sys.modules, {name: None for name in ("mcp", "mcp.server", "mcp.server.fastmcp", "mcp.server.mcpserver")})

    def _build(self, modules: dict[str, types.ModuleType]):
        from sentinel import mcp as sentinel_mcp

        with self.cleared, patch.dict(sys.modules, modules):
            return sentinel_mcp.build_server()

    def test_mcp2_documented_module(self) -> None:
        server = self._build(_modules_v2("mcpserver"))
        self.assertEqual(type(server).__name__, "MCPServer")

    def test_mcp2_reexport_from_mcp_server(self) -> None:
        server = self._build(_modules_v2("server"))
        self.assertEqual(type(server).__name__, "MCPServer")

    def test_mcp1_fastmcp_fallback(self) -> None:
        server = self._build(_modules_v1())
        self.assertEqual(type(server).__name__, "FastMCP")

    def test_only_the_name_is_positional(self) -> None:
        server = self._build(_modules_v2("mcpserver"))
        self.assertEqual(server.name, "ignite-sentinel")
        self.assertIn("instructions", server.kwargs)
        self.assertNotIn("title", server.kwargs)

    def test_same_tools_on_both_versions(self) -> None:
        v2 = self._build(_modules_v2("mcpserver"))
        v1 = self._build(_modules_v1())
        self.assertEqual(sorted(v2.tools), sorted(v1.tools))
        self.assertEqual(len(v2.tools), 33)

    def test_missing_dependency_message(self) -> None:
        from sentinel import mcp as sentinel_mcp

        with self.cleared, self.assertRaises(RuntimeError) as ctx:
            sentinel_mcp.build_server()
        self.assertIn("pip install", str(ctx.exception))

    def test_main_runs_over_stdio_explicitly(self) -> None:
        from sentinel import mcp as sentinel_mcp

        with self.cleared, patch.dict(sys.modules, _modules_v2("mcpserver")):
            sentinel_mcp.main([])
        self.assertEqual(_FakeServer.instances[-1].run_calls, [{"transport": "stdio"}])

    def test_extra_is_bounded(self) -> None:
        from pathlib import Path

        pyproject = (Path(__file__).resolve().parents[1] / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn('"mcp>=1.2,<3"', pyproject)


if __name__ == "__main__":
    unittest.main()
