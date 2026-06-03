from __future__ import annotations

from pathlib import Path


ID_PREFIXES = ("RAW", "REQ", "GAP", "DEC", "SPEC", "EPIC", "US", "AC", "TC", "CHG")


def next_id(prefix: str, existing: list[str]) -> str:
    if prefix not in ID_PREFIXES:
        raise ValueError(f"Unsupported Sentinel id prefix: {prefix}")
    highest = 0
    marker = f"{prefix}-"
    for value in existing:
        if value.startswith(marker):
            try:
                highest = max(highest, int(value.split("-", 1)[1]))
            except ValueError:
                continue
    return f"{prefix}-{highest + 1:03d}"


def workspace_id_from_path(path: Path) -> str:
    return path.name


def prefix_for_node_type(node_type: str) -> str:
    mapping = {
        "raw_input": "RAW",
        "requirement": "REQ",
        "gap_report": "GAP",
        "decision_log": "DEC",
        "impact_report": "DEC",
        "spec": "SPEC",
        "epic": "EPIC",
        "user_story": "US",
        "acceptance_criteria": "AC",
        "test_case": "TC",
        "change": "CHG",
    }
    return mapping.get(node_type, "")
