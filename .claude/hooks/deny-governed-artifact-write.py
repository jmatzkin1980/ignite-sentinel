#!/usr/bin/env python3
"""Claude Code PreToolUse hook (IMP-179): deny hand Write/Edit of governed artifacts.

Deterministic, stdlib-only, <100ms. Reads the PreToolUse JSON on stdin, and if a
mutating tool targets a governed Ignite Sentinel artifact (project-brief.md,
03_specs/*.md, 04_backlog/*.md) it denies the tool call and points at the owning
command. This is tier 1 of the defense stack: it works in any Claude Code version
(command hook, no Agent-hook support required), complementing the deep, opt-in
`ignite-verifier` (tier 3, PostToolUse). The decision logic is shared with the
Codex hook and the Kilo `file.deny` globs via sentinel.hooks_logic.

Wire it (versioned default policy) in .claude/settings.json under
PreToolUse -> matcher "Write|Edit". Fails open (allows) if anything goes wrong —
a guard must never break a legitimate session; the runtime checksum guard
(IMP-147) is the deterministic backstop.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def _load_logic():
    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    try:
        from sentinel import hooks_logic
    except ImportError:
        return None
    return hooks_logic


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (ValueError, OSError):
        return 0  # fail open: no parseable input, do not block

    tool_name = str(payload.get("tool_name", ""))
    tool_input = payload.get("tool_input") or {}
    path = ""
    if isinstance(tool_input, dict):
        path = str(tool_input.get("file_path") or tool_input.get("path") or "")

    logic = _load_logic()
    if logic is None:
        return 0  # fail open: shared logic unavailable

    reason = logic.governed_artifact_deny_reason(tool_name, path)
    if not reason:
        return 0  # allow

    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": reason,
                }
            }
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
