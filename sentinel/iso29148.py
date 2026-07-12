"""ISO/IEC/IEEE 29148 requirement-quality rubric mapped to Ignite checks (IMP-189).

A declarative, auditable bridge between the nine individual-requirement quality
characteristics of ISO 29148 (clause 9.4.2) and the deterministic checks Ignite
already runs. Two versionable JSON sources under ``sentinel/iso29148/``:

- ``characteristics.json`` — the nine characteristics, each declaring, if no
  check covers it, whether that absence is an honest ``heuristic_gap`` (a
  deterministic rule is feasible but not yet written) or ``out_of_scope`` (no
  local deterministic heuristic can decide it without simulating domain
  knowledge — e.g. Complete, Feasible, Correct, Necessary).
- ``check_catalog.json`` — each existing check declares ``covers_29148: [...]``,
  inert metadata that is the single source of coverage. Coverage flows ONLY from
  the catalog, so the report cannot drift from a hand-maintained per-character
  list.

The report (surfaced in ``/validate``) joins the two: a characteristic is
``covered`` when at least one catalogued check lists it; otherwise it falls back
to its declared disposition and reason. Nothing here calls an LLM.

Molde de registry: ``lens_registry.py`` / ``risk_category_registry.py`` — add
JSON, not Python. The one live rule this module owns (verifiability of a
requirement statement) is deterministic and cites every finding verbatim.
"""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

from .core.io import read_json, read_json_resource
from .ears import requirement_statements_from_markdown
from .resources import package_resource

_DEFAULT_ISO_DIR = Path(__file__).resolve().parent / "iso29148"
ISO_DIR = _DEFAULT_ISO_DIR

# Canonical ISO 29148 order, used to sort the report deterministically and to
# validate that the data file declares exactly these nine characteristics.
CHARACTERISTIC_ORDER = (
    "necessary",
    "appropriate",
    "unambiguous",
    "complete",
    "singular",
    "feasible",
    "verifiable",
    "correct",
    "conforming",
)

VALID_DISPOSITIONS = {"heuristic_gap", "out_of_scope"}

# A requirement statement is verifiable when it carries a measurable or
# observable acceptance anchor: an acceptance/verification/test word, or a
# concrete numeric/temporal quantity. Deliberately shares vocabulary with
# ``ears.py`` so the two never disagree about what "verifiable" wording is.
_VERIFIABILITY_ANCHOR_RE = re.compile(
    r"\b("
    r"acceptance|accepted|criteria|criterion|verify|verified|verifiable|validate|validated|"
    r"test|tested|measure|measured|measurable|metric|baseline|target|threshold|kpi|sla|audit|evidence|"
    r"aceptacion|aceptación|criterio|criterios|verificar|verificable|validar|validado|prueba|probar|"
    r"medir|medido|medible|metrica|métrica|objetivo|umbral|evidencia|auditoria|auditoría"
    r")\b|(?:\d+(?:[.,]\d+)?\s?"
    r"(?:%|percent|por ciento|seconds?|segundos?|minutes?|minutos?|hours?|horas?|days?|dias|días))",
    re.I,
)


def load_characteristics(iso_dir: Path | str | None = None) -> list[dict]:
    """Return the nine ISO 29148 characteristics in canonical order."""
    if iso_dir is None and ISO_DIR == _DEFAULT_ISO_DIR:
        return list(_load_characteristics_package())
    directory = Path(iso_dir) if iso_dir is not None else ISO_DIR
    return list(_load_characteristics_path(str(directory)))


def load_check_catalog(iso_dir: Path | str | None = None) -> list[dict]:
    """Return the catalogued checks, each with its inert ``covers_29148`` map."""
    if iso_dir is None and ISO_DIR == _DEFAULT_ISO_DIR:
        return list(_load_catalog_package())
    directory = Path(iso_dir) if iso_dir is not None else ISO_DIR
    return list(_load_catalog_path(str(directory)))


@lru_cache(maxsize=1)
def _load_characteristics_package() -> tuple[dict, ...]:
    data = read_json_resource(package_resource("iso29148", "characteristics.json"), {})
    return _normalize_characteristics(data)


@lru_cache(maxsize=8)
def _load_characteristics_path(directory: str) -> tuple[dict, ...]:
    data = read_json(Path(directory) / "characteristics.json", {})
    return _normalize_characteristics(data)


@lru_cache(maxsize=1)
def _load_catalog_package() -> tuple[dict, ...]:
    data = read_json_resource(package_resource("iso29148", "check_catalog.json"), {})
    return _normalize_catalog(data)


@lru_cache(maxsize=8)
def _load_catalog_path(directory: str) -> tuple[dict, ...]:
    data = read_json(Path(directory) / "check_catalog.json", {})
    return _normalize_catalog(data)


def _normalize_characteristics(data: dict) -> tuple[dict, ...]:
    by_id = {}
    for raw in data.get("characteristics", []):
        char_id = str(raw.get("id", "")).strip().lower()
        if not char_id:
            continue
        disposition = str(raw.get("when_uncovered", "heuristic_gap")).strip().lower()
        if disposition not in VALID_DISPOSITIONS:
            disposition = "heuristic_gap"
        by_id[char_id] = {
            "id": char_id,
            "label": str(raw.get("label", char_id.title())).strip(),
            "description": str(raw.get("description", "")).strip(),
            "when_uncovered": disposition,
            "reason": str(raw.get("reason", "")).strip(),
        }
    ordered = [by_id[name] for name in CHARACTERISTIC_ORDER if name in by_id]
    ordered += [by_id[name] for name in sorted(by_id) if name not in CHARACTERISTIC_ORDER]
    return tuple(ordered)


def _normalize_catalog(data: dict) -> tuple[dict, ...]:
    checks: list[dict] = []
    for raw in data.get("checks", []):
        check_id = str(raw.get("id", "")).strip()
        if not check_id:
            continue
        covers = raw.get("covers_29148", [])
        covers_list = [str(item).strip().lower() for item in covers if str(item).strip()] if isinstance(covers, list) else []
        checks.append(
            {
                "id": check_id,
                "label": str(raw.get("label", check_id)).strip(),
                "module": str(raw.get("module", "")).strip(),
                "imp": str(raw.get("imp", "")).strip(),
                "covers_29148": covers_list,
                "note": str(raw.get("note", "")).strip(),
            }
        )
    return tuple(checks)


def coverage_by_characteristic(iso_dir: Path | str | None = None) -> dict[str, list[str]]:
    """Map each characteristic id to the ids of checks that declare covering it."""
    coverage: dict[str, list[str]] = {}
    for check in load_check_catalog(iso_dir):
        for char_id in check["covers_29148"]:
            coverage.setdefault(char_id, []).append(check["id"])
    return coverage


def verifiability_findings(requirements_markdown: str) -> list[dict[str, str]]:
    """NEW deterministic rule (IMP-189): requirement statements lacking a
    verifiability anchor.

    Reuses the same statement extraction as the EARS scorer, so it covers the
    primary requirement and every confirmed ``REQ-EARS-*`` row — including
    well-formed EARS statements, which the ``ears.missing_verification`` signal
    intentionally leaves unscrutinized. Each finding cites the offending
    statement verbatim; silence when a statement already carries an anchor.
    """
    findings: list[dict[str, str]] = []
    for item in requirement_statements_from_markdown(requirements_markdown):
        statement = str(item.get("statement", "")).strip()
        if not statement or _VERIFIABILITY_ANCHOR_RE.search(statement):
            continue
        findings.append(
            {
                "id": "iso29148.verifiability_anchor",
                "characteristic": "verifiable",
                "severity": "low",
                "statement_id": str(item.get("id", "")).strip(),
                "source": str(item.get("source", "")).strip(),
                "message": (
                    "Requirement statement carries no measurable or observable acceptance anchor "
                    "(no metric, threshold, or acceptance/test signal), so its satisfaction cannot be verified."
                ),
                "statement": statement,
            }
        )
    return findings


def coverage_report(requirements_markdown: str = "", iso_dir: Path | str | None = None) -> dict[str, object]:
    """The ISO 29148 coverage report surfaced by ``/validate``.

    Joins the declared characteristics with the check catalog: a characteristic
    is ``covered`` when a catalogued check lists it, otherwise it takes its
    declared disposition (``heuristic_gap`` or ``out_of_scope``) and reason. The
    live verifiability rule runs over ``requirements.md`` (when present) so the
    report shows both the static map and any concrete unverifiable statements.
    """
    characteristics = load_characteristics(iso_dir)
    coverage = coverage_by_characteristic(iso_dir)
    rows: list[dict[str, object]] = []
    summary = {"covered": 0, "heuristic_gap": 0, "out_of_scope": 0}
    for char in characteristics:
        covered_by = coverage.get(char["id"], [])
        if covered_by:
            status = "covered"
            reason = ""
        else:
            status = char["when_uncovered"]
            reason = char["reason"]
        summary[status] = summary.get(status, 0) + 1
        rows.append(
            {
                "id": char["id"],
                "label": char["label"],
                "description": char["description"],
                "status": status,
                "covered_by": covered_by,
                "reason": reason,
            }
        )
    findings = verifiability_findings(requirements_markdown) if requirements_markdown else []
    return {
        "standard": "ISO/IEC/IEEE 29148:2018",
        "scope": "individual requirement quality characteristics (clause 9.4.2)",
        "characteristics": rows,
        "summary": {**summary, "total": len(rows)},
        "verifiability_findings": findings,
    }


def clear_cache() -> None:
    _load_characteristics_package.cache_clear()
    _load_characteristics_path.cache_clear()
    _load_catalog_package.cache_clear()
    _load_catalog_path.cache_clear()
