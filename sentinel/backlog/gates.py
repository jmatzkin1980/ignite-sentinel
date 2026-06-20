from __future__ import annotations

from pathlib import Path
from typing import Any

from ..discovery import parse_gap_rows
from ..implementation_feedback import open_feedback_for_story
from ..core.graph import add_edge, add_node
from ..workspace import load_config, read_json, state_path, update_state, workspace_path


BACKLOG_GATE_DEFAULT_THRESHOLD = 1.0
BLOCKING_GAP_STATUSES = {"OPEN", "ANSWERED", "PARTIALLY_CLOSED"}
REQUIRED_AC_CLASSES = {"fail-to-pass", "pass-to-pass", "evidence"}


def backlog_gate_config(project_id: str) -> dict[str, Any]:
    config = load_config(project_id)
    gate = config.get("backlog_gate", {}) if isinstance(config.get("backlog_gate", {}), dict) else {}
    return {
        "threshold": float(gate.get("threshold", BACKLOG_GATE_DEFAULT_THRESHOLD)),
        "strict": bool(gate.get("strict", False)),
    }


def evaluate_story_gates(
    project_id: str,
    story: dict[str, Any],
    readiness_item: dict[str, Any] | None = None,
) -> dict[str, Any]:
    story_id = str(story.get("id") or story.get("story_id") or "")
    readiness = readiness_item or {}
    acceptance = story.get("acceptance", [])
    if not isinstance(acceptance, list):
        acceptance = []
    owner = str(story.get("owner") or readiness.get("owner") or "").strip()
    trace = [str(item) for item in story.get("trace", readiness.get("trace", [])) if str(item).strip()]
    gate = backlog_gate_config(project_id)
    readiness_score = float(readiness.get("readiness_score", story.get("readiness_score", 0.0)) or 0.0)
    readiness_label = str(readiness.get("readiness", story.get("readiness", "")))
    ac_classes = {str(item.get("classification", "")).strip() for item in acceptance if isinstance(item, dict)}
    blocking_gaps = blocking_gaps_for_trace(project_id, trace)
    evidence = acceptance_evidence_for_story(project_id, story_id)
    story_quality = story_quality_for_story(project_id, story_id)
    implementation_feedback = open_feedback_for_story(project_id, story_id)

    dor_items = [
        check_item(
            "acceptance_criteria_classified",
            REQUIRED_AC_CLASSES.issubset(ac_classes),
            "Acceptance criteria must include fail-to-pass, pass-to-pass, and evidence classifications.",
        ),
        check_item(
            "readiness_score",
            readiness_score >= gate["threshold"] and readiness_label == "Ready With Domain Evidence",
            (
                "Implementation readiness must be Ready With Domain Evidence "
                f"and score >= {gate['threshold']:.2f}; current score is {readiness_score:.2f}."
            ),
            score=readiness_score,
        ),
        check_item(
            "no_blocking_trace_gaps",
            not blocking_gaps,
            "No open blocking GAP-* may touch this story trace.",
            gaps=blocking_gaps,
        ),
        check_item(
            "slicing_pattern_assigned",
            bool(str(story.get("slicing", readiness.get("slicing", ""))).strip())
            and "[PENDING INPUT]" not in str(story.get("slicing", readiness.get("slicing", ""))),
            "A slicing pattern must be assigned from the governed backlog slicing model.",
        ),
        check_item(
            "owner_assigned",
            bool(owner),
            "Assign a human owner with /story-status --owner before treating the story as Ready.",
        ),
    ]
    if story_quality:
        dor_items.append(
            check_item(
                "story_quality_invest",
                bool(story_quality.get("score", 0.0) >= story_quality.get("threshold", 0.8)),
                "Quality audit must pass the governed INVEST/SPIDR story quality threshold.",
                score=story_quality.get("score", 0.0),
                status=story_quality.get("status", "UNKNOWN"),
                warnings=story_quality.get("warnings", []),
            )
        )
    dod_items = [
        check_item(
            "acceptance_evidence_traced",
            bool(evidence),
            "Attach traced downstream acceptance evidence before treating the story as Done.",
            evidence=evidence,
        ),
        check_item(
            "implementation_feedback_resolved",
            not implementation_feedback,
            "Resolve open implementation feedback before treating the story as Done.",
            feedback=implementation_feedback,
        ),
        check_item(
            "ready_gate_passed",
            all(item["passed"] for item in dor_items),
            "DoR must pass before DoD can pass.",
        ),
    ]
    dor_passed = all(item["passed"] for item in dor_items)
    dod_passed = all(item["passed"] for item in dod_items)
    return {
        "story_id": story_id,
        "threshold": gate["threshold"],
        "strict": gate["strict"],
        "dor": {"passed": dor_passed, "items": dor_items, "missing": missing_messages(dor_items)},
        "dod": {"passed": dod_passed, "items": dod_items, "missing": missing_messages(dod_items)},
    }


def check_item(key: str, passed: bool, missing: str, **extra: Any) -> dict[str, Any]:
    item = {"key": key, "passed": bool(passed), "missing": "" if passed else missing}
    item.update(extra)
    return item


def missing_messages(items: list[dict[str, Any]]) -> list[str]:
    return [str(item["missing"]) for item in items if not item.get("passed") and item.get("missing")]


def blocking_gaps_for_trace(project_id: str, trace: list[str]) -> list[str]:
    if not trace:
        return []
    config = load_config(project_id)
    blocking = set(config.get("maturity", {}).get("blocking_gap_severities", ["critical", "high"]))
    path = workspace_path(project_id) / "01_discovery" / "gaps.md"
    gaps = parse_gap_rows(path.read_text(encoding="utf-8")) if path.exists() else []
    trace_tokens = {item for item in trace if item.startswith("GAP-")}
    result: list[str] = []
    for gap in gaps:
        gap_id = str(gap.get("id", "")).strip("`")
        severity = str(gap.get("severity", "")).lower()
        status = str(gap.get("status", "OPEN")).upper()
        if severity in blocking and status in BLOCKING_GAP_STATUSES and (gap_id in trace_tokens or not trace_tokens):
            result.append(gap_id)
    return result


def acceptance_evidence_for_story(project_id: str, story_id: str) -> list[dict[str, str]]:
    state = read_json(state_path(project_id), {})
    evidence = state.get("story_acceptance_evidence", {})
    entries = evidence.get(story_id, []) if isinstance(evidence, dict) else []
    if not isinstance(entries, list):
        return []
    return [
        {"path": str(item.get("path", "")), "trace_id": str(item.get("trace_id", ""))}
        for item in entries
        if isinstance(item, dict) and item.get("path")
    ]


def story_quality_for_story(project_id: str, story_id: str) -> dict[str, Any]:
    state = read_json(state_path(project_id), {})
    quality = state.get("story_quality", {})
    if isinstance(quality, dict) and isinstance(quality.get(story_id), dict):
        return quality[story_id]
    return {}


def register_acceptance_evidence(project_id: str, story_id: str, source: Path) -> dict[str, str]:
    base = workspace_path(project_id)
    source = source.resolve()
    if not source.exists() or not source.is_file():
        raise RuntimeError(f"Acceptance evidence file does not exist: {source}")
    target_dir = base / "04_backlog" / "acceptance_evidence"
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"{story_id}-{source.name}"
    target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    trace_id = add_node(
        project_id,
        "EV",
        "story_acceptance_evidence",
        target,
        f"Acceptance evidence for {story_id}",
        status="accepted",
        domain="quality",
    )
    story_node = story_node_id(project_id, story_id)
    if story_node:
        add_edge(project_id, trace_id, story_node, "acceptance_evidence_for")
    state = read_json(state_path(project_id), {})
    evidence = state.get("story_acceptance_evidence", {})
    if not isinstance(evidence, dict):
        evidence = {}
    entries = evidence.setdefault(story_id, [])
    if isinstance(entries, list):
        entries.append({"path": target.relative_to(base).as_posix(), "trace_id": trace_id})
    update_state(project_id, story_acceptance_evidence=evidence)
    return {"path": target.relative_to(base).as_posix(), "trace_id": trace_id}


def story_node_id(project_id: str, story_id: str) -> str:
    graph = read_json(workspace_path(project_id) / "06_traceability" / "traceability_graph.json", {})
    for node in graph.get("nodes", []):
        if str(node.get("type")) != "user_story":
            continue
        if str(node.get("path", "")).endswith(f"04_backlog/{story_id}.md"):
            return str(node.get("id", ""))
    return ""


def update_story_gate_state(project_id: str, story_id: str, gate_result: dict[str, Any]) -> None:
    state = read_json(state_path(project_id), {})
    gates = state.get("story_gates", {})
    if not isinstance(gates, dict):
        gates = {}
    gates[story_id] = gate_result
    update_state(project_id, story_gates=gates, last_story_gate_update=story_id)


def story_gate_from_readiness(project_id: str, story_id: str) -> dict[str, Any] | None:
    state = read_json(state_path(project_id), {})
    gates = state.get("story_gates", {})
    if isinstance(gates, dict) and isinstance(gates.get(story_id), dict):
        return gates[story_id]
    return None
