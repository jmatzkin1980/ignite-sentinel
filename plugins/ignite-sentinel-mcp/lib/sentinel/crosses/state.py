"""IMP-404 task 3: where each cross-read of a change stands, its summary, fingerprint and report."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from ..changes import _squash, change_gaps_path, change_language, get_change
from ..core.io import read_json, write_text
from ..gaps import parse_gap_rows
from ..harvest import load_harvest
from ..sources import load_source_manifest
from ..workspace import workspace_path
from . import CROSS_KINDS, cross_path, crosses_dir
from .claims import TAG_NAMES, cross_sources

HARVEST_KINDS = ("fact", "inferred", "not_found", "out_of_code", "divergence")
HARVEST_NAMES = {
    "es": {"fact": "HECHO", "inferred": "INFERIDO", "not_found": "NO ENCONTRADO",
           "out_of_code": "FUERA DEL CÓDIGO", "divergence": "DIVERGENCIA"},
    "en": {"fact": "FACT", "inferred": "INFERRED", "not_found": "NOT FOUND",
           "out_of_code": "OUT OF CODE", "divergence": "DIVERGENCE"},
}
KIND_LABELS = {
    "es": {"linea_de_base": "línea de base", "diseno": "diseño nuevo", "contradicciones": "contradicciones internas"},
    "en": {"linea_de_base": "baseline", "diseno": "new design", "contradicciones": "internal contradictions"},
}
STATE_LABELS = {
    "es": {"done": "hecho", "waived": "descartado", "missing": "falta", "stale": "desactualizado",
           "no_aplica": "no aplica"},
    "en": {"done": "done", "waived": "waived", "missing": "missing", "stale": "stale",
           "no_aplica": "not applicable"},
}


def _empty(state: str) -> dict[str, Any]:
    return {"state": state, "source_id": None, "counts": {}, "gaps": [], "reason": None, "stale_sources": [], "new_sources": [],
            "claims_hash": ""}


def _load(base: Path, change_id: str, kind: str) -> dict | None:
    data = read_json(cross_path(base, change_id, kind), None)
    return data if isinstance(data, dict) else None


def _baseline_state(base: Path, change: dict, record: dict | None) -> dict[str, Any]:
    harvests = [str(i) for i in change.get("harvests") or []]
    if harvests:
        counts = {kind: 0 for kind in HARVEST_KINDS}
        for entry in load_harvest(base).get("entries", []):
            if isinstance(entry, dict) and str(entry.get("source_id")) in harvests and entry.get("kind") in counts:
                counts[entry["kind"]] += 1
        return {"state": "done", "source_ids": harvests, "counts": {k: n for k, n in counts.items() if n}, "reason": None}
    if record and record.get("status") == "waived":
        return {"state": "waived", "source_ids": [], "counts": {}, "reason": str(record.get("reason") or "")}
    waiver = change.get("baseline_waived")
    if waiver:
        return {"state": "waived", "source_ids": [], "counts": {}, "reason": str((waiver or {}).get("reason") or "")}
    return {"state": "missing", "source_ids": [], "counts": {}, "reason": None}


def cross_status(project_id: str, change_id: str) -> dict[str, Any]:
    change = get_change(project_id, change_id)
    base = workspace_path(project_id)
    language = change_language(project_id, change)
    current = {
        str(row.get("id")) for row in load_source_manifest(project_id).get("registry", [])
        if row.get("validity", "current") == "current"
    }
    kinds: dict[str, dict[str, Any]] = {
        "linea_de_base": _baseline_state(base, change, _load(base, change_id, "linea_de_base"))
    }
    sources = cross_sources(project_id, change_id)
    for kind in ("diseno", "contradicciones"):
        record = _load(base, change_id, kind)
        if record is None:
            # no prototype loaded and nothing recorded: there is no design to cross the request with
            kinds[kind] = _empty("no_aplica" if kind == "diseno" and not sources["diseno"] else "missing")
            continue
        basis = record.get("basis") if isinstance(record.get("basis"), dict) else None
        added = [] if basis is None else [
            i for side in ("pedido", "diseno") for i in sources[side] if i not in [str(b) for b in basis.get(side) or []]]
        if record.get("status") == "waived":
            kinds[kind] = {**_empty("stale" if added else "waived"), "reason": str(record.get("reason") or ""),
                           "new_sources": added, "claims_hash": str(record.get("claims_hash") or "")}
        else:
            cited = [str(c.get("source_id")) for claim in record.get("claims", []) for c in claim.get("citations", [])]
            stale = list(dict.fromkeys(i for i in cited if i not in current))
            kinds[kind] = {
                "state": "stale" if stale or added else "done", "source_id": record.get("source_id"),
                "counts": dict(record.get("counts") or {}), "gaps": list(record.get("gaps") or []),
                "reason": None, "stale_sources": stale, "new_sources": added,
                "claims_hash": str(record.get("claims_hash") or ""),
            }
    missing = [kind for kind in CROSS_KINDS if kinds[kind]["state"] in ("missing", "stale")]
    status: dict[str, Any] = {
        "kinds": kinds, "missing": missing, "complete": not missing,
        "design_sources": list(cross_sources(project_id, change_id)["diseno"]),
    }
    status["text"] = cross_summary(status, language)
    return status


def cross_summary(status: dict[str, Any], language: str) -> str:
    lang = "es" if language == "es" else "en"
    parts: list[str] = []
    for kind in CROSS_KINDS:
        info = status["kinds"][kind]
        text = f"{KIND_LABELS[lang][kind]}: {STATE_LABELS[lang][info['state']]}"
        counts = info.get("counts") or {}
        if counts:
            names = HARVEST_NAMES[lang] if kind == "linea_de_base" else TAG_NAMES[lang]
            order = HARVEST_KINDS if kind == "linea_de_base" else tuple(TAG_NAMES[lang])
            text += " (" + ", ".join(f"{names[tag]} {counts[tag]}" for tag in order if counts.get(tag)) + ")"
        elif info["state"] == "waived":
            text += f" ({'motivo' if lang == 'es' else 'reason'}: {info.get('reason') or '-'})"
        parts.append(text)
    return "; ".join(parts)


def crosses_fingerprint(project_id: str, change_id: str) -> str:
    """12 hex of what the cross-reads decided; empty when the change has none (an older change keeps its brief)."""
    change = get_change(project_id, change_id)
    base = workspace_path(project_id)
    surfaces = change.get("new_surfaces") or {}
    has_file = any(cross_path(base, change_id, kind).exists() for kind in CROSS_KINDS)
    if not has_file and not change.get("harvests") and not surfaces:
        return ""
    status = cross_status(project_id, change_id)
    kinds = {}
    for kind in CROSS_KINDS:
        info = status["kinds"][kind]
        kinds[kind] = [info["state"], info["counts"],
                       info["source_ids"] if kind == "linea_de_base" else info.get("claims_hash") or info["source_id"]]
    decisions = {
        str(key): [str(v.get("decision", "")), str(v.get("type", "")), str(v.get("name", "")), str(v.get("reason", ""))]
        for key, v in surfaces.items() if isinstance(v, dict)
    }
    payload = json.dumps({"kinds": kinds, "new_surfaces": decisions}, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]


def _cite_text(cite: dict, lang: str) -> str:
    side = "Pedido" if lang == "es" else "Request"
    if cite["side"] == "diseno":
        side = "Diseño" if lang == "es" else "Design"
    where = f":{cite['line']}" if cite["side"] == "pedido" and cite.get("line") else ""
    opening, closing = ("«", "»") if lang == "es" else ("“", "”")
    return f"{side} {cite['source_id']}{where} {opening}{_squash(cite['quote'])}{closing}"


def write_cross_report(project_id: str, change_id: str) -> Path:
    change = get_change(project_id, change_id)
    lang = "es" if change_language(project_id, change) == "es" else "en"
    base = workspace_path(project_id)
    status = cross_status(project_id, change_id)
    gaps_path = change_gaps_path(base, change_id)
    gap_rows = parse_gap_rows(gaps_path.read_text(encoding="utf-8-sig")) if gaps_path.exists() else []
    open_ids = {g["id"] for g in gap_rows if str(g.get("status", "OPEN")).strip("`").upper() != "CLOSED"}
    title = f"# Cruces del pedido — {change_id}" if lang == "es" else f"# Cross-reads of the request — {change_id}"
    lines = [title, "", status["text"], ""]
    for kind in CROSS_KINDS:
        info = status["kinds"][kind]
        lines += [f"## {KIND_LABELS[lang][kind]}", "",
                  f"{'Estado' if lang == 'es' else 'State'}: {STATE_LABELS[lang][info['state']]}"]
        if info["state"] == "waived":
            lines.append(f"{'Motivo' if lang == 'es' else 'Reason'}: {info.get('reason') or '-'}")
        if kind == "linea_de_base":
            if info.get("source_ids"):
                lines.append(f"Harvests: {', '.join(info['source_ids'])}")
            lines.append("")
            continue
        if info["stale_sources"]:
            note = "Fuentes citadas que ya no están vigentes" if lang == "es" else "Cited sources no longer current"
            lines.append(f"{note}: {', '.join(info['stale_sources'])}")
        if info.get("new_sources"):
            note = "Fuentes vigentes que el cruce no leyó" if lang == "es" else "Current sources the cross-read did not read"
            lines.append(f"{note}: {', '.join(info['new_sources'])}")
        record = _load(base, change_id, kind)
        if record and record.get("status") == "done":
            lines.append("")
            names = TAG_NAMES[lang]
            for claim in record.get("claims", []):
                cites = "; ".join(_cite_text(c, lang) for c in claim.get("citations", []))
                arrow = f" → {claim['gap']}" if claim.get("gap") else ""
                tail = f" — {cites}{arrow}" if cites or arrow else ""
                lines.append(f"- [{names[claim['tag']]}] {_squash(claim['text'])}{tail}")
        if record and record.get("status") in ("done", "waived"):
            dropped = [g for g in record.get("dropped_gaps", []) if g in open_ids]
            if dropped:
                lead = ("Preguntas de entregas anteriores que esta entrega no repite (siguen abiertas hasta que el BA las cierre): "
                        if lang == "es" else
                        "Questions from earlier deliveries that this one does not repeat (they stay open until the BA closes them): ")
                lines += ["", lead + ", ".join(dropped)]
        lines.append("")
    from .surfaces import new_surface_candidates

    candidates = new_surface_candidates(project_id, change_id)
    if candidates:
        lines += ["## Candidatas a superficie nueva (del harvest)" if lang == "es"
                  else "## New surface candidates (from the harvest)", ""]
        for item in candidates:
            if item["decision"] == "accepted":
                verdict = (f"aceptada como {item['type']} «{item['name']}»" if lang == "es"
                           else f"accepted as {item['type']} «{item['name']}»")
            elif item["decision"] == "declined":
                verdict = f"{'descartada' if lang == 'es' else 'declined'}: {item['reason']}"
            else:
                verdict = "pendiente" if lang == "es" else "pending"
            lines.append(f"- {item['id']} «{item['text']}» ({item['source_id']}:{item['line']}): {verdict}")
        lines.append("")
    path = crosses_dir(base, change_id) / "crosses.md"
    write_text(path, "\n".join(lines).rstrip() + "\n")
    return path
