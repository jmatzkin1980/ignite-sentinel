"""Elicitation text built from open gaps: interview script, FAQ and gap rounds."""
from __future__ import annotations

from ..core.io import read_json, write_text
from ..errors import GateRefusal
from ..gaps import candidate_options_for_gap, evidence_note_for_gap, gap_kind, gap_meanwhile_map, human_title_for_gap, is_blocking, lens_for_gap, parse_gap_answers, parse_gap_rows, question_for_gap
from ..workspace import load_config, read_state, workspace_path


# --- IMP-183: read-only "interview script" export from open gaps -------------

_INTERVIEW_SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}


def interview_probing_for_gap(gap: dict[str, str], language: str = "en") -> list[dict[str, str]]:
    """1-2 cited probing follow-ups DERIVED from the IMP-113 candidate options.

    Never invents questions: it reuses ``candidate_options_for_gap`` verbatim, so a gap
    without local evidence (no ``evidence_mention``) yields no probing questions (silence).
    """
    return [
        {"text": option["text"], "citation": option["citation"]}
        for option in candidate_options_for_gap(gap, language)
    ]


def _interview_gap_entry(number: int, gap: dict[str, str], language: str = "en") -> str:
    gap_id = gap["id"]
    lens = gap.get("lens") or lens_for_gap(gap_id)
    severity = str(gap.get("severity", "")).strip("`").lower()
    title = human_title_for_gap(gap_id, language)
    question = str(gap.get("question") or question_for_gap(gap_id, language)).strip()
    context = evidence_note_for_gap(gap, language)
    probing = interview_probing_for_gap(gap, language)
    if language == "es":
        lines = [f"{number}. {title} (`{gap_id}`, severidad `{severity}`, lente `{lens}`)", ""]
        if context:
            lines.append(f"- Contexto citado: {context}")
        lines.append(f"- Preguntar: {question}")
        if probing:
            lines.append("- Preguntas de profundizacion:")
            for probe in probing:
                lines.append(f"  - {probe['text']} Cita local: `{probe['citation']}`.")
        return "\n".join(lines)
    lines = [f"{number}. {title} (`{gap_id}`, severity `{severity}`, lens `{lens}`)", ""]
    if context:
        lines.append(f"- Cited context: {context}")
    lines.append(f"- Ask: {question}")
    if probing:
        lines.append("- Probing questions:")
        for probe in probing:
            lines.append(f"  - {probe['text']} Local citation: `{probe['citation']}`.")
    return "\n".join(lines)


def _interview_grouped_sections(
    gaps: list[dict[str, str]], counter_start: int, language: str
) -> tuple[list[str], int]:
    """Render gaps grouped by lens (alphabetical, stable), continuously numbered."""
    by_lens: dict[str, list[dict[str, str]]] = {}
    for gap in gaps:
        lens = gap.get("lens") or lens_for_gap(gap["id"])
        by_lens.setdefault(lens, []).append(gap)
    sections: list[str] = []
    number = counter_start
    for lens in sorted(by_lens):
        lens_gaps = sorted(
            by_lens[lens],
            key=lambda g: (_INTERVIEW_SEVERITY_ORDER.get(str(g.get("severity", "")).strip("`").lower(), 4), g["id"]),
        )
        entries = []
        for gap in lens_gaps:
            entries.append(_interview_gap_entry(number, gap, language))
            number += 1
        sections.append(f"### {lens}\n\n" + "\n\n".join(entries))
    return sections, number


def _owner_heading(owner: dict[str, str] | None, language: str) -> str:
    es = language == "es"
    if owner is None:
        return (
            "Sin dueño asignado (asignar vía `/stakeholders`)"
            if es
            else "Unassigned (no stakeholder owner — assign via `/stakeholders`)"
        )
    label = "Dueño" if es else "Owner"
    domain_label = "dominio" if es else "domain"
    heading = f"{label}: {owner.get('name', '').strip() or owner.get('id', '')} ({domain_label} `{owner.get('domain', '')}`"
    profile = owner.get("respondent_profile", "").strip()
    if profile:
        heading += f", respondent_profile `{profile}`"
    return heading + ")"


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
        owner_gaps = sorted(
            owner_gaps,
            key=lambda g: (_INTERVIEW_SEVERITY_ORDER.get(str(g.get("severity", "")).strip("`").lower(), 4), g["id"]),
        )
        entries = []
        for gap in owner_gaps:
            entries.append(_interview_gap_entry(number, gap, language))
            number += 1
        sections.append(f"### {_owner_heading(owner, language)}\n\n" + "\n\n".join(entries))
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
    if language == "es":
        header = (
            f"# Guion de entrevista - {project_id}\n\n"
            "Vista derivada READ-ONLY de los gaps abiertos, ordenada como guion de reunion "
            "(gaps bloqueantes primero, agrupados por lente). Las preguntas de profundizacion "
            "salen de las opciones candidatas citadas; nunca se inventan. Este guion "
            "NO reemplaza a `01_discovery/gaps.md` (la fuente de verdad) y no cierra ningun gap.\n"
        )
        blocking_heading = "## Preguntas bloqueantes"
        followup_heading = "## Preguntas de seguimiento"
        empty = "_No hay gaps abiertos: no hay preguntas para la entrevista._"
    else:
        header = (
            f"# Interview Script - {project_id}\n\n"
            "READ-ONLY derived view of the open gaps, ordered as a meeting script "
            "(blocking gaps first, grouped by lens). Probing questions come from the cited "
            "candidate options; they are never invented. This script does NOT replace "
            "`01_discovery/gaps.md` (the source of truth) and closes no gap.\n"
        )
        blocking_heading = "## Blocking questions"
        followup_heading = "## Follow-up questions"
        empty = "_No open gaps: there are no interview questions._"
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


def build_interview_script(project_id: str) -> str:
    """Read open gaps from the canonical gaps.md and render the interview script."""
    base = workspace_path(project_id)
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
