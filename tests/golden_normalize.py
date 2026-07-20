"""IMP-219 (H11, F-GOLD-4/5): shared, conservative normalization harness for
golden/snapshot tests.

It normalizes ONLY known-volatile tokens to stable placeholders so a snapshot is
byte-identical across runs and machines:

  - the project id            -> [PROJECT_ID]
  - absolute workspace paths  -> collapsed to workspaces/[PROJECT_ID]
  - ISO timestamps            -> [TIMESTAMP]
  - bare dates                -> [DATE]
  - sha256 hashes (64 hex)    -> [SHA256]

Conservative by design: it never masks real content. A dropped section, a changed
heading, or a reordered list MUST still break the golden — only the machine-specific
volatile tokens above are collapsed. This extends the path/timestamp normalization
IMP-215 used inline for the trace-matrix golden; sha256 handling is new for the mdx
export (`source_sha256`), whose value changes with any timestamped source content,
and the abs-path collapse now also fires inside JSON strings (the `/view` HTML embeds
its model as a JSON blob) without eating the surrounding quote.
"""

from __future__ import annotations

import re

# Order matters: timestamp before date (a full ISO timestamp starts with a date),
# sha256 is dash-free so it never collides with the date pattern.
_WORKSPACE_PREFIX_RE = re.compile(r'[^`"\s]*/workspaces/\[PROJECT_ID\]')
_ISO_TIMESTAMP_RE = re.compile(
    r"\d{4}-\d\d-\d\d[T ]\d\d:\d\d:\d\d(?:\.\d+)?(?:[+-]\d\d:?\d\d|Z)?"
)
_SHA256_RE = re.compile(r"\b[0-9a-f]{64}\b")
_DATE_RE = re.compile(r"\d{4}-\d\d-\d\d")


def normalize(text: str, project_id: str) -> str:
    """Collapse known-volatile tokens in ``text`` to stable placeholders.

    ``project_id`` is the concrete workspace id used by the fixture; it is
    replaced first so the workspace-path collapse can match the placeholder form.
    """
    text = text.replace(project_id, "[PROJECT_ID]")
    # Collapse the machine-specific absolute prefix in front of the workspace
    # root, whether the path sits in a markdown backtick cell or a JSON string.
    # The negated class excludes backtick and double-quote so a table cell or a
    # JSON key/value boundary survives (only the volatile prefix is eaten).
    text = _WORKSPACE_PREFIX_RE.sub("workspaces/[PROJECT_ID]", text)
    text = _ISO_TIMESTAMP_RE.sub("[TIMESTAMP]", text)
    text = _SHA256_RE.sub("[SHA256]", text)
    text = _DATE_RE.sub("[DATE]", text)
    return text
