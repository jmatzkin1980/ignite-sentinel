"""IMP-414 (H27 inc 5a) task 2: the text of an element with the decision applied, written by the BA and confirmed one by one.

The extraction decides how an element of the request is treated; nothing records the text that replaces an
element a closed decision changed. The BA (or an agent) writes it in a block headed by the element
(`### RN-02`, `- Decisión: GAP-…`, `- Líneas: 31-31`, `- Texto: …`); this module checks that every sentence
comes from the element or from the answer of the decision (word by word, with two guards: numbers and ids,
and negations), records it in `extraction/consolidation.json` and keeps it as `proposed` until the BA confirms it.
"Transcribe, don't draft": a sentence that is neither one nor the other needs `Tipo: extension`.
"""
from __future__ import annotations

import re
from hashlib import sha256
from pathlib import Path
from typing import Any

from ..changes import _squash, change_language, get_change
from ..core.io import copy_file, read_json, write_json
from ..core.paths import workspace_path
from ..discovery.detection import split_evidence_sentences
from ..errors import GateRefusal, InputError
from . import extraction_dir
from .inventory import _fold, element_lines, inventory_state, load_inventory
from .lines import format_ranges, parse_line_ranges
from .proposals import TYPES, _element_text_cached, _msg, _next_submitted, _now, load_proposals, parse_proposals

KEEPS_REQUEST = {"GAP-DIS": {"B"}, "GAP-SRD": {"A", "B"}, "GAP-SED": {"A", "B", "C"}, "GAP-VER": {"A", "B", "C", "D"}}
RETIRES = {"GAP-SRD": {"C"}}
NEGATIONS = {"no", "sin", "nunca", "ningun", "ninguna", "not", "never", "without"}
_WORD = re.compile(r"\d+(?:[.,]\d+)*|\w+")
_ID_TOKEN = re.compile(r"\b[A-Z]{2,}(?:-[A-Za-z0-9]+)+\b")
_NUMBER_TOKEN = re.compile(r"\d+(?:[.,/:\-]\d+)*%?")
_PIECE = re.compile(r"(?<=[.!?])\s+|\n")

_MESSAGES = {
    "no_decision": (
        "{id}: un reemplazo necesita Decisión: con la GAP que lo motiva",
        "{id}: a replacement needs Decision: with the GAP that motivates it",
    ),
    "not_linked": (
        "{id}: {gap} no está vinculada a {id} (ni por el elemento ni por una línea citada)",
        "{id}: {gap} is not linked to {id} (neither by the element nor by a quoted line)",
    ),
    "keeps": (
        "{id}: la opción {opt} de {gap} conserva el texto del pedido: no hace falta reemplazo",
        "{id}: option {opt} of {gap} keeps the text of the request: no replacement is needed",
    ),
    "retires": (
        "{id}: {gap} lo saca del cambio: proponelo como descarte en la extracción",
        "{id}: {gap} takes it out of the change: propose it as a discard in the extraction",
    ),
    "replaces_other": (
        "{id}: Reemplaza dice {x}; el bloque es de {id}",
        "{id}: Replaces says {x}; the block is for {id}",
    ),
    "no_text": (
        "{id}: falta Texto: con cómo queda el elemento",
        "{id}: Text: is missing, with how the element reads",
    ),
    "unanchored": (
        "{id}: «{sentence}» no está en el elemento ni en la respuesta de {gaps}: si agrega algo, declaralo con Tipo: extension",
        "{id}: «{sentence}» is neither in the element nor in the answer of {gaps}: if it adds something, declare it with Type: extension",
    ),
    "bad_location": (
        "{id}: Ubicación debe ser un lugar del brief v2 (p. ej. 3.6)",
        "{id}: Location must be a place of the brief v2 (e.g. 3.6)",
    ),
    "confirm_first": (
        "{id}: confirmá primero su extracción",
        "{id}: confirm its extraction first",
    ),
    "keep_needs_reason": (
        "--keep-text necesita --reason con el porqué",
        "--keep-text needs --reason with the why",
    ),
    "keep_already": (
        "{gap}: la opción {opt} ya conserva el texto del pedido; no hace falta --keep-text",
        "{gap}: option {opt} already keeps the text of the request; --keep-text is not needed",
    ),
    "no_pending": (
        "{id} no tiene un reemplazo pendiente de confirmar",
        "{id} has no replacement pending confirmation",
    ),
}


def _text(code: str, language: str, **values: Any) -> str:
    spanish, english = _MESSAGES[code]
    return (spanish if language == "es" else english).format(**values)


# --- storage -------------------------------------------------------------------------------


def consolidation_path(base: Path, change_id: str) -> Path:
    return extraction_dir(base, change_id) / "consolidation.json"


def _skeleton(change_id: str) -> dict:
    return {"schema_version": 1, "change_id": change_id, "replacements": {}, "kept": {}, "rejections": []}


def load_consolidation(base: Path, change_id: str) -> dict:
    data = read_json(consolidation_path(base, change_id), None)
    if not isinstance(data, dict):
        return _skeleton(change_id)
    data.setdefault("schema_version", 1)
    data.setdefault("change_id", change_id)
    for key, empty in (("replacements", {}), ("kept", {}), ("rejections", [])):
        if not isinstance(data.get(key), type(empty)):
            data[key] = empty
    return data


# --- decisions and elements ----------------------------------------------------------------


def linked(decision: dict, element: dict) -> bool:
    """The decision touches the element: it lists it, or a citation of the request falls inside its lines."""
    if str(element.get("id")) in (decision.get("elements") or []):
        return True
    if str(element.get("id")) in (decision.get("holders") or []):  # IMP-435: it holds the literal the decision gave up
        return True
    first, last = element_lines(element)
    for cite in decision.get("citations") or []:
        if cite.get("side") == "pedido" and cite.get("line") and str(cite.get("source_id")) == str(element.get("source_id")):
            if first <= int(cite["line"]) <= last:
                return True
    return False


def keeps_request(decision: dict, element: dict) -> bool:
    """The option chosen leaves the text of the request as it is (for this element)."""
    option = str(decision.get("option") or "").strip().upper()
    if not option:
        return False
    family = str(decision.get("id", "")).rpartition("-")[0]
    if family == "GAP-CON":  # positional: A keeps the element of the first quoted request line, B the second's
        index = {"A": 0, "B": 1}.get(option)
        cites = [c for c in decision.get("citations") or [] if c.get("side") == "pedido" and c.get("line")]
        if index is None or index >= len(cites):
            return False
        first, last = element_lines(element)
        cite = cites[index]
        return str(cite.get("source_id")) == str(element.get("source_id")) and first <= int(cite["line"]) <= last
    return option in KEEPS_REQUEST.get(family, set())


def _losing_tokens(decision: dict, elements: list[dict]) -> list[str]:
    """IMP-435 (B-22): the numbers the request says where the decision does not keep it, and neither the answer nor
    the other side quote repeat (`5.000.000` when the design says `1.000.000`)."""
    cites = [c for c in decision.get("citations") or [] if c.get("quote")]
    winning = " ".join([str(decision.get("answer") or ""),
                        *(str(c["quote"]) for c in cites if c.get("side") != "pedido")])
    found: list[str] = []
    for element in elements:
        if str(element.get("id")) not in (decision.get("elements") or []) or keeps_request(decision, element):
            continue
        first, last = element_lines(element)
        for cite in cites:
            if (cite.get("side") == "pedido" and cite.get("line") and str(cite.get("source_id")) == str(element.get("source_id"))
                    and first <= int(cite["line"]) <= last):
                found.extend(t for t in _tokens(str(cite["quote"])) if not _has_token(t, winning))
    return list(dict.fromkeys(found))


def _holders_by_gap(project_id: str, change_id: str, decisions: list[dict]) -> dict[str, list[str]]:
    """Per closed decision that changes the request, the elements OTHER than the ones it links that still say the
    literal it gave up (the consolidation only linked the element the cross-read quoted)."""
    base = workspace_path(project_id)
    elements = list((load_inventory(base, change_id) or {}).get("elements", []))
    if not elements:
        return {}
    cache: dict[str, list[str] | None] = {}
    texts = {str(e["id"]): _element_text_cached(base, e, cache) or "" for e in elements}
    out: dict[str, list[str]] = {}
    for decision in decisions:
        if retires(decision):
            continue
        tokens = _losing_tokens(decision, elements)
        if not tokens:
            continue
        held = [str(e["id"]) for e in elements
                if not linked(decision, e) and any(_has_token(t, texts[str(e["id"])]) for t in tokens)]
        if held:
            out[str(decision["id"])] = held
    return out


def losing_literal_holders(project_id: str, change_id: str) -> list[str]:
    """IMP-435 (B-22): the elements, besides the ones a decision links, that still hold the figure it gave up."""
    from ..decision_memory import closed_decisions

    held = _holders_by_gap(project_id, change_id, closed_decisions(project_id, change_id))
    return list(dict.fromkeys(e for ids in held.values() for e in ids))


def governing_decisions(project_id: str, change_id: str) -> list[dict]:
    """The closed decisions, each with `holders`: the elements that still say what it gave up."""
    from ..decision_memory import closed_decisions

    decisions = closed_decisions(project_id, change_id)
    held = _holders_by_gap(project_id, change_id, decisions)
    return [{**d, "holders": held[d["id"]]} if d["id"] in held else d for d in decisions]


def decision_sha(decision: dict) -> str:
    """16 hex of what a decision says (answer and option): a replacement is anchored to exactly this."""
    text = f"{str(decision.get('option') or '').strip().upper()}|{_squash(str(decision.get('answer') or ''))}"
    return sha256(text.encode("utf-8")).hexdigest()[:16]


def decisions_moved(item: dict, decisions: dict[str, dict]) -> list[str]:
    """The decisions a stored replacement cites whose answer changed, or that are not closed (and governing) any more."""
    shas = item.get("decision_shas")
    if not isinstance(shas, dict):
        return []
    return [g for g, recorded in shas.items() if g not in decisions or decision_sha(decisions[g]) != recorded]


def retires(decision: dict) -> bool:
    option = str(decision.get("option") or "").strip().upper()
    return option in RETIRES.get(str(decision.get("id", "")).rpartition("-")[0], set())


def _places() -> set[str]:
    from ..brief_schema import load_brief_schema

    return {str(sub["id"]) for section in load_brief_schema().get("sections", []) for sub in section.get("subsections", [])}


# --- anchoring -----------------------------------------------------------------------------


def _words(text: str) -> list[str]:
    return _WORD.findall(_fold(str(text)))


def _pieces(text: str) -> list[str]:
    return [p for p in (piece.strip(" |-*>\t") for piece in _PIECE.split(str(text))) if p]


def _clean(sentence: str) -> str:
    return " ".join(sentence.strip(" |.!?;").split())


def _has_token(token: str, haystack: str) -> bool:
    percent = "" if token.endswith("%") else "(?!%)"
    return re.search(rf"(?<!\w)(?<!\d[.,]){re.escape(token)}(?!\w)(?![.,]\d){percent}", haystack) is not None


def _tokens(sentence: str) -> list[str]:
    ids = _ID_TOKEN.findall(sentence)
    rest = _ID_TOKEN.sub(" ", sentence)
    return [*ids, *_NUMBER_TOKEN.findall(rest)]


def _numbers_unknown(sentence: str, haystack: str) -> list[str]:
    """Guard (a): numbers, amounts, dates, percentages and ids of the sentence that are nowhere else, verbatim."""
    return [t for t in _tokens(sentence) if not _has_token(t, haystack)]


def _negation_changed(sentence: str, element_text: str, answers: list[str]) -> bool:
    """Guard (b): the sentence this one rewrites says no/sin/nunca… and the new one no longer does (the answer may say it
    for the element, never for itself), or the new one says one that neither that sentence nor an answer has."""
    mine = set(_words(sentence))
    if not mine:
        return False
    answer_words: set[str] = set()
    for answer in answers:
        answer_words.update(_words(answer))
    best: tuple[float, set[str], bool] = (0.0, set(), True)
    for from_element, texts in ((True, [element_text]), (False, answers)):
        for text in texts:
            for piece in _pieces(text):
                theirs = set(_words(piece))
                overlap = len(mine & theirs) / len(mine)
                if overlap > best[0]:
                    best = (overlap, theirs, from_element)
    overlap, theirs, from_element = best
    if overlap < 0.5:  # a sentence that joins several: the whole element is the reference, and nothing is "lost"
        return bool((mine & NEGATIONS) - set(_words(element_text)) - answer_words)
    if (theirs & NEGATIONS) - mine - (answer_words if from_element else set()):
        return True
    return bool((mine & NEGATIONS) - theirs - answer_words)


def anchored(sentence: str, element_text: str, answers: list[str]) -> bool:
    """The sentence is in the element or the answers word by word, without inventing a number, losing a no or adding one.

    A literal hit is no shortcut: a sentence that is a prefix or an infix of a longer source can cut a number or start after a `no`."""
    flat = _squash(_clean(sentence))
    if not flat:
        return True
    sources = [_squash(element_text or ""), *(_squash(a) for a in answers)]
    allowed: set[str] = set()
    for source in sources:
        allowed.update(_words(source))
    if any(word not in allowed for word in _words(flat)):
        return False
    if _numbers_unknown(flat, " ".join(sources)):
        return False
    return not _negation_changed(flat, element_text or "", answers)


def unanchored_sentences(text: str, element_text: str, answers: list[str]) -> list[str]:
    """The sentences of `text` (without the final punctuation) that `anchored` refuses."""
    found: list[str] = []
    kept = [_clean(s) for s in split_evidence_sentences(text)]
    for sentence in kept:
        if sentence and not anchored(sentence, element_text, answers):
            found.append(sentence)
    # `split_evidence_sentences` drops the short sentences and the digits a sentence starts with: check those pieces too
    for piece in _pieces(text):
        cleaned = _clean(piece)
        if not cleaned or any(cleaned in k for k in kept) or any(k in cleaned for k in found):
            continue
        if not anchored(cleaned, element_text, answers):
            found.append(cleaned)
    return found


# --- validation ----------------------------------------------------------------------------


def _raw_text(raw: dict) -> str:
    lines = raw.get("summary_lines") or ([raw["summary"]] if raw.get("summary") else [])
    return "\n".join(line.strip() for line in lines if str(line).strip())


def validate_replacement(
    element: dict, element_text: str | None, raw: dict, decisions: dict[str, dict], language: str,
    source_lines: list[str] | None, change_id: str = "",
) -> tuple[dict | None, list[str]]:
    """The normalized replacement of an element, or the errors that keep it out."""
    element_id = element["id"]
    values = {"id": element_id, "cid": change_id}
    errors: list[str] = []

    def fail(message: str) -> None:
        errors.append(message)

    flat = _squash(element_text) if element_text is not None else None
    if flat is None or sha256(flat.encode("utf-8")).hexdigest()[:16] != element.get("sha"):
        return None, [_msg("stale_element", language, id=element_id, pid="", cid=change_id)]

    cited = list(dict.fromkeys(str(d) for d in raw.get("decisions") or []))
    if not cited:
        fail(_text("no_decision", language, **values))
    for gap in cited:
        decision = decisions.get(gap)
        if decision is None:
            fail(_msg("unknown_decision", language, id=element_id, gap=gap, cid=change_id))
        elif not linked(decision, element):
            fail(_text("not_linked", language, gap=gap, **values))
        elif keeps_request(decision, element):
            fail(_text("keeps", language, gap=gap, opt=str(decision.get("option", "")).upper(), **values))
        elif retires(decision):
            fail(_text("retires", language, gap=gap, **values))
    known_all = [decisions[g] for g in cited if g in decisions]

    replaces = str(raw.get("replaces", "")).strip()
    if replaces and replaces != element_id:
        fail(_text("replaces_other", language, x=replaces, **values))

    kind_type = "aplica"
    type_raw = str(raw.get("type", "")).strip()
    if type_raw:
        kind_type = TYPES.get(type_raw.lower(), "")
        if not kind_type:
            fail(_msg("bad_type", language, id=element_id))
    text = _raw_text(raw)
    if not text:
        fail(_text("no_text", language, **values))
    elif kind_type == "aplica":
        answers = [str(d.get("answer", "")) for d in known_all]
        # the element's own id may head its replacement (`| RN-02 | … |`): it is a label, never a source of numbers
        body = re.sub(rf"(?m)^(\s*\|?\s*){re.escape(element_id)}\s*\|", r"\1", text)
        for sentence in unanchored_sentences(body, element_text, answers):
            fail(_text("unanchored", language, sentence=sentence, gaps=", ".join(cited), **values))

    location = str(raw.get("location", "")).strip()
    if location and location not in _places():
        fail(_text("bad_location", language, **values))

    lines: list[list[int]] = []
    if source_lines is not None:
        first, last = element_lines(element)
        lines_raw = str(raw.get("lines", "")).strip()
        parsed = parse_line_ranges(lines_raw) if lines_raw else None
        if not lines_raw:
            fail(_msg("no_lines", language, id=element_id, a=first, b=last))
        elif parsed is None:
            fail(_msg("bad_lines", language, id=element_id))
        elif parsed[0][0] < first or parsed[-1][1] > last:
            fail(_msg("lines_outside", language, id=element_id, ranges=format_ranges(parsed), a=first, b=last))
        else:
            lines = parsed

    if errors:
        return None, errors
    flags = [{"origin": "proposal", "kind": "extension", "ref": "", "note": ""}] if kind_type == "extension" else []
    return {
        "id": f"REP-{element_id}",
        "element_sha": element["sha"],
        "decisions": cited,
        "lines": lines,
        "text": text,
        "type": kind_type,
        "location": location,
        "flags": flags,
        "decision_shas": {g: decision_sha(decisions[g]) for g in cited},
    }, []


def _same(stored: dict, item: dict) -> bool:
    return all(stored.get(k) == item.get(k) for k in ("element_sha", "decisions", "lines", "text", "type", "location", "decision_shas"))


def _raw_of(item: dict) -> dict:
    """The stored replacement as the block it came from, so it can be validated again."""
    text = str(item.get("text", ""))
    return {
        "decisions": list(item.get("decisions") or []), "lines": format_ranges(item.get("lines") or []),
        "summary": " ".join(text.split()), "summary_lines": text.splitlines(),
        "type": item.get("type") or "", "location": item.get("location") or "", "replaces": "",
    }


# --- recording -----------------------------------------------------------------------------


def _precondition(project_id: str, change_id: str, change: dict, language: str) -> None:
    es = language == "es"
    if change.get("round") == "scope":
        raise GateRefusal(
            f"Cerrá primero el borde de {change_id} (GAP-SCOPE): las superficies salen de ahí" if es
            else f"Close the border of {change_id} (GAP-SCOPE) first: the surfaces come from there",
            next_step=f"/resolve-gaps {project_id} --change {change_id}",
        )
    state = inventory_state(project_id, change_id)
    if state in ("missing", "stale"):
        state_word = ("falta" if state == "missing" else "quedó viejo") if es else (
            "missing" if state == "missing" else "out of date")
        raise GateRefusal(
            f"Corré /extract {project_id} --change {change_id} antes de consolidar: el inventario {state_word}" if es
            else f"Run /extract {project_id} --change {change_id} before consolidating: the inventory is {state_word}",
            next_step=f"/extract {project_id} --change {change_id}",
        )


def _closed_by_id(project_id: str, change_id: str) -> dict[str, dict]:
    return {d["id"]: d for d in governing_decisions(project_id, change_id)}


def _extraction_confirmed(items: dict, element: dict) -> bool:
    item = items.get(element["id"]) or {}
    return item.get("status") == "confirmed" and item.get("element_sha") == element.get("sha")


def record_consolidation(project_id: str, change_id: str, source: Path) -> dict:
    change = get_change(project_id, change_id)
    language = change_language(project_id, change)
    es = language == "es"
    _precondition(project_id, change_id, change, language)
    base = workspace_path(project_id)
    inventory = load_inventory(base, change_id) or {}
    try:
        text = Path(source).read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError) as exc:
        raise InputError(f"No se pudo leer {source}: {exc}" if es else f"Could not read {source}: {exc}") from exc
    blocks, _repeated = parse_proposals(text)
    if not blocks:
        raise InputError(
            f"{Path(source).name} no tiene ningún bloque `### ID`" if es
            else f"{Path(source).name} has no `### ID` block"
        )
    folder = extraction_dir(base, change_id) / "submitted"
    folder.mkdir(parents=True, exist_ok=True)
    copy = _next_submitted(folder, Path(source).name)
    copy_file(source, copy)
    submitted = copy.relative_to(base).as_posix()

    elements = {e["id"]: e for e in inventory.get("elements", [])}
    extraction_items = load_proposals(base, change_id)["items"]
    store = load_consolidation(base, change_id)
    decisions = _closed_by_id(project_id, change_id)
    cache: dict[str, list[str] | None] = {}
    recorded: list[str] = []
    unchanged: list[str] = []
    flagged: list[str] = []
    skipped: list[str] = []
    rejected: dict[str, list[str]] = {}
    now = _now()
    for element_id, raw in blocks.items():
        if not (raw.get("decisions") or raw.get("summary") or raw.get("lines") or raw.get("replaces")):
            skipped.append(element_id)  # a blank block of the worksheet
            continue
        element = elements.get(element_id)
        if element is None:
            rejected[element_id] = [_msg("unknown_element", language, id=element_id, cid=change_id)]
            continue
        body = _element_text_cached(base, element, cache)
        item, errors = validate_replacement(
            element, body, raw, decisions, language, cache.get(str(element.get("path", ""))), change_id)
        if not _extraction_confirmed(extraction_items, element):
            errors = [*errors, _text("confirm_first", language, id=element_id)]
            item = None
        if item is None:
            rejected[element_id] = errors
            continue
        previous = store["replacements"].get(element_id) or {}
        if previous.get("status") in ("confirmed", "proposed") and _same(previous, item):
            unchanged.append(element_id)
            continue
        entry = dict(item)
        entry.update({"status": "proposed", "proposed_at": now, "confirmed_at": None, "submitted": submitted})
        store["replacements"][element_id] = entry
        recorded.append(element_id)
        if item["flags"]:
            flagged.append(element_id)
    known = {(r.get("id"), r.get("reason")) for r in store["rejections"] if isinstance(r, dict)}
    for element_id, errors in rejected.items():
        for reason in errors:
            if (element_id, reason) not in known:  # the same file again says nothing new
                store["rejections"].append({"id": element_id, "reason": reason, "at": now})
    write_json(consolidation_path(base, change_id), store)
    from ..consolidation_control import write_consolidation_control
    from ..readiness_verdict import change_next_step

    write_consolidation_control(project_id, change_id)
    n, u, r = len(recorded), len(unchanged), len(rejected)
    message = (
        f"{change_id}: {n} reemplazo(s) registrado(s), {u} sin cambios, {r} rechazado(s)" if es
        else f"{change_id}: {n} replacement(s) recorded, {u} unchanged, {r} rejected"
    )
    return {
        "project_id": project_id,
        "change_id": change_id,
        "action": "consolidate",
        "recorded": recorded,
        "unchanged": unchanged,
        "skipped": skipped,
        "rejected": rejected,
        "flagged": flagged,
        "submitted": submitted,
        "next_step": change_next_step(project_id, change_id),
        "message": message,
    }


def confirm_replacement(
    project_id: str, change_id: str, element_id: str, delegated: bool = False, note: str = "",
) -> dict:
    """Confirm the replacement of one element; the BA confirming what was delegated ratifies it."""
    from ..consolidation_control import write_consolidation_control
    from ..readiness_verdict import change_next_step
    from .confirm import _context, _source_lines
    from .inventory import element_text

    base, _inventory, elements, _change, language = _context(project_id, change_id)
    store = load_consolidation(base, change_id)
    item = store["replacements"].get(element_id)
    element = elements.get(element_id)
    result: dict[str, Any] = {"project_id": project_id, "change_id": change_id, "action": "confirm_replacement"}
    moved = decisions_moved(item, _closed_by_id(project_id, change_id)) if item is not None else []
    if (not delegated and item is not None and element is not None and not moved
            and item.get("status") == "confirmed" and item.get("confirmed_by") == "delegated"):
        for key in ("confirmed_by", "delegated_note", "delegated_at"):
            item.pop(key, None)
        write_json(consolidation_path(base, change_id), store)
        write_consolidation_control(project_id, change_id)
        result.update({"replacement": item, "ratified": [element_id], "next_step": change_next_step(project_id, change_id)})
        return result
    reconfirm = item is not None and item.get("status") == "confirmed" and bool(moved)
    if item is None or element is None or (item.get("status") != "proposed" and not reconfirm):
        raise InputError(_text("no_pending", language, id=element_id))
    problems: list[str] = []
    if item.get("element_sha") != element.get("sha"):
        problems.append(_msg("stale_element", language, id=element_id, pid=project_id, cid=change_id))
    else:
        if not _extraction_confirmed(load_proposals(base, change_id)["items"], element):
            problems.append(_text("confirm_first", language, id=element_id))
        _, errors = validate_replacement(
            element, element_text(base, element), _raw_of(item), _closed_by_id(project_id, change_id), language,
            _source_lines(base, element), change_id)
        problems.extend(errors)
    if problems:
        raise InputError("; ".join(problems))
    item["status"] = "confirmed"
    item["confirmed_at"] = _now()
    item["decision_shas"] = {g: decision_sha(d) for g, d in _closed_by_id(project_id, change_id).items() if g in item["decisions"]}
    if delegated:
        item["confirmed_by"], item["delegated_note"], item["delegated_at"] = (
            "delegated", str(note or "").strip(), item["confirmed_at"])
        result["delegated"] = [element_id]
    else:
        for key in ("confirmed_by", "delegated_note", "delegated_at"):
            item.pop(key, None)
    write_json(consolidation_path(base, change_id), store)
    write_consolidation_control(project_id, change_id)
    result.update({"replacement": item, "next_step": change_next_step(project_id, change_id)})
    return result


def keep_text(project_id: str, change_id: str, element_id: str, gap_id: str, reason: str) -> dict:
    """The BA keeps the text of the request for an element although a closed decision touches it (with the why)."""
    from ..consolidation_control import write_consolidation_control
    from ..readiness_verdict import change_next_step

    change = get_change(project_id, change_id)
    language = change_language(project_id, change)
    why = " ".join(str(reason or "").split())
    if not why:
        raise InputError(_text("keep_needs_reason", language))
    _precondition(project_id, change_id, change, language)
    base = workspace_path(project_id)
    elements = {e["id"]: e for e in (load_inventory(base, change_id) or {}).get("elements", [])}
    element = elements.get(element_id)
    if element is None:
        raise InputError(_msg("unknown_element", language, id=element_id, cid=change_id))
    decision = _closed_by_id(project_id, change_id).get(gap_id)
    if decision is None:
        raise InputError(_msg("unknown_decision", language, id=element_id, gap=gap_id, cid=change_id))
    if not linked(decision, element):
        raise InputError(_text("not_linked", language, id=element_id, gap=gap_id))
    if keeps_request(decision, element):
        raise InputError(_text("keep_already", language, gap=gap_id, opt=str(decision.get("option", "")).upper()))
    if retires(decision):
        raise InputError(_text("retires", language, id=element_id, gap=gap_id))
    store = load_consolidation(base, change_id)
    entry = store["kept"].setdefault(element_id, {})
    if not isinstance(entry.get(gap_id), dict) or entry[gap_id].get("reason") != why:
        entry[gap_id] = {"reason": why, "at": _now()}
    write_json(consolidation_path(base, change_id), store)
    write_consolidation_control(project_id, change_id)
    return {
        "project_id": project_id, "change_id": change_id, "action": "keep_text", "element": element_id, "gap": gap_id,
        "next_step": change_next_step(project_id, change_id),
    }
