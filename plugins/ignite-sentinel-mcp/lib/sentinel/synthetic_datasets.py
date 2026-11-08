"""IMP-196: synthetic handoff datasets — non-governed, disposable, never cited.

Single source of truth for the synthetic-dataset contract:

- **Where** they live (`08_context_packs/synthetic/` inside a workspace — the derived
  context-pack area, deliberately *outside* the SSoT lifecycle tree `00_raw..07_changes`).
- **How** they are marked (`SYNTHETIC — not evidence`).
- The **negative-guard predicate** (`references_synthetic`) that keeps them out of every
  citation/traceability channel.

Synthetic datasets are realistic test data (CSV/JSON/SQL) generated from specs/stories to
seed a developer handoff. Because they are *invented by design*, they are not governed
evidence: they are git-ignored, disposable, live outside the SSoT and traceability, and must
never be cited as a source. This module is pure stdlib so it stays within the local-first
purity guard (IMP-103); generation itself belongs to the `sentinel-handoff-datasets` skill.
"""
from __future__ import annotations

from pathlib import Path

# Relative to a workspace root. A sibling of `exports`/`requests` under the derived
# context-pack area — never a governed lifecycle dir, so no evidence scan reaches it.
SYNTHETIC_DIR_SEGMENTS = ("08_context_packs", "synthetic")
SYNTHETIC_RELATIVE_DIR = "/".join(SYNTHETIC_DIR_SEGMENTS)

# Every synthetic file (and its manifest) must carry this verbatim marker so a reader can
# never mistake generated data for cited evidence.
SYNTHETIC_MARKER = "SYNTHETIC — not evidence"

# Governed lifecycle dirs whose artifacts may cite evidence. The negative guard scans these;
# the synthetic area (08_context_packs/synthetic) is intentionally absent.
GOVERNED_LIFECYCLE_DIRS = (
    "00_raw",
    "01_discovery",
    "02_requirements",
    "03_specs",
    "04_backlog",
    "05_quality",
    "06_traceability",
    "07_changes",
)


def synthetic_dir(base: Path) -> Path:
    """Absolute path of the synthetic-dataset area under a workspace ``base``."""
    return base.joinpath(*SYNTHETIC_DIR_SEGMENTS)


def references_synthetic(text_or_pointer: str) -> bool:
    """True when a citation pointer or artifact body references the synthetic area.

    Normalizes path separators so a Windows or POSIX pointer both resolve. This is the
    single predicate behind the negative guard: any governed artifact that points at
    ``08_context_packs/synthetic`` is citing non-evidence and must be flagged.
    """
    if not text_or_pointer:
        return False
    normalized = str(text_or_pointer).replace("\\", "/").lower()
    return SYNTHETIC_RELATIVE_DIR.lower() in normalized
