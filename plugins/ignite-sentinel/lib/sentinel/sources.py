from __future__ import annotations

from pathlib import Path
from typing import Any

from .core.hashing import content_sha256, file_content_hash, hash_matches
from .source_registry import (
    COPY_STATUSES,
    REGISTERING_STATUSES,
    attach_alias,
    attach_copy,
    close_row,
    SourceRegistryError,
    ensure_registry,
    find_row,
    open_row,
    registry_summary,
    row_for_hash,
    update_row,
    write_source_log,
)
from .core.io import write_text
from .source_routing import (
    cascade_impact,
    closing_report,
    find_row_or_raise,
    mark_cell,
    render_closing_report,
    resolve_precedence,
    row_authority,
    seed_impact,
    set_authority,
)
from .workspace import load_config, read_json, utc_now, workspace_path, write_json


TRACKED_SUFFIXES = {".md", ".txt", ".html", ".htm", ".docx"}  # IMP-270: .docx too
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


def source_log_path(project_id: str) -> Path:
    return workspace_path(project_id) / "07_changes" / "source_log.md"


def load_source_manifest(project_id: str) -> dict[str, Any]:
    return ensure_registry(read_json(source_manifest_path(project_id), {"sources": {}}))


def save_source_manifest(project_id: str, manifest: dict[str, Any]) -> None:
    write_json(source_manifest_path(project_id), manifest)
    if manifest.get("registry"):  # IMP-250a: the human render follows every write
        write_source_log(project_id, manifest, source_log_path(project_id), _language(project_id))


def _language(project_id: str) -> str:
    language = read_json(workspace_path(project_id) / "state.json", {}).get("project_language", "en")
    return str(language if language in {"es", "en"} else "en")


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


def source_record(path: Path, status: str, event_id: str | None = None, source_id: str | None = None) -> dict[str, Any]:
    stat = path.stat()
    record: dict[str, Any] = {
        "path": source_key(path),
        "hash": file_hash(path),
        "size": stat.st_size,
        "mtime": int(stat.st_mtime),
        "status": status,
        "event_id": event_id,
        "last_seen_at": utc_now(),
        "last_processed_at": utc_now(),
    }
    if source_id:
        record["source_id"] = source_id
    return record


def open_source_row(project_id: str, path: Path, via: str, event_id: str | None = None) -> str:
    """IMP-250a: open the F-NN row before a command crosses the source; returns its id."""
    manifest = load_source_manifest(project_id)
    row = open_row(manifest, source_key(path), file_hash(path), via, event_id)
    seed_impact(row)  # IMP-250b: authority + impact matrix on first sight
    save_source_manifest(project_id, manifest)
    return str(row["id"])


def mark_source_processed(
    project_id: str,
    path: Path,
    status: str,
    event_id: str | None = None,
    source_id: str | None = None,
    impacted: list[str] | None = None,
) -> str | None:
    """Record a processed path. A registering status closes its F-NN row; a copy joins it."""
    manifest = load_source_manifest(project_id)
    key = source_key(path)
    digest = file_hash(path)
    row = find_row(manifest, source_id) if source_id else None
    if status in REGISTERING_STATUSES:
        if row is None or row.get("hash") != digest:
            row = open_row(manifest, key, digest, status, event_id)
            seed_impact(row)
        attach_alias(row, key)
        close_row(row, event_id, impacted)
    elif status in COPY_STATUSES and row is not None:
        attach_copy(row, key)
    else:
        row = None
    manifest.setdefault("sources", {})[key] = source_record(path, status, event_id, row["id"] if row else None)
    save_source_manifest(project_id, manifest)
    return str(row["id"]) if row else None


def discover_source_novelty(project_id: str) -> dict[str, list[dict[str, Any]]]:
    """Pending sources, plus unseen paths whose content is already a registered row.

    Novelty is decided by content hash or by a missing row, never by date (IMP-250a).
    """
    manifest = load_source_manifest(project_id)
    known = manifest.get("sources", {})
    pending: list[dict[str, Any]] = []
    duplicates: list[dict[str, Any]] = []
    first_new: dict[str, str] = {}  # hash -> key of the first unseen path with it in this scan
    for path in scan_candidate_sources(project_id):
        key = source_key(path)
        data = path.read_bytes()
        current_hash = content_sha256(data)
        previous = known.get(key)
        if previous is None:
            row = row_for_hash(manifest, current_hash)
            if row is not None or current_hash in first_new:
                duplicates.append({
                    "path": path,
                    "key": key,
                    "hash": current_hash,
                    "source_id": row["id"] if row is not None else None,
                    "same_as": None if row is not None else first_new[current_hash],
                })
                continue
            first_new[current_hash] = key
            reason = "new"
        elif not hash_matches(previous.get("hash"), data):
            reason = "modified"
        else:
            continue
        pending.append({"path": path, "key": key, "hash": current_hash, "reason": reason})
    return {"pending": pending, "duplicates": duplicates}


def discover_pending_sources(project_id: str) -> list[dict[str, Any]]:
    return discover_source_novelty(project_id)["pending"]


def record_duplicate_source(project_id: str, path: Path, source_id: str) -> None:
    """A second path for content already registered joins that row instead of opening one."""
    manifest = load_source_manifest(project_id)
    row = find_row(manifest, source_id)
    if row is None:
        return
    attach_alias(row, source_key(path))
    manifest.setdefault("sources", {})[source_key(path)] = source_record(path, "duplicate_content", None, source_id)
    save_source_manifest(project_id, manifest)


def list_sources(project_id: str) -> dict[str, Any]:
    manifest = load_source_manifest(project_id)
    if manifest.get("registry"):
        save_source_manifest(project_id, manifest)  # persists a migration and refreshes the log
    return {
        "project_id": project_id,
        "registry": manifest.get("registry", []),
        "summary": registry_summary(manifest),
        "source_log": source_log_path(project_id).as_posix() if manifest.get("registry") else None,
    }


def update_source(
    project_id: str,
    source_id: str,
    *,
    authority: str | None = None,
    cell: str | None = None,
    mark: str | None = None,
    **changes: Any,
) -> dict[str, Any]:
    manifest = load_source_manifest(project_id)
    if (cell is None) != (mark is None):
        raise SourceRegistryError("--cell and --mark go together: --cell DOCUMENT/SECTION --mark updated|reviewed|pending.")
    if cell is not None:
        find_row_or_raise(manifest, source_id)
    row = update_row(manifest, source_id, **{**changes, "reason": None if cell else changes.get("reason")})
    if authority:
        set_authority(row, authority)
    if changes.get("retire"):
        cascade_impact(row)  # IMP-250b: a retired source reaches every document
    if cell is not None:
        mark_cell(row, cell, str(mark), changes.get("reason"))
    save_source_manifest(project_id, manifest)
    return {
        "project_id": project_id,
        "row": row,
        "summary": registry_summary(manifest),
        "source_log": source_log_path(project_id).as_posix(),
    }


def source_registry_summary(project_id: str) -> dict[str, Any]:
    return registry_summary(load_source_manifest(project_id))


def closing_report_path(project_id: str) -> Path:
    return workspace_path(project_id) / "07_changes" / "closing_report.md"


def write_closing_report(project_id: str) -> dict[str, Any]:
    """IMP-250b: closing report by recipient. Writes the report; never deletes a file."""
    manifest = load_source_manifest(project_id)

    def exists(key: str) -> bool:
        return (Path.cwd() / key).exists() or Path(key).exists()

    report = closing_report(manifest, exists)
    path = closing_report_path(project_id)
    write_text(path, render_closing_report(project_id, report, _language(project_id)))
    return {"project_id": project_id, "closing_report": path.as_posix(), **report}


def source_precedence(project_id: str, scope: str, source_ids: list[str]) -> dict[str, Any]:
    """IMP-250b: which of these rows governs in `scope`. Read-only."""
    manifest = load_source_manifest(project_id)
    if len(source_ids) < 2:
        raise SourceRegistryError("--between needs at least two source ids, for example F-01,F-03.")
    candidates = [
        {"id": row["id"], "authority": row_authority(row)}
        for row in (find_row_or_raise(manifest, source_id) for source_id in source_ids)
    ]
    result = resolve_precedence(scope, candidates, load_config(project_id))
    return {"project_id": project_id, "candidates": candidates, **result}


def source_row(project_id: str, source_id: str) -> dict[str, Any] | None:
    return find_row(load_source_manifest(project_id), source_id)


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
