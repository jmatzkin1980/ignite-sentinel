"""IMP-396: escalation warnings of a change. The runtime warns; the BA decides (split or project path)."""
from __future__ import annotations

from .change_requirements import load_change_ears
from .changes import change_language, get_change

TEXT = {
    "es": {
        "several_processes": "El borde del cambio toca {surfaces}: {count} procesos o integraciones nuevas o adyacentes para un pedido de {elements} elementos (umbral {threshold}).",
        "new_actors": "El borde del cambio incorpora roles nuevos: {surfaces}.",
        "third_party_contract": "Las filas {rows} modifican o quitan {surfaces}, un contrato que usan terceros.",
        "suggest": "El BA decide: partir el cambio o pasar al camino de proyecto",
        "kept_single": "decidido: sigue como un cambio ({reason})",
    },
    "en": {
        "several_processes": "The change border touches {surfaces}: {count} processes or new or adjacent integrations for a request of {elements} elements (threshold {threshold}).",
        "new_actors": "The change border adds new roles: {surfaces}.",
        "third_party_contract": "Rows {rows} modify or remove {surfaces}, a contract third parties rely on.",
        "suggest": "The BA decides: split the change or move to the project path",
        "kept_single": "decided: it stays one change ({reason})",
    },
}


def _names(border: list[dict], predicate) -> list[str]:
    names: list[str] = []
    for item in border:
        name = str(item.get("name", ""))
        if name and predicate(item) and name not in names:
            names.append(name)
    return names


def request_element_count(project_id: str, change_id: str) -> int:
    """T2-05: size of the request: the inventory total, or the request's own elements before there is one."""
    from .compilers.change_deliverable import _request_elements
    from .extraction.inventory import load_inventory
    from .workspace import workspace_path

    inventory = load_inventory(workspace_path(project_id), change_id)
    if inventory is not None and "total" in inventory:
        return int(inventory["total"] or 0)
    return len(_request_elements(project_id, change_id))


def escalation_threshold(elements: int) -> int:
    """T2-05: processes or integrations that make a request look like more than one change."""
    return max(2, elements // 40)


def warning_size(warning: dict) -> int:
    """How big a trigger is: its process count, or the surfaces and rows it names (a decision covers up to that size)."""
    return int(warning.get("count") or (len(warning.get("surfaces") or []) + len(warning.get("rows") or [])))


def escalation_warnings(project_id: str, change_id: str) -> list[dict]:
    """Warnings computed on the fly from the confirmed border and the EARS rows; [] while the border is open.

    A BA decision (`/sources --keep-single`) replaces the warnings it covered with one `decided` notice."""
    change = get_change(project_id, change_id)
    warnings = _raw_warnings(project_id, change_id)
    decision = change.get("keep_single")
    if not isinstance(decision, dict):
        return warnings
    sizes = decision.get("sizes") if isinstance(decision.get("sizes"), dict) else {}
    triggers = set(decision.get("triggers") or [])

    def covers(w: dict) -> bool:
        # IMP-412 final review (I4): a decision reaches what it saw; a trigger that grew warns again
        return w["trigger"] in triggers and warning_size(w) <= int(sizes.get(w["trigger"], warning_size(w)))

    if not any(covers(w) for w in warnings):
        return warnings
    text = TEXT.get(change_language(project_id, change), TEXT["es"])
    decided = {"trigger": "kept_single", "surfaces": [], "rows": [], "decided": True,
               "message": text["kept_single"].format(reason=decision.get("reason", ""))}
    return [decided, *(w for w in warnings if not covers(w))]


def _raw_warnings(project_id: str, change_id: str) -> list[dict]:
    change = get_change(project_id, change_id)
    if change.get("round") != "lenses" or not change.get("border_confirmed_at"):
        return []
    text = TEXT.get(change_language(project_id, change), TEXT["es"])
    border = list(change.get("border", []))
    found: list[tuple] = []

    processes = _names(border, lambda i: i.get("type") == "proceso")
    integrations = _names(border, lambda i: i.get("type") == "integracion" and i.get("zone") in ("nuevo", "adyacente"))
    count = len(processes) + len(integrations)
    if count >= 2:
        elements = request_element_count(project_id, change_id)
        threshold = escalation_threshold(elements)
        if count >= threshold:
            found.append(("several_processes", list(dict.fromkeys(processes + integrations)), [],
                          {"count": count, "elements": elements, "threshold": threshold}))

    actors = _names(border, lambda i: i.get("type") == "rol" and i.get("zone") == "nuevo")
    if actors:
        found.append(("new_actors", actors, [], {}))

    contracts = set(_names(
        border, lambda i: i.get("type") in ("endpoint", "integracion") and i.get("zone") == "adyacente"))
    rows: list[str] = []
    surfaces: list[str] = []
    for row in load_change_ears(project_id, change_id):
        if row.get("delta") not in ("MODIFIED", "REMOVED"):
            continue
        hit = [s for s in row.get("surfaces", []) if s in contracts]
        if hit:
            rows.append(row["id"])
            surfaces.extend(s for s in hit if s not in surfaces)
    if rows:
        found.append(("third_party_contract", surfaces, rows, {}))

    out = []
    for trigger, names, ids, extra in found:
        message = text[trigger].format(surfaces=", ".join(names), rows=", ".join(ids), **extra)
        out.append({"trigger": trigger, "surfaces": names, "rows": ids,
                    **({"count": extra["count"], "threshold": extra["threshold"]} if extra else {}),
                    "message": f"{message} {text['suggest']}"})
    return out
