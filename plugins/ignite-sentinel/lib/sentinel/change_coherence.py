"""IMP-410 (H27 inc 3): the lens view of a change and the deterministic checks of IMP-260 over it.

The project applies IMP-260 to `02_requirements/project-brief.md`; a change has no such brief of its
own, so its request, border and baseline facts are placed at the v2 places (`coherence_brief_inputs`),
rendered with the project's compiler and read by the same rules (`run_cross_checks(only=...)`).

Everything lives under `01_discovery/CHG-NNN/coherence/`: `view.md` and `checks.json` (this module),
`coherence.json` and `coherence.md` (the BA's confirmed reading, recorded in the registry).
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

from .core.io import read_json, write_json, write_text
from .errors import GateRefusal, InputError
from .workspace import workspace_path

CHANGE_CROSS_CHECKS = ("roles_named_alike", "error_codes_have_text", "excluded_transitions_have_codes",
                       "rules_have_steps", "flags_in_parameters", "events_feed_metrics", "training_has_item")


def coherence_dir(base: Path, change_id: str) -> Path:
    return base / "01_discovery" / change_id / "coherence"


def coherence_ready(project_id: str, change_id: str) -> bool:
    """The lens view is worth reading once the border is settled and the cross-reads and new surfaces are decided."""
    from .changes import get_change
    from .crosses.state import cross_status
    from .crosses.surfaces import new_surface_candidates

    if get_change(project_id, change_id).get("round") == "scope":
        return False
    if cross_status(project_id, change_id)["missing"]:
        return False
    return all(item["decision"] is not None for item in new_surface_candidates(project_id, change_id))


def coherence_view(project_id: str, change_id: str) -> dict[str, Any]:
    """{text, fingerprint, unplaced}: the change seen by lenses and the hash of what it is made of."""
    from .compilers.brief_v2 import render_brief_v2
    from .compilers.change_deliverable import coherence_brief_inputs
    from .crosses.state import crosses_fingerprint

    inputs, unplaced = coherence_brief_inputs(project_id, change_id)
    text = render_brief_v2(inputs)[0]
    payload = json.dumps({"facts": inputs.place_facts, "crosses": crosses_fingerprint(project_id, change_id)},
                         sort_keys=True, ensure_ascii=False)
    return {"text": text, "fingerprint": hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16], "unplaced": unplaced}


_FINGERPRINTS: dict[tuple[str, str], tuple[str, str]] = {}


def _inputs_stamp(project_id: str, change_id: str) -> str:
    """A cheap stamp of everything the lens view reads (sources, discovery files, workspace state), without reading it."""
    from .core.paths import state_path

    base = workspace_path(project_id)
    skip = coherence_dir(base, change_id)
    items: list[tuple[str, int, int]] = []
    for root in (base / "00_raw", base / "01_discovery"):
        for folder, dirs, files in os.walk(root):
            if Path(folder) == skip:
                dirs[:] = []
                continue
            for name in files:
                try:
                    info = os.stat(os.path.join(folder, name))
                except OSError:
                    continue
                items.append((os.path.join(folder, name), info.st_size, info.st_mtime_ns))
    try:
        info = os.stat(state_path(project_id))
        items.append(("state", info.st_size, info.st_mtime_ns))
    except OSError:
        pass
    return hashlib.sha256(json.dumps(sorted(items)).encode("utf-8")).hexdigest()


def view_fingerprint(project_id: str, change_id: str, persist: bool = False) -> str:
    """The fingerprint of the lens view; the view is rendered again only when the stamp of its inputs moved (IMP-410 I3).

    IMP-435 (C-06): `fingerprint.json` is a cache that only `/self-review --crosses` and `/cross` write (`persist=True`);
    a read (`/status`, `/next`, `/view`, `/dashboard`) computes the fingerprint in memory and writes nothing."""
    base = workspace_path(project_id)
    folder = coherence_dir(base, change_id)
    stamp = _inputs_stamp(project_id, change_id)
    key = (str(base), change_id)
    cached = _FINGERPRINTS.get(key)
    stored = read_json(folder / "fingerprint.json", {})
    stored_current = isinstance(stored, dict) and stored.get("stamp") == stamp and bool(stored.get("fingerprint"))
    if cached and cached[0] == stamp:
        fingerprint = cached[1]
    elif stored_current:
        fingerprint = str(stored["fingerprint"])
    else:
        fingerprint = coherence_view(project_id, change_id)["fingerprint"]
    if persist and folder.is_dir() and not (stored_current and stored.get("fingerprint") == fingerprint):
        write_json(folder / "fingerprint.json", {"stamp": stamp, "fingerprint": fingerprint})
    _FINGERPRINTS[key] = (stamp, fingerprint)
    return fingerprint


def _checks_file(base: Path, change_id: str) -> dict[str, Any]:
    found = read_json(coherence_dir(base, change_id) / "checks.json", {})
    return found if isinstance(found, dict) else {}


def refresh_coherence(project_id: str, change_id: str, persist: bool = False) -> dict[str, Any] | None:
    """Write `view.md` and `checks.json` when what they come from changed; None while the change is not ready."""
    from .cross_checks import run_cross_checks

    if not coherence_ready(project_id, change_id):
        return None
    base = workspace_path(project_id)
    folder = coherence_dir(base, change_id)
    recorded = _checks_file(base, change_id)
    fingerprint = view_fingerprint(project_id, change_id, persist=persist)
    if recorded.get("fingerprint") != fingerprint or not (folder / "view.md").is_file():
        view = coherence_view(project_id, change_id)
        fingerprint = view["fingerprint"]
        checks = run_cross_checks(view["text"], only=CHANGE_CROSS_CHECKS)
        write_text(folder / "view.md", view["text"])
        write_json(folder / "checks.json", {"fingerprint": view["fingerprint"], "checks": checks,
                                            "unplaced": view["unplaced"]})
        recorded = _checks_file(base, change_id)
    return {"view_path": (folder / "view.md").as_posix(), "fingerprint": fingerprint,
            "checks": recorded.get("checks", []), "unplaced": recorded.get("unplaced", [])}


def coherence_state(project_id: str, change_id: str) -> dict[str, Any]:
    """missing (nothing recorded), stale (the change moved after it), done or waived."""
    base = workspace_path(project_id)
    folder = coherence_dir(base, change_id)
    record = read_json(folder / "coherence.json", None)
    record = record if isinstance(record, dict) else None
    if record is None and not coherence_ready(project_id, change_id):
        # nothing recorded and not ready to read: nothing to render
        return {"state": "missing", "view_current": False, "fingerprint": "", "recorded_fingerprint": "",
                "checks": {"pass": 0, "warn": 0, "skip": 0, "issues": []}}
    current = view_fingerprint(project_id, change_id)
    checks_file = _checks_file(base, change_id)
    recorded = str((record or {}).get("fingerprint") or "")
    if record is None:
        state = "missing"
    elif recorded != current:
        state = "stale"
    else:
        state = "waived" if record.get("status") == "waived" else "done"
    results = checks_file.get("checks") or []
    counts = {"pass": 0, "warn": 0, "skip": 0}
    issues: list[str] = []
    for result in results:
        counts[str(result.get("status", "")).lower()] = counts.get(str(result.get("status", "")).lower(), 0) + 1
        issues.extend(str(i) for i in result.get("issues") or [])
    return {
        "state": state,
        "view_current": (folder / "view.md").is_file() and checks_file.get("fingerprint") == current,
        "fingerprint": current,
        "recorded_fingerprint": recorded,
        "checks": {**counts, "issues": issues},
    }


# --- IMP-410 task 5: the BA's confirmed reading of the lens crosses --------------------------------------


class CoherenceError(InputError):
    pass


def locate_in_requests(project_id: str, change_id: str, quote: str,
                       texts: dict[str, tuple[str, str]] | None = None) -> dict | None:
    """The citation of a quote in the current requests of the change (side `pedido`, its F-NN and line), or None."""
    from .crosses.claims import locate_quote
    from .extraction.inventory import _read_text, _row_path, pedido_rows

    base = workspace_path(project_id)
    cache = texts if texts is not None else {}
    for row in pedido_rows(project_id, change_id):
        source_id = str(row["id"])
        if source_id not in cache:
            path = _row_path(row)
            cache[source_id] = (_read_text(base, path) or "", Path(path).suffix)
        text, suffix = cache[source_id]
        found = locate_quote(text, suffix, quote) if text else None
        if found:
            return {"side": "pedido", "source_id": source_id, "line": found["line"],
                    "quote": " ".join(str(quote).split())}
    return None


def coherence_citations(project_id: str, change_id: str, cross: dict,
                        texts: dict[str, tuple[str, str]] | None = None) -> list[dict]:
    """The citations of one cross of `coherence.json`: each of its `a`/`b` quotes that sits in the request."""
    found: list[dict] = []
    for side in ("a", "b"):
        part = cross.get(side)
        if isinstance(part, dict) and part.get("quote"):
            cite = locate_in_requests(project_id, change_id, str(part["quote"]), texts)
            if cite:
                found.append(cite)
    return found


def render_coherence_report(record: dict, language: str) -> str:
    es = language == "es"
    cid = record.get("change_id", "")
    done = record.get("status") != "waived"
    lines = [f"# Coherencia entre lentes — {cid}" if es else f"# Coherence between lenses — {cid}", ""]
    status = ("registrada" if done else "descartada") if es else ("recorded" if done else "waived")
    lines += [f"- {'Estado' if es else 'Status'}: {status}", ""]
    lines += ["## Chequeos deterministas" if es else "## Deterministic checks", ""]
    results = [r for r in record.get("checks") or [] if isinstance(r, dict)]
    for result in results:
        if str(result.get("status", "")).upper() == "WARN":
            for issue in result.get("issues") or [""]:
                lines.append(f"- WARN {result.get('id', '')}: {issue}")
    others = {s: sum(1 for r in results if str(r.get("status", "")).upper() == s) for s in ("PASS", "SKIP")}
    lines += [f"- PASS {others['PASS']} · SKIP {others['SKIP']}", ""]
    lines += ["## Cruces semánticos" if es else "## Semantic crosses", ""]
    if not done:
        lines.append(f"- {'Motivo del descarte' if es else 'Reason for the waiver'}: {record.get('reason', '')}")
    elif not record.get("crosses"):
        lines.append("- Leído sin cruces." if es else "- Read, no crosses.")
    for cross in record.get("crosses") or []:
        a = cross.get("a") or {}
        open_q, close_q = ("«", "»") if es else ("“", "”")
        side = f"§{a.get('place', '')} {open_q}{' '.join(str(a.get('quote', '')).split())}{close_q}"
        if cross.get("kind") == "conflict":
            b = cross.get("b") or {}
            other = f"§{b.get('place', '')} {open_q}{' '.join(str(b.get('quote', '')).split())}{close_q}"
        else:
            other = f"§{cross.get('missing_in', '')} ({'falta' if es else 'missing'})"
        lines.append(f"- {cross.get('gap', '')} {cross.get('rule', '')} ({cross.get('kind', '')}) {side} ↔ {other}")
    return "\n".join(lines) + "\n"


def _write_record(project_id: str, change_id: str, record: dict, language: str) -> None:
    from .decision_memory import index_change_decisions

    folder = coherence_dir(workspace_path(project_id), change_id)
    write_json(folder / "coherence.json", record)
    write_text(folder / "coherence.md", render_coherence_report(record, language))
    index_change_decisions(project_id, change_id)


def _checks_now(project_id: str, change_id: str) -> tuple[dict[str, Any], str]:
    """The refreshed view and its text; a gate refusal when the change is not ready."""
    refreshed = refresh_coherence(project_id, change_id)
    if refreshed is None:
        raise CoherenceError("coherence is not ready", gate=True)
    return refreshed, Path(refreshed["view_path"]).read_text(encoding="utf-8")


def record_change_coherence(project_id: str, change_id: str, source: Path) -> dict[str, Any]:
    from .agent_sweep import log_payload_findings, payload_cleaner, record_sweep
    from .changes import change_language, get_change
    from .core.text import unique_path
    from .core.time import utc_now
    from .cross_review import validate_crosses
    from .crosses.record import _next_number, add_change_gaps
    from .payload_hygiene import sanitize_payload
    from .prior_decisions import load_priors

    es = change_language(project_id, get_change(project_id, change_id)) == "es"
    language = "es" if es else "en"
    base = workspace_path(project_id)
    source = Path(source)
    payload = read_json(source, None)
    if not isinstance(payload, dict):
        raise CoherenceError("El archivo de coherencia tiene que ser un objeto JSON." if es
                             else "The coherence file must be a JSON object.")
    refreshed, view_text = _checks_now(project_id, change_id)
    crosses = payload.get("crosses")
    accepted: list[dict] = []
    counts = {"conflict": 0, "missing": 0}
    if not (isinstance(crosses, list) and not crosses):
        result = validate_crosses(view_text, payload, clean=payload_cleaner(base))
        if result["rejected"]:
            head = "Cruces rechazados" if es else "Crosses rejected"
            reasons = sanitize_payload(base, result["rejected"], verbatim_keys=("reason",))
            raise CoherenceError(f"{head}:\n- " + "\n- ".join(
                f"#{r['index']} {r.get('rule', '?')}: {r['reason']}" for r in reasons))
        accepted, counts = result["accepted"], result["counts"]
    log_payload_findings(base, source)
    clean_payload = sanitize_payload(base, payload)
    texts: dict[str, tuple[str, str]] = {}
    candidates: dict[str, dict] = {}
    entries: list[dict] = []
    if accepted:
        # accepted keeps the order of the payload's valid items; every item was valid (nothing was rejected)
        for gap, original, cross in zip(accepted, payload["crosses"], clean_payload["crosses"]):
            cites = coherence_citations(project_id, change_id, original, texts)
            candidates[gap["id"]] = {"id": gap["id"], "citations": cites, "sources": [], "text": gap["description"]}
            entry = {"rule": str(cross.get("rule", "")), "kind": str(cross.get("kind", "")).lower(),
                     "a": cross.get("a"), "gap": gap["id"]}
            if entry["kind"] == "conflict":
                entry["b"] = cross.get("b")
            else:
                entry["missing_in"] = cross.get("missing_in")
            entries.append(entry)
    opened = add_change_gaps(project_id, change_id, accepted, candidates) if accepted else []
    submitted = coherence_dir(base, change_id) / "submitted"
    target = unique_path(submitted / f"{_next_number(submitted):03d}-{source.name}")
    write_text(target, json.dumps(clean_payload, ensure_ascii=False, indent=2) + "\n")
    record = {
        "schema_version": 1, "change_id": change_id, "status": "done", "fingerprint": refreshed["fingerprint"],
        "recorded_at": utc_now(), "submitted": target.relative_to(base).as_posix(), "counts": counts,
        "gaps": [e["gap"] for e in entries], "crosses": entries, "checks": refreshed["checks"],
    }
    record_sweep(base, "cross-review", payload, opened)
    _write_record(project_id, change_id, record, language)
    priors = load_priors(base, change_id)
    return {"counts": counts, "gaps_opened": opened,
            "pre_decided": [g for g in opened if priors.get(g, {}).get("match") == "linked"]}


def skip_change_coherence(project_id: str, change_id: str, reason: str) -> dict[str, Any]:
    from .changes import change_language, get_change
    from .core.time import utc_now

    es = change_language(project_id, get_change(project_id, change_id)) == "es"
    if not (reason or "").strip():
        raise InputError(
            "--skip necesita --reason con el porqué: sin motivo no hay descarte" if es
            else "--skip needs --reason with the why: no reason, no waiver",
            next_step=f'/self-review {project_id} --crosses --change {change_id} --skip --reason "…"')
    refreshed, _text = _checks_now(project_id, change_id)
    record = {"schema_version": 1, "change_id": change_id, "status": "waived", "reason": reason.strip(),
              "waived_at": utc_now(), "fingerprint": refreshed["fingerprint"], "checks": refreshed["checks"]}
    _write_record(project_id, change_id, record, "es" if es else "en")
    return {"counts": {}, "gaps_opened": [], "pre_decided": []}


def run_change_coherence(project_id: str, change_id: str, source: str | None, skip: bool,
                         reason: str | None) -> dict[str, Any]:
    from .changes import change_language, get_change
    from .readiness_verdict import change_next_step

    es = change_language(project_id, get_change(project_id, change_id)) == "es"
    if not coherence_ready(project_id, change_id):
        raise GateRefusal(
            f"Terminá primero los cruces de {change_id}: la coherencia lee el pedido, el borde y las superficies decididas" if es
            else f"Finish the cross-reads of {change_id} first: the coherence reads the request, the border and the decided surfaces",
            next_step=change_next_step(project_id, change_id)["command"])
    action: str = "status"
    outcome: dict[str, Any] = {"counts": {}, "gaps_opened": [], "pre_decided": []}
    if source:
        action, outcome = "crosses", record_change_coherence(project_id, change_id, Path(source))
    elif skip:
        action, outcome = "skip", skip_change_coherence(project_id, change_id, reason or "")
    refreshed = refresh_coherence(project_id, change_id, persist=True) or {}
    state = coherence_state(project_id, change_id)
    view_path = refreshed.get("view_path", "")
    if action == "crosses":
        counts = outcome["counts"]
        opened = len(outcome["gaps_opened"])
        message = (f"{change_id}: coherencia registrada (conflictos {counts['conflict']}, contrapartes faltantes "
                   f"{counts['missing']}); {opened} pregunta(s) nueva(s)" if es
                   else f"{change_id}: coherence recorded (conflicts {counts['conflict']}, missing counterparts "
                        f"{counts['missing']}); {opened} new question(s)")
    elif action == "skip":
        why = (reason or "").strip()
        message = f"{change_id}: coherencia descartada: {why}" if es else f"{change_id}: coherence waived: {why}"
    else:
        warn = state["checks"]["warn"]
        message = (f"{change_id}: vista por lentes en {view_path}; chequeos: {warn} advertencia(s)" if es
                   else f"{change_id}: lens view at {view_path}; checks: {warn} warning(s)")
    return {
        "project_id": project_id, "change_id": change_id, "action": action, "view_path": view_path,
        "checks": state["checks"], "counts": outcome["counts"], "gaps_opened": outcome["gaps_opened"],
        "pre_decided": outcome["pre_decided"], "state": state["state"],
        "next_step": change_next_step(project_id, change_id), "message": message,
    }
