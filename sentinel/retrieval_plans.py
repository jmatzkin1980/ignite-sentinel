"""Declarative retrieval plans for generation workflows.

Plans live in ``sentinel/retrieval_plans/<workflow>.json`` so section queries,
filters, budgets, and lens vocabulary can evolve without Python edits.
"""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from .core.io import read_json
from .lens_registry import lens_checks_for_lens
from .resources import read_package_json


_DEFAULT_RETRIEVAL_PLANS_DIR = Path(__file__).resolve().parent / "retrieval_plans"
RETRIEVAL_PLANS_DIR = _DEFAULT_RETRIEVAL_PLANS_DIR


def load_retrieval_plan(
    workflow: str,
    plans_dir: Path | str | None = None,
    override: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Load and normalize a workflow retrieval plan.

    ``override`` is intentionally uncached so tests can inject a plan without
    mutating the package JSON. ``plans_dir`` supports fixture directories.
    """
    if override is not None:
        return normalize_plan(workflow, override)
    if plans_dir is None and RETRIEVAL_PLANS_DIR == _DEFAULT_RETRIEVAL_PLANS_DIR:
        return _load_package_cached(workflow)
    directory = Path(plans_dir) if plans_dir is not None else RETRIEVAL_PLANS_DIR
    return _load_path_cached(str(directory), workflow)


@lru_cache(maxsize=16)
def _load_path_cached(directory: str, workflow: str) -> dict[str, Any]:
    path = Path(directory) / f"{workflow}.json"
    data = read_json(path, {})
    return normalize_plan(workflow, data)


@lru_cache(maxsize=16)
def _load_package_cached(workflow: str) -> dict[str, Any]:
    data = read_package_json("retrieval_plans", f"{workflow}.json")
    return normalize_plan(workflow, data)


def clear_cache() -> None:
    _load_path_cached.cache_clear()
    _load_package_cached.cache_clear()


def normalize_plan(workflow: str, data: dict[str, Any]) -> dict[str, Any]:
    sections = data.get("sections", {})
    if not isinstance(sections, dict):
        raise ValueError(f"Retrieval plan {workflow} must define object field 'sections'.")
    normalized_sections: dict[str, dict[str, Any]] = {}
    for name, raw in sections.items():
        if not isinstance(raw, dict):
            raise ValueError(f"Retrieval plan section {name} must be an object.")
        query = str(raw.get("query", "")).strip()
        if not query:
            raise ValueError(f"Retrieval plan section {name} must define a non-empty query.")
        filters = raw.get("filters", {})
        if not isinstance(filters, dict):
            raise ValueError(f"Retrieval plan section {name} filters must be an object.")
        normalized_sections[str(name)] = {
            "query": query,
            "domain": raw.get("domain"),
            "filters": filters,
            "limit": int(raw.get("limit", data.get("default_limit", 5))),
            "budget_chars": int(raw.get("budget_chars", data.get("default_budget_chars", 2000))),
            "summary_chars": int(raw.get("summary_chars", data.get("default_summary_chars", 240))),
            "lenses": [str(item) for item in raw.get("lenses", [])],
            "source_sections": [str(item) for item in raw.get("source_sections", [])],
        }
    return {
        "workflow": str(data.get("workflow", workflow)),
        "version": int(data.get("version", 1)),
        # IMP-127: optional global character ceiling across all pack sections.
        # 0 means "no global cap" so plans that omit it keep prior behavior; the
        # cross-section chunk dedup applies regardless.
        "global_budget_chars": int(data.get("global_budget_chars", 0)),
        "sections": normalized_sections,
    }


def compose_plan_query(plan: dict[str, Any], source_context: str = "") -> str:
    parts = [str(plan["query"])]
    lens_terms = lens_terms_for_plan(plan)
    if lens_terms:
        parts.append("Lens vocabulary: " + " ".join(lens_terms))
    if source_context.strip():
        parts.append(source_context.strip())
    return "\n\n".join(parts)


def lens_terms_for_plan(plan: dict[str, Any]) -> list[str]:
    terms: list[str] = []
    seen: set[str] = set()
    for lens in plan.get("lenses", []):
        for check in lens_checks_for_lens(str(lens)):
            for field in ("tokens", "triggers", "counterparts", "suppressors"):
                values = check.get(field, [])
                if isinstance(values, str):
                    values = [values]
                for value in values:
                    for token in re.findall(r"[A-Za-z0-9_-]{3,}", str(value).lower()):
                        if token not in seen:
                            seen.add(token)
                            terms.append(token)
    return terms[:80]


def select_source_context(documents: dict[str, str], plan: dict[str, Any]) -> str:
    """Pick source excerpts by declared sections, then query-token relevance."""
    budget = int(plan.get("budget_chars", 2000))
    selected: list[str] = []
    for wanted in plan.get("source_sections", []):
        for label, text in documents.items():
            excerpt = section_excerpt(text, wanted)
            if excerpt:
                selected.append(f"[{label}:{wanted}]\n{excerpt}")
    if not selected:
        selected = relevant_paragraphs(documents, str(plan.get("query", "")), budget)
    context = "\n\n".join(selected)
    return context[:budget].rstrip()


def section_excerpt(text: str, wanted: str) -> str:
    if not text.strip() or not wanted.strip():
        return ""
    wanted_lower = wanted.lower()
    lines = text.splitlines()
    starts = []
    for index, line in enumerate(lines):
        if not line.lstrip().startswith("#"):
            continue
        heading = line.lstrip("#").strip().lower()
        if wanted_lower in heading:
            starts.append(index)
    if not starts:
        return ""
    start = starts[0]
    end = len(lines)
    level = len(lines[start]) - len(lines[start].lstrip("#"))
    for index in range(start + 1, len(lines)):
        line = lines[index]
        if line.lstrip().startswith("#"):
            next_level = len(line) - len(line.lstrip("#"))
            if next_level <= level:
                end = index
                break
    return "\n".join(lines[start:end]).strip()


def relevant_paragraphs(documents: dict[str, str], query: str, budget: int) -> list[str]:
    query_tokens = set(re.findall(r"[A-Za-z0-9_-]{3,}", query.lower()))
    candidates: list[tuple[int, str, str]] = []
    for label, text in documents.items():
        paragraphs = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
        for paragraph in paragraphs:
            tokens = set(re.findall(r"[A-Za-z0-9_-]{3,}", paragraph.lower()))
            score = len(query_tokens & tokens)
            if score:
                candidates.append((score, label, paragraph))
    candidates.sort(key=lambda item: (-item[0], item[1], item[2]))
    selected: list[str] = []
    used = 0
    for _, label, paragraph in candidates:
        chunk = f"[{label}]\n{paragraph}"
        if selected and used + len(chunk) > budget:
            continue
        selected.append(chunk)
        used += len(chunk)
        if used >= budget:
            break
    return selected
