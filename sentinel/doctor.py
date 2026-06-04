from __future__ import annotations

import importlib.util
import os
import platform
import sys
from pathlib import Path
from typing import Any


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
    "resolve-gaps",
    "brief",
    "context-request",
    "status",
    "export",
]


def run_doctor(root: Path | None = None) -> dict[str, Any]:
    root = (root or Path.cwd()).resolve()
    checks = [
        python_check(),
        path_check(root, "sentinel", "core runtime"),
        path_check(root, ".codex/skills", "Codex skills adapter"),
        path_check(root, ".kilo/agents", "Kilo Code agents adapter"),
        path_check(root, ".kilo/commands", "Kilo Code slash commands"),
        path_check(root, "kilo.jsonc", "Kilo Code repo config"),
        path_check(root, "user_guide", "user guide"),
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
        required_dependency_check("lancedb"),
        optional_dependency_check("sentence_transformers"),
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
    return {
        "name": f"optional dependency: {module_name}",
        "status": "PASS" if found else "WARN",
        "detail": "available" if found else "not installed; JSON fallback remains usable",
    }


def required_dependency_check(module_name: str) -> dict[str, str]:
    found = importlib.util.find_spec(module_name) is not None
    return {
        "name": f"required dependency: {module_name}",
        "status": "PASS" if found else "FAIL",
        "detail": "available" if found else "not installed",
    }
