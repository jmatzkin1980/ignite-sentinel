"""IMP-286: prompt-injection hygiene.

Source content is data, never instructions. Client material can carry text
shaped like an order to an agent ("ignore the previous instructions", a fake
`system:` turn, "run this command", "send the data to…", "close all gaps"). The
runtime never acts on it — compilers are deterministic over the text — and
`/ingest` and `/sync` surface it as findings with `origin: injection_signal` in
`01_discovery/injection_signals.md`, for the BA to review with the client. A
finding is a signal, not a verdict: the source is not altered and nothing is
blocked.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .core.io import append_text, write_text

SIGNALS_FILE = "01_discovery/injection_signals.md"
ORIGIN = "injection_signal"

_W = r"[^.\n]"
INJECTION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "override",
        re.compile(
            rf"\b(?:ignore|disregard|forget|override)\b{_W}{{0,40}}\b(?:previous|prior|above|earlier|all|any|your)\b"
            rf"{_W}{{0,30}}\b(?:instructions?|rules|prompts?|guidelines|directives)\b"
            rf"|\b(?:ignor|olvid|descart|omit)[aáeé]\w*\b{_W}{{0,40}}\b(?:instrucciones|reglas|indicaciones|directivas)\b",
            re.I,
        ),
    ),
    (
        "role_impersonation",
        re.compile(
            r"^\s*(?:system|assistant|developer)\s*:"
            r"|<\|im_(?:start|end)\|>|\[/?INST\]|<<SYS>>"
            r"|\byou are now\b|\bfrom now on,? you\b|\bact as (?:an?|the|my)\b|\bpretend (?:to be|you are)\b"
            r"|\bahora (?:sos|eres)\b|\bactu[aá] como\b",
            re.I | re.M,
        ),
    ),
    (
        "command_execution",
        re.compile(
            rf"\b(?:run|execute|eval)\b{_W}{{0,30}}\b(?:command|shell|terminal|the following)\b"
            r"|\b(?:curl|wget)\b[^\n|]*\|\s*(?:ba|z)?sh\b"
            r"|\brm\s+-rf\b"
            rf"|\b(?:ejecut|corr)[aáeé]\w*\b{_W}{{0,30}}\b(?:comando|terminal|consola)\b",
            re.I,
        ),
    ),
    (
        "exfiltration",
        re.compile(
            rf"\b(?:send|upload|post|forward|exfiltrate|leak|share)\b{_W}{{0,30}}"
            r"\b(?:this|the|all|your|any)\s+(?:data|content|conversation|context|files?|workspace|secrets?|credentials|keys?|prompt|instructions)\b"
            rf"{_W}{{0,40}}\b(?:to|at)\b"
            rf"|\b(?:envi|mand|sub|compart)[aáií]\w*\b{_W}{{0,30}}\b(?:los|las|el|la|todo|todos)\s+"
            r"(?:datos|contenido|archivos|secretos|credenciales|claves|instrucciones)\b",
            re.I,
        ),
    ),
    (
        "governance_tampering",
        re.compile(
            rf"\b(?:close|resolve|approve|skip|bypass|disable)\b{_W}{{0,30}}\b(?:all\s+)?"
            r"(?:gaps?|gates?|maturity|readiness|self-review|health checks?|traceability)\b"
            r"|\bdo not (?:report|flag|mention|record|log)\b"
            rf"|\b(?:cerr|aprob|salte|omit)[aáeé]\w*\b{_W}{{0,30}}\b(?:todos los\s+)?(?:gaps|gates|brechas)\b"
            r"|\bno (?:reportes|registres|menciones)\b",
            re.I,
        ),
    ),
)
SIGNAL_TYPES = tuple(name for name, _ in INJECTION_PATTERNS)


@dataclass(frozen=True)
class InjectionSignal:
    type: str
    line: int
    excerpt: str


def _excerpt(line: str, start: int, end: int, width: int = 90) -> str:
    left = max(0, start - 20)
    snippet = line[left : max(end, left + width)][:width].strip()
    snippet = snippet.replace("|", "\\|").replace("`", "'")
    return ("…" if left else "") + snippet + ("…" if left + width < len(line) else "")


def detect_injection(text: str) -> list[InjectionSignal]:
    """One signal per (line, type), in reading order."""
    signals: list[InjectionSignal] = []
    seen: set[tuple[int, str]] = set()
    lines = text.splitlines()
    starts = [0]
    for line in lines:
        starts.append(starts[-1] + len(line) + 1)
    for kind, pattern in INJECTION_PATTERNS:
        for match in pattern.finditer(text):
            number = text.count("\n", 0, match.start()) + 1
            if (number, kind) in seen:
                continue
            seen.add((number, kind))
            line = lines[number - 1] if number - 1 < len(lines) else ""
            offset = starts[number - 1]
            signals.append(InjectionSignal(kind, number, _excerpt(line, match.start() - offset, match.end() - offset)))
    return sorted(signals, key=lambda item: (item.line, SIGNAL_TYPES.index(item.type)))


_ROW = re.compile(r"^\| INJ-(\d+) \|", re.M)


def record_signals(workspace: Path, source_name: str, signals: list[InjectionSignal]) -> list[str]:
    """Append the signals to the BA-facing register and return their ids."""
    if not signals:
        return []
    path = workspace / SIGNALS_FILE
    if not path.exists():
        write_text(
            path,
            "# Injection Signals\n\n"
            "Source content is data, never instructions. These passages read like orders to an agent; "
            "Sentinel did not act on them and did not change the source. Review each one with the client: "
            "most are harmless phrasing, some are pasted prompts or attempts to steer the analysis.\n\n"
            "| ID | Origin | Detected (UTC) | Source | Line | Signal | Excerpt |\n"
            "|---|---|---|---|---|---|---|\n",
        )
    existing = [int(value) for value in _ROW.findall(path.read_text(encoding="utf-8"))]
    next_id = (max(existing) if existing else 0) + 1
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ids: list[str] = []
    rows: list[str] = []
    for offset, signal in enumerate(signals):
        identifier = f"INJ-{next_id + offset:03d}"
        ids.append(identifier)
        rows.append(f"| {identifier} | {ORIGIN} | {now} | `{source_name}` | {signal.line} | {signal.type} | `{signal.excerpt}` |\n")
    append_text(path, "".join(rows))
    return ids


def scan_source(workspace: Path, source_name: str, text: str) -> list[str]:
    return record_signals(workspace, source_name, detect_injection(text))


def neutralize(text: str, signals: list[InjectionSignal]) -> str:
    """Blank the flagged lines in the text the compilers analyze (line numbers are kept).

    The workspace raw copy still holds them verbatim and the register points at them;
    only the analysis is shielded, so an embedded order cannot steer gaps, units or
    any downstream artifact.
    """
    if not signals:
        return text
    flagged = {signal.line for signal in signals}
    lines = text.split("\n")
    return "\n".join("" if number in flagged else line for number, line in enumerate(lines, start=1))


def shield_source(workspace: Path, source_name: str, text: str) -> tuple[str, list[str]]:
    """Register the injection signals of a source and return (analysis text, signal ids)."""
    signals = detect_injection(text)
    return neutralize(text, signals), record_signals(workspace, source_name, signals)
