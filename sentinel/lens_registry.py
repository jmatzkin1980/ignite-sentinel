"""Lens knowledge registry (IMP-033).

Single declarative, versionable source for the lens knowledge that used to be
hardcoded in ``discovery.py::detect_gaps()``. Each lens lives in
``sentinel/lenses/<lens>.json`` and the team (business, product, design,
quality, technology, compliance, delivery) can add or tune checks there without
touching Python. The deterministic checklist (``detect_gaps``), the
context-request render, and future agentic skills (IMP-021/022/023) all read
this same source, so they can never diverge.

Local-first: plain JSON, no third-party parser, no network.

Check schema (per entry in a lens file's ``checks`` array):
- id: stable GAP-* id.
- severity: critical | high | medium | low.
- description: English statement of what is missing.
- rule: how the check fires.
    - "absent_tokens": fires when NONE of ``tokens`` appear in the evidence.
    - "mention_without_counterpart": fires when a surface is mentioned
      (``triggers``) but its counterpart detail (``counterparts``) is absent;
      anchors the question to the detected mention.
    - "metric_without_source": fires when a quantitative metric is present but
      none of ``suppressors`` (source/baseline words) appear.
- evidence_scope: which text the rule reads — source | technical | design |
  quality | frontend | all.
- why (optional): the field experience that motivates the check (team notes).
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from .core.io import read_json, read_json_resource
from .resources import package_json_files

_DEFAULT_LENSES_DIR = Path(__file__).resolve().parent / "lenses"
LENSES_DIR = _DEFAULT_LENSES_DIR

# Deterministic load order keeps gap emission stable. Lens files not listed
# here are appended alphabetically, so a brand-new lens still loads.
LENS_ORDER = ("business", "product", "quality", "technical", "compliance", "delivery", "design")

VALID_RULES = {
    "absent_tokens",
    "mention_without_counterpart",
    "mention_requires_counterpart",
    "metric_without_source",
    "hypothetical_without_event",
}
VALID_SCOPES = {"source", "technical", "design", "quality", "frontend", "all"}


def load_lens_checks(lenses_dir: Path | str | None = None) -> list[dict]:
    """Return the flat, ordered list of lens checks (each tagged with ``lens``)."""
    if lenses_dir is None and LENSES_DIR == _DEFAULT_LENSES_DIR:
        return _load_package_cached()
    directory = Path(lenses_dir) if lenses_dir is not None else LENSES_DIR
    return _load_path_cached(str(directory))


@lru_cache(maxsize=8)
def _load_path_cached(directory: str) -> tuple:
    path = Path(directory)
    by_name = {f.stem: f for f in sorted(path.glob("*.json"))}
    return _load_ordered_lenses(by_name)


@lru_cache(maxsize=1)
def _load_package_cached() -> tuple:
    by_name = {f.name.removesuffix(".json"): f for f in package_json_files("lenses")}
    return _load_ordered_lenses(by_name)


def _load_ordered_lenses(by_name: dict) -> tuple:
    ordered_names = [n for n in LENS_ORDER if n in by_name]
    ordered_names += [n for n in sorted(by_name) if n not in LENS_ORDER]
    checks: list[dict] = []
    for name in ordered_names:
        source = by_name[name]
        data = read_json(source, {}) if isinstance(source, Path) else read_json_resource(source, {})
        lens = data.get("lens", name)
        for raw in data.get("checks", []):
            entry = dict(raw)
            entry["lens"] = lens
            checks.append(entry)
    return tuple(checks)


def lens_checks_for_lens(lens: str, lenses_dir: Path | str | None = None) -> list[dict]:
    """All checks belonging to a given lens (business/product/.../design)."""
    return [c for c in load_lens_checks(lenses_dir) if c.get("lens") == lens]


def known_lenses(lenses_dir: Path | str | None = None) -> set[str]:
    """Set of lens names declared in the lens knowledge base.

    Single source for validating lens names supplied by agentic input
    (IMP-021 ``/annotate``): an agent gap whose lens is not declared here is
    rejected, so the runtime stays the authority and lens identity (invariant
    #1) is never bypassed.
    """
    return {check["lens"] for check in load_lens_checks(lenses_dir)}


def clear_cache() -> None:
    _load_path_cached.cache_clear()
    _load_package_cached.cache_clear()
