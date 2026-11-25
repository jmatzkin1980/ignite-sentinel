"""IMP-406 task 5: the reading plan of a change request, in batches the agent reads in full.

Pure batching over the inventory elements (`chars` is how much each one weighs), a plan written next to
the inventory, and the status the next step names the batch from.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from ..core.io import read_json, write_json, write_text
from ..core.paths import workspace_path
from . import extraction_dir

READING_BUDGET = 60_000  # characters of the request an agent reads in one batch

_WORDS = {
    "es": {"title": "Plan de lectura", "batch": "Lote {n} de {m} — {chars} caracteres", "lines": "líneas", "elements": "Elementos",
           "note": "Un lote «propuesto» no es un lote leído: declará en Líneas lo que leíste de cada elemento."},
    "en": {"title": "Reading plan", "batch": "Batch {n} of {m} — {chars} characters", "lines": "lines", "elements": "Elements",
           "note": "A «proposed» batch is not a read batch: declare in Lines what you read of each element."},
}


def plan_batches(elements: list[dict], budget: int | None = None) -> list[dict]:
    """Group the elements, in order, while the sum of their `chars` does not pass the budget.

    An element that does not fit opens a batch; one bigger than the budget goes alone."""
    from .inventory import element_lines

    limit = READING_BUDGET if budget is None else budget
    groups: list[list[dict]] = []
    current: list[dict] = []
    total = 0
    for element in elements:
        size = int(element.get("chars", 0) or 0)
        if current and total + size > limit:
            groups.append(current)
            current, total = [], 0
        current.append(element)
        total += size
        if size > limit:
            groups.append(current)
            current, total = [], 0
    if current:
        groups.append(current)
    batches = []
    for number, group in enumerate(groups, start=1):
        ranges: dict[str, dict[str, Any]] = {}
        for element in group:
            first, last = element_lines(element)
            found = ranges.get(element["source_id"])
            if found is None:
                ranges[element["source_id"]] = {
                    "source_id": element["source_id"], "path": element.get("path", ""), "lines": [first, last],
                }
            else:
                found["lines"] = [min(found["lines"][0], first), max(found["lines"][1], last)]
        batches.append({
            "number": number, "elements": [e["id"] for e in group],
            "chars": sum(int(e.get("chars", 0) or 0) for e in group), "ranges": list(ranges.values()),
        })
    return batches


def reading_plan_paths(base: Path, change_id: str) -> tuple[Path, Path]:
    folder = extraction_dir(base, change_id)
    return folder / "reading_plan.json", folder / "reading_plan.md"


def write_reading_plan(base: Path, change_id: str, inventory: dict, language: str) -> Path:
    """`extraction/reading_plan.json` and `reading_plan.md` of the inventory; returns the markdown path."""
    budget = READING_BUDGET
    batches = plan_batches(inventory.get("elements", []), budget)
    json_path, md_path = reading_plan_paths(base, change_id)
    read_json(json_path, None)  # the plan is rebuilt whole: note what is on disk, so only an outside writer conflicts
    write_json(json_path, {
        "schema_version": 1, "change_id": change_id, "inventory_version": inventory.get("version", 1),
        "budget_chars": budget, "batches": batches,
    })
    words = _WORDS["es" if language == "es" else "en"]
    label = change_id or ("proyecto" if language == "es" else "project")
    lines = [f"# {words['title']} — {label}", "", words["note"], ""]
    for batch in batches:
        lines.append("## " + words["batch"].format(n=batch["number"], m=len(batches), chars=batch["chars"]))
        for found in batch["ranges"]:
            lines.append(f"- {found['source_id']} `{found['path']}` {words['lines']} {found['lines'][0]}-{found['lines'][1]}")
        lines.append(f"- {words['elements']}: {', '.join(batch['elements'])}")
        lines.append("")
    write_text(md_path, "\n".join(lines))
    return md_path


def reading_plan_status(project_id: str, change_id: str) -> dict[str, Any]:
    """Where the reading plan of the current inventory stands (computed, the plan file is not read)."""
    from ..changes import change_language, resolve_scope
    from .inventory import load_inventory
    from .proposals import load_proposals

    es = resolve_scope(project_id, change_id).language == "es"
    base = workspace_path(project_id)
    inventory = load_inventory(base, change_id)
    if inventory is None:
        return {"total": 0, "proposed": 0, "next": None, "next_batch": None, "text": "sin plan" if es else "no plan"}
    items = load_proposals(base, change_id)["items"]
    batches = plan_batches(inventory.get("elements", []))
    by_id = {e["id"]: e for e in inventory.get("elements", [])}

    def proposed(batch: dict) -> bool:
        for element_id in batch["elements"]:
            item = items.get(element_id)
            if not isinstance(item, dict) or item.get("element_sha") != by_id[element_id].get("sha"):
                return False
        return True

    done = [proposed(b) for b in batches]
    pending = next((b for b, ok in zip(batches, done) if not ok), None)
    total = len(batches)
    if pending is not None:
        text = f"lote {pending['number']} de {total}" if es else f"batch {pending['number']} of {total}"
    elif total:
        text = f"{total} de {total} lotes propuestos" if es else f"{total} of {total} batches proposed"
    else:
        text = "sin plan" if es else "no plan"
    return {
        "total": total, "proposed": sum(done), "next": pending["number"] if pending else None,
        "next_batch": pending, "text": text,
    }
