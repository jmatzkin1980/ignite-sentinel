from __future__ import annotations

import re
from typing import Any

from .core.markdown import parse_table_rows


GAP_ROW_FIELDS = (
    "id",
    "lens",
    "severity",
    "status",
    "parent",
    "description",
    "question",
    "source",
    "evidence_mention",
    "origin",
    "resolution_note",
)
BLOCKING_GAP_STATUSES = {"OPEN", "ANSWERED", "PARTIALLY_CLOSED"}
GAP_STATUSES = BLOCKING_GAP_STATUSES | {"CLOSED"}
DEFAULT_BLOCKING_GAP_SEVERITIES = {"critical", "high"}


def blocking_severities(config: dict[str, Any] | None) -> set[str]:
    maturity = config.get("maturity", {}) if isinstance(config, dict) else {}
    configured = maturity.get("blocking_gap_severities", DEFAULT_BLOCKING_GAP_SEVERITIES)
    if not isinstance(configured, (list, tuple, set)):
        return set(DEFAULT_BLOCKING_GAP_SEVERITIES)
    severities = {str(value).strip().lower() for value in configured if str(value).strip()}
    return severities or set(DEFAULT_BLOCKING_GAP_SEVERITIES)


def parse_gap_table(text: str, *, include_legacy: bool = False) -> list[dict[str, str]]:
    gaps: list[dict[str, str]] = []
    for line in text.splitlines():
        rows = parse_table_rows(line)
        cells = rows[0] if rows else []
        if not cells or not cells[0].startswith("GAP-"):
            continue
        if len(cells) >= 8:
            gap = {
                "id": cells[0],
                "lens": cells[1],
                "severity": cells[2],
                "status": cells[3],
                "parent": cells[4],
                "description": cells[5],
                "question": cells[6],
                "source": cells[7],
            }
            for index, field in enumerate(GAP_ROW_FIELDS[8:], start=8):
                if len(cells) > index and cells[index] not in {"", "N/A"}:
                    gap[field] = cells[index]
            gaps.append(gap)
            continue
        if include_legacy:
            legacy = legacy_gap_row(cells)
            if legacy:
                gaps.append(legacy)
    return gaps


def legacy_gap_row(cells: list[str]) -> dict[str, str] | None:
    if len(cells) < 4:
        return None
    second = cells[2].strip("`").upper()
    if second in GAP_STATUSES:
        return {
            "id": cells[0],
            "lens": "",
            "severity": cells[1],
            "status": cells[2],
            "parent": "",
            "description": cells[3],
            "question": "",
            "source": "",
        }
    return {
        "id": cells[0],
        "lens": cells[1],
        "severity": cells[2],
        "status": cells[3],
        "parent": "",
        "description": cells[4] if len(cells) > 4 else "",
        "question": "",
        "source": "",
    }


def is_blocking(
    gap: dict[str, Any],
    severities: set[str] | None = None,
    statuses: set[str] | None = None,
) -> bool:
    blocking = severities or DEFAULT_BLOCKING_GAP_SEVERITIES
    blocking_statuses = statuses or BLOCKING_GAP_STATUSES
    severity = str(gap.get("severity", "")).strip("`").lower()
    status = str(gap.get("status", "OPEN")).strip("`").upper()
    return severity in blocking and status in blocking_statuses


def parse_gap_responses(text: str) -> dict[str, dict[str, str]]:
    pattern = re.compile(r"^###\s+(GAP-[A-Z0-9-]+).*?(?=^###\s+GAP-[A-Z0-9-]+|\Z)", re.M | re.S)
    responses: dict[str, dict[str, str]] = {}
    for match in pattern.finditer(text):
        gap_id = match.group(1).strip()
        block = match.group(0)
        responses[gap_id] = {
            "answer": extract_field(block, ("Respuesta", "Answer")),
            "owner": extract_field(block, ("Owner / fuente", "Owner / source")),
            "evidence": extract_field(block, ("Evidencia o referencia", "Evidence or reference")),
            "decision_status": extract_field(block, ("Estado de decisión", "Decision status")),
        }
    return responses


def extract_field(block: str, labels: tuple[str, ...]) -> str:
    for label in labels:
        pattern = re.compile(rf"^\s*-\s*{re.escape(label)}\s*:\s*(.*)$", re.I | re.M)
        match = pattern.search(block)
        if match:
            return match.group(1).strip()
    return ""


def parse_gap_answers(text: str) -> dict[str, dict[str, str]]:
    """Map gap_id -> confirmed answer from the gap-resolution seed/decision tables."""
    answers: dict[str, dict[str, str]] = {}
    for row in parse_table_rows(text, skip_separator_rows=True):
        if len(row) >= 5 and row[1].startswith("GAP-") and row[2].upper() == "CONFIRMED":
            answers.setdefault(row[1], {"statement": row[3], "source": row[4]})
    return answers
