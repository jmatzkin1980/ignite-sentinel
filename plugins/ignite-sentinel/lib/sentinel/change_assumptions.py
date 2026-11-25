"""IMP-412 (H27 inc 4): the assumptions of a change close their question and have a life cycle.

The project's register (`assumptions.py`) never unblocks a gap: there an assumption is a visible,
provisional link. In a change the BA decides to go on with a risk, so the assumption closes the
question (`CLOSED`, `closure_reason = "assumed"`) until someone validates it (the closure becomes an
answer) or invalidates it (the question opens again). Same validation and table as the project's
register; another register (`01_discovery/CHG-nnn/assumptions.md`) and another closing semantic.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .assumptions import (
    AssumptionError,
    archive_payload,
    assumption_grounding_text,
    load_assumption_source,
    load_assumptions,
    render_assumptions,
    sanitize_payload,
    summarize_assumptions,
    validate_assumptions,
)
from .core.io import read_json, write_text
from .core.text import unique_path
from .core.time import utc_now
from .errors import InputError
from .gaps import ASSUMED_CLOSURE, parse_gap_rows
from .gaps.model import extract_field
from .workspace import workspace_path, write_json

SUPUESTO_STATUSES = {"supuesto", "assumption", "assumed"}
ORIGINS = ("assume", "response")


def change_assumptions_path(base: Path, change_id: str) -> Path:
    return base / "01_discovery" / change_id / "assumptions.md"


def assumptions_meta_path(base: Path, change_id: str) -> Path:
    return base / "01_discovery" / change_id / "assumptions.json"


def assumed_note(assumption_id: str, validate_with: str, language: str) -> str:
    if language == "es":
        return f"supuesto {assumption_id}: a validar con {validate_with}"
    return f"assumption {assumption_id}: to validate with {validate_with}"


def _es(language: str) -> bool:
    return language == "es"


MIN_QUOTE_WORDS = 4


def change_grounding_exclusions(base: Path, change_id: str) -> tuple[Path, ...]:
    """What an assumption of a change cannot quote: its own register, its lateral, its archive and the answer files
    /resolve-gaps kept (the agent's own words). One list for `/assume --change` and for the `supuesto` bridge."""
    return (change_assumptions_path(base, change_id), assumptions_meta_path(base, change_id),
            base / "01_discovery" / change_id / "assumptions", base / "07_changes" / "00_client_responses")


def literal_quote(text: str) -> str:
    """The first quoted span (", «», “”) of `text` with at least MIN_QUOTE_WORDS words, or ''."""
    for found in _QUOTED.finditer(text or ""):
        span = next(group for group in found.groups() if group is not None).strip()
        if len(span.split()) >= MIN_QUOTE_WORDS:
            return span
    return ""


def _read_meta(base: Path, change_id: str) -> dict[str, dict]:
    data = read_json(assumptions_meta_path(base, change_id), {})
    found = data.get("assumptions") if isinstance(data, dict) else None
    return {str(k): dict(v) for k, v in found.items() if isinstance(v, dict)} if isinstance(found, dict) else {}


def _write_meta(base: Path, change_id: str, meta: dict[str, dict]) -> None:
    write_json(assumptions_meta_path(base, change_id), {"schema_version": 1, "assumptions": meta})


def load_change_assumptions(project_id: str, change_id: str) -> list[dict]:
    """The rows of the change's register, each with the `validate_with`, `gap` and `origin` of its lateral."""
    base = workspace_path(project_id)
    rows = load_assumptions(project_id, change_assumptions_path(base, change_id))
    meta = _read_meta(base, change_id)
    out: list[dict] = []
    for row in rows:
        side = meta.get(row["id"], {})
        out.append({**row,
                    "validate_with": str(side.get("validate_with") or row.get("owner", "")),
                    "gap": str(side.get("gap") or row.get("closes_gap", "")),
                    "origin": str(side.get("origin") or "assume")})
    return out


def _persist(project_id: str, change_id: str, rows: list[dict], meta: dict[str, dict]) -> Path:
    base = workspace_path(project_id)
    path = change_assumptions_path(base, change_id)
    plain = [{k: v for k, v in row.items() if k not in ("validate_with", "gap", "origin")} for row in rows]
    write_text(path, render_assumptions(change_id, plain))
    _write_meta(base, change_id, meta)
    return path


def register_change_assumptions(project_id: str, change_id: str, rows: list[dict],
                                meta: dict[str, dict]) -> dict[str, list[str]]:
    """Add the rows whose id is not in the register yet and write the table and its lateral."""
    base = workspace_path(project_id)
    existing = load_change_assumptions(project_id, change_id)
    known = {row["id"] for row in existing}
    accepted = [row for row in rows if row["id"] not in known]
    skipped = [row["id"] for row in rows if row["id"] in known]
    if accepted:
        lateral = _read_meta(base, change_id)
        for row in accepted:
            side = meta.get(row["id"], {})
            lateral[row["id"]] = {"validate_with": str(side.get("validate_with", "")), "gap": str(side.get("gap", "")),
                                  "origin": str(side.get("origin", "assume")), "reason": str(side.get("reason", "")),
                                  "decided_at": str(side.get("decided_at", ""))}
        _persist(project_id, change_id, [*existing, *accepted], lateral)
    return {"accepted": [row["id"] for row in accepted], "skipped": skipped}


def _gap_rows(project_id: str, change_id: str) -> tuple[Path, list[dict]]:
    from .changes import change_gaps_path

    path = change_gaps_path(workspace_path(project_id), change_id)
    rows = [g for g in parse_gap_rows(path.read_text(encoding="utf-8-sig")) if g.get("id") != "NONE"] if path.exists() else []
    return path, rows


def _status(row: dict) -> str:
    return str(row.get("status", "OPEN")).strip("`").strip().upper()


def _closure(row: dict) -> str:
    return str(row.get("closure_reason") or "").strip("`").strip().lower()


def close_gaps_as_assumed(project_id: str, change_id: str, links: dict[str, tuple[str, str]]) -> list[str]:
    """Close the questions in `links` (gap -> (ASM, validate_with)) as assumed; returns the ones it closed."""
    from .change_coherence import refresh_coherence
    from .changes import change_language, get_change
    from .crosses.record import _save_change_gaps

    path, rows = _gap_rows(project_id, change_id)
    language = change_language(project_id, get_change(project_id, change_id))
    closed: list[str] = []
    for gap in rows:
        link = links.get(str(gap.get("id")))
        if not link or _status(gap) == "CLOSED":
            continue
        gap["status"] = "CLOSED"
        gap["closure_reason"] = ASSUMED_CLOSURE
        gap["resolution_note"] = assumed_note(link[0], link[1], language)
        closed.append(str(gap["id"]))
    if closed:
        _save_change_gaps(project_id, change_id, path, rows)
        refresh_coherence(project_id, change_id)
    return closed


def apply_change_assumptions(project_id: str, change_id: str, source: Path) -> dict[str, Any]:
    from .changes import change_language, get_change
    from .readiness_verdict import change_next_step

    base = workspace_path(project_id)
    change = get_change(project_id, change_id)
    language = change_language(project_id, change)
    es = _es(language)
    path, gaps = _gap_rows(project_id, change_id)
    if not path.exists():
        from .errors import GateRefusal

        raise GateRefusal(f"{change_id} no tiene preguntas registradas todavía" if es
                          else f"{change_id} has no questions recorded yet")
    data = load_assumption_source(Path(source))
    own = change_grounding_exclusions(base, change_id)
    # IMP-412 final review: in a change the justification is a literal quote of at least 4 words (quote marks optional in the JSON field)
    for index, item in enumerate((i for i in data.get("assumptions", []) if isinstance(i, dict)), start=1):
        raw = str(item.get("justification", item.get("evidence", ""))).strip()
        quoted = literal_quote(raw) if _QUOTED.search(raw) else raw
        if raw and len(quoted.split()) < MIN_QUOTE_WORDS:
            asm_id = str(item.get("id") or f"ASM-{index:03d}").strip().upper()
            raise AssumptionError(
                f"{asm_id}: la justificación debe ser una cita literal de al menos {MIN_QUOTE_WORDS} palabras de una fuente local" if es
                else f"{asm_id}: the justification must be a literal quote of at least {MIN_QUOTE_WORDS} words from a local source")
        if raw and quoted != raw:
            item["justification"] = quoted
            item.pop("evidence", None)
    validated = validate_assumptions(data, assumption_grounding_text(base, exclude=own))
    raw_items = [item for item in data.get("assumptions", []) if isinstance(item, dict)]
    extra = {str(item.get("id") or f"ASM-{index:03d}").strip().upper(): str(item.get("validate_with") or "").strip()
             for index, item in enumerate(raw_items, start=1)}
    known = {row["id"] for row in load_change_assumptions(project_id, change_id)}
    by_gap = {str(g["id"]): g for g in gaps}
    taken: set[str] = set()
    for row in validated:
        asm, gap_id = row["id"], row.get("closes_gap", "")
        if asm in known or not gap_id:
            continue
        if gap_id not in by_gap:
            raise AssumptionError(f"{asm}: {gap_id} no es una pregunta de {change_id}" if es
                                  else f"{asm}: {gap_id} is not a question of {change_id}")
        if gap_id == "GAP-SCOPE":
            raise AssumptionError(f"{asm}: GAP-SCOPE se cierra confirmando el borde, no con un supuesto" if es
                                  else f"{asm}: GAP-SCOPE closes by confirming the border, not with an assumption")
        if _status(by_gap[gap_id]) == "CLOSED" or gap_id in taken:
            raise AssumptionError(f"{asm}: {gap_id} ya está cerrada; un supuesto no reemplaza una decisión" if es
                                  else f"{asm}: {gap_id} is already closed; an assumption does not replace a decision")
        taken.add(gap_id)
    rows = sanitize_payload(base, validated)
    meta = {row["id"]: {"validate_with": extra.get(row["id"]) or row["owner"], "gap": row.get("closes_gap", ""),
                        "origin": "assume", "reason": "", "decided_at": ""} for row in rows}
    meta = sanitize_payload(base, meta)
    result = register_change_assumptions(project_id, change_id, rows, meta)
    if result["accepted"]:
        folder = base / "01_discovery" / change_id / "assumptions"
        folder.mkdir(parents=True, exist_ok=True)
        archive_payload(base, Path(source), unique_path(folder / f"{Path(source).stem}.json"))
    links = {row["closes_gap"]: (row["id"], meta[row["id"]]["validate_with"])
             for row in rows if row["id"] in result["accepted"] and row.get("closes_gap")}
    closed = close_gaps_as_assumed(project_id, change_id, links) if links else []
    summary = summarize_assumptions(load_change_assumptions(project_id, change_id))
    message = (f"{change_id}: {len(result['accepted'])} supuesto(s) registrado(s); {len(closed)} pregunta(s) cerrada(s) como supuesto"
               if es else
               f"{change_id}: {len(result['accepted'])} assumption(s) registered; {len(closed)} question(s) closed as an assumption")
    return {"project_id": project_id, "change_id": change_id, "action": "assume",
            "path": change_assumptions_path(base, change_id).as_posix(),
            "accepted": result["accepted"], "skipped_duplicates": result["skipped"], "closed_gaps": closed,
            "assumption_summary": summary, "next_step": change_next_step(project_id, change_id), "message": message}


def set_change_assumption_status(project_id: str, change_id: str, assumption_id: str, action: str,
                                 reason: str) -> dict[str, Any]:
    """Validate (the closure stays, as an answer) or invalidate (the question opens again) an assumption."""
    from .change_coherence import refresh_coherence
    from .changes import change_language, get_change, list_changes
    from .crosses.record import _save_change_gaps
    from .readiness_verdict import change_next_step

    base = workspace_path(project_id)
    change = get_change(project_id, change_id)
    language = change_language(project_id, change)
    es = _es(language)
    if action not in ("validate", "invalidate"):
        raise InputError(f"unknown assumption action {action!r}")
    reason = " ".join(str(reason or "").split())
    if not reason:
        raise InputError("--validate/--invalidate necesita --reason con el porqué" if es
                         else "--validate/--invalidate needs --reason with the why")
    asm = str(assumption_id).strip().upper()
    rows = load_change_assumptions(project_id, change_id)
    row = next((r for r in rows if r["id"] == asm), None)
    if row is None:
        raise InputError(f"{asm} no es un supuesto de {change_id}" if es else f"{asm} is not an assumption of {change_id}")
    current = str(row.get("status", "")).upper()
    if current != "ASSUMED":
        raise InputError(f"{asm} ya está {current}" if es else f"{asm} is already {current}")
    gap_id = row["gap"]
    path, gaps = _gap_rows(project_id, change_id)
    gap = next((g for g in gaps if str(g.get("id")) == gap_id), None) if gap_id else None
    if gap is not None and _status(gap) == "CLOSED" and _closure(gap) == ASSUMED_CLOSURE:
        if action == "validate":
            gap["closure_reason"] = "answered"
            gap["resolution_note"] = (f"supuesto {asm} validado: {reason}" if es else f"assumption {asm} validated: {reason}")
        else:
            previous = f"{_closure(gap)}: {gap.get('resolution_note', '')}".strip(": ")
            gap["status"] = "OPEN"
            gap["resolution_note"] = f"reopened: {asm} invalidated; previous closure kept: {previous}"
            gap.pop("closure_reason", None)
        _save_change_gaps(project_id, change_id, path, gaps)
        refresh_coherence(project_id, change_id)
    row["status"] = "VALIDATED" if action == "validate" else "INVALIDATED"
    meta = _read_meta(base, change_id)
    meta.setdefault(asm, {"validate_with": row["validate_with"], "gap": gap_id, "origin": row["origin"]})
    meta[asm].update(reason=reason, decided_at=utc_now())
    _persist(project_id, change_id, rows, meta)
    _, after = _gap_rows(project_id, change_id)
    now = next((g for g in after if str(g.get("id")) == gap_id), None) if gap_id else None
    counts = dict(list_changes(project_id)[change_id].get("gap_counts") or {})
    message = (f"{change_id}: {asm} {'validado' if action == 'validate' else 'invalidado'}"
               if es else f"{change_id}: {asm} {'validated' if action == 'validate' else 'invalidated'}")
    from . import decision_conflicts

    conflicts = decision_conflicts.refresh_decision_conflicts(project_id, change_id)  # IMP-414: a validated answer is a decision to compare
    counts = dict(list_changes(project_id)[change_id].get("gap_counts") or {})
    return {"project_id": project_id, "change_id": change_id, "action": action, "assumption_id": asm,
            "gap": gap_id, "gap_status": _status(now) if now else "", "gap_counts": counts,
            "next_step": change_next_step(project_id, change_id), "message": message,
            **({"decision_conflicts": conflicts["opened"]} if conflicts["opened"] else {}),
            **({"conflicts_retired": conflicts["retired"]} if conflicts["retired"] else {})}


_HEADING = re.compile(r"^###\s+GAP-[A-Z0-9-]+", re.M)
_QUOTED = re.compile(r'"([^"]+)"|«([^»]+)»|“([^”]+)”')
_RISK_BY_SEVERITY = {"critical": "high", "high": "high", "medium": "med", "low": "low"}


def _normal_status(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def without_assumption_blocks(text: str) -> str:
    """The text minus the `### GAP-…` blocks whose decision status is `supuesto`: their wording ("a validar") is the
    assumption's own, not a claim that the file is not validated. The other blocks stay as they are."""
    starts = [m.start() for m in _HEADING.finditer(text)]
    if not starts:
        return text
    kept = [text[: starts[0]]]
    for index, start in enumerate(starts):
        end = starts[index + 1] if index + 1 < len(starts) else len(text)
        block = text[start:end]
        if _normal_status(extract_field(block, ("Estado de decisión", "Decision status"))) not in SUPUESTO_STATUSES:
            kept.append(block)
    return "".join(kept)


def prepare_response_assumptions(project_id: str, change_id: str, responses: dict, gaps: list[dict],
                                 exclude: Path, language: str) -> dict:
    """Bridge: each `supuesto` response with a substantive answer becomes an ASM row (validated like `/assume --change`).

    Marks the response with `assumption_id` and `assumption_note`, or with `assumption_error` when the quote is not
    found in a local source (the question then stays ANSWERED). Returns `{"rows", "meta", "links"}`."""
    from .gap_resolution import AGENT_OWNER_TOKENS, UNNAMED_BA, _mentions_any, is_substantive_answer
    from .lens_registry import known_lenses

    es = _es(language)
    base = workspace_path(project_id)
    by_id = {str(g.get("id")): g for g in gaps}
    grounding = assumption_grounding_text(base, exclude=(*change_grounding_exclusions(base, change_id), exclude))
    known = {row["id"]: str(row.get("status", "")).upper() for row in load_change_assumptions(project_id, change_id)}
    lenses = known_lenses()
    rows: list[dict] = []
    meta: dict[str, dict] = {}
    links: dict[str, tuple[str, str]] = {}
    for gap_id, response in responses.items():
        if _normal_status(response.get("decision_status", "")) not in SUPUESTO_STATUSES:
            continue
        answer = str(response.get("answer", "")).strip()
        gap = by_id.get(gap_id)
        if gap is None or not is_substantive_answer(answer):
            continue
        asm = "ASM-" + gap_id[4:]
        # IMP-412 final review (C1/I1): a rerun never re-closes, reopens or downgrades; it only says why nothing moved
        if known.get(asm) in ("VALIDATED", "INVALIDATED"):
            state = known[asm]
            word = "validado" if state == "VALIDATED" else "invalidado"
            response["assumption_skip"] = (
                f"{asm} ya {word} ({state}): el supuesto no vuelve a cerrar la pregunta; para otro supuesto, otro id o una decisión" if es
                else f"{asm} is already {state}: the assumption does not close the question again; use another id or a decision")
            continue
        if _status(gap) == "CLOSED" and _closure(gap) != ASSUMED_CLOSURE:
            response["assumption_skip"] = ("la pregunta ya está cerrada; un supuesto no reemplaza una decisión" if es
                                           else "the question is already closed; an assumption does not replace a decision")
            continue
        owner = str(response.get("owner", "")).strip()
        if not owner or _mentions_any(owner.lower(), AGENT_OWNER_TOKENS):
            owner = UNNAMED_BA["es" if es else "en"]
        lens = str(gap.get("lens", "")).strip("`").strip().lower()
        validate_with = str(response.get("validates", "")).strip() or owner
        row = {"id": asm, "lens": lens if lens in lenses else "product", "statement": answer, "owner": owner,
               "risk": _RISK_BY_SEVERITY.get(str(gap.get("severity", "")).strip("`").strip().lower(), "med"),
               "uncertainty": "med", "justification": literal_quote(str(response.get("evidence", ""))),
               "closes_gap": gap_id}
        try:
            if not row["justification"]:
                raise AssumptionError("no literal quote")
            (valid,) = validate_assumptions({"assumptions": [row]}, grounding)
        except AssumptionError:
            response["assumption_error"] = (
                f"el supuesto necesita en `Evidencia o referencia` una cita literal (entre comillas) de al menos {MIN_QUOTE_WORDS} palabras de una fuente local; sin cita queda ANSWERED"
                if es else
                f"the assumption needs a literal quote (in quotation marks) of at least {MIN_QUOTE_WORDS} words from a local source in `Evidence or reference`; without one it stays ANSWERED")
            continue
        response["assumption_id"] = asm
        response["assumption_note"] = assumed_note(asm, validate_with, language)
        rows.append(valid)
        meta[asm] = {"validate_with": validate_with, "gap": gap_id, "origin": "response", "reason": "", "decided_at": ""}
        links[gap_id] = (asm, validate_with)
    return {"rows": rows, "meta": meta, "links": links}


def open_change_assumptions(project_id: str, change_id: str) -> list[dict]:
    """The change's assumptions still to validate (`ASSUMED`); empty when the change has no register."""
    return [row for row in load_change_assumptions(project_id, change_id) if str(row.get("status", "")).upper() == "ASSUMED"]


def change_assumption_summary(project_id: str, change_id: str) -> dict[str, Any] | None:
    """`{"open", "by_domain", "ids"}` of the change's register, or None when the change has none."""
    if not change_assumptions_path(workspace_path(project_id), change_id).exists():
        return None
    open_rows = open_change_assumptions(project_id, change_id)
    by_domain: dict[str, int] = {}
    for row in open_rows:
        by_domain[row["validate_with"]] = by_domain.get(row["validate_with"], 0) + 1
    return {"open": len(open_rows), "by_domain": by_domain, "ids": [row["id"] for row in open_rows]}
