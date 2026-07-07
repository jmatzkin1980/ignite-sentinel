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

# Governed artifacts: regenerated ONLY through their owning Sentinel command
# (invariant #1). A hand Write/Edit to one of these is denied at the tool boundary
# (IMP-179). This is the single source of truth for the protected set, shared by
# every surface's guard — the Codex hook (block), the Claude PreToolUse hook
# (deny), and the Kilo `file.deny` globs in kilo.jsonc.
GOVERNED_ARTIFACT_GLOBS = (
    "workspaces/*/02_requirements/project-brief.md",
    "workspaces/*/03_specs/*.md",
    "workspaces/*/04_backlog/*.md",
)
_GOVERNED_ARTIFACT = re.compile(
    r"(?:^|/)workspaces/[^/]+/(?:"
    r"02_requirements/project-brief\.md"
    r"|03_specs/[^/]+\.md"
    r"|04_backlog/[^/]+\.md"
    r")$"
)
# Tools that write files, across surfaces (Claude, Codex, Kilo editors). Read-type
# tools must never be denied, so the deny only fires for a known mutating tool;
# an unknown tool fails open (allow) — deterministic runtime guards (IMP-147) and
# the per-surface agent instructions remain the defense in depth.
_MUTATING_TOOLS = {
    "write",
    "edit",
    "multiedit",
    "notebookedit",
    "apply_patch",
    "applypatch",
    "str_replace",
    "str_replace_editor",
    "write_file",
    "edit_file",
    "create_file",
    "write_to_file",
    "apply_diff",
    "insert_content",
    "search_and_replace",
}
_GOVERNED_DENY_REASON = (
    "This is a governed Ignite Sentinel artifact; it is regenerated only through "
    "its owning command (/brief, /specs, /backlog) and never hand-edited. Edit the "
    "upstream evidence and re-run the command instead (invariant #1: mutate only "
    "via the CLI)."
)


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


def is_governed_artifact(path: str) -> bool:
    """True when the path is a governed artifact (brief/PRD-specs/backlog markdown)."""
    return bool(_GOVERNED_ARTIFACT.search(_normalize(path)))


def _is_mutating_tool(tool_name: str) -> bool:
    return str(tool_name or "").strip().lower() in _MUTATING_TOOLS


def governed_artifact_deny_reason(tool_name: str, path: str) -> str | None:
    """IMP-179: the deny reason when a mutating tool targets a governed artifact,
    or None to allow. Surface-neutral: each surface maps it to its own deny verb
    (Codex `block`, Claude `permissionDecision: deny`). Read-type tools and unknown
    tools are allowed (fail open) so legitimate reads and CLI regeneration proceed.
    """
    if not _is_mutating_tool(tool_name):
        return None
    if not is_governed_artifact(path):
        return None
    return _GOVERNED_DENY_REASON


def pre_tool_use_decision(tool_name: str, args, context=None) -> dict:
    """Codex pre-tool guardrail: block hand-edits to governed artifacts (IMP-179),
    otherwise a non-blocking local-first reminder. Blocking here targets only
    *illegitimate* mutation (a hand Write/Edit that bypasses the owning command);
    legitimate mutation flows through the CLI, which the hook never sees."""
    path = _path_arg(args)
    deny = governed_artifact_deny_reason(tool_name, path)
    if deny:
        return {"decision": "block", "reason": deny}
    warning = local_first_warning(path)
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
