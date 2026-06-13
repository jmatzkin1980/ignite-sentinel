from __future__ import annotations

from pathlib import Path


ID_PREFIXES = ("RAW", "REQ", "GAP", "DEC", "SEED", "DISC", "PRD", "SPEC", "EPIC", "US", "AC", "TC", "QA", "CHG", "EV", "CTX")


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
        "decision": "DEC",
        "impact_report": "DEC",
        "gap_resolution_report": "DEC",
        "regeneration_diff": "DEC",
        "identity_seed_bank": "SEED",
        "identity_seed": "SEED",
        "discovery_log": "DISC",
        "lens_review": "DISC",
        "agent_annotation": "DISC",
        "project_brief": "REQ",
        "ears_requirement": "REQ",
        "prd": "PRD",
        "prd_composition": "PRD",
        "backlog_refinement": "CHG",
        "story_status_change": "CHG",
        "story_acceptance_evidence": "EV",
        "spec": "SPEC",
        "spec_unit": "SPEC",
        "epic": "EPIC",
        "user_story": "US",
        "acceptance_criteria": "AC",
        "test_case": "TC",
        "backlog_readiness_audit": "QA",
        "change": "CHG",
        "context_request": "CTX",
    }
    return mapping.get(node_type, "")
