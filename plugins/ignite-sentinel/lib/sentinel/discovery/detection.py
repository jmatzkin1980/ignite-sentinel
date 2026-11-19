"""Deterministic gap detection over the requirement text and its units."""
from __future__ import annotations

import re

from ..gaps import question_for_gap
from ..lens_registry import check_applies, load_lens_checks, load_smell_catalog

from .momtest import scan_questions


METRIC_RE = re.compile(
    r"(\d+(?:[.,]\d+)?\s?(?:%|percent|por ciento|porcentaje)|\$\s?\d+|\d+\s?(?:usd|ars|eur|hours|horas|days|dias))",
    re.I,
)


def requirement_sentences(text: str) -> list[str]:
    cleaned = re.sub(r"\s+", " ", text.replace("\n", " ")).strip()
    if not cleaned:
        return []
    parts = re.split(r"(?<=[.!?])\s+|;\s+|\s+-\s+", cleaned)
    return [part.strip(" .\t") for part in parts if part.strip(" .\t")]


PERSONA_HINTS = (
    "user", "usuario", "usuarios", "actor", "actores", "persona", "lead", "leads",
    "analyst", "analista", "manager", "operator", "operador", "cliente", "customer",
    "equipo", "team", "back office", "stakeholder", "supervisor",
)


REQUIREMENT_HINTS = (
    "must", "shall", "should", "need", "want", "require", "expect",
    "queremos", "necesit", "debe", "deber", "se requiere", "permitir", "esperamos",
)


MISSING_CONTEXT_HINTS = (
    "no ",
    "not ",
    "without ",
    "missing ",
    "unclear ",
    "undefined ",
    "not defined",
    "did not define",
    "does not define",
    "do not define",
    "lacks ",
    "lack ",
    "unknown ",
    "sin ",
    "no se defin",
    "no defin",
    "falta ",
    "pendiente ",
)


CLAUSE_BOUNDARY_HINTS = (
    ".",
    ";",
    "\n",
    " but ",
    " however ",
    " yet ",
    " pero ",
    " aunque ",
    " sin embargo ",
)


def split_evidence_sentences(text: str) -> list[str]:
    """Split raw evidence into clean sentences, dropping markdown noise."""
    import re as _re

    cleaned_lines = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        line = line.lstrip("-*>0123456789. \t")
        if line:
            cleaned_lines.append(line)
    blob = " ".join(cleaned_lines)
    parts = _re.split(r"(?<=[.!?])\s+", blob)
    return [part.strip() for part in parts if len(part.strip()) >= 15]


def extract_personas(text: str, limit: int = 5) -> list[dict[str, str]]:
    """Extract persona/actor evidence sentences from raw client input."""
    results: list[dict[str, str]] = []
    seen: set[str] = set()
    for sentence in split_evidence_sentences(text):
        lowered = sentence.lower()
        if any(hint in lowered for hint in PERSONA_HINTS):
            key = lowered[:80]
            if key in seen:
                continue
            seen.add(key)
            results.append({"evidence": sentence})
            if len(results) >= limit:
                break
    return results


def extract_functional_signals(text: str, limit: int = 7) -> list[dict[str, str]]:
    """Extract requirement-like statements (modal/need language) from raw input."""
    results: list[dict[str, str]] = []
    seen: set[str] = set()
    for sentence in split_evidence_sentences(text):
        lowered = sentence.lower()
        if any(hint in lowered for hint in REQUIREMENT_HINTS):
            key = lowered[:80]
            if key in seen:
                continue
            seen.add(key)
            results.append({"statement": sentence})
            if len(results) >= limit:
                break
    return results


def extract_metric_signals(text: str, limit: int = 5) -> list[dict[str, str]]:
    """Extract quantitative metric mentions with their evidence sentence."""
    results: list[dict[str, str]] = []
    seen: set[str] = set()
    for sentence in split_evidence_sentences(text):
        match = METRIC_RE.search(sentence)
        if not match:
            continue
        key = sentence.lower()[:80]
        if key in seen:
            continue
        seen.add(key)
        results.append({"metric": match.group(0), "evidence": sentence})
        if len(results) >= limit:
            break
    return results


def has_positive_token_evidence(evidence: str, tokens: tuple[str, ...] | list[str]) -> bool:
    """Return true when a token appears outside a missing/negated context."""
    sentences = split_evidence_sentences(evidence)
    if not sentences:
        sentences = [evidence]
    for sentence in sentences:
        lowered = sentence.lower()
        for token in tokens:
            token_text = str(token).lower()
            index = lowered.find(token_text)
            while index >= 0:
                clause_start = 0
                clause_end = len(lowered)
                for boundary in CLAUSE_BOUNDARY_HINTS:
                    previous = lowered.rfind(boundary, 0, index)
                    if previous >= 0:
                        clause_start = max(clause_start, previous + len(boundary))
                    following = lowered.find(boundary, index + len(token_text))
                    if following >= 0:
                        clause_end = min(clause_end, following)
                window_start = max(clause_start, index - 48)
                window_end = min(clause_end, index + len(token_text) + 48)
                window = lowered[window_start:window_end]
                if not any(hint in window for hint in MISSING_CONTEXT_HINTS):
                    return True
                index = lowered.find(token_text, index + len(token_text))
    return False


def weak_word_terms(check: dict) -> list[dict[str, str]]:
    catalog_id = check.get("catalog", "weak_words")
    catalogs = load_smell_catalog()
    catalog = catalogs.get(catalog_id, {})
    categories = check.get("categories", ())
    selected = categories or catalog.get("categories", {}).keys()
    terms: list[dict[str, str]] = []
    for category in selected:
        for term in catalog.get("categories", {}).get(category, ()):
            if isinstance(term, str):
                terms.append({"term": term, "mechanism": category})
            elif isinstance(term, dict) and term.get("term"):
                terms.append(
                    {
                        "term": str(term["term"]),
                        "mechanism": str(term.get("mechanism", category)),
                    }
                )
    terms.extend({"term": str(token), "mechanism": "custom"} for token in check.get("tokens", ()))
    return terms


def first_weak_word_smell(text: str, evidence: str, check: dict) -> tuple[str, str] | None:
    for item in weak_word_terms(check):
        term = item["term"].strip().lower()
        if not term or term not in evidence:
            continue
        sentence = next(
            (candidate for candidate in split_evidence_sentences(text) if term in candidate.lower()),
            term,
        )
        return sentence, item["mechanism"]
    return None


COUNTERPART_WINDOW = 1  # IMP-256: sentences on each side of a mention


def counterpart_present(evidence: str, source: str, check: dict) -> bool:
    """IMP-256: is the counterpart of a mentioned surface actually given?

    Before, one counterpart word anywhere in the document suppressed the gap. Now,
    when the source names the surface, the counterpart has to sit near that mention
    (the same sentence or `COUNTERPART_WINDOW` sentences around it) or in a domain
    context folder. With no mention in the source, the old document-wide test stays.
    A check can opt out with `"counterpart_scope": "document"`.
    """
    counterparts = [str(t) for t in check.get("counterparts", ())]
    triggers = [str(t) for t in check.get("triggers", ())]
    if check.get("counterpart_scope") == "document":
        return any(token in evidence for token in counterparts)
    sentences = [s.lower() for s in split_evidence_sentences(source)] or [source]
    mentions = [i for i, sentence in enumerate(sentences) if any(t in sentence for t in triggers)]
    if not mentions:
        return any(token in evidence for token in counterparts)
    context_only = evidence.replace(source, "", 1)
    if any(token in context_only for token in counterparts):
        return True
    for index in mentions:
        window = " ".join(sentences[max(0, index - COUNTERPART_WINDOW):index + COUNTERPART_WINDOW + 1])
        if any(token in window for token in counterparts):
            return True
    return False


def detect_gaps(
    text: str,
    context: dict[str, str] | None = None,
    lenses_dir=None,
    *,
    work: str = "project",
    border_types: frozenset[str] | None = None,
) -> list[dict[str, str]]:
    """Detect gaps by applying the declarative lens checklist (IMP-033).

    The lens knowledge (checks, severities, tokens, inquisitive rules) lives in
    ``sentinel/lenses/*.json`` via :mod:`sentinel.lens_registry`, not hardcoded
    here. Each check declares a ``rule`` that decides how it fires; behavior is
    identical to the previous in-code checklist. ``lenses_dir`` overrides the
    source directory (used by tests to add a check without touching Python).
    ``work`` and ``border_types`` (IMP-382) scope the checklist to a change: checks
    that do not apply to the work kind or whose surfaces miss the border are
    skipped. The defaults keep the project result byte-identical.
    """
    lowered = text.lower()
    context = context or {}
    tech_evidence = " ".join([text, context.get("technical", "")]).lower()
    design_evidence = " ".join([text, context.get("design", "")]).lower()
    quality_evidence = " ".join([text, context.get("quality", "")]).lower()
    frontend_evidence = " ".join([text, context.get("design", ""), context.get("technical", "")]).lower()
    scopes = {
        "source": lowered,
        "technical": tech_evidence,
        "design": design_evidence,
        "quality": quality_evidence,
        "frontend": frontend_evidence,
        "all": " ".join([lowered, tech_evidence, design_evidence, quality_evidence]),
    }
    gaps: list[dict[str, str]] = []
    for check in load_lens_checks(lenses_dir):
        if not check_applies(check, work, border_types):
            continue
        rule = check.get("rule")
        evidence = scopes.get(check.get("evidence_scope", "source"), lowered)
        gap = {
            "id": check["id"],
            "lens": check["lens"],
            "severity": check["severity"],
            "description": check["description"],
        }
        if rule == "absent_tokens":
            if not has_positive_token_evidence(evidence, check.get("tokens", ())):
                gaps.append(gap)
        elif rule == "mention_without_counterpart":
            # Inquisitive tier (IMP-015): a surface is mentioned but its
            # counterpart detail is absent; a bare mention anchors the question
            # to the input instead of suppressing it.
            if counterpart_present(evidence, lowered, check):
                continue
            mention = next((token.strip() for token in check.get("triggers", ()) if token in evidence), None)
            if mention:
                gap["evidence_mention"] = mention
            gaps.append(gap)
        elif rule == "mention_requires_counterpart":
            # IMP-117: end false maturity for surface concepts. Unlike
            # ``mention_without_counterpart`` (which fires unless a counterpart is
            # present, trigger optional), this rule fires ONLY when the concept is
            # actually named (trigger present) and its counterpart is absent, so a
            # bare mention of a metric/auth concept anchors the question instead of
            # passing as coverage. No trigger -> nothing to ask.
            mention = next((token.strip() for token in check.get("triggers", ()) if token in evidence), None)
            if not mention:
                continue
            if counterpart_present(evidence, lowered, check):
                continue
            gap["evidence_mention"] = mention
            gaps.append(gap)
        elif rule == "metric_without_source":
            metric_match = METRIC_RE.search(text)
            metric_sentence = ""
            if metric_match:
                metric_sentence = next(
                    (sentence for sentence in split_evidence_sentences(text) if METRIC_RE.search(sentence)),
                    metric_match.group(0),
                ).lower()
            if metric_match and not any(token in metric_sentence for token in check.get("suppressors", ())):
                gap["evidence_mention"] = metric_match.group(0)
                gaps.append(gap)
        if rule == "weak_word_smell":
            smell = first_weak_word_smell(text, evidence, check)
            if not smell:
                continue
            sentence, mechanism = smell
            gap["evidence_mention"] = sentence
            gap["smell_mechanism"] = mechanism
            gaps.append(gap)
        if rule == "hypothetical_without_event":
            trigger = next((token.strip() for token in check.get("triggers", ()) if token in evidence), None)
            if not trigger:
                continue
            if any(token in evidence for token in check.get("event_anchors", ())):
                continue
            sentence = next(
                (sentence for sentence in split_evidence_sentences(text) if trigger in sentence.lower()),
                trigger,
            )
            gap["evidence_mention"] = sentence
            gaps.append(gap)
    return gaps


def unit_scope_text(unit: dict[str, str], text: str) -> str:
    """Cited evidence scope for a Requirement Unit (IMP-116).

    Returns the source sentence(s) that mention the unit, so lens checks can be
    evaluated against the unit's own cited text instead of the whole document.
    Falls back to the unit label when no sentence carries the mention verbatim.
    """
    mention = str(unit.get("evidence_mention", "")).strip().lower()
    sentences = [
        sentence
        for sentence in requirement_sentences(text)
        if mention and mention in sentence.lower()
    ]
    if sentences:
        return " ".join(sentences)
    return str(unit.get("label", "")).strip()


def anchoring_unit_for_gap(gap: dict[str, str], units: list[dict[str, str]], text: str) -> str:
    """Return the RU id whose cited scope explains an inquisitive gap (IMP-116).

    Only gaps carrying a detected trigger (``evidence_mention``) are anchored;
    document-level ``absent_tokens`` gaps stay unanchored. The first unit (stable
    RU order) whose scoped text contains the trigger wins.
    """
    mention = str(gap.get("evidence_mention", "")).strip().lower()
    if not mention or mention == "n/a":
        return ""
    for unit in units:
        if mention in unit_scope_text(unit, text).lower():
            return str(unit.get("id", ""))
    return ""


def detect_unit_anchored_gaps(
    text: str,
    context: dict[str, str] | None = None,
    units: list[dict[str, str]] | None = None,
    lenses_dir=None,
) -> list[dict[str, str]]:
    """Run lens checks globally and per Requirement Unit (IMP-116).

    Document-level detection is unchanged: every gap ``detect_gaps`` would emit
    is still produced. When Requirement Units (IMP-115) exist, each unit's cited
    evidence is also scoped on its own, so a trigger token present in one unit
    can no longer suppress an inquisitive gap that belongs to another unit. Each
    emitted gap carries the RU that explains it in an additive ``unit`` field;
    document-level gaps without a unit scope stay unanchored. Without units the
    result is identical to ``detect_gaps`` (back-compat for existing workspaces).
    """
    base_gaps = detect_gaps(text, context, lenses_dir)
    if not units:
        return base_gaps
    by_id = {gap["id"]: gap for gap in base_gaps}
    for gap in base_gaps:
        gap["unit"] = anchoring_unit_for_gap(gap, units, text)
    for unit in units:
        scope = unit_scope_text(unit, text)
        for gap in detect_gaps(scope, context, lenses_dir):
            if gap["id"] in by_id:
                continue
            # Only inquisitive (trigger-bearing) gaps are surfaced per unit;
            # document-level absent_tokens gaps remain a single global signal.
            if not str(gap.get("evidence_mention", "")).strip():
                continue
            gap["unit"] = str(unit.get("id", ""))
            by_id[gap["id"]] = gap
            base_gaps.append(gap)
    return base_gaps


def gap_question_warnings(gaps: list[dict[str, str]], language: str = "en") -> list[dict[str, str]]:
    """IMP-180: Mom-Test findings over the elicited questions in a gap set.

    Uses each gap's rendered question (agent-authored when present, else the
    built-in checklist question) so the heuristic covers every elicited question,
    not only agentic ones. Never blocks — findings carry ``severity: warning``.
    """
    pairs = [
        (gap.get("id", ""), gap.get("question") or question_for_gap(gap.get("id", ""), language))
        for gap in gaps
    ]
    return scan_questions(pairs)
