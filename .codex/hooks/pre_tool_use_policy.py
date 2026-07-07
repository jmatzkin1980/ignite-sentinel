"""Optional Ignite Sentinel pre-tool guardrail (Codex surface).

Thin shim over ``sentinel.hooks_logic``. Two responsibilities:
- IMP-179: BLOCK a hand Write/Edit to a governed artifact (project-brief.md,
  03_specs/*.md, 04_backlog/*.md) — the deterministic policy that mirrors the
  Claude PreToolUse deny and the Kilo ``file.deny`` globs, so every surface
  enforces invariant #1 (mutate only via the owning CLI command). It blocks only
  illegitimate hand-edits; legitimate mutation flows through the CLI.
- IMP-172: otherwise SIGNAL a non-blocking local-first reminder.

If the shared logic cannot be imported it fails open (allow); the runtime
checksum guard (IMP-147) and the agent instructions remain the defense in depth.
"""

from __future__ import annotations

import sys
from pathlib import Path


def pre_tool_use(tool_name: str, args: dict, context: dict | None = None) -> dict:
    logic = _load_logic()
    if logic is None:
        return {"decision": "allow", "reason": "Sentinel guardrail unavailable."}
    return logic.pre_tool_use_decision(tool_name, args, context)


def _load_logic():
    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    try:
        from sentinel import hooks_logic
    except ImportError:
        return None
    return hooks_logic
