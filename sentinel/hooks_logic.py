"""Shared, stdlib-pure decision logic for Ignite Sentinel tool-use hooks.

Per-surface entrypoints — the Codex hooks in ``.codex/hooks/`` today, a Claude
Code hook in ``.claude/hooks/`` from IMP-179 — are thin shims over these
functions, so the signalling logic lives in one tested place instead of being
copy-pasted (and drifting) per surface (doc 37 §3 IMP-172; doc 38 §6.1 E1).

Hooks *signal*: they return non-blocking reminders and never mutate governed
state or memory. Deterministic CLI validation plus ``/health`` remain the
enforcement layer (AGENTS.md; doc 37 §2 discards active blocking/mutation in
hooks). This module therefore performs pure, fast path inspection only.
"""

from __future__ import annotations

import re

# Workspace layout folders are named ``NN_something`` (``01_discovery``,
# ``02_requirements``, ``07_changes``, ...). A file carrying such a segment but
# living outside ``workspaces/`` is workspace content in the wrong place. This
# structural signature is repo-rename-proof, unlike the old hard-coded
# ``ignite-sentinel/`` substring that silently died on the -vnext rename (A3).
_WORKSPACE_LAYOUT_SEGMENT = re.compile(r"(?:^|/)\d{2}_[^/]+/")
_DATA_SUFFIXES = (".md", ".txt", ".json")
_LANGUAGE_SENSITIVE_SEGMENTS = ("/01_discovery/", "/02_requirements/", "/07_changes/")


def _normalize(path: str) -> str:
    return path.replace("\\", "/")


def _path_arg(args) -> str:
    if not isinstance(args, dict):
        return ""
    return str(args.get("path", "") or "")


def _under_local_root(normalized: str) -> bool:
    return (
        "/workspaces/" in normalized
        or normalized.startswith("workspaces/")
        or "/input/" in normalized
        or normalized.startswith("input/")
    )


def local_first_warning(path: str) -> str | None:
    """Non-blocking reminder when a file looks like workspace content but sits
    outside the governed ``workspaces/`` tree (or the ``input/`` staging area).

    Anchored to the ``NN_`` workspace-layout signature rather than a repo name,
    so it survives repo renames and does not false-fire on the framework's own
    versioned docs/code.
    """
    normalized = _normalize(path)
    if not normalized.endswith(_DATA_SUFFIXES):
        return None
    if _under_local_root(normalized):
        return None
    if not _WORKSPACE_LAYOUT_SEGMENT.search(normalized):
        return None
    return (
        "this looks like workspace content (an `NN_` layout folder) outside "
        "`workspaces/`; client/project artifacts must stay under "
        "`workspaces/PROJECT_ID/` (local-first)"
    )


def audit_warnings(path: str) -> list[str]:
    """Post-write reminders for a touched path. Never blocks; never mutates."""
    normalized = _normalize(path)
    warnings: list[str] = []
    under_workspace = "/workspaces/" in normalized or normalized.startswith("workspaces/")
    if under_workspace and normalized.endswith((".md", ".txt")):
        # A1: governed mutation, not hand-editing. /reindex is for sources only.
        warnings.append(
            "governed artifacts are regenerated only through their owning Sentinel "
            "command; edits made outside the CLI are flagged by `/health` (IMP-147); "
            "`/reindex` covers changed sources, not artifact regeneration"
        )
    misplaced = local_first_warning(path)
    if misplaced:
        warnings.append(misplaced)
    if any(segment in normalized for segment in _LANGUAGE_SENSITIVE_SEGMENTS):
        warnings.append("ensure human-facing artifact language matches `project_language`")
    return warnings


def pre_tool_use_decision(tool_name: str, args, context=None) -> dict:
    """Codex pre-tool guardrail: a non-blocking local-first reminder."""
    warning = local_first_warning(_path_arg(args))
    if warning:
        return {
            "decision": "allow",
            "reason": f"Warning: {warning}; continuing (non-blocking local-first guardrail).",
        }
    return {"decision": "allow", "reason": "No Sentinel guardrail violation detected."}


def post_tool_use_decision(tool_name: str, args, context=None) -> dict:
    """Codex post-tool audit: reminders to re-validate, never a mutation."""
    reason = (
        "Run `python -m sentinel /validate PROJECT_ID` and "
        "`python -m sentinel /health PROJECT_ID` after Sentinel artifact changes."
    )
    warnings = audit_warnings(_path_arg(args))
    if warnings:
        reason += " Warnings: " + "; ".join(warnings)
    return {"decision": "allow", "reason": reason}
