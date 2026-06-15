from __future__ import annotations

from pathlib import Path
from typing import Any

from .backlog_hooks import assert_backlog_privacy_clean
from .traceability import load_graph, write_mermaid_graph, write_traceability_matrix
from .workspace import read_json, state_path, update_state, utc_now, workspace_path

READ_ONLY_COMMANDS = {"retrieve", "maturity", "health", "trace", "validate", "status"}
MUTATING_COMMANDS = {
    "ingest",
    "sync",
    "specs",
    "backlog",
    "backlog-status",
    "quality",
    "reindex",
    "gaps",
    "annotate",
    "challenge",
    "scrutinize",
    "assume",
    "compose",
    "refine-backlog",
    "implementation-feedback",
    "story-status",
    "brief",
    "resolve-gaps",
    "context-request",
    "export",
}
PROJECT_COMMANDS = READ_ONLY_COMMANDS | MUTATING_COMMANDS


def preflight_command(command: str, project_id: str | None) -> None:
    if command not in PROJECT_COMMANDS:
        return
    if not project_id:
        raise RuntimeError(f"{command} requires PROJECT_ID.")

    base = workspace_path(project_id)
    if not base.exists():
        raise RuntimeError(f"Workspace not found: {project_id}. Run /init {project_id} first.")

    state = read_json(state_path(project_id), {})
    health = str(state.get("health", "UNKNOWN")).upper()
    phase = str(state.get("phase", "unknown"))

    if command in {"specs", "backlog"} and phase == "initialized":
        raise RuntimeError("Cannot generate downstream artifacts before /ingest creates discovery artifacts.")

    if command in {"backlog", "quality", "refine-backlog"} and health == "DIRTY":
        raise RuntimeError(f"Cannot run /{command} while project health is DIRTY. Run /maturity, /sync, or /health to inspect blockers.")

    if command in {"backlog", "backlog-status", "quality", "refine-backlog", "implementation-feedback", "story-status"}:
        assert_backlog_privacy_clean(project_id)

    if command == "quality" and not any(node.get("type") == "user_story" for node in load_graph(project_id).get("nodes", [])):
        raise RuntimeError("Cannot generate quality artifacts without backlog user stories.")


def postflight_command(command: str, project_id: str | None, result: Any) -> None:
    if command not in PROJECT_COMMANDS or not project_id:
        return

    if command in MUTATING_COMMANDS | {"trace"}:
        write_traceability_matrix(project_id)
        write_mermaid_graph(project_id)

    state = read_json(state_path(project_id), {})
    command_log = list(state.get("command_log", []))
    entry = {
        "timestamp": utc_now(),
        "command": command,
        "phase": state.get("phase", "unknown"),
        "health": state.get("health", "UNKNOWN"),
        "summary": summarize_result(result),
    }
    command_log.append(entry)
    update_state(
        project_id,
        last_command=command,
        last_command_at=entry["timestamp"],
        command_log=command_log[-25:],
    )
    write_command_protocol_log(project_id, command_log[-25:])


def summarize_result(result: Any) -> str:
    if isinstance(result, dict):
        keys = ("readiness", "verdict", "change_id", "spec_id", "story_id", "count", "processed", "detected")
        parts = [f"{key}={result[key]}" for key in keys if key in result]
        if parts:
            return "; ".join(parts)
        if "changes" in result and isinstance(result["changes"], list):
            return f"changes={len(result['changes'])}"
    return "completed"


def write_command_protocol_log(project_id: str, command_log: list[dict[str, Any]]) -> Path:
    path = workspace_path(project_id) / "06_traceability" / "command_protocol_log.md"
    rows = "\n".join(
        f"| {entry.get('timestamp', '')} | `{entry.get('command', '')}` | {entry.get('phase', '')} | {entry.get('health', '')} | {entry.get('summary', '')} |"
        for entry in command_log
    )
    if not rows:
        rows = "| N/A | N/A | N/A | N/A | N/A |"
    path.write_text(
        f"""# Command Protocol Log - {project_id}

This log records Sentinel vNext command anchors. It is the repo-local replacement for Roo command sync anchors.

| Timestamp | Command | Phase | Health | Summary |
| --- | --- | --- | --- | --- |
{rows}
""",
        encoding="utf-8",
    )
    return path
