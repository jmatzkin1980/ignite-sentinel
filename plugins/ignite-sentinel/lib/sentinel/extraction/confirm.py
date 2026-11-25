"""IMP-402 task 4: confirmation of proposals and materialization of what was confirmed.

A proposal becomes real only here, by the BA's command: a requirement turns into EARS rows
of the change (each statement with its own Delta, Surface and Affects), a section is kept in
`extraction/sections.json` for the brief, a discard only changes state. A flagged element is
held in bulk and confirmed one by one.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from ..change_requirements import (
    load_change_ears, reconcile_extraction_ears, reconcile_project_extraction_ears,
)
from ..changes import change_language, resolve_scope
from ..core.io import write_json
from ..core.paths import workspace_path
from ..errors import GateRefusal, InputError
from . import extraction_dir
from .flags import refresh_flags
from .inventory import (
    _fold, _read_text, _split_lines, element_text, inventory_state, load_inventory, section_slug, span_text,
)
from .lines import format_ranges
from .proposals import _msg, _now, _proposals_path, load_proposals, validate_proposal, write_review

_EXT_SOURCE = re.compile(r"`EXT:([^`]+)`")


def sections_path(base: Path, change_id: str) -> Path:
    return extraction_dir(base, change_id) / "sections.json"


def _context(
    project_id: str, change_id: str, allow_stale: bool = False,
) -> tuple[Path, dict, dict[str, dict], dict, str]:
    change = resolve_scope(project_id, change_id).entry
    language = change_language(project_id, change)
    state = inventory_state(project_id, change_id)
    if state == "missing" or (state == "stale" and not allow_stale):
        # a stale inventory may point at lines that moved: confirming against it would cite the wrong text
        if language == "es":
            message = f"Corré /extract {project_id} --change {change_id} antes de confirmar: el inventario " + (
                "falta" if state == "missing" else "quedó viejo")
        else:
            message = f"Run /extract {project_id} --change {change_id} before confirming: the inventory is " + (
                "missing" if state == "missing" else "out of date")
        raise GateRefusal(message, next_step=f"/extract {project_id} --change {change_id}")
    base = workspace_path(project_id)
    inventory = load_inventory(base, change_id) or {}
    return base, inventory, {e["id"]: e for e in inventory.get("elements", [])}, change, language


def _empty_result(action: str) -> dict[str, Any]:
    return {
        "action": action, "confirmed": [], "held": [], "invalid": {},
        "rows_added": [], "rows_updated": [], "rows_superseded": [],
    }


def _no_pending(element_id: str, language: str) -> InputError:
    return InputError(
        f"{element_id} no tiene una propuesta pendiente de confirmar" if language == "es"
        else f"{element_id} has no pending proposal to confirm"
    )


def _raw(item: dict) -> dict:
    """The stored item as the block it came from, so `validate_proposal` can check it again."""
    return {
        "treatment": item.get("treatment", ""),
        "type": item.get("type") or "",
        "quote": item.get("quote", ""),
        "statements": [
            {
                "text": s.get("text", ""), "delta": s.get("delta") or "",
                "surface": "; ".join(s.get("surfaces") or []), "affects": ", ".join(s.get("affects") or []),
            }
            for s in item.get("statements", []) or []
        ],
        "section": item.get("section") or "",
        "summary": item.get("summary") or "",
        "lines": format_ranges(item.get("lines") or []),
        "reading": item.get("reading") or "",
        "reason": item.get("reason") or "",
        "flag": "", "flag_note": "", "errors": [],
    }


def _source_lines(base: Path, element: dict) -> list[str]:
    text = _read_text(base, str(element.get("path", "")))
    return [] if text is None else _split_lines(text)


def _element_rows(project_id: str, change_id: str, element_id: str) -> list[str]:
    rows = []
    for row in load_change_ears(project_id, change_id):
        found = _EXT_SOURCE.match(str(row.get("source", "")))
        if found and found.group(1) == element_id:
            rows.append(row["id"])
    return rows


def _reconcile(project_id: str, change_id: str | None, element_id: str, statements: list[dict], cite: str,
               language: str, a_confirmar: bool = False) -> dict[str, list[str]]:
    """The rows of an element, in the change's table or, with no change, in the project's 4-column table."""
    if change_id is None:
        rows = reconcile_project_extraction_ears(project_id, element_id, statements, cite, a_confirmar)
        return {"added": rows["added"], "delta_updated": [], "superseded": rows["retired"]}
    return reconcile_extraction_ears(project_id, change_id, element_id, statements, cite, language, a_confirmar=a_confirmar)


def _merge(result: dict, rows: dict[str, list[str]]) -> None:
    result["rows_added"].extend(rows.get("added", []))
    result["rows_updated"].extend(rows.get("delta_updated", []))
    result["rows_superseded"].extend(rows.get("superseded", []))


def _try_confirm(
    project_id: str, change_id: str, element: dict, item: dict, border: list[dict], language: str,
    result: dict, force: bool, delegated: bool = False, note: str = "", reason: str = "",
) -> None:
    """Confirm one proposed item, or leave it held (flagged) or invalid (no longer valid)."""
    element_id = element["id"]
    base = workspace_path(project_id)
    flags = refresh_flags(project_id, change_id, element_id, item)
    item["flags"] = flags
    if flags and not force:
        result["held"].append(element_id)
        return
    body = element_text(base, element)
    source_lines = _source_lines(base, element)
    ctx = {"pid": project_id, "cid": change_id}
    if item.get("element_sha") != element.get("sha"):
        normalized, errors = None, [_msg("stale_element", language, id=element_id, **ctx)]
    else:
        normalized, errors = validate_proposal(element, body, _raw(item), border, language, ctx, source_lines,
                                              project=change_id is None)
    speculative = any(f.get("kind") == "a_confirmar" for f in flags)
    if normalized is None:
        result["invalid"][element_id] = errors or [_msg("stale_element", language, id=element_id, **ctx)]
        return
    treatment = normalized["treatment"]
    if treatment == "requisito":
        statements = normalized["statements"]
        item["statements"] = statements
        cite = f"{element['source_id']}:{element['line']}"
        _merge(result, _reconcile(project_id, change_id, element_id, statements, cite, language, speculative))
        item["rows"] = _element_rows(project_id, change_id, element_id)
    else:
        if treatment == "seccion":
            item["section"], item["brief_section"] = normalized["section"], normalized["brief_section"]
        if item.get("rows"):
            # corrected from requirement to section or discard: its rows no longer stand
            _merge(result, _reconcile(project_id, change_id, element_id, [], "", language))
            item["rows"] = []
    item["status"] = "confirmed"
    item["confirmed_at"] = _now()
    if speculative:  # IMP-412: the request left it to confirm; the BA's reason stays with the item
        item["a_confirmar"], item["a_confirmar_reason"] = True, str(reason or "").strip()
    else:
        item.pop("a_confirmar", None)
        item.pop("a_confirmar_reason", None)
    if delegated:  # IMP-412: confirmed on behalf of the BA, kept apart and listed to review
        item["confirmed_by"], item["delegated_note"], item["delegated_at"] = "delegated", note, item["confirmed_at"]
        result.setdefault("delegated", []).append(element_id)
    else:
        for key in ("confirmed_by", "delegated_note", "delegated_at"):
            item.pop(key, None)
    item["flags"] = [f for f in item.get("flags", []) or [] if f.get("origin") != "verify"]  # corrected: the mark is done
    result["confirmed"].append(element_id)


def write_sections(project_id: str, change_id: str) -> Path:
    """`extraction/sections.json` from the confirmed section items, in inventory order."""
    base = workspace_path(project_id)
    inventory = load_inventory(base, change_id) or {}
    items = load_proposals(base, change_id)["items"]
    entries = []
    for element in inventory.get("elements", []):
        item = items.get(element["id"])
        if not item or item.get("status") != "confirmed" or item.get("treatment") != "seccion":
            continue
        source = _source_lines(base, element)
        content = span_text(source, element.get("spans", []), element.get("cspan"))
        entries.append({
            "element": element["id"], "section": item.get("section"), "brief_section": item.get("brief_section"),
            "content": content, "lines": item.get("lines") or [], "summary": item.get("summary"),
            "quote": item.get("quote"), "path": element.get("path"),
            "line": element.get("line"), "source_id": element.get("source_id"),
        })
    path = sections_path(base, change_id)
    write_json(path, {"schema_version": 1, "change_id": change_id, "entries": entries})
    return path


def _finish(project_id: str, change_id: str, base: Path, store: dict, result: dict) -> dict:
    write_json(_proposals_path(base, change_id), store)
    if sections_path(base, change_id).exists() or any(
        i.get("status") == "confirmed" and i.get("treatment") == "seccion" for i in store["items"].values()
    ):
        write_sections(project_id, change_id)
    result["project_id"], result["change_id"] = project_id, change_id
    result["review_path"] = str(write_review(project_id, change_id))
    return result


def _select(inventory: dict, section: str, language: str) -> list[dict]:
    elements = inventory.get("elements", [])
    wanted = str(section or "").strip()
    if wanted.lower() == "all":
        return list(elements)
    headings = {e["section_slug"]: e["section"] for e in elements}
    folded = _fold(wanted)
    slug = next(
        (s for s, heading in headings.items() if s == wanted or s == folded or _fold(heading) == folded or s == section_slug(wanted)),
        None,
    )
    if slug is None:
        listing = ", ".join(headings) or "—"
        raise InputError(
            f"Sección desconocida «{section}». Secciones del inventario: {listing} (o all)" if language == "es"
            else f"Unknown section «{section}». Inventory sections: {listing} (or all)"
        )
    return [e for e in elements if e["section_slug"] == slug]


def confirm_proposals(project_id: str, change_id: str, section: str, delegated: bool = False, note: str = "") -> dict:
    """Confirm every proposed item of a section (or `all`); flagged ones are held, invalid ones reported."""
    base, inventory, _, change, language = _context(project_id, change_id)
    selected = _select(inventory, section, language)
    store = load_proposals(base, change_id)
    result = _empty_result("confirm")
    border = change.get("border", []) or []
    for element in selected:
        item = store["items"].get(element["id"])
        if item and item.get("status") == "proposed":
            _try_confirm(project_id, change_id, element, item, border, language, result, force=False,
                         delegated=delegated, note=str(note or "").strip())
    return _finish(project_id, change_id, base, store, result)


def confirm_item(
    project_id: str, change_id: str, element_id: str, delegated: bool = False, note: str = "", reason: str = "",
) -> dict:
    """Confirm one proposed item, flagged or not; the BA confirming what was delegated ratifies it."""
    base, _, elements, change, language = _context(project_id, change_id)
    store = load_proposals(base, change_id)
    item = store["items"].get(element_id)
    element = elements.get(element_id)
    if (not delegated and item is not None and element is not None
            and item.get("status") == "confirmed" and item.get("confirmed_by") == "delegated"):
        for key in ("confirmed_by", "delegated_note", "delegated_at"):
            item.pop(key, None)
        ratified = _empty_result("confirm")
        ratified["ratified"] = [element_id]
        return _finish(project_id, change_id, base, store, ratified)
    if item is None or element is None or item.get("status") != "proposed":
        raise _no_pending(element_id, language)
    for flag in item.get("flags", []) or []:
        if flag.get("origin") == "verify":
            note = str(flag.get("note", "")).strip()
            raise InputError(
                f"{element_id}: la verificación dijo que difiere ({note}) y la propuesta no cambió: corregila y proponela "
                "de nuevo" if language == "es"
                else f"{element_id}: the verification said it differs ({note}) and the proposal has not changed: correct "
                "it and propose it again"
            )
        if flag.get("origin") != "coverage":
            continue
        if flag.get("kind") == "lineas_sin_cubrir":
            ranges = format_ranges(item.get("missing_lines") or []) or str(flag.get("note", "")).split(" ", 1)[-1]
            raise InputError(
                f"{element_id}: la propuesta no cubre las líneas {ranges} del elemento: proponelo de nuevo con Líneas que "
                "cubran todo lo que tiene contenido" if language == "es"
                else f"{element_id}: the proposal does not cover lines {ranges} of the element: propose it again with "
                "Lines covering everything with content"
            )
        if flag.get("kind") == "lectura_parcial":
            raise InputError(
                f"{element_id}: la propuesta declara Lectura: parcial: leé el elemento completo y proponelo de nuevo"
                if language == "es"
                else f"{element_id}: the proposal declares Reading: partial: read the whole element and propose it again"
            )
    for flag in refresh_flags(project_id, change_id, element_id, item):
        if flag.get("kind") == "a_confirmar" and not str(reason or "").strip():
            term = str(flag.get("note", "")).strip()
            raise InputError(
                f"{element_id}: el pedido lo marca como a confirmar («{term}»): confirmalo con --confirm-item "
                f"{element_id} --reason \"…\"" if language == "es"
                else f"{element_id}: the request marks it as to be confirmed («{term}»): confirm it with "
                f"--confirm-item {element_id} --reason \"…\""
            )
    result = _empty_result("confirm")
    _try_confirm(project_id, change_id, element, item, change.get("border", []) or [], language, result, force=True,
                 delegated=delegated, note=str(note or "").strip(), reason=str(reason or "").strip())
    return _finish(project_id, change_id, base, store, result)


def reject_item(project_id: str, change_id: str, element_id: str, reason: str) -> dict:
    """Take an item out (back to pending), keep the reason, and supersede the rows it had.

    It also takes out an orphan: an element no longer in the inventory whose rows still stand."""
    base, _, _, _, language = _context(project_id, change_id, allow_stale=True)
    if not str(reason or "").strip():
        raise InputError(
            "Rechazar necesita un motivo (--reason)" if language == "es" else "Rejecting needs a reason (--reason)"
        )
    store = load_proposals(base, change_id)
    item = store["items"].get(element_id)
    standing = _element_rows(project_id, change_id, element_id)
    if item is None and not standing:
        raise _no_pending(element_id, language)
    result = _empty_result("reject")
    if standing or (item or {}).get("rows"):
        _merge(result, _reconcile(project_id, change_id, element_id, [], "", language))
    store["items"].pop(element_id, None)
    store["rejections"].append({"id": element_id, "reason": str(reason).strip(), "at": _now()})
    return _finish(project_id, change_id, base, store, result)
