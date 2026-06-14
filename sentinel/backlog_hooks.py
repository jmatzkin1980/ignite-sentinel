from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .backlog_gates import backlog_gate_config
from .backlog_rollup import backlog_status
from .backlog_status import append_status_log, story_lifecycle_state, update_story_frontmatter
from .traceability import add_edge, add_node
from .workspace import read_json, update_state, utc_now, workspace_path, write_json


SPEC_UNIT_RE = re.compile(r"\bSPEC-U-\d{3}\b")

BACKLOG_PRIVACY_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "credential_assignment",
        re.compile(
            r"\b(password|passwd|secret|api[_ -]?key|access[_ -]?token|refresh[_ -]?token|credential)\b\s*[:=]\s*\S+",
            re.IGNORECASE,
        ),
    ),
    ("auth_header", re.compile(r"\b(bearer|basic)\s+[A-Za-z0-9._~+/=-]{12,}", re.IGNORECASE)),
    (
        "external_endpoint",
        re.compile(r"\bhttps?://(?!localhost\b|127\.0\.0\.1\b|0\.0\.0\.0\b|example\.(com|org|net)\b)[^\s)>\]]+", re.IGNORECASE),
    ),
    ("email_address", re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)),
    (
        "private_identifier",
        re.compile(r"\b(account|tenant|customer|client)[ _-]?id\s*[:=]\s*[A-Za-z0-9_-]{6,}", re.IGNORECASE),
    ),
)


def stale_spec_units_from_change(source: Path, text: str) -> list[str]:
    units = set(SPEC_UNIT_RE.findall(text))
    if SPEC_UNIT_RE.fullmatch(source.stem):
        units.add(source.stem)
    return sorted(units)


def mark_stale_stories_for_spec_units(
    project_id: str,
    stale_spec_units: list[str],
    reason: str,
    change_id: str | None = None,
) -> dict[str, Any]:
    units = sorted({unit for unit in stale_spec_units if SPEC_UNIT_RE.fullmatch(str(unit))})
    if not units:
        return {"stale_spec_units": [], "stale_stories": []}

    base = workspace_path(project_id)
    readiness_path = base / "08_context_packs" / "implementation_readiness.json"
    readiness = read_json(readiness_path, {})
    stories = readiness.get("stories", []) if isinstance(readiness, dict) else []
    affected: list[dict[str, Any]] = []
    for item in stories if isinstance(stories, list) else []:
        if not isinstance(item, dict):
            continue
        story_units = story_spec_units(item)
        matched = sorted(story_units.intersection(units))
        if matched:
            affected.append({"story_id": str(item.get("story_id", "")), "units": matched, "readiness": item})

    if not affected:
        return {"stale_spec_units": units, "stale_stories": []}

    lifecycle = story_lifecycle_state(project_id)
    timestamp = utc_now()
    stale_story_ids: list[str] = []
    for match in affected:
        story_id = match["story_id"]
        if not story_id:
            continue
        previous = lifecycle.get(story_id, {})
        previous_status = str(previous.get("status", "Draft"))
        owner = str(previous.get("owner", "")).strip()
        lifecycle[story_id] = {
            "status": "Stale",
            "owner": owner,
            "updated_at": timestamp,
            "stale_reason": reason,
            "stale_spec_units": match["units"],
        }
        stale_story_ids.append(story_id)
        story_path = base / "04_backlog" / f"{story_id}.md"
        if story_path.exists():
            update_story_frontmatter(story_path, "Stale", owner)
            append_status_log(project_id, story_id, previous_status, "Stale", owner)
        readiness_item = match["readiness"]
        readiness_item["story_status"] = "Stale"
        readiness_item["staleness"] = {"reason": reason, "stale_spec_units": match["units"], "updated_at": timestamp}
        change_node = add_node(
            project_id,
            "CHG",
            "story_staleness",
            base / "04_backlog" / "status_log.md",
            f"{story_id} marked Stale by spec-unit change",
            status="applied",
            domain="delivery",
        )
        if change_id:
            add_edge(project_id, change_id, change_node, "triggers_story_staleness")
        add_edge(project_id, change_node, story_id, "marks_story_stale")

    update_state(
        project_id,
        story_lifecycle=lifecycle,
        last_story_staleness_update=timestamp,
        stale_stories={"reason": reason, "spec_units": units, "stories": stale_story_ids, "updated_at": timestamp},
    )
    if isinstance(readiness, dict):
        write_json(readiness_path, readiness)
    backlog_status(project_id)
    return {"stale_spec_units": units, "stale_stories": stale_story_ids}


def story_spec_units(item: dict[str, Any]) -> set[str]:
    units: set[str] = set()
    for value in (item.get("source_unit"), *item.get("trace", [])):
        if isinstance(value, str) and SPEC_UNIT_RE.fullmatch(value):
            units.add(value)
    return units


def pre_handoff_gate(project_id: str, readiness_pack: dict[str, Any]) -> dict[str, Any]:
    gate = backlog_gate_config(project_id)
    warnings: list[dict[str, Any]] = []
    for item in readiness_pack.get("stories", []) if isinstance(readiness_pack, dict) else []:
        if not isinstance(item, dict):
            continue
        story_id = str(item.get("story_id", "")).strip()
        dor = item.get("dor", {})
        missing = dor.get("missing", []) if isinstance(dor, dict) else []
        if dor.get("passed") is not True:
            warnings.append(
                {
                    "story_id": story_id,
                    "severity": "blocker" if gate["strict"] else "warning",
                    "missing": [str(value) for value in missing] or ["DoR has not passed."],
                }
            )
    verdict = "PASS" if not warnings else ("BLOCKED" if gate["strict"] else "WARN")
    return {"strict": gate["strict"], "threshold": gate["threshold"], "verdict": verdict, "warnings": warnings}


def enforce_pre_handoff_gate(project_id: str, readiness_pack: dict[str, Any]) -> dict[str, Any]:
    gate = pre_handoff_gate(project_id, readiness_pack)
    if gate["strict"] and gate["warnings"]:
        story_ids = ", ".join(str(item.get("story_id")) for item in gate["warnings"])
        raise RuntimeError(f"Pre-handoff DoR gate blocks backlog handoff for: {story_ids}.")
    return gate


def scan_backlog_privacy(project_id: str) -> list[dict[str, Any]]:
    base = workspace_path(project_id)
    backlog_dir = base / "04_backlog"
    if not backlog_dir.exists():
        return []
    return scan_backlog_texts(base, {path: path.read_text(encoding="utf-8") for path in sorted(backlog_dir.rglob("*")) if path.is_file() and path.suffix.lower() in {".md", ".json"}})


def scan_backlog_texts(base: Path, texts: dict[Path, str]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for path, text in texts.items():
        relative = path.relative_to(base).as_posix() if path.is_absolute() and path.is_relative_to(base) else path.as_posix()
        for line_number, line in enumerate(text.splitlines(), start=1):
            for pattern_id, pattern in BACKLOG_PRIVACY_PATTERNS:
                if pattern.search(line):
                    findings.append(
                        {
                            "path": relative,
                            "line": line_number,
                            "pattern": pattern_id,
                            "message": "Backlog artifact contains a sensitive identifier, endpoint, credential, or private datum.",
                        }
                    )
    return findings


def assert_backlog_privacy_clean(project_id: str, findings: list[dict[str, Any]] | None = None) -> None:
    findings = scan_backlog_privacy(project_id) if findings is None else findings
    if findings:
        first = findings[0]
        raise RuntimeError(
            "Backlog privacy scan blocked handoff: "
            f"{first['path']}:{first['line']} matched {first['pattern']}."
        )
