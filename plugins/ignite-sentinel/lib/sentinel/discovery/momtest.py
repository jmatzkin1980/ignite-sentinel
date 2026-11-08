"""IMP-180 (H7 F1): Mom-Test heuristic for elicited questions.

Declarative and bilingual (regex/tokens, **never** an LLM). Flags elicited
questions in ``gaps.md`` phrased as a hypothetical or future opinion
("would you like...?", "¿le gustaría...?") instead of asking about a concrete
past event — the Mom-Test principle: ask about the past and specifics, not
imagined futures. Generalizes the IMP-158 anti-hypothetical anchor
(``GAP-HYPOTHETICAL-ANCHOR`` in ``lenses/product.json``, which is *source*
-scoped) to any elicited question.

Severity is always ``warning``: it signals, it never blocks. Callers surface the
findings in ``/gaps`` (regeneration result) and in the ``/validate``
semantic-quality warnings.

False-positive guard (adversarial seed doc 39 §4.1): a question legitimately
about future *system* capability (load, scale, growth) is not a personal-opinion
hypothetical, so an allowlist of system-capacity terms exonerates it. Likewise a
question that already anchors a concrete past event/observation honors the
Mom-Test and stays silent.
"""
from __future__ import annotations

import re
from collections.abc import Iterable

# Hypothetical / future-opinion phrasing the Mom-Test warns against. Bilingual;
# matched on a normalized, casefolded copy of the question. Accented and
# unaccented Spanish variants are both listed so detection survives input that
# drops diacritics.
MOMTEST_TRIGGERS: tuple[str, ...] = (
    # English
    "would you",
    "would it",
    "would they",
    "would that",
    "would you like",
    "would you want",
    "would you be willing",
    "will you use",
    "do you think you would",
    "do you plan to",
    "are you planning to",
    "in the future",
    "some day",
    "someday",
    "what if",
    # Spanish
    "le gustaria",
    "le gustaría",
    "les gustaria",
    "les gustaría",
    "te gustaria",
    "te gustaría",
    "estaria dispuesto",
    "estaría dispuesto",
    "estarian dispuestos",
    "estarían dispuestos",
    "estaria dispuesta",
    "estaría dispuesta",
    "usaria",
    "usaría",
    "usarian",
    "usarían",
    "haria",
    "haría",
    "harian",
    "harían",
    "seria bueno si",
    "sería bueno si",
    "seria ideal si",
    "sería ideal si",
    "en el futuro",
    "algun dia",
    "algún día",
    "que pasaria si",
    "qué pasaría si",
    "cree que usaria",
    "cree que usaría",
)

# Concrete past-event / observation anchors that exonerate a question: if it
# already asks about a real past event, it honors the Mom-Test.
MOMTEST_EVENT_ANCHORS: tuple[str, ...] = (
    # English
    "last time",
    "last week",
    "last month",
    "recently",
    "when did you",
    "how do you currently",
    "how did you",
    "what happened",
    "what did you do",
    "walk me through",
    "tell me about the last",
    "in the demo",
    "in support",
    # Spanish
    "la ultima vez",
    "la última vez",
    "la semana pasada",
    "el mes pasado",
    "recientemente",
    "cuando fue la ultima",
    "cuándo fue la última",
    "como hacen hoy",
    "cómo hacen hoy",
    "como resolvieron",
    "cómo resolvieron",
    "que paso",
    "qué pasó",
    "que hicieron",
    "qué hicieron",
    "en la demo",
    "en soporte",
    "actualmente",
    "hoy en dia",
    "hoy en día",
)

# Allowlist (adversarial seed doc 39 §4.1): questions legitimately about future
# *system* capability (load, scale, growth) are not personal-opinion
# hypotheticals, so they are exonerated even if they read as future-tense.
MOMTEST_ALLOWLIST: tuple[str, ...] = (
    "el sistema",
    "the system",
    "la plataforma",
    "the platform",
    "capacidad",
    "capacity",
    "escala",
    "scale",
    "escalar",
    "scaling",
    "volumen",
    "volume",
    "carga pico",
    "peak load",
    "crecimiento",
    "growth",
    "concurren",
    "concurrent",
    "throughput",
    "sla",
)


def _normalize(text: object) -> str:
    return re.sub(r"\s+", " ", str(text)).strip().lower()


def hypothetical_trigger(question: object) -> str | None:
    """Return the first Mom-Test trigger phrase in *question*, else ``None``.

    Silent when the question already anchors a concrete past event/observation
    or is allowlisted as a future *system*-capability question.
    """
    normalized = _normalize(question)
    if not normalized:
        return None
    if any(anchor in normalized for anchor in MOMTEST_EVENT_ANCHORS):
        return None
    if any(term in normalized for term in MOMTEST_ALLOWLIST):
        return None
    for trigger in MOMTEST_TRIGGERS:
        if trigger in normalized:
            return trigger
    return None


def scan_questions(pairs: Iterable[tuple[object, object]]) -> list[dict[str, str]]:
    """Mom-Test findings over ``(gap_id, question)`` pairs.

    Each finding cites the offending question verbatim and the matched trigger.
    Warning severity by construction — callers surface, never block.
    """
    findings: list[dict[str, str]] = []
    for gap_id, question in pairs:
        trigger = hypothetical_trigger(question)
        if trigger:
            findings.append(
                {
                    "gap_id": str(gap_id).strip(),
                    "question": str(question).strip(),
                    "trigger": trigger,
                    "severity": "warning",
                }
            )
    return findings


def momtest_warning_line(finding: dict[str, str]) -> str:
    """Human-readable Mom-Test warning with the offending question cited."""
    return (
        f"{finding['gap_id']} Mom-Test warning: the elicited question is phrased as a "
        f"hypothetical/future opinion ('{finding['trigger']}') instead of asking about a "
        f"concrete past event or observation. Prefer asking what actually happened. "
        f"Question: \"{finding['question']}\""
    )
