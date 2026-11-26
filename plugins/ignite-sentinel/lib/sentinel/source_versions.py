"""IMP-400: does the request cite another version of a source that is loaded?

The request (`pedido`) of a change names the documents it was written on, sometimes with a
sha. When a loaded source (baseline, previous plan, new design) has the same name or the
same family of names (`sad-compras-v3.md` vs `sad-compras-v2.md`) but another content, the
request may rest on a version nobody loaded: a blocking GAP-VER-* asks which one governs.
A document that matches no loaded source is only reported (`not_loaded`): it may simply
not have been delivered, and Sentinel never opens a gap for what it cannot compare.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

from .core.hashing import content_sha256
from .source_registry import SOURCE_ROLES, row_role

NAME_RE = re.compile(r"(?<![\w.-])([\w.-]+\.(?:md|txt|html|htm|docx|pdf|xlsx|pptx))(?!\w)", re.I)
SHA_RE = re.compile(r"\bsha(?:-?256)?\s*[:=]?\s*`?([0-9a-f]{7,64})`?", re.I)
_EXT_RE = re.compile(r"\.(?:md|txt|html|htm|docx|pdf|xlsx|pptx)$", re.I)
_DATE_RE = re.compile(r"\d{4}[-_]?\d{2}[-_]?\d{2}")
_VERSION_TOKEN_RE = re.compile(r"v\d+(?:[._]\d+)*|r\d+|rev\d*|final|draft|borrador")
COMPARED_ROLES = tuple(role for role in SOURCE_ROLES if role != "pedido")


def cited_references(text: str) -> list[dict[str, Any]]:
    """Names and shas the text cites; a sha on the line of a name belongs to that name."""
    found: list[dict[str, Any]] = []
    for number, line in enumerate(text.splitlines(), start=1):
        shas = [m.group(1).lower() for m in SHA_RE.finditer(line)]
        names = [m.group(1) for m in NAME_RE.finditer(line)]
        if names:
            for index, name in enumerate(names):
                found.append({"name": name, "sha": shas[index] if index < len(shas) else None, "line": number})
        else:
            found.extend({"name": None, "sha": sha, "line": number} for sha in shas)
    return found


def version_key(name: str) -> str:
    """The name without its extension and its version marks: the family a document belongs to."""
    text = _DATE_RE.sub(" ", _EXT_RE.sub("", name.strip().lower()))
    parts = [p for p in re.split(r"[-_ ]+", text) if p and not _VERSION_TOKEN_RE.fullmatch(p)]
    cleaned = [re.sub(r"\.+", "-", p).strip("-") for p in parts]
    return "-".join(p for p in cleaned if p)


def version_marks(name: str) -> tuple[str, ...]:
    """The version marks of a name (dates and tokens like v3, rev2, final), in order."""
    text = _EXT_RE.sub("", name.strip().lower())
    dates = tuple(re.sub(r"[-_]", "", d) for d in _DATE_RE.findall(text))
    tokens = tuple(p for p in re.split(r"[-_ ]+", _DATE_RE.sub(" ", text)) if p and _VERSION_TOKEN_RE.fullmatch(p))
    return dates + tuple(t.replace("_", ".") for t in tokens)


def same_document(cited: str, loaded: str) -> bool:
    """Same family and the same version marks: one document in another format or spacing."""
    key = version_key(cited)
    return bool(key) and key == version_key(loaded) and version_marks(cited) == version_marks(loaded)


def _row_hashes(row: dict[str, Any]) -> set[str]:
    """The row's hash plus the raw and line-ending-aware sha256 of its original file and copies."""
    found = {str(row.get("hash") or "")} - {""}
    for candidate in [*(row.get("paths") or []), *(row.get("copies") or [])]:
        path = Path(str(candidate))
        if not path.is_absolute():
            path = Path.cwd() / path
        try:
            data = path.read_bytes()
        except OSError:
            continue
        found.add(hashlib.sha256(data).hexdigest())
        found.add(content_sha256(data))
    return found


def _sha_matches(row: dict[str, Any], sha: str) -> bool:
    return any(digest.startswith(sha) for digest in _row_hashes(row))


def _basenames(row: dict[str, Any]) -> set[str]:
    return {Path(str(p)).name.lower() for p in [*(row.get("paths") or []), *(row.get("copies") or [])]}


def _read_row_text(row: dict[str, Any]) -> str:
    for candidate in [*(row.get("copies") or []), *(row.get("paths") or [])]:
        found = Path(str(candidate))
        if not found.is_absolute():
            found = Path.cwd() / found
        if found.is_file():
            try:
                return found.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
    return ""


def _gap(change_id: str, language: str, cited: str, sha: str | None, loaded: str, source_id: str,
         role: str = "linea_de_base", own_name: str | None = None) -> dict[str, str]:
    es = language == "es"
    # The cited name lower-cased: SAD-v3.md and sad-v3.md in one request are one question.
    digest = hashlib.sha256(f"{change_id}|{cited.lower() if cited else sha}".encode("utf-8")).hexdigest()[:6].upper()
    shown = f"`{cited}`" if cited else f"sha {sha}"
    sha_part = f" (sha {sha})" if sha and cited else ""
    if es:
        description = (f"El pedido cita {shown}{sha_part} y la fuente cargada es `{loaded}` ({source_id}). "
                       "¿Sobre qué versión se escribió el pedido?")
        question = ("¿Sobre qué versión se escribió el pedido? Opciones: "
                    "(A) rige la cargada (la cita del pedido está desactualizada); "
                    f"(B) cargar la versión citada (/sources … --load … --role {role}); "
                    "(C) el pedido se escribió sobre otra versión: revisar lo que dependa de ella.")
        if own_name:
            description += f" El nombre citado es de la misma familia que el propio pedido (`{own_name}`)."
            question += f" (D) es una versión anterior del propio pedido: no se compara con `{loaded}`."
    else:
        description = (f"The request cites {shown}{sha_part} and the loaded source is `{loaded}` ({source_id}). "
                       "Which version was the request written on?")
        question = ("Which version was the request written on? Options: "
                    "(A) the loaded one governs (the request's citation is out of date); "
                    f"(B) load the cited version (/sources … --load … --role {role}); "
                    "(C) the request was written on another version: review whatever depends on it.")
        if own_name:
            description += f" The cited name belongs to the same family as the request itself (`{own_name}`)."
            question += f" (D) it is an earlier version of the request itself: it is not compared with `{loaded}`."
    return {"id": f"GAP-VER-{digest}", "lens": "technical", "severity": "high", "status": "OPEN", "kind": "client",
            "description": description, "question": question,
            "evidence_mention": cited or str(sha), "origin": "sources", "resolution_note": ""}


def check_change_versions(project_id: str, change_id: str, write: bool = True) -> dict[str, Any]:
    """Compare what the change's request cites against the current non-request sources.

    `write=False` only reports (no gap is opened): `/status` reads, it never writes.
    """
    from .changes import change_gaps_path, change_language, list_changes
    from .core.io import write_text
    from .gaps import count_gaps, parse_gap_rows, render_gaps
    from .sources import load_source_manifest
    from .workspace import update_state, workspace_path

    result: dict[str, Any] = {"matched": [], "mismatched": [], "not_loaded": [], "opened": [], "self_version": []}
    entry = list_changes(project_id).get(change_id)
    if not entry:
        return result
    rows = {str(r.get("id")): r for r in load_source_manifest(project_id).get("registry", [])}
    pedidos = [rows[i] for i in entry.get("sources") or [] if i in rows and row_role(rows[i]) == "pedido"]
    # H27 inc 7a: a derived copy adds provenance to its origin; it is never a version of anything
    loaded = [r for r in rows.values() if r.get("validity", "current") == "current" and row_role(r) in COMPARED_ROLES
              and not r.get("derived_from")]
    own = [(n, p) for p in pedidos for n in _basenames(p)]
    own_names = {n for n, _ in own}
    own_families = {version_key(n) for n in own_names} - {""}
    own_label = {id(p): (Path(str(p["paths"][0])).name if p.get("paths") else str(p["id"])) for p in pedidos}
    seen: set[tuple[str, str]] = set()
    new_gaps: list[dict[str, str]] = []
    language = change_language(project_id, entry)
    for pedido in pedidos:
        for ref in cited_references(_read_row_text(pedido)):
            cited, sha = ref["name"], ref["sha"]
            key = ((cited or "").lower(), sha or "")
            if key in seen:
                continue
            seen.add(key)
            own_hit = next((p for n, p in own if cited and (cited.lower() == n or same_document(cited, n))), None)
            if own_hit is not None:  # the request names itself: nothing to compare
                result["matched"].append({"cited": cited, "sha": sha, "line": ref["line"], "source_id": own_hit["id"]})
                continue
            own_family = bool(cited) and version_key(cited) in own_families
            by_name = next((r for r in loaded if cited and cited.lower() in _basenames(r)), None)
            if cited and by_name is None:  # the same document in another format or spacing counts as the name
                by_name = next((r for r in loaded if any(same_document(cited, n) for n in _basenames(r))), None)
            by_family = None
            if cited and by_name is None and version_key(cited):
                by_family = next((r for r in loaded if any(version_key(n) == version_key(cited) for n in _basenames(r))), None)
            report = {"cited": cited, "sha": sha, "line": ref["line"]}
            row = by_name or by_family
            mine = next((p for n, p in own if version_key(n) == version_key(cited)), None) if own_family else None
            if own_family and row is None:  # an earlier version of the request itself
                result["self_version"].append({"cited": cited, "line": ref["line"], "pedido": own_label[id(mine)]})
                continue
            own_name = own_label[id(mine)] if mine is not None and by_name is None else None
            if cited is None:  # a bare sha: it must prefix some loaded hash
                hit = next((r for r in loaded if sha and _sha_matches(r, sha)), None)
                result["matched" if hit else "not_loaded"].append({**report, "source_id": hit["id"]} if hit else report)
            elif row is None:
                result["not_loaded"].append(report)
            elif sha is None and by_name is not None or (sha and _sha_matches(row, sha)):
                result["matched"].append({**report, "source_id": row["id"]})  # the sha counts only on the row the name points to
            else:
                result["mismatched"].append({**report, "source_id": row["id"], "reason": "sha" if by_name is not None else "version"})
                loaded_name = Path(str(row["paths"][0])).name if row.get("paths") else str(row["id"])
                new_gaps.append(_gap(change_id, language, cited, sha, loaded_name, str(row["id"]), row_role(row) or "linea_de_base",
                                     own_name=own_name))
    if new_gaps and write:
        path = change_gaps_path(workspace_path(project_id), change_id)
        existing = [g for g in parse_gap_rows(path.read_text(encoding="utf-8")) if g.get("id") != "NONE"] if path.exists() else []
        known = {g["id"] for g in existing}
        added = []
        for gap in new_gaps:  # exact id only: two stale documents are two questions, never folded by topic
            if gap["id"] not in known:
                known.add(gap["id"])
                added.append(gap)
        result["opened"] = [g["id"] for g in added]
        if added:
            rows = [*existing, *added]
            write_text(path, render_gaps(project_id, rows, change_id, language, path.with_name("gap_elicitation.json")))
            updated = {k: dict(v) for k, v in list_changes(project_id).items()}
            updated[change_id]["gap_counts"] = count_gaps(rows)
            update_state(project_id, changes=updated)
    return result


def check_versions_for(project_id: str, change_id: str | None) -> list[str]:
    """Run the check on one change, or on every change; returns the gap ids it opened."""
    from .changes import list_changes

    targets = [change_id] if change_id else list(list_changes(project_id))
    opened: list[str] = []
    for target in targets:
        opened.extend(check_change_versions(project_id, target)["opened"])
    return opened
