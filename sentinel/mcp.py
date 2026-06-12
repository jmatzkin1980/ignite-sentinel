"""Local-first MCP server for Ignite Sentinel (IMP-017).

Exposes the governed lifecycle as MCP tools over stdio, so any MCP client
(Claude Desktop, Claude Code, VS Code, Cursor, Codex, ...) can operate Sentinel
without a per-IDE chat adapter. 100% local: stdio transport, no network, the
same CLI gates and command protocol apply. Workspace files remain the source
of truth.

Requires the optional `mcp` dependency:

    python -m pip install -e .[mcp]

Run from the repository root:

    python -m sentinel.mcp

Claude Desktop / Claude Code configuration example:

    {
      "mcpServers": {
        "ignite-sentinel": {
          "command": "python",
          "args": ["-m", "sentinel.mcp"],
          "cwd": "C:/path/to/ignite-sentinel"
        }
      }
    }
"""
from __future__ import annotations

import contextlib
import io
import json
import sys


TOOL_SPECS: list[tuple[str, str, list[str]]] = [
    ("doctor", "Validate that Ignite Sentinel is ready in this repository.", []),
    ("init", "Create a new Sentinel project workspace.", ["project_id"]),
    ("ingest", "Ingest raw client/domain evidence and run inquisitive discovery.", ["project_id", "source"]),
    ("gaps", "Regenerate the human-friendly discovery gaps document.", ["project_id"]),
    ("resolve_gaps", "Process structured gap answers; closes only substantive confirmed answers.", ["project_id", "source"]),
    ("maturity", "Evaluate requirement maturity with quantified metrics and trend.", ["project_id"]),
    ("brief", "Materialize the mature project brief from discovery evidence.", ["project_id"]),
    ("context_request", "Generate a domain context request (technology|design|quality|frontend|backend).", ["project_id", "domain"]),
    ("status", "Report phase, health, gap counts, maturity metrics, and next step.", ["project_id"]),
    ("sync", "Metabolize new evidence; without source runs the autonomous novelty scan.", ["project_id"]),
    ("reindex", "Rebuild local memory from workspace artifacts.", ["project_id"]),
    ("retrieve", "Focused context retrieval (progressive disclosure) for a workflow.", ["project_id", "query", "workflow"]),
    ("specs", "Generate PRD and AI-friendly specs (blocked while maturity is BLOCKED).", ["project_id"]),
    ("backlog", "Generate epics, stories, and implementation readiness (gated by health).", ["project_id"]),
    ("quality", "Generate test cases and the backlog readiness audit.", ["project_id"]),
    ("trace", "Generate the traceability matrix and graph.", ["project_id"]),
    ("health", "Audit project health, including domain-context staleness.", ["project_id"]),
    ("validate", "Validate structure plus non-blocking semantic quality scores.", ["project_id"]),
    ("annotate", "Merge a validated agentic semantic analysis (origin: agent) of the raw input into gaps; each gap needs a verbatim evidence quote.", ["project_id", "source"]),
    ("challenge", "Merge validated advanced-elicitation findings (origin: challenge) from pre-mortem, per-lens role-play, and assumption inversion; writes challenge_report.md.", ["project_id", "source"]),
]


def run_cli(arguments: list[str]) -> dict[str, object]:
    """Run a Sentinel CLI command in-process and capture its JSON/text output."""
    from .cli import main

    stdout, stderr = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        try:
            exit_code = main(arguments)
        except SystemExit as exc:  # argparse or guards
            exit_code = int(exc.code or 0)
        except Exception as exc:  # surface gate errors as structured output
            return {"exit_code": 1, "error": str(exc), "output": stdout.getvalue().strip()}
    raw = stdout.getvalue().strip()
    payload: object
    try:
        payload = json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        payload = raw
    result: dict[str, object] = {"exit_code": exit_code, "output": payload}
    err = stderr.getvalue().strip()
    if err:
        result["error"] = err
    if exit_code != 0 and "error" not in result:
        result["error"] = raw or "Command failed; check gates with the status/health tools."
    return result


def describe_tools() -> list[dict[str, object]]:
    return [
        {"name": f"sentinel_{name}", "description": description, "required": required}
        for name, description, required in TOOL_SPECS
    ]


def build_server():
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "The MCP server requires the optional `mcp` dependency. "
            "Install it with: python -m pip install -e .[mcp]"
        ) from exc

    server = FastMCP(
        "ignite-sentinel",
        instructions=(
            "Ignite Sentinel: local-first requirements-maturation lifecycle. "
            "Typical flow: init -> ingest -> gaps -> resolve_gaps -> maturity -> brief -> "
            "specs -> backlog -> quality -> trace -> health -> validate. Gates are enforced: "
            "blocked maturity stops specs/backlog; DIRTY health stops backlog/quality. "
            "Workspace files are the source of truth."
        ),
    )

    @server.tool(name="sentinel_doctor", description=TOOL_SPECS[0][1])
    def sentinel_doctor() -> dict:
        return run_cli(["doctor"])

    @server.tool(name="sentinel_init", description=TOOL_SPECS[1][1])
    def sentinel_init(project_id: str) -> dict:
        return run_cli(["init", project_id])

    @server.tool(name="sentinel_ingest", description=TOOL_SPECS[2][1])
    def sentinel_ingest(project_id: str, source: str) -> dict:
        return run_cli(["ingest", project_id, "--source", source])

    @server.tool(name="sentinel_gaps", description=TOOL_SPECS[3][1])
    def sentinel_gaps(project_id: str) -> dict:
        return run_cli(["gaps", project_id])

    @server.tool(name="sentinel_resolve_gaps", description=TOOL_SPECS[4][1])
    def sentinel_resolve_gaps(project_id: str, source: str) -> dict:
        return run_cli(["resolve-gaps", project_id, "--source", source])

    @server.tool(name="sentinel_maturity", description=TOOL_SPECS[5][1])
    def sentinel_maturity(project_id: str) -> dict:
        return run_cli(["maturity", project_id])

    @server.tool(name="sentinel_brief", description=TOOL_SPECS[6][1])
    def sentinel_brief(project_id: str) -> dict:
        return run_cli(["brief", project_id])

    @server.tool(name="sentinel_context_request", description=TOOL_SPECS[7][1])
    def sentinel_context_request(project_id: str, domain: str) -> dict:
        return run_cli(["context-request", project_id, "--domain", domain])

    @server.tool(name="sentinel_status", description=TOOL_SPECS[8][1])
    def sentinel_status(project_id: str) -> dict:
        return run_cli(["status", project_id])

    @server.tool(name="sentinel_sync", description=TOOL_SPECS[9][1])
    def sentinel_sync(project_id: str, source: str = "", note: str = "") -> dict:
        arguments = ["sync", project_id]
        if source:
            arguments += ["--source", source]
        if note:
            arguments += ["--note", note]
        return run_cli(arguments)

    @server.tool(name="sentinel_reindex", description=TOOL_SPECS[10][1])
    def sentinel_reindex(project_id: str) -> dict:
        return run_cli(["reindex", project_id])

    @server.tool(name="sentinel_retrieve", description=TOOL_SPECS[11][1])
    def sentinel_retrieve(project_id: str, query: str, workflow: str = "discovery") -> dict:
        return run_cli(["retrieve", project_id, "--query", query, "--workflow", workflow])

    @server.tool(name="sentinel_specs", description=TOOL_SPECS[12][1])
    def sentinel_specs(project_id: str) -> dict:
        return run_cli(["specs", project_id])

    @server.tool(name="sentinel_backlog", description=TOOL_SPECS[13][1])
    def sentinel_backlog(project_id: str) -> dict:
        return run_cli(["backlog", project_id])

    @server.tool(name="sentinel_quality", description=TOOL_SPECS[14][1])
    def sentinel_quality(project_id: str) -> dict:
        return run_cli(["quality", project_id])

    @server.tool(name="sentinel_trace", description=TOOL_SPECS[15][1])
    def sentinel_trace(project_id: str) -> dict:
        return run_cli(["trace", project_id])

    @server.tool(name="sentinel_health", description=TOOL_SPECS[16][1])
    def sentinel_health(project_id: str) -> dict:
        return run_cli(["health", project_id])

    @server.tool(name="sentinel_validate", description=TOOL_SPECS[17][1])
    def sentinel_validate(project_id: str) -> dict:
        return run_cli(["validate", project_id])

    @server.tool(name="sentinel_annotate", description=TOOL_SPECS[18][1])
    def sentinel_annotate(project_id: str, source: str) -> dict:
        return run_cli(["annotate", project_id, "--source", source])

    @server.tool(name="sentinel_challenge", description=TOOL_SPECS[19][1])
    def sentinel_challenge(project_id: str, source: str) -> dict:
        return run_cli(["challenge", project_id, "--source", source])

    return server


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--describe" in argv:
        print(json.dumps({"server": "ignite-sentinel", "tools": describe_tools()}, indent=2))
        return 0
    build_server().run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
