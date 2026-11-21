"""Elicitation text built from open gaps: interview script, FAQ and gap rounds."""
from __future__ import annotations

import re

from ..core.io import read_json, write_text
from ..errors import GateRefusal
from ..gaps import candidate_options_for_gap, gap_kind, gap_meanwhile_map, human_title_for_gap, is_blocking, lens_for_gap, parse_gap_answers, parse_gap_rows, question_for_gap
from ..workspace import load_config, read_state, workspace_path


# --- IMP-183: read-only "interview script" export from open gaps -------------

_INTERVIEW_SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}


# IMP-349: the interview goes to the client, so it names no lens, severity or other
# internal label. Each question keeps its `### GAP-...` heading: /resolve-gaps reads the
# answers back by that id. Questions are grouped under plain topic names instead.
_INTERVIEW_TOPICS = {
    "en": {"business": "Business goals and rules", "product": "Product scope", "design": "Design and user experience",
           "technical": "Systems and data", "quality": "Quality and testing",
           "compliance": "Security, privacy and compliance", "delivery": "Delivery and rollout"},
    "es": {"business": "Objetivos y reglas de negocio", "product": "Alcance del producto", "design": "Diseño y experiencia de usuario",
           "technical": "Sistemas y datos", "quality": "Calidad y pruebas",
           "compliance": "Seguridad, privacidad y cumplimiento", "delivery": "Entrega y puesta en marcha"},
}
_INTERVIEW_OTHER_TOPIC = {"en": "Other questions", "es": "Otras preguntas"}
_INTERVIEW_ANSWER_FIELDS = {
    "en": ("- Answer:", "- Owner / source:", "- Evidence or reference:", "- Decision status:"),
    "es": ("- Respuesta:", "- Owner / fuente:", "- Evidencia o referencia:", "- Estado de decisión:"),
}
_GENERIC_QUESTIONS = ("What confirmed information resolves this uncertainty?", "¿Qué información confirmada resuelve esta incertidumbre?")
# IMP-349: a follow-up built from the text the lens check matched, per gap. A gap that is
# not listed gets no follow-up: its matched text cannot be turned into an honest question.
_INTERVIEW_FOLLOW_UPS = {
    "en": {
        "GAP-METRIC-SOURCE": 'You mention "{m}": where does that figure come from, what is the value today, and how will it be measured?',
        "GAP-METRIC-DEFINITION": 'You mention "{m}": which measures do you mean exactly, and how is each one calculated?',
        "GAP-CTP-EXCLUSION": 'You mention "{m}": what exactly is left out, and who decided it?',
        "GAP-DESIGN-FLOW": 'You mention "{m}": how do people get there, and what do they do there step by step?',
        "GAP-DESIGN-STATES": 'For "{m}": what should people see while it loads, when there is nothing to show, and when something fails?',
        "GAP-DESIGN-PROTOTYPE-INPUT": 'What about "{m}" should a prototype help you decide or test with users?',
        "GAP-FRONTEND-SURFACE": 'For "{m}": who uses it, and what can each kind of user see or do there?',
        "GAP-BACKEND-SURFACE": 'For "{m}": where does its data come from, and what should happen if that source is not available?',
        "GAP-TECH-DEEP-DIVE-INPUT": 'Which systems or components are behind "{m}"?',
        "GAP-AUTH-MODEL": 'You mention "{m}": how will people sign in, and which roles or permissions exist?',
        "GAP-BUSINESS-RULE-WEAK-WORD-SMELL": 'You wrote: "{m}". What does that mean in practice: which condition, value or limit applies?',
        "GAP-QUALITY-WEAK-WORD-SMELL": 'You wrote: "{m}". How would you check it: which value or result counts as good enough?',
        "GAP-HYPOTHETICAL-ANCHOR": 'You wrote: "{m}". Has this already happened? If so, when, and what happened?',
    },
    "es": {
        "GAP-METRIC-SOURCE": 'El texto menciona "{m}": ¿de dónde sale ese valor, cuál es el valor hoy y cómo se va a medir?',
        "GAP-METRIC-DEFINITION": 'El texto menciona "{m}": ¿qué medidas son exactamente y cómo se calcula cada una?',
        "GAP-CTP-EXCLUSION": 'El texto menciona "{m}": ¿qué queda afuera exactamente y quién lo decidió?',
        "GAP-DESIGN-FLOW": 'El texto menciona "{m}": ¿cómo llegan las personas ahí y qué hacen paso a paso?',
        "GAP-DESIGN-STATES": 'Para "{m}": ¿qué deberían ver las personas mientras carga, cuando no hay nada para mostrar y cuando algo falla?',
        "GAP-DESIGN-PROTOTYPE-INPUT": '¿Qué aspecto de "{m}" debería ayudar a decidir o probar con usuarios un prototipo?',
        "GAP-FRONTEND-SURFACE": 'Para "{m}": ¿quién lo usa y qué puede ver o hacer cada tipo de usuario?',
        "GAP-BACKEND-SURFACE": 'Para "{m}": ¿de dónde salen sus datos y qué debe pasar si esa fuente no está disponible?',
        "GAP-TECH-DEEP-DIVE-INPUT": '¿Qué sistemas o componentes están detrás de "{m}"?',
        "GAP-AUTH-MODEL": 'El texto menciona "{m}": ¿cómo van a ingresar las personas y qué roles o permisos existen?',
        "GAP-BUSINESS-RULE-WEAK-WORD-SMELL": 'El texto dice: "{m}". ¿Qué significa en la práctica: qué condición, valor o límite aplica?',
        "GAP-QUALITY-WEAK-WORD-SMELL": 'El texto dice: "{m}". ¿Cómo se verificaría: qué valor o resultado alcanza?',
        "GAP-HYPOTHETICAL-ANCHOR": 'El texto dice: "{m}". ¿Esto ya pasó? Si es así, ¿cuándo y qué pasó?',
    },
}
# A matched text that is a path, a gap id, a source id or a section mark is not something
# the client wrote, so it never goes into a client question.
_INTERNAL_MENTION = re.compile(r"GAP-|[A-Z]{2,}-\d|/|\\|§|\bharvest\b")


def interview_probing_for_gap(gap: dict[str, str], language: str = "en") -> list[dict[str, str]]:
    """At most one follow-up question built from the text the lens check matched.

    IMP-349: it used to repeat the BA's candidate options ("Confirm `x` is in scope ...").
    Now it is a plain question to the client that quotes the matched text, or nothing
    when that text cannot be phrased honestly. A gap without local evidence gets nothing.
    """
    if str(gap.get("status", "OPEN")).strip("`").upper() == "CLOSED":
        return []
    mention = str(gap.get("evidence_mention", "")).strip()
    if not mention or mention.upper() == "N/A" or _INTERNAL_MENTION.search(mention):
        return []
    template = _INTERVIEW_FOLLOW_UPS["es" if language == "es" else "en"].get(str(gap.get("id", "")).strip("`"))
    if not template:
        return []
    return [{"text": template.format(m=mention.rstrip(".")), "citation": mention}]


def _interview_question(gap: dict[str, str], language: str) -> str:
    question = str(gap.get("question") or "").strip()
    if not question or question in _GENERIC_QUESTIONS:
        question = question_for_gap(gap["id"], language)
    return question


def _interview_gap_entry(number: int, gap: dict[str, str], language: str = "en") -> str:
    lang = "es" if language == "es" else "en"
    lines = [f"### {gap['id']}", "", f"**{number}.** {_interview_question(gap, language)}", ""]
    for probe in interview_probing_for_gap(gap, language):
        lines += [probe["text"], ""]
    lines += list(_INTERVIEW_ANSWER_FIELDS[lang])
    return "\n".join(lines)


def _by_severity(gaps: list[dict[str, str]]) -> list[dict[str, str]]:
    return sorted(gaps, key=lambda g: (_INTERVIEW_SEVERITY_ORDER.get(str(g.get("severity", "")).strip("`").lower(), 4), g["id"]))


def _interview_grouped_sections(
    gaps: list[dict[str, str]], counter_start: int, language: str
) -> tuple[list[str], int]:
    """Render gaps grouped by topic (stable order), continuously numbered."""
    lang = "es" if language == "es" else "en"
    topics = _INTERVIEW_TOPICS[lang]
    by_lens: dict[str, list[dict[str, str]]] = {}
    for gap in gaps:
        lens = gap.get("lens") or lens_for_gap(gap["id"])
        by_lens.setdefault(lens if lens in topics else "", []).append(gap)
    sections: list[str] = []
    number = counter_start
    for lens in sorted(by_lens, key=lambda key: (key == "", key)):
        entries = []
        for gap in _by_severity(by_lens[lens]):
            entries.append(_interview_gap_entry(number, gap, language))
            number += 1
        sections.append(f"**{topics.get(lens, _INTERVIEW_OTHER_TOPIC[lang])}**\n\n" + "\n\n".join(entries))
    return sections, number


def _owner_heading(owner: dict[str, str] | None, language: str) -> str:
    es = language == "es"
    if owner is None:
        return "Preguntas sin contacto asignado todavía" if es else "Questions with no contact named yet"
    name = owner.get("name", "").strip() or owner.get("id", "")
    return f"Preguntas para {name}" if es else f"Questions for {name}"


def _interview_owner_sections(
    gaps: list[dict[str, str]],
    stakeholders: list[dict[str, str]],
    counter_start: int,
    language: str,
) -> tuple[list[str], int]:
    """IMP-192: group gaps by their assigned stakeholder owner (routed by lens).

    Named owners come first (stable by id); gaps with no owner land in an explicit
    unassigned bucket last — never an invented owner. Numbering stays continuous.
    """
    from ..stakeholders import owner_for_lens

    buckets: dict[str | None, tuple[dict[str, str] | None, list[dict[str, str]]]] = {}
    for gap in gaps:
        lens = gap.get("lens") or lens_for_gap(gap["id"])
        owner = owner_for_lens(lens, stakeholders)
        key = owner["id"] if owner else None
        if key not in buckets:
            buckets[key] = (owner, [])
        buckets[key][1].append(gap)
    ordered_keys = sorted([k for k in buckets if k is not None]) + ([None] if None in buckets else [])
    sections: list[str] = []
    number = counter_start
    for key in ordered_keys:
        owner, owner_gaps = buckets[key]
        entries = []
        for gap in _by_severity(owner_gaps):
            entries.append(_interview_gap_entry(number, gap, language))
            number += 1
        sections.append(f"**{_owner_heading(owner, language)}**\n\n" + "\n\n".join(entries))
    return sections, number


def render_interview_script(
    project_id: str,
    gaps: list[dict[str, str]],
    language: str = "en",
    stakeholders: list[dict[str, str]] | None = None,
) -> str:
    from ..brief_schema import SETTINGS_GAP_ID

    # IMP-344: the brief settings gap is the BA's own decision (a CLI command), not a client question
    open_gaps = [gap for gap in gaps if str(gap.get("status", "OPEN")).strip("`").upper() != "CLOSED"
                 and str(gap.get("id", "")).strip("`") != SETTINGS_GAP_ID]
    blocking = [gap for gap in open_gaps if is_blocking(gap)]
    followup = [gap for gap in open_gaps if not is_blocking(gap)]
    route_by_owner = bool(stakeholders)

    def group(section_gaps: list[dict[str, str]], counter: int) -> tuple[list[str], int]:
        if route_by_owner:
            return _interview_owner_sections(section_gaps, stakeholders or [], counter, language)
        return _interview_grouped_sections(section_gaps, counter, language)
    # IMP-349: written for the client. No word here may match the "unvalidated source"
    # pattern of source_routing.json (it reads the first lines of an answer file), or an
    # answered copy fed to /resolve-gaps could not close anything.
    if language == "es":
        header = (
            f"# Guion de entrevista - {project_id}\n\n"
            "Estas son las preguntas que necesitamos responder para completar el requerimiento, "
            "las más urgentes primero. Escribir cada respuesta debajo de su pregunta: en "
            "\"Respuesta\" la respuesta, en \"Owner / fuente\" quién la da, en \"Evidencia o "
            "referencia\" el documento, reunión o mensaje que la respalda, y en \"Estado de "
            "decisión\" confirmado, pendiente o no aplica.\n\n"
            "Cada pregunta empieza con un código de referencia (por ejemplo `GAP-SCOPE`); "
            "mantenerlo junto a la respuesta, porque con él asociamos cada respuesta a su pregunta.\n"
        )
        blocking_heading = "## Preguntas bloqueantes"
        followup_heading = "## Preguntas de seguimiento"
        empty = "_No hay preguntas abiertas para la entrevista._"
    else:
        header = (
            f"# Interview Script - {project_id}\n\n"
            "These are the questions we need answered to complete the requirement, the most "
            "urgent first. Please write each answer under its question: under \"Answer\" the "
            "answer, under \"Owner / source\" who gives it, under \"Evidence or reference\" the "
            "document, meeting or message that supports it, and under \"Decision status\" "
            "confirmed, pending or not applicable.\n\n"
            "Each question starts with a reference code (for example `GAP-SCOPE`); please keep "
            "it with your answer, because we use it to match each answer to its question.\n"
        )
        blocking_heading = "## Blocking questions"
        followup_heading = "## Follow-up questions"
        empty = "_No open questions: there are no interview questions._"
    if not open_gaps:
        return header + "\n" + empty + "\n"
    parts = [header]
    number = 1
    if blocking:
        sections, number = group(blocking, number)
        parts.append(blocking_heading + "\n\n" + "\n\n".join(sections))
    if followup:
        sections, number = group(followup, number)
        parts.append(followup_heading + "\n\n" + "\n\n".join(sections))
    return "\n\n".join(parts) + "\n"


def build_interview_script(project_id: str, change_id: str | None = None) -> str:
    """Read open gaps from the canonical gaps.md (the change's, with change_id) and render the interview script."""
    base = workspace_path(project_id)
    if change_id:  # IMP-386: only the change's questions
        from ..changes import change_gaps_path

        gaps_path = change_gaps_path(base, change_id)
    else:
        gaps_path = base / "01_discovery" / "gaps.md"
    if not gaps_path.exists():
        raise GateRefusal("Cannot export an interview script before /ingest creates 01_discovery/gaps.md.")
    gaps = parse_gap_rows(gaps_path.read_text(encoding="utf-8"))
    state = read_json(base / "state.json", {})
    configured = state.get("project_language", load_config(project_id).get("project_language", "auto"))
    language = configured if configured in {"es", "en"} else "en"
    from ..stakeholders import load_stakeholders

    return render_interview_script(project_id, gaps, language, load_stakeholders(project_id))


def build_faq(project_id: str) -> str:
    """Render a traceable FAQ (resolved questions) from the governed gap ledger.

    Question = an elicited gap; answer = its CONFIRMED closure, quoted verbatim
    from the seed/decision tables with a citation to the gap and its source.
    ``parse_gap_answers`` only returns CONFIRMED rows, so open gaps are
    structurally excluded and never shown as answered (never invented)."""
    base = workspace_path(project_id)
    seeds_path = base / "01_discovery" / "identity_seeds.md"
    decisions_path = base / "01_discovery" / "decisions.md"
    if not seeds_path.exists() and not decisions_path.exists():
        raise GateRefusal(
            "Cannot export a FAQ before gaps are resolved into "
            "01_discovery/decisions.md or identity_seeds.md."
        )
    seed_text = seeds_path.read_text(encoding="utf-8") if seeds_path.exists() else ""
    decision_text = decisions_path.read_text(encoding="utf-8") if decisions_path.exists() else ""
    answers = parse_gap_answers(seed_text + "\n" + decision_text)
    state = read_json(base / "state.json", {})
    configured = state.get("project_language", load_config(project_id).get("project_language", "auto"))
    language = configured if configured in {"es", "en"} else "en"
    return render_faq(project_id, answers, language)


def render_faq(project_id: str, answers: dict[str, dict[str, str]], language: str = "en") -> str:
    """Render resolved gaps as a cited FAQ, or an explicit empty marker."""
    if language == "es":
        header = (
            f"# Preguntas resueltas (FAQ) - {project_id}\n\n"
            "Vista derivada READ-ONLY de los gaps ya cerrados: cada pregunta es un gap "
            "elicitado y cada respuesta es su cierre CONFIRMADO, citado textualmente desde "
            "las tablas de seeds/decisiones (`01_discovery/`). Solo aparecen gaps confirmados; "
            "los gaps abiertos nunca figuran como respondidos. Esta FAQ NO reemplaza a "
            "`01_discovery/gaps.md` (la fuente de verdad) y no cierra ningun gap.\n"
        )
        answer_label = "R"
        source_label = "Fuente"
        empty = "_No hay gaps confirmados todavia: la FAQ esta vacia (no se inventan respuestas)._"
        prefix = "P"
    else:
        header = (
            f"# Resolved Questions (FAQ) - {project_id}\n\n"
            "READ-ONLY derived view of the already-closed gaps: each question is an elicited "
            "gap and each answer is its CONFIRMED closure, quoted verbatim from the "
            "seed/decision tables (`01_discovery/`). Only confirmed gaps appear; open gaps "
            "never show up as answered. This FAQ does NOT replace `01_discovery/gaps.md` "
            "(the source of truth) and closes no gap.\n"
        )
        answer_label = "A"
        source_label = "Source"
        empty = "_No confirmed gaps yet: the FAQ is empty (answers are never invented)._"
        prefix = "Q"
    if not answers:
        return header + "\n" + empty + "\n"
    parts = [header]
    number = 1
    for gap_id, answer in answers.items():
        title = human_title_for_gap(gap_id, language)
        statement = str(answer.get("statement", "")).strip()
        source = str(answer.get("source", "")).strip()
        cite = f"`{gap_id}`" + (f" / `{source}`" if source else "")
        parts.append(
            f"### {prefix}{number}. {title}\n\n"
            f"- **{answer_label}:** {statement}\n"
            f"- **{source_label}:** {cite}\n"
        )
        number += 1
    return "\n".join(parts).rstrip() + "\n"


# --- IMP-257: rounds of questions -------------------------------------------------------

# Order inside a round: scope > security and privacy > UX > technical, then the rest.
ROUND_LENS_ORDER = {"product": 0, "business": 0, "compliance": 1, "design": 2, "technical": 3}


ROUND_SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}


def gap_round(project_id: str, top: int = 5) -> dict[str, object]:
    """The next batch of at most `top` questions, one decision each, recommended option first."""
    base = workspace_path(project_id)
    gaps_path = base / "01_discovery" / "gaps.md"
    if not gaps_path.exists():
        raise GateRefusal("Cannot plan a round before /ingest creates 01_discovery/gaps.md.")
    state = read_state(project_id, {})
    language = state.get("project_language") if state.get("project_language") in {"es", "en"} else "en"
    gaps = [gap for gap in parse_gap_rows(gaps_path.read_text(encoding="utf-8"))
            if gap.get("id") != "NONE" and str(gap.get("status", "OPEN")).upper() != "CLOSED"]
    gaps.sort(key=lambda gap: (ROUND_LENS_ORDER.get(str(gap.get("lens", "")).strip("`"), 4),
                               ROUND_SEVERITY_ORDER.get(str(gap.get("severity", "")).strip("`").lower(), 4), gap["id"]))
    meanwhile = gap_meanwhile_map(project_id)
    leave = "Dejar pendiente" if language == "es" else "Leave pending"
    items = []
    for gap in gaps[:max(1, int(top))]:
        options = candidate_options_for_gap(gap, language)
        choices = [{"label": o["label"], "text": o["text"], "recommended": index == 0, "inferred": index == 0}
                   for index, o in enumerate(options)]
        choices.append({"label": "-", "text": leave, "recommended": False, "inferred": False})
        items.append({
            "id": gap["id"],
            "kind": gap_kind(gap),
            "lens": gap.get("lens", ""),
            "severity": gap.get("severity", ""),
            "question": gap.get("question") or question_for_gap(gap["id"], language),
            "choices": choices,
            "meanwhile": meanwhile.get(gap["id"]),
        })
    path = base / "01_discovery" / "gap_round.md"
    write_text(path, render_gap_round(project_id, items, len(gaps), language))
    return {"project_id": project_id, "round": items, "open_total": len(gaps), "remaining": max(0, len(gaps) - len(items)),
            "path": str(path.as_posix())}


def render_gap_round(project_id: str, items: list[dict[str, object]], total: int, language: str) -> str:
    es = language == "es"
    lines = [f"# {'Ronda de preguntas' if es else 'Question round'} - {project_id}", "",
             (f"{len(items)} de {total} gaps abiertos. Una decisión por pregunta; la recomendada es una inferencia y no se aplica sola."
              if es else f"{len(items)} of {total} open gaps. One decision per question; the recommended option is an inference and never applies by itself."), ""]
    for number, item in enumerate(items, start=1):
        lines += [f"## {number}. {item['id']} ({item['kind']}, {item['severity']})", "", str(item["question"]), ""]
        for choice in item["choices"]:  # type: ignore[union-attr]
            mark = (" (recomendada, inferida)" if es else " (recommended, inferred)") if choice["recommended"] else ""
            prefix = f"{choice['label']}. " if choice["label"] != "-" else ""
            lines.append(f"- {prefix}{choice['text']}{mark}")
        meanwhile = item.get("meanwhile")
        if isinstance(meanwhile, dict):
            lines += ["", f"{'Mientras tanto (inferido)' if es else 'Meanwhile (inferred)'}: {meanwhile['statement']} (`{meanwhile['assumption']}`)"]
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
