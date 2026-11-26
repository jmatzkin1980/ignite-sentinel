"""IMP-416: `specs.md` of a change as the AI-ready document: one section per functionality (FUN-nn) with eight blocks.

Every block shows only registered data, quoted with its citation (the request's lines, the consolidated text of 5a, the
closed decisions, the assumptions and the harvest facts); a block with no data says so and is never drafted. The
project's `specs.md` is the contract plus the recovery plan and does not use this adapter.
"""
from __future__ import annotations

import re
from typing import Any

from ..change_assumptions import open_change_assumptions
from ..change_requirements import _fold_name, load_change_ears, parse_delta
from ..changes import change_gaps_path, change_language, deferred_gaps, get_change
from ..extraction.coverage import extraction_view
from ..workspace import workspace_path
from .change_deliverable import _EXT_SOURCE, _template, decision_log_lines

NO_DATA = {"es": "sin dato registrado", "en": "no data recorded"}
BLOCKS = {
    "es": ["Objetivo", "As-is (lo que existe hoy)", "To-be (cómo debe quedar)", "Interfaces que toca", "No regresión",
           "Decisiones que la afectan", "Supuestos y pendientes", "Orden y dependencias"],
    "en": ["Objective", "As-is (what exists today)", "To-be (target behavior)", "Interfaces touched", "No regression",
           "Decisions affecting it", "Assumptions and open items", "Order and dependencies"],
}
KEYS = ["objective", "as_is", "to_be", "interfaces", "no_regression", "decisions", "assumptions", "order"]
AS_IS_LIMIT = 10

COPY = {
    "es": {
        "title": "# Especificación del cambio {cid}",
        "fun": "## {fun} — {name} ({type}, {zone})",
        "no_surface": "## {fun} — Sin superficie: lugar {place}",
        "trace": "## Trazabilidad",
        "trace_header": ["Unidad", "REQ-EARS", "Elemento", "Cita", "Superficie", "GAP"],
        "preserved": "## Comportamiento preservado",
        "preserved_header": ["REQ-EARS", "Enunciado"],
        "no_preserved": "_Sin filas UNCHANGED._",
        "delivered": "entregado en {rid}",
        "note": "Las historias del cambio salen de estas unidades con /backlog --change.",
        "criteria": "Criterios de aceptación:",
        "build": "a construir", "existing": "existente", "kept": "preservado",
        "pass": "pass-to-pass", "assumption": "supuesto", "open": "pendiente",
        "first": "Va primero: es superficie nueva.", "depends": "Depende de {fun} ({name})",
    },
    "en": {
        "title": "# Change specification {cid}",
        "fun": "## {fun} — {name} ({type}, {zone})",
        "no_surface": "## {fun} — No surface: place {place}",
        "trace": "## Traceability",
        "trace_header": ["Unit", "REQ-EARS", "Element", "Citation", "Surface", "GAP"],
        "preserved": "## Preserved behavior",
        "preserved_header": ["REQ-EARS", "Statement"],
        "no_preserved": "_No UNCHANGED rows._",
        "delivered": "delivered in {rid}",
        "note": "The stories of the change come from these units with /backlog --change.",
        "criteria": "Acceptance criteria:",
        "build": "to build", "existing": "existing", "kept": "preserved",
        "pass": "pass-to-pass", "assumption": "assumption", "open": "open",
        "first": "Goes first: it is a new surface.", "depends": "Depends on {fun} ({name})",
    },
}


ZONES_EN = {"nuevo": "new", "adyacente": "adjacent", "preservado": "preserved"}


def _kind(language: str, kind: Any) -> str:
    """The surface type as the change language names it (the enablers use the same table)."""
    from .slicing import ENABLER_SURFACE_TEXT

    return str(ENABLER_SURFACE_TEXT[language]["types"].get(str(kind), kind))


def _zone(language: str, zone: Any) -> str:
    return ZONES_EN.get(str(zone), str(zone)) if language == "en" else str(zone)


def _cell(text: Any) -> str:
    return " ".join(str(text).split()).replace("|", "\\|")


def _cite(element: dict) -> str:
    parts = []
    for span in element.get("spans") or []:
        a, b = int(span[0]), int(span[-1])
        parts.append(f"{element['path']}:L{a}" if a == b else f"{element['path']}:L{a}-L{b}")
    return ", ".join(parts)


def _mentions(text: str, code: str) -> bool:
    return bool(re.search(rf"(?<![\w-]){re.escape(code)}(?![\w-])", str(text)))


def _plain(text: str, element_id: str = "") -> str:
    """A table row of the request reads as its cells, without the pipes and the element's own id."""
    lines = []
    for line in str(text or "").splitlines():
        if line.strip().startswith("|"):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            line = " ".join(c for c in cells if c and c != element_id and not set(c) <= set("-: "))
        lines.append(line)
    return "\n".join(lines)


def _quote(text: str, cite: str, element_id: str = "") -> str | None:
    """The first sentence of a registered text, quoted with where it comes from."""
    from ..discovery.detection import split_evidence_sentences

    sentences = split_evidence_sentences(_plain(text, element_id))
    if not sentences:
        return None
    return f"> «{sentences[0]}» ({cite})" if cite else f"> «{sentences[0]}»"


def change_spec_context(project_id: str, change_id: str, units: list[dict], funs: list[dict],
                        delivered: dict[str, list[str]] | None = None) -> dict:
    """`delivered`: release id -> the `SPEC-U` ids a closed release already delivered; they read as preserved behavior (IMP-429)."""
    from ..consolidation_control import consolidation_control
    from ..decision_memory import closed_decisions
    from ..extraction.consolidation import load_consolidation
    from ..extraction.proposals import _element_text_cached
    from ..gaps.render import parse_gap_rows
    from ..harvest import load_harvest

    change = get_change(project_id, change_id)
    language = "en" if change_language(project_id, change) == "en" else "es"
    copy = COPY[language]
    base = workspace_path(project_id)
    template = _template()
    border = {str(i.get("name")): i for i in change.get("border") or []}
    rows = load_change_ears(project_id, change_id)
    row_by_id = {r["id"]: r for r in rows}
    unit_of = {u["ears"][0]: u for u in units}
    view = extraction_view(project_id, change_id)
    elements = {str(e["id"]): e for e in view.get("elements", [])} if view.get("state", "missing") != "missing" else {}
    replaced: dict[str, dict] = {}
    if elements:
        stored = load_consolidation(base, change_id)["replacements"]
        for row in consolidation_control(project_id, change_id)["rows"]:
            if row["status"] == "modificado" and row["element"] in stored:
                replaced[str(row["element"])] = stored[row["element"]]
    cache: dict[str, list[str] | None] = {}
    decisions = closed_decisions(project_id, change_id)
    log = [line for line in decision_log_lines(project_id, change_id, language, {}, replaced) if line.startswith("|")]
    log_head, log_rows = log[:2], log[2:]
    assumptions = open_change_assumptions(project_id, change_id)
    path = change_gaps_path(base, change_id)
    questions: dict[str, str] = {}
    if path.exists():
        for gap in parse_gap_rows(path.read_text(encoding="utf-8-sig")):
            questions[str(gap.get("id", "")).strip("`")] = str(gap.get("question") or gap.get("description") or "")
    deferred = deferred_gaps(project_id, change_id)
    entries = load_harvest(base).get("entries", [])
    facts = [e for e in entries if isinstance(e, dict) and e.get("kind") == "fact"] if border else []
    by_fun = {f["id"]: f for f in funs}

    def element_gaps(element_id: str) -> list[str]:
        found = [str(g) for g in (replaced.get(element_id) or {}).get("decisions") or []]
        found += [str(d["id"]) for d in decisions if element_id in (d.get("elements") or [])]
        return sorted(dict.fromkeys(found))

    def element_quote(element_id: str) -> str | None:
        element = elements.get(element_id)
        if element is None:
            return None
        if element_id in replaced:
            # IMP-416: the replacement quotes its own lines and the GAP decisions it comes from, not the superseded element's span
            found = replaced[element_id]
            own = _cite({"path": element["path"], "spans": found.get("lines") or element.get("spans") or []})
            gaps = [str(g) for g in found.get("decisions") or []]
            return _quote(str(found.get("text") or ""), "; ".join([own, *gaps]) if own else "; ".join(gaps), element_id)
        return _quote(str(_element_text_cached(base, element, cache) or ""), _cite(element), element_id)

    out_funs: list[dict] = []
    trace_rows: list[list[str]] = []
    for fun in funs:
        linked = [e for e in fun["elements"] if e in elements]
        criteria = [e for e in linked if str(elements[e].get("kind")) == "criterion" or e.startswith("CA-")]
        group_rows = [row_by_id[r] for r in fun["rows"] if r in row_by_id]
        wanted_gaps = set(g for e in linked for g in element_gaps(e)) | set(fun["gaps"])
        blocks: dict[str, list[str]] = {key: [] for key in KEYS}

        for element_id in linked:
            quote = None if element_id in criteria else element_quote(element_id)
            if quote:
                blocks["objective"].append(quote)
        for row in group_rows:
            code = re.search(r"`(GAP-[^`]+)`", str(row.get("source", "")))
            quote = _quote(row["statement"], code.group(1)) if code else None
            if quote:
                blocks["objective"].append(quote)

        if fun["type"]:
            wanted = set(template["surface_blocks"].get(fun["type"], []))
            folded = _fold_name(fun["name"])
            found = [e for e in facts if e.get("block") in wanted]
            named = [e for e in found if folded and folded in _fold_name(str(e.get("text", "")))]
            chosen = named if (named or fun["zone"] == "nuevo") else found  # a surface that does not exist yet has no as-is of its own
            blocks["as_is"] = [f"- {e['text']} ({e['ref']})" for e in chosen[:AS_IS_LIMIT]]
            if len(chosen) > AS_IS_LIMIT:
                blocks["as_is"].append(f"(+{len(chosen) - AS_IS_LIMIT})")

        for row in group_rows:
            unit = unit_of.get(row["id"])
            if unit:
                blocks["to_be"].append(f"- {unit['id']} {row['id']} [{parse_delta(row['delta'])}] {row['statement']}")
        quotes = [q for e in criteria if (q := element_quote(e))]
        if quotes:
            blocks["to_be"] += ["", copy["criteria"], "", *quotes]

        for name in fun["surfaces"]:
            item = border.get(name)
            if item is None:
                continue
            state = copy["build"] if item.get("zone") == "nuevo" else copy["existing"]
            line = f"- {_kind(language, item.get('type', ''))} — {name} — {state}"
            blocks["interfaces"].append(f"{line} ({item['cite']})" if item.get("cite") else line)

        for other_id in fun["preserved"]:
            other = row_by_id.get(other_id)
            if other:
                blocks["no_regression"].append(f"- {other_id} {other['statement']} — {copy['pass']}")
        for name in fun["surfaces"]:
            item = border.get(name)
            if item is not None and item.get("zone") == "preservado":
                blocks["no_regression"].append(f"- {_kind(language, item.get('type', ''))} — {name} — {copy['kept']}")

        mine = [row for row in log_rows if any(row.startswith(f"| {gap} |") for gap in wanted_gaps)]
        blocks["decisions"] = [*log_head, *mine] if mine else []

        for asm in assumptions:
            if str(asm.get("gap") or "") in wanted_gaps or any(_mentions(asm["statement"], e) for e in linked):
                gap = asm.get("gap") or asm.get("closes_gap") or ""
                blocks["assumptions"].append(
                    f"- [{copy['assumption']}] {asm['id']} {asm['statement']}" + (f" ({gap})" if gap else ""))
        sources = " ".join(str(r.get("source", "")) for r in group_rows)
        folded_name = _fold_name(fun["name"])
        for gap in deferred:
            question = questions.get(gap["id"], "")
            if (_mentions(sources, gap["id"]) or any(_mentions(question, e) for e in linked)
                    or (folded_name and folded_name in _fold_name(question))):
                blocks["assumptions"].append(f"- [{copy['open']}] {gap['id']} {question}".rstrip())

        if fun["zone"] == "nuevo":
            blocks["order"].append(copy["first"])
        for dep in fun["depends_on"]:
            blocks["order"].append(f"- {copy['depends'].format(fun=dep, name=by_fun[dep]['name'])}")

        out_funs.append({**fun, "blocks": blocks})

        for row in group_rows:
            unit = unit_of.get(row["id"])
            found = _EXT_SOURCE.match(str(row.get("source", "")))
            if found:
                element_id = found.group(1)
                element = elements.get(element_id)
                cite = _cite(element) if element else str(row.get("source", ""))
                gaps = element_gaps(element_id)
            else:
                code = re.search(r"`(GAP-[^`]+)`", str(row.get("source", "")))
                element_id, cite, gaps = (code.group(1) if code else ""), str(row.get("source", "")), []
            trace_rows.append([unit["id"] if unit else "—", row["id"], element_id, cite,
                               fun["name"] or "—", ", ".join(gaps) or "—"])

    preserved_rows = [r for r in rows if parse_delta(r["delta"]) == "UNCHANGED"]
    delivered_rows: list[tuple[str, str, str]] = []
    if delivered:
        from .change_backlog import read_change_units

        known = {u["id"]: u for u in read_change_units(project_id, change_id)}
        delivered_rows = [(uid, str(known[uid]["statement"]), rid) for rid, ids in delivered.items() for uid in ids if uid in known]
    return {"language": language, "funs": out_funs, "trace_rows": trace_rows, "preserved_rows": preserved_rows,
            "delivered_rows": delivered_rows}


def _table(header: list[str], rows: list[list[str]]) -> list[str]:
    return ["| " + " | ".join(header) + " |", "| " + " | ".join("---" for _ in header) + " |",
            *["| " + " | ".join(_cell(c) for c in row) + " |" for row in rows]]


def render_change_spec_doc(context: dict, change_id: str) -> str:
    language = context["language"]
    copy = COPY[language]
    empty = f"_{NO_DATA[language]}_"
    lines = [copy["title"].format(cid=change_id), ""]
    for fun in context["funs"]:
        if fun["name"]:
            lines.append(copy["fun"].format(fun=fun["id"], name=fun["name"], type=_kind(language, fun["type"]),
                                      zone=_zone(language, fun["zone"])))
        else:
            lines.append(copy["no_surface"].format(fun=fun["id"], place=fun["place"]))
        lines.append("")
        for title, key in zip(BLOCKS[language], KEYS):
            lines += [f"### {title}", "", *(fun["blocks"][key] or [empty]), ""]
    lines += [copy["trace"], "", *_table(copy["trace_header"], context["trace_rows"]), "", copy["preserved"], ""]
    delivered = [[f"`{uid}`", f"{statement} ({copy['delivered'].format(rid=rid)})"]
                 for uid, statement, rid in context.get("delivered_rows") or []]
    if context["preserved_rows"] or delivered:
        lines += _table(copy["preserved_header"],
                        [[f"`{r['id']}`", r["statement"]] for r in context["preserved_rows"]] + delivered)
    else:
        lines.append(copy["no_preserved"])
    lines += ["", copy["note"], ""]
    return "\n".join(lines)
