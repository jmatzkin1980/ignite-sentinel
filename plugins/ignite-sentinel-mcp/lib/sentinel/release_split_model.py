"""IMP-264 (H17a): the release split model as data.

`sentinel/templates/release_split_model.json` is the framework's knowledge on
splitting a v2 brief into a series of releases:

* signals for splitting (7) and for not splitting (5), with no numeric threshold;
* cut criteria (14) and patterns carried to release level (24), each with its
  question, what it contains and inherits, the contract the siblings share,
  parallel or chained, and when not to use it;
* the flow (step 0 plus 12 steps), the stopping criterion and the cut evaluation;
* the ordering rule in 5 steps with MoSCoW (Must at most 60 %, about 20 % Could);
* release types and interleave subtypes, release base vs. backlog enabler, the
  spike contract, release INVEST and the anti-patterns.

/split --assess reads the signals, the release-split skill walks the flow, and
the partition validation checks the rules. The loader validates the model with a
stdlib validator (IMP-103); `schemas/release_split_model.schema.json` documents
the contract and `tests/test_release_split_model.py` keeps both in step.

The enabler boundary lives in the backlog slicing model: this model cites it
and never copies it.
"""
from __future__ import annotations

import re
from functools import lru_cache
from typing import Any

from .resources import read_package_json

MODEL_FILE = "release_split_model.json"

REQUIRED_SECTIONS = {
    "model", "version", "signals", "cut_criteria", "patterns", "flow", "cut_evaluation",
    "ordering", "release_types", "base_vs_enabler", "spike", "release_invest", "anti_patterns",
    "series_fields",
}
PATTERN_FIELDS = {"id", "name", "origin", "question", "contains", "inherits", "contract", "shape", "not_use_if"}
VALID_SHAPES = {"parallel", "chained", "depends", "not_a_cut"}
RELEASE_TYPES = {
    "enabler", "functional", "measuring", "conditional", "interleaved", "integrator",
    "segment_cutover", "already_built",
}
INVEST_KEYS = ["independent", "negotiable", "valuable", "estimable", "small", "testable"]
# the anti-patterns the partition validation (IMP-266) rejects deterministically
VALIDATED_ANTI_PATTERNS = {
    "layer_cut", "enabler_without_demo", "empty_release", "spike_without_questions",
    "release_without_outcome_metric", "cut_without_source",
}
COUNTS = {"split": 7, "no_split": 5, "cut_criteria": 14, "patterns": 24, "step_0": 3, "steps": 12, "ordering": 5}
_P9_FORBIDDEN = {"the rule is legal", "the rule is regulatory", "the rule is a Must"}


@lru_cache(maxsize=1)
def _load_package() -> dict[str, Any]:
    return read_package_json("templates", MODEL_FILE)


def load_release_split_model(override: dict[str, Any] | None = None) -> dict[str, Any]:
    """The validated model. ``override`` (uncached) lets tests inject a model."""
    model = override if override is not None else _load_package()
    problems = validate_model(model)
    if problems:
        raise ValueError("release split model: " + "; ".join(problems))
    return model


def clear_cache() -> None:
    _load_package.cache_clear()


def enabler_boundary() -> dict[str, Any]:
    """The enabler boundary the model cites, read from the backlog slicing model."""
    from .slicing_model import load_slicing_model

    return load_slicing_model()["enabler_boundary"]


def _text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _ids(items: list[dict[str, Any]], prefix: str, count: int, label: str, problems: list[str]) -> None:
    expected = [f"{prefix}{n}" for n in range(1, count + 1)]
    found = [str(item.get("id", "")) for item in items]
    if found != expected:
        problems.append(f"{label}: expected {count} ids {expected[0]}..{expected[-1]} in order, found {len(found)}")


def validate_model(model: dict[str, Any]) -> list[str]:
    """Structural problems; an empty list means the model is usable."""
    problems: list[str] = []
    missing = sorted(REQUIRED_SECTIONS - set(model))
    if missing:
        return [f"missing sections: {', '.join(missing)}"]

    signals = model["signals"]
    for kind, prefix in (("split", "S"), ("no_split", "N")):
        items = signals.get(kind, [])
        _ids(items, prefix, COUNTS[kind], f"signals {kind}", problems)
        problems.extend(f"signals {kind} {item.get('id')}: needs key and text"
                        for item in items if not (_text(item.get("key")) and _text(item.get("text"))))

    criteria = model["cut_criteria"].get("items", [])
    _ids(criteria, "C", COUNTS["cut_criteria"], "cut criteria", problems)
    problems.extend(f"{item.get('id')}: a cut criterion needs name and applies"
                    for item in criteria if not (_text(item.get("name")) and _text(item.get("applies"))))
    c14 = next((item for item in criteria if item.get("id") == "C14"), {})
    if c14 and c14.get("never_alone") is not True:
        problems.append("C14: session size is never the only criterion (never_alone)")

    patterns = model["patterns"].get("items", [])
    _ids(patterns, "P", COUNTS["patterns"], "patterns", problems)
    pattern_ids = {str(item.get("id")) for item in patterns}
    for item in patterns:
        pid = item.get("id")
        absent = sorted(PATTERN_FIELDS - set(item))
        if absent:
            problems.append(f"{pid}: missing {', '.join(absent)}")
            continue
        for field in ("name", "question", "contains", "contract"):
            if not _text(item[field]):
                problems.append(f"{pid}: {field} is empty")
        if item["shape"] not in VALID_SHAPES:
            problems.append(f"{pid}: unknown shape {item['shape']!r}; use {', '.join(sorted(VALID_SHAPES))}")
        if not isinstance(item["not_use_if"], list):
            problems.append(f"{pid}: not_use_if must be a list")
    p9 = next((item for item in patterns if item.get("id") == "P9"), None)
    if p9 is not None and (not _P9_FORBIDDEN <= set(p9.get("not_use_if", [])) or p9.get("requires_restored_in") is not True):
        problems.append("P9: relaxing a rule is never for a legal, regulatory or Must rule and always names restored_in")

    flow = model["flow"]
    step0 = flow.get("step_0", {}).get("questions", [])
    if len(step0) != COUNTS["step_0"]:
        problems.append(f"flow step 0: expected {COUNTS['step_0']} questions, found {len(step0)}")
    steps = flow.get("steps", [])
    if [step.get("step") for step in steps] != list(range(1, COUNTS["steps"] + 1)):
        problems.append(f"flow: expected steps 1..{COUNTS['steps']} in order")
    for step in steps:
        unknown = [pid for pid in step.get("patterns", []) if pid not in pattern_ids]
        if unknown or not step.get("patterns"):
            problems.append(f"flow step {step.get('step')}: unknown or missing patterns {', '.join(unknown) or '(none)'}")
    if not flow.get("stopping_criterion", {}).get("items"):
        problems.append("flow: the stopping criterion is missing")
    if not model["cut_evaluation"]:
        problems.append("cut evaluation is empty")

    ordering = model["ordering"]
    combination = ordering.get("combination", [])
    methods = {method.get("key") for method in ordering.get("methods", [])}
    if [step.get("step") for step in combination] != list(range(1, COUNTS["ordering"] + 1)):
        problems.append(f"ordering: expected a {COUNTS['ordering']}-step combination")
    problems.extend(f"ordering step {step.get('step')}: unknown method {step.get('method')!r}"
                    for step in combination if step.get("method") not in methods)
    moscow = ordering.get("moscow", {})
    if moscow.get("must_max_share") != 0.6 or moscow.get("could_target_share") != 0.2:
        problems.append("ordering: MoSCoW is Must at most 0.6 and Could about 0.2")

    types = model["release_types"]
    keys = {item.get("key") for item in types.get("items", [])}
    if keys != RELEASE_TYPES:
        problems.append(f"release types: expected {', '.join(sorted(RELEASE_TYPES))}")
    if len(types.get("interleave_subtypes", [])) != 2:
        problems.append("release types: two interleave subtypes")

    source = model["base_vs_enabler"].get("boundary_source", {})
    if source.get("model") != "slicing/backlog_slicing_model.json" or source.get("field") != "enabler_boundary":
        problems.append("base vs enabler: the boundary is cited from slicing/backlog_slicing_model.json#enabler_boundary")

    spike = model["spike"]
    if (spike.get("questions_min"), spike.get("questions_max")) != (1, 3) or spike.get("time_box_required") is not True \
            or spike.get("decision_record") != "DEC" or spike.get("pattern") not in pattern_ids \
            or spike.get("release_type") not in RELEASE_TYPES:
        problems.append("spike: 1-3 questions, a time-box and a DEC")

    if [item.get("key") for item in model["release_invest"]] != INVEST_KEYS:
        problems.append(f"release INVEST: expected {', '.join(INVEST_KEYS)}")

    anti = model["anti_patterns"]
    validated = {item.get("key") for item in anti if item.get("validated") is True}
    for key in sorted(VALIDATED_ANTI_PATTERNS - validated):
        problems.append(f"anti-pattern {key}: the partition validation checks it, mark it validated")
    for key in sorted(validated - VALIDATED_ANTI_PATTERNS):
        problems.append(f"anti-pattern {key}: marked validated but no partition check exists")
    if [item.get("id") for item in anti] != [f"AP{n}" for n in range(1, len(anti) + 1)]:
        problems.append("anti-patterns: ids AP1..APn in order")

    for field, section in model["series_fields"].items():
        if not re.fullmatch(r"[a-z_]+", str(field)) or section not in model:
            problems.append(f"series field {field}: maps to unknown section {section!r}")
    return problems
