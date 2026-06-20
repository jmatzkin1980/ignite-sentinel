from __future__ import annotations

from collections import defaultdict
from typing import Any

from .backlog.hooks import enforce_pre_handoff_gate
from .memory import ContextBroker
from .workspace import workspace_path, write_json


def generate_slice_plan(
    project_id: str,
    stories: list[dict[str, Any]],
    readiness_pack: dict[str, Any],
) -> dict[str, Any]:
    """Write the deterministic backlog handoff plan for downstream agents."""
    base = workspace_path(project_id)
    story_rows = build_story_rows(stories, readiness_pack)
    phases = build_phases(story_rows)
    handoff_packs = build_handoff_packs(story_rows)
    pre_handoff = enforce_pre_handoff_gate(project_id, readiness_pack)
    plan = {
        "project_id": project_id,
        "workflow": "slice_plan",
        "generated_from": {
            "backlog": "04_backlog/",
            "implementation_readiness": "08_context_packs/implementation_readiness.json",
        },
        "rule": (
            "Ignite exposes ordering, checkpoints, and per-story handoff context; "
            "it does not create or execute downstream tasking."
        ),
        "summary": {
            "stories_total": len(story_rows),
            "enablers_total": sum(1 for item in story_rows if item["type"] == "cross_cutting_enabler"),
            "value_stories_total": sum(1 for item in story_rows if item["type"] != "cross_cutting_enabler"),
            "waves_total": len(phases["implementation_waves"]),
        },
        "phases": phases,
        "handoff_packs": handoff_packs,
        "pre_handoff_gate": pre_handoff,
        "checkpoints": build_checkpoints(phases),
    }
    md_path = base / "04_backlog" / "SLICE-PLAN.md"
    json_path = base / "08_context_packs" / "slice_plan.json"
    md_path.write_text(render_slice_plan(project_id, plan), encoding="utf-8")
    write_json(json_path, plan)
    ContextBroker(project_id).index_artifact(
        "SLICE-PLAN",
        "slice_plan",
        md_path,
        md_path.read_text(encoding="utf-8"),
        domain="delivery",
        trace_ids=[item["story_id"] for item in story_rows] or ["SLICE-PLAN"],
    )
    ContextBroker(project_id).index_artifact(
        "SLICE-PLAN-JSON",
        "slice_plan",
        json_path,
        json_path.read_text(encoding="utf-8"),
        domain="delivery",
        trace_ids=[item["story_id"] for item in story_rows] or ["SLICE-PLAN"],
    )
    return {
        "path": str(md_path.as_posix()),
        "json_path": str(json_path.as_posix()),
        "plan": plan,
    }


def build_story_rows(stories: list[dict[str, Any]], readiness_pack: dict[str, Any]) -> list[dict[str, Any]]:
    readiness_by_id = {
        str(item.get("story_id")): item
        for item in readiness_pack.get("stories", [])
        if isinstance(item, dict) and item.get("story_id")
    }
    rows: list[dict[str, Any]] = []
    for story in stories:
        story_id = str(story.get("id", ""))
        readiness = readiness_by_id.get(story_id, {})
        execution = readiness.get("execution_contract", story.get("execution_contract", {}))
        dependencies = [str(item) for item in story.get("dependencies", [])]
        enables = [str(item) for item in story.get("enables", [])]
        rows.append(
            {
                "story_id": story_id,
                "title": str(story.get("title", story_id)),
                "type": str(story.get("type", "value_story")),
                "source_unit": str(readiness.get("source_unit", story.get("source_unit", ""))),
                "dependencies": dependencies,
                "enables": enables,
                "readiness_score": float(readiness.get("readiness_score", 0.0) or 0.0),
                "readiness": str(readiness.get("readiness", "")),
                "story_status": str(readiness.get("story_status", story.get("status", "Draft"))),
                "owner": str(readiness.get("owner", story.get("owner", ""))),
                "pending": [str(item) for item in readiness.get("pending", [])],
                "dor": readiness.get("dor", {}),
                "dod": readiness.get("dod", {}),
                "execution_contract": execution if isinstance(execution, dict) else {},
                "retrieval_plan": readiness.get("retrieval_plan", execution.get("retrieval_plan", []) if isinstance(execution, dict) else []),
                "validation": readiness.get("validation", execution.get("validation", {}) if isinstance(execution, dict) else {}),
                "trace": readiness.get("trace", story.get("trace", [])),
                "context_pack": readiness.get("context_pack", story.get("context_pack", "08_context_packs/backlog_generation.json")),
                "context_pack_section": readiness.get("context_pack_section", story.get("context_pack_section", "")),
            }
        )
    return rows


def build_phases(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_id = {item["story_id"]: item for item in rows}
    enablers = [item for item in rows if item["type"] == "cross_cutting_enabler"]
    value_items = [item for item in rows if item["type"] != "cross_cutting_enabler"]
    prerequisites = story_prerequisites(rows)
    positions: dict[str, dict[str, Any]] = {}
    for order, item in enumerate(enablers, start=1):
        positions[item["story_id"]] = {
            "phase": "enablers",
            "wave": 0,
            "order": order,
            "parallel_group": "EPIC-002",
            "prerequisites": sorted(prerequisites.get(item["story_id"], set())),
        }
    done = {item["story_id"] for item in enablers}
    remaining = {item["story_id"] for item in value_items}
    waves: list[dict[str, Any]] = []
    wave_number = 1
    while remaining:
        ready = sorted(
            story_id
            for story_id in remaining
            if prerequisites.get(story_id, set()).issubset(done)
        )
        if not ready:
            ready = sorted(remaining)
        wave_items = []
        for order, story_id in enumerate(ready, start=1):
            item = by_id[story_id]
            missing = sorted(prerequisites.get(story_id, set()) - done)
            positions[story_id] = {
                "phase": "implementation",
                "wave": wave_number,
                "order": order,
                "parallel_group": f"wave-{wave_number:02d}",
                "prerequisites": sorted(prerequisites.get(story_id, set())),
                "blocked_by": missing,
            }
            wave_items.append(story_plan_row(item, positions[story_id]))
        waves.append({"wave": wave_number, "stories": wave_items})
        remaining.difference_update(ready)
        done.update(ready)
        wave_number += 1
    return {
        "enabler_phase": [story_plan_row(item, positions[item["story_id"]]) for item in enablers],
        "implementation_waves": waves,
        "positions": positions,
    }


def story_prerequisites(rows: list[dict[str, Any]]) -> dict[str, set[str]]:
    prerequisites: dict[str, set[str]] = defaultdict(set)
    known = {item["story_id"] for item in rows}
    for item in rows:
        story_id = item["story_id"]
        for dependency in item.get("dependencies", []):
            if dependency in known:
                prerequisites[story_id].add(dependency)
        if item["type"] == "cross_cutting_enabler":
            for enabled in item.get("enables", []):
                if enabled in known:
                    prerequisites[enabled].add(story_id)
    return prerequisites


def story_plan_row(item: dict[str, Any], position: dict[str, Any]) -> dict[str, Any]:
    return {
        "story_id": item["story_id"],
        "title": item["title"],
        "type": item["type"],
        "source_unit": item["source_unit"],
        "position": position,
        "story_status": item["story_status"],
        "owner": item["owner"],
        "readiness_score": item["readiness_score"],
        "dor_status": gate_status(item.get("dor", {})),
        "pending": item.get("pending", []),
    }


def build_handoff_packs(rows: list[dict[str, Any]]) -> dict[str, Any]:
    phases = build_phases(rows)
    positions = phases["positions"]
    packs: dict[str, Any] = {}
    for item in rows:
        story_id = item["story_id"]
        packs[story_id] = {
            "story_id": story_id,
            "position": positions.get(story_id, {}),
            "story_status": item["story_status"],
            "owner": item["owner"],
            "readiness_score": item["readiness_score"],
            "dor": item.get("dor", {}),
            "dod": item.get("dod", {}),
            "pending": item.get("pending", []),
            "dependencies": item.get("dependencies", []),
            "enables": item.get("enables", []),
            "execution_contract": item.get("execution_contract", {}),
            "retrieval_plan": item.get("retrieval_plan", []),
            "anchors": collect_anchors(item.get("execution_contract", {})),
            "validation": item.get("validation", {}),
            "trace": item.get("trace", []),
            "context_pack": item.get("context_pack", ""),
            "context_pack_section": item.get("context_pack_section", ""),
        }
    return packs


def build_checkpoints(phases: dict[str, Any]) -> list[dict[str, Any]]:
    checkpoints: list[dict[str, Any]] = []
    enablers = phases.get("enabler_phase", [])
    if enablers:
        checkpoints.append(
            {
                "id": "CHK-ENABLERS",
                "after": "enablers",
                "objective": "Confirm concrete EPIC-002 enablers are accepted or explicitly stubbed before dependent value stories start.",
                "stories": [item["story_id"] for item in enablers],
            }
        )
    for wave in phases.get("implementation_waves", []):
        wave_id = int(wave.get("wave", 0))
        checkpoints.append(
            {
                "id": f"CHK-WAVE-{wave_id:02d}",
                "after": f"wave-{wave_id:02d}",
                "objective": "Review DoR, validation evidence, blockers, and traceability before the next wave starts.",
                "stories": [item["story_id"] for item in wave.get("stories", [])],
            }
        )
    return checkpoints


def collect_anchors(value: object) -> list[dict[str, Any]]:
    anchors: list[dict[str, Any]] = []
    if isinstance(value, dict):
        if {"source_path", "line_start", "line_end"}.issubset(value):
            anchors.append(value)
        for item in value.values():
            anchors.extend(collect_anchors(item))
    elif isinstance(value, list):
        for item in value:
            anchors.extend(collect_anchors(item))
    return anchors


def gate_status(gate: object) -> str:
    if isinstance(gate, dict) and gate.get("passed") is True:
        return "Ready"
    if isinstance(gate, dict) and gate.get("missing"):
        return "[PENDING DOR]"
    return "[PENDING DOR]"


def render_slice_plan(project_id: str, plan: dict[str, Any]) -> str:
    phases = plan["phases"]
    checkpoints = plan["checkpoints"]
    return f"""# Slice Plan - {project_id}

This plan is generated from `04_backlog/US-NNN.md`, `04_backlog/EPIC-002-cross-cutting-enablers.md` when present, and `08_context_packs/implementation_readiness.json`. It is a deterministic handoff contract for planning agents. Ignite does not create or execute downstream tasks here.

## Summary

| Stories | Enablers | Value Stories | Waves |
| --- | --- | --- | --- |
| {plan['summary']['stories_total']} | {plan['summary']['enablers_total']} | {plan['summary']['value_stories_total']} | {plan['summary']['waves_total']} |

## Phase 0 - Enablers

{render_story_plan_table(phases['enabler_phase'])}

## Implementation Waves

{render_waves(phases['implementation_waves'])}

## Checkpoints

{render_checkpoint_table(checkpoints)}

## Pre-Handoff Gate

{render_pre_handoff_gate(plan.get('pre_handoff_gate', {}))}

## Per-Story Handoff Packs

Machine-readable handoff packs live in `08_context_packs/slice_plan.json#handoff_packs`. Each pack carries position, DoR/DoD state, dependencies, execution contract, retrieval plan, anchors, validation contract and trace IDs.
"""


def render_waves(waves: list[dict[str, Any]]) -> str:
    if not waves:
        return "No implementation waves were generated."
    blocks = []
    for wave in waves:
        blocks.append(f"### Wave {wave['wave']}\n\n{render_story_plan_table(wave.get('stories', []))}")
    return "\n\n".join(blocks)


def render_story_plan_table(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "| Story | Type | Source | Prerequisites | DoR | Readiness | Owner |\n| --- | --- | --- | --- | --- | --- | --- |\n| N/A | N/A | N/A | N/A | N/A | N/A | N/A |"
    rendered = []
    for row in rows:
        position = row.get("position", {})
        prerequisites = ", ".join(position.get("prerequisites", [])) or "None"
        rendered.append(
            "| `{story}` | {type} | `{source}` | {prereq} | {dor} | {score:.3f} | {owner} |".format(
                story=row["story_id"],
                type=row["type"],
                source=row.get("source_unit") or "N/A",
                prereq=prerequisites,
                dor=row.get("dor_status", "[PENDING DOR]"),
                score=float(row.get("readiness_score", 0.0)),
                owner=row.get("owner") or "N/A",
            )
        )
    return "| Story | Type | Source | Prerequisites | DoR | Readiness | Owner |\n| --- | --- | --- | --- | --- | --- | --- |\n" + "\n".join(rendered)


def render_checkpoint_table(checkpoints: list[dict[str, Any]]) -> str:
    if not checkpoints:
        return "| Checkpoint | After | Stories | Objective |\n| --- | --- | --- | --- |\n| N/A | N/A | N/A | N/A |"
    rows = []
    for checkpoint in checkpoints:
        rows.append(
            "| `{id}` | {after} | {stories} | {objective} |".format(
                id=checkpoint["id"],
                after=checkpoint["after"],
                stories=", ".join(f"`{story}`" for story in checkpoint.get("stories", [])) or "N/A",
                objective=checkpoint["objective"],
            )
        )
    return "| Checkpoint | After | Stories | Objective |\n| --- | --- | --- | --- |\n" + "\n".join(rows)


def render_pre_handoff_gate(gate: dict[str, Any]) -> str:
    verdict = str(gate.get("verdict", "WARN"))
    mode = "strict" if gate.get("strict") else "soft"
    warnings = gate.get("warnings", [])
    if not warnings:
        return f"- Mode: `{mode}`\n- Verdict: `{verdict}`\n- DoR: all stories passed."
    rows = []
    for item in warnings:
        missing = "; ".join(str(value) for value in item.get("missing", [])) or "DoR has not passed."
        rows.append(f"| `{item.get('story_id', 'N/A')}` | {item.get('severity', 'warning')} | {missing} |")
    return (
        f"- Mode: `{mode}`\n- Verdict: `{verdict}`\n\n"
        "| Story | Severity | Missing DoR |\n| --- | --- | --- |\n" + "\n".join(rows)
    )
