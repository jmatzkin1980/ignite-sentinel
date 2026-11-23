"""IMP-402 task 2: citation-backed proposals, one block per inventory element.

The BA (or an agent) fills the worksheet `proposals_template.md`; this module parses
the file, validates every block against the inventory (verbatim quote, EARS, border
surfaces) and records the valid ones in `extraction/proposals.json`. Nothing is
confirmed here: "transcribe, don't draft".
"""
from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any

from ..change_requirements import load_change_ears, parse_affects, parse_delta, parse_surfaces
from ..changes import MIN_BASELINE_QUOTE, _squash, change_language, get_change
from ..core.io import copy_file, read_json, write_json, write_text
from ..core.paths import workspace_path
from ..core.text import unique_path
from ..ears import classify_ears
from ..errors import GateRefusal, InputError
from ..gap_resolution import ears_statements
from . import extraction_dir
from .flags import change_flag_context, element_flags
from .inventory import _read_text, _split_lines, inventory_state, load_inventory

TREATMENTS = {
    "requisito": "requisito", "requirement": "requisito",
    "seccion": "seccion", "sección": "seccion", "section": "seccion",
    "descarte": "descarte", "discard": "descarte",
}
SECTION_KEYS = {"objetivo": 2, "usuarios": 2, "proceso": 4, "alcance": 3, "preservado": 6, "reglas": 7, "aceptacion": 7}
SECTION_ALIASES = {
    "objective": "objetivo", "users": "usuarios", "process": "proceso", "scope": "alcance",
    "preserved": "preservado", "rules": "reglas", "acceptance": "aceptacion", "aceptación": "aceptacion",
}
FLAG_KINDS = {
    "divergencia": "divergencia", "divergence": "divergencia",
    "contradiccion": "contradiccion", "contradicción": "contradiccion", "contradiction": "contradiccion",
    "sin_respaldo": "sin_respaldo", "sin respaldo": "sin_respaldo", "unsupported": "sin_respaldo",
}

_LABELS = {
    "tratamiento": "treatment", "treatment": "treatment",
    "cita": "quote", "quote": "quote",
    "enunciado": "statement", "statement": "statement",
    "delta": "delta",
    "superficie": "surface", "surface": "surface",
    "afecta": "affects", "affects": "affects",
    "seccion": "section", "sección": "section", "section": "section",
    "texto": "text", "text": "text",
    "motivo": "reason", "reason": "reason",
    "marca": "flag", "flag": "flag",
}
_FIELD_NAMES = {"delta": "Delta", "surface": "Superficie", "affects": "Afecta"}
_HEADING = re.compile(r"^###\s+(.+?)\s*$")
_FIELD = re.compile(r"^\s*[-*]\s*([^\W\d_]+)\s*:\s*(.*?)\s*$")
_FLAG_SPLIT = re.compile(r" — |:| - ")
_CONTINUED = ("text", "reason", "quote")  # an indented line under these fields continues their value
_EXT_SOURCE = re.compile(r"`EXT:([^`]+)`")


def _fold(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", text) if not unicodedata.combining(c)).lower().strip()


def _unquote(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and ((value[0] == '"' and value[-1] == '"') or (value[0] == "“" and value[-1] == "”")):
        return value[1:-1].strip()
    return value


def _new_block() -> dict[str, Any]:
    return {
        "treatment": "", "quote": "", "statements": [], "section": "", "text": "",
        "reason": "", "flag": "", "flag_note": "", "errors": [],
    }


def parse_proposals(text: str) -> tuple[dict[str, dict], list[str]]:
    """The blocks of a proposals file by element id, and warnings (a repeated id: the last wins)."""
    blocks: dict[str, dict] = {}
    warnings: list[str] = []
    current: dict[str, Any] | None = None
    last_key: str | None = None
    raw_quote = ""
    in_comment = False
    for line in text.splitlines():
        stripped = line.strip()
        if in_comment:
            in_comment = "-->" not in stripped
            continue
        if stripped.startswith("<!--"):
            in_comment = "-->" not in stripped
            continue
        if stripped.startswith(">"):
            continue
        heading = _HEADING.match(line)
        if heading:
            current_id = heading.group(1)
            if current_id in blocks:
                warnings.append(current_id)
            current = _new_block()
            blocks[current_id] = current
            last_key = None
            continue
        if current is None:
            continue
        field = _FIELD.match(line)
        key = _LABELS.get(field.group(1).lower()) if field else None
        if key is None:
            if last_key in _CONTINUED and not field and stripped and line[:1].isspace():
                if last_key == "quote":
                    raw_quote = f"{raw_quote} {stripped}"
                    current["quote"] = _unquote(raw_quote)
                else:
                    current[last_key] = f"{current[last_key]} {stripped}".strip()
                continue
            last_key = None
            continue
        value = field.group(2)
        last_key = key
        if key == "statement":
            current["statements"].append({"text": value, "delta": "", "surface": "", "affects": ""})
        elif key in ("delta", "surface", "affects"):
            if current["statements"]:
                current["statements"][-1][key] = value
            elif value:
                current["errors"].append({"code": "orphan_field", "field": _FIELD_NAMES[key]})
        elif key == "quote":
            raw_quote = value
            current["quote"] = _unquote(value)
        elif key == "flag":
            found = _FLAG_SPLIT.search(value)
            kind, note = (value[: found.start()], value[found.end():]) if found else (value, "")
            current["flag"], current["flag_note"] = kind.strip().lower(), note.strip()
        else:
            current[key] = value
    return blocks, warnings


# --- messages ------------------------------------------------------------------------------

_MESSAGES = {
    "unknown_element": (
        "{id}: no está en el inventario de {cid} (usá los ids de la planilla)",
        "{id}: is not in the inventory of {cid} (use the ids of the worksheet)",
    ),
    "stale_element": (
        "{id}: el texto cambió en la fuente desde el inventario; corré /extract {pid} --change {cid}",
        "{id}: the text changed in the source since the inventory; run /extract {pid} --change {cid}",
    ),
    "bad_treatment": (
        "{id}: Tratamiento debe ser requisito, seccion o descarte",
        "{id}: Treatment must be requirement, section or discard",
    ),
    "no_quote": (
        "{id}: falta Cita (una frase literal del elemento, de 20 caracteres o más)",
        "{id}: Quote is missing (a literal phrase of the element, 20 characters or more)",
    ),
    "short_quote": (
        "{id}: la cita tiene menos de 20 caracteres",
        "{id}: the quote is shorter than 20 characters",
    ),
    "quote_not_found": (
        "{id}: la cita no aparece literal en el elemento (`{path}`:{line}); se compara sin diferencias de espacios, respetando mayúsculas",
        "{id}: the quote does not appear verbatim in the element (`{path}`:{line}); it is compared ignoring whitespace differences, case-sensitive",
    ),
    "no_statement": (
        "{id}: un requisito necesita al menos un Enunciado",
        "{id}: a requirement needs at least one Statement",
    ),
    "not_ears": (
        "{id}: «{statement}» no es EARS (Cuando/Mientras/Si/Donde …, el sistema debe …)",
        "{id}: «{statement}» is not EARS (When/While/If/Where …, the system shall …)",
    ),
    "multi_statement": (
        "{id}: «{statement}» tiene más de un enunciado EARS; poné cada uno en su propio Enunciado",
        "{id}: «{statement}» has more than one EARS statement; put each in its own Statement",
    ),
    "bad_delta": (
        "{id}: «{statement}» necesita Delta ADDED, MODIFIED, REMOVED o UNCHANGED",
        "{id}: «{statement}» needs Delta ADDED, MODIFIED, REMOVED or UNCHANGED",
    ),
    "no_surface": (
        "{id}: «{statement}» necesita Superficie (una o más del borde, separadas por ;)",
        "{id}: «{statement}» needs Surface (one or more from the border, separated by ;)",
    ),
    "unknown_surface": (
        "{id}: {names} no están en el borde de {cid}",
        "{id}: {names} are not in the border of {cid}",
    ),
    "bad_affects": (
        "{id}: Afecta debe nombrar historias US-NNN o decir ninguna",
        "{id}: Affects must name US-NNN stories or say none",
    ),
    "orphan_field": (
        "{id}: {field} sin un Enunciado antes",
        "{id}: {field} without a Statement before it",
    ),
    "bad_section": (
        "{id}: Seccion debe ser objetivo, usuarios, proceso, alcance, preservado, reglas o aceptacion",
        "{id}: Section must be objective, users, process, scope, preserved, rules or acceptance",
    ),
    "no_reason": (
        "{id}: un descarte necesita Motivo",
        "{id}: a discard needs Reason",
    ),
    "bad_flag": (
        "{id}: Marca debe ser divergencia, contradiccion o sin_respaldo",
        "{id}: Flag must be divergence, contradiction or unsupported",
    ),
}


def _msg(code: str, language: str, **values: Any) -> str:
    spanish, english = _MESSAGES[code]
    return (spanish if language == "es" else english).format(**values)


# --- validation ----------------------------------------------------------------------------


def validate_proposal(
    element: dict, element_text: str | None, raw: dict, border: list[dict], language: str, ctx: dict,
) -> tuple[dict | None, list[str]]:
    """The normalized item of a block, or the errors that keep it out. An empty treatment is neither."""
    treatment_raw = str(raw.get("treatment", "")).strip()
    if not treatment_raw:
        return None, []
    values = {"id": element["id"], "pid": ctx.get("pid", ""), "cid": ctx.get("cid", "")}
    errors: list[str] = []

    def fail(code: str, **extra: Any) -> None:
        errors.append(_msg(code, language, **values, **extra))

    treatment = TREATMENTS.get(treatment_raw.lower())
    if treatment is None:
        fail("bad_treatment")
        return None, errors

    flat = _squash(element_text) if element_text is not None else None
    if flat is None or sha256(flat.encode("utf-8")).hexdigest()[:16] != element.get("sha"):
        fail("stale_element")
        return None, errors
    quote = _squash(str(raw.get("quote", "")))
    if not quote:
        fail("no_quote")
    elif len(quote) < MIN_BASELINE_QUOTE:
        fail("short_quote")
    elif quote not in flat:
        fail("quote_not_found", path=element.get("path", ""), line=element.get("line", ""))

    for problem in raw.get("errors", []):
        fail(problem["code"], field=problem.get("field", ""))

    statements: list[dict] = []
    section: str | None = None
    brief_section: int | None = None
    if treatment == "requisito":
        entries = [
            s for s in raw.get("statements", [])
            if str(s.get("text", "")).strip() or any(str(s.get(k, "")).strip() for k in ("delta", "surface", "affects"))
        ]
        if not entries:
            fail("no_statement")
        for entry in entries:
            sentence = " ".join(str(entry.get("text", "")).split())
            ears = classify_ears(sentence)
            if len(ears_statements(sentence)) > 1:
                fail("multi_statement", statement=sentence)
            elif ears is None:
                fail("not_ears", statement=sentence)
            delta = parse_delta(str(entry.get("delta", "")))
            if delta is None:
                fail("bad_delta", statement=sentence)
            valid, unknown = parse_surfaces(str(entry.get("surface", "")), border)
            if unknown:
                fail("unknown_surface", names=", ".join(unknown))
            elif not valid:
                fail("no_surface", statement=sentence)
            affects: list[str] = []
            affects_raw = str(entry.get("affects", "")).strip()
            if affects_raw:
                parsed = parse_affects(affects_raw)
                if parsed is None:
                    fail("bad_affects")
                elif delta in ("MODIFIED", "REMOVED"):
                    affects = parsed
            statements.append({
                "text": sentence, "pattern": ears, "delta": delta, "surfaces": valid, "affects": affects,
            })
    elif treatment == "seccion":
        key = str(raw.get("section", "")).strip().lower()
        key = SECTION_ALIASES.get(key, key)
        if key not in SECTION_KEYS:
            folded = _fold(key)
            key = SECTION_ALIASES.get(folded, folded)
        if key in SECTION_KEYS:
            section, brief_section = key, SECTION_KEYS[key]
        else:
            fail("bad_section")
    else:
        if not str(raw.get("reason", "")).strip():
            fail("no_reason")

    flags: list[dict] = []
    flag_raw = str(raw.get("flag", "")).strip().lower()
    if flag_raw:
        kind = FLAG_KINDS.get(flag_raw)
        if kind is None:
            fail("bad_flag")
        else:
            flags.append({"origin": "agent", "kind": kind, "ref": "", "note": str(raw.get("flag_note", "")).strip()})

    if errors:
        return None, errors
    section_text = str(raw.get("text", "")).strip() or None
    reason = str(raw.get("reason", "")).strip() or None
    return {
        "element_sha": element["sha"],
        "treatment": treatment,
        "quote": quote,
        "statements": statements,
        "section": section,
        "brief_section": brief_section,
        "text": section_text if treatment == "seccion" else None,
        "reason": reason if treatment == "descarte" else None,
        "flags": flags,
    }, []


# --- storage -------------------------------------------------------------------------------


def _proposals_path(base: Path, change_id: str) -> Path:
    return extraction_dir(base, change_id) / "proposals.json"


def _skeleton(change_id: str) -> dict:
    return {"schema_version": 1, "change_id": change_id, "items": {}, "rejections": []}


def load_proposals(base: Path, change_id: str) -> dict:
    data = read_json(_proposals_path(base, change_id), None)
    if not isinstance(data, dict) or not isinstance(data.get("items"), dict):
        return _skeleton(change_id)
    data.setdefault("schema_version", 1)
    data.setdefault("change_id", change_id)
    if not isinstance(data.get("rejections"), list):
        data["rejections"] = []
    return data


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _next_submitted(folder: Path, name: str) -> Path:
    highest = 0
    if folder.is_dir():
        for existing in folder.iterdir():
            head = existing.name.split("-", 1)[0]
            if head.isdigit():
                highest = max(highest, int(head))
    return unique_path(folder / f"{highest + 1:03d}-{name}")


def _element_text_cached(base: Path, element: dict, cache: dict[str, list[str] | None]) -> str | None:
    """Same text as `inventory.element_text`, reading each source file once per call."""
    path = str(element.get("path", ""))
    if path not in cache:
        text = _read_text(base, path)
        cache[path] = None if text is None else _split_lines(text)
    lines = cache[path]
    if lines is None:
        return None
    chunks = []
    for start, end in element.get("spans", []):
        if start < 1 or end > len(lines):
            return None
        chunks.append("\n".join(lines[start - 1 : end]))
    return "\n".join(chunks)


def record_proposals(project_id: str, change_id: str, source: Path) -> dict:
    change = get_change(project_id, change_id)
    language = change_language(project_id, change)
    es = language == "es"
    if change.get("round") == "scope":
        raise GateRefusal(
            f"Cerrá primero el borde de {change_id} (GAP-SCOPE): las superficies salen de ahí" if es
            else f"Close the border of {change_id} (GAP-SCOPE) first: the surfaces come from there",
            next_step=f"/resolve-gaps {project_id} --change {change_id}",
        )
    state = inventory_state(project_id, change_id)
    if state in ("missing", "stale"):
        if es:
            message = f"Corré /extract {project_id} --change {change_id} antes de proponer: el inventario " + (
                "falta" if state == "missing" else "quedó viejo")
        else:
            message = f"Run /extract {project_id} --change {change_id} before proposing: the inventory is " + (
                "missing" if state == "missing" else "out of date")
        raise GateRefusal(message, next_step=f"/extract {project_id} --change {change_id}")
    base = workspace_path(project_id)
    inventory = load_inventory(base, change_id) or {}
    try:
        text = Path(source).read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError) as exc:
        raise InputError(f"No se pudo leer {source}: {exc}" if es else f"Could not read {source}: {exc}") from exc
    blocks, repeated = parse_proposals(text)
    if not blocks:
        raise InputError(
            f"{Path(source).name} no tiene ningún bloque `### ID`; usá la planilla proposals_template.md" if es
            else f"{Path(source).name} has no `### ID` block; use the proposals_template.md worksheet"
        )
    folder = extraction_dir(base, change_id) / "submitted"
    folder.mkdir(parents=True, exist_ok=True)
    copy = _next_submitted(folder, Path(source).name)
    copy_file(source, copy)
    submitted = copy.relative_to(base).as_posix()

    elements = {e["id"]: e for e in inventory.get("elements", [])}
    store = load_proposals(base, change_id)
    items: dict[str, dict] = store["items"]
    ctx = {"pid": project_id, "cid": change_id}
    warnings = [
        (f"{element_id}: aparece más de una vez en el archivo; se usó el último bloque" if es
         else f"{element_id}: appears more than once in the file; the last block was used")
        for element_id in repeated
    ]
    cache: dict[str, list[str] | None] = {}
    recorded: list[str] = []
    unchanged: list[str] = []
    skipped: list[str] = []
    flagged: list[str] = []
    rejected: dict[str, list[str]] = {}
    now = _now()
    open_gaps, harvest_entries = change_flag_context(project_id, change_id)
    for element_id, raw in blocks.items():
        if not str(raw.get("treatment", "")).strip():
            skipped.append(element_id)
            continue
        element = elements.get(element_id)
        if element is None:
            rejected[element_id] = [_msg("unknown_element", language, id=element_id, cid=change_id)]
            continue
        element_body = _element_text_cached(base, element, cache)
        item, errors = validate_proposal(
            element, element_body, raw, change.get("border", []) or [], language, ctx,
        )
        if item is None:
            rejected[element_id] = errors
            continue
        item["flags"] = element_flags(
            element_id, element_body or "", item["quote"], item["flags"], open_gaps, harvest_entries,
        )
        previous = items.get(element_id) or {}
        if previous.get("status") == "confirmed" and _same_proposal(previous, item):
            # re-submitted as it was confirmed: it stays confirmed
            unchanged.append(element_id)
            continue
        entry = dict(item)
        entry.update({
            "status": "proposed", "proposed_at": now, "confirmed_at": None,
            "rows": previous.get("rows", []),
            "submitted": submitted,
        })
        items[element_id] = entry
        recorded.append(element_id)
        if item["flags"]:
            flagged.append(element_id)
    for element_id, errors in rejected.items():
        for reason in errors:
            store["rejections"].append({"id": element_id, "reason": reason, "at": now})
    write_json(_proposals_path(base, change_id), store)
    review = write_review(project_id, change_id)
    return {
        "project_id": project_id,
        "change_id": change_id,
        "action": "proposals",
        "recorded": recorded,
        "unchanged": unchanged,
        "skipped": skipped,
        "rejected": rejected,
        "flagged": flagged,
        "warnings": warnings,
        "submitted": submitted,
        "review_path": str(review),
    }


def _agent_flags(item: dict) -> list[tuple[str, str]]:
    return [(str(f.get("kind", "")), str(f.get("note", ""))) for f in item.get("flags", []) or [] if f.get("origin") == "agent"]


def _same_proposal(stored: dict, item: dict) -> bool:
    """The normalized proposal says exactly what the stored one says (statements, deltas, surfaces, flag, text…)."""
    keys = ("element_sha", "treatment", "quote", "section", "brief_section", "text", "reason")
    if any(stored.get(key) != item.get(key) for key in keys):
        return False
    statement_keys = ("text", "delta", "surfaces", "affects")
    mine = [{k: s.get(k) or ([] if k in ("surfaces", "affects") else "") for k in statement_keys} for s in stored.get("statements") or []]
    theirs = [{k: s.get(k) or ([] if k in ("surfaces", "affects") else "") for k in statement_keys} for s in item.get("statements") or []]
    return mine == theirs and _agent_flags(stored) == _agent_flags(item)


def extraction_orphans(project_id: str, change_id: str, elements: list[dict]) -> list[dict]:
    """The elements no longer in the inventory whose EARS rows still stand: [{id, rows}], in row order."""
    present = {str(e.get("id")) for e in elements}
    orphans: dict[str, list[str]] = {}
    for row in load_change_ears(project_id, change_id):
        found = _EXT_SOURCE.match(str(row.get("source", "")))
        if found and found.group(1) not in present:
            orphans.setdefault(found.group(1), []).append(row["id"])
    return [{"id": element_id, "rows": rows} for element_id, rows in orphans.items()]


def write_review(project_id: str, change_id: str) -> Path:
    base = workspace_path(project_id)
    change = get_change(project_id, change_id)
    es = change_language(project_id, change) == "es"
    inventory = load_inventory(base, change_id) or {}
    items = load_proposals(base, change_id)["items"]
    words = (
        {"pending": "pendiente", "proposed": "propuesta", "confirmed": "confirmada", "stale": "vieja"} if es
        else {"pending": "pending", "proposed": "proposed", "confirmed": "confirmed", "stale": "stale"}
    )
    lines = [f"# Revisión de la extracción — {change_id}" if es else f"# Extraction review — {change_id}", ""]
    groups: dict[str, dict[str, Any]] = {}
    for element in inventory.get("elements", []):
        group = groups.setdefault(element["section_slug"], {"heading": element["section"], "elements": []})
        group["elements"].append(element)
    flagged: list[tuple[str, dict]] = []
    for slug, group in groups.items():
        lines.append(f"## {group['heading']} (`--confirm {slug}`)")
        for element in group["elements"]:
            item = items.get(element["id"])
            if item is None:
                state, treatment, quote = words["pending"], "—", ""
            else:
                stale = item.get("element_sha") != element.get("sha")
                state = words["stale"] if stale else words.get(str(item.get("status")), str(item.get("status")))
                treatment, quote = str(item.get("treatment", "")), str(item.get("quote", ""))
                for flag in item.get("flags", []) or []:
                    flagged.append((element["id"], flag))
            tail = f" — «{quote}»" if quote else ""
            lines.append(f"- {element['id']} — {treatment} — {state}{tail}")
        lines.append("")
    lines.append(
        "## Marcadas (se confirman una por una con --confirm-item)" if es
        else "## Flagged (confirmed one by one with --confirm-item)"
    )
    for element_id, flag in flagged:
        note = f" — {flag.get('note')}" if flag.get("note") else ""
        lines.append(f"- {element_id} — {flag.get('origin')}: {flag.get('kind')}{note}")
    lines.append("")
    orphans = extraction_orphans(project_id, change_id, inventory.get("elements", []))
    if orphans:
        lines.append(
            "## Huérfanas (ya no están en el pedido; se sacan con --reject-item ID --reason TEXTO)" if es
            else "## Orphans (no longer in the request; take them out with --reject-item ID --reason TEXT)"
        )
        for orphan in orphans:
            lines.append(f"- {orphan['id']} — {', '.join(orphan['rows'])}")
        lines.append("")
    path = extraction_dir(base, change_id) / "review.md"
    write_text(path, "\n".join(lines))
    return path
