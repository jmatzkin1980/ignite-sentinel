"""Governed drift detection (Horizonte 3).

IMP-148 records a deterministic fingerprint of the *source* artifacts a derived
artifact was generated from, at generation time. IMP-149 compares that recorded
fingerprint against the current source bytes to flag downstream artifacts that
drifted from the cited source they came from — the system signals, the BA
reconciles; nothing is ever rewritten automatically.

The fingerprint is a sha256 of source bytes, never an embedding "similarity".
Absent sources are recorded as ``None`` so a later appearance/removal is itself
a detectable change.
"""

from __future__ import annotations

import hashlib
from typing import Any

from .workspace import read_json, state_path, update_state, workspace_path

# Which source artifacts each derived artifact is generated from. Kept explicit
# so drift maps to the real provenance edge (brief/requirements -> specs; specs
# -> backlog), mirroring the discovery->brief->specs->backlog lifecycle.
DERIVED_SOURCE_MAP: dict[str, tuple[str, ...]] = {
    "specs": ("02_requirements/project-brief.md", "02_requirements/requirements.md"),
    "backlog": ("03_specs/specs.md",),
}


def _hash_source(project_id: str, rel_path: str) -> str | None:
    path = workspace_path(project_id) / rel_path
    if not path.is_file():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_fingerprint(project_id: str, rel_paths: tuple[str, ...]) -> dict[str, str | None]:
    """Deterministic sha256 registry of the given source artifacts (IMP-148)."""
    return {rel: _hash_source(project_id, rel) for rel in rel_paths}


def record_derived_source_fingerprint(project_id: str, derived: str) -> dict[str, str | None]:
    """Snapshot the fingerprint of ``derived``'s sources into state.json (IMP-148).

    Called at the end of specs/backlog generation. Merges into the per-derived
    registry so recording one derived artifact never drops another's snapshot.
    """
    fingerprint = source_fingerprint(project_id, DERIVED_SOURCE_MAP.get(derived, ()))
    state = read_json(state_path(project_id), {})
    registry: dict[str, Any] = dict(state.get("derived_source_fingerprints", {}))
    registry[derived] = fingerprint
    update_state(project_id, derived_source_fingerprints=registry)
    return fingerprint
