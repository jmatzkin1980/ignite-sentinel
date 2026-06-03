"""Optional Ignite Sentinel pre-tool guardrail.

This hook is intentionally conservative: deterministic CLI validation remains
the enforcement layer. Use it as a repo-local reminder when wiring Codex hooks.
"""

from __future__ import annotations

BLOCKED_PATH_PARTS = (".roo/", "04_temp/")


def pre_tool_use(tool_name: str, args: dict, context: dict | None = None) -> dict:
    path = str(args.get("path", "") if isinstance(args, dict) else "")
    for blocked in BLOCKED_PATH_PARTS:
        if blocked in path.replace("\\", "/"):
            return {
                "decision": "block",
                "reason": f"Ignite Sentinel vNext does not use deprecated path segment: {blocked}",
            }
    return {"decision": "allow", "reason": "No Sentinel guardrail violation detected."}
