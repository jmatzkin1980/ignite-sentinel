"""IMP-271: the sweep protocol for agentic channels, and F7 (BA disposition).

Every agentic channel (`/annotate`, `/challenge`, `/scrutinize`, the
implementability probe and `/self-review`) follows
`sentinel/templates/agent_sweep_protocol.md`. The runtime enforces the parts that
can be checked, on top of `validate_agent_gaps` (verbatim evidence, declared lens,
severity):

- **`AUSENTE: <what> en <where>`** (or `ABSENT: <what> in <where>`). Every entry of
  `absent` must have both parts, and what it says is absent must really be absent
  from the grounding text: an absence is re-verified, never taken on trust.
- **What I saw and did NOT touch.** `untouched` is a list of non-empty strings.
- **Findings classified by whether they block.** `blocks`, when given, is a boolean.
- **Figures are injected by the runtime, not written by the agent.** A payload with
  `counts`, `totals`, `summary`, `figures`, `stats` or `metrics` is rejected; the
  runtime counts what it accepted and writes those figures in
  `01_discovery/agent_sweep_log.md`.

**F7.** The BA records a disposition on every gap an agentic channel raised:
`accepted`, `rejected` or `irrelevant` (`/gaps PROJECT_ID --id GAP-X --disposition
...`). `/maturity` reports, per channel, how many gaps were raised and disposed and
the false-alarm rate: (rejected + irrelevant) / disposed.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from .core.io import append_text, read_json, write_json

PROTOCOL_PATH = "sentinel/templates/agent_sweep_protocol.md"
AGENTIC_ORIGINS = ("agent", "challenge", "scrutiny", "implementability-probe", "self-review")
DISPOSITIONS = ("accepted", "rejected", "irrelevant")
FALSE_ALARM = ("rejected", "irrelevant")
RUNTIME_FIGURE_KEYS = ("counts", "totals", "summary", "figures", "stats", "metrics")
DISPOSITIONS_FILE = "01_discovery/agent_dispositions.json"
SWEEP_LOG_FILE = "01_discovery/agent_sweep_log.md"

ABSENT_RE = re.compile(
    r"^\s*(?:AUSENTE|ABSENT)\s*:\s*(?P<what>.+?)\s+(?:en|in)\s+(?P<where>\S.*?)\s*$", re.I | re.S
)


class SweepProtocolError(ValueError):
    """A payload that breaks the sweep protocol."""


def _strip_quotes(text: str) -> str:
    return text.strip().strip("\"'`«»“”").strip()


def validate_sweep_extras(data: dict, haystack: str, normalize: Callable[[str], str]) -> dict[str, list[str]]:
    """Check the protocol fields of an agent payload. `haystack` is the normalized grounding text."""
    present = sorted(key for key in RUNTIME_FIGURE_KEYS if key in data)
    if present:
        raise SweepProtocolError(
            f"The payload carries {', '.join(present)}: figures are injected by the runtime, "
            f"never written by the agent (see {PROTOCOL_PATH})."
        )
    absent = data.get("absent", [])
    if not isinstance(absent, list):
        raise SweepProtocolError("'absent' must be a list of 'AUSENTE: <what> en <where>' entries.")
    for index, entry in enumerate(absent, start=1):
        match = ABSENT_RE.match(str(entry)) if isinstance(entry, str) else None
        if match is None:
            raise SweepProtocolError(
                f"absent #{index} is malformed: {entry!r}. Write 'AUSENTE: <what> en <where>' "
                "(or 'ABSENT: <what> in <where>')."
            )
        what = _strip_quotes(match.group("what"))
        if len(what) < 3:
            raise SweepProtocolError(f"absent #{index}: say what was looked for, not just {what!r}.")
        if normalize(what) in haystack:
            raise SweepProtocolError(
                f"absent #{index}: {what!r} is reported absent but it is in the grounding text. "
                "An absence is re-verified, never taken on trust."
            )
    untouched = data.get("untouched", [])
    if not isinstance(untouched, list) or any(not isinstance(item, str) or not item.strip() for item in untouched):
        raise SweepProtocolError("'untouched' (what I saw and did NOT touch) must be a list of non-empty strings.")
    for index, item in enumerate(data.get("gaps") or [], start=1):
        if isinstance(item, dict) and "blocks" in item and not isinstance(item["blocks"], bool):
            raise SweepProtocolError(f"Gap #{index}: 'blocks' must be true or false.")
    return {"absent": [str(entry).strip() for entry in absent], "untouched": [item.strip() for item in untouched]}


def record_sweep(base: Path, channel: str, data: dict, accepted_gap_ids: list[str]) -> Path:
    """Append the run to the sweep log. Every figure here is counted by the runtime."""
    absent = [str(entry).strip() for entry in data.get("absent", []) or []]
    untouched = [str(item).strip() for item in data.get("untouched", []) or []]
    blocking = [str(item.get("id", "")).strip().upper() for item in data.get("gaps") or []
                if isinstance(item, dict) and item.get("blocks") is True]
    path = base / SWEEP_LOG_FILE
    lines = []
    if not path.exists():
        lines += [
            "# Agent sweep log",
            "",
            f"Generated by IMP-271. Every figure is counted by the runtime; protocol: `{PROTOCOL_PATH}`.",
            "",
        ]
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    lines += [
        f"## {channel} - {stamp}",
        "",
        f"- Findings accepted (runtime count): {len(accepted_gap_ids)}"
        + (f" ({', '.join(accepted_gap_ids)})" if accepted_gap_ids else ""),
        f"- Marked as blocking by the agent: {len(blocking)}" + (f" ({', '.join(blocking)})" if blocking else ""),
        f"- Absences re-verified: {len(absent)}",
        *[f"  - {entry}" for entry in absent],
        f"- Seen and NOT touched: {len(untouched)}",
        *[f"  - {item}" for item in untouched],
        "",
    ]
    append_text(path, "\n".join(lines) + "\n", root=base)
    return path


# --- F7: BA disposition --------------------------------------------------------


def load_dispositions(base: Path) -> dict[str, dict[str, Any]]:
    data = read_json(base / DISPOSITIONS_FILE, {})
    return dict(data.get("dispositions", {})) if isinstance(data, dict) else {}


def set_disposition(base: Path, gap: dict[str, str], disposition: str, reason: str = "") -> dict[str, Any]:
    if disposition not in DISPOSITIONS:
        raise SweepProtocolError(f"--disposition must be one of {', '.join(DISPOSITIONS)}.")
    origin = str(gap.get("origin", "checklist")).strip() or "checklist"
    if origin not in AGENTIC_ORIGINS:
        raise SweepProtocolError(
            f"{gap['id']} has origin {origin!r}; a disposition applies only to gaps an agentic channel raised "
            f"({', '.join(AGENTIC_ORIGINS)})."
        )
    if disposition in FALSE_ALARM and not reason.strip():
        raise SweepProtocolError(f"--disposition {disposition} needs --reason: say why it was a false alarm.")
    dispositions = load_dispositions(base)
    record = {"origin": origin, "disposition": disposition, "reason": reason.strip(),
              "at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
    dispositions[gap["id"]] = record
    write_json(base / DISPOSITIONS_FILE, {"version": 1, "dispositions": dict(sorted(dispositions.items()))}, root=base)
    return record


def channel_dispositions(base: Path, gaps: list[dict[str, str]]) -> dict[str, dict[str, Any]]:
    """Per agentic channel: raised, each disposition, undisposed and the false-alarm rate."""
    dispositions = load_dispositions(base)
    report: dict[str, dict[str, Any]] = {}
    for gap in gaps:
        origin = str(gap.get("origin", "")).strip()
        if origin not in AGENTIC_ORIGINS:
            continue
        row = report.setdefault(origin, {"raised": 0, **{d: 0 for d in DISPOSITIONS}, "undisposed": 0})
        row["raised"] += 1
        disposition = dispositions.get(gap["id"], {}).get("disposition")
        row[disposition if disposition in DISPOSITIONS else "undisposed"] += 1
    for row in report.values():
        disposed = sum(row[d] for d in DISPOSITIONS)
        row["false_alarm_rate"] = round(sum(row[d] for d in FALSE_ALARM) / disposed, 3) if disposed else None
    return dict(sorted(report.items()))
