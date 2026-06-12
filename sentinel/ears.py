"""EARS requirement normalization (IMP-026).

EARS (Easy Approach to Requirements Syntax) turns prose into testable,
agent-parseable statements in five canonical patterns:

- ubiquitous:      "The <system> shall <response>."
- event-driven:    "When <trigger>, the <system> shall <response>."
- state-driven:    "While <state>, the <system> shall <response>."
- unwanted:        "If <condition>, then the <system> shall <response>."
- optional:        "Where <feature>, the <system> shall <response>."

The runtime never invents EARS: an agent proposes a normalized statement (e.g.
as the substantive answer to a functional gap) and this module validates the
structure. Statements that do not match a pattern stay as prose (invariant #3:
evidence or silence — only confirmed, well-formed statements are normalized).

English and Spanish keyword variants are accepted (When/Cuando, While/Mientras,
If…then/Si…entonces, Where/Donde, shall/must/should/debe…).
"""
from __future__ import annotations

import re

_SHALL = r"(?:shall|will|must|should|debe\w*)"

# Order matters: the conditional patterns are checked before the ubiquitous one.
EARS_PATTERNS: dict[str, re.Pattern[str]] = {
    "event": re.compile(rf"^(?:when|cuando)\s+.+\s+{_SHALL}\s+.+", re.I),
    "state": re.compile(rf"^(?:while|mientras)\s+.+\s+{_SHALL}\s+.+", re.I),
    "unwanted": re.compile(rf"^(?:if|si)\s+.+?(?:\s+(?:then|entonces))?\s+.*{_SHALL}\s+.+", re.I),
    "optional": re.compile(rf"^(?:where|donde)\s+.+\s+{_SHALL}\s+.+", re.I),
    "ubiquitous": re.compile(rf"^(?:the|el|la|los|las)\s+.+\s+{_SHALL}\s+.+", re.I),
}

_PATTERN_ORDER = ("event", "state", "unwanted", "optional", "ubiquitous")


def classify_ears(text: str) -> str | None:
    """Return the EARS pattern name a statement matches, or None if it is not EARS."""
    normalized = " ".join(str(text).strip().split())
    if not normalized:
        return None
    for name in _PATTERN_ORDER:
        if EARS_PATTERNS[name].match(normalized):
            return name
    return None


def is_ears(text: str) -> bool:
    return classify_ears(text) is not None
