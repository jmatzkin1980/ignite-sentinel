"""IMP-404 (H26 inc 4): registered cross-reads of a change request against the baseline and the new design.

Everything lives under `01_discovery/CHG-NNN/crosses/` of the project workspace. A cross-read is a
claims file the BA writes: every claim carries verbatim quotes, checked against the registered sources.
"""
from __future__ import annotations

from pathlib import Path

from ..errors import InputError

CROSS_KINDS = ("linea_de_base", "diseno", "contradicciones")

KIND_ALIASES = {
    "linea_de_base": "linea_de_base",
    "baseline": "linea_de_base",
    "diseno": "diseno",
    "diseño": "diseno",
    "design": "diseno",
    "contradicciones": "contradicciones",
    "contradictions": "contradicciones",
}


def normalize_kind(value: str, language: str) -> str:
    kind = KIND_ALIASES.get(str(value).strip().lower())
    if kind is None:
        if language == "es":
            raise InputError(f"Tipo de cruce desconocido «{value}»: linea_de_base, diseno o contradicciones")
        raise InputError(f"Unknown cross kind «{value}»: linea_de_base, diseno or contradicciones")
    return kind


def crosses_dir(base: Path, change_id: str) -> Path:
    """The folder that holds a change's registered cross-reads."""
    return base / "01_discovery" / change_id / "crosses"


def cross_path(base: Path, change_id: str, kind: str) -> Path:
    return crosses_dir(base, change_id) / f"{kind}.json"
