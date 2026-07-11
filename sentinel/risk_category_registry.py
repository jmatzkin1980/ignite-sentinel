"""Declarative Cagan risk-category registry (IMP-181).

Governed assumptions may optionally tag a ``risk_category``: which of Marty
Cagan's four product risks (value, usability, viability, feasibility) the
assumption is about. The default four live as versionable JSON under
``sentinel/risk_categories/``; a project can add an extended taxonomy (e.g.
go-to-market, strategy, team) via a directory override, same molde as
``lens_registry.py`` / ``technique_registry.py`` — add JSON, not Python.

Deliberately kept separate from the 7 discovery lenses (business/product/...):
a risk category answers "which Cagan risk", a lens answers "whose evidence
scope"; mapping the two would collapse two different questions into one.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from .core.io import read_json, read_json_resource
from .resources import package_json_files

_DEFAULT_RISK_CATEGORIES_DIR = Path(__file__).resolve().parent / "risk_categories"
RISK_CATEGORIES_DIR = _DEFAULT_RISK_CATEGORIES_DIR

RISK_CATEGORY_ORDER = ("value", "usability", "viability", "feasibility")


def load_risk_categories(risk_categories_dir: Path | str | None = None) -> list[dict]:
    if risk_categories_dir is None and RISK_CATEGORIES_DIR == _DEFAULT_RISK_CATEGORIES_DIR:
        return list(_load_package_cached())
    directory = Path(risk_categories_dir) if risk_categories_dir is not None else RISK_CATEGORIES_DIR
    return list(_load_path_cached(str(directory)))


@lru_cache(maxsize=8)
def _load_path_cached(directory: str) -> tuple[dict, ...]:
    path = Path(directory)
    by_name = {f.stem: f for f in sorted(path.glob("*.json"))}
    return _load_ordered({name: read_json(source, {}) for name, source in by_name.items()})


@lru_cache(maxsize=1)
def _load_package_cached() -> tuple[dict, ...]:
    by_name = {f.name.removesuffix(".json"): f for f in package_json_files("risk_categories")}
    return _load_ordered({name: read_json_resource(source, {}) for name, source in by_name.items()})


def _load_ordered(by_name: dict[str, dict]) -> tuple[dict, ...]:
    ordered_names = [name for name in RISK_CATEGORY_ORDER if name in by_name]
    ordered_names += [name for name in sorted(by_name) if name not in RISK_CATEGORY_ORDER]
    categories: list[dict] = []
    for name in ordered_names:
        data = by_name[name]
        category_id = str(data.get("id", name)).strip().lower()
        categories.append(
            {
                "id": category_id,
                "label": str(data.get("label", category_id.title())).strip(),
                "description": str(data.get("description", "")).strip(),
            }
        )
    return tuple(categories)


def known_risk_categories(risk_categories_dir: Path | str | None = None) -> set[str]:
    return {category["id"] for category in load_risk_categories(risk_categories_dir)}


def risk_category_label(category_id: str, risk_categories_dir: Path | str | None = None) -> str:
    normalized = str(category_id or "").strip().lower()
    for category in load_risk_categories(risk_categories_dir):
        if category["id"] == normalized:
            return category["label"]
    return normalized.title() if normalized else ""


def clear_cache() -> None:
    _load_path_cached.cache_clear()
    _load_package_cached.cache_clear()
