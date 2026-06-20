"""Declarative backlog slicing model (IMP-049).

The slicing model is team knowledge, not generation filler. It lives in
``sentinel/slicing/backlog_slicing_model.json`` so the team can tune heuristics
without touching Python, while the runtime keeps validating a known taxonomy.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

from .core.io import read_json


SLICING_DIR = Path(__file__).resolve().parent / "slicing"
SLICING_MODEL_FILE = "backlog_slicing_model.json"

VALID_SLICING_PATTERNS = {
    "Workflow Step / Happy Path",
    "Rules / Regression Slice",
    "Data / External Dependency",
    "Interface / UX State",
    "Quality Evidence / Traceability",
}


def load_slicing_model(
    slicing_dir: Path | str | None = None,
    override: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Load the backlog slicing model.

    ``override`` is intentionally uncached so tests can inject a model without
    editing the package JSON. ``slicing_dir`` supports fixture directories.
    """
    if override is not None:
        return normalize_slicing_model(override)
    directory = Path(slicing_dir) if slicing_dir is not None else SLICING_DIR
    return _load_cached(str(directory))


@lru_cache(maxsize=8)
def _load_cached(directory: str) -> dict[str, Any]:
    data = read_json(Path(directory) / SLICING_MODEL_FILE, {})
    return normalize_slicing_model(data)


def clear_cache() -> None:
    _load_cached.cache_clear()


def normalize_slicing_model(data: dict[str, Any]) -> dict[str, Any]:
    strategy_rows = data.get("strategy_rows", [])
    if not isinstance(strategy_rows, list) or not strategy_rows:
        raise ValueError("Slicing model must define non-empty strategy_rows.")
    normalized_rows = []
    for row in strategy_rows:
        heuristic = str(row.get("heuristic", "")).strip()
        applies = str(row.get("applies", "")).strip()
        if not heuristic or not applies:
            raise ValueError("Each slicing strategy row must define heuristic and applies.")
        normalized_rows.append({"heuristic": heuristic, "applies": applies})

    boundary = data.get("enabler_boundary", {})
    paragraphs = [str(item).strip() for item in boundary.get("paragraphs", []) if str(item).strip()]
    if len(paragraphs) != 2:
        raise ValueError("Slicing model must preserve the two Cross-Cutting Enabler Boundary paragraphs.")

    patterns = data.get("patterns", [])
    if not isinstance(patterns, list) or not patterns:
        raise ValueError("Slicing model must define non-empty patterns.")
    normalized_patterns = []
    seen = set()
    for raw in patterns:
        slicing = str(raw.get("slicing", "")).strip()
        pattern_id = str(raw.get("id", slicing)).strip()
        if slicing not in VALID_SLICING_PATTERNS:
            raise ValueError(f"Unknown slicing pattern: {slicing}")
        if pattern_id in seen:
            raise ValueError(f"Duplicate slicing pattern id: {pattern_id}")
        seen.add(pattern_id)
        normalized_patterns.append(
            {
                "id": pattern_id,
                "slicing": slicing,
                "rationale": str(raw.get("rationale", "")).strip(),
                "priority": int(raw.get("priority", 100)),
                "tokens": [str(item).lower() for item in raw.get("tokens", []) if str(item).strip()],
            }
        )
    normalized_patterns.sort(key=lambda item: (item["priority"], item["id"]))
    if "Workflow Step / Happy Path" not in {item["slicing"] for item in normalized_patterns}:
        raise ValueError("Slicing model must include Workflow Step / Happy Path fallback.")

    return {
        "model": str(data.get("model", "backlog_slicing")),
        "version": int(data.get("version", 1)),
        "strategy_rows": normalized_rows,
        "enabler_boundary": {"paragraphs": paragraphs},
        "patterns": normalized_patterns,
    }
