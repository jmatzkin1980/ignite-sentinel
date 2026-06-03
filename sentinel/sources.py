from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from .workspace import read_json, utc_now, workspace_path, write_json


TRACKED_SUFFIXES = {".md", ".txt"}
REPO_INPUT_DIRS = [
    "input/client_requirement",
    "input/business_context",
    "input/technology_context",
    "input/design_context",
    "input/quality_context",
    "input/interactions",
]
WORKSPACE_INPUT_DIRS = [
    "00_raw/00_client_requirement",
    "00_raw/01_business_context",
    "00_raw/02_technology_context",
    "00_raw/03_design_context",
    "00_raw/04_quality_context",
    "00_raw/05_interactions",
    "07_changes/00_client_responses",
    "07_changes/01_meetings",
    "07_changes/02_mail_slack",
    "07_changes/03_domain_updates",
]


def source_manifest_path(project_id: str) -> Path:
    return workspace_path(project_id) / "00_raw" / "source_manifest.json"


def load_source_manifest(project_id: str) -> dict[str, Any]:
    return read_json(source_manifest_path(project_id), {"sources": {}})


def save_source_manifest(project_id: str, manifest: dict[str, Any]) -> None:
    write_json(source_manifest_path(project_id), manifest)


def source_key(path: Path) -> str:
    path = path.resolve()
    try:
        return path.relative_to(Path.cwd()).as_posix()
    except ValueError:
        return path.as_posix()


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def source_record(path: Path, status: str, event_id: str | None = None) -> dict[str, Any]:
    stat = path.stat()
    return {
        "path": source_key(path),
        "hash": file_hash(path),
        "size": stat.st_size,
        "mtime": int(stat.st_mtime),
        "status": status,
        "event_id": event_id,
        "last_seen_at": utc_now(),
        "last_processed_at": utc_now(),
    }


def mark_source_processed(project_id: str, path: Path, status: str, event_id: str | None = None) -> None:
    manifest = load_source_manifest(project_id)
    manifest.setdefault("sources", {})[source_key(path)] = source_record(path, status, event_id)
    save_source_manifest(project_id, manifest)


def discover_pending_sources(project_id: str) -> list[dict[str, Any]]:
    manifest = load_source_manifest(project_id)
    known = manifest.get("sources", {})
    pending: list[dict[str, Any]] = []
    for path in scan_candidate_sources(project_id):
        key = source_key(path)
        current_hash = file_hash(path)
        previous = known.get(key)
        if previous is None:
            reason = "new"
        elif previous.get("hash") != current_hash:
            reason = "modified"
        else:
            continue
        pending.append({"path": path, "key": key, "hash": current_hash, "reason": reason})
    return pending


def scan_candidate_sources(project_id: str) -> list[Path]:
    candidates: list[Path] = []
    for relative in REPO_INPUT_DIRS:
        candidates.extend(iter_source_files(Path.cwd() / relative))

    base = workspace_path(project_id)
    for relative in WORKSPACE_INPUT_DIRS:
        candidates.extend(iter_source_files(base / relative))

    unique: dict[str, Path] = {}
    for path in candidates:
        unique[source_key(path)] = path
    return sorted(unique.values(), key=lambda item: source_key(item))


def iter_source_files(folder: Path) -> list[Path]:
    if not folder.exists():
        return []
    files = []
    for path in folder.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in TRACKED_SUFFIXES:
            continue
        if path.name.startswith(".") or path.name.endswith("_impact_report.md"):
            continue
        files.append(path)
    return files
