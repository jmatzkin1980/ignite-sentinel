"""IMP-393: the stories of a change (CHG-nnn), one per spec unit, under an epic of their own.

Stories live in `04_backlog/` next to the project's, with ids from the shared US registry (never
reused) and `change:` in their frontmatter. The epic is `EPIC-CHG-nnn`; the project's EPIC-001, its
stories and its `phase` are not touched. Each `UNCHANGED` row of the change becomes a pass-to-pass
criterion of every story, so the validation contract lists the behavior the change must preserve.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .. import id_registry
from ..change_requirements import load_change_ears, parse_delta
from ..changes import change_language, get_change
from ..core.graph import add_edge, add_node, children_of, load_graph, save_graph, upsert_node
from ..core.io import read_json, remove, write_json, write_text
from ..core.markdown import frontmatter_bounds, frontmatter_list, parse_frontmatter, table_cell
from ..core.time import utc_now
from ..errors import GateRefusal
from ..story_ids import ensure_story_ids_seeded
from ..workspace import read_state, state_path, update_state, workspace_path
from .change_brief import _note_title
from .change_specs import UNIT_DELTAS
from .specs import spec_unit_pattern, spec_unit_statement, spec_unit_title

TEXT = {
    "es": {
        "no_specs": "{cid} no tiene especificación: /backlog --change parte de {path}",
        "no_units": "{cid} no tiene unidades en {path}: no hay historias que derivar",
        "blocking": "{cid} tiene {n} gap(s) bloqueante(s) abierto(s): las historias saldrían de unidades desactualizadas",
        "stale_specs": "La especificación de {cid} no está al día con sus filas REQ-EARS (cambiaron desde /specs --change)",
        "epic_outcome": "Entregar el cambio {cid} sobre lo existente: una historia por unidad, con el comportamiento preservado como criterios pass-to-pass.",
        "stories": "## Historias",
        "header": ["Historia", "Delta", "Unidad", "Título"],
        "preserved": "## Comportamiento preservado",
        "no_preserved": "_Sin filas UNCHANGED._",
        "next": "Revisá el tablero {board} y las historias de {cid} en {epic}.",
        "stale_reason": "El cambio {cid} modifica o retira lo que esta historia entrega",
        "in_progress": "{sid} está {status}: queda como está; {new} lleva el cambio {cid} como change request y hay que coordinarlo con quien la implementa",
    },
    "en": {
        "no_specs": "{cid} has no specification: /backlog --change starts from {path}",
        "no_units": "{cid} has no units in {path}: there are no stories to derive",
        "blocking": "{cid} has {n} blocking gap(s) open: the stories would come from stale units",
        "stale_specs": "The specification of {cid} is not current with its REQ-EARS rows (they changed since /specs --change)",
        "epic_outcome": "Deliver the change {cid} on the existing system: one story per unit, with the preserved behavior as pass-to-pass criteria.",
        "stories": "## Stories",
        "header": ["Story", "Delta", "Unit", "Title"],
        "preserved": "## Preserved behavior",
        "no_preserved": "_No UNCHANGED rows._",
        "next": "Review the board {board} and the stories of {cid} in {epic}.",
        "stale_reason": "The change {cid} modifies or retires what this story delivers",
        "in_progress": "{sid} is {status}: it is left as it is; {new} carries the change {cid} as a change request, coordinate it with whoever implements it",
    },
}


def _specs_path(change_id: str) -> str:
    return f"03_specs/{change_id}/specs.md"


def _units_path(change_id: str) -> str:
    return f"03_specs/{change_id}/units"


def epic_id_for(change_id: str) -> str:
    return f"EPIC-{change_id}"


def read_change_units(project_id: str, change_id: str) -> list[dict[str, Any]]:
    base = workspace_path(project_id)
    units: list[dict[str, Any]] = []
    for path in sorted((base / _units_path(change_id)).glob("SPEC-U-*.md")):
        text = path.read_text(encoding="utf-8")
        front = parse_frontmatter(text)
        unit_id = str(front.get("id", path.stem)).strip() or path.stem
        if str(front.get("change", "")).strip() != change_id or str(front.get("delta", "")).strip() not in UNIT_DELTAS:
            continue
        units.append({
            "id": unit_id,
            "title": spec_unit_title(text, unit_id),
            "status": str(front.get("status", "")).strip().lower() or "evidence-backed",
            "path": path,
            "relative_path": path.relative_to(base).as_posix(),
            "change": change_id,
            "delta": str(front.get("delta", "")).strip(),
            "trace_ids": [str(item) for item in front.get("trace_ids", []) if str(item).strip()],
            "ears": [str(item) for item in front.get("ears", []) if str(item).strip()],
            "sources": [str(item) for item in front.get("sources", []) if str(item).strip()],
            "statement": spec_unit_statement(text),
            "pattern": spec_unit_pattern(text),
        })
    return units


def _change_story_ids(base: Path, change_id: str) -> list[str]:
    """The ids of the stories on disk that this change wrote."""
    found: list[str] = []
    for path in sorted((base / "04_backlog").glob("US-*.md")):
        try:
            front = parse_frontmatter(path.read_text(encoding="utf-8"))
        except OSError:
            continue
        if str(front.get("change", "")).strip() == change_id:
            found.append(path.stem)
    return found


def _render_epic(project_id: str, change_id: str, title: str, stories: list[dict[str, Any]],
                 preserved: list[dict[str, str]], text: dict[str, Any], context_pack: str) -> str:
    header = text["header"]
    lines = ["| " + " | ".join(header) + " |", "| " + " | ".join("---" for _ in header) + " |"]
    lines += [
        f"| `{s['id']}` | {s['delta']} | `{s['source_unit']}` | {table_cell(s['title'], 160)} |" for s in stories
    ]
    preserved_lines = (
        "\n".join(f"- `{row['id']}`: {table_cell(row['statement'], 220)}" for row in preserved)
        if preserved else text["no_preserved"]
    )
    trace = [change_id, *[s["source_unit"] for s in stories]]
    return f"""---
id: {epic_id_for(change_id)}
project: {project_id}
change: {change_id}
status: draft
trace:
{frontmatter_list(trace)}
context_pack: {context_pack}
---

# {epic_id_for(change_id)} - {title}

{text['epic_outcome'].format(cid=change_id)}

{text['stories']}

{chr(10).join(lines)}

{text['preserved']}

{preserved_lines}
"""


def _gate(project_id: str, change_id: str) -> tuple[dict, dict[str, Any], list[dict[str, Any]]]:
    change = get_change(project_id, change_id)
    base = workspace_path(project_id)
    text = TEXT.get(change_language(project_id, change), TEXT["es"])
    next_step = f"/specs {project_id} --change {change_id}"
    if not (base / _specs_path(change_id)).is_file():
        raise GateRefusal(text["no_specs"].format(cid=change_id, path=_specs_path(change_id)), next_step=next_step)
    units = read_change_units(project_id, change_id)
    if not units:
        raise GateRefusal(text["no_units"].format(cid=change_id, path=_units_path(change_id)), next_step=next_step)
    blocking = int((change.get("gap_counts") or {}).get("blocking_open", 0) or 0)
    if blocking > 0:
        raise GateRefusal(
            text["blocking"].format(cid=change_id, n=blocking),
            next_step=f"/resolve-gaps {project_id} --change {change_id}",
        )
    report = read_json(base / "03_specs" / change_id / "change_specs_report.json", {})
    specs_ears = set(report.get("ears", [])) if isinstance(report, dict) else set()
    current_ears = {
        str(row["id"]) for row in load_change_ears(project_id, change_id) if parse_delta(row["delta"]) in UNIT_DELTAS
    }
    if specs_ears != current_ears:
        raise GateRefusal(text["stale_specs"].format(cid=change_id), next_step=next_step)
    return change, text, units


_NOT_IMPLEMENTED = ("Draft", "Ready", "Blocked")
_IN_PROGRESS = ("In Progress", "In Review")


def _classify_affected(project_id: str, base: Path, change_id: str, stories: list[dict[str, Any]],
                       units: list[dict[str, Any]], rows: list[dict[str, Any]],
                       text: dict[str, Any]) -> dict[str, Any]:
    """What each MODIFIED/REMOVED row does to the existing stories it affects.

    Not implemented ones go Stale; implemented (Done) and in-progress ones make the row's story a change request.
    A REMOVED row that touches only not-implemented stories produces no story. Mutates `stories` (type, modifica, drops).
    """
    from ..backlog.status import lifecycle_for_story

    rows_by_id = {str(row["id"]): row for row in rows}
    ears_of_unit = {unit["id"]: next((e for e in unit["ears"] if e in rows_by_id), "") for unit in units}
    on_disk = {path.stem for path in (base / "04_backlog").glob("US-*.md")}
    to_stale: list[str] = []
    modified_by: dict[str, list[str]] = {}
    warnings: list[str] = []
    kept: list[dict[str, Any]] = []
    dropped: list[str] = []
    for story in stories:
        row = rows_by_id.get(ears_of_unit.get(str(story.get("source_unit", "")), ""))
        delta = parse_delta(row["delta"]) if row else None
        affected = list(row.get("affects") or []) if row and delta in ("MODIFIED", "REMOVED") else []
        affected = [sid for sid in affected if sid in on_disk]
        statuses = {sid: lifecycle_for_story(project_id, sid)["status"] for sid in affected}
        modifies = [sid for sid, status in statuses.items() if status == "Done" or status in _IN_PROGRESS]
        to_stale += [sid for sid, status in statuses.items() if status in _NOT_IMPLEMENTED]
        for sid in modifies:
            modified_by.setdefault(sid, []).append(story["id"])
            if statuses[sid] in _IN_PROGRESS:
                warnings.append(text["in_progress"].format(sid=sid, status=statuses[sid], new=story["id"], cid=change_id))
        if modifies:
            story["type"], story["modifica"] = "change_request", modifies
        elif delta == "REMOVED" and affected:
            dropped.append(story["id"])
            continue
        kept.append(story)
    stories[:] = kept
    return {"to_stale": list(dict.fromkeys(to_stale)), "modified_by": modified_by, "warnings": warnings, "dropped": dropped}


def _with_modificada_por(text: str, ids: list[str]) -> str:
    """The story's text with `modificada_por` set to `ids` (removed when empty); nothing else changes."""
    bounds = frontmatter_bounds(text)
    if bounds is None:
        return text
    start, end = bounds
    lines = text[start:end].split("\n")
    out: list[str] = []
    skipping = False
    for line in lines:
        if line.startswith("modificada_por:"):
            skipping = True
            continue
        if skipping and line.startswith("  - "):
            continue
        skipping = False
        out.append(line)
    if ids:
        out += ["modificada_por:", *[f"  - {sid}" for sid in ids]]
    return text[:start] + "\n".join(out) + text[end:]


def _write_modificada_por(base: Path, own: set[str], modified_by: dict[str, list[str]]) -> None:
    """Originals gain `modificada_por` (this change's stories that modify them); entries of this change that no
    longer apply are dropped. Only that key of the frontmatter is touched."""
    for path in sorted((base / "04_backlog").glob("US-*.md")):
        front_text = path.read_text(encoding="utf-8")
        front = parse_frontmatter(front_text)
        if str(front.get("change", "")).strip():
            continue
        current = front.get("modificada_por", [])
        current = [str(i) for i in current] if isinstance(current, list) else [str(current)]
        wanted = list(dict.fromkeys([i for i in current if i not in own] + modified_by.get(path.stem, [])))
        if wanted != current:
            write_text(path, _with_modificada_por(front_text, wanted))


def _readiness_summary(items: list[dict[str, Any]]) -> tuple[str, dict[str, Any]]:
    blockers = sum(1 for item in items if item.get("status") != "ready")
    pending_by_domain: dict[str, int] = {}
    for item in items:
        for blocker in item.get("pending", []):
            if str(blocker).startswith("Pending domain context: "):
                domain = str(blocker).split(": ", 1)[1]
                pending_by_domain[domain] = pending_by_domain.get(domain, 0) + 1
    summary = {
        "stories_total": len(items),
        "stories_ready": len(items) - blockers,
        "stories_needing_context": blockers,
        "avg_readiness_score": round(sum(float(i.get("readiness_score", 0.0) or 0.0) for i in items) / len(items), 3) if items else 0.0,
        "pending_context_by_domain": pending_by_domain,
    }
    return ("READY" if blockers == 0 else "PARTIAL"), summary


def compile_change_backlog(project_id: str, change_id: str) -> dict[str, Any]:
    """The change's stories. Memory rows of the change's own derived files are dropped while building (so a rerun
    does not retrieve its previous output) and indexed again from disk on every exit path, refusals included."""
    try:
        return _compile_change_backlog(project_id, change_id)
    finally:
        _reindex_change_artifacts(project_id, change_id)


def _reindex_change_artifacts(project_id: str, change_id: str) -> None:
    from ..memory import shared_broker

    base = workspace_path(project_id)
    epic_id = epic_id_for(change_id)
    epic_path = base / "04_backlog" / f"{epic_id}.md"
    pack_path = base / "08_context_packs" / "implementation_readiness.json"
    story_ids = _change_story_ids(base, change_id)
    if not epic_path.is_file() and not story_ids:
        return
    items: dict[str, dict[str, Any]] = {}
    pack = read_json(pack_path, {})
    for item in pack.get("stories", []) if isinstance(pack, dict) else []:
        if isinstance(item, dict) and item.get("story_id"):
            items[str(item["story_id"])] = item
    broker = shared_broker(project_id)
    if epic_path.is_file():
        broker.index_artifact(epic_id, "epic", epic_path, epic_path.read_text(encoding="utf-8"),
                              trace_ids=[epic_id, change_id, *story_ids])
    for story_id in story_ids:
        path = base / "04_backlog" / f"{story_id}.md"
        text = path.read_text(encoding="utf-8")
        trace = [str(t) for t in parse_frontmatter(text).get("trace", []) or []]
        broker.index_artifact(story_id, "user_story", path, text,
                              domain=str(items.get(story_id, {}).get("domain", "functional")),
                              trace_ids=[epic_id, story_id, *trace])
    if pack_path.is_file():
        broker.index_artifact("IMPL-READINESS", "implementation_readiness", pack_path, pack_path.read_text(encoding="utf-8"),
                              domain="delivery", trace_ids=list(items) or ["IMPL-READINESS"])


def _compile_change_backlog(project_id: str, change_id: str) -> dict[str, Any]:
    from ..backlog.gates import evaluate_story_gates, update_story_gate_state
    from ..backlog.hooks import assert_backlog_privacy_clean
    from ..backlog.rollup import backlog_status
    from ..backlog.status import audit_acceptance_criteria_freezes, lifecycle_for_story
    from ..generation import build_backlog_generation_context, implementation_readiness_for_story
    from ..memory import memory_key, shared_broker
    from .backlog import render_story
    from .slicing import build_backlog_story_specs

    change, text, units = _gate(project_id, change_id)
    base = workspace_path(project_id)
    language = change_language(project_id, change)
    rows = load_change_ears(project_id, change_id)
    preserved = [
        {"id": str(row["id"]), "statement": str(row["statement"])}
        for row in rows if parse_delta(row["delta"]) == "UNCHANGED"
    ]
    for unit in units:
        unit["preserved"] = preserved

    ensure_story_ids_seeded(project_id, base)
    ids = id_registry.assign_ids(project_id, "US", [unit["id"] for unit in units])

    # A rerun must not retrieve what the previous run derived (the change's epic, stories and readiness pack):
    # drop those rows from memory so the same inputs give the same stories; they are indexed again at the end.
    previous_ids = set(_change_story_ids(base, change_id))
    pack_path = base / "08_context_packs" / "implementation_readiness.json"
    epic_path = base / "04_backlog" / f"{epic_id_for(change_id)}.md"
    shared_broker(project_id).forget_sources({
        memory_key(project_id, path)
        for path in (epic_path, pack_path, *(base / "04_backlog" / f"{sid}.md" for sid in previous_ids))
    })
    specs_text = (base / _specs_path(change_id)).read_text(encoding="utf-8")
    backlog_context = build_backlog_generation_context(project_id, specs_text, "")
    stories = build_backlog_story_specs(project_id, backlog_context, language=language, units=units, ids=ids)
    affected = _classify_affected(project_id, base, change_id, stories, units, rows, text)
    for story_id in affected["dropped"]:
        backlog_context.get("per_story", {}).pop(story_id, None)
    pack_rel = f"08_context_packs/{change_id}/backlog_generation.json"
    epic_id = epic_id_for(change_id)
    lifecycle = read_state(project_id).get("story_lifecycle", {})
    lifecycle = dict(lifecycle) if isinstance(lifecycle, dict) else {}
    for story in stories:
        story["context_pack"] = pack_rel
        current = lifecycle_for_story(project_id, story["id"]) if story["id"] in lifecycle else {"status": "Draft", "owner": ""}
        story["status"], story["owner"] = current["status"], current["owner"]
    audit_acceptance_criteria_freezes(project_id, stories)

    readiness_items: list[dict[str, Any]] = []
    for story in stories:
        item = implementation_readiness_for_story(story)
        gate_result = evaluate_story_gates(project_id, story, item)
        item["dor"], item["dod"] = gate_result["dor"], gate_result["dod"]
        item["backlog_gate"] = {"threshold": gate_result["threshold"], "strict": gate_result["strict"]}
        story["dor"], story["dod"] = gate_result["dor"], gate_result["dod"]
        update_story_gate_state(project_id, str(story["id"]), gate_result)
        readiness_items.append(item)

    # Files: this change's stories (and only them) are replaced; the ones that no longer come out are removed.
    current_ids = {story["id"] for story in stories}
    removed = sorted(previous_ids - current_ids)
    write_json(base / pack_rel, backlog_context)
    title = _note_title(base, change)
    write_text(epic_path, _render_epic(project_id, change_id, title, stories, preserved, text, pack_rel))
    story_paths: list[Path] = []
    for story in stories:
        path = base / "04_backlog" / f"{story['id']}.md"
        write_text(path, render_story(project_id, epic_id, story))
        story_paths.append(path)
    for story_id in removed:
        remove(base / "04_backlog" / f"{story_id}.md")

    # Graph: ids equal the registry ids (upsert, never add_node).
    upsert_node(project_id, epic_id, "epic", epic_path, title, domain="product")
    add_edge(project_id, change_id, epic_id, "decomposes_to")
    node_type = {str(n.get("id")): str(n.get("type")) for n in load_graph(project_id).get("nodes", [])}
    for story, path in zip(stories, story_paths):
        story_node = upsert_node(project_id, story["id"], "user_story", path, story["title"], domain=story["domain"])
        add_edge(project_id, epic_id, story_node, "contains")
        for trace_id in story["trace"]:
            if str(trace_id).startswith("SPEC-U-"):
                add_edge(project_id, str(trace_id), story_node, "decomposes_to")
        if not any(node_type.get(child) == "acceptance_criteria" for child in children_of(project_id, story_node)):
            ac_node = add_node(project_id, "AC", "acceptance_criteria", path, f"Acceptance criteria for {story_node}", domain="quality")
            add_edge(project_id, story_node, ac_node, "validated_by")
    if removed:
        graph = load_graph(project_id)
        dropped = set(removed)
        for story_id in removed:
            dropped.update(child for child in children_of(project_id, story_id) if node_type.get(child) == "acceptance_criteria")
        graph["nodes"] = [n for n in graph["nodes"] if n.get("id") not in dropped]
        graph["edges"] = [e for e in graph["edges"] if e.get("from") not in dropped and e.get("to") not in dropped]
        save_graph(project_id, graph)

    # Readiness: this change's items replace their own previous ones; the others stay.
    pack = read_json(pack_path, {})
    pack = pack if isinstance(pack, dict) else {}
    own = previous_ids | current_ids
    kept = [item for item in pack.get("stories", []) if isinstance(item, dict) and str(item.get("story_id", "")) not in own]
    all_items = [*kept, *readiness_items]
    verdict, summary = _readiness_summary(all_items)
    pack.setdefault("project_id", project_id)
    pack.setdefault("workflow", "implementation_readiness")
    pack.setdefault("generated_from", {"backlog_context_pack": pack_rel})
    pack.setdefault("retrieval_contract", {
        "rule": "Execution agents should use these queries before planning, implementing, or testing. Workspace files remain source of truth; memory is only retrieval evidence.",
        "freshness_rule": "If the current domain context snapshot differs from this pack, rerun /reindex and /backlog before implementation handoff.",
    })
    pack.update({"verdict": verdict, "summary": summary, "stories": all_items})
    write_json(pack_path, pack)

    # Lifecycle: new stories start Draft, existing entries stay, removed stories leave.
    for story in stories:
        lifecycle.setdefault(story["id"], {"status": "Draft", "owner": ""})
    for story_id in removed:
        lifecycle.pop(story_id, None)
    state = read_json(state_path(project_id), {})
    gates = state.get("story_gates", {})
    gates = dict(gates) if isinstance(gates, dict) else {}
    for story_id in removed:
        gates.pop(story_id, None)
    story_ids = [story["id"] for story in stories]
    change_requests = [story["id"] for story in stories if story["type"] == "change_request"]
    changes = state.get("changes", {})
    update_state(project_id, story_gates=gates, story_lifecycle=lifecycle)

    # Existing stories the change affects: Stale for the not implemented, `modificada_por` + `modifies` for the rest.
    from ..backlog.hooks import mark_stories_stale

    _write_modificada_por(base, previous_ids | current_ids, affected["modified_by"])
    node_ids = {str(n.get("id")) for n in load_graph(project_id).get("nodes", [])}
    for story in stories:
        for original in story.get("modifica", []):
            if story["id"] in node_ids and original in node_ids:
                add_edge(project_id, story["id"], original, "modifies")
    stale_now = mark_stories_stale(project_id, affected["to_stale"], text["stale_reason"].format(cid=change_id), change_id)
    record = changes.get(change_id, {}).get("backlog") or {}
    stale = list(dict.fromkeys([*record.get("stale", []), *stale_now]))
    changes[change_id]["backlog"] = {
        "stories": story_ids, "change_requests": change_requests, "stale": stale, "generated_at": utc_now(),
    }
    update_state(project_id, changes=changes)

    assert_backlog_privacy_clean(project_id)
    board = backlog_status(project_id)

    epic_rel = epic_path.relative_to(base).as_posix()
    report = {
        "change_id": change_id, "epic": epic_id, "stories": story_ids, "removed": removed,
        "pass_to_pass": [row["id"] for row in preserved],
        "change_requests": change_requests, "stale": stale_now, "warnings": affected["warnings"],
    }
    write_json(base / "08_context_packs" / change_id / "backlog_report.json", report)
    return {
        "project_id": project_id,
        "change_id": change_id,
        "epic": epic_id,
        "path": epic_rel,
        "stories": story_ids,
        "change_requests": change_requests,
        "stale": stale_now,
        "warnings": affected["warnings"],
        "report": report,
        "backlog_board": board["path"],
        "next_step": text["next"].format(board="04_backlog/BACKLOG.md", cid=change_id, epic=epic_rel),
    }
