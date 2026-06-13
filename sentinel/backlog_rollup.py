from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .workspace import read_json, state_path, update_state, workspace_path


STATUSES = ("Draft", "Ready", "In Progress", "In Review", "Done", "Blocked", "Stale")


def backlog_status(project_id: str, write: bool = True) -> dict[str, Any]:
    base = workspace_path(project_id)
    stories = collect_story_rows(project_id)
    epics = rollup_by_epic(stories)
    summary = rollup_summary(stories, epics)
    path = base / "04_backlog" / "BACKLOG.md"
    if write:
        path.write_text(render_backlog_board(project_id, summary, epics, stories), encoding="utf-8")
        update_state(project_id, backlog_rollup=summary, backlog_board_path=path.relative_to(base).as_posix())
    return {
        "project_id": project_id,
        "path": str(path.as_posix()),
        "summary": summary,
        "epics": epics,
        "stories": stories,
    }


def collect_story_rows(project_id: str) -> list[dict[str, Any]]:
    base = workspace_path(project_id)
    state = read_json(state_path(project_id), {})
    lifecycle = state.get("story_lifecycle", {}) if isinstance(state.get("story_lifecycle", {}), dict) else {}
    gates = state.get("story_gates", {}) if isinstance(state.get("story_gates", {}), dict) else {}
    readiness = readiness_by_story(project_id)
    rows: list[dict[str, Any]] = []
    for path in sorted((base / "04_backlog").glob("US-*.md")) if (base / "04_backlog").exists() else []:
        story_id = path.stem
        text = path.read_text(encoding="utf-8")
        frontmatter = parse_frontmatter(text)
        item = readiness.get(story_id, {})
        life = lifecycle.get(story_id, {}) if isinstance(lifecycle.get(story_id), dict) else {}
        gate = gates.get(story_id, {}) if isinstance(gates.get(story_id), dict) else {}
        status = str(life.get("status") or item.get("story_status") or frontmatter.get("status") or "Draft")
        owner = str(life.get("owner") or item.get("owner") or frontmatter.get("owner") or "").strip()
        rows.append(
            {
                "story_id": story_id,
                "title": story_title(text, story_id),
                "epic_id": str(frontmatter.get("parent_epic") or "EPIC-001"),
                "status": status if status in STATUSES else "Draft",
                "owner": owner,
                "readiness_score": float(item.get("readiness_score", 0.0) or 0.0),
                "readiness": str(item.get("readiness", "")),
                "pending": [str(value) for value in item.get("pending", [])],
                "dor_passed": bool(gate.get("dor", {}).get("passed", item.get("dor", {}).get("passed", False))) if isinstance(gate.get("dor", item.get("dor", {})), dict) else False,
                "dod_passed": bool(gate.get("dod", {}).get("passed", item.get("dod", {}).get("passed", False))) if isinstance(gate.get("dod", item.get("dod", {})), dict) else False,
                "dor_missing": missing_from_gate(gate, item, "dor"),
                "dod_missing": missing_from_gate(gate, item, "dod"),
                "dependencies": [str(value) for value in item.get("dependencies", [])],
                "source_unit": str(item.get("source_unit", "")),
                "path": path.relative_to(base).as_posix(),
            }
        )
    return rows


def readiness_by_story(project_id: str) -> dict[str, dict[str, Any]]:
    path = workspace_path(project_id) / "08_context_packs" / "implementation_readiness.json"
    pack = read_json(path, {})
    stories = pack.get("stories", []) if isinstance(pack, dict) else []
    return {
        str(item.get("story_id")): item
        for item in stories
        if isinstance(item, dict) and item.get("story_id")
    }


def missing_from_gate(gate: dict[str, Any], item: dict[str, Any], key: str) -> list[str]:
    source = gate.get(key, {}) if isinstance(gate, dict) else {}
    if not isinstance(source, dict):
        source = item.get(key, {}) if isinstance(item.get(key, {}), dict) else {}
    return [str(value) for value in source.get("missing", [])]


def parse_frontmatter(text: str) -> dict[str, str]:
    if not text.startswith("---\n"):
        return {}
    end = text.find("\n---", 4)
    if end == -1:
        return {}
    data: dict[str, str] = {}
    for raw in text[4:end].splitlines():
        if ":" not in raw or raw.startswith("  "):
            continue
        key, value = raw.split(":", 1)
        data[key.strip()] = value.strip().strip('"')
    return data


def story_title(text: str, fallback: str) -> str:
    for line in text.splitlines():
        if line.startswith("# "):
            title = line[2:].strip()
            return re.sub(r"^US-\d{3}\s*-\s*", "", title) or fallback
    return fallback


def rollup_by_epic(stories: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    epics: dict[str, dict[str, Any]] = {}
    for story in stories:
        epic_id = str(story.get("epic_id", "EPIC-001"))
        epic = epics.setdefault(epic_id, new_epic_rollup(epic_id))
        epic["stories_total"] += 1
        epic["status_counts"][story["status"]] = epic["status_counts"].get(story["status"], 0) + 1
        if story["status"] == "Ready":
            epic["ready_count"] += 1
        if story["status"] == "Done":
            epic["done_count"] += 1
        if story["owner"]:
            epic["owners"].append(story["owner"])
        blockers = story_blockers(story)
        if blockers:
            epic["blockers"].append({"story_id": story["story_id"], "items": blockers})
        epic["readiness_scores"].append(float(story.get("readiness_score", 0.0)))
    for epic in epics.values():
        total = max(int(epic["stories_total"]), 1)
        epic["ready_percent"] = round(int(epic["ready_count"]) / total, 3)
        epic["done_percent"] = round(int(epic["done_count"]) / total, 3)
        scores = epic.pop("readiness_scores")
        epic["avg_readiness_score"] = round(sum(scores) / len(scores), 3) if scores else 0.0
        epic["owners"] = sorted(set(epic["owners"]))
    return dict(sorted(epics.items()))


def new_epic_rollup(epic_id: str) -> dict[str, Any]:
    return {
        "epic_id": epic_id,
        "stories_total": 0,
        "status_counts": {status: 0 for status in STATUSES},
        "ready_count": 0,
        "done_count": 0,
        "ready_percent": 0.0,
        "done_percent": 0.0,
        "avg_readiness_score": 0.0,
        "owners": [],
        "blockers": [],
        "readiness_scores": [],
    }


def rollup_summary(stories: list[dict[str, Any]], epics: dict[str, dict[str, Any]]) -> dict[str, Any]:
    counts = {status: 0 for status in STATUSES}
    for story in stories:
        counts[story["status"]] = counts.get(story["status"], 0) + 1
    total = len(stories)
    scores = [float(story.get("readiness_score", 0.0)) for story in stories]
    return {
        "stories_total": total,
        "epics_total": len(epics),
        "status_counts": counts,
        "ready_percent": round(counts.get("Ready", 0) / total, 3) if total else 0.0,
        "done_percent": round(counts.get("Done", 0) / total, 3) if total else 0.0,
        "avg_readiness_score": round(sum(scores) / len(scores), 3) if scores else 0.0,
        "blocker_count": sum(1 for story in stories if story_blockers(story)),
        "owners": sorted({story["owner"] for story in stories if story.get("owner")}),
    }


def story_blockers(story: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    blockers.extend(str(item) for item in story.get("pending", []))
    blockers.extend(f"DoR: {item}" for item in story.get("dor_missing", []))
    if story.get("status") == "Done":
        blockers.extend(f"DoD: {item}" for item in story.get("dod_missing", []))
    return blockers


def render_backlog_board(
    project_id: str,
    summary: dict[str, Any],
    epics: dict[str, dict[str, Any]],
    stories: list[dict[str, Any]],
) -> str:
    return f"""# Backlog Board - {project_id}

This board is generated from `state.json`, `04_backlog/US-NNN.md`, and `08_context_packs/implementation_readiness.json`. It is a review view, not a second source of truth. Update story state through `/story-status`.

## Summary

| Stories | Epics | Ready | Done | Avg Readiness | Stories With Blockers | Owners |
| --- | --- | --- | --- | --- | --- | --- |
| {summary['stories_total']} | {summary['epics_total']} | {percent(summary['ready_percent'])} | {percent(summary['done_percent'])} | {summary['avg_readiness_score']:.3f} | {summary['blocker_count']} | {', '.join(summary['owners']) or 'N/A'} |

## Epic Rollup

{render_epic_rollup_table(epics)}

## Board By Status

{render_status_board(stories)}
"""


def render_epic_rollup_table(epics: dict[str, dict[str, Any]]) -> str:
    if not epics:
        return "| Epic | Stories | Ready | Done | Avg Readiness | Owners | Blockers |\n| --- | --- | --- | --- | --- | --- | --- |\n| N/A | 0 | 0% | 0% | 0.000 | N/A | 0 |"
    rows = []
    for epic in epics.values():
        rows.append(
            "| {epic} | {total} | {ready} | {done} | {score:.3f} | {owners} | {blockers} |".format(
                epic=epic["epic_id"],
                total=epic["stories_total"],
                ready=percent(epic["ready_percent"]),
                done=percent(epic["done_percent"]),
                score=epic["avg_readiness_score"],
                owners=", ".join(epic["owners"]) or "N/A",
                blockers=len(epic["blockers"]),
            )
        )
    return "| Epic | Stories | Ready | Done | Avg Readiness | Owners | Blockers |\n| --- | --- | --- | --- | --- | --- | --- |\n" + "\n".join(rows)


def render_status_board(stories: list[dict[str, Any]]) -> str:
    blocks = []
    for status in STATUSES:
        rows = [story for story in stories if story["status"] == status]
        blocks.append(f"### {status}\n\n{render_story_table(rows)}")
    return "\n\n".join(blocks)


def render_story_table(stories: list[dict[str, Any]]) -> str:
    if not stories:
        return "| Story | Epic | Owner | Readiness | Blockers |\n| --- | --- | --- | --- | --- |\n| N/A | N/A | N/A | N/A | N/A |"
    rows = []
    for story in stories:
        blockers = story_blockers(story)
        rows.append(
            "| `{story}` | {epic} | {owner} | {score:.3f} | {blockers} |".format(
                story=story["story_id"],
                epic=story["epic_id"],
                owner=story["owner"] or "N/A",
                score=float(story.get("readiness_score", 0.0)),
                blockers="; ".join(blockers) if blockers else "None",
            )
        )
    return "| Story | Epic | Owner | Readiness | Blockers |\n| --- | --- | --- | --- | --- |\n" + "\n".join(rows)


def percent(value: float) -> str:
    return f"{round(value * 100, 1)}%"
