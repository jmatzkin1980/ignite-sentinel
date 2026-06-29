from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

from .gates import backlog_gate_config
from .rollup import backlog_status
from .status import append_status_log, story_lifecycle_state, update_story_frontmatter
from ..core.graph import add_edge, add_node
from ..workspace import load_config, read_json, update_state, utc_now, workspace_path, write_json


SPEC_UNIT_RE = re.compile(r"\bSPEC-U-\d{3}\b")
ACTIVITY_DIVERGENCE_TRIGGER_STATUSES = {"In Progress", "In Review", "Done"}
ACTIVITY_DIVERGENCE_STATUS_RANKS = {
    "Draft": 0,
    "Ready": 1,
    "Blocked": 1,
    "In Progress": 2,
    "In Review": 3,
    "Done": 4,
    "Stale": -1,
}

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
PRIVACY_SCAN_MODES = {"off", "warn", "block"}
DEFAULT_PRIVACY_SCAN_MODE = "warn"


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

    base, readiness_path, readiness, stories = _readiness_story_pack(project_id)
    affected: list[dict[str, Any]] = []
    for item in stories:
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
        if previous_status == "Stale":
            continue
        owner = str(previous.get("owner", "")).strip()
        detail = {"stale_spec_units": match["units"]}
        _apply_story_staleness(
            project_id,
            base=base,
            lifecycle=lifecycle,
            story_id=story_id,
            previous_status=previous_status,
            owner=owner,
            reason=reason,
            detail=detail,
            readiness_item=match["readiness"],
            change_message=f"{story_id} marked Stale by spec-unit change",
            timestamp=timestamp,
            change_id=change_id,
        )
        stale_story_ids.append(story_id)

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


def mark_stale_stories_for_activity_divergence(
    project_id: str,
    story_id: str,
    change_id: str | None = None,
) -> dict[str, Any]:
    base, readiness_path, readiness, stories = _readiness_story_pack(project_id)
    trigger_item = next((item for item in stories if str(item.get("story_id", "")).strip() == story_id), None)
    if not trigger_item:
        return {"reason": "activity_divergence", "stale_stories": []}

    lifecycle = story_lifecycle_state(project_id)
    trigger_lifecycle = lifecycle.get(story_id, {})
    trigger_status = str(trigger_lifecycle.get("status", "Draft"))
    if trigger_status not in ACTIVITY_DIVERGENCE_TRIGGER_STATUSES:
        return {"reason": "activity_divergence", "stale_stories": []}

    trigger_rank = story_activity_rank(trigger_status)
    trigger_updated_at = str(trigger_lifecycle.get("updated_at", "")).strip()
    trigger_source_unit = str(trigger_item.get("source_unit", "")).strip()
    trigger_domain = story_domain(trigger_item)

    peers: list[dict[str, Any]] = []
    group_kind = ""
    group_value = ""
    if trigger_source_unit:
        peers = [
            item
            for item in stories
            if str(item.get("story_id", "")).strip() != story_id
            and str(item.get("source_unit", "")).strip() == trigger_source_unit
        ]
        if peers:
            group_kind = "source_unit"
            group_value = trigger_source_unit
    if not peers and trigger_domain:
        peers = [
            item
            for item in stories
            if str(item.get("story_id", "")).strip() != story_id and story_domain(item) == trigger_domain
        ]
        if peers:
            group_kind = "domain"
            group_value = trigger_domain
    if not peers:
        return {"reason": "activity_divergence", "stale_stories": []}

    timestamp = utc_now()
    stale_story_ids: list[str] = []
    for item in peers:
        peer_story_id = str(item.get("story_id", "")).strip()
        if not peer_story_id:
            continue
        previous = lifecycle.get(peer_story_id, {})
        previous_status = str(previous.get("status", "Draft"))
        if previous_status == "Stale" or story_activity_rank(previous_status) >= trigger_rank:
            continue
        peer_updated_at = str(previous.get("updated_at", "")).strip()
        if trigger_updated_at and peer_updated_at and peer_updated_at >= trigger_updated_at:
            continue
        owner = str(previous.get("owner", "")).strip()
        detail = {
            "stale_group_kind": group_kind,
            "stale_group_value": group_value,
            "stale_trigger_story": story_id,
            "stale_trigger_status": trigger_status,
        }
        _apply_story_staleness(
            project_id,
            base=base,
            lifecycle=lifecycle,
            story_id=peer_story_id,
            previous_status=previous_status,
            owner=owner,
            reason="activity_divergence",
            detail=detail,
            readiness_item=item,
            change_message=f"{peer_story_id} marked Stale by activity divergence after {story_id}",
            timestamp=timestamp,
            change_id=change_id,
        )
        stale_story_ids.append(peer_story_id)

    if not stale_story_ids:
        return {
            "reason": "activity_divergence",
            "stale_stories": [],
            "trigger_story": story_id,
            "trigger_status": trigger_status,
            "group_kind": group_kind,
            "group_value": group_value,
        }

    update_state(
        project_id,
        story_lifecycle=lifecycle,
        last_story_staleness_update=timestamp,
        stale_stories={
            "reason": "activity_divergence",
            "stories": stale_story_ids,
            "trigger_story": story_id,
            "trigger_status": trigger_status,
            "group_kind": group_kind,
            "group_value": group_value,
            "updated_at": timestamp,
        },
    )
    if isinstance(readiness, dict):
        write_json(readiness_path, readiness)
    backlog_status(project_id)
    return {
        "reason": "activity_divergence",
        "stale_stories": stale_story_ids,
        "trigger_story": story_id,
        "trigger_status": trigger_status,
        "group_kind": group_kind,
        "group_value": group_value,
    }


def story_spec_units(item: dict[str, Any]) -> set[str]:
    units: set[str] = set()
    for value in (item.get("source_unit"), *item.get("trace", [])):
        if isinstance(value, str) and SPEC_UNIT_RE.fullmatch(value):
            units.add(value)
    return units


def story_domain(item: dict[str, Any]) -> str:
    return str(item.get("domain", "")).strip().lower()


def story_activity_rank(status: str) -> int:
    return ACTIVITY_DIVERGENCE_STATUS_RANKS.get(str(status).strip(), 0)


def _readiness_story_pack(project_id: str) -> tuple[Path, Path, dict[str, Any], list[dict[str, Any]]]:
    base = workspace_path(project_id)
    readiness_path = base / "08_context_packs" / "implementation_readiness.json"
    readiness = read_json(readiness_path, {})
    stories = readiness.get("stories", []) if isinstance(readiness, dict) else []
    return base, readiness_path, readiness, [item for item in stories if isinstance(item, dict)]


def _apply_story_staleness(
    project_id: str,
    *,
    base: Path,
    lifecycle: dict[str, dict[str, Any]],
    story_id: str,
    previous_status: str,
    owner: str,
    reason: str,
    detail: dict[str, Any],
    readiness_item: dict[str, Any],
    change_message: str,
    timestamp: str,
    change_id: str | None,
) -> None:
    lifecycle[story_id] = {
        "status": "Stale",
        "owner": owner,
        "updated_at": timestamp,
        "stale_reason": reason,
        **detail,
    }
    story_path = base / "04_backlog" / f"{story_id}.md"
    if story_path.exists():
        update_story_frontmatter(story_path, "Stale", owner)
    append_status_log(project_id, story_id, previous_status, "Stale", owner)
    readiness_item["story_status"] = "Stale"
    readiness_item["staleness"] = {"reason": reason, **detail, "updated_at": timestamp}
    change_node = add_node(
        project_id,
        "CHG",
        "story_staleness",
        base / "04_backlog" / "status_log.md",
        change_message,
        status="applied",
        domain="delivery",
    )
    if change_id:
        add_edge(project_id, change_id, change_node, "triggers_story_staleness")
    add_edge(project_id, change_node, story_id, "marks_story_stale")


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
    if backlog_privacy_scan_mode(project_id) == "off":
        return []
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


def backlog_privacy_scan_mode(project_id: str) -> str:
    config = load_config(project_id)
    scan = config.get("privacy_scan", {}) if isinstance(config.get("privacy_scan", {}), dict) else {}
    mode = str(scan.get("mode", DEFAULT_PRIVACY_SCAN_MODE)).strip().lower()
    return mode if mode in PRIVACY_SCAN_MODES else DEFAULT_PRIVACY_SCAN_MODE


def evaluate_backlog_privacy(project_id: str, findings: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    mode = backlog_privacy_scan_mode(project_id)
    findings = [] if mode == "off" else (scan_backlog_privacy(project_id) if findings is None else findings)
    if mode == "off" or not findings:
        verdict = "PASS"
    else:
        verdict = "BLOCKED" if mode == "block" else "WARN"
    return {"mode": mode, "verdict": verdict, "findings": findings}


def assert_backlog_privacy_clean(project_id: str, findings: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    result = evaluate_backlog_privacy(project_id, findings)
    if result["verdict"] == "BLOCKED":
        first = result["findings"][0]
        raise RuntimeError(
            "Backlog privacy scan blocked handoff: "
            f"{first['path']}:{first['line']} matched {first['pattern']}."
        )
    if result["verdict"] == "WARN":
        first = result["findings"][0]
        print(
            "Backlog privacy scan warning: "
            f"{len(result['findings'])} finding(s); first is {first['path']}:{first['line']} matched {first['pattern']}.",
            file=sys.stderr,
        )
    return result
