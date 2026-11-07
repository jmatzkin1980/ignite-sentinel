"""IMP-285: secrets and sensitive data at ingestion.

`/ingest` and `/sync` run every incoming source through `sanitize_text` before
anything is extracted. The user's original file is never touched; what enters
the workspace (the `00_raw/` copy and every artifact derived from it) carries
`<SECRETO:type>` instead of the secret, and each redaction opens an alert in
`01_discovery/secret_alerts.md` that records the type, the line and a SHA-256
fingerprint — never the value. A confirmed false positive is allowlisted by that
fingerprint in `secrets_allowlist.txt` at the workspace root.

Personal data (emails, phone numbers, card numbers) is reported only, and only
when the workspace opts in with `pii_report: true`: it is never redacted.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path

from .core.io import append_text, copy_file, write_text

ALLOWLIST_FILE = "secrets_allowlist.txt"
ALERTS_FILE = "01_discovery/secret_alerts.md"
PII_REPORT_FILE = "01_discovery/pii_report.md"

# Ordered: a span claimed by an earlier type is not reported again by a later one.
SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "private_key",
        re.compile(r"-----BEGIN (?:[A-Z0-9]+ )*PRIVATE KEY(?: BLOCK)?-----.*?-----END (?:[A-Z0-9]+ )*PRIVATE KEY(?: BLOCK)?-----", re.S),
    ),
    (
        "connection_string",
        re.compile(
            r"(?i)\b(?:Server|Data Source|Host|Endpoint|AccountName)=[^;\n]+;(?:[^;\n]*;)*?\s*"
            r"(?:Password|Pwd|AccountKey|SharedAccessKey)=[^;\s]+;?"
        ),
    ),
    ("url_credentials", re.compile(r"\b[a-z][a-z0-9+.-]{1,20}://[^\s:/@]+:[^\s/@]+@[^\s/]+", re.I)),
    (
        "cloud_key",
        re.compile(
            r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"
            r"|\bAIza[0-9A-Za-z_-]{35}\b"
            r"|(?i:aws_secret_access_key)\s*[:=]\s*[\"']?[A-Za-z0-9/+=]{40}\b"
        ),
    ),
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}")),
    (
        "token",
        re.compile(
            r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{36}\b"
            r"|\bgithub_pat_[A-Za-z0-9_]{60,}\b"
            r"|\bglpat-[A-Za-z0-9_-]{20}\b"
            r"|\bxox[abprs]-[A-Za-z0-9-]{10,}\b"
            r"|\bsk-(?:proj-|ant-)?[A-Za-z0-9_-]{32,}\b"
            r"|(?i:\bbearer\s+)[A-Za-z0-9._~+/-]{24,}=*"
        ),
    ),
)
SECRET_TYPES = tuple(name for name, _ in SECRET_PATTERNS)

PII_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("email", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")),
    ("phone", re.compile(r"(?<![\w+])\+?\d[\d ().-]{8,}\d\b")),
    ("card_number", re.compile(r"\b(?:\d[ -]?){13,19}\b")),
)


@dataclass(frozen=True)
class SecretFinding:
    type: str
    start: int
    end: int
    line: int
    fingerprint: str  # sha256 of the matched value

    @property
    def short(self) -> str:
        return self.fingerprint[:12]


def fingerprint(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def redaction_marker(kind: str) -> str:
    return f"<SECRETO:{kind}>"


def detect_secrets(text: str, allowlist: frozenset[str] | set[str] = frozenset()) -> list[SecretFinding]:
    claimed: list[tuple[int, int]] = []
    findings: list[SecretFinding] = []
    for kind, pattern in SECRET_PATTERNS:
        for match in pattern.finditer(text):
            start, end = match.span()
            if any(start < taken_end and taken_start < end for taken_start, taken_end in claimed):
                continue
            claimed.append((start, end))
            digest = fingerprint(match.group(0))
            if digest in allowlist:
                continue
            findings.append(SecretFinding(kind, start, end, text.count("\n", 0, start) + 1, digest))
    return sorted(findings, key=lambda item: item.start)


def redact(text: str, findings: list[SecretFinding]) -> str:
    for finding in sorted(findings, key=lambda item: item.start, reverse=True):
        text = text[: finding.start] + redaction_marker(finding.type) + text[finding.end :]
    return text


def load_allowlist(workspace: Path) -> frozenset[str]:
    path = workspace / ALLOWLIST_FILE
    if not path.exists():
        return frozenset()
    entries = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        value = line.split("#", 1)[0].strip().lower()
        if re.fullmatch(r"[0-9a-f]{64}", value):
            entries.add(value)
    return frozenset(entries)


def _luhn_ok(digits: str) -> bool:
    total = 0
    for index, char in enumerate(reversed(digits)):
        value = int(char)
        if index % 2:
            value *= 2
            if value > 9:
                value -= 9
        total += value
    return total % 10 == 0


def detect_pii(text: str) -> list[tuple[str, int]]:
    """(type, line) pairs for personal data; report-only, the values are never kept."""
    found: list[tuple[str, int]] = []
    for kind, pattern in PII_PATTERNS:
        for match in pattern.finditer(text):
            value = match.group(0)
            if kind == "card_number":
                digits = re.sub(r"\D", "", value)
                if not 13 <= len(digits) <= 19 or not _luhn_ok(digits):
                    continue
            found.append((kind, text.count("\n", 0, match.start()) + 1))
    return found


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def record_alerts(workspace: Path, source_name: str, findings: list[SecretFinding]) -> Path | None:
    if not findings:
        return None
    path = workspace / ALERTS_FILE
    if not path.exists():
        write_text(
            path,
            "# Secret Alerts\n\n"
            "Secrets found in incoming sources were redacted before extraction. The original file "
            "was not modified: rotate the secret at its origin and remove it from the source. A "
            f"confirmed false positive goes to `{ALLOWLIST_FILE}` by its full fingerprint.\n\n"
            "| Detected (UTC) | Source | Line | Type | Fingerprint (sha256, 12) |\n"
            "|---|---|---|---|---|\n",
        )
    rows = "".join(
        f"| {_now()} | `{source_name}` | {item.line} | {item.type} | `{item.short}` |\n" for item in findings
    )
    append_text(path, rows)
    return path


def record_pii_report(workspace: Path, source_name: str, found: list[tuple[str, int]]) -> Path | None:
    if not found:
        return None
    path = workspace / PII_REPORT_FILE
    if not path.exists():
        write_text(
            path,
            "# Personal Data Report\n\n"
            "Opt-in (`pii_report: true`). Report only: nothing was redacted and no value is stored here.\n\n"
            "| Detected (UTC) | Source | Line | Type |\n|---|---|---|---|\n",
        )
    append_text(path, "".join(f"| {_now()} | `{source_name}` | {line} | {kind} |\n" for kind, line in found))
    return path


@dataclass(frozen=True)
class SanitizedSource:
    text: str
    findings: tuple[SecretFinding, ...]
    alerts_path: Path | None
    pii_path: Path | None

    @property
    def redactions(self) -> int:
        return len(self.findings)


def sanitize_text(workspace: Path, source_name: str, text: str, pii_report: bool = False) -> SanitizedSource:
    findings = detect_secrets(text, load_allowlist(workspace))
    alerts = record_alerts(workspace, source_name, findings)
    pii = record_pii_report(workspace, source_name, detect_pii(text)) if pii_report else None
    return SanitizedSource(redact(text, findings), tuple(findings), alerts, pii)


def pii_report_enabled(config: dict[str, object]) -> bool:
    value = config.get("pii_report", False)
    return value is True or str(value).strip().lower() in {"true", "yes", "1"}


def ingest_source(workspace: Path, source: Path, target: Path, pii_report: bool = False) -> tuple[str, SanitizedSource]:
    """Store the workspace copy of `source` (redacted when needed) and return the text to extract from.

    The original file is only read. Without findings the copy is byte-identical;
    with findings the copy keeps the original line endings and carries the markers.
    """
    raw = source.read_bytes().decode("utf-8")
    result = sanitize_text(workspace, source.name, raw, pii_report)
    if result.redactions:
        write_text(target, result.text, newline="")
    else:
        copy_file(source, target)
    return result.text.replace("\r\n", "\n").replace("\r", "\n"), result


_WORKSPACE_REF = r"workspaces[/\\]{name}(?![\w-])"  # either path separator


def output_leaks(project_id: str, text: str, workspace: Path) -> list[str]:
    """Secrets or references to another workspace in a view or export about to be written."""
    leaks = [f"secret {item.type} (line {item.line})" for item in detect_secrets(text, load_allowlist(workspace))]
    workspaces_dir = workspace.parent
    if workspaces_dir.is_dir():
        for sibling in sorted(workspaces_dir.iterdir()):
            if sibling.is_dir() and sibling.name != project_id:
                if re.search(_WORKSPACE_REF.format(name=re.escape(sibling.name)), text):
                    leaks.append(f"reference to workspace {sibling.name}")
    return leaks


class OutputLeak(RuntimeError):
    """A view or export would carry a secret or another workspace's content (IMP-285)."""


def assert_no_leaks(project_id: str, text: str, workspace: Path, what: str) -> None:
    leaks = output_leaks(project_id, text, workspace)
    if leaks:
        raise OutputLeak(f"refusing to write {what} for {project_id}: " + "; ".join(leaks))
