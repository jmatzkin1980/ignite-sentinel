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
    ("dashboard", "Generate the local read-only HTML portfolio dashboard for all workspaces.", []),
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
    ("backlog", "Generate epics, stories, and implementation readiness; optionally include task-seed contracts (gated by health).", ["project_id"]),
    ("quality", "Generate test cases and the backlog readiness audit.", ["project_id"]),
    ("trace", "Generate the traceability matrix and graph.", ["project_id"]),
    ("health", "Audit project health, including domain-context staleness.", ["project_id"]),
    ("validate", "Validate structure plus non-blocking semantic quality scores.", ["project_id"]),
    ("view", "Generate a local read-only HTML artifact view for gaps, brief, PRD, specs, or backlog.", ["project_id", "artifact"]),
    ("annotate", "Merge a validated agentic semantic analysis (origin: agent) of the raw input into gaps; each gap needs a verbatim evidence quote.", ["project_id", "source"]),
    ("challenge", "Merge validated advanced-elicitation findings (origin: challenge) from pre-mortem, per-lens role-play, assumption inversion, and JTBD Four Forces; writes challenge_report.md.", ["project_id", "source"]),
    ("scrutinize", "Merge validated systematic per-lens scrutiny findings (origin: scrutiny) grounded in raw input or local domain context; refreshes the knowledge ledger.", ["project_id", "source"]),
    ("assume", "Register governed BA-owned assumptions with risk, local cited basis, optional provisional gap link, and ledger refresh.", ["project_id", "source"]),
    ("compose", "Merge validated agent-authored PRD narrative blocks; every paragraph cites verbatim local source-of-truth evidence.", ["project_id", "source"]),
    ("refine_backlog", "Merge validated agent-authored backlog refinement proposals; every proposal cites verbatim local source-of-truth evidence.", ["project_id", "source"]),
    ("story_status", "Update a backlog story lifecycle status and owner through the governed state machine; optionally attach local acceptance evidence for Done.", ["project_id", "story", "status", "evidence"]),
    ("backlog_status", "Generate the BA-facing backlog board and rollup by epic/status.", ["project_id"]),
    ("implementation_feedback", "Merge structured downstream implementation feedback as traced backlog feedback without rewriting stories directly.", ["project_id", "source"]),
    ("self_review", "Merge skeptical PRD/spec self-review findings as cited gaps and hard-to-reverse decision records.", ["project_id", "source"]),
    ("export", "Export a governed artifact (gaps|brief|context-request|prd) to Markdown or MDX through the audited local export channel.", ["project_id", "artifact"]),
    ("gap_elicitation", "Return a structured MCP elicitation request for one GAP when the client declares elicitation support; otherwise fall back to sentinel_gaps.", ["project_id", "gap_id"]),
]

# Look up descriptions by tool name so tool registrations do not depend on the
# positional index of TOOL_SPECS (IMP-176 F4: inserting a tool used to silently
# shift every later `TOOL_SPECS[N][1]` reference).
TOOL_DESCRIPTIONS: dict[str, str] = {name: description for name, description, _ in TOOL_SPECS}


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


def client_supports_elicitation(capabilities: object) -> bool:
    if not capabilities:
        return False
    if isinstance(capabilities, str):
        try:
            capabilities = json.loads(capabilities)
        except json.JSONDecodeError:
            return False
    if isinstance(capabilities, list | tuple | set):
        return "elicitation" in capabilities
    if not isinstance(capabilities, dict):
        return False
    if capabilities.get("elicitation") is not None:
        return True
    nested = capabilities.get("capabilities")
    return isinstance(nested, dict) and nested.get("elicitation") is not None


def gap_elicitation(project_id: str, gap_id: str, client_capabilities: object | None = None) -> dict[str, object]:
    if not client_supports_elicitation(client_capabilities):
        return run_cli(["gaps", project_id])

    from .discovery import candidate_options_for_gap, expected_format_for_gap, parse_gap_rows, unblocks_for_gap
    from .workspace import load_config, workspace_path

    base = workspace_path(project_id)
    gaps_path = base / "01_discovery" / "gaps.md"
    if not gaps_path.exists():
        return {"exit_code": 1, "error": f"Gap artifact not found for project {project_id}; run sentinel_gaps first."}

    language = str(load_config(project_id).get("project_language", "es") or "es").lower()
    normalized_gap_id = str(gap_id or "").strip().upper()
    gap = next(
        (item for item in parse_gap_rows(gaps_path.read_text(encoding="utf-8")) if item.get("id") == normalized_gap_id),
        None,
    )
    if gap is None:
        return {"exit_code": 1, "error": f"Gap not found: {normalized_gap_id}"}

    options = candidate_options_for_gap(gap, language)
    properties = {
        "answer": {"type": "string"},
        "status": {"type": "string", "enum": ["confirmed", "not_applicable", "unknown"]},
        "evidence": {"type": "string"},
    }
    if options:
        properties["selected_option"] = {
            "type": "string",
            "enum": [option["label"] for option in options],
        }

    output = {
        "type": "mcp_elicitation_request",
        "spec": "2025-06-18",
        "project_id": project_id,
        "gap_id": normalized_gap_id,
        "question": gap.get("question", ""),
        "lens": gap.get("lens", ""),
        "severity": gap.get("severity", ""),
        "evidence": gap.get("evidence_mention", ""),
        "unblocks": unblocks_for_gap(normalized_gap_id, language),
        "expected_format": expected_format_for_gap(normalized_gap_id, language),
        "candidate_options": options,
        "schema": {
            "type": "object",
            "required": ["answer", "status", "evidence"],
            "properties": properties,
        },
    }
    return {"exit_code": 0, "output": output}


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

    @server.tool(name="sentinel_doctor", description=TOOL_DESCRIPTIONS["doctor"])
    def sentinel_doctor() -> dict:
        return run_cli(["doctor"])

    @server.tool(name="sentinel_dashboard", description=TOOL_DESCRIPTIONS["dashboard"])
    def sentinel_dashboard(open_browser: bool = False) -> dict:
        arguments = ["dashboard"]
        if open_browser:
            arguments.append("--open")
        return run_cli(arguments)

    @server.tool(name="sentinel_init", description=TOOL_DESCRIPTIONS["init"])
    def sentinel_init(project_id: str) -> dict:
        return run_cli(["init", project_id])

    @server.tool(name="sentinel_ingest", description=TOOL_DESCRIPTIONS["ingest"])
    def sentinel_ingest(project_id: str, source: str) -> dict:
        return run_cli(["ingest", project_id, "--source", source])

    @server.tool(name="sentinel_gaps", description=TOOL_DESCRIPTIONS["gaps"])
    def sentinel_gaps(project_id: str) -> dict:
        return run_cli(["gaps", project_id])

    @server.tool(name="sentinel_resolve_gaps", description=TOOL_DESCRIPTIONS["resolve_gaps"])
    def sentinel_resolve_gaps(project_id: str, source: str) -> dict:
        return run_cli(["resolve-gaps", project_id, "--source", source])

    @server.tool(name="sentinel_maturity", description=TOOL_DESCRIPTIONS["maturity"])
    def sentinel_maturity(project_id: str) -> dict:
        return run_cli(["maturity", project_id])

    @server.tool(name="sentinel_brief", description=TOOL_DESCRIPTIONS["brief"])
    def sentinel_brief(project_id: str) -> dict:
        return run_cli(["brief", project_id])

    @server.tool(name="sentinel_context_request", description=TOOL_DESCRIPTIONS["context_request"])
    def sentinel_context_request(project_id: str, domain: str) -> dict:
        return run_cli(["context-request", project_id, "--domain", domain])

    @server.tool(name="sentinel_status", description=TOOL_DESCRIPTIONS["status"])
    def sentinel_status(project_id: str) -> dict:
        return run_cli(["status", project_id])

    @server.tool(name="sentinel_sync", description=TOOL_DESCRIPTIONS["sync"])
    def sentinel_sync(project_id: str, source: str = "", note: str = "") -> dict:
        arguments = ["sync", project_id]
        if source:
            arguments += ["--source", source]
        if note:
            arguments += ["--note", note]
        return run_cli(arguments)

    @server.tool(name="sentinel_reindex", description=TOOL_DESCRIPTIONS["reindex"])
    def sentinel_reindex(project_id: str) -> dict:
        return run_cli(["reindex", project_id])

    @server.tool(name="sentinel_retrieve", description=TOOL_DESCRIPTIONS["retrieve"])
    def sentinel_retrieve(
        project_id: str,
        query: str = "",
        workflow: str = "discovery",
        order: str = "relevance",
        timeline: bool = False,
        write_pack: bool = False,
    ) -> dict:
        arguments = ["retrieve", project_id]
        if query:
            arguments += ["--query", query]
        if workflow:
            arguments += ["--workflow", workflow]
        if order and order != "relevance":
            arguments += ["--order", order]
        if timeline:
            arguments.append("--timeline")
        if write_pack:
            arguments.append("--write-pack")
        return run_cli(arguments)

    @server.tool(name="sentinel_specs", description=TOOL_DESCRIPTIONS["specs"])
    def sentinel_specs(project_id: str) -> dict:
        return run_cli(["specs", project_id])

    @server.tool(name="sentinel_backlog", description=TOOL_DESCRIPTIONS["backlog"])
    def sentinel_backlog(project_id: str, with_task_seeds: bool = False) -> dict:
        arguments = ["backlog", project_id]
        if with_task_seeds:
            arguments.append("--with-task-seeds")
        return run_cli(arguments)

    @server.tool(name="sentinel_quality", description=TOOL_DESCRIPTIONS["quality"])
    def sentinel_quality(project_id: str) -> dict:
        return run_cli(["quality", project_id])

    @server.tool(name="sentinel_trace", description=TOOL_DESCRIPTIONS["trace"])
    def sentinel_trace(project_id: str) -> dict:
        return run_cli(["trace", project_id])

    @server.tool(name="sentinel_health", description=TOOL_DESCRIPTIONS["health"])
    def sentinel_health(project_id: str) -> dict:
        return run_cli(["health", project_id])

    @server.tool(name="sentinel_validate", description=TOOL_DESCRIPTIONS["validate"])
    def sentinel_validate(project_id: str) -> dict:
        return run_cli(["validate", project_id])

    @server.tool(name="sentinel_view", description=TOOL_DESCRIPTIONS["view"])
    def sentinel_view(project_id: str, artifact: str, open_browser: bool = False) -> dict:
        arguments = ["view", project_id, "--artifact", artifact]
        if open_browser:
            arguments.append("--open")
        return run_cli(arguments)

    @server.tool(name="sentinel_annotate", description=TOOL_DESCRIPTIONS["annotate"])
    def sentinel_annotate(project_id: str, source: str) -> dict:
        return run_cli(["annotate", project_id, "--source", source])

    @server.tool(name="sentinel_challenge", description=TOOL_DESCRIPTIONS["challenge"])
    def sentinel_challenge(project_id: str, source: str) -> dict:
        return run_cli(["challenge", project_id, "--source", source])

    @server.tool(name="sentinel_scrutinize", description=TOOL_DESCRIPTIONS["scrutinize"])
    def sentinel_scrutinize(project_id: str, source: str, lens: str = "", mode: str = "") -> dict:
        arguments = ["scrutinize", project_id, "--source", source]
        if lens:
            arguments += ["--lens", lens]
        if mode:
            arguments += ["--mode", mode]
        return run_cli(arguments)

    @server.tool(name="sentinel_assume", description=TOOL_DESCRIPTIONS["assume"])
    def sentinel_assume(project_id: str, source: str) -> dict:
        return run_cli(["assume", project_id, "--source", source])

    @server.tool(name="sentinel_compose", description=TOOL_DESCRIPTIONS["compose"])
    def sentinel_compose(project_id: str, source: str) -> dict:
        return run_cli(["compose", project_id, "--source", source])

    @server.tool(name="sentinel_refine_backlog", description=TOOL_DESCRIPTIONS["refine_backlog"])
    def sentinel_refine_backlog(project_id: str, source: str) -> dict:
        return run_cli(["refine-backlog", project_id, "--source", source])

    @server.tool(name="sentinel_story_status", description=TOOL_DESCRIPTIONS["story_status"])
    def sentinel_story_status(project_id: str, story: str, status: str, owner: str = "", evidence: str = "") -> dict:
        arguments = ["story-status", project_id, "--story", story, "--set", status]
        if owner:
            arguments += ["--owner", owner]
        if evidence:
            arguments += ["--evidence", evidence]
        return run_cli(arguments)

    @server.tool(name="sentinel_backlog_status", description=TOOL_DESCRIPTIONS["backlog_status"])
    def sentinel_backlog_status(project_id: str) -> dict:
        return run_cli(["backlog-status", project_id])

    @server.tool(name="sentinel_implementation_feedback", description=TOOL_DESCRIPTIONS["implementation_feedback"])
    def sentinel_implementation_feedback(project_id: str, source: str) -> dict:
        return run_cli(["implementation-feedback", project_id, "--source", source])

    @server.tool(name="sentinel_self_review", description=TOOL_DESCRIPTIONS["self_review"])
    def sentinel_self_review(project_id: str, source: str) -> dict:
        return run_cli(["self-review", project_id, "--source", source])

    @server.tool(name="sentinel_export", description=TOOL_DESCRIPTIONS["export"])
    def sentinel_export(project_id: str, artifact: str, format: str = "md") -> dict:
        return run_cli(["export", project_id, "--artifact", artifact, "--format", format])

    @server.tool(name="sentinel_gap_elicitation", description=TOOL_DESCRIPTIONS["gap_elicitation"])
    def sentinel_gap_elicitation(project_id: str, gap_id: str, client_capabilities: str = "") -> dict:
        return gap_elicitation(project_id, gap_id, client_capabilities)

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
