from __future__ import annotations

import re
import shutil
from pathlib import Path

from .memory import ContextBroker
from .traceability import add_edge, add_node
from .workspace import ensure_workspace, update_state, workspace_path

METRIC_RE = re.compile(r"(\d+(?:[.,]\d+)?\s?%|\$\s?\d+|\d+\s?(?:usd|ars|eur|hours|horas|days|dias))", re.I)


def ingest(project_id: str, source: Path) -> dict[str, str]:
    ensure_workspace(project_id)
    base = workspace_path(project_id)
    text = source.read_text(encoding="utf-8")
    raw_target = base / "00_raw" / f"{source.stem}.md"
    shutil.copyfile(source, raw_target)
    raw_id = add_node(project_id, "RAW", "raw_input", raw_target, source.stem, domain="product")

    req_text = extract_requirement(text)
    req_path = base / "02_requirements" / "requirements.md"
    req_path.write_text(render_requirement(project_id, req_text, raw_id), encoding="utf-8")
    req_id = add_node(project_id, "REQ", "requirement", req_path, "Primary requirement", domain="product")
    add_edge(project_id, raw_id, req_id, "extracts")

    gaps = detect_gaps(text)
    gap_path = base / "01_discovery" / "gaps.md"
    gap_path.write_text(render_gaps(project_id, gaps, req_id), encoding="utf-8")
    gap_id = add_node(
        project_id,
        "GAP",
        "gap_report",
        gap_path,
        "Discovery gaps",
        status="open" if gaps else "closed",
        domain="product",
    )
    add_edge(project_id, req_id, gap_id, "has_gap")

    dec_path = base / "01_discovery" / "decisions.md"
    dec_path.write_text(render_decisions(project_id, text, req_id), encoding="utf-8")
    dec_id = add_node(project_id, "DEC", "decision_log", dec_path, "Pending decisions", status="pending")
    add_edge(project_id, req_id, dec_id, "requires_decision")

    digest_path = base / "01_discovery" / "raw_input_digest.md"
    digest_path.write_text(render_digest(project_id, text, raw_id, req_id, gap_id), encoding="utf-8")

    broker = ContextBroker(project_id)
    broker.index_artifact(raw_id, "raw_input", raw_target, text, trace_ids=[raw_id])
    broker.index_artifact(req_id, "requirement", req_path, req_path.read_text(encoding="utf-8"), trace_ids=[raw_id, req_id])
    broker.index_artifact(gap_id, "gap_report", gap_path, gap_path.read_text(encoding="utf-8"), trace_ids=[req_id, gap_id])
    broker.index_artifact(dec_id, "decision_log", dec_path, dec_path.read_text(encoding="utf-8"), trace_ids=[req_id, dec_id])

    update_state(
        project_id,
        phase="discovery_completed",
        health="DIRTY" if gaps else "CLEAN",
        artifacts={
            "raw_input": str(raw_target.as_posix()),
            "requirements": str(req_path.as_posix()),
            "gaps": str(gap_path.as_posix()),
            "decisions": str(dec_path.as_posix()),
        },
        metrics={"requirements": 1, "gaps_open": len(gaps), "decisions_pending": 1, "user_stories": 0},
    )
    return {"raw_id": raw_id, "requirement_id": req_id, "gap_id": gap_id, "decision_id": dec_id}


def extract_requirement(text: str) -> str:
    lines = [line.strip(" -\t") for line in text.splitlines() if line.strip()]
    for line in lines:
        if any(word in line.lower() for word in ("need", "necesit", "require", "objetivo", "queremos", "must")):
            return line
    return lines[0] if lines else "Requirement to be refined."


def detect_gaps(text: str) -> list[dict[str, str]]:
    lowered = text.lower()
    checks = [
        ("GAP-OBJECTIVE", "high", "Business objective or expected outcome is not explicit.", ("objetivo", "outcome", "resultado", "goal")),
        ("GAP-USERS", "high", "Target users or personas are not explicit.", ("usuario", "user", "persona", "actor")),
        ("GAP-SCOPE", "critical", "Scope boundaries are not explicit.", ("alcance", "scope", "in scope", "out of scope")),
        ("GAP-ACCEPTANCE", "critical", "Acceptance criteria or success conditions are missing.", ("criterio", "acceptance", "success", "done")),
        ("GAP-QUALITY", "medium", "Quality or testability expectations are not explicit.", ("test", "quality", "calidad", "qa")),
    ]
    gaps = [
        {"id": gap_id, "severity": severity, "description": description}
        for gap_id, severity, description, tokens in checks
        if not any(token in lowered for token in tokens)
    ]
    if METRIC_RE.search(text) and not any(token in lowered for token in ("source", "fuente", "baseline", "medido", "measured")):
        gaps.append(
            {
                "id": "GAP-METRIC-SOURCE",
                "severity": "high",
                "description": "Quantitative metric appears without an explicit source or baseline.",
            }
        )
    return gaps


def render_requirement(project_id: str, req_text: str, raw_id: str) -> str:
    return f"""# Requirement Register - {project_id}

## REQ-001 Primary Requirement

- Source: `{raw_id}`
- Status: `draft`
- Domains: product, functional, quality

{req_text}
"""


def render_gaps(project_id: str, gaps: list[dict[str, str]], req_id: str) -> str:
    rows = "\n".join(
        f"| {gap['id']} | {gap['severity']} | OPEN | `{req_id}` | {gap['description']} |"
        for gap in gaps
    )
    if not rows:
        rows = "| NONE | none | CLOSED | N/A | No blocking gaps detected by deterministic scan. |"
    return f"""# Discovery Gaps - {project_id}

| Gap ID | Severity | Status | Parent | Description |
| --- | --- | --- | --- | --- |
{rows}
"""


def render_decisions(project_id: str, text: str, req_id: str) -> str:
    decision = "Confirm scope, success criteria, and implementation constraints with stakeholders."
    if "decid" in text.lower() or "decision" in text.lower():
        decision = "Validate stated decisions and record their downstream impact."
    return f"""# Decision Log - {project_id}

| Decision ID | Status | Parent | Decision Needed |
| --- | --- | --- | --- |
| DEC-001 | PENDING | `{req_id}` | {decision} |
"""


def render_digest(project_id: str, text: str, raw_id: str, req_id: str, gap_id: str) -> str:
    return f"""# Raw Input Digest - {project_id}

- Raw source: `{raw_id}`
- Requirement: `{req_id}`
- Gap report: `{gap_id}`
- Character count: {len(text)}

## Summary

{extract_requirement(text)}
"""
