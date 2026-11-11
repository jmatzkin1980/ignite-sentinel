"""IMP-250a: governed source registry, F-NN rows inside `00_raw/source_manifest.json`.

The manifest already kept one record per path with its sha256. This module adds a
row per *source content* on top of it, so the same document delivered under two
paths is one source:

- **Registry.** Every source that enters through `/ingest`, `/sync` or
  `/resolve-gaps` gets an `F-NN` row. The counter never restarts, even when a row
  is retired. Sentinel's own copies of the source attach to the same row.
- **Novelty by hash or by missing row, never by date.** A path never seen whose
  content matches an existing row is that row again, not a new source. A known
  path whose content changed is a new row, recorded as a *candidate* new version
  of the previous one. The registry never decides that the newest version governs:
  a person confirms it with `/sources --superseded-by` or `--current`.
- **Row lifecycle.** A row opens when its command starts and closes when the cross
  finishes. A row left open means a cross that never finished, and `/status`
  reports it.
- **Validity.** current / superseded ("corrects F-NN") / retired (a dead source,
  with its replacement) / expired by a cut-off date, optionally only for one topic.

`07_changes/source_log.md` is the human render of the rows. It is regenerated on
every write and is never edited by hand.
"""
from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from typing import Any

from .core.io import write_text
from .core.time import utc_now

SOURCE_ID_RE = re.compile(r"^F-(\d{2,})$")
# Commands whose `source` argument is information entering the project.
REGISTERING_STATUSES = {"initial_ingested", "synced", "gap_resolved", "harvested"}  # IMP-262: a code harvest
# Sentinel's verbatim copies of a registered source (redacted, so the hash may differ).
COPY_STATUSES = {"raw_copy", "change_copy", "gap_response_copy"}
VALIDITY_VALUES = ("current", "superseded", "retired", "expired")
LIFECYCLE_VALUES = ("open", "closed")
# Folder name -> source kind. The repo `input/` folders use the same names without the number.
KIND_BY_FOLDER = {
    "00_client_requirement": "client_requirement",
    "01_business_context": "business_context",
    "02_technology_context": "technology_context",
    "03_design_context": "design_context",
    "04_quality_context": "quality_context",
    "05_interactions": "interaction",
    "00_client_responses": "client_response",
    "01_meetings": "meeting",
    "02_mail_slack": "mail_slack",
    "03_domain_updates": "domain_update",
    "client_requirement": "client_requirement",
    "business_context": "business_context",
    "technology_context": "technology_context",
    "design_context": "design_context",
    "quality_context": "quality_context",
    "interactions": "interaction",
}


class SourceRegistryError(ValueError):
    """A `/sources` request that would leave the registry inconsistent."""


def source_kind(key: str) -> str:
    for part in reversed(Path(key).parts[:-1]):
        if part in KIND_BY_FOLDER:
            return KIND_BY_FOLDER[part]
    return "external"


def format_source_id(number: int) -> str:
    return f"F-{number:02d}"


def ensure_registry(manifest: dict[str, Any]) -> dict[str, Any]:
    """Add the registry to a manifest, migrating path records written before IMP-250a.

    Each distinct content that a registering command processed becomes one closed,
    current row, in the order it was processed. Copies attach by event id.
    """
    if isinstance(manifest.get("registry"), list):
        manifest.setdefault("next_source_number", _max_number(manifest["registry"]) + 1)
        for row in manifest["registry"]:
            # IMP-250b: rows written before the impact matrix keep an empty one.
            row.setdefault("authority", None)
            row.setdefault("impact", [])
        return manifest
    records = manifest.setdefault("sources", {})
    rows: list[dict[str, Any]] = []
    by_hash: dict[str, dict[str, Any]] = {}
    by_event: dict[str, dict[str, Any]] = {}
    registering = sorted(
        (item for item in records.items() if item[1].get("status") in REGISTERING_STATUSES),
        key=lambda item: (str(item[1].get("last_processed_at", "")), item[0]),
    )
    for key, record in registering:
        digest = str(record.get("hash", ""))
        row = by_hash.get(digest)
        if row is None:
            row = _new_row(format_source_id(len(rows) + 1), digest, key, str(record.get("last_processed_at") or utc_now()))
            row.update(lifecycle="closed", closed_at=row["registered_at"], migrated=True, impact=[])
            rows.append(row)
            by_hash[digest] = row
        elif key not in row["paths"]:
            row["paths"].append(key)
        record["source_id"] = row["id"]
        if record.get("event_id"):
            by_event[str(record["event_id"])] = row
    for key, record in records.items():
        row = by_event.get(str(record.get("event_id"))) if record.get("status") in COPY_STATUSES else None
        if row is not None:
            row["copies"].append(key)
            record["source_id"] = row["id"]
    manifest["registry"] = rows
    manifest["next_source_number"] = len(rows) + 1
    return manifest


def _max_number(rows: list[dict[str, Any]]) -> int:
    numbers = [int(match.group(1)) for row in rows if (match := SOURCE_ID_RE.match(str(row.get("id", ""))))]
    return max(numbers, default=0)


def _new_row(source_id: str, digest: str, key: str, at: str) -> dict[str, Any]:
    return {
        "id": source_id,
        "hash": digest,
        "kind": source_kind(key),
        "from": None,
        "registered_at": at,
        "paths": [key],
        "copies": [],
        "events": [],
        "impacted": [],
        "lifecycle": "open",
        "closed_at": None,
        "validity": "current",
        "superseded_by": None,
        "replacement": None,
        "cutoff": None,
        "topic": None,
        "reason": None,
        "pending_version_of": None,
        # IMP-250b: filled by source_routing.seed_impact when the row is first opened.
        "authority": None,
        "impact": None,
    }


def find_row(manifest: dict[str, Any], source_id: str) -> dict[str, Any] | None:
    return next((row for row in manifest.get("registry", []) if row.get("id") == source_id), None)


def row_for_hash(manifest: dict[str, Any], digest: str) -> dict[str, Any] | None:
    return next((row for row in manifest.get("registry", []) if row.get("hash") == digest), None)


def open_row(manifest: dict[str, Any], key: str, digest: str, via: str, event_id: str | None = None) -> dict[str, Any]:
    """Open the row for this content, reusing the row that already has the same hash.

    A known path with different content opens a new row and records the row it may
    replace as `pending_version_of`; nothing is superseded until a person says so.
    """
    ensure_registry(manifest)
    now = utc_now()
    row = row_for_hash(manifest, digest)
    if row is None:
        row = _new_row(format_source_id(int(manifest["next_source_number"])), digest, key, now)
        manifest["next_source_number"] = int(manifest["next_source_number"]) + 1
        previous_id = manifest.get("sources", {}).get(key, {}).get("source_id")
        previous = find_row(manifest, str(previous_id)) if previous_id else None
        if previous is not None and previous.get("validity") == "current":
            row["pending_version_of"] = previous["id"]
        manifest["registry"].append(row)
    else:
        row["lifecycle"] = "open"
        row["closed_at"] = None
        if key not in row["paths"]:
            row["paths"].append(key)
    row["events"].append({"via": via, "event_id": event_id, "at": now})
    return row


def close_row(row: dict[str, Any], event_id: str | None = None, impacted: list[str] | None = None) -> None:
    row["lifecycle"] = "closed"
    row["closed_at"] = utc_now()
    if event_id and row["events"] and not row["events"][-1].get("event_id"):
        row["events"][-1]["event_id"] = event_id
    for node_id in impacted or []:
        if node_id not in row["impacted"]:
            row["impacted"].append(node_id)


def attach_copy(row: dict[str, Any], key: str) -> None:
    if key not in row["copies"] and key not in row["paths"]:
        row["copies"].append(key)


def attach_alias(row: dict[str, Any], key: str) -> None:
    if key not in row["paths"]:
        row["paths"].append(key)


# --- /sources: the only way a person changes a row ---------------------------------


def update_row(
    manifest: dict[str, Any],
    source_id: str,
    *,
    from_who: str | None = None,
    superseded_by: str | None = None,
    retire: bool = False,
    replacement: str | None = None,
    expire: str | None = None,
    topic: str | None = None,
    current: bool = False,
    close: bool = False,
    reason: str | None = None,
) -> dict[str, Any]:
    ensure_registry(manifest)
    row = find_row(manifest, source_id)
    if row is None:
        raise SourceRegistryError(f"Unknown source row: {source_id}")
    validity_changes = [bool(superseded_by), retire, bool(expire), current]
    if sum(validity_changes) > 1:
        raise SourceRegistryError("Pass only one of --superseded-by, --retire, --expire or --current.")
    if replacement and not retire:
        raise SourceRegistryError("--replacement only applies with --retire.")
    if topic and not expire:
        raise SourceRegistryError("--topic only applies with --expire.")
    if from_who is not None:
        row["from"] = from_who.strip() or None
    if superseded_by:
        newer = _existing_other(manifest, row, superseded_by)
        if _supersedes_chain(manifest, newer, row["id"]):
            raise SourceRegistryError(f"{superseded_by} is already superseded by {row['id']}; that would be a cycle.")
        _set_validity(row, "superseded", reason=reason, superseded_by=newer["id"])
        if newer.get("pending_version_of") == row["id"]:
            newer["pending_version_of"] = None
    elif retire:
        if not (reason or "").strip():
            raise SourceRegistryError("--retire needs --reason: say why the source is dead.")
        if replacement:
            _existing_other(manifest, row, replacement)
        _set_validity(row, "retired", reason=reason, replacement=replacement)
        _clear_pending_versions(manifest, row["id"])
    elif expire:
        try:
            date.fromisoformat(expire)
        except ValueError as exc:
            raise SourceRegistryError(f"--expire needs an ISO date (YYYY-MM-DD), got {expire!r}.") from exc
        _set_validity(row, "expired", reason=reason, cutoff=expire, topic=(topic or "").strip() or None)
    elif current:
        _set_validity(row, "current", reason=reason)
        row["pending_version_of"] = None
    if close:
        row["lifecycle"] = "closed"
        row["closed_at"] = utc_now()
        if reason and not any(validity_changes):
            row["reason"] = reason
    return row


def _existing_other(manifest: dict[str, Any], row: dict[str, Any], other_id: str) -> dict[str, Any]:
    other = find_row(manifest, other_id)
    if other is None:
        raise SourceRegistryError(f"Unknown source row: {other_id}")
    if other["id"] == row["id"]:
        raise SourceRegistryError(f"{row['id']} cannot point at itself.")
    return other


def _supersedes_chain(manifest: dict[str, Any], start: dict[str, Any], target_id: str) -> bool:
    seen: set[str] = set()
    current: dict[str, Any] | None = start
    while current is not None and current.get("superseded_by") and current["id"] not in seen:
        seen.add(current["id"])
        if current["superseded_by"] == target_id:
            return True
        current = find_row(manifest, str(current["superseded_by"]))
    return False


def _set_validity(row: dict[str, Any], validity: str, **fields: Any) -> None:
    row.update(validity=validity, superseded_by=None, replacement=None, cutoff=None, topic=None)
    row.update({key: value for key, value in fields.items() if value is not None})


def _clear_pending_versions(manifest: dict[str, Any], source_id: str) -> None:
    for other in manifest.get("registry", []):
        if other.get("pending_version_of") == source_id:
            other["pending_version_of"] = None


# --- findings ---------------------------------------------------------------------


def registry_summary(manifest: dict[str, Any]) -> dict[str, Any]:
    rows = ensure_registry(manifest).get("registry", [])
    by_validity = {value: 0 for value in VALIDITY_VALUES}
    for row in rows:
        by_validity[str(row.get("validity", "current"))] = by_validity.get(str(row.get("validity", "current")), 0) + 1
    return {
        "rows": len(rows),
        "open": [row["id"] for row in rows if row.get("lifecycle") == "open"],
        "unconfirmed_versions": [
            {"id": row["id"], "version_of": row["pending_version_of"]} for row in rows if row.get("pending_version_of")
        ],
        "by_validity": by_validity,
        "impact_pending": {
            row["id"]: pending
            for row in rows
            if (pending := sum(1 for cell in row.get("impact") or [] if cell.get("state") == "pending"))
        },
    }


def registry_warnings(summary: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    if summary["open"]:
        warnings.append(
            f"Source rows still open, their cross never finished: {', '.join(summary['open'])}. "
            "Re-run the command or close them with /sources --close."
        )
    for item in summary["unconfirmed_versions"]:
        warnings.append(
            f"{item['id']} is a new version of {item['version_of']} (same path, new content). "
            f"Confirm which one governs: /sources --id {item['version_of']} --superseded-by {item['id']}, "
            f"or /sources --id {item['id']} --current."
        )
    return warnings


def row_validity(manifest: dict[str, Any], key: str, on: str | None = None, topic: str | None = None) -> str | None:
    """Validity of the row behind a path. IMP-258 uses it to flag a cited dead source."""
    record = ensure_registry(manifest).get("sources", {}).get(key) or {}
    row = find_row(manifest, str(record.get("source_id"))) if record.get("source_id") else None
    if row is None:
        return None
    if row.get("validity") == "expired":
        applies = not row.get("topic") or (topic or "").strip().lower() == str(row["topic"]).lower()
        if not applies or (on and str(row.get("cutoff")) > on):
            return "current"
    return str(row.get("validity"))


# --- render -------------------------------------------------------------------------

_COPY = {
    "en": {
        "title": "# Source log - {project}",
        "intro": (
            "GENERATED artifact: the human render of the F-NN rows in `00_raw/source_manifest.json`. "
            "Change rows only through `/sources`, never by hand. A row opens when its command starts "
            "and closes when the cross finishes; novelty is decided by content hash, never by date."
        ),
        "empty": "_No sources registered yet._",
        "headers": ("ID", "Registered", "Kind", "From", "sha256", "Paths", "Lifecycle", "Validity", "Notes"),
        "lifecycle": {"open": "open", "closed": "closed"},
        "validity": {"current": "current", "superseded": "superseded", "retired": "retired", "expired": "expired"},
        "corrected_by": "corrected by {id}",
        "replaced_by": "replaced by {id}",
        "cutoff": "expired on {date}",
        "topic": "topic: {topic}",
        "candidate": "candidate new version of {id}, not confirmed",
        "copies": "copies: {n}",
        "authority": "authority: {authority}",
        "cells": "impact cells pending: {n}",
        "missing": "original no longer present",
        "unknown": "unknown",
    },
    "es": {
        "title": "# Registro de fuentes - {project}",
        "intro": (
            "Artefacto GENERADO: render humano de las filas F-NN de `00_raw/source_manifest.json`. "
            "Las filas se cambian solo con `/sources`, nunca a mano. Una fila se abre cuando arranca su "
            "comando y se cierra cuando termina el cruce; la novedad se decide por hash del contenido, nunca por fecha."
        ),
        "empty": "_Todavía no hay fuentes registradas._",
        "headers": ("ID", "Registrada", "Tipo", "De quién", "sha256", "Rutas", "Ciclo", "Vigencia", "Notas"),
        "lifecycle": {"open": "abierta", "closed": "cerrada"},
        "validity": {"current": "vigente", "superseded": "superada", "retired": "retirada", "expired": "vencida"},
        "corrected_by": "la corrige {id}",
        "replaced_by": "reemplazo: {id}",
        "cutoff": "vencida el {date}",
        "topic": "tema: {topic}",
        "candidate": "posible versión nueva de {id}, sin confirmar",
        "copies": "copias: {n}",
        "authority": "autoridad: {authority}",
        "cells": "celdas de impacto pendientes: {n}",
        "missing": "el original ya no está",
        "unknown": "sin dato",
    },
}


def _cell(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ") if value not in (None, "") else "—"


def render_source_log(project_id: str, manifest: dict[str, Any], language: str = "en", root: Path | None = None) -> str:
    copy = _COPY["es" if language == "es" else "en"]
    rows = ensure_registry(manifest).get("registry", [])
    lines = [copy["title"].format(project=project_id), "", copy["intro"], ""]
    if not rows:
        return "\n".join(lines + [copy["empty"], ""])
    lines.append("| " + " | ".join(copy["headers"]) + " |")
    lines.append("|" + "---|" * len(copy["headers"]))
    base = root or Path.cwd()
    for row in rows:
        notes: list[str] = []
        if row.get("superseded_by"):
            notes.append(copy["corrected_by"].format(id=row["superseded_by"]))
        if row.get("replacement"):
            notes.append(copy["replaced_by"].format(id=row["replacement"]))
        if row.get("cutoff"):
            notes.append(copy["cutoff"].format(date=row["cutoff"]))
        if row.get("topic"):
            notes.append(copy["topic"].format(topic=row["topic"]))
        if row.get("pending_version_of"):
            notes.append(copy["candidate"].format(id=row["pending_version_of"]))
        if row.get("copies"):
            notes.append(copy["copies"].format(n=len(row["copies"])))
        if row.get("authority"):
            notes.append(copy["authority"].format(authority=row["authority"]))
        pending = sum(1 for cell in row.get("impact") or [] if cell.get("state") == "pending")
        if pending:
            notes.append(copy["cells"].format(n=pending))
        if row.get("paths") and not any((base / path).exists() or Path(path).exists() for path in row["paths"]):
            notes.append(copy["missing"])
        if row.get("reason"):
            notes.append(str(row["reason"]))
        cells = (
            row["id"],
            str(row.get("registered_at", ""))[:10],
            row.get("kind"),
            row.get("from") or copy["unknown"],
            f"`{str(row.get('hash', ''))[:12]}`",
            "<br>".join(f"`{path}`" for path in row.get("paths", [])),
            copy["lifecycle"].get(str(row.get("lifecycle")), row.get("lifecycle")),
            copy["validity"].get(str(row.get("validity")), row.get("validity")),
            "; ".join(notes),
        )
        lines.append("| " + " | ".join(_cell(value) for value in cells) + " |")
    return "\n".join(lines) + "\n"


def write_source_log(project_id: str, manifest: dict[str, Any], path: Path, language: str = "en") -> None:
    write_text(path, render_source_log(project_id, manifest, language))
