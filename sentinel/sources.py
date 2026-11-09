from __future__ import annotations

from pathlib import Path
from typing import Any

from .core.hashing import content_sha256, file_content_hash, hash_matches
from .workspace import read_json, utc_now, workspace_path, write_json


TRACKED_SUFFIXES = {".md", ".txt", ".html", ".htm"}
# IMP-293: files Sentinel writes into the scanned 07_changes buckets. They are
# never client input, even after a person edits them: a PROPOSED gap response
# is applied only through an explicit `/resolve-gaps --source`.
SENTINEL_OUTPUT_SUFFIXES: tuple[str, ...] = (
    "_impact_report.md",
    "_interaction_digest.md",
    "_gap_response_proposed.md",
    "_gap_resolution_report.md",
)
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
    """Workspace-root-relative key for a source; absolute only when it lives outside.

    Compares like with like (IMP-246): resolved against resolved, and the path as
    written against the cwd as written, because Windows can reach one folder by two
    spellings (8.3 short names such as RUNNER~1, junctions, symlinks).
    """
    cwd = Path.cwd()
    for candidate, base in ((path.resolve(), cwd.resolve()), (path.absolute(), cwd.absolute())):
        try:
            return candidate.relative_to(base).as_posix()
        except ValueError:
            continue
    return path.resolve().as_posix()


def file_hash(path: Path) -> str:
    return file_content_hash(path)  # IMP-291: a line-ending flip is not a new version


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
        data = path.read_bytes()
        current_hash = content_sha256(data)
        previous = known.get(key)
        if previous is None:
            reason = "new"
        elif not hash_matches(previous.get("hash"), data):
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
        if path.name.startswith(".") or path.name.endswith(SENTINEL_OUTPUT_SUFFIXES):
            continue
        files.append(path)
    return files
