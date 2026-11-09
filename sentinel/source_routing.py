"""IMP-250b: precedence by scope, impact matrix and closing report over the F-NN rows.

Builds on the registry of IMP-250a (`source_registry.py`). Everything here is data
plus pure functions over the manifest; `sources.py` does the IO.

- **Authority.** Every row carries an `authority`: what kind of source it is for
  precedence (minutes, API contract, example...). The bucket a file arrived in
  gives the default and a file named like an example is an `example`; a person
  corrects it with `/sources --authority`.
- **Precedence by scope, never linear.** Who governs depends on the scope of the
  clash (business, scope, to-be stack, behavior, api, compliance, legacy, design).
  The default table lives in `templates/source_routing.json`; `precedence:` in
  `sentinel.config.yaml` overrides one scope with a chain (`a > b > c`). When no
  rule settles a clash the answer is `unresolved`: the newest source never wins
  by default. An own artifact is never an authority ("echo, not authority"), and
  an example never closes a rule.
- **Impact matrix, document x section.** A new row gets one cell per document and
  section its authority routes to, with what to look for there. A person closes
  each cell as `updated` or `reviewed` (no change, with the reason). A retired
  source cascades to every document, even outside its routing radius.
- **Closing report by recipient.** ADDED / MODIFIED / REMOVED per row (the IMP-187
  vocabulary), the cells each recipient must look at, and the originals that are
  ready to delete: extraction saved, every cell closed and the row closed. The
  report never deletes anything.
"""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from .deltas import DeltaStatus
from .resources import read_package_json
from .source_registry import SourceRegistryError, ensure_registry, find_row

CELL_STATES = ("pending", "updated", "reviewed")
SCOPES = ("business", "scope", "stack_to_be", "behavior", "api", "compliance", "legacy", "design", "rule")


@lru_cache(maxsize=1)
def routing_data() -> dict[str, Any]:
    return read_package_json("templates", "source_routing.json")


def authorities() -> tuple[str, ...]:
    return tuple(routing_data()["authorities"])


def is_own_artifact_key(key: str) -> bool:
    """A path Sentinel wrote: a governed artifact folder or a generated change report."""
    return bool(re.search(routing_data()["own_artifact_path_pattern"], key.replace("\\", "/")))


def default_authority(kind: str, key: str = "") -> str:
    data = routing_data()
    if key and is_own_artifact_key(key):
        return "own_artifact"  # IMP-251: Sentinel reading itself is echo, never authority
    name = Path(key).name.lower()
    if name and re.search(data["example_name_pattern"], name):
        return "example"
    return str(data["authority_by_kind"].get(kind, "unclassified"))


def row_authority(row: dict[str, Any]) -> str:
    authority = row.get("authority")
    if authority:
        return str(authority)
    kind = str(row.get("kind", "external"))
    events = row.get("events") or []
    if kind == "external" and events and events[0].get("via") == "initial_ingested":
        kind = "client_requirement"  # /ingest takes the client requirement, wherever the file sits
    return default_authority(kind, (row.get("paths") or [""])[0])


# --- impact matrix -------------------------------------------------------------


def route_cells(authority: str) -> list[dict[str, Any]]:
    return [
        {"document": route["document"], "section": route["section"], "look_for": route["look_for"],
         "state": "pending", "reason": None, "cascade": False}
        for route in routing_data()["routes"].get(authority, [])
    ]


def seed_impact(row: dict[str, Any]) -> None:
    """Give a row its authority and matrix the first time it is seen."""
    if not row.get("authority"):
        row["authority"] = row_authority(row)
    if row.get("impact") is None:  # only a row created in this run; older rows carry a list
        row["impact"] = route_cells(row["authority"])


def set_authority(row: dict[str, Any], authority: str) -> None:
    if authority not in authorities():
        raise SourceRegistryError(f"Unknown authority {authority!r}. Use one of: {', '.join(authorities())}.")
    row["authority"] = authority
    impact = row.get("impact") or []
    if all(cell.get("state") == "pending" and not cell.get("cascade") for cell in impact):
        row["impact"] = route_cells(authority) + [cell for cell in impact if cell.get("cascade")]


def cascade_impact(row: dict[str, Any]) -> None:
    """A retired source reaches every document, even outside its routing radius."""
    present = {cell["document"] for cell in row.get("impact", [])}
    for document in routing_data()["documents"]:
        if document not in present:
            row.setdefault("impact", []).append({
                "document": document, "section": "*",
                "look_for": f"Content that relied on {row['id']}",
                "state": "pending", "reason": None, "cascade": True,
            })


def mark_cell(row: dict[str, Any], cell_ref: str, state: str, reason: str | None = None) -> dict[str, Any]:
    if state not in CELL_STATES:
        raise SourceRegistryError(f"--mark must be one of {', '.join(CELL_STATES)}.")
    document, _, section = cell_ref.partition("/")
    if not document or not section:
        raise SourceRegistryError("--cell takes DOCUMENT/SECTION, for example brief/business.")
    cell = next((item for item in row.get("impact", [])
                 if item["document"] == document and item["section"] == section), None)
    if cell is None:
        documents = routing_data()["documents"]
        if document not in documents or (section != "*" and section not in documents[document]["sections"]):
            raise SourceRegistryError(f"{row['id']} has no cell {cell_ref} and it is not a known document/section.")
        cell = {"document": document, "section": section, "look_for": "Added by hand",
                "state": "pending", "reason": None, "cascade": False}
        row.setdefault("impact", []).append(cell)
    if state == "reviewed" and not (reason or "").strip():
        raise SourceRegistryError("--mark reviewed needs --reason: say why nothing changed.")
    cell["state"] = state
    cell["reason"] = (reason or "").strip() or None
    return cell


def pending_cells(row: dict[str, Any]) -> list[dict[str, Any]]:
    return [cell for cell in row.get("impact", []) if cell.get("state") == "pending"]


def impact_pending_summary(manifest: dict[str, Any]) -> dict[str, int]:
    rows = ensure_registry(manifest).get("registry", [])
    return {row["id"]: len(pending_cells(row)) for row in rows if pending_cells(row)}


# --- precedence ----------------------------------------------------------------


def precedence_rules(config: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Default rules, with each scope in `precedence:` replaced by its chain."""
    rules = [dict(rule) for rule in routing_data()["precedence"]]
    overrides = (config or {}).get("precedence")
    if not isinstance(overrides, dict):
        return rules
    known = set(authorities())
    for scope, chain in overrides.items():
        order = [part.strip() for part in str(chain).split(">") if part.strip()]
        unknown = [name for name in order if name not in known]
        if unknown or len(order) < 2:
            raise SourceRegistryError(
                f"precedence: {scope} must be a chain of known authorities like 'minutes > interaction'; "
                f"unknown: {', '.join(unknown) or 'none'}."
            )
        rules = [rule for rule in rules if rule["scope"] != scope]
        for index, winner in enumerate(order[:-1]):
            rules.append({"id": f"CFG-{scope}-{index + 1}", "scope": scope, "winner": winner,
                          "over": order[index + 1:], "note": "Configured in sentinel.config.yaml."})
    return rules


def _beats(rule: dict[str, Any], winner: str, loser: str, scope: str) -> bool:
    if winner == loser:  # same authority on both sides is a tie, never settled by "*"
        return False
    if rule["winner"] != winner or rule["scope"] not in (scope, "*"):
        return False
    if loser in rule.get("except", []):
        return False
    return rule["over"] == "*" or loser in rule["over"]


def resolve_precedence(scope: str, candidates: list[dict[str, str]], config: dict[str, Any] | None = None) -> dict[str, Any]:
    """Which candidate governs in `scope`. Each candidate is `{"id", "authority"}`.

    The winner must beat every other candidate by some rule. Otherwise the clash is
    `unresolved` and a person decides; the newest source never wins by default.
    """
    if scope not in SCOPES:
        raise SourceRegistryError(f"Unknown scope {scope!r}. Use one of: {', '.join(SCOPES)}.")
    data = routing_data()
    excluded: list[dict[str, str]] = []
    eligible: list[dict[str, str]] = []
    for candidate in candidates:
        authority = candidate["authority"]
        if authority in data["never_authority"]:
            excluded.append({**candidate, "why": "echo: an own artifact is never an authority"})
        elif authority in data["only_in_scope"] and scope not in data["only_in_scope"][authority]:
            excluded.append({**candidate, "why": f"{authority} only has authority in {', '.join(data['only_in_scope'][authority])}"})
        else:
            eligible.append(candidate)
    result: dict[str, Any] = {"scope": scope, "winner": None, "rules": [], "excluded": excluded,
                              "opens_gap": False, "status": "unresolved"}
    if len(eligible) == 1:
        result.update(winner=eligible[0]["id"], status="resolved", rules=["only eligible source"])
        return result
    rules = precedence_rules(config)
    for candidate in eligible:
        used: list[dict[str, Any]] = []
        for other in eligible:
            if other is candidate:
                continue
            rule = next((r for r in rules if _beats(r, candidate["authority"], other["authority"], scope)), None)
            if rule is None:
                break
            used.append(rule)
        else:
            result.update(
                winner=candidate["id"], status="resolved",
                rules=sorted({rule["id"] for rule in used}),
                opens_gap=any(rule.get("opens_gap") for rule in used),
            )
            return result
    return result


def can_close_rules(authority: str) -> bool:
    return authority not in routing_data()["never_closes"]


# --- closing report ------------------------------------------------------------


def row_delta(row: dict[str, Any], manifest: dict[str, Any]) -> DeltaStatus:
    if row.get("validity") in ("retired", "expired"):
        return DeltaStatus.REMOVED
    corrects = any(other.get("superseded_by") == row["id"] for other in manifest.get("registry", []))
    if corrects or row.get("pending_version_of"):
        return DeltaStatus.MODIFIED
    return DeltaStatus.ADDED


def deletable(row: dict[str, Any], exists) -> tuple[bool, list[str]]:
    """Three conditions: extraction saved, every cell closed, row closed."""
    missing: list[str] = []
    if not any(exists(copy) for copy in row.get("copies", [])):
        missing.append("no saved extraction")
    if pending_cells(row):
        missing.append(f"{len(pending_cells(row))} cell(s) pending")
    if row.get("lifecycle") != "closed":
        missing.append("row still open")
    if not any(exists(path) for path in row.get("paths", [])):
        missing.append("original already gone")
    return (not missing, missing)


def closing_report(manifest: dict[str, Any], exists) -> dict[str, Any]:
    rows = ensure_registry(manifest).get("registry", [])
    documents = routing_data()["documents"]
    recipients: dict[str, list[dict[str, Any]]] = {}
    ready: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    for row in rows:
        delta = row_delta(row, manifest).value
        for cell in row.get("impact", []):
            recipient = documents.get(cell["document"], {}).get("recipient", "ba")
            recipients.setdefault(recipient, []).append({
                "source_id": row["id"], "delta": delta, "document": cell["document"],
                "section": cell["section"], "state": cell["state"], "reason": cell.get("reason"),
                "look_for": cell.get("look_for"),
            })
        if row.get("migrated") and not row.get("impact"):
            continue
        ok, missing = deletable(row, exists)
        entry = {"source_id": row["id"], "paths": [p for p in row.get("paths", []) if exists(p)]}
        if ok:
            ready.append(entry)
        else:
            blocked.append({**entry, "missing": missing})
    return {"recipients": recipients, "ready_to_delete": ready, "not_ready": blocked}


_REPORT = {
    "en": {
        "title": "# Closing report - {project}",
        "intro": ("GENERATED by `/sources --report`. What each recipient must look at, per source row, "
                  "with the closed vocabulary ADDED / MODIFIED / REMOVED. Nothing here is deleted."),
        "recipient": "## For {who}",
        "headers": ("Source", "Delta", "Document / section", "State", "Look for / reason"),
        "ready": "## Originals ready to delete",
        "ready_note": "Extraction saved, every cell closed and the row closed. Deleting is still your call.",
        "not_ready": "## Not ready to delete",
        "none": "- None.",
        "states": {"pending": "pending", "updated": "updated", "reviewed": "reviewed, no change"},
        "who": {"ba": "the BA", "tech_lead": "the tech lead", "product_owner": "the product owner",
                "qa": "QA", "design": "design", "client": "the client"},
    },
    "es": {
        "title": "# Reporte de cierre - {project}",
        "intro": ("GENERADO por `/sources --report`. Qué tiene que mirar cada destinatario, por fila de fuente, "
                  "con el vocabulario cerrado ADDED / MODIFIED / REMOVED (agregado / modificado / quitado). "
                  "Acá no se borra nada."),
        "recipient": "## Para {who}",
        "headers": ("Fuente", "Delta", "Documento / sección", "Estado", "Qué buscar / motivo"),
        "ready": "## Originales listos para borrar",
        "ready_note": "Extracción guardada, todas las celdas cerradas y la fila cerrada. Borrar sigue siendo decisión tuya.",
        "not_ready": "## Todavía no se pueden borrar",
        "none": "- Ninguno.",
        "states": {"pending": "pendiente", "updated": "actualizada", "reviewed": "revisada sin cambio"},
        "who": {"ba": "el BA", "tech_lead": "el líder técnico", "product_owner": "el product owner",
                "qa": "QA", "design": "diseño", "client": "el cliente"},
    },
}

_MISSING_ES = {
    "no saved extraction": "sin extracción guardada",
    "row still open": "fila abierta",
    "original already gone": "el original ya no está",
}


def _esc(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ") if value not in (None, "") else "—"


def render_closing_report(project_id: str, report: dict[str, Any], language: str = "en") -> str:
    copy = _REPORT["es" if language == "es" else "en"]
    lines = [copy["title"].format(project=project_id), "", copy["intro"], ""]
    for recipient in sorted(report["recipients"]):
        lines += [copy["recipient"].format(who=copy["who"].get(recipient, recipient)), ""]
        lines.append("| " + " | ".join(copy["headers"]) + " |")
        lines.append("|" + "---|" * len(copy["headers"]))
        for item in report["recipients"][recipient]:
            note = item["reason"] if item["state"] != "pending" and item["reason"] else item["look_for"]
            lines.append("| " + " | ".join(_esc(v) for v in (
                item["source_id"], item["delta"], f"{item['document']} / {item['section']}",
                copy["states"].get(item["state"], item["state"]), note,
            )) + " |")
        lines.append("")
    lines += [copy["ready"], "", copy["ready_note"], ""]
    lines += [f"- {item['source_id']}: " + ", ".join(f"`{p}`" for p in item["paths"]) for item in report["ready_to_delete"]] or [copy["none"]]
    lines += ["", copy["not_ready"], ""]
    rows = []
    for item in report["not_ready"]:
        reasons = item["missing"]
        if language == "es":
            reasons = [_MISSING_ES.get(r, r.replace("cell(s) pending", "celda(s) pendiente(s)")) for r in reasons]
        rows.append(f"- {item['source_id']}: {'; '.join(reasons)}")
    lines += rows or [copy["none"]]
    return "\n".join(lines) + "\n"


def find_row_or_raise(manifest: dict[str, Any], source_id: str) -> dict[str, Any]:
    row = find_row(manifest, source_id)
    if row is None:
        raise SourceRegistryError(f"Unknown source row: {source_id}")
    return row
