"""Optional Ignite Sentinel post-tool audit helper."""

from __future__ import annotations


def post_tool_use(tool_name: str, args: dict, context: dict | None = None) -> dict:
    return {
        "decision": "allow",
        "reason": "Run `python -m sentinel /validate PROJECT_ID` and `python -m sentinel /health PROJECT_ID` after Sentinel artifact changes.",
    }
