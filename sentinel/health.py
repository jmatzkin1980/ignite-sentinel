from __future__ import annotations

import re

from .backlog.hooks import evaluate_backlog_privacy
from .gaps import blocking_severities, is_blocking, parse_gap_table
from .generation import domain_context_snapshot
from .memory import ContextBroker
from .core.graph import children_of, load_graph, parents_of
from .workspace import load_config, memory_path, read_json, update_state, workspace_path, write_json

METRIC_RE = re.compile(r"(\d+(?:[.,]\d+)?\s?%|\$\s?\d+)", re.I)


def run_health(project_id: str) -> dict[str, object]:
    base = workspace_path(project_id)
    graph = load_graph(project_id)
    findings: list[str] = []
    warnings: list[str] = []

    for node in graph.get("nodes", []):
        if node["type"] == "user_story" and not parents_of(project_id, node["id"]):
            findings.append(f"{node['id']} has no parent trace.")
        if node["type"] == "acceptance_criteria" and not parents_of(project_id, node["id"]):
            findings.append(f"{node['id']} has no parent user story.")

    gaps_path = base / "01_discovery" / "gaps.md"
    if gaps_path.exists():
        gaps_text = gaps_path.read_text(encoding="utf-8")
        if has_blocking_open_gap(gaps_text, blocking_severities(load_config(project_id))):
            findings.append("Blocking gaps remain open.")

    for path in base.rglob("*.md"):
        text = path.read_text(encoding="utf-8")
        if METRIC_RE.search(text) and not re.search(r"(source|fuente|baseline|measured|medido)", text, re.I):
            findings.append(f"Metric without explicit source detected in {path.name}.")

    broker = ContextBroker(project_id)
    memory = broker.data
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
    warnings.extend(domain_context_freshness_findings(project_id, base))
    findings.extend(backlog_lifecycle_findings(project_id))
    findings.extend(knowledge_staleness_findings(project_id))
    privacy = backlog_privacy_findings(project_id)
    findings.extend(privacy["findings"])
    warnings.extend(privacy["warnings"])
    findings.extend(implementation_feedback_findings(project_id))

    verdict = "CLEAN" if not findings else "DIRTY"
    report_path = base / "06_traceability" / "health_report.md"
    report_path.write_text(render_health(project_id, verdict, findings, warnings), encoding="utf-8")
    write_json(
        base / "06_traceability" / "health_report.json",
        {
            "verdict": verdict,
            "findings": findings,
            "warnings": warnings,
            "memory_backend": broker.backend,
            "memory_backend_degradation_reason": broker.lancedb_degraded_reason or None,
        },
    )
    update_state(project_id, health=verdict)
    return {
        "verdict": verdict,
        "findings": findings,
        "warnings": warnings,
        "memory": str(memory_path(project_id)),
        "memory_backend": broker.backend,
        "memory_backend_degradation_reason": broker.lancedb_degraded_reason or None,
    }


def render_health(project_id: str, verdict: str, findings: list[str], warnings: list[str] | None = None) -> str:
    rows = "\n".join(f"- {finding}" for finding in findings) or "- No findings."
    warning_rows = "\n".join(f"- {warning}" for warning in (warnings or [])) or "- No warnings."
    return f"""# Health Report - {project_id}

- Verdict: `{verdict}`

## Findings

{rows}

## Warnings

{warning_rows}
"""


def domain_context_freshness_findings(project_id: str, base) -> list[str]:
    readiness_path = base / "08_context_packs" / "implementation_readiness.json"
    backlog_path = base / "08_context_packs" / "backlog_generation.json"
    snapshot = {}
    if readiness_path.exists():
        readiness_pack = read_json(readiness_path, {})
        snapshot = readiness_pack.get("generated_from", {}).get("domain_context_snapshot", {})
    elif backlog_path.exists():
        backlog_pack = read_json(backlog_path, {})
        snapshot = backlog_pack.get("domain_context_snapshot", {})
    if not snapshot:
        return []

    current = domain_context_snapshot(project_id)
    if current.get("aggregate_hash") == snapshot.get("aggregate_hash"):
        return []
    changed_domains = sorted(
        domain
        for domain, payload in current.get("domains", {}).items()
        if payload.get("aggregate_hash") != snapshot.get("domains", {}).get(domain, {}).get("aggregate_hash")
    )
    detail = f" Changed domains: {', '.join(changed_domains)}." if changed_domains else ""
    return [
        "Domain context changed after backlog generation; run /reindex and retrieve focused context before implementation handoff. Regenerate backlog only if the change materially affects story scope, sequencing, acceptance, or execution contracts." + detail
    ]


def backlog_lifecycle_findings(project_id: str) -> list[str]:
    state = read_json(workspace_path(project_id) / "state.json", {})
    lifecycle = state.get("story_lifecycle", {})
    if not isinstance(lifecycle, dict):
        return []
    stale = sorted(story_id for story_id, item in lifecycle.items() if isinstance(item, dict) and item.get("status") == "Stale")
    if not stale:
        return []
    return ["Backlog contains Stale stories after source changes: " + ", ".join(stale) + "."]


def knowledge_staleness_findings(project_id: str) -> list[str]:
    state = read_json(workspace_path(project_id) / "state.json", {})
    payload = state.get("knowledge_staleness", {})
    if not isinstance(payload, dict):
        return []
    artifacts = [str(item) for item in payload.get("downstream_artifacts", []) if item]
    units = [str(item) for item in payload.get("impacted_knowledge_units", []) if item]
    if not artifacts:
        return []
    detail = f" Impacted knowledge units: {', '.join(units)}." if units else ""
    return [
        "Knowledge changed after downstream artifacts were generated; refresh affected brief/PRD/spec/backlog before implementation handoff."
        + detail
    ]


def backlog_privacy_findings(project_id: str) -> dict[str, list[str]]:
    result = evaluate_backlog_privacy(project_id)
    messages = [
        f"Backlog privacy scan finding in {item['path']}:{item['line']} ({item['pattern']})."
        for item in result["findings"]
    ]
    if result["verdict"] == "BLOCKED":
        return {"findings": messages, "warnings": []}
    return {"findings": [], "warnings": messages}


def implementation_feedback_findings(project_id: str) -> list[str]:
    state = read_json(workspace_path(project_id) / "state.json", {})
    payload = state.get("implementation_feedback", {})
    open_by_story = payload.get("open_by_story", {}) if isinstance(payload, dict) else {}
    if not isinstance(open_by_story, dict) or not open_by_story:
        return []
    return [
        "Open implementation feedback blocks DoD for "
        + ", ".join(f"{story} ({len(ids)})" for story, ids in sorted(open_by_story.items()))
        + "."
    ]


def has_blocking_open_gap(text: str, severities: set[str] | None = None) -> bool:
    blocking = severities or blocking_severities({})
    for gap in parse_gap_table(text, include_legacy=True):
        if is_blocking(gap, blocking):
            return True
    return False
