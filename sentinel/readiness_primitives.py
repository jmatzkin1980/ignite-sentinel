from __future__ import annotations

from typing import Any, Iterable, Mapping

from .gaps import is_blocking


def is_blocking_gap(
    gap: dict[str, Any],
    severities: set[str] | None = None,
    statuses: set[str] | None = None,
) -> bool:
    return is_blocking(gap, severities, statuses)


def above_threshold(score: float, threshold: float, *, inclusive: bool = True) -> bool:
    return score >= threshold if inclusive else score > threshold


def average_score(values: Iterable[float], *, digits: int = 3) -> float:
    items = [float(value) for value in values]
    return round(sum(items) / len(items), digits) if items else 0.0


def weighted_score(
    cells: Iterable[Mapping[str, Any]],
    weights: Mapping[str, float],
    *,
    status_key: str = "status",
    digits: int = 3,
) -> float:
    return average_score(
        (float(weights.get(str(cell.get(status_key, "")), 0.0)) for cell in cells),
        digits=digits,
    )
