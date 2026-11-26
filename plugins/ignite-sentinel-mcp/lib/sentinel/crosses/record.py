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

from ..changes import _squash, change_gaps_path, change_language, resolve_scope, list_changes
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


def _design_place(cite: dict, origins: dict[str, str] | None, es: bool) -> str:
    """The cited design source, with where it comes from when it is a derived copy (H27 inc 7a)."""
    origin = (origins or {}).get(str(cite["source_id"]))
    if not origin:
        return str(cite["source_id"])
    return f"{cite['source_id']}, {'derivado de' if es else 'derived from'} {origin}"


def _gap_texts(tag: str, claim: dict, es: bool, origins: dict[str, str] | None = None) -> tuple[str, str]:
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
                    f"{q(qd)} ({_design_place(qd, origins, es)}). {text}",
                    "¿Qué rige? Opciones: (A) rige el diseño: el pedido se corrige en la extracción; "
                    "(B) rige el pedido: el prototipo se corrige; "
                    "(C) se corrigen los dos: escribí en la respuesta el comportamiento que va.")
        return (f"⚠ Divergence between the request and the new design: the request says {q(qp)} ({_place(qp)}) and the prototype shows "
                f"{q(qd)} ({_design_place(qd, origins, es)}). {text}",
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
            return (f"Sólo en el diseño nuevo: el prototipo muestra {q(qd)} ({_design_place(qd, origins, es)}) y el pedido no lo menciona. {text}",
                    "¿Entra en este cambio? Opciones: (A) entra: sumalo al borde con /cross --accept-new este id --type TIPO --name NOMBRE y al pedido; "
                    "(B) no entra: el prototipo se adelanta; (C) ya existe en lo construido.")
        return (f"Only in the new design: the prototype shows {q(qd)} ({_design_place(qd, origins, es)}) and the request does not mention it. {text}",
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


def cross_gap(change_id: str | None, claim: dict, language: str, origins: dict[str, str] | None = None) -> dict | None:
    """The question a claim raises, or None for a backed claim."""
    tag = claim["tag"]
    if tag not in GAP_PREFIXES:
        return None
    cites = claim["citations"]
    digest = hashlib.sha256(
        f"{change_id or 'project'}|{tag}|{' // '.join(_squash(c['quote']) for c in cites)}".encode("utf-8")
    ).hexdigest()[:8].upper()
    side = "diseno" if tag == "solo_en_diseno" else "pedido"
    mention = " // ".join(_squash(c["quote"]) for c in cites if c["side"] == side)
    description, question = _gap_texts(tag, claim, language == "es", origins)
    return {
        "id": f"{GAP_PREFIXES[tag]}{digest}", "lens": _LENS[tag], "severity": _SEVERITY[tag], "status": "OPEN",
        "description": description, "question": question, "evidence_mention": mention,
        "origin": "cross", "resolution_note": "",
    }


def add_change_gaps(project_id: str, change_id: str, gaps: list[dict], candidates: dict[str, dict] | None = None,
                    refs: dict[str, dict] | None = None) -> list[str]:
    """Open the gaps whose exact id the change does not have yet; returns the new ids.

    IMP-410: before they are written, the new ones are settled against what the change already decided."""
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
        from ..prior_decisions import apply_prior_decisions

        apply_prior_decisions(project_id, change_id, added, candidates or {}, refs)
        _save_change_gaps(project_id, change_id, path, [*existing, *added])
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
    _save_change_gaps(project_id, change_id, path, rows)
    return True


RETIRE_NOTE = {"es": "afirmación retirada al re-registrar el cruce", "en": "claim withdrawn when the cross-read was re-recorded"}


def _save_change_gaps(project_id: str, change_id: str | None, path: Path, rows: list[dict]) -> None:
    language = resolve_scope(project_id, change_id).language
    if change_id is None:  # H27 inc 6b: the project's gaps.md, rendered and counted like the harvest does
        from ..gaps import readiness_stage_after_gap_change

        req_id = str(rows[0].get("parent") or "REQ-001").strip("`") if rows else "REQ-001"
        write_text(path, render_gaps(project_id, rows, req_id, language))
        counts = count_gaps(rows)
        update_state(project_id, gap_counts=counts, readiness_stage=readiness_stage_after_gap_change(project_id, counts))
        return
    write_text(path, render_gaps(project_id, rows, change_id, language, path.with_name("gap_elicitation.json")))
    updated = {k: dict(v) for k, v in list_changes(project_id).items()}
    updated[change_id]["gap_counts"] = count_gaps(rows)
    update_state(project_id, changes=updated)


def _gap_rows(path: Path) -> list[dict]:
    return [g for g in parse_gap_rows(path.read_text(encoding="utf-8-sig")) if g.get("id") != "NONE"] if path.exists() else []


def retire_change_gaps(project_id: str, change_id: str, gap_ids: list[str], note: str) -> list[str]:
    """Close, in one write, the open questions among gap_ids with the note; returns the ones it closed."""
    path = change_gaps_path(workspace_path(project_id), change_id)
    rows = _gap_rows(path)
    wanted = set(gap_ids)
    closed = [g for g in rows if g.get("id") in wanted and str(g.get("status", "OPEN")).strip("`").upper() != "CLOSED"]
    if not closed:
        return []
    for gap in closed:
        gap["status"] = "CLOSED"
        gap["resolution_note"] = note
    _save_change_gaps(project_id, change_id, path, rows)
    return [g["id"] for g in closed]


def reopen_retired_gaps(project_id: str, change_id: str, gap_ids: list[str]) -> list[str]:
    """Reopen the questions among gap_ids that a re-recording had withdrawn (never one the BA answered)."""
    path = change_gaps_path(workspace_path(project_id), change_id)
    rows = _gap_rows(path)
    wanted = set(gap_ids)
    notes = set(RETIRE_NOTE.values())
    back = [g for g in rows if g.get("id") in wanted and str(g.get("status", "")).strip("`").upper() == "CLOSED"
            and (str(g.get("resolution_note", "")).strip() in notes
                 or str(g.get("closure_reason") or "").strip("`").strip().lower() == "retired")]
    if not back:
        return []
    for gap in back:
        gap["status"] = "OPEN"
        gap["resolution_note"] = ""
        if "closure_reason" in gap:
            gap["closure_reason"] = ""
    _save_change_gaps(project_id, change_id, path, rows)
    return [g["id"] for g in back]


def load_cross(base: Path, change_id: str, kind: str) -> dict | None:
    data = read_json(cross_path(base, change_id, kind), None)
    return data if isinstance(data, dict) else None


def _next_number(folder: Path) -> int:
    numbers = [int(m.group(1)) for p in folder.glob("*") if (m := re.match(r"(\d+)-", p.name))] if folder.exists() else []
    return max(numbers, default=0) + 1


def _counts(claims: list[dict]) -> dict[str, int]:
    found = {tag: sum(1 for c in claims if c["tag"] == tag) for tag in TAG_NAMES["es"]}
    return {tag: n for tag, n in found.items() if n}


def record_cross(project_id: str, change_id: str, kind: str, claims_path: Path, delta: bool = False) -> dict[str, Any]:
    from ..secrets_scan import sanitize_text
    from ..sources import mark_source_processed, open_source_row, settle_rerun

    change = resolve_scope(project_id, change_id).entry
    language = change_language(project_id, change)
    es = language == "es"
    kind = normalize_kind(kind, language)
    if kind == "linea_de_base":
        raise CrossError(
            "El cruce con la línea de base es el harvest" if es else "The cross-read with the baseline is the harvest",
            next_step=f"/harvest {project_id} --source ARCHIVO --change {change_id}" if es
            else f"/harvest {project_id} --source FILE --change {change_id}")
    base = workspace_path(project_id)
    if delta:
        earlier = load_cross(base, change_id, kind) or {}
        if earlier.get("status") != "done":
            raise CrossError(
                f"No hay un cruce {kind} registrado para completar: registrá el cruce completo sin --delta" if es
                else f"There is no recorded {kind} cross-read to complete: record the full cross-read without --delta")
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

    previous = load_cross(base, change_id, kind) or {}
    source_id = open_source_row(project_id, claims_path, "crossed")
    submitted = crosses_dir(base, change_id) / "submitted"
    target = unique_path(submitted / f"{_next_number(submitted):03d}-{claims_path.name}")
    write_text(target, sanitize_text(base, claims_path.name, raw).text)
    source_id = mark_source_processed(project_id, claims_path, "crossed", source_id=source_id) or source_id
    mark_source_processed(project_id, target, "raw_copy", source_id=source_id)
    # H27 inc 6a: a re-run of this kind's cross-read closes its own version chain.
    settle_rerun(project_id, source_id, "crossed", [str(previous["source_id"])] if previous.get("source_id") else [])

    from ..prior_decisions import candidate_from_claim, design_request_ref, load_priors

    gap_ids: list[str] = []
    gaps: list[dict] = []
    candidates: dict[str, dict] = {}
    refs: dict[str, dict] = {}
    origins = {sid: str(row["derived_from"]) for sid, row in cross_sources(project_id, change_id)["diseno"].items()
               if row.get("derived_from")}
    for claim in claims:
        gap = cross_gap(change_id, claim, language, origins)
        if gap is not None:
            claim["gap"] = gap["id"]
            candidates[gap["id"]] = candidate_from_claim(gap, claim)
            ref = design_request_ref(project_id, change_id, claim) if claim["tag"] == "divergencia" else None
            if ref:  # IMP-410: the request already asks Design for this (the id stays: it comes from the quotes)
                refs[gap["id"]] = ref
                gap["description"] += (f" Ya registrado en el pedido como pedido a Diseño: {ref['ref']}." if es
                                       else f" Already registered in the request as a request to Design: {ref['ref']}.")
            gaps.append(gap)
            if gap["id"] not in gap_ids:
                gap_ids.append(gap["id"])
    kept: list[int] = []
    replaced: list[str] = []
    if delta:  # H27 inc 6a: the claims the sync marked are replaced; the others stay with their questions and answers
        touched = {int(n) for n in (previous.get("pending_delta") or {}).get("touched") or []}
        stay = [c for c in previous.get("claims") or [] if int(c["n"]) not in touched]
        replaced = [c["gap"] for c in previous.get("claims") or [] if int(c["n"]) in touched and c.get("gap")]
        kept = [int(c["n"]) for c in stay]
        known = {(c["tag"], tuple(_squash(x["quote"]) for x in c["citations"])) for c in stay}
        fresh = [c for c in claims if (c["tag"], tuple(_squash(x["quote"]) for x in c["citations"])) not in known
                 and (c["tag"] != "sin_hallazgos" or not stay)]
        if fresh:
            stay = [c for c in stay if c["tag"] != "sin_hallazgos"]
        claims = [*stay, *fresh]
        gap_ids = list(dict.fromkeys(c["gap"] for c in claims if c.get("gap")))
    reopened = reopen_retired_gaps(project_id, change_id, gap_ids)
    opened = add_change_gaps(project_id, change_id, gaps, candidates, refs)
    priors = load_priors(base, change_id)
    pre_decided = [g for g in opened if priors.get(g, {}).get("match") == "linked"]
    design_requests = [g for g in opened if priors.get(g, {}).get("match") == "design_request"]

    earlier = [g for g in previous.get("gaps", []) if previous.get("status") == "done"]
    dropped = [g for g in (replaced if delta else earlier) if g not in gap_ids]
    carried = [g for g in [*(previous.get("dropped_gaps") or []), *dropped] if g not in gap_ids]
    retired = retire_change_gaps(project_id, change_id, dropped, RETIRE_NOTE["es" if es else "en"])
    # an answered question of a replaced claim stays closed with its answer: it is replaced, not withdrawn
    replaced_kept = [g for g in dropped if g not in retired] if delta else []
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
        **({"retired_gaps": retired} if retired else {}),
        **({"replaced_gaps": replaced_kept} if replaced_kept else {}),
    }
    write_json(path, record)
    report = write_cross_report(project_id, change_id)
    return {
        "project_id": project_id, "change_id": change_id, "action": "claims", "kind": kind, "source_id": source_id,
        "counts": counts, "gaps": gap_ids, "gaps_opened": opened, "dropped_gaps": dropped,
        "retired_gaps": retired, "reopened_gaps": reopened, "pre_decided": pre_decided, "design_requests": design_requests,
        "path": path.as_posix(), "report_path": report.as_posix(),
        **({"mode": "delta", "kept": kept, "replaced_gaps": replaced_kept} if delta else {}),
    }


def skip_cross(project_id: str, change_id: str, kind: str, reason: str) -> dict[str, Any]:
    change = resolve_scope(project_id, change_id).entry
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
