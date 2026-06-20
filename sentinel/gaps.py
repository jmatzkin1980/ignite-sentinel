from __future__ import annotations

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
