from __future__ import annotations

from pathlib import Path

from .ids import prefix_for_node_type
from .traceability import load_graph, parents_of
from .workspace import state_path, workspace_path


def validate_project(project_id: str) -> dict[str, object]:
    findings: list[str] = []
    base = workspace_path(project_id)
    if not base.exists():
        return {"verdict": "INVALID", "findings": [f"Workspace does not exist: {project_id}"]}
    if not state_path(project_id).exists():
        findings.append("Missing state.json.")
    config = base / "sentinel.config.yaml"
    if not config.exists():
        findings.append("Missing sentinel.config.yaml.")

    graph = load_graph(project_id)
    node_ids = set()
    for node in graph.get("nodes", []):
        node_id = node.get("id", "")
        node_type = node.get("type", "")
        expected_prefix = prefix_for_node_type(node_type)
        if expected_prefix and not node_id.startswith(f"{expected_prefix}-"):
            findings.append(f"{node_id} prefix does not match type {node_type}.")
        if node_id in node_ids:
            findings.append(f"Duplicate node id: {node_id}.")
        node_ids.add(node_id)
        path_value = node.get("path")
        if path_value and not resolve_path(base, path_value).exists():
            findings.append(f"{node_id} points to missing artifact: {path_value}.")

    for edge in graph.get("edges", []):
        if edge.get("from") not in node_ids:
            findings.append(f"Edge source missing: {edge.get('from')}.")
        if edge.get("to") not in node_ids:
            findings.append(f"Edge target missing: {edge.get('to')}.")

    findings.extend(validate_semantic_artifacts(project_id, base, graph))

    verdict = "VALID" if not findings else "INVALID"
    return {"verdict": verdict, "findings": findings}


def resolve_path(base: Path, path_value: str) -> Path:
    path = Path(path_value)
    if path.is_absolute():
        return path
    candidate = Path.cwd() / path
    if candidate.exists():
        return candidate
    return base / path


def validate_semantic_artifacts(project_id: str, base: Path, graph: dict) -> list[str]:
    findings: list[str] = []
    node_types = {node.get("type") for node in graph.get("nodes", [])}
    if "raw_input" in node_types:
        for required in ("identity_seed_bank", "discovery_log", "lens_review", "gap_report", "requirement"):
            if required not in node_types:
                findings.append(f"Discovery artifact missing after raw input: {required}.")

    spec_path = base / "03_specs" / "prd_ai_friendly.md"
    if spec_path.exists():
        spec_text = spec_path.read_text(encoding="utf-8")
        for section in ("Jobs To Be Done", "Domain Context Retrieved From Memory", "Acceptance Strategy", "Traceability"):
            if section not in spec_text:
                findings.append(f"PRD missing section: {section}.")

    for story in [node for node in graph.get("nodes", []) if node.get("type") == "user_story"]:
        story_path = resolve_path(base, story.get("path", ""))
        if not story_path.exists():
            continue
        story_text = story_path.read_text(encoding="utf-8")
        for section in ("JTBD", "Acceptance Criteria", "Readiness Checklist"):
            if section not in story_text:
                findings.append(f"{story['id']} missing story readiness signal: {section}.")
        if not parents_of(project_id, story["id"]):
            findings.append(f"{story['id']} has no upstream parent.")

    if "user_story" in node_types and "backlog_readiness_audit" not in node_types:
        findings.append("Backlog exists without backlog_readiness_audit.")
    gaps_path = base / "01_discovery" / "gaps.md"
    if gaps_path.exists() and "CLOSED" in gaps_path.read_text(encoding="utf-8"):
        resolution_log = base / "01_discovery" / "gap_resolution_log.md"
        if not resolution_log.exists():
            findings.append("Closed gaps exist without gap_resolution_log.md.")
    return findings
