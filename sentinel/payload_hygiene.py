"""IMP-342: secret and injection hygiene for agent and BA payloads.

`/self-review`, the gate overrides (`/quality`, `/validate`, `/backlog` with an
override source), `/compose`, `/implementation-feedback`, `/assume` and
`/refine-backlog` take a JSON payload, archive it in the workspace and write its
text into artifacts. They get the same treatment as client sources (IMP-285,
IMP-286, IMP-336):

- **Archived copy** (`archive_payload`): secrets are redacted with the `/ingest`
  sanitizer and each one is logged in `01_discovery/secret_alerts.md`; injection-shaped
  lines stay verbatim, like the `00_raw/` copy, and are listed in
  `01_discovery/injection_signals.md` for the BA.
- **What is stored or rendered** (`sanitize_payload`): every string of the accepted
  items is redacted and every injection-shaped line becomes `<NEUTRALIZADO:type>`.

Validation always runs first, on the payload as written, so a verbatim quote is
checked against the evidence exactly as the agent cited it; only the copy that is
written is sanitized. A field that is re-checked verbatim later (the `/compose`
citations, re-validated each time the PRD is regenerated) is passed in
`verbatim_keys`: it is redacted but not neutralized where it is stored, and the
renderer neutralizes it when it prints it. Rejection reasons are runtime prose and
are passed the same way; the payload quote inside one goes through `shield_quote`.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from .core.io import copy_file, write_text
from .injection import detect_injection, neutralize_marked, record_signals
from .secrets_scan import detect_secrets, load_allowlist, redact, sanitize_text


@dataclass(frozen=True)
class ArchivedPayload:
    path: Path
    redactions: int
    injection_ids: tuple[str, ...]


def archive_payload(workspace: Path, source: Path, target: Path) -> ArchivedPayload:
    """Store the workspace copy of a payload: secrets redacted, everything else as written."""
    text = source.read_bytes().decode("utf-8-sig")
    sanitized = sanitize_text(workspace, source.name, text)
    if sanitized.redactions:
        write_text(target, sanitized.text, newline="")  # keep the payload's own line endings
    else:
        copy_file(source, target)
    ids = record_signals(workspace, source.name, detect_injection(sanitized.text))
    return ArchivedPayload(target, sanitized.redactions, tuple(ids))


def clean_text(text: str, allowlist: frozenset[str] | set[str] = frozenset(), *, neutralize: bool = True) -> str:
    findings = detect_secrets(text, allowlist)
    if findings:
        text = redact(text, findings)
    if neutralize:
        signals = detect_injection(text)
        if signals:
            text = neutralize_marked(text, signals)
    return text


def shield_quote(text: str) -> str:
    """Neutralize the flagged lines of payload text quoted inside a runtime message.

    A rejection reason is runtime prose (`"citation not found verbatim …: <quote>"`) and
    is stored redacted only, because its own wording can look like an order ("resolve
    the feeding gap"); the payload quote it carries is shielded here, before it is embedded.
    """
    signals = detect_injection(text)
    return neutralize_marked(text, signals) if signals else text


def sanitize_payload(workspace: Path | None, value: Any, *, verbatim_keys: Iterable[str] = ()) -> Any:
    """A copy of `value` (dicts, lists, strings) with every string cleaned; the input is not changed.

    Strings under a key in `verbatim_keys` are redacted but keep their flagged lines.
    The workspace's `secrets_allowlist.txt` applies, as at `/ingest`.
    """
    allowlist = load_allowlist(workspace) if workspace is not None else frozenset()
    keep = frozenset(verbatim_keys)

    def walk(item: Any, neutralize: bool) -> Any:
        if isinstance(item, str):
            return clean_text(item, allowlist, neutralize=neutralize)
        if isinstance(item, dict):
            return {key: walk(child, neutralize and key not in keep) for key, child in item.items()}
        if isinstance(item, (list, tuple)):
            return type(item)(walk(child, neutralize) for child in item)
        return item

    return walk(value, True)
