"""EARS requirement normalization (IMP-026).

EARS (Easy Approach to Requirements Syntax) turns prose into testable,
agent-parseable statements in five canonical patterns:

- ubiquitous:      "The <system> shall <response>."
- event-driven:    "When <trigger>, the <system> shall <response>."
- state-driven:    "While <state>, the <system> shall <response>."
- unwanted:        "If <condition>, then the <system> shall <response>."
- optional:        "Where <feature>, the <system> shall <response>."

The runtime never invents EARS: an agent proposes a normalized statement (e.g.
as the substantive answer to a functional gap) and this module validates the
structure. Statements that do not match a pattern stay as prose (invariant #3:
evidence or silence — only confirmed, well-formed statements are normalized).

English and Spanish keyword variants are accepted (When/Cuando, While/Mientras,
If…then/Si…entonces, Where/Donde, shall/must/should/debe…).
"""
from __future__ import annotations

import re

_SHALL = r"(?:shall|will|must|should|debe\w*)"
_REQ_EARS_ID_RE = re.compile(r"^`?(REQ-EARS-\d{3})`?$")

AMBIGUOUS_TERMS: tuple[str, ...] = (
    "adequate",
    "appropriate",
    "as needed",
    "easy",
    "efficient",
    "fast",
    "flexible",
    "intuitive",
    "nice",
    "quick",
    "quickly",
    "robust",
    "seamless",
    "simple",
    "soon",
    "user friendly",
    "usable",
    "various",
    "better",
    "mejor",
    "rapido",
    "rapida",
    "rapidez",
    "facil",
    "intuitivo",
    "intuitiva",
    "adecuado",
    "adecuada",
    "eficiente",
    "flexible",
    "robusto",
    "robusta",
    "simple",
    "pronto",
    "usable",
    "amigable",
)

UNANCHORED_QUANTIFIER_TERMS: tuple[str, ...] = (
    "as needed",
    "fast",
    "quick",
    "quickly",
    "soon",
    "various",
    "several",
    "many",
    "multiple",
    "frequent",
    "frequently",
    "often",
    "rapid",
    "rapido",
    "rapida",
    "rapidez",
    "pronto",
    "varios",
    "varias",
    "muchos",
    "muchas",
    "frecuente",
    "frecuentemente",
)

_TEMPORAL_AMBIGUITY_TERMS = {
    "as needed",
    "fast",
    "quick",
    "quickly",
    "soon",
    "frequent",
    "frequently",
    "often",
    "rapid",
    "rapido",
    "rapida",
    "rapidez",
    "pronto",
    "frecuente",
    "frecuentemente",
}
_QUANTITY_AMBIGUITY_TERMS = {
    "various",
    "several",
    "many",
    "multiple",
    "varios",
    "varias",
    "muchos",
    "muchas",
}
_SCOPE_AMBIGUITY_TERMS = {
    "adequate",
    "appropriate",
    "flexible",
    "robust",
    "adecuado",
    "adecuada",
    "flexible",
    "robusto",
    "robusta",
}
_SUBJECTIVE_AMBIGUITY_TERMS = {
    "easy",
    "efficient",
    "intuitive",
    "nice",
    "seamless",
    "simple",
    "user friendly",
    "usable",
    "better",
    "mejor",
    "facil",
    "intuitivo",
    "intuitiva",
    "eficiente",
    "simple",
    "usable",
    "amigable",
}
_AMBIGUITY_CATEGORY_WHY: dict[str, str] = {
    "temporal": "Timing words need an explicit threshold or SLA before QA can verify them.",
    "scope": "Scope or multi-action wording hides which behavior, owner, or boundary must be implemented and tested.",
    "quantity": "Quantity words need counts, ranges, or thresholds before acceptance can be measured.",
    "subjective": "Subjective quality words need observable criteria before teams can implement or test them consistently.",
}

_ACTION_VERBS = (
    "allow",
    "approve",
    "audit",
    "block",
    "calculate",
    "create",
    "delete",
    "display",
    "export",
    "flag",
    "import",
    "log",
    "notify",
    "record",
    "reject",
    "route",
    "send",
    "show",
    "store",
    "update",
    "validate",
    "aprobar",
    "auditar",
    "bloquear",
    "calcular",
    "crear",
    "eliminar",
    "enviar",
    "exportar",
    "importar",
    "marcar",
    "mostrar",
    "notificar",
    "permitir",
    "rechazar",
    "registrar",
    "rutear",
    "validar",
)
_ACTION_VERB_RE = "|".join(re.escape(verb) for verb in _ACTION_VERBS)
_COMPOUND_ACTION_RE = re.compile(
    rf"\b(?:and|or|y|o)\s+(?:then\s+|entonces\s+)?(?:{_SHALL}\s+)?(?:{_ACTION_VERB_RE})\b",
    re.I,
)
_NUMERIC_ANCHOR_RE = re.compile(
    r"\b(?:\d+(?:[.,]\d+)?|one|two|three|four|five|six|seven|eight|nine|ten|"
    r"uno|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez)\b|"
    r"(?:%|percent|por ciento|seconds?|segundos?|minutes?|minutos?|hours?|horas?|days?|dias|días|"
    r"sla|kpi|metric|métrica|metrica|threshold|umbral)",
    re.I,
)

_PASSIVE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\b(?:is|are|was|were|be|been|being)\s+(?:\w+\s+){0,2}\w+(?:ed|en)\b", re.I),
    re.compile(r"\b(?:es|son|fue|fueron|sera|seran|será|serán)\s+(?:\w+\s+){0,2}\w+(?:ado|ada|ados|adas|ido|ida|idos|idas)\b", re.I),
)

_VERIFICATION_RE = re.compile(
    r"\b("
    r"acceptance|accepted|criteria|criterion|verify|verified|validate|validated|test|tested|"
    r"measure|measured|metric|baseline|target|kpi|sla|audit|evidence|"
    r"aceptacion|aceptación|criterio|criterios|verificar|validar|validado|prueba|probar|"
    r"medir|medido|metrica|métrica|baseline|objetivo|evidencia|auditoria|auditoría"
    r")\b|(?:\d+(?:[.,]\d+)?\s?(?:%|percent|por ciento|seconds?|segundos?|minutes?|minutos?|hours?|horas?|days?|dias|días))",
    re.I,
)

# Order matters: the conditional patterns are checked before the ubiquitous one.
EARS_PATTERNS: dict[str, re.Pattern[str]] = {
    "event": re.compile(rf"^(?:when|cuando)\s+.+\s+{_SHALL}\s+.+", re.I),
    "state": re.compile(rf"^(?:while|mientras)\s+.+\s+{_SHALL}\s+.+", re.I),
    "unwanted": re.compile(rf"^(?:if|si)\s+.+?(?:\s+(?:then|entonces))?\s+.*{_SHALL}\s+.+", re.I),
    "optional": re.compile(rf"^(?:where|donde)\s+.+\s+{_SHALL}\s+.+", re.I),
    "ubiquitous": re.compile(rf"^(?:the|el|la|los|las)\s+.+\s+{_SHALL}\s+.+", re.I),
}

_PATTERN_ORDER = ("event", "state", "unwanted", "optional", "ubiquitous")


def classify_ears(text: str) -> str | None:
    """Return the EARS pattern name a statement matches, or None if it is not EARS."""
    normalized = " ".join(str(text).strip().split())
    if not normalized:
        return None
    for name in _PATTERN_ORDER:
        if EARS_PATTERNS[name].match(normalized):
            return name
    return None


def is_ears(text: str) -> bool:
    return classify_ears(text) is not None


def score_requirement_quality(text: str) -> dict[str, object]:
    """Score whether a requirement statement is testable enough to act on.

    The scorer is intentionally heuristic and non-authoritative. It never
    rewrites the statement; it emits cited signals that /maturity and /validate
    can surface before downstream agents treat vague prose as executable truth.
    """
    normalized = " ".join(str(text).strip().split())
    if not normalized:
        return {
            "score": 0.0,
            "classification": "empty",
            "ears_pattern": None,
            "signals": [
                {
                    "id": "empty_statement",
                    "severity": "high",
                    "message": "Requirement statement is empty.",
                    "fragment": "",
                }
            ],
        }
    signals: list[dict[str, str]] = []
    ears_pattern = classify_ears(normalized)
    if not ears_pattern:
        signals.append(
            {
                "id": "not_ears_normalizable",
                "severity": "medium",
                "message": "Statement is not written in a recognized EARS pattern.",
                "fragment": _excerpt(normalized),
            }
        )
    compound = _compound_statement_fragment(normalized)
    if compound:
        signals.append(
            _quality_signal(
                "compound_statement",
                "medium",
                "Compound scope statement appears to combine more than one required system action.",
                compound,
                "scope",
            )
        )
    unanchored_quantifiers = _matched_unanchored_quantifiers(normalized)
    for term in unanchored_quantifiers:
        category = _ambiguity_category_for_term(term)
        signals.append(
            _quality_signal(
                "unanchored_quantifier",
                "medium",
                f"Unanchored {category} term lacks a nearby numeric anchor: {term}.",
                _excerpt_around(normalized, term),
                category,
            )
        )
    unanchored_terms = {term.lower() for term in unanchored_quantifiers}
    for term in _matched_ambiguous_terms(normalized):
        if term.lower() in unanchored_terms:
            continue
        category = _ambiguity_category_for_term(term)
        signals.append(
            _quality_signal(
                "ambiguous_term",
                "medium",
                f"Ambiguous {category} term: {term}.",
                _excerpt_around(normalized, term),
                category,
            )
        )
    passive = _passive_match(normalized)
    if passive:
        signals.append(
            {
                "id": "passive_voice",
                "severity": "low",
                "message": "Passive voice can hide the actor or accountable system.",
                "fragment": _excerpt_around(normalized, passive),
            }
        )
    if not _VERIFICATION_RE.search(normalized) and not ears_pattern:
        signals.append(
            {
                "id": "missing_verification",
                "severity": "medium",
                "message": "Statement lacks an explicit verification, metric, acceptance, or test signal.",
                "fragment": _excerpt(normalized),
            }
        )
    penalty = 0.0
    for signal in signals:
        if signal["id"] == "ambiguous_term":
            penalty += 0.10
        elif signal["severity"] == "high":
            penalty += 0.40
        elif signal["severity"] == "medium":
            penalty += 0.25
        else:
            penalty += 0.15
    score = max(0.0, round(1.0 - min(penalty, 1.0), 3))
    if score >= 0.8:
        classification = "testable"
    elif score >= 0.55:
        classification = "needs-review"
    else:
        classification = "weak"
    return {
        "score": score,
        "classification": classification,
        "ears_pattern": ears_pattern,
        "signals": signals,
    }


def requirements_quality_report(markdown_text: str) -> dict[str, object]:
    statements = requirement_statements_from_markdown(markdown_text)
    scored: list[dict[str, object]] = []
    for item in statements:
        result = score_requirement_quality(str(item["statement"]))
        scored.append({**item, **result})
    average_score = round(sum(float(item["score"]) for item in scored) / len(scored), 3) if scored else 0.0
    counts: dict[str, int] = {}
    for item in scored:
        classification = str(item["classification"])
        counts[classification] = counts.get(classification, 0) + 1
    return {
        "score": average_score,
        "statement_count": len(scored),
        "classifications": counts,
        "statements": scored,
        "warnings": [
            {
                "statement_id": item["id"],
                "signal_id": signal["id"],
                "message": signal["message"],
                "fragment": signal["fragment"],
            }
            for item in scored
            for signal in item.get("signals", [])
            if isinstance(signal, dict)
        ],
    }


def requirement_statements_from_markdown(markdown_text: str) -> list[dict[str, str]]:
    lines = str(markdown_text).splitlines()
    statements: list[dict[str, str]] = []
    primary_lines: list[str] = []
    in_primary = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("## "):
            in_primary = stripped.lower().startswith("## req-001")
            continue
        if not in_primary or not stripped:
            continue
        if stripped.startswith("#"):
            continue
        if stripped.startswith("- Source:") or stripped.startswith("- Status:") or stripped.startswith("- Domains:"):
            continue
        primary_lines.append(stripped)
    primary_statement = " ".join(primary_lines).strip()
    if primary_statement:
        statements.append({"id": "REQ-001", "statement": primary_statement, "source": "02_requirements/requirements.md"})
    for line in lines:
        stripped = line.strip()
        if not stripped.startswith("|") or "REQ-EARS-" not in stripped:
            continue
        cells = [cell.strip().replace("`", "") for cell in stripped.strip("|").split("|")]
        if len(cells) < 4 or not _REQ_EARS_ID_RE.match(cells[0]):
            continue
        statements.append({"id": cells[0], "statement": cells[2], "source": cells[3]})
    return statements


def _quality_signal(
    signal_id: str,
    severity: str,
    message: str,
    fragment: str,
    category: str,
) -> dict[str, str]:
    why_it_matters = _AMBIGUITY_CATEGORY_WHY[category]
    return {
        "id": signal_id,
        "severity": severity,
        "category": category,
        "message": f"{message} Category: {category}. Why it matters: {why_it_matters}",
        "why_it_matters": why_it_matters,
        "fragment": fragment,
    }


def _ambiguity_category_for_term(term: str) -> str:
    normalized = term.lower()
    if normalized in _TEMPORAL_AMBIGUITY_TERMS:
        return "temporal"
    if normalized in _QUANTITY_AMBIGUITY_TERMS:
        return "quantity"
    if normalized in _SCOPE_AMBIGUITY_TERMS:
        return "scope"
    return "subjective"


def _compound_statement_fragment(text: str) -> str:
    match = _COMPOUND_ACTION_RE.search(text)
    if not match:
        return ""
    return _excerpt(text)


def _matched_unanchored_quantifiers(text: str) -> list[str]:
    lowered = text.lower()
    matches: list[str] = []
    for term in UNANCHORED_QUANTIFIER_TERMS:
        if not re.search(rf"(?<!\w){re.escape(term)}(?!\w)", lowered, re.I):
            continue
        if _has_nearby_numeric_anchor(text, term):
            continue
        matches.append(term)
    return matches[:5]


def _has_nearby_numeric_anchor(text: str, term: str) -> bool:
    lowered = text.lower()
    index = lowered.find(term.lower())
    if index < 0:
        return False
    start = max(0, index - 60)
    end = min(len(text), index + len(term) + 60)
    return bool(_NUMERIC_ANCHOR_RE.search(text[start:end]))


def _matched_ambiguous_terms(text: str) -> list[str]:
    lowered = text.lower()
    matches = []
    for term in AMBIGUOUS_TERMS:
        if re.search(rf"(?<!\w){re.escape(term)}(?!\w)", lowered, re.I):
            matches.append(term)
    return matches[:5]


def _passive_match(text: str) -> str:
    for pattern in _PASSIVE_PATTERNS:
        match = pattern.search(text)
        if match:
            return match.group(0)
    return ""


def _excerpt(text: str, limit: int = 160) -> str:
    return text if len(text) <= limit else text[: limit - 3].rstrip() + "..."


def _excerpt_around(text: str, needle: str, radius: int = 80) -> str:
    index = text.lower().find(needle.lower())
    if index < 0:
        return _excerpt(text)
    start = max(0, index - radius)
    end = min(len(text), index + len(needle) + radius)
    prefix = "..." if start else ""
    suffix = "..." if end < len(text) else ""
    return prefix + text[start:end].strip() + suffix
