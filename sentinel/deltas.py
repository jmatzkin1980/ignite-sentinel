"""Closed delta vocabulary shared by regeneration/spec/AC/requirement-unit reports.

IMP-187: every "what changed" report marks each affected section or unit with a
single closed enum — ``ADDED``, ``MODIFIED``, or ``REMOVED`` (plus ``UNCHANGED``
for full snapshots) — so a downstream coding agent can act on the delta without
diffing whole documents (OpenSpec-style). The enum is the only source of these
tokens, so an invalid marker is impossible by construction: ``delta_status``
raises on anything outside the closed set instead of emitting a stray label.
"""
from __future__ import annotations

from enum import Enum


class DeltaStatus(str, Enum):
    ADDED = "ADDED"
    MODIFIED = "MODIFIED"
    REMOVED = "REMOVED"
    UNCHANGED = "UNCHANGED"


# Surface-specific change vocabularies mapped onto the closed enum. This keeps
# each report's local nuance (e.g. the acceptance "added_after_freeze" review
# signal) while exposing one canonical marker a coding agent can filter on.
_ALIASES: dict[str, DeltaStatus] = {
    "added": DeltaStatus.ADDED,
    "added_after_freeze": DeltaStatus.ADDED,
    "modified": DeltaStatus.MODIFIED,
    "changed": DeltaStatus.MODIFIED,
    "removed": DeltaStatus.REMOVED,
    "unchanged": DeltaStatus.UNCHANGED,
}


def delta_status(value: "DeltaStatus | str") -> DeltaStatus:
    """Normalize a raw or surface-specific change label to a ``DeltaStatus``.

    Raises ``ValueError`` on anything outside the closed vocabulary — this is
    what makes an invalid delta marker impossible to render.
    """
    if isinstance(value, DeltaStatus):
        return value
    key = str(value).strip().lower()
    try:
        return _ALIASES[key]
    except KeyError as exc:
        raise ValueError(
            f"Unknown delta status {value!r}; expected one of "
            f"{[m.value for m in DeltaStatus]} or a known alias {sorted(_ALIASES)}."
        ) from exc


def delta_marker(value: "DeltaStatus | str") -> str:
    """Canonical uppercase token for a report cell (``ADDED``/``MODIFIED``/``REMOVED``/``UNCHANGED``)."""
    return delta_status(value).value


DELTA_LEGEND = (
    "Delta markers use the closed vocabulary `ADDED` | `MODIFIED` | `REMOVED` "
    "(IMP-187) so a downstream agent can act on each change without diffing whole documents."
)
