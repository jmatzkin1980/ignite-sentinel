"""Optional Ignite Sentinel post-tool audit reminder (Codex surface).

Thin shim over ``sentinel.hooks_logic`` (IMP-172): the decision logic is shared
and tested there. This hook only SIGNALS — it never indexes memory or mutates
state (the former side-channel indexer was removed; ``/sync`` autonomous
detection and ``/reindex`` are the governed channels). If the shared logic
cannot be imported it fails open (allow), because a non-authoritative reminder
must never block legitimate work.
"""

from __future__ import annotations

import sys
from pathlib import Path


def post_tool_use(tool_name: str, args: dict, context: dict | None = None) -> dict:
    logic = _load_logic()
    if logic is None:
        return {"decision": "allow", "reason": "Sentinel audit reminder unavailable."}
    return logic.post_tool_use_decision(tool_name, args, context)


def _load_logic():
    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    try:
        from sentinel import hooks_logic
    except ImportError:
        return None
    return hooks_logic
