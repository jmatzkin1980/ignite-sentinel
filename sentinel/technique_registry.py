"""Declarative challenge technique registry (IMP-112).

The /challenge workflow validates findings through the runtime, but the
elicitation technique catalog is versionable data under ``sentinel/techniques``.
Adding a technique should mean adding JSON, not editing discovery code.
"""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

from .core.io import read_json, read_json_resource
from .resources import package_json_files

_DEFAULT_TECHNIQUES_DIR = Path(__file__).resolve().parent / "techniques"
TECHNIQUES_DIR = _DEFAULT_TECHNIQUES_DIR

TECHNIQUE_ORDER = (
    "pre-mortem",
    "role-play",
    "assumption-inversion",
    "red-blue-team",
    "first-principles",
    "stakeholder-round-robin",
)

VALID_CATEGORIES = {"failure-analysis", "lens-role", "assumption", "adversarial", "decomposition", "stakeholder"}
TECHNIQUE_ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def load_techniques(techniques_dir: Path | str | None = None) -> list[dict]:
    if techniques_dir is None and TECHNIQUES_DIR == _DEFAULT_TECHNIQUES_DIR:
        return list(_load_package_cached())
    directory = Path(techniques_dir) if techniques_dir is not None else TECHNIQUES_DIR
    return list(_load_path_cached(str(directory)))


@lru_cache(maxsize=8)
def _load_path_cached(directory: str) -> tuple[dict, ...]:
    path = Path(directory)
    by_name = {f.stem: f for f in sorted(path.glob("*.json"))}
    return _load_ordered_techniques(by_name)


@lru_cache(maxsize=1)
def _load_package_cached() -> tuple[dict, ...]:
    by_name = {f.name.removesuffix(".json"): f for f in package_json_files("techniques")}
    return _load_ordered_techniques(by_name)


def _load_ordered_techniques(by_name: dict) -> tuple[dict, ...]:
    ordered_names = [name for name in TECHNIQUE_ORDER if name in by_name]
    ordered_names += [name for name in sorted(by_name) if name not in TECHNIQUE_ORDER]
    techniques: list[dict] = []
    seen: set[str] = set()
    for name in ordered_names:
        source = by_name[name]
        data = read_json(source, {}) if isinstance(source, Path) else read_json_resource(source, {})
        technique = _normalize_technique(data, fallback_id=name)
        if technique["id"] in seen:
            raise ValueError(f"Duplicate challenge technique id: {technique['id']}")
        seen.add(technique["id"])
        techniques.append(technique)
    return tuple(techniques)


def _normalize_technique(data: dict, fallback_id: str) -> dict:
    technique_id = str(data.get("id", fallback_id)).strip().lower()
    if not TECHNIQUE_ID_RE.match(technique_id):
        raise ValueError(f"Invalid challenge technique id: {technique_id}")
    category = str(data.get("category", "")).strip().lower()
    if category not in VALID_CATEGORIES:
        raise ValueError(f"{technique_id}: category must be one of {', '.join(sorted(VALID_CATEGORIES))}.")
    name = str(data.get("name", "")).strip()
    prompt = str(data.get("prompt", "")).strip()
    evidence_contract = str(data.get("evidence_contract", "")).strip()
    if not name or not prompt or not evidence_contract:
        raise ValueError(f"{technique_id}: name, prompt, and evidence_contract are required.")
    return {
        "id": technique_id,
        "name": name,
        "category": category,
        "default": bool(data.get("default", False)),
        "prompt": prompt,
        "evidence_contract": evidence_contract,
        "output_focus": [str(item).strip() for item in data.get("output_focus", []) if str(item).strip()],
    }


def technique_by_id(technique_id: str, techniques_dir: Path | str | None = None) -> dict | None:
    normalized = str(technique_id or "").strip().lower()
    for technique in load_techniques(techniques_dir):
        if technique["id"] == normalized:
            return technique
    return None


def known_technique_ids(techniques_dir: Path | str | None = None) -> set[str]:
    return {technique["id"] for technique in load_techniques(techniques_dir)}


def default_challenge_technique_ids(techniques_dir: Path | str | None = None) -> tuple[str, ...]:
    return tuple(technique["id"] for technique in load_techniques(techniques_dir) if technique.get("default"))


def technique_label(technique_id: str) -> str:
    technique = technique_by_id(technique_id)
    return str(technique["name"]) if technique else str(technique_id or "n/a")


def default_technique_summary() -> str:
    labels = [technique_label(technique_id) for technique_id in default_challenge_technique_ids()]
    if not labels:
        return "the default challenge technique set"
    if len(labels) == 1:
        return labels[0]
    return ", ".join(labels[:-1]) + f", and {labels[-1]}"


def clear_cache() -> None:
    _load_path_cached.cache_clear()
    _load_package_cached.cache_clear()
