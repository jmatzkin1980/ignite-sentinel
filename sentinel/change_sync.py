"""H27 inc 6a: what a new source of a change touches.

A new source (a version of the request, a prototype, a baseline) does not send the BA back through
every cross-read. The claims whose quotes are still verbatim in the sources now current are carried
(their `source_id` moves, their question and its answer stay); the ones whose quote no longer fits, and
the elements of the request that are new or changed, are marked in a `pending_delta` of the cross-read
record, and `01_discovery/<CHG>/sync_report.md` lists both with the commands for just that part.

This module is not `sync.py`, which is the project's `/sync` event in `07_changes`.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .changes import _squash, change_language, get_change
from .core.io import write_json, write_text
from .core.time import utc_now
from .crosses import cross_path
from .crosses.claims import TAG_NAMES, rebase_claim
from .crosses.record import claims_hash, load_cross, source_basis
from .crosses.state import KIND_LABELS, _baseline_state, write_cross_report
from .errors import InputError
from .extraction.inventory import _row_path, build_inventory, inventory_path, parse_request_elements, row_text
from .source_registry import row_role
from .sources import load_source_manifest
from .workspace import workspace_path

# the kinds a source of each role can touch
ROLE_KINDS = {"pedido": ("diseno", "contradicciones"), "diseno_nuevo": ("diseno",)}

HEADINGS = {
    "es": {
        "title": "# Sync del cambio {cid}",
        "carried": "## Afirmaciones que siguen vigentes",
        "reread": "## Afirmaciones a releer",
        "elements": "## Elementos nuevos, cambiados o quitados",
        "commands": "## Próximos comandos",
        "empty": "_sin novedad_",
        "source": "Fuente nueva",
        "version": "versión de",
        "role": "rol",
        "note": "Nota",
        "new": "Nuevos", "changed": "Cambiados", "removed": "Quitados",
        "stale": "Propuestas de extracción desactualizadas",
        "file": "ARCHIVO",
    },
    "en": {
        "title": "# Change sync {cid}",
        "carried": "## Claims carried",
        "reread": "## Claims to re-read",
        "elements": "## New, changed or removed elements",
        "commands": "## Next commands",
        "empty": "_nothing new_",
        "source": "New source",
        "version": "version of",
        "role": "role",
        "note": "Note",
        "new": "New", "changed": "Changed", "removed": "Removed",
        "stale": "Stale extraction proposals",
        "file": "FILE",
    },
}


def _row(project_id: str, source_id: str) -> dict | None:
    for row in load_source_manifest(project_id).get("registry", []):
        if str(row.get("id")) == source_id:
            return row
    return None


def _shas(base: Path, row: dict | None) -> dict[str, str]:
    """The (id, sha) of every element of a source row; empty when there is no row or it cannot be read."""
    if row is None:
        return {}
    text = row_text(base, row)
    if text is None:
        return {}
    elements = parse_request_elements(text, str(row["id"]), _row_path(row))
    return {str(e["id"]): str(e["sha"]) for e in elements}


def _delta(before: dict[str, str], after: dict[str, str]) -> tuple[dict[str, list[str]], list[str], list[str]]:
    """The delta, and the new and removed ids that are only a rename (the same text under another id)."""
    new = [i for i in after if i not in before]
    removed = [i for i in before if i not in after]
    changed = [i for i in after if i in before and after[i] != before[i]]
    gone = {before[i] for i in removed}
    appeared = {after[i] for i in new}
    renamed_new = [i for i in new if after[i] in gone]
    renamed_removed = [i for i in removed if before[i] in appeared]
    return {"new": new, "changed": changed, "removed": removed}, renamed_new, renamed_removed


def element_delta(project_id: str, change_id: str, previous_id: str | None, new_id: str) -> dict[str, list[str]]:
    """The elements of the new request source against the previous one, by id and text hash.

    It reads the two rows, so it works before the extraction exists. `previous_id=None`: all new.
    """
    base = workspace_path(project_id)
    before = _shas(base, _row(project_id, previous_id)) if previous_id else {}
    delta, _, _ = _delta(before, _shas(base, _row(project_id, new_id)))
    return delta


def _unique(items: list[Any]) -> list[Any]:
    return list(dict.fromkeys(items))


def _touch_kind(project_id: str, change_id: str, kind: str, record: dict, current: set[str]) -> tuple[dict, list[int], list[int]]:
    """The record with its still-literal claims rebased, and the numbers carried and touched."""
    claims: list[dict] = []
    carried: list[int] = []
    touched: list[int] = []
    for claim in record.get("claims", []):
        stale = any(str(c.get("source_id")) not in current for c in claim.get("citations", []))
        if not stale:
            claims.append(claim)
            continue
        rebased = rebase_claim(project_id, change_id, claim, current)
        if rebased is None:
            touched.append(int(claim["n"]))
            claims.append(claim)
        else:
            carried.append(int(claim["n"]))
            claims.append(rebased)
    return {**record, "claims": claims}, carried, touched


def apply_touched_set(project_id: str, change_id: str, *, previous_id: str | None, new_id: str, note: str = "") -> dict[str, Any]:
    """Carry the claims a new source leaves verbatim, mark what it touches and write the sync report."""
    change = get_change(project_id, change_id)
    language = change_language(project_id, change)
    es = language == "es"
    file_word = HEADINGS["es" if es else "en"]["file"]
    base = workspace_path(project_id)
    row = _row(project_id, new_id)
    if row is None:
        raise InputError(f"{new_id} no es una fuente registrada" if es else f"{new_id} is not a registered source")
    role = row_role(row)
    current = {str(r.get("id")) for r in load_source_manifest(project_id).get("registry", [])
               if r.get("validity", "current") == "current"}

    extraction: dict[str, Any] = {"new": [], "changed": [], "removed": [], "stale_proposals": [], "inventory": "absent"}
    trigger: list[str] = []
    gone: list[str] = []
    if role == "pedido":
        before = _shas(base, _row(project_id, previous_id)) if previous_id else {}
        after = _shas(base, row)
        found, renamed_new, renamed_removed = _delta(before, after)
        extraction.update(found)
        trigger = [i for i in [*found["new"], *found["changed"]] if i not in renamed_new]
        gone = [i for i in found["removed"] if i not in renamed_removed]
        if inventory_path(base, change_id).exists():
            built = build_inventory(project_id, change_id)
            extraction["stale_proposals"] = list(built.get("stale_proposals") or [])
            extraction["inventory"] = "rebuilt"

    crosses: dict[str, dict[str, Any]] = {}
    commands: list[str] = []
    baseline = _baseline_state(project_id, base, change, None)
    baseline_stale = baseline["state"] == "stale"
    baseline_command = f"/harvest {project_id} --source {file_word} --change {change_id}" if baseline_stale else None
    if baseline_command:
        commands.append(baseline_command)

    for kind in ROLE_KINDS.get(role or "", ()):
        record = load_cross(base, change_id, kind)
        if not record or record.get("status") != "done":
            continue  # missing, waived or not applicable: the cross-read is not carried
        updated, carried, touched = _touch_kind(project_id, change_id, kind, record, current)
        old = record.get("pending_delta") if isinstance(record.get("pending_delta"), dict) else None
        if role == "pedido":
            wanted = bool(touched or trigger)
        else:
            known = [str(i) for i in (record.get("basis") or {}).get("diseno") or []]
            # a new version of the design may add screens the old claims never covered, and the design has no
            # element diff to prove otherwise: it is always read again, whatever rebased
            wanted = bool(touched or previous_id is not None or new_id not in known)
        if wanted or old:
            before_old = old or {}
            pending = {
                "source_id": new_id,
                "touched": sorted({*[int(n) for n in before_old.get("touched") or []], *touched}),
                "elements": _unique([*(before_old.get("elements") or []), *trigger]),
                "removed": _unique([*(before_old.get("removed") or []), *gone]),
                "design": new_id if role == "diseno_nuevo" else before_old.get("design"),
                "at": utc_now(),
            }
            updated["pending_delta"] = pending
        else:
            updated.pop("pending_delta", None)
        updated["basis"] = source_basis(project_id, change_id)
        updated["claims_hash"] = claims_hash(updated["claims"], reason="")
        if updated != record:
            write_json(cross_path(base, change_id, kind), updated)
        has_delta = "pending_delta" in updated
        command = f"/cross {project_id} --change {change_id} --kind {kind} --claims {file_word} --delta" if has_delta else None
        if command:
            commands.append(command)
        crosses[kind] = {"carried": carried, "touched": touched, "delta": has_delta, "command": command}

    if role == "diseno_nuevo":
        # the internal contradictions quote only the request: a new prototype is not news to them
        record = load_cross(base, change_id, "contradicciones")
        if record and record.get("status") == "done" and record.get("basis") != source_basis(project_id, change_id):
            write_json(cross_path(base, change_id, "contradicciones"), {**record, "basis": source_basis(project_id, change_id)})

    result: dict[str, Any] = {
        "change_id": change_id, "source_id": new_id, "previous_id": previous_id, "role": role,
        "extraction": extraction, "crosses": crosses,
        "baseline": {"stale": baseline_stale, "command": baseline_command},
        "commands": commands, "note": note,
    }
    write_cross_report(project_id, change_id)
    result["report_path"] = write_sync_report(project_id, change_id, result, language).as_posix()
    return result


def write_sync_report(project_id: str, change_id: str, result: dict[str, Any], language: str) -> Path:
    """`01_discovery/<CHG>/sync_report.md`: what stays, what to re-read, what changed and what to run next."""
    lang = "es" if language == "es" else "en"
    words = HEADINGS[lang]
    base = workspace_path(project_id)
    names = TAG_NAMES[lang]
    labels = KIND_LABELS[lang]
    empty = words["empty"]
    source = f"{words['source']}: {result['source_id']}"
    if result.get("previous_id"):
        source += f" ({words['version']} {result['previous_id']})"
    if result.get("role"):
        source += f", {words['role']} {result['role']}"
    lines = [words["title"].format(cid=change_id), "", source]
    if (result.get("note") or "").strip():
        lines.append(f"{words['note']}: {_squash(result['note'])}")

    carried = [f"- {labels[kind]}: {', '.join(str(n) for n in info['carried'])}"
               for kind, info in result["crosses"].items() if info["carried"]]
    reread: list[str] = []
    for kind, info in result["crosses"].items():
        claims = {int(c["n"]): c for c in (load_cross(base, change_id, kind) or {}).get("claims", [])}
        for n in info["touched"]:
            claim = claims.get(n)
            text = f" [{names[claim['tag']]}] {_squash(claim['text'])}" if claim else ""
            reread.append(f"- {labels[kind]} {n}:{text}")
        delta = (load_cross(base, change_id, kind) or {}).get("pending_delta") or {}
        if info["delta"] and not info["touched"] and delta.get("design"):
            reread.append(f"- {labels[kind]}: {delta['design']}")
    extraction = result["extraction"]
    elements = [f"- {words[key]}: {', '.join(extraction[key])}" for key in ("new", "changed", "removed") if extraction[key]]
    if extraction.get("stale_proposals"):
        elements.append(f"- {words['stale']}: {', '.join(extraction['stale_proposals'])}")
    commands = [f"- `{c}`" for c in result["commands"]]

    for heading, body in ((words["carried"], carried), (words["reread"], reread),
                          (words["elements"], elements), (words["commands"], commands)):
        lines += ["", heading, "", *(body or [empty])]
    path = base / "01_discovery" / change_id / "sync_report.md"
    write_text(path, "\n".join(lines).rstrip() + "\n")
    return path


def _versions_of(project_id: str, change_id: str, role: str, stem: str, new_id: str) -> str | None:
    """The current row of the change with this role whose copy has the same file stem, if any."""
    change = get_change(project_id, change_id)
    held = {str(i) for i in change.get("sources") or []}
    found = None
    for row in load_source_manifest(project_id).get("registry", []):
        if str(row.get("id")) not in held or str(row.get("id")) == new_id:
            continue
        if row.get("validity", "current") != "current" or row_role(row) != role:
            continue
        if any(Path(str(p)).stem == stem for p in [*row.get("copies", []), *row.get("paths", [])]):
            found = str(row["id"])
    return found


def _refuse_event_id(project_id: str, change_id: str) -> None:
    """A CHG id that is a project /sync event in 07_changes is not an open change (decision 14)."""
    from .changes import list_changes
    from .core.graph import load_graph

    changes = list_changes(project_id)
    if change_id in changes:
        return
    for node in load_graph(project_id).get("nodes", []):
        if node.get("id") == change_id and "07_changes" in Path(str(node.get("path") or "")).parts:
            first = next(iter(changes.values()), None)
            es = (change_language(project_id, first) if first else "es") == "es"
            known = ", ".join(sorted(changes))
            if known:
                next_step = f"Cambios conocidos: {known}." if es else f"Known changes: {known}."
            else:
                next_step = (f"Abrí uno con /ingest {project_id} --source NOTA --change." if es
                             else f"Open one with /ingest {project_id} --source NOTE --change.")
            raise InputError(
                f"{change_id} es un evento de /sync del proyecto (07_changes), no un cambio abierto" if es
                else f"{change_id} is a project /sync event (07_changes), not an open change",
                next_step=next_step,
            )
    get_change(project_id, change_id)  # raises the usual refusal


def sync_change_scope(
    project_id: str,
    change_id: str,
    source: Path | None = None,
    role: str | None = None,
    supersedes: str | None = None,
    note: str = "",
) -> dict[str, Any]:
    """`/sync --change`: load the new source of a change by role, confirm its version and re-cross what it touched."""
    from .core.io import forget_read_snapshots
    from .readiness_verdict import change_next_step
    from .source_registry import ROLE_FOLDERS, mark_pending_version
    from .sources import discover_source_novelty, iter_source_files, load_source, save_source_manifest, update_source

    _refuse_event_id(project_id, change_id)
    change = get_change(project_id, change_id)
    es = change_language(project_id, change) == "es"
    if source is not None and not role:
        raise InputError(
            "/sync --change con --source necesita --role pedido|linea_de_base|plan_previo|diseno_nuevo" if es
            else "/sync --change with --source needs --role pedido|linea_de_base|plan_previo|diseno_nuevo")
    if source is None and (role or supersedes):
        raise InputError("--role y --supersedes van con --source" if es else "--role and --supersedes go with --source")
    if supersedes:
        old = _row(project_id, supersedes)
        if old is None or supersedes not in {str(i) for i in change.get("sources") or []} or row_role(old) != role:
            raise InputError(
                f"{supersedes} no es una fuente de rol {role} de {change_id}" if es
                else f"{supersedes} is not a source with role {role} in {change_id}")

    base = workspace_path(project_id)
    targets: list[tuple[Path, str]] = []
    if source is not None:
        targets.append((source, str(role)))
    else:
        for folder_role, folder in ROLE_FOLDERS.items():
            files = iter_source_files(base / folder)
            for item in discover_source_novelty(project_id, paths=files)["pending"]:
                targets.append((Path(item["path"]), folder_role))

    loaded: list[dict[str, Any]] = []
    synced: list[dict[str, Any]] = []
    for path, path_role in targets:
        result = load_source(project_id, path, path_role, change_id)
        new_id, reused = str(result["source_id"]), bool(result["reused"])
        manifest = load_source_manifest(project_id)
        row = next(r for r in manifest["registry"] if str(r["id"]) == new_id)
        if not reused and not row.get("pending_version_of"):
            previous = _versions_of(project_id, change_id, path_role, path.stem, new_id)
            if previous:
                mark_pending_version(manifest, row, previous)
                save_source_manifest(project_id, manifest)
        version_of = supersedes or row.get("pending_version_of")
        old_row = _row(project_id, str(supersedes)) if supersedes else None
        confirmed = False
        results: list[dict[str, Any]] = []
        if supersedes:
            confirmed = True
            if old_row is not None and old_row.get("validity", "current") == "current":
                # the confirmation of the version is the one place that runs the touched set
                results = list(update_source(project_id, supersedes, superseded_by=new_id,
                                             reason=_squash(note) or "/sync --change").get("sync") or [])
        elif not reused and not version_of:
            results = [apply_touched_set(project_id, change_id, previous_id=None, new_id=new_id, note=note)]
            confirmed = True
        if note.strip():
            language = change_language(project_id, get_change(project_id, change_id))
            for item in results:
                if item.get("change_id") == change_id:
                    item["note"] = note
                    write_sync_report(project_id, change_id, item, language)
        synced.extend(results)
        loaded.append({"source_id": new_id, "role": path_role, "path": result["path"], "reused": reused,
                       "version_of": str(version_of) if version_of else None, "confirmed": confirmed})

    forget_read_snapshots()
    return {"project_id": project_id, "change_id": change_id, "loaded": loaded, "sync": synced,
            "next_step": change_next_step(project_id, change_id)}
