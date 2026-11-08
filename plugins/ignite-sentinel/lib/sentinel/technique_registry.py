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
    "jtbd-forces",
    "red-blue-team",
    "first-principles",
    "stakeholder-round-robin",
)

VALID_CATEGORIES = {
    "failure-analysis",
    "lens-role",
    "assumption",
    "jtbd",
    "adversarial",
    "decomposition",
    "stakeholder",
}
VALID_RESPONDENT_PROFILES = {"business", "technical"}
# Closed pre-mortem risk taxonomy (IMP-195): an unknown label is rejected at
# load time, so an invalid classification is impossible by construction.
RISK_TAXONOMY_LABELS = ("Tiger", "Paper Tiger", "Elephant")
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
    calibration = normalize_technique_calibration(data.get("calibration", {}))
    if not name or not prompt or not evidence_contract:
        raise ValueError(f"{technique_id}: name, prompt, and evidence_contract are required.")
    return {
        "id": technique_id,
        "name": name,
        "category": category,
        "default": bool(data.get("default", False)),
        "prompt": prompt,
        "calibration": calibration,
        "evidence_contract": evidence_contract,
        "output_focus": [str(item).strip() for item in data.get("output_focus", []) if str(item).strip()],
        "risk_taxonomy": normalize_risk_taxonomy(data.get("risk_taxonomy", []), technique_id),
    }


def normalize_risk_taxonomy(raw: object, technique_id: str = "") -> list[dict[str, str]]:
    """Validate an optional pre-mortem risk taxonomy (IMP-195).

    Each entry declares a ``label`` from the closed ``RISK_TAXONOMY_LABELS`` set
    plus a non-empty ``definition`` and ``response``. An unknown label or a
    duplicate raises, so the report can never render an invented classification.
    Absent taxonomy is simply an empty list.
    """
    if not raw:
        return []
    if not isinstance(raw, list):
        raise ValueError(f"{technique_id}: risk_taxonomy must be a list.")
    taxonomy: list[dict[str, str]] = []
    seen: set[str] = set()
    for entry in raw:
        if not isinstance(entry, dict):
            raise ValueError(f"{technique_id}: each risk_taxonomy entry must be an object.")
        label = str(entry.get("label", "")).strip()
        if label not in RISK_TAXONOMY_LABELS:
            raise ValueError(
                f"{technique_id}: risk_taxonomy label must be one of {', '.join(RISK_TAXONOMY_LABELS)}."
            )
        if label in seen:
            raise ValueError(f"{technique_id}: duplicate risk_taxonomy label: {label}.")
        definition = str(entry.get("definition", "")).strip()
        response = str(entry.get("response", "")).strip()
        if not definition or not response:
            raise ValueError(f"{technique_id}: risk_taxonomy '{label}' needs a definition and a response.")
        seen.add(label)
        taxonomy.append({"label": label, "definition": definition, "response": response})
    return taxonomy


def technique_risk_taxonomy(
    technique_id: str, techniques_dir: Path | str | None = None
) -> list[dict[str, str]]:
    technique = technique_by_id(technique_id, techniques_dir)
    return list(technique.get("risk_taxonomy", [])) if technique else []


def normalize_technique_calibration(raw: object) -> dict[str, str]:
    if not isinstance(raw, dict):
        return {}
    calibration: dict[str, str] = {}
    for key, value in raw.items():
        profile = normalize_respondent_profile(str(key))
        text = str(value).strip()
        if profile and text:
            calibration[profile] = text
    return calibration


def technique_by_id(technique_id: str, techniques_dir: Path | str | None = None) -> dict | None:
    normalized = str(technique_id or "").strip().lower()
    for technique in load_techniques(techniques_dir):
        if technique["id"] == normalized:
            return technique
    return None


def normalize_respondent_profile(value: str | None) -> str | None:
    normalized = re.sub(r"[^a-záéíóúñü]+", "_", str(value or "").lower()).strip("_")
    aliases = {
        "business": "business",
        "negocio": "business",
        "business_owner": "business",
        "domain": "business",
        "technical": "technical",
        "tecnico": "technical",
        "técnico": "technical",
        "technology": "technical",
        "engineering": "technical",
    }
    profile = aliases.get(normalized)
    return profile if profile in VALID_RESPONDENT_PROFILES else None


def technique_prompt(
    technique_id: str,
    *,
    respondent_profile: str | None = None,
    techniques_dir: Path | str | None = None,
) -> str:
    technique = technique_by_id(technique_id, techniques_dir)
    if technique is None:
        return str(technique_id or "")
    prompt = str(technique["prompt"])
    profile = normalize_respondent_profile(respondent_profile)
    if not profile:
        return prompt
    calibration = technique.get("calibration", {})
    if not isinstance(calibration, dict):
        return prompt
    calibrated = str(calibration.get(profile, "")).strip()
    if not calibrated:
        return prompt
    return f"{prompt} Respondent calibration: {calibrated}"


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
