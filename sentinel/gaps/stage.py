"""Readiness stage after a change in the gap counts."""
from __future__ import annotations

from ..workspace import read_state


def readiness_stage_for_counts(counts: dict[str, int]) -> str:
    if counts.get("blocking_open", 0):
        return "CLIENT_RESPONSE_NEEDED"
    if counts.get("open", 0) or counts.get("partially_closed", 0) or counts.get("answered", 0):
        return "DOMAIN_RESPONSE_NEEDED"
    return "READY_FOR_PROJECT_BRIEF"


# IMP-292: stages that only /brief, /specs or /backlog move past. Rewriting gaps
# must not drop a project out of them unless a blocking gap is now open.
POST_BRIEF_STAGES = frozenset({
    "READY_FOR_SPECS",
    "SPECS_BELOW_THRESHOLD",
    "READY_FOR_BACKLOG",
    "BRIEF_BELOW_THRESHOLD",
    "SELF_CORRECTION_FAILED",
    "UNITS_NOT_IMPLEMENTABLE",
})


def next_readiness_stage(current: object, counts: dict[str, int]) -> str:
    """Stage after a command rewrote gaps.md: back only when something blocks."""
    if counts.get("blocking_open", 0):
        return "CLIENT_RESPONSE_NEEDED"
    if current in POST_BRIEF_STAGES:
        return str(current)
    return readiness_stage_for_counts(counts)


def readiness_stage_after_gap_change(project_id: str, counts: dict[str, int]) -> str:
    return next_readiness_stage(read_state(project_id, {}).get("readiness_stage"), counts)
