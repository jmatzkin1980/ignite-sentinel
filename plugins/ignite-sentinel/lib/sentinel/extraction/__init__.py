"""IMP-402 (H26 inc 3): extraction of a change request, element by element, with coverage.

Everything lives under `02_requirements/CHG-NNN/extraction/` of the project workspace.
"""
from __future__ import annotations

from pathlib import Path


def extraction_dir(base: Path, change_id: str) -> Path:
    """The folder that holds a change's inventory, proposals, review and submitted sheets."""
    return base / "02_requirements" / change_id / "extraction"


def run_extract(
    project_id: str,
    change_id: str,
    proposals: str | None = None,
    confirm: str | None = None,
    confirm_item: str | None = None,
    reject_item: str | None = None,
    reason: str | None = None,
    verify: bool = False,
    sample: int | None = None,
    verify_result: str | None = None,
    delegated: bool = False,
    note: str = "",
    consolidate: str | None = None,
    confirm_replacement: str | None = None,
    keep_text: str | None = None,
    gap: str | None = None,
) -> dict:
    """The /extract command: inventory, proposals, confirmation or rejection of one change."""
    from ..changes import change_language, get_change
    from ..readiness_verdict import change_next_step
    from .confirm import confirm_item as _confirm_item
    from .confirm import confirm_proposals, reject_item as _reject_item
    from .consolidation import confirm_replacement as _confirm_replacement
    from .consolidation import keep_text as _keep_text
    from .consolidation import record_consolidation
    from .coverage import KIND_LABELS, extraction_coverage
    from .inventory import build_inventory
    from .proposals import record_proposals
    from .verify import record_verification, start_verification

    change = get_change(project_id, change_id)  # an unknown change is a GateRefusal
    lang = "es" if change_language(project_id, change) == "es" else "en"
    es = lang == "es"
    if proposals:
        result = record_proposals(project_id, change_id, Path(proposals))
    elif confirm:
        result = confirm_proposals(project_id, change_id, confirm, delegated=delegated, note=note or "")
    elif confirm_item:
        result = _confirm_item(project_id, change_id, confirm_item, delegated=delegated, note=note or "",
                               reason=reason or "")
    elif consolidate:
        result = record_consolidation(project_id, change_id, Path(consolidate))
    elif confirm_replacement:
        result = _confirm_replacement(project_id, change_id, confirm_replacement, delegated=delegated, note=note or "")
    elif keep_text:
        result = _keep_text(project_id, change_id, keep_text, gap or "", reason or "")
    elif reject_item:
        result = _reject_item(project_id, change_id, reject_item, reason or "")
    elif verify:
        result = start_verification(project_id, change_id, sample)
    elif verify_result:
        result = record_verification(project_id, change_id, Path(verify_result))
    else:
        result = build_inventory(project_id, change_id)
        from ..core.paths import workspace_path
        from .proposals import _proposals_path, write_review

        if _proposals_path(workspace_path(project_id), change_id).exists():
            write_review(project_id, change_id)  # stale and orphan elements show up in the review at once
    coverage = extraction_coverage(project_id, change_id)
    action = result.get("action")
    if action == "inventory":
        by_kind = ", ".join(
            f"{KIND_LABELS[lang].get(kind, kind)} {count}" for kind, count in (result.get("by_kind") or {}).items()
        )
        sheet = result["worksheet_path"]
        message = (
            f"{change_id}: {result['total']} elementos inventariados ({by_kind}). Planilla: `{sheet}`" if es
            else f"{change_id}: {result['total']} elements inventoried ({by_kind}). Worksheet: `{sheet}`"
        )
        split = result.get("split") or {}
        if split:
            k = sum(len(parts) for parts in split.values())
            message += (
                f"; {len(split)} sección(es) larga(s) partida(s) en {k} parte(s)" if es
                else f"; {len(split)} long section(s) split into {k} part(s)"
            )
        batches = (result.get("reading_plan") or {}).get("batches")
        if batches:
            message += (
                f"; plan de lectura: {batches} lote(s) (`reading_plan.md`)" if es
                else f"; reading plan: {batches} batch(es) (`reading_plan.md`)"
            )
    elif action == "proposals":
        n, r, f = len(result["recorded"]), len(result["rejected"]), len(result["flagged"])
        u, s = len(result.get("unchanged", [])), len(result.get("skipped", []))
        message = (
            f"{change_id}: {n} propuesta(s) registrada(s), {r} rechazada(s), {f} marcada(s), "
            f"{u} sin cambios (siguen confirmadas), {s} sin tratamiento" if es
            else f"{change_id}: {n} proposal(s) recorded, {r} rejected, {f} flagged, "
            f"{u} unchanged (still confirmed), {s} without treatment"
        )
    elif action == "confirm":
        n, h, i = len(result["confirmed"]), len(result["held"]), len(result.get("invalid", {}))
        message = (
            f"{change_id}: {n} confirmada(s), {h} retenida(s) por marca, {i} ya no válida(s); cobertura {coverage['text']}" if es
            else f"{change_id}: {n} confirmed, {h} held by flag, {i} no longer valid; coverage {coverage['text']}"
        )
        d = len(result.get("delegated", []))
        if d:  # IMP-412
            message += f"; {d} por delegación (revisar)" if es else f"; {d} on behalf of the BA (to review)"
    elif action == "verify":
        k, path = len(result["sample"]), result["request_path"]
        message = (
            f"{change_id}: muestra de verificación {result['run']} con {k} elemento(s): `{path}`. Releé cada uno contra el pedido "
            f"y respondé con /extract {project_id} --change {change_id} --verify-result ARCHIVO" if es
            else f"{change_id}: verification sample {result['run']} with {k} element(s): `{path}`. Read each one against the request "
            f"and answer with /extract {project_id} --change {change_id} --verify-result FILE"
        )
    elif action == "verify_result":
        a, b = len(result["same"]), len(result["differs"])
        ids = ", ".join(result["reopened"]) or "—"
        message = (
            f"{change_id}: verificación {result['run']}: {a} igual(es), {b} difiere(n); reabiertos: {ids}" if es
            else f"{change_id}: verification {result['run']}: {a} same, {b} differ; reopened: {ids}"
        )
        if result.get("not_reopened"):
            skipped = ", ".join(result["not_reopened"])
            message += (f"; no se reabrieron (ya no estaban confirmados): {skipped}" if es
                        else f"; not reopened (no longer confirmed): {skipped}")
    elif action == "consolidate":  # IMP-414
        message = result["message"]
    elif action == "confirm_replacement":
        flag = "por delegación (revisar)" if es else "on behalf of the BA (to review)"
        word = "ratificado" if es else "ratified"
        tail = f" {flag}" if result.get("delegated") else (f" {word}" if result.get("ratified") else "")
        message = (
            f"{change_id}: reemplazo de {confirm_replacement} confirmado{tail}" if es
            else f"{change_id}: replacement of {confirm_replacement} confirmed{tail}"
        )
    elif action == "keep_text":
        message = (
            f"{change_id}: {keep_text} conserva el texto del pedido ({result['gap']})" if es
            else f"{change_id}: {keep_text} keeps the text of the request ({result['gap']})"
        )
    elif action == "reject":
        message = f"{change_id}: {reject_item} volvió a pendiente" if es else f"{change_id}: {reject_item} back to pending"
    else:
        message = f"{change_id}: {action}"
    result["coverage"] = coverage
    result["next_step"] = change_next_step(project_id, change_id)
    result["message"] = message
    return result
