"""IMP-412 (H27 inc 4): review views of a change for a third party (the border explained, the decisions).

The BA delegates and reviews: a colleague or a client reads what is registered and says yes or no. Both views
are built only from registered data (the confirmed border, the answers, the EARS rows, the elements of the
request, the open questions, the assumption register); nothing is written that nobody said.
"""
from __future__ import annotations

from pathlib import Path

from .changes import change_gaps_path, change_language, get_change
from .core.io import write_text
from .workspace import workspace_path

REVIEW_ARTIFACTS = ("borde", "decisiones")
ZONES = ("nuevo", "adyacente", "preservado")
LINE_MAX = 200

COPY = {
    "es": {
        "border_title": "Borde explicado", "decisions_title": "Decisiones del cambio",
        "intro": "> Vista de revisión armada sólo con lo registrado en Sentinel (borde, respuestas, requisitos y preguntas); no agrega nada.",
        "ba_answer": "Respuesta del BA (GAP-SCOPE)",
        "zones": {"nuevo": "Nuevo (se construye)", "adyacente": "Adyacente (existe y se toca)",
                  "preservado": "Preservado (no cambia)"},
        "zone_text": {"nuevo": "Se construye: hoy no existe.", "adyacente": "Existe y este cambio la toca.",
                      "preservado": "Existe y este cambio no la modifica."},
        "what": "Qué es", "why": "Por qué en esta zona", "from": "De dónde sale", "doubts": "Dudas abiertas",
        "to_confirm": "a confirmar", "none": "ninguna", "none_naming": "ninguna que la nombre", "no_description": "sin descripción registrada",
        "no_regression": "sin filas de no regresión todavía", "rows": "filas",
        "surfaces": "Superficies nuevas decididas", "accepted": "aceptada", "declined": "descartada",
        "option": "Opción elegida", "answer": "Respuesta", "evidence": "Evidencia", "quotes": "Citas",
        "decided": "Decidió", "unnamed": "BA (sin nombre)", "drafted": "redactó", "delegated": "confirmado por delegación del BA",
        "replaced": "Decisiones reemplazadas (no rigen)", "assumptions": "Supuestos (no son decisiones: a validar)", "validate": "a validar con",
    },
    "en": {
        "border_title": "Border explained", "decisions_title": "Decisions of the change",
        "intro": "> Review view built only from what is registered in Sentinel (border, answers, requirements and questions); it adds nothing.",
        "ba_answer": "BA answer (GAP-SCOPE)",
        "zones": {"nuevo": "New (to build)", "adyacente": "Adjacent (exists and is touched)",
                  "preservado": "Preserved (unchanged)"},
        "zone_text": {"nuevo": "To be built: it does not exist today.", "adyacente": "It exists and this change touches it.",
                      "preservado": "It exists and this change does not modify it."},
        "what": "What it is", "why": "Why in this zone", "from": "Where it comes from", "doubts": "Open doubts",
        "to_confirm": "to be confirmed", "none": "none", "none_naming": "none that names it", "no_description": "no recorded description",
        "no_regression": "no non-regression rows yet", "rows": "rows",
        "surfaces": "New surfaces decided", "accepted": "accepted", "declined": "declined",
        "option": "Chosen option", "answer": "Answer", "evidence": "Evidence", "quotes": "Quotes",
        "decided": "Decided by", "unnamed": "BA (unnamed)", "drafted": "drafted by", "delegated": "confirmed on behalf of the BA",
        "replaced": "Replaced decisions (they do not govern)", "assumptions": "Assumptions (not decisions: to validate)", "validate": "to validate with",
    },
}


def review_path(base: Path, change_id: str, artifact: str) -> Path:
    return base / "02_requirements" / change_id / "review" / f"{artifact}.md"


def _copy(project_id: str, change_id: str) -> dict:
    language = change_language(project_id, get_change(project_id, change_id))
    return COPY["es" if language == "es" else "en"]


def _fold(text: object) -> str:
    from .crosses.surfaces import _fold_name

    return _fold_name(str(text or ""))


def _squash(text: object) -> str:
    return " ".join(str(text or "").split())


def _scope_answer(project_id: str, change_id: str) -> str:
    from .compilers.change_brief import _answers

    found = _answers(workspace_path(project_id), get_change(project_id, change_id)).get("GAP-SCOPE") or {}
    return _squash(found.get("answer"))


def _open_questions(project_id: str, change_id: str) -> list[dict]:
    from .gaps import parse_gap_rows

    path = change_gaps_path(workspace_path(project_id), change_id)
    if not path.exists():
        return []
    out: list[dict] = []
    for row in parse_gap_rows(path.read_text(encoding="utf-8-sig")):
        gap_id = str(row.get("id", "")).strip()
        status = str(row.get("status", "")).strip("`").strip().upper()
        if gap_id in ("", "NONE") or status == "CLOSED":
            continue
        out.append({"id": gap_id, "question": _squash(row.get("question"))})
    return out


def _to_confirm_reason(project_id: str, change_id: str, row: dict) -> str:
    import re

    from .extraction.proposals import load_proposals

    found = re.search(r"EXT:([^`\s/]+)", str(row.get("source", "")))
    items = load_proposals(workspace_path(project_id), change_id)["items"]
    return _squash((items.get(found.group(1)) or {}).get("a_confirmar_reason")) if found else ""


def _quoted(text: str) -> str:
    return f"«{text[:LINE_MAX]}»"


def render_border_review(project_id: str, change_id: str) -> str:
    from .change_requirements import load_change_ears
    from .compilers.change_deliverable import _request_elements
    from .extraction.inventory import element_lines

    t = _copy(project_id, change_id)
    change = get_change(project_id, change_id)
    border = [item for item in change.get("border") or [] if isinstance(item, dict)]
    ears = load_change_ears(project_id, change_id)  # IMP-412 (P3): the rows the request left to confirm are in, marked
    elements = _request_elements(project_id, change_id)
    questions = _open_questions(project_id, change_id)
    lines = [f"# {t['border_title']} — {change_id}", "", t["intro"], ""]
    answer = _scope_answer(project_id, change_id)
    if answer:
        lines += [f"{t['ba_answer']}: {answer}", ""]
    for zone in ZONES:
        members = [item for item in border if item.get("zone") == zone]
        if not members:
            continue
        lines += [f"## {t['zones'][zone]}", ""]
        for item in members:
            name = str(item.get("name", ""))
            key = _fold(name)
            mine = [row for row in ears if key in {_fold(s) for s in row.get("surfaces") or []}]
            found = [(element, flat) for element, flat in elements if key and key in _fold(flat)]
            lines += [f"### {name} — {item.get('type', '')}", f"- {t['what']}:"]
            for row in mine:
                mark = f" — {t['to_confirm']}: {_to_confirm_reason(project_id, change_id, row)}" if row.get("a_confirmar") else ""
                lines.append(f"  - {row['id']}: {_squash(row['statement'])}{mark}")
            for element, flat in found:
                first = element_lines(element)[0]
                lines.append(f"  - {element['id']} ({element['source_id']}:{first}): {_quoted(flat)}")
            if not mine and not found:
                lines.append(f"  - {t['no_description']}")
            why = t["zone_text"][zone]
            if zone == "adyacente":
                touched = [row for row in mine if str(row.get("delta")) in ("MODIFIED", "REMOVED")]
                if touched:
                    why += f" {t['rows'].capitalize()}: " + ", ".join(f"{row['id']} ({row['delta']})" for row in touched)
            elif zone == "preservado":
                kept = [row for row in mine if str(row.get("delta")) == "UNCHANGED"]
                why += (f" {t['rows'].capitalize()}: " + ", ".join(row["id"] for row in kept)) if kept \
                    else f" ({t['no_regression']})"
            lines.append(f"- {t['why']}: {why}")
            origin = [str(item.get("cite", "")).strip()] + [f"{e['source_id']}:{element_lines(e)[0]}" for e, _ in found]
            lines.append(f"- {t['from']}: " + "; ".join(o for o in origin if o))
            doubts = [q for q in questions if key and key in _fold(q["question"])]
            if doubts:
                lines.append(f"- {t['doubts']}:")
                lines += [f"  - {q['id']}: {q['question']}" for q in doubts]
            else:
                lines.append(f"- {t['doubts']}: {t['none_naming']}")
            lines.append("")
    lines += [f"## {t['surfaces']}", ""]
    decided = _decided_surfaces(project_id, change_id, change, t)
    lines += decided or [t["none"]]
    return "\n".join(lines).rstrip() + "\n"


def _decided_surfaces(project_id: str, change_id: str, change: dict, t: dict) -> list[str]:
    out: list[str] = []
    for key, decision in sorted((change.get("new_surfaces") or {}).items()):
        if not isinstance(decision, dict):
            continue
        if decision.get("decision") == "accepted":
            out.append(f"- {decision.get('name', key)} ({decision.get('type', '')}) — {t['accepted']} ({key})")
        elif decision.get("decision") == "declined":
            text = _candidate_text(project_id, change_id, str(key)) or str(key)
            out.append(f"- {text} — {t['declined']} ({key}): {_squash(decision.get('reason'))}")
    return out


def _candidate_text(project_id: str, change_id: str, key: str) -> str:
    from .crosses.surfaces import new_surface_candidates, solo_en_diseno_item

    for item in new_surface_candidates(project_id, change_id):
        if item["id"] == key:
            return _squash(item["text"])
    try:
        return _squash(solo_en_diseno_item(project_id, change_id, key, "es")["text"])
    except Exception:  # the candidate is no longer in the record: the id is all there is
        return ""


def render_decisions_review(project_id: str, change_id: str) -> str:
    from .change_assumptions import open_change_assumptions
    from .decision_memory import closed_decisions, superseded_decisions
    from .delegation import current_gap_delegations
    from .resources import read_package_json

    t = _copy(project_id, change_id)
    language = "es" if t is COPY["es"] else "en"
    titles = read_package_json("templates", "change_brief.json")["lens_titles"]
    decisions = closed_decisions(project_id, change_id)
    delegated = current_gap_delegations(workspace_path(project_id), change_id)
    by_lens: dict[str, list[dict]] = {}
    for item in decisions:
        by_lens.setdefault(item["lens"].strip("`").lower(), []).append(item)
    lines = [f"# {t['decisions_title']} — {change_id}", "", t["intro"], ""]
    for lens in [*titles, *[k for k in by_lens if k not in titles]]:
        if lens not in by_lens:
            continue
        lines += [f"## {titles.get(lens, {}).get(language, lens)}", ""]
        for item in by_lens[lens]:
            lines.append(f"### {item['id']} — {item['question']}")
            if item["option"]:
                lines.append(f"- {t['option']}: {item['option']}")
            lines.append(f"- {t['answer']}: {_squash(item['answer'])}")
            if item["evidence"]:
                lines.append(f"- {t['evidence']}: {_squash(item['evidence'])}")
            if item["citations"]:
                lines.append(f"- {t['quotes']}:")
                for cite in item["citations"]:
                    lines.append(f"  - {cite['source_id']}:{cite['line']} «{cite['quote']}»")
            # IMP-412 final review (I5): who decided, who drafted and who confirmed for the BA show even without `Owner / fuente`
            line = f"- {t['decided']}: {item['owner'] or t['unnamed']}"
            if item["drafted_by"]:
                line += f" — {t['drafted']}: {item['drafted_by']}"
            if item["id"] in delegated:
                line += f" — {t['delegated']}"
            lines.append(line)
            lines.append("")
    replaced = superseded_decisions(project_id, change_id)
    if replaced:  # IMP-412: decisions a GAP-CHQ answer replaced are not facts; they are listed apart
        lines += [f"## {t['replaced']}", ""]
        lines += [f"- {item['id']}: {item['note']}" for item in replaced]
        lines.append("")
    open_rows = open_change_assumptions(project_id, change_id)
    if open_rows:
        lines += [f"## {t['assumptions']}", ""]
        for row in open_rows:
            lines.append(f"- {row['id']}: {_squash(row.get('statement'))} — {t['validate']} {row['validate_with']} ({row['gap']})")
    return "\n".join(lines).rstrip() + "\n"


def write_review_view(project_id: str, change_id: str, artifact: str) -> Path:
    if artifact not in REVIEW_ARTIFACTS:
        raise ValueError(f"Unsupported review view: {artifact}")
    text = (render_border_review if artifact == "borde" else render_decisions_review)(project_id, change_id)
    return write_text(review_path(workspace_path(project_id), change_id, artifact), text, newline="\n")
