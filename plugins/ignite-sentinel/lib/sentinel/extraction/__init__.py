"""IMP-402 (H26 inc 3): extraction of a change request, element by element, with coverage.

Everything lives under `02_requirements/CHG-NNN/extraction/` of the project workspace.
"""
from __future__ import annotations

from pathlib import Path


def extraction_dir(base: Path, change_id: str) -> Path:
    """The folder that holds a change's inventory, proposals, review and submitted sheets."""
    return base / "02_requirements" / change_id / "extraction"
