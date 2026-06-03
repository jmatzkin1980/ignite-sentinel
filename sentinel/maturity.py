from __future__ import annotations

import re

from .memory import ContextBroker
from .workspace import load_config, update_state, workspace_path


def evaluate(project_id: str) -> dict[str, object]:
    base = workspace_path(project_id)
    gaps_path = base / "01_discovery" / "gaps.md"
    requirements_path = base / "02_requirements" / "requirements.md"
    gaps_text = gaps_path.read_text(encoding="utf-8") if gaps_path.exists() else ""
    req_text = requirements_path.read_text(encoding="utf-8") if requirements_path.exists() else ""
    config = load_config(project_id)
    blocking = set(config.get("maturity", {}).get("blocking_gap_severities", ["critical", "high"]))
    blocking_gaps = parse_blocking_gaps(gaps_text, blocking)
    readiness = "READY_FOR_SPECS" if not blocking_gaps and req_text else "BLOCKED"
    report_path = base / "01_discovery" / "requirement_maturity_report.md"
    report_path.write_text(render_report(project_id, readiness, blocking_gaps), encoding="utf-8")
    ContextBroker(project_id).index_artifact(
        "MATURITY-001",
        "maturity_report",
        report_path,
        report_path.read_text(encoding="utf-8"),
        trace_ids=["MATURITY-001"],
    )
    update_state(project_id, phase="maturity_evaluated", health="CLEAN" if readiness.startswith("READY") else "DIRTY")
    return {"readiness": readiness, "blocking_gaps": blocking_gaps, "report": str(report_path)}


def parse_blocking_gaps(text: str, blocking_severities: set[str]) -> list[str]:
    blocking_gaps = []
    for line in text.splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if not cells or not cells[0].startswith("GAP-"):
            continue
        if len(cells) >= 4:
            severity = cells[2] if cells[1].lower() not in blocking_severities else cells[1]
            status = cells[3] if cells[1].lower() not in blocking_severities else cells[2]
            if status.upper() == "OPEN" and severity.lower() in blocking_severities:
                blocking_gaps.append(cells[0])
    return blocking_gaps


def render_report(project_id: str, readiness: str, blocking_gaps: list[str]) -> str:
    gaps = ", ".join(f"`{gap}`" for gap in blocking_gaps) or "None"
    return f"""# Requirement Maturity Report - {project_id}

- Readiness: `{readiness}`
- Blocking gaps: {gaps}

## Domain Readiness

| Domain | Status |
| --- | --- |
| product | {'READY' if readiness != 'BLOCKED' else 'BLOCKED'} |
| functional | {'READY' if readiness != 'BLOCKED' else 'BLOCKED'} |
| quality | {'READY' if readiness != 'BLOCKED' else 'BLOCKED'} |

## Verdict

{'The requirement can move into specs and backlog generation.' if readiness != 'BLOCKED' else 'Resolve blocking gaps before generating specs or backlog.'}
"""
