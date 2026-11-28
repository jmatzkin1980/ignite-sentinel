"""IMP-402 (H26 inc 3): extraction of a change request, element by element, with coverage.

Everything lives under `02_requirements/CHG-NNN/extraction/` of the project workspace.
"""
from __future__ import annotations

from pathlib import Path


def extraction_dir(base: Path, change_id: str | None) -> Path:
    """The folder that holds a change's inventory, proposals, review and submitted sheets (the project's with None)."""
    if change_id is None:
        return base / "02_requirements" / "extraction"
    return base / "02_requirements" / change_id / "extraction"


def project_next_step(project_id: str, result: dict) -> dict:
    """IMP-420: a result on the project's request carries `scope`, `next` and `next_step` (the step of `/next P`)."""
    from ..status import project_next

    step = project_next(project_id)
    result["change_id"], result["scope"], result["next"] = None, "project", step
    return step


def run_extract(
    project_id: str,
    change_id: str | None,
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
    from ..changes import resolve_scope
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

    if change_id is None:  # the same guard as the CLI: no ids, change-only options, a workspace of changes only
        from ..changes import refuse_project_extraction

        refuse_project_extraction(project_id, "extract", {
            "--consolidate": consolidate, "--confirm-replacement": confirm_replacement, "--keep-text": keep_text})
    scope = resolve_scope(project_id, change_id)  # an unknown change is a GateRefusal; None is the project (IMP-420)
    lang = "es" if scope.language == "es" else "en"
    es = lang == "es"
    who = change_id or project_id
    where = f" --change {change_id}" if change_id else ""
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
            f"{who}: {result['total']} elementos inventariados ({by_kind}). Planilla: `{sheet}`" if es
            else f"{who}: {result['total']} elements inventoried ({by_kind}). Worksheet: `{sheet}`"
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
            f"{who}: {n} propuesta(s) registrada(s), {r} rechazada(s), {f} marcada(s), "
            f"{u} sin cambios (siguen confirmadas), {s} sin tratamiento" if es
            else f"{who}: {n} proposal(s) recorded, {r} rejected, {f} flagged, "
            f"{u} unchanged (still confirmed), {s} without treatment"
        )
        if r and not n and not u:  # B-38: nothing was recorded, and exit 0 alone says nothing; the reasons say why
            import sys

            reasons = "; ".join(reason for errors in result["rejected"].values() for reason in errors)
            print(f"sentinel warning: {who}: " + (
                f"ninguna propuesta se registró, {r} rechazada(s): {reasons}" if es
                else f"no proposal was recorded, {r} rejected: {reasons}"), file=sys.stderr)
    elif action == "confirm":
        n, h, i = len(result["confirmed"]), len(result["held"]), len(result.get("invalid", {}))
        message = (
            f"{who}: {n} confirmada(s), {h} retenida(s) por marca, {i} ya no válida(s); cobertura {coverage['text']}" if es
            else f"{who}: {n} confirmed, {h} held by flag, {i} no longer valid; coverage {coverage['text']}"
        )
        d = len(result.get("delegated", []))
        if d:  # IMP-412
            message += f"; {d} por delegación (revisar)" if es else f"; {d} on behalf of the BA (to review)"
    elif action == "verify":
        k, path = len(result["sample"]), result["request_path"]
        message = (
            f"{who}: muestra de verificación {result['run']} con {k} elemento(s): `{path}`. Releé cada uno contra el pedido "
            f"y respondé con /extract {project_id}{where} --verify-result ARCHIVO" if es
            else f"{who}: verification sample {result['run']} with {k} element(s): `{path}`. Read each one against the request "
            f"and answer with /extract {project_id}{where} --verify-result FILE"
        )
    elif action == "verify_result":
        a, b = len(result["same"]), len(result["differs"])
        ids = ", ".join(result["reopened"]) or "—"
        message = (
            f"{who}: verificación {result['run']}: {a} igual(es), {b} difiere(n); reabiertos: {ids}" if es
            else f"{who}: verification {result['run']}: {a} same, {b} differ; reopened: {ids}"
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
            f"{who}: reemplazo de {confirm_replacement} confirmado{tail}" if es
            else f"{who}: replacement of {confirm_replacement} confirmed{tail}"
        )
    elif action == "keep_text":
        message = (
            f"{who}: {keep_text} conserva el texto del pedido ({result['gap']})" if es
            else f"{who}: {keep_text} keeps the text of the request ({result['gap']})"
        )
    elif action == "reject":
        message = f"{who}: {reject_item} volvió a pendiente" if es else f"{who}: {reject_item} back to pending"
    else:
        message = f"{who}: {action}"
    result["coverage"] = coverage
    result["next_step"] = change_next_step(project_id, change_id) if change_id else project_next_step(project_id, result)
    result["message"] = message
    return result
