from __future__ import annotations

import re

from .memory import ContextBroker
from .traceability import load_graph, parents_of
from .workspace import memory_path, update_state, workspace_path, write_json

METRIC_RE = re.compile(r"(\d+(?:[.,]\d+)?\s?%|\$\s?\d+)", re.I)


def run_health(project_id: str) -> dict[str, object]:
    base = workspace_path(project_id)
    graph = load_graph(project_id)
    findings: list[str] = []

    for node in graph.get("nodes", []):
        if node["type"] == "user_story" and not parents_of(project_id, node["id"]):
            findings.append(f"{node['id']} has no parent trace.")
        if node["type"] == "acceptance_criteria" and not parents_of(project_id, node["id"]):
            findings.append(f"{node['id']} has no parent user story.")

    gaps_path = base / "01_discovery" / "gaps.md"
    if gaps_path.exists():
        gaps_text = gaps_path.read_text(encoding="utf-8")
        if "| critical | OPEN |" in gaps_text or "| high | OPEN |" in gaps_text:
            findings.append("Blocking gaps remain open.")

    for path in base.rglob("*.md"):
        text = path.read_text(encoding="utf-8")
        if METRIC_RE.search(text) and not re.search(r"(source|fuente|baseline|measured|medido)", text, re.I):
            findings.append(f"Metric without explicit source detected in {path.name}.")

    memory = ContextBroker(project_id).data
    indexed_paths = {item["source_path"] for item in memory.get("artifacts", [])}
    for node in graph.get("nodes", []):
        if node.get("path") and node["path"] not in indexed_paths and node["type"] not in {"acceptance_criteria"}:
            findings.append(f"{node['id']} is not indexed in memory.")

    verdict = "CLEAN" if not findings else "DIRTY"
    report_path = base / "06_traceability" / "health_report.md"
    report_path.write_text(render_health(project_id, verdict, findings), encoding="utf-8")
    write_json(base / "06_traceability" / "health_report.json", {"verdict": verdict, "findings": findings})
    update_state(project_id, health=verdict)
    return {"verdict": verdict, "findings": findings, "memory": str(memory_path(project_id))}


def render_health(project_id: str, verdict: str, findings: list[str]) -> str:
    rows = "\n".join(f"- {finding}" for finding in findings) or "- No findings."
    return f"""# Health Report - {project_id}

- Verdict: `{verdict}`

## Findings

{rows}
"""
