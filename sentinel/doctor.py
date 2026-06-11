from __future__ import annotations

import importlib.util
import importlib.metadata
import os
import platform
import sys
import tempfile
from pathlib import Path
from typing import Any

from .adapters import manifest_command_names


REQUIRED_COMMANDS = [
    "doctor",
    "init",
    "ingest",
    "retrieve",
    "sync",
    "maturity",
    "specs",
    "backlog",
    "quality",
    "health",
    "trace",
    "validate",
    "reindex",
    "gaps",
    "annotate",
    "resolve-gaps",
    "brief",
    "context-request",
    "status",
    "export",
]

REQUIRED_CODEX_SKILLS = [
    "sentinel-annotate",
    "sentinel-backlog",
    "sentinel-command-router",
    "sentinel-discovery",
    "sentinel-domain-request",
    "sentinel-gap-response",
    "sentinel-health",
    "sentinel-maturity",
    "sentinel-privacy-local-first",
    "sentinel-project-brief",
    "sentinel-quality",
    "sentinel-specs",
    "sentinel-sync",
]

REQUIRED_CLAUDE_COMMANDS = manifest_command_names()

REQUIRED_KILO_COMMANDS = manifest_command_names()


def run_doctor(root: Path | None = None) -> dict[str, Any]:
    root = (root or Path.cwd()).resolve()
    checks = [
        python_check(),
        path_check(root, "sentinel", "core runtime"),
        path_check(root, "AGENTS.md", "Codex Desktop and agent instructions"),
        path_check(root, "README.md", "repository quick start"),
        path_check(root, ".codex/skills", "Codex skills adapter (canonical)"),
        path_check(root, ".agents/skills", "Agent Skills standard directory"),
        path_check(root, ".claude/skills", "Claude Code skills directory"),
        path_check(root, ".codex/hooks", "Codex hooks adapter"),
        path_check(root, ".kilo/agents", "Kilo Code agents adapter"),
        path_check(root, ".kilo/commands", "Kilo Code slash commands"),
        path_check(root, "kilo.jsonc", "Kilo Code repo config"),
        path_check(root, "CLAUDE.md", "Claude Code and Claude Desktop instructions"),
        path_check(root, "sentinel/templates/commands_manifest.json", "command adapter manifest"),
        path_check(root, ".claude/commands", "Claude Code slash commands"),
        path_check(root, "user_guide", "user guide"),
        path_check(root, "user_guide/06-installation-vscode.md", "VS Code portable installation guide"),
        path_check(root, "user_guide/07-kilo-code-adapter.md", "Kilo Code adapter guide"),
        path_check(root, "user_guide/08-codex-adapter.md", "Codex adapter guide"),
        path_check(root, "user_guide/13-claude-adapter.md", "Claude adapter guide"),
        path_check(root, "installers/install.ps1", "Windows portable installer"),
        path_check(root, "installers/install.sh", "Unix portable installer"),
        path_check(root, "installers/sentinel.ps1", "Windows portable Sentinel launcher"),
        path_check(root, "installers/sentinel.sh", "Unix portable Sentinel launcher"),
        path_check(root, "input", "input folder scaffold"),
        path_check(root, "input/client_requirement", "input client requirement scaffold"),
        path_check(root, "input/technology_context", "input technology context scaffold"),
        path_check(root, "input/design_context", "input design context scaffold"),
        path_check(root, "input/interactions", "input interactions scaffold"),
        path_check(root, "workspaces/_template", "workspace template scaffold"),
        path_check(root, "workspaces/_template/00_raw/00_client_requirement", "workspace client requirement template"),
        path_check(root, "workspaces/_template/00_raw/02_technology_context", "workspace technology context template"),
        path_check(root, "workspaces/_template/00_raw/03_design_context", "workspace design context template"),
        path_check(root, "workspaces/_template/07_changes/03_domain_updates", "workspace domain updates template"),
        write_check(root),
        *codex_skill_checks(root),
        *kilo_command_checks(root),
        *claude_command_checks(root),
        memory_dependency_check(),
        lancedb_smoke_check(),
        optional_dependency_check("sentence_transformers"),
        mcp_dependency_check(),
    ]
    blocking = [check for check in checks if check["status"] == "FAIL"]
    warnings = [check for check in checks if check["status"] == "WARN"]
    return {
        "verdict": "PASS" if not blocking else "FAIL",
        "root": str(root),
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "python": sys.version.split()[0],
            "executable": sys.executable,
        },
        "commands": REQUIRED_COMMANDS,
        "checks": checks,
        "summary": {
            "failures": len(blocking),
            "warnings": len(warnings),
        },
    }


def python_check() -> dict[str, str]:
    if sys.version_info >= (3, 10):
        return {"name": "python>=3.10", "status": "PASS", "detail": sys.version.split()[0]}
    return {"name": "python>=3.10", "status": "FAIL", "detail": sys.version.split()[0]}


def path_check(root: Path, relative: str, label: str) -> dict[str, str]:
    path = root / relative
    return {
        "name": label,
        "status": "PASS" if path.exists() else "FAIL",
        "detail": str(path),
    }


def write_check(root: Path) -> dict[str, str]:
    probe = root / ".sentinel_doctor_write_test"
    try:
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        return {"name": "repo write access", "status": "PASS", "detail": str(root)}
    except OSError as exc:
        return {"name": "repo write access", "status": "FAIL", "detail": str(exc)}


def optional_dependency_check(module_name: str) -> dict[str, str]:
    found = importlib.util.find_spec(module_name) is not None
    detail = package_detail(module_name) if found else "not installed; JSON fallback remains usable"
    return {
        "name": f"optional dependency: {module_name}",
        "status": "PASS" if found else "WARN",
        "detail": detail,
    }


def codex_skill_checks(root: Path) -> list[dict[str, str]]:
    return [
        path_check(root, f".codex/skills/{skill}/SKILL.md", f"Codex skill: {skill}")
        for skill in REQUIRED_CODEX_SKILLS
    ]


def kilo_command_checks(root: Path) -> list[dict[str, str]]:
    return [
        path_check(root, f".kilo/commands/{command}.md", f"Kilo slash command: /{command}")
        for command in REQUIRED_KILO_COMMANDS
    ]


def claude_command_checks(root: Path) -> list[dict[str, str]]:
    return [
        path_check(root, f".claude/commands/{command}.md", f"Claude slash command: /{command}")
        for command in REQUIRED_CLAUDE_COMMANDS
    ]


def mcp_dependency_check() -> dict[str, str]:
    found = importlib.util.find_spec("mcp") is not None
    if found:
        detail = package_detail("mcp") + "; expose the lifecycle to MCP clients with `python -m sentinel.mcp`"
    else:
        detail = (
            "not installed; chat adapters and CLI remain fully functional. "
            "Enable the local stdio MCP server with `python -m pip install -e .[mcp]`."
        )
    return {
        "name": "optional dependency: mcp (local stdio server)",
        "status": "PASS" if found else "WARN",
        "detail": detail,
    }


def memory_dependency_check() -> dict[str, str]:
    found = importlib.util.find_spec("lancedb") is not None
    if found:
        detail = package_detail("lancedb")
    else:
        detail = (
            "not installed; deterministic JSON memory fallback is active. "
            "Vector retrieval is degraded but the full lifecycle works. "
            "Enable with `python -m pip install -e .[memory]` when the environment allows it."
        )
    return {
        "name": "memory dependency: lancedb (optional)",
        "status": "PASS" if found else "WARN",
        "detail": detail,
    }


def lancedb_smoke_check() -> dict[str, str]:
    if importlib.util.find_spec("lancedb") is None:
        return {
            "name": "LanceDB local open/create",
            "status": "WARN",
            "detail": "lancedb is not installed; ContextBroker runs in deterministic json-hybrid mode",
        }
    try:
        import lancedb  # type: ignore

        with tempfile.TemporaryDirectory(prefix="sentinel_lancedb_doctor_") as temp_dir:
            db = lancedb.connect(temp_dir)
            db.create_table(
                "doctor_probe",
                data=[
                    {
                        "id": "probe",
                        "text": "local LanceDB probe",
                        "vector": [0.0, 1.0],
                    }
                ],
                mode="overwrite",
            )
        return {
            "name": "LanceDB local open/create",
            "status": "PASS",
            "detail": "local table probe succeeded",
        }
    except Exception as exc:
        return {
            "name": "LanceDB local open/create",
            "status": "FAIL",
            "detail": str(exc),
        }


def package_detail(module_name: str) -> str:
    try:
        version = importlib.metadata.version(module_name.replace("_", "-"))
        return f"available ({version})"
    except importlib.metadata.PackageNotFoundError:
        return "available"
