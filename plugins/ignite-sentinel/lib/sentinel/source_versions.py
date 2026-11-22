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


def _gap(change_id: str, language: str, cited: str, sha: str | None, loaded: str, source_id: str) -> dict[str, str]:
    es = language == "es"
    digest = hashlib.sha256(f"{change_id}|{cited if cited else sha}".encode("utf-8")).hexdigest()[:6].upper()
    shown = f"`{cited}`" if cited else f"sha {sha}"
    sha_part = f" (sha {sha})" if sha and cited else ""
    if es:
        description = (f"El pedido cita {shown}{sha_part} y la fuente cargada es `{loaded}` ({source_id}). "
                       "¿Sobre qué versión se escribió el pedido?")
        question = ("¿Sobre qué versión se escribió el pedido? Opciones: "
                    "(A) rige la cargada (la cita del pedido está desactualizada); "
                    "(B) cargar la versión citada (/sources … --load … --role linea_de_base); "
                    "(C) el pedido se escribió sobre otra versión: revisar lo que dependa de ella.")
    else:
        description = (f"The request cites {shown}{sha_part} and the loaded source is `{loaded}` ({source_id}). "
                       "Which version was the request written on?")
        question = ("Which version was the request written on? Options: "
                    "(A) the loaded one governs (the request's citation is out of date); "
                    "(B) load the cited version (/sources … --load … --role linea_de_base); "
                    "(C) the request was written on another version: review whatever depends on it.")
    return {"id": f"GAP-VER-{digest}", "lens": "technical", "severity": "high", "status": "OPEN", "kind": "client",
            "description": description, "question": question,
            "evidence_mention": cited or str(sha), "origin": "sources", "resolution_note": ""}


def check_change_versions(project_id: str, change_id: str) -> dict[str, Any]:
    """Compare what the change's request cites against the current non-request sources."""
    from .changes import change_gaps_path, change_language, list_changes
    from .core.io import write_text
    from .gaps import count_gaps, merge_gaps_by_topic, parse_gap_rows, render_gaps
    from .sources import load_source_manifest
    from .workspace import update_state, workspace_path

    result: dict[str, Any] = {"matched": [], "mismatched": [], "not_loaded": [], "opened": []}
    entry = list_changes(project_id).get(change_id)
    if not entry:
        return result
    rows = {str(r.get("id")): r for r in load_source_manifest(project_id).get("registry", [])}
    pedidos = [rows[i] for i in entry.get("sources") or [] if i in rows and row_role(rows[i]) == "pedido"]
    loaded = [r for r in rows.values() if r.get("validity", "current") == "current" and row_role(r) in COMPARED_ROLES]
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
            by_sha = next((r for r in loaded if sha and str(r.get("hash", "")).startswith(sha)), None)
            by_name = next((r for r in loaded if cited and cited.lower() in _basenames(r)), None)
            by_family = None
            if cited and by_name is None and version_key(cited):
                by_family = next((r for r in loaded if any(version_key(n) == version_key(cited) for n in _basenames(r))), None)
            report = {"cited": cited, "sha": sha, "line": ref["line"]}
            if by_sha is not None or (by_name is not None and not sha):
                result["matched"].append({**report, "source_id": (by_sha or by_name)["id"]})
            elif by_name is not None or by_family is not None:
                row = by_name or by_family
                reason = "sha" if by_name is not None else "version"
                result["mismatched"].append({**report, "source_id": row["id"], "reason": reason})
                loaded_name = Path(str(row["paths"][0])).name if row.get("paths") else str(row["id"])
                new_gaps.append(_gap(change_id, language, cited or "", sha, loaded_name, str(row["id"])))
            else:
                result["not_loaded"].append(report)
    if new_gaps:
        path = change_gaps_path(workspace_path(project_id), change_id)
        existing = [g for g in parse_gap_rows(path.read_text(encoding="utf-8")) if g.get("id") != "NONE"] if path.exists() else []
        merged = merge_gaps_by_topic(existing, new_gaps)
        result["opened"] = [g["id"] for g in merged["added"]]
        if merged["added"]:
            write_text(path, render_gaps(project_id, merged["gaps"], change_id, language, path.with_name("gap_elicitation.json")))
            updated = {k: dict(v) for k, v in list_changes(project_id).items()}
            updated[change_id]["gap_counts"] = count_gaps(merged["gaps"])
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
