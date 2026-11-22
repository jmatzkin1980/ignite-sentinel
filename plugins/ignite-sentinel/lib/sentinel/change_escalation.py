"""IMP-396: escalation warnings of a change. The runtime warns; the BA decides (split or project path)."""
from __future__ import annotations

from .change_requirements import load_change_ears
from .changes import change_language, get_change

TEXT = {
    "es": {
        "several_processes": "El borde del cambio toca {surfaces}: más de un proceso o una integración nueva o adyacente.",
        "new_actors": "El borde del cambio incorpora roles nuevos: {surfaces}.",
        "third_party_contract": "Las filas {rows} modifican o quitan {surfaces}, un contrato que usan terceros.",
        "suggest": "El BA decide: partir el cambio o pasar al camino de proyecto",
    },
    "en": {
        "several_processes": "The change border touches {surfaces}: more than one process or a new or adjacent integration.",
        "new_actors": "The change border adds new roles: {surfaces}.",
        "third_party_contract": "Rows {rows} modify or remove {surfaces}, a contract third parties rely on.",
        "suggest": "The BA decides: split the change or move to the project path",
    },
}


def _names(border: list[dict], predicate) -> list[str]:
    names: list[str] = []
    for item in border:
        name = str(item.get("name", ""))
        if name and predicate(item) and name not in names:
            names.append(name)
    return names


def escalation_warnings(project_id: str, change_id: str) -> list[dict]:
    """Warnings computed on the fly from the confirmed border and the EARS rows; [] while the border is open."""
    change = get_change(project_id, change_id)
    if change.get("round") != "lenses" or not change.get("border_confirmed_at"):
        return []
    text = TEXT.get(change_language(project_id, change), TEXT["es"])
    border = list(change.get("border", []))
    found: list[tuple[str, list[str], list[str]]] = []

    processes = _names(border, lambda i: i.get("type") == "proceso")
    integrations = _names(border, lambda i: i.get("type") == "integracion" and i.get("zone") in ("nuevo", "adyacente"))
    if len(processes) >= 2 or integrations:
        found.append(("several_processes", list(dict.fromkeys(processes + integrations)), []))

    actors = _names(border, lambda i: i.get("type") == "rol" and i.get("zone") == "nuevo")
    if actors:
        found.append(("new_actors", actors, []))

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
        found.append(("third_party_contract", surfaces, rows))

    return [
        {
            "trigger": trigger,
            "surfaces": names,
            "rows": ids,
            "message": f"{text[trigger].format(surfaces=', '.join(names), rows=', '.join(ids))} {text['suggest']}",
        }
        for trigger, names, ids in found
    ]
