from __future__ import annotations

import re

from .memory import ContextBroker
from .traceability import children_of, load_graph, parents_of
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
        if has_blocking_open_gap(gaps_text):
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

    node_types = {node.get("type") for node in graph.get("nodes", [])}
    if "raw_input" in node_types and "identity_seed_bank" not in node_types:
        findings.append("Raw input exists without identity seeds.")
    if "raw_input" in node_types and "discovery_log" not in node_types:
        findings.append("Raw input exists without discovery log.")
    if "raw_input" in node_types and "lens_review" not in node_types:
        findings.append("Raw input exists without multi-lens critical review.")
    for req in [node for node in graph.get("nodes", []) if node.get("type") == "requirement"]:
        if not children_of(project_id, req["id"]):
            findings.append(f"{req['id']} has no downstream trace.")
    for story in [node for node in graph.get("nodes", []) if node.get("type") == "user_story"]:
        if not any(parent.startswith("EPIC-") for parent in parents_of(project_id, story["id"])):
            findings.append(f"{story['id']} is not linked to an epic.")

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


def has_blocking_open_gap(text: str) -> bool:
    for line in text.splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if not cells or not cells[0].startswith("GAP-"):
            continue
        # Old format: Gap ID | Severity | Status | ...
        if len(cells) >= 3 and cells[1].lower() in {"critical", "high"} and cells[2].upper() == "OPEN":
            return True
        # New format: Gap ID | Lens | Severity | Status | ...
        if len(cells) >= 4 and cells[2].lower() in {"critical", "high"} and cells[3].upper() == "OPEN":
            return True
    return False
