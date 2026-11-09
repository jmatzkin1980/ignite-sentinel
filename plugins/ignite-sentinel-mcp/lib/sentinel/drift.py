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

from typing import Any

from .core.hashing import file_content_hash, hash_matches
from .workspace import read_json, state_path, update_state, workspace_path

# Which source artifacts each derived artifact is generated from. Kept explicit
# so drift maps to the real provenance edge (brief/requirements -> specs; specs
# -> backlog), mirroring the discovery->brief->specs->backlog lifecycle.
DERIVED_SOURCE_MAP: dict[str, tuple[str, ...]] = {
    "specs": ("02_requirements/project-brief.md", "02_requirements/requirements.md"),
    "backlog": ("03_specs/specs.md",),
}

# IMP-291 [A29]: where each derived artifact lives, to tell "never fingerprinted"
# (unverifiable) apart from "not generated yet".
DERIVED_ARTIFACT_PATHS: dict[str, str] = {
    "specs": "03_specs/specs.md",
    "backlog": "04_backlog",
}


def _hash_source(project_id: str, rel_path: str) -> str | None:
    path = workspace_path(project_id) / rel_path
    if not path.is_file():
        return None
    return file_content_hash(path)  # IMP-291: a line-ending flip is not drift


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


# IMP-151: which derived artifacts form the "foundation" a phase builds on.
# /specs builds on the brief/requirements (i.e. on the `specs` derivation);
# /backlog builds on specs, which in turn builds on the brief — so a stale
# upstream `specs` is the more valuable "don't build on sand" signal.
FOUNDATION_FOR_PHASE: dict[str, tuple[str, ...]] = {
    "specs": ("specs",),
    "backlog": ("specs", "backlog"),
}


def _drifted_sources(project_id: str) -> dict[str, list[str]]:
    """Per-derived list of source paths that changed since generation (IMP-148/149).

    Shared core: for each derived artifact with a recorded fingerprint, compare
    the recorded source hashes against the current bytes and return the changed
    sources. Empty when there is no registry (pre-IMP-148 workspaces) or nothing
    drifted.
    """
    registry = read_json(state_path(project_id), {}).get("derived_source_fingerprints", {})
    if not isinstance(registry, dict) or not registry:
        return {}
    drifted: dict[str, list[str]] = {}
    for derived in DERIVED_SOURCE_MAP:
        recorded = registry.get(derived)
        if not isinstance(recorded, dict) or not recorded:
            continue
        changed = sorted(rel for rel, digest in recorded.items() if _source_changed(project_id, rel, digest))
        if changed:
            drifted[derived] = changed
    return drifted


def _source_changed(project_id: str, rel_path: str, recorded: object) -> bool:
    path = workspace_path(project_id) / rel_path
    if not path.is_file():
        return recorded is not None
    return not hash_matches(recorded, path.read_bytes())


def _derived_exists(project_id: str, derived: str) -> bool:
    path = workspace_path(project_id) / DERIVED_ARTIFACT_PATHS[derived]
    return path.is_file() or (path.is_dir() and any(path.glob("*.md")))


def unverifiable_derived(project_id: str) -> list[str]:
    """IMP-291 [A29]: derived artifacts on disk with no recorded source fingerprint."""
    registry = read_json(state_path(project_id), {}).get("derived_source_fingerprints", {})
    registry = registry if isinstance(registry, dict) else {}
    return [
        derived for derived in DERIVED_ARTIFACT_PATHS
        if not registry.get(derived) and _derived_exists(project_id, derived)
    ]


def derived_drift_warnings(project_id: str) -> list[str]:
    """IMP-149: governed drift detection in /health — signal, never rewrite.

    If a derived artifact's source changed since generation, report it and name
    which source(s) changed. Upgrades the exists-based
    ``metabolism.downstream_stale_artifacts`` to a fingerprint-based divergence
    check. It only warns; the BA decides whether to regenerate or mark the change
    immaterial. Nothing is rewritten.
    """
    unverifiable = [
        f"Derived artifact `{derived}` cannot be verified: no source fingerprint was recorded "
        f"when it was generated. Regenerate /{derived} through the CLI to record one."
        for derived in unverifiable_derived(project_id)
    ]
    return unverifiable + [
        f"Derived artifact `{derived}` may have DRIFTED: its source(s) changed since "
        f"generation: {', '.join(changed)}. Reconcile by regenerating /{derived} through "
        "the CLI once the change is reviewed, or confirm the change is immaterial. "
        "Nothing was rewritten."
        for derived, changed in _drifted_sources(project_id).items()
    ]


def foundation_drift_warnings(project_id: str, phase: str) -> list[str]:
    """IMP-151: soft-gate warning when a phase's foundation drifted since generation.

    Reuses the IMP-149 drift computation, scoped to the derived artifacts that
    make up ``phase``'s foundation, and frames it as a "don't build on a stale
    foundation" recommendation. It only warns — the BA decides whether to
    reconcile (regenerate the stale upstream) or proceed; nothing is blocked
    unless ``drift_gate.strict`` is opted in by the caller.
    """
    drifted = _drifted_sources(project_id)
    warnings: list[str] = []
    for derived in FOUNDATION_FOR_PHASE.get(phase, ()):
        changed = drifted.get(derived)
        if changed:
            warnings.append(
                f"Foundation for /{phase} may be STALE: `{derived}` was generated before its "
                f"source(s) changed ({', '.join(changed)}). Regenerate /{derived} through the CLI "
                f"before relying on /{phase}, or confirm the change is immaterial. Nothing was rewritten."
            )
    return warnings
