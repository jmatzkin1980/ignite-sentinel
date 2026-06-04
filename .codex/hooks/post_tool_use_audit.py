"""Optional Ignite Sentinel post-tool audit helper."""

from __future__ import annotations

import sys
from pathlib import Path


def post_tool_use(tool_name: str, args: dict, context: dict | None = None) -> dict:
    indexed = index_workspace_artifact(args)
    warnings = audit_warnings(args)
    suffix = f" Indexed `{indexed}` in Sentinel memory." if indexed else ""
    warning_text = f" Warnings: {'; '.join(warnings)}" if warnings else ""
    return {
        "decision": "allow",
        "reason": "Run `python -m sentinel /validate PROJECT_ID` and `python -m sentinel /health PROJECT_ID` after Sentinel artifact changes."
        + suffix
        + warning_text,
    }


def audit_warnings(args: dict) -> list[str]:
    path_value = str(args.get("path", "") if isinstance(args, dict) else "")
    if not path_value:
        return []
    normalized = path_value.replace("\\", "/")
    warnings: list[str] = []
    if normalized.endswith((".md", ".txt")) and "/workspaces/" in normalized:
        warnings.append("run `/reindex PROJECT_ID` after manual artifact edits")
    if "/workspaces/" not in normalized and "/input/" not in normalized and normalized.endswith((".md", ".txt", ".json")):
        warnings.append("project/client data should stay under `workspaces/PROJECT_ID/` or `input/`")
    if any(segment in normalized for segment in ("/01_discovery/", "/02_requirements/", "/07_changes/")):
        warnings.append("ensure human-facing artifact language matches `project_language`")
    return warnings


def index_workspace_artifact(args: dict) -> str | None:
    path_value = str(args.get("path", "") if isinstance(args, dict) else "")
    if not path_value:
        return None
    path = Path(path_value)
    if not path.exists() or path.suffix.lower() not in {".md", ".txt"}:
        return None
    parts = path.parts
    if "workspaces" not in parts:
        return None
    workspace_index = parts.index("workspaces")
    if len(parts) <= workspace_index + 1:
        return None
    project_id = parts[workspace_index + 1]
    if project_id == "_template":
        return None

    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    try:
        from sentinel.memory import ContextBroker, context_artifact_id

        artifact_id = context_artifact_id(project_id, path)
        artifact_type, domain = classify_path(path)
        ContextBroker(project_id).index_artifact(
            artifact_id,
            artifact_type,
            path,
            path.read_text(encoding="utf-8"),
            domain=domain,
            trace_ids=[artifact_id],
        )
        return artifact_id
    except Exception:
        return None


def classify_path(path: Path) -> tuple[str, str]:
    normalized = path.as_posix()
    if "/02_technology_context/" in normalized:
        return "technology_context", "technical"
    if "/03_design_context/" in normalized:
        return "design_context", "design"
    if "/04_quality_context/" in normalized or "/05_quality/" in normalized:
        return "quality_context", "quality"
    if "/01_business_context/" in normalized:
        return "business_context", "business"
    if "/07_changes/" in normalized:
        return "change_context", "product"
    if "/01_discovery/" in normalized:
        return "discovery_artifact", "product"
    return "workspace_artifact", "product"
