"""IMP-404 task 3: record a cross-read (or waive it) and open the questions its claims raise.

All or nothing, like the harvest: a claims file with one false quote registers nothing.
A resubmission keeps the ids of the questions it repeats (exact id, never by topic).
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from ..changes import _squash, change_gaps_path, change_language, get_change, list_changes
from ..core.io import read_json, write_json, write_text
from ..core.text import unique_path
from ..core.time import utc_now
from ..errors import InputError
from ..gaps import count_gaps, parse_gap_rows, render_gaps
from ..workspace import update_state, workspace_path
from . import cross_path, crosses_dir, normalize_kind
from .claims import TAG_NAMES, cross_sources, parse_claims, validate_claims
from .state import write_cross_report


class CrossError(InputError):
    pass


GAP_PREFIXES = {
    "divergencia": "GAP-DIS-",
    "sin_respaldo": "GAP-SRD-",
    "solo_en_diseno": "GAP-SED-",
    "contradiccion": "GAP-CON-",
}

_SEVERITY = {"divergencia": "high", "sin_respaldo": "medium", "solo_en_diseno": "medium", "contradiccion": "high"}
_LENS = {"divergencia": "design", "sin_respaldo": "design", "solo_en_diseno": "design", "contradiccion": "product"}


def _place(cite: dict) -> str:
    return f"{cite['source_id']}:{cite['line']}" if cite.get("line") else str(cite["source_id"])


def _gap_texts(tag: str, claim: dict, es: bool) -> tuple[str, str]:
    cites = claim["citations"]
    pedido = [c for c in cites if c["side"] == "pedido"]
    diseno = [c for c in cites if c["side"] == "diseno"]
    open_q, close_q = ("«", "»") if es else ("“", "”")

    def q(cite: dict) -> str:
        return f"{open_q}{_squash(cite['quote'])}{close_q}"

    text = claim["text"]
    if tag == "divergencia":
        qp, qd = pedido[0], diseno[0]
        if es:
            return (f"⚠ Divergencia entre el pedido y el diseño nuevo: el pedido dice {q(qp)} ({_place(qp)}) y el prototipo muestra "
                    f"{q(qd)} ({qd['source_id']}). {text}",
                    "¿Qué rige? Opciones: (A) rige el diseño: el pedido se corrige en la extracción; "
                    "(B) rige el pedido: el prototipo se corrige; "
                    "(C) se corrigen los dos: escribí en la respuesta el comportamiento que va.")
        return (f"⚠ Divergence between the request and the new design: the request says {q(qp)} ({_place(qp)}) and the prototype shows "
                f"{q(qd)} ({qd['source_id']}). {text}",
                "Which one governs? Options: (A) the design governs: the request is corrected in the extraction; "
                "(B) the request governs: the prototype is corrected; "
                "(C) both are corrected: write the behavior that applies in the answer.")
    if tag == "sin_respaldo":
        qp = pedido[0]
        if es:
            return (f"Sin respaldo en el diseño nuevo: el pedido pide {q(qp)} ({_place(qp)}) y el prototipo no tiene pantalla ni flujo para eso. {text}",
                    "¿Falta en el prototipo o sale del cambio? Opciones: (A) falta en el prototipo: se diseña; "
                    "(B) se construye sin pantalla nueva; (C) sale de este cambio: descartalo en la extracción.")
        return (f"Not backed by the new design: the request asks for {q(qp)} ({_place(qp)}) and the prototype has no screen or flow for it. {text}",
                "Is it missing in the prototype or out of the change? Options: (A) missing in the prototype: it gets designed; "
                "(B) it is built without a new screen; (C) it leaves this change: discard it in the extraction.")
    if tag == "solo_en_diseno":
        qd = diseno[0]
        if es:
            return (f"Sólo en el diseño nuevo: el prototipo muestra {q(qd)} ({qd['source_id']}) y el pedido no lo menciona. {text}",
                    "¿Entra en este cambio? Opciones: (A) entra: sumalo al borde con /cross --accept-new este id --type TIPO --name NOMBRE y al pedido; "
                    "(B) no entra: el prototipo se adelanta; (C) ya existe en lo construido.")
        return (f"Only in the new design: the prototype shows {q(qd)} ({qd['source_id']}) and the request does not mention it. {text}",
                "Does it belong in this change? Options: (A) it does: add it to the border with /cross --accept-new this id --type TYPE --name NAME, and to the request; "
                "(B) it does not: the prototype is ahead; (C) it already exists in what is built.")
    first, second = pedido[0], pedido[1]
    if es:
        return (f"⚠ Contradicción interna del pedido: {q(first)} ({_place(first)}) y {q(second)} ({_place(second)}). {text}",
                "¿Cuál rige? Opciones: (A) rige la primera; (B) rige la segunda; "
                "(C) ninguna: escribí en la respuesta el comportamiento que va.")
    return (f"⚠ Internal contradiction in the request: {q(first)} ({_place(first)}) and {q(second)} ({_place(second)}). {text}",
            "Which one governs? Options: (A) the first governs; (B) the second governs; "
            "(C) neither: write the behavior that applies in the answer.")


def cross_gap(change_id: str, claim: dict, language: str) -> dict | None:
    """The question a claim raises, or None for a backed claim."""
    tag = claim["tag"]
    if tag not in GAP_PREFIXES:
        return None
    cites = claim["citations"]
    digest = hashlib.sha256(
        f"{change_id}|{tag}|{' // '.join(_squash(c['quote']) for c in cites)}".encode("utf-8")
    ).hexdigest()[:8].upper()
    side = "diseno" if tag == "solo_en_diseno" else "pedido"
    mention = " // ".join(_squash(c["quote"]) for c in cites if c["side"] == side)
    description, question = _gap_texts(tag, claim, language == "es")
    return {
        "id": f"{GAP_PREFIXES[tag]}{digest}", "lens": _LENS[tag], "severity": _SEVERITY[tag], "status": "OPEN",
        "description": description, "question": question, "evidence_mention": mention,
        "origin": "cross", "resolution_note": "",
    }


def add_change_gaps(project_id: str, change_id: str, gaps: list[dict]) -> list[str]:
    """Open the gaps whose exact id the change does not have yet; returns the new ids."""
    base = workspace_path(project_id)
    path = change_gaps_path(base, change_id)
    existing = [g for g in parse_gap_rows(path.read_text(encoding="utf-8-sig")) if g.get("id") != "NONE"] if path.exists() else []
    known = {g["id"] for g in existing}
    added: list[dict] = []
    for gap in gaps:  # exact id only: two marks are two questions, never folded by topic
        if gap["id"] not in known:
            known.add(gap["id"])
            added.append(gap)
    if added:
        language = change_language(project_id, get_change(project_id, change_id))
        rows = [*existing, *added]
        write_text(path, render_gaps(project_id, rows, change_id, language, path.with_name("gap_elicitation.json")))
        updated = {k: dict(v) for k, v in list_changes(project_id).items()}
        updated[change_id]["gap_counts"] = count_gaps(rows)
        update_state(project_id, changes=updated)
    return [g["id"] for g in added]


def source_basis(project_id: str, change_id: str) -> dict[str, list[str]]:
    """The current sources a cross-read had in front of it: the change's requests and the new-design prototypes."""
    found = cross_sources(project_id, change_id)
    return {side: sorted(found[side]) for side in ("pedido", "diseno")}


def claims_hash(claims: list[dict], reason: str = "") -> str:
    """What a delivery decided, apart from where it was filed: its tags, quotes and questions (and a waiver's reason)."""
    shape = [[c["tag"], _squash(c["text"]), c.get("gap", ""),
              [[x["side"], x["source_id"], _squash(x["quote"])] for x in c["citations"]]] for c in claims]
    payload = json.dumps([shape, reason.strip()], ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def close_change_gap(project_id: str, change_id: str, gap_id: str, note: str) -> bool:
    """Close one question of the change by its exact id, with the way it was settled."""
    base = workspace_path(project_id)
    path = change_gaps_path(base, change_id)
    if not path.exists():
        return False
    rows = [g for g in parse_gap_rows(path.read_text(encoding="utf-8-sig")) if g.get("id") != "NONE"]
    hit = [g for g in rows if g.get("id") == gap_id]
    if not hit:
        return False
    hit[0]["status"] = "CLOSED"
    hit[0]["resolution_note"] = note
    language = change_language(project_id, get_change(project_id, change_id))
    write_text(path, render_gaps(project_id, rows, change_id, language, path.with_name("gap_elicitation.json")))
    updated = {k: dict(v) for k, v in list_changes(project_id).items()}
    updated[change_id]["gap_counts"] = count_gaps(rows)
    update_state(project_id, changes=updated)
    return True


def load_cross(base: Path, change_id: str, kind: str) -> dict | None:
    data = read_json(cross_path(base, change_id, kind), None)
    return data if isinstance(data, dict) else None


def _next_number(folder: Path) -> int:
    numbers = [int(m.group(1)) for p in folder.glob("*") if (m := re.match(r"(\d+)-", p.name))] if folder.exists() else []
    return max(numbers, default=0) + 1


def _counts(claims: list[dict]) -> dict[str, int]:
    found = {tag: sum(1 for c in claims if c["tag"] == tag) for tag in TAG_NAMES["es"]}
    return {tag: n for tag, n in found.items() if n}


def record_cross(project_id: str, change_id: str, kind: str, claims_path: Path) -> dict[str, Any]:
    from ..secrets_scan import sanitize_text
    from ..sources import mark_source_processed, open_source_row

    change = get_change(project_id, change_id)
    language = change_language(project_id, change)
    es = language == "es"
    kind = normalize_kind(kind, language)
    if kind == "linea_de_base":
        raise CrossError(
            "El cruce con la línea de base es el harvest" if es else "The cross-read with the baseline is the harvest",
            next_step=f"/harvest {project_id} --source ARCHIVO --change {change_id}" if es
            else f"/harvest {project_id} --source FILE --change {change_id}")
    claims_path = Path(claims_path)
    if not claims_path.is_file():
        raise CrossError(f"No existe el archivo de cruce: {claims_path}" if es else f"The cross-read file does not exist: {claims_path}")
    try:
        raw = claims_path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise CrossError(f"El archivo de cruce no está en UTF-8 ({claims_path.name}): guardalo como UTF-8" if es
                         else f"The cross-read file is not UTF-8 ({claims_path.name}): save it as UTF-8") from exc
    claims, errors = parse_claims(raw, language)
    if not errors:
        claims, errors = validate_claims(project_id, change_id, kind, claims)
    if errors:
        head = "Cruce rechazado" if es else "Cross-read rejected"
        raise CrossError(f"{head}:\n- " + "\n- ".join(errors))

    base = workspace_path(project_id)
    source_id = open_source_row(project_id, claims_path, "crossed")
    submitted = crosses_dir(base, change_id) / "submitted"
    target = unique_path(submitted / f"{_next_number(submitted):03d}-{claims_path.name}")
    write_text(target, sanitize_text(base, claims_path.name, raw).text)
    source_id = mark_source_processed(project_id, claims_path, "crossed", source_id=source_id) or source_id
    mark_source_processed(project_id, target, "raw_copy", source_id=source_id)

    gap_ids: list[str] = []
    gaps: list[dict] = []
    for claim in claims:
        gap = cross_gap(change_id, claim, language)
        if gap is not None:
            claim["gap"] = gap["id"]
            gaps.append(gap)
            if gap["id"] not in gap_ids:
                gap_ids.append(gap["id"])
    opened = add_change_gaps(project_id, change_id, gaps)

    previous = load_cross(base, change_id, kind) or {}
    earlier = [g for g in previous.get("gaps", []) if previous.get("status") == "done"]
    dropped = [g for g in earlier if g not in gap_ids]
    carried = [g for g in [*(previous.get("dropped_gaps") or []), *dropped] if g not in gap_ids]
    counts = _counts(claims)
    path = cross_path(base, change_id, kind)
    record = {
        "schema_version": 1, "change_id": change_id, "kind": kind, "status": "done", "recorded_at": utc_now(),
        "source_id": source_id, "submitted": target.relative_to(base).as_posix(),
        "claims": [{"n": index, "line": c["line"], "tag": c["tag"], "text": c["text"], "citations": c["citations"],
                    **({"gap": c["gap"]} if c.get("gap") else {})} for index, c in enumerate(claims, start=1)],
        "counts": counts, "gaps": gap_ids, "basis": source_basis(project_id, change_id),
        "claims_hash": claims_hash(claims, reason=""),
        **({"dropped_gaps": list(dict.fromkeys(carried))} if carried else {}),
    }
    write_json(path, record)
    report = write_cross_report(project_id, change_id)
    return {
        "project_id": project_id, "change_id": change_id, "action": "claims", "kind": kind, "source_id": source_id,
        "counts": counts, "gaps": gap_ids, "gaps_opened": opened, "dropped_gaps": dropped,
        "path": path.as_posix(), "report_path": report.as_posix(),
    }


def skip_cross(project_id: str, change_id: str, kind: str, reason: str) -> dict[str, Any]:
    change = get_change(project_id, change_id)
    language = change_language(project_id, change)
    es = language == "es"
    kind = normalize_kind(kind, language)
    if not (reason or "").strip():
        raise InputError(
            "--skip necesita --reason con el porqué: sin motivo no hay descarte" if es
            else "--skip needs --reason with the why: no reason, no waiver",
            next_step=f'/cross {project_id} --change {change_id} --kind {kind} --skip --reason "…"')
    from .state import cross_status

    base = workspace_path(project_id)
    existing = load_cross(base, change_id, kind) or {}
    current_done = existing.get("status") == "done" and cross_status(project_id, change_id)["kinds"][kind]["state"] != "stale"
    if current_done or (kind == "linea_de_base" and change.get("harvests")):
        raise InputError(f"El cruce {kind} de {change_id} ya está hecho: no se descarta" if es
                         else f"The {kind} cross-read of {change_id} is already done: it is not waived")
    path = cross_path(base, change_id, kind)
    # a stale cross that is waived keeps the questions it opened: they stay open until the BA closes them
    earlier = [*(existing.get("gaps") or []), *(existing.get("dropped_gaps") or [])] if existing else []
    write_json(path, {"schema_version": 1, "change_id": change_id, "kind": kind, "status": "waived",
                      "reason": reason.strip(), "waived_at": utc_now(), "basis": source_basis(project_id, change_id),
                      "claims_hash": claims_hash([], reason=reason),
                      **({"dropped_gaps": list(dict.fromkeys(earlier))} if earlier else {})})
    report = write_cross_report(project_id, change_id)
    return {"project_id": project_id, "change_id": change_id, "action": "skip", "kind": kind,
            "reason": reason.strip(), "path": path.as_posix(), "report_path": report.as_posix()}
