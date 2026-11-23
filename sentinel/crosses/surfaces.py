"""IMP-404 task 4: the harvest as the baseline cross, and the new-surface candidates its NOT FOUND entries propose."""
from __future__ import annotations

import hashlib
from typing import Any

from ..change_requirements import _fold_name, load_change_ears
from ..changes import _BORDER_TYPE_ALIASES, change_language, get_change, list_changes, regenerate_change_gaps
from ..core.time import utc_now
from ..errors import GateRefusal, InputError
from ..harvest import load_harvest
from ..lens_registry import SURFACE_TYPES
from ..workspace import update_state, workspace_path
from .state import write_cross_report

NAME_MAX = 80


def candidate_id(entry: dict) -> str:
    digest = hashlib.sha256(f"{entry['ref']}|{entry['text']}".encode("utf-8")).hexdigest()[:6].upper()
    return f"NEW-{digest}"


def new_surface_candidates(project_id: str, change_id: str) -> list[dict]:
    change = get_change(project_id, change_id)
    harvests = [str(i) for i in change.get("harvests") or []]
    decided = change.get("new_surfaces") or {}
    out: list[dict] = []
    for entry in load_harvest(workspace_path(project_id)).get("entries", []):
        if not isinstance(entry, dict) or entry.get("kind") != "not_found" or str(entry.get("source_id")) not in harvests:
            continue
        cid = candidate_id(entry)
        saved = decided.get(cid) if isinstance(decided.get(cid), dict) else {}
        out.append({
            "id": cid, "text": entry["text"], "ref": entry["ref"], "source_id": str(entry["source_id"]),
            "line": entry.get("line"), "block": entry.get("block", ""),
            "decision": saved.get("decision"), "type": saved.get("type"), "name": saved.get("name"),
            "reason": saved.get("reason"),
        })
    out.sort(key=lambda c: (c["block"], int(c["line"] or 0)))
    return out


def _msg(language: str, es: str, en: str) -> str:
    return es if language == "es" else en


def _find(project_id: str, change_id: str, candidate: str, language: str) -> dict:
    candidates = new_surface_candidates(project_id, change_id)
    for item in candidates:
        if item["id"] == candidate:
            return item
    known = ", ".join(c["id"] for c in candidates) or "-"
    raise InputError(
        _msg(language, f"Candidata desconocida «{candidate}»: {known}", f"Unknown candidate «{candidate}»: {known}"),
        next_step=_msg(language, "Elegí una de las candidatas de crosses.md.", "Pick one of the candidates in crosses.md."),
    )


def _save(project_id: str, change_id: str, border: list[dict], candidate: str, decision: dict) -> None:
    changes = {key: dict(value) for key, value in list_changes(project_id).items()}
    entry = changes[change_id]
    entry["border"] = border
    surfaces = dict(entry.get("new_surfaces") or {})
    surfaces[candidate] = decision
    entry["new_surfaces"] = surfaces
    update_state(project_id, changes=changes)


def accept_new_surface(project_id: str, change_id: str, candidate: str, surface_type: str, name: str) -> dict[str, Any]:
    change = get_change(project_id, change_id)
    language = change_language(project_id, change)
    if change.get("round") == "scope":
        raise GateRefusal(
            _msg(language,
                 f"Cerrá primero el borde de {change_id} (GAP-SCOPE): una superficie nueva entra a un borde confirmado",
                 f"Close the border of {change_id} first (GAP-SCOPE): a new surface joins a confirmed border"),
            next_step=f"/gaps {project_id} --change {change_id}",
        )
    found = _find(project_id, change_id, candidate, language)
    if found["decision"] == "accepted":
        raise InputError(_msg(language, f"{candidate} ya está aceptada como «{found['name']}»",
                              f"{candidate} is already accepted as «{found['name']}»"))
    kind = str(surface_type).strip().lower()
    kind = _BORDER_TYPE_ALIASES.get(kind, kind)
    if kind not in SURFACE_TYPES:
        raise InputError(_msg(language, f"Tipo de superficie inválido «{surface_type}»: {', '.join(SURFACE_TYPES)}",
                              f"Invalid surface type «{surface_type}»: {', '.join(SURFACE_TYPES)}"))
    label = str(name).strip()
    problem = None
    if not label:
        problem = _msg(language, "está vacío", "is empty")
    elif ";" in label or "|" in label:
        problem = _msg(language, "no puede llevar `;` ni `|`", "cannot contain `;` or `|`")
    elif len(label) > NAME_MAX:
        problem = _msg(language, f"tiene más de {NAME_MAX} caracteres", f"is longer than {NAME_MAX} characters")
    if problem:
        raise InputError(_msg(language, f"El nombre de la superficie «{label}» {problem}.",
                              f"The surface name «{label}» {problem}."))
    border = [dict(item) for item in change.get("border") or []]
    key = _fold_name(label)
    for item in border:
        if item.get("candidate") == candidate:
            continue
        if key in (_fold_name(item.get("name", "")), _fold_name(item.get("alias", "")) if item.get("alias") else None):
            raise InputError(_msg(language, f"«{label}» ya es una superficie del borde: «{item.get('name')}»",
                                  f"«{label}» is already a border surface: «{item.get('name')}»"))
    surface = {"zone": "nuevo", "type": kind, "name": label,
               "cite": f"harvest {found['source_id']}:{found['line']} ({candidate})",
               "origin": "cross", "candidate": candidate}
    border = [item for item in border if item.get("candidate") != candidate] + [surface]
    _save(project_id, change_id, border, candidate,
          {"decision": "accepted", "type": kind, "name": label, "at": utc_now()})
    regenerate_change_gaps(project_id, change_id)
    write_cross_report(project_id, change_id)
    return {"action": "accept_new", "candidate": candidate, "surface": surface,
            "border": list(get_change(project_id, change_id).get("border") or [])}


def decline_new_surface(project_id: str, change_id: str, candidate: str, reason: str) -> dict[str, Any]:
    change = get_change(project_id, change_id)
    language = change_language(project_id, change)
    found = _find(project_id, change_id, candidate, language)
    text = str(reason or "").strip()
    if not text:
        raise InputError(_msg(language, "El motivo del descarte es obligatorio.", "The reason for declining is required."),
                         next_step=_msg(language, "Decí por qué no es una superficie nueva.", "Say why it is not a new surface."))
    keep = [dict(item) for item in change.get("border") or []]
    if found["decision"] == "accepted":
        label = str(found["name"])
        key = _fold_name(label)
        rows = [str(r.get("id")) for r in load_change_ears(project_id, change_id)
                if key in {_fold_name(s) for s in r.get("surfaces") or []}]
        if rows:
            raise InputError(_msg(language, f"«{label}» ya la usan {', '.join(rows)}: no se saca del borde",
                                  f"«{label}» is already used by {', '.join(rows)}: it stays in the border"))
        keep = [item for item in keep if item.get("candidate") != candidate]
    _save(project_id, change_id, keep, candidate, {"decision": "declined", "reason": text, "at": utc_now()})
    write_cross_report(project_id, change_id)
    return {"action": "decline_new", "candidate": candidate, "reason": text}
