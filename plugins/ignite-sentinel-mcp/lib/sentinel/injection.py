"""IMP-286: prompt-injection hygiene.

Source content is data, never instructions. Client material can carry text
shaped like an order to an agent ("ignore the previous instructions", a fake
`system:` turn, "run this command", "send the data to…", "close all gaps"). The
runtime never acts on it — compilers are deterministic over the text — and
`/ingest` and `/sync` surface it as findings with `origin: injection_signal` in
`01_discovery/injection_signals.md`, for the BA to review with the client. A
finding is a signal, not a verdict: the source is not altered and nothing is
blocked. Agent and BA payloads are scanned too (`payload_hygiene`, IMP-342).
IMP-351: the same patterns are also looked for where a reader does not see them:
inside HTML comments, in encoded runs (base64, hex, percent-encoding) and behind
zero-width or look-alike characters (`HIDDEN_TYPES`).
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
# IMP-336: like _W, but a dot inside a token (`state.json`, `evil.example`) does not end the phrase.
_WD = r"(?:[^.\n]|\.(?=\S))"
INJECTION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "override",
        re.compile(
            rf"\b(?:ignore|disregard|forget|override)\b{_W}{{0,40}}\b(?:previous|prior|above|earlier|all|any|your)\b"
            rf"{_W}{{0,30}}\b(?:instructions?|rules|prompts?|guidelines|directives)\b"
            # IMP-398: like the English branch, Spanish needs a "previous instructions" qualifier, or the
            # second-person imperative; "El diseño omite reglas vigentes" is business text, not an override.
            rf"|\b(?:ignor|olvid|descart|omit)[aáeé]\w*\b{_W}{{0,40}}\b(?:anteriores|previas|de\s+arriba|todas|tus|las\s+del\s+sistema)\b"
            rf"{_W}{{0,30}}\b(?:instrucciones|reglas|indicaciones|directivas)\b"
            rf"|\b(?:ignorá|ignora\s+las|olvidá|olvida\s+las|omití)\s+(?:\w+\s+){{0,3}}?(?:instrucciones|indicaciones|directivas)\b",
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
            rf"{_WD}{{0,40}}\b(?:to|at)\b"
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
# IMP-351: the same patterns, found where a reader does not see them.
#   html_comment: inside `<!-- ... -->` (hidden when the Markdown or HTML is rendered),
#     also when the phrase is split across lines or the comment opens with `system:`;
#   encoded: a base64, hex or percent-encoded run that decodes to an instruction;
#   obfuscated: the line only matches once zero-width characters are removed and
#     look-alike forms (fullwidth letters) are folded (NFKC).
HIDDEN_TYPES = ("html_comment", "encoded", "obfuscated")
_ORDER = SIGNAL_TYPES + HIDDEN_TYPES


@dataclass(frozen=True)
class InjectionSignal:
    type: str
    line: int
    excerpt: str
    end_line: int | None = None  # IMP-351: a multi-line HTML comment flags every line it spans

    @property
    def lines(self) -> range:
        return range(self.line, max(self.line, self.end_line or self.line) + 1)


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
    signals.extend(_hidden_signals(text, {line for line, _ in seen}))
    return sorted(signals, key=lambda item: (item.line, _ORDER.index(item.type)))


# --- IMP-351: hidden instructions -------------------------------------------------

_HTML_COMMENT = re.compile(r"<!--(.*?)-->", re.S)  # an unclosed `<!--` is left to the line patterns
_BASE64_RUN = re.compile(r"(?<![A-Za-z0-9+/_-])[A-Za-z0-9+/_-]{24,}={0,2}")
_HEX_RUN = re.compile(r"(?<![0-9A-Fa-f])(?:[0-9A-Fa-f]{2}){12,}(?![0-9A-Fa-f])")
_PERCENT_RUN = re.compile(r"(?:%[0-9A-Fa-f]{2}|[A-Za-z0-9._~+-]){12,}")
_PERCENT_BYTE = re.compile(rb"%([0-9A-Fa-f]{2})")
_MAX_ENCODED = 8192  # characters decoded per run: an instruction is short, an image is not worth decoding whole
# zero-width space / non-joiner / joiner, word joiner, BOM, soft hyphen, Mongolian vowel separator
_INVISIBLE = dict.fromkeys((0x200B, 0x200C, 0x200D, 0x2060, 0xFEFF, 0x00AD, 0x180E))


def _first_match(text: str) -> re.Match[str] | None:
    for _, pattern in INJECTION_PATTERNS:
        match = pattern.search(text)
        if match:
            return match
    return None


def _flat_excerpt(prefix: str, text: str, match: re.Match[str]) -> str:
    """Excerpt of decoded or comment text: one line, and secrets redacted (the decoded text never went through /ingest's sanitizer)."""
    from .secrets_scan import detect_secrets, redact

    flat = re.sub(r"\s", " ", text)
    findings = detect_secrets(flat)
    snippet = _excerpt(redact(flat, findings) if findings else flat, match.start(), match.end())
    return f"{prefix} {snippet}"


def _printable(text: str) -> bool:
    return bool(text) and sum(ch.isprintable() or ch in "\n\r\t" for ch in text) >= 0.9 * len(text)


def _decode_base64(run: str) -> str | None:
    import base64
    import binascii

    body = run.rstrip("=")[:_MAX_ENCODED].replace("-", "+").replace("_", "/")
    body = body[: len(body) - len(body) % 4] if len(body) % 4 == 1 else body
    try:
        raw = base64.b64decode(body + "=" * (-len(body) % 4), validate=True)
    except (binascii.Error, ValueError):
        return None
    return _as_text(raw)


def _decode_hex(run: str) -> str | None:
    return _as_text(bytes.fromhex(run[: _MAX_ENCODED - _MAX_ENCODED % 2]))


def _decode_percent(run: str) -> str | None:
    if run.count("%") < 4:
        return None
    raw = _PERCENT_BYTE.sub(lambda m: bytes([int(m.group(1), 16)]), run[:_MAX_ENCODED].encode("ascii"))
    return _as_text(raw.replace(b"+", b" "))


def _as_text(raw: bytes) -> str | None:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return None
    return text if _printable(text) else None


_DECODERS = (("base64", _BASE64_RUN, _decode_base64), ("hex", _HEX_RUN, _decode_hex), ("percent", _PERCENT_RUN, _decode_percent))


def _encoded_signal(number: int, line: str) -> InjectionSignal | None:
    for scheme, pattern, decode in _DECODERS:
        for run in pattern.finditer(line):
            decoded = decode(run.group(0))
            match = _first_match(decoded) if decoded else None
            if match:
                return InjectionSignal("encoded", number, _flat_excerpt(f"{scheme}:", decoded, match))
    return None


def _obfuscated_signal(number: int, line: str) -> InjectionSignal | None:
    if line.isascii():
        return None
    import unicodedata

    folded = unicodedata.normalize("NFKC", line.translate(_INVISIBLE))
    match = _first_match(folded) if folded != line else None
    return InjectionSignal("obfuscated", number, _flat_excerpt("folded:", folded, match)) if match else None


def _comment_signals(text: str) -> list[InjectionSignal]:
    signals: list[InjectionSignal] = []
    for comment in _HTML_COMMENT.finditer(text):
        inner = comment.group(1)
        stripped = "\n".join(part.strip() for part in inner.split("\n"))  # `<!-- system: ...` starts a line here
        collapsed = " ".join(inner.split())  # a phrase split across the comment's lines
        source, match = stripped, _first_match(stripped)
        if not match:
            source, match = collapsed, _first_match(collapsed)
        if not match:
            continue
        start = text.count("\n", 0, comment.start()) + 1
        end = start + comment.group(0).count("\n")
        signals.append(InjectionSignal("html_comment", start, _flat_excerpt("comment:", source, match), end if end > start else None))
    return signals


def _hidden_signals(text: str, flagged: set[int]) -> list[InjectionSignal]:
    signals = _comment_signals(text)
    for number, line in enumerate(text.split("\n"), start=1):
        found = _encoded_signal(number, line)
        if found:
            signals.append(found)
        if number not in flagged:
            found = _obfuscated_signal(number, line)
            if found:
                signals.append(found)
    return signals


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
        line = f"{signal.line}-{signal.end_line}" if signal.end_line else str(signal.line)
        rows.append(f"| {identifier} | {ORIGIN} | {now} | `{source_name}` | {line} | {signal.type} | `{signal.excerpt}` |\n")
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
    flagged = {number for signal in signals for number in signal.lines}
    lines = text.split("\n")
    return "\n".join("" if number in flagged else line for number, line in enumerate(lines, start=1))


def neutralized_marker(kind: str) -> str:
    return f"<NEUTRALIZADO:{kind}>"


def neutralize_marked(text: str, signals: list[InjectionSignal]) -> str:
    """IMP-342: like `neutralize`, but each flagged line becomes a visible `<NEUTRALIZADO:type>`.

    Used on the text of agent and BA payloads before it lands in an artifact: a blank
    would leave an empty decision or table cell with no sign that something was there.
    """
    if not signals:
        return text
    kinds: dict[int, str] = {}
    for signal in signals:
        for number in signal.lines:
            kinds.setdefault(number, signal.type)
    lines = text.split("\n")
    return "\n".join(
        neutralized_marker(kinds[number]) if number in kinds else line for number, line in enumerate(lines, start=1)
    )


def shield_source(workspace: Path, source_name: str, text: str) -> tuple[str, list[str]]:
    """Register the injection signals of a source and return (analysis text, signal ids)."""
    signals = detect_injection(text)
    return neutralize(text, signals), record_signals(workspace, source_name, signals)
