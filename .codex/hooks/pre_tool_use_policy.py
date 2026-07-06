"""Optional Ignite Sentinel pre-tool guardrail (Codex surface).

Thin shim over ``sentinel.hooks_logic`` (IMP-172). Intentionally conservative:
it SIGNALS a non-blocking local-first reminder and never blocks a mutation —
deterministic CLI validation plus ``/health`` remain the enforcement layer. The
governed-artifact deny for Claude Code arrives as a separate hook in IMP-179.
If the shared logic cannot be imported it fails open (allow).
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
