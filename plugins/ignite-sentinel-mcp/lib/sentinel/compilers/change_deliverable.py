"""IMP-406: the deliverable of a change, in the project brief v2 format.

This module renders nothing. It translates what the change holds (the confirmed border, the
extraction, the answered and open questions, the EARS rows) into the `BriefInputs` that the
project's compiler (`render_brief_v2`, `templates/brief_v2.json`) already knows how to write, so
the change's `/export` and the project's brief share one format.

Transcribe, don't draft: the sections come as the request wrote them (the verbatim content the
extraction stored at confirm, never a summary), and every fact and block opens with its delta tag
(`[nuevo]`, `[modificado]`, `[preservado]`). What the change does not touch is N/A, never pending.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from ..brief_model import V2_GAP_ROUTES
from ..brief_schema import applicability, brief_settings, profile_order
from ..change_assumptions import open_change_assumptions
from ..change_requirements import load_change_ears, parse_surfaces
from ..core.time import utc_now
from ..extraction.lines import format_ranges
from ..extraction.proposals import _element_text_cached
from ..resources import read_package_json
from ..workspace import workspace_path
from .brief_v2 import BriefInputs, render_brief_v2

DELTA_TAGS = {
    "es": {"nuevo": "nuevo", "modificado": "modificado", "preservado": "preservado"},
    "en": {"nuevo": "new", "modificado": "modified", "preservado": "preserved"},
}
ROW_TAG = {"ADDED": "nuevo", "MODIFIED": "modificado", "REMOVED": "modificado", "UNCHANGED": "preservado"}
ZONE_TAG = {"nuevo": "nuevo", "adyacente": "modificado", "preservado": "preservado"}
SECTION_PLACES = {"objetivo": "1.1", "usuarios": "2.1", "proceso": "3.2", "alcance": "1.3", "reglas": "2.2",
                  "aceptacion": "1.5", "preservado": "6.2"}
ROW_PLACES = {"business": "2.2", "product": "3.2", "design": "4.1", "technical": "5.12"}
LENS_PLACES = {"business": "2.4", "product": "3.6", "design": "4.2", "technical": "5.1", "quality": "1.5",
               "compliance": "5.11", "delivery": "2.5"}
CHANGE_ROUTE_OVERRIDES = {"GAP-SCOPE": "1.3"}  # 6.1 stays for the border, so §9 comes from it
DECISION_PREFIXES = ("GAP-DIS-", "GAP-CON-", "GAP-SRD-", "GAP-SED-", "GAP-VER-")  # cross-reads and versions: decisions
DECISION_PLACE = "7.1"
SURFACE_PROFILES = {"pantalla": "UI", "endpoint": "API", "dato": "API", "integracion": "INT"}
GENESIS = "brownfield-extension"
_EXT_SOURCE = re.compile(r"`EXT:([^`]+)`")
_FIRST_CODE = re.compile(r"`([^`]+)`")

COPY = {
    "es": {
        "out": "Fuera de este cambio", "out_project": "Fuera del alcance", "no_regression": "no regresión", "rows": "filas",
        "table": ["Pendiente", "Clase", "Bloquea", "Responsable"], "yes": "sí", "no": "no",
        "blocking": "bloqueante", "construccion": "construccion", "operativo": "operativo",
        "reason": "el cambio no toca este punto", "condition": "el borde del cambio lo suma",
        "draft": "borrador",
    },
    "en": {
        "out": "Out of this change", "out_project": "Out of scope", "no_regression": "no regression", "rows": "rows",
        "table": ["Item", "Class", "Blocks", "Owner"], "yes": "yes", "no": "no",
        "blocking": "blocking", "construccion": "build", "operativo": "operational",
        "reason": "the change does not touch this point", "condition": "the change border adds it",
        "draft": "draft",
    },
}


def _lang(language: str) -> str:
    return "es" if language == "es" else "en"


def _template() -> dict[str, Any]:
    return read_package_json("templates", "change_brief.json")


def brief_sha(base: Path, change_id: str) -> str:
    """The first 16 hex digits of the sha256 of the change's internal brief ('' when it is not compiled)."""
    path = base / "02_requirements" / change_id / "project-brief.md"
    if not path.is_file():
        return ""
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def row_lens(row: dict, border: list[dict], template: dict) -> str:
    """The lens of a requirement row: the type of its first surface of the border; without one, business."""
    valid, _unknown = parse_surfaces(";".join(row.get("surfaces") or []), border)
    for name in valid[:1]:
        kind = next((item.get("type") for item in border if item.get("name") == name), None)
        for lens, kinds in template["lens_surfaces"].items():
            if kind in kinds:
                return lens
    return "business"


def change_profiles(border: list[dict], settings: dict) -> list[str]:
    """The profiles the workspace confirmed; else those the border's surface types imply (UI when none)."""
    order = profile_order()
    given = [p for p in (settings or {}).get("profiles") or [] if p in order]
    if given:
        try:
            applicability(given, GENESIS)
            return given
        except ValueError:
            pass
    found = {SURFACE_PROFILES[item["type"]] for item in border if item.get("type") in SURFACE_PROFILES}
    return [profile for profile in order if profile in found] or ["UI"]


def build_seal(project_id: str, change_id: str, final: bool, language: str) -> dict[str, Any]:
    from ..extraction.coverage import extraction_coverage
    from ..readiness_verdict import build_change_verdict

    lang = _lang(language)
    coverage = extraction_coverage(project_id, change_id)
    verdict = build_change_verdict(project_id, change_id)
    from ..delegation import delegated_summary

    delegated = delegated_summary(project_id, change_id)
    return {
        "state": "final" if final else COPY[lang]["draft"],
        "date": utc_now()[:10],
        "covered": int(coverage["covered"]),
        "total": int(coverage["total"]),
        "deferred": {"construccion": int(verdict["deferred"]["construccion"]),
                     "operativo": int(verdict["deferred"]["operativo"])},
        "assumptions": len(open_change_assumptions(project_id, change_id)),  # IMP-412: the ones still to validate
        "delegated": [*delegated["elements"], *delegated["gaps"]],  # IMP-412: confirmed on behalf of the BA, to review
        "verdict": str(verdict["verdict"]),
    }


def seal_sha(project_id: str, change_id: str) -> str:
    """IMP-406 I7: the first 16 hex digits of the sha256 of what the seal says (verdict, coverage, deferred ids and classes).

    The final export is current only while the brief AND this hash are the ones it was made from."""
    from ..changes import deferred_gaps
    from ..extraction.coverage import extraction_coverage
    from ..readiness_verdict import build_change_verdict

    coverage = extraction_coverage(project_id, change_id)
    payload = {
        "verdict": build_change_verdict(project_id, change_id)["verdict"],
        "covered": int(coverage["covered"]), "total": int(coverage["total"]),
        "deferred": sorted((d["id"], d["impact"]) for d in deferred_gaps(project_id, change_id)),
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()[:16]


def seal_lines(seal: dict[str, Any], language: str) -> list[str]:
    build, operational = seal["deferred"]["construccion"], seal["deferred"]["operativo"]
    ids = seal.get("delegated") or []
    es = _lang(language) == "es"
    delegated_line = ([
        f"> **Confirmado por delegación:** {len(ids)} (revisar: {', '.join(ids)})" if es
        else f"> **Confirmed on behalf of the BA:** {len(ids)} (review: {', '.join(ids)})"
    ] if ids else [])
    if _lang(language) == "es":
        return [
            f"> **Estado:** {seal['state']} · **Fecha:** {seal['date']} · **Veredicto:** {seal['verdict']}",
            f"> **Cobertura:** {seal['covered']} de {seal['total']} elementos del pedido",
            f"> **Pendientes diferidos:** {build + operational} (construcción {build}, operativo {operational})",
            f"> **Supuestos:** {seal['assumptions']}",
            *delegated_line,
        ]
    return [
        f"> **Status:** {seal['state']} · **Date:** {seal['date']} · **Verdict:** {seal['verdict']}",
        f"> **Coverage:** {seal['covered']} of {seal['total']} request elements",
        f"> **Deferred items:** {build + operational} (build {build}, operational {operational})",
        f"> **Assumptions:** {seal['assumptions']}",
        *delegated_line,
    ]


_HEADING = re.compile(r"^(\s{0,3})(#{1,6})(\s)")


def _keep_flat(line: str) -> str:
    """A request line that looks like a heading would open a subsection of the brief: escape its first `#` (the text stays)."""
    return _HEADING.sub(lambda m: f"{m.group(1)}\\{m.group(2)}{m.group(3)}", line)


def _cell(text: Any) -> str:
    return " ".join(str(text or "").split()).replace("|", "\\|")


def v2_heading_place(heading: str, schema: dict[str, Any]) -> str:
    """The place of the brief v2 a request heading names (`2.2 ...` by id, or by its es/en title); `""` when it names none."""
    from ..extraction.inventory import _fold, _heading_keyword

    text = str(heading or "").strip()
    places = {str(sub["id"]): sub for section in schema.get("sections", []) if int(section.get("id", 0)) > 0
              for sub in section.get("subsections", [])}
    found = re.match(r"^(\d+\.\d+)(?=[.):\s]|$)", text)
    if found and found.group(1) in places:
        return found.group(1)
    key = _heading_keyword(text)
    if not key:
        return ""
    for place, sub in places.items():
        titles = sub.get("title") or {}
        if key in {_fold(str(titles.get(code, ""))) for code in ("es", "en")}:
            return place
    return ""


def request_follows_v2(elements: list[dict]) -> bool:
    """The request is written on the v2 template when its headings name at least 3 distinct places of it."""
    from ..brief_schema import load_brief_schema

    schema = load_brief_schema()
    found = {v2_heading_place(str(e.get("section") or e.get("heading") or ""), schema) for e in elements}
    return len(found - {""}) >= 3


def gap_place(gap_id: str, lens: str) -> str:
    """The v2 place where the answer of a closed question of the change lands."""
    if gap_id in CHANGE_ROUTE_OVERRIDES:
        return CHANGE_ROUTE_OVERRIDES[gap_id]
    if gap_id in V2_GAP_ROUTES:
        return V2_GAP_ROUTES[gap_id]
    if gap_id.startswith(DECISION_PREFIXES):
        return DECISION_PLACE
    return LENS_PLACES.get(str(lens).strip("`").lower(), DECISION_PLACE)


def _change_rows(project_id: str, change_id: str, view: dict[str, Any]) -> tuple[list[dict], list[dict]]:
    """(every active EARS row, the rows the extraction confirmed and still stand), with their surfaces and source."""
    by_element = {e["id"]: e for e in view.get("elements", [])}
    owner = {row["id"]: element_id for element_id, rows in (view.get("rows") or {}).items() for row in rows}
    every: list[dict] = []
    placed: list[dict] = []
    for row in load_change_ears(project_id, change_id):
        found = _EXT_SOURCE.match(str(row.get("source", "")))
        item = {**row, "element": found.group(1) if found else "", "source_id": "", "gap": ""}
        if found:
            element = by_element.get(found.group(1))
            item["source_id"] = str((element or {}).get("source_id") or "")
            if row["id"] in owner:
                placed.append(item)
        else:
            code = _FIRST_CODE.search(str(row.get("source", "")))
            item["gap"] = code.group(1) if code and code.group(1).startswith("GAP-") else ""
        every.append(item)
    return every, placed


def _border_facts(border: list[dict], every_rows: list[dict], copy: dict[str, str], add_fact: Any) -> None:
    """The border's surfaces to build or touch (6.1) and to preserve (6.2), each with the rows that cite it."""
    rows_of: dict[str, list[str]] = {}
    for row in every_rows:
        valid, _unknown = parse_surfaces(";".join(row.get("surfaces") or []), border)
        for name in valid:
            rows_of.setdefault(name, []).append(row["id"])
    for item in border:
        zone = item.get("zone")
        if zone not in ZONE_TAG:
            continue
        text = f"{item.get('type', '')} — {item.get('name', '')}"
        ids = rows_of.get(item.get("name", ""), [])
        if ids:
            text += f" — {copy['no_regression' if zone == 'preservado' else 'rows']}: {', '.join(ids)}"
        add_fact("6.2" if zone == "preservado" else "6.1", ZONE_TAG[zone], text, gap="GAP-SCOPE")


def _harvest_facts(harvest: dict, border: list[dict], template: dict, add_fact: Any) -> None:
    """The code facts of the harvest that belong to the border's blocks (as in the project)."""
    from ..harvest import BLOCK_PLACES

    harvest_source = str(harvest.get("source_id") or "")
    wanted: set[str] = set()
    for item in border:
        wanted |= set(template["surface_blocks"].get(item.get("type"), []))
    transversal = template.get("transversal", {})
    if {item.get("type") for item in border} & set(transversal.get("surfaces", [])):
        wanted |= set(transversal.get("context", [])) | set(transversal.get("technical", []))
    for entry in harvest.get("entries", []) if harvest_source and border else []:
        place = BLOCK_PLACES.get(entry.get("block", ""))
        if place and entry.get("kind") == "fact" and entry.get("block") in wanted:
            add_fact(place, "preservado", f"{entry['text']} ({entry['ref']})", harvest_source)


def extraction_places(project_id: str, change_id: str | None, view: dict[str, Any], language: str, *,
                      border: list[dict], tags: bool, consolidation: dict[str, Any] | None = None,
                      after_rows: Any = None) -> tuple[dict[str, list[dict[str, str]]], dict[str, list[str]]]:
    """(facts, blocks) of the confirmed extraction: sections verbatim, rows as facts, what the request leaves out.

    The change brief calls it with its border and `tags=True` (each line opens with its delta tag); the project's
    brief v2 (IMP-420) with `border=[]` and `tags=False` (on the project everything is new, so no tag).
    `consolidation` (IMP-414: control_rows, replacements, v2_schema and the `element_places` it fills) and
    `after_rows(add_fact, every_rows)` (the change's border facts, which sit between the rows and the leftovers)
    are the change's own.
    """
    template = _template()
    lang = _lang(language)
    copy, change_copy = COPY[lang], template["copy"][lang]
    delta_tags = DELTA_TAGS[lang]
    base = workspace_path(project_id)
    has_inventory = view.get("state", "missing") != "missing"
    facts: dict[str, list[dict[str, str]]] = {}
    blocks: dict[str, list[str]] = {}
    consolidated = consolidation is not None
    control_rows = (consolidation or {}).get("control_rows", {})
    replacements = (consolidation or {}).get("replacements", {})
    v2_schema = (consolidation or {}).get("v2_schema", {})
    element_places: dict[str, str] = (consolidation or {}).get("element_places", {})
    by_element = {e["id"]: e for e in view.get("elements", [])} if has_inventory else {}

    def label(tag: str) -> str:
        return f"[{delta_tags[tag]}] " if tags and tag else ""

    def add_fact(place: str, tag: str, text: str, source: str = "", gap: str = "") -> None:
        facts.setdefault(place, []).append({"text": f"{label(tag)}{text}", "source": source, "gap": gap})

    def v2_place(element_id: str) -> str:
        return v2_heading_place(str((by_element.get(element_id) or {}).get("section") or ""), v2_schema) if v2_schema else ""

    def to_confirm(element_id: str, head: str) -> str:
        held = (view.get("items") or {}).get(element_id) or {}
        if held.get("a_confirmar"):  # IMP-412 (M5): the BA's reason travels with a section left to confirm
            head += f" — {change_copy['to_confirm']}: {str(held.get('a_confirmar_reason', '')).strip()}"
        return head

    def replace_element(element_id: str, default_place: str) -> None:
        """The confirmed replacement of an element, with its reference, at its place (or under its related subsection)."""
        found = replacements[element_id]
        gaps = ", ".join(found.get("decisions") or [])
        head = to_confirm(element_id, change_copy["consolidated_content"].format(
            element=element_id, path=(by_element.get(element_id) or {}).get("path", ""),
            lines=format_ranges(found.get("lines") or []), gaps=gaps))
        body = [f"- {label('modificado')}{head}", "", *(_keep_flat(line) for line in str(found.get("text", "")).split("\n")), ""]
        element_places[element_id] = str(found.get("location") or default_place)
        if found.get("location"):
            blocks.setdefault(str(found["location"]), []).extend(
                [change_copy["related"].format(element=element_id, gaps=gaps), "", *body])
        else:
            blocks.setdefault(default_place, []).extend(body)

    # the confirmed sections, as the request wrote them (the verbatim content, never a summary)
    for entry in view.get("sections", []) if has_inventory else []:
        place = SECTION_PLACES.get(str(entry.get("section") or ""), SECTION_PLACES["reglas"])
        place = v2_place(str(entry.get("element") or "")) or place
        if entry.get("element") in replacements:
            replace_element(entry["element"], place)
            continue
        tag = "preservado" if entry.get("section") == "preservado" else "nuevo"
        content = entry.get("content")
        if content is None:  # an entry stored before the content was kept: its quote is all there is
            quote = str(entry.get("text") or entry.get("quote") or "").strip()
            add_fact(place, tag, f"{quote} ({entry.get('element', '')}, `{entry.get('path', '')}`:{entry.get('line', '')})",
                     str(entry.get("source_id") or ""))
            continue
        head = change_copy["extracted_content"].format(
            element=entry.get("element", ""), path=entry.get("path", ""),
            lines=format_ranges(entry.get("lines") or []) or entry.get("line", ""))
        head = to_confirm(str(entry.get("element") or ""), head)
        element_places.setdefault(str(entry.get("element") or ""), place)
        blocks.setdefault(place, []).extend(
            [f"- {label(tag)}{head}", "", *(_keep_flat(line) for line in str(content).split("\n")), ""])

    # the confirmed requirement rows, by the lens of their first surface
    every_rows, placed_rows = _change_rows(project_id, change_id, view)
    if consolidated:  # the final body transcribes the element, not the EARS rows derived from it
        cache: dict[str, list[str] | None] = {}
        by_owner: dict[str, list[dict]] = {}
        for row in placed_rows:
            by_owner.setdefault(row["element"], []).append(row)
        for element_id, rows in by_owner.items():
            deltas = [str(r.get("delta", "")).strip().upper() for r in rows]
            unchanged = all(d == "UNCHANGED" for d in deltas)
            tag = "preservado" if unchanged else "modificado" if any(d in ("MODIFIED", "REMOVED") for d in deltas) else "nuevo"
            place = v2_place(element_id) or ("6.2" if unchanged else ROW_PLACES[row_lens(rows[0], border, template)])
            if element_id in replacements:
                replace_element(element_id, place)
                continue
            element = by_element[element_id]
            body = _element_text_cached(base, element, cache)
            if body is None:
                body = "\n".join(f"{r['statement']} ({r['id']})" for r in rows)
            head = change_copy["extracted_content"].format(
                element=element_id, path=element.get("path", ""), lines=format_ranges(element.get("spans") or []))
            head = to_confirm(element_id, head)
            element_places[element_id] = place
            blocks.setdefault(place, []).extend(
                [f"- {label(tag)}{head}", "", *(_keep_flat(line) for line in body.split("\n")), ""])
    for row in [] if consolidated else placed_rows:
        delta = str(row.get("delta", "")).strip().upper()
        tag = ROW_TAG.get(delta, "nuevo")
        place = "6.2" if delta == "UNCHANGED" else ROW_PLACES[row_lens(row, border, template)]
        statement = f"{row['statement']} ({row['id']})"
        if row.get("a_confirmar"):  # IMP-412: the request left it to confirm; the BA's reason travels with the fact
            reason = str(((view.get("items") or {}).get(row["element"]) or {}).get("a_confirmar_reason", "")).strip()
            statement += f" — {change_copy['to_confirm']}: {reason}"
        add_fact(place, tag, statement, row["source_id"])

    if after_rows is not None:
        after_rows(add_fact, every_rows)

    # what the request leaves out
    for element in view.get("elements", []) if has_inventory else []:
        item = (view.get("items") or {}).get(element["id"])
        if (isinstance(item, dict) and item.get("status") == "confirmed" and item.get("element_sha") == element.get("sha")
                and item.get("treatment") == "descarte"):
            if consolidated:
                retiring = (control_rows.get(element["id"]) or {}).get("gaps") or []
                add_fact("6.2", "", f"{change_copy['not_included']}: {element['id']} — {str(item.get('reason', '')).strip()}",
                         str(element.get("source_id") or ""), gap=str(retiring[0]) if retiring else "")
                continue
            add_fact("6.2", "", f"{copy['out' if change_id else 'out_project']}: {element['id']} — {str(item.get('reason', '')).strip()}",
                     str(element.get("source_id") or ""))
    return facts, blocks


def change_brief_inputs(project_id: str, change_id: str, final: bool, skip_gaps: tuple[str, ...] = ()) -> BriefInputs:
    from ..changes import deferred_gaps
    from ..compilers.change_brief import collect_change_brief_inputs
    from ..sources import load_source_manifest

    inputs = collect_change_brief_inputs(project_id, change_id)
    if skip_gaps:  # IMP-427: the series' own gaps (GAP-SPLIT-*) are not content of the change the series is cut from
        inputs = {**inputs, "gaps": [g for g in inputs["gaps"] if not str(g.get("id", "")).strip("`").startswith(skip_gaps)]}
    template = _template()
    language = inputs["language"] if inputs.get("language") in ("es", "en") else "es"
    lang = _lang(language)
    copy, change_copy = COPY[lang], template["copy"][lang]
    tags = DELTA_TAGS[lang]
    base = workspace_path(project_id)
    change = inputs["change"]
    border = list(change.get("border") or [])
    view = inputs.get("extraction") or {}
    has_inventory = view.get("state", "missing") != "missing"

    # IMP-414: the final body is the consolidated text; the control table says what is replaced, kept or excluded
    consolidated = bool(final and has_inventory)
    control_rows: dict[str, dict] = {}
    replacements: dict[str, dict] = {}
    by_element = {e["id"]: e for e in view.get("elements", [])} if has_inventory else {}
    v2_schema: dict[str, Any] = {}
    element_places: dict[str, str] = {}  # element id -> where the final body wrote it (the annex names it)
    if consolidated:
        from ..brief_schema import load_brief_schema
        from ..consolidation_control import consolidation_control
        from ..extraction.consolidation import load_consolidation

        control_rows = {r["element"]: r for r in consolidation_control(project_id, change_id)["rows"]}
        stored = load_consolidation(base, change_id)["replacements"]
        replacements = {i: stored[i] for i, r in control_rows.items() if r["status"] == "modificado" and i in stored}
        if request_follows_v2(list(by_element.values())):
            v2_schema = load_brief_schema()

    def border_facts(add_fact: Any, every_rows: list[dict]) -> None:
        # the border: surfaces to build or touch (6.1, so each is a build item with its rows) and to preserve (6.2)
        _border_facts(border, [] if consolidated else every_rows, copy, add_fact)

    facts, blocks = extraction_places(
        project_id, change_id, view, language, border=border, tags=True, after_rows=border_facts,
        consolidation={"control_rows": control_rows, "replacements": replacements, "v2_schema": v2_schema,
                       "element_places": element_places} if consolidated else None)

    def add_fact(place: str, tag: str, text: str, source: str = "", gap: str = "") -> None:
        label = f"[{tags[tag]}] " if tag else ""
        facts.setdefault(place, []).append({"text": f"{label}{text}", "source": source, "gap": gap})

    # answers of closed questions, at the place the project routes them to
    for gap in inputs["gaps"]:
        if str(gap.get("status", "OPEN")).strip("`").upper() != "CLOSED":
            continue
        gap_id = str(gap["id"]).strip("`")
        if gap.get("closure_reason") == "assumed":
            continue  # IMP-412: an assumption is no fact: its statement is in section 8, to validate
        if consolidated and (gap_id.startswith(DECISION_PREFIXES) or gap.get("closure_reason") == "superseded"):
            continue  # IMP-414: applied in the elements; the annex lists it
        if gap.get("closure_reason") == "superseded":
            add_fact("6.2", "", f"{'Decisión reemplazada' if lang == 'es' else 'Replaced decision'}: {gap_id} — "
                     f"{str(gap.get('resolution_note', '')).strip()}", gap=gap_id)
            continue
        answer = str(gap.get("answer", "")).strip()
        tag = "nuevo"
        text = answer or change_copy["no_text"]
        if gap.get("closure_reason") == "by_baseline":
            path = re.search(r"`([^`]+)`", str(gap.get("evidence", "")))
            quote = re.search(r'"([^"]*)"|“([^”]*)”', str(gap.get("evidence", "")))
            if path and quote:
                said = (quote.group(1) if quote.group(1) is not None else quote.group(2)).strip()
                tag = "preservado"
                text = (f"{answer or change_copy['no_text']} — {change_copy['baseline_support']}: «{said}» (`{path.group(1).strip()}`)"
                        if _is_divergence(gap) else f"{change_copy['already']}: «{said}» (`{path.group(1).strip()}`)")
        add_fact(gap_place(gap_id, str(gap.get("lens", ""))), tag, text, gap=gap_id)

    # the code facts of the harvest that belong to the border's blocks (as in the project)
    _harvest_facts(inputs.get("harvest") or {}, border, template, add_fact)

    # the seal, and the open questions with their class and owner
    seal = build_seal(project_id, change_id, final, language)
    blocks["0.2"] = seal_lines(seal, language) + [""]
    classes = {d["id"]: d["impact"] for d in deferred_gaps(project_id, change_id)}
    open_rows = [gap for gap in inputs["gaps"] if str(gap.get("status", "OPEN")).strip("`").upper() != "CLOSED"]
    if open_rows:
        header = copy["table"]
        table = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
        for gap in sorted(open_rows, key=lambda g: str(g["id"])):
            gap_id = str(gap["id"]).strip("`")
            klass = copy["blocking"] if gap.get("blocks") else copy[classes.get(gap_id, "construccion")]
            question = _cell(gap.get("question") or gap.get("description"))
            table.append(f"| `{gap_id}`{': ' + question if question else ''} | {klass} | "
                         f"{copy['yes'] if gap.get('blocks') else copy['no']} | {_cell(gap.get('owner')) or '-'} |")
        blocks["7.1"] = table

    # IMP-412: the open assumptions of the change fill section 8; an empty closes_gap keeps V2_GAP_ROUTES from injecting them
    to_validate = "— a validar con" if lang == "es" else "— to validate with"
    assumptions = [{"id": row["id"], "statement": f"{row['statement']} {to_validate} {row['validate_with']}",
                    "status": row["status"], "closes_gap": ""} for row in open_change_assumptions(project_id, change_id)]
    manifest = load_source_manifest(project_id)
    mine = {str(i) for i in change.get("sources") or []}
    registry = [row for row in manifest.get("registry", []) if isinstance(row, dict) and str(row.get("id")) in mine]
    settings = brief_settings(project_id)
    extra_annexes: list[dict[str, Any]] = []
    if consolidated:  # IMP-414: the decisions annex rides the final export only; the working draft keeps its shape
        extra_annexes.append({"id": change_copy["decisions_id"], "title": change_copy["decisions_title"],
                              "lines": decision_log_lines(project_id, change_id, language, element_places, replacements)})
    return BriefInputs(
        project_id=project_id,
        language=language,
        profiles=change_profiles(border, settings),
        genesis=GENESIS,
        validation_direction="to-build",
        raw_sources=[],
        gap_answers=[],
        gaps=[{"id": str(g["id"]).strip("`"), "severity": str(g.get("severity", "")).strip("`"),
               "status": str(g.get("status", "")).strip("`"), "origin": str(g.get("origin", "")).strip("`")}
              for g in inputs["gaps"]],
        assumptions=assumptions,
        harvest={},
        registry=registry,
        title=change_copy["heading"].format(change_id=change_id, title=inputs.get("note_title", "")),
        place_facts=facts,
        place_blocks=blocks,
        empty_na={"reason": copy["reason"], "condition": copy["condition"]},
        extra_annexes=extra_annexes,
    )


def decision_log_lines(project_id: str, change_id: str, language: str, places: dict[str, str],
                       replacements: dict[str, dict] | None = None) -> list[str]:
    """IMP-414: the annex of the final export, one row per closed decision (assumptions stay in section 8).

    `places` maps an element id to the place the final body wrote it; a decision sits where the first element
    that applied it sits, else where its answer routes (`gap_place`). Reuses closed_decisions,
    superseded_decisions and delegated_summary; creates nothing of its own."""
    from ..decision_memory import closed_decisions, superseded_decisions
    from ..delegation import delegated_summary

    copy = _template()["copy"][_lang(language)]
    decisions = sorted(closed_decisions(project_id, change_id), key=lambda d: d["id"])
    replaced = sorted(superseded_decisions(project_id, change_id), key=lambda d: d["id"])
    if not decisions and not replaced:
        return [copy["decisions_none"]]
    delegated = set(delegated_summary(project_id, change_id)["gaps"])
    applied: dict[str, str] = {}
    for element_id, found in (replacements or {}).items():
        for gap in found.get("decisions") or []:
            if element_id in places:
                applied.setdefault(str(gap), places[element_id])
    rows = [copy["decisions_header"], "|---|---|---|---|---|"]
    for item in decisions:
        gap = item["id"]
        place = applied.get(gap) or next((places[e] for e in item["elements"] if e in places), "")
        place = place or gap_place(gap, item.get("lens", ""))
        said = _cell(str(item["answer"]).strip().split("\n")[0])
        said = said if len(said) <= 120 else said[:119].rstrip() + "…"
        who = copy["decisions_delegated"] if gap in delegated else _cell(item["owner"]) or copy["decisions_default_owner"]
        rows.append(f"| {gap} | {place} | {said} | {item['option'] or '—'} | {who} |")
    for item in replaced:
        rows.append(f"| {item['id']} | {applied.get(item['id']) or gap_place(item['id'], '')} | {_cell(item['note'])} | — | — |")
    return rows


def _is_divergence(gap: dict) -> bool:
    gap_id = str(gap.get("id", ""))
    return (gap_id.startswith("GAP-HRV-") and str(gap.get("kind", "")).strip("`").lower() != "domain"
            and str(gap.get("origin", "harvest")).strip("`").lower() == "harvest")


def render_change_deliverable_parts(project_id: str, change_id: str, final: bool,
                                    skip_gaps: tuple[str, ...] = ()) -> tuple[str, dict[str, Any]]:
    """The deliverable text and the compile report of the project's compiler (`fill_sites` count its pending marks)."""
    text, report = render_brief_v2(change_brief_inputs(project_id, change_id, final, skip_gaps))[:2]
    return text, report


def render_change_deliverable(project_id: str, change_id: str, final: bool) -> str:
    return render_change_deliverable_parts(project_id, change_id, final)[0]


# --- IMP-410: the lens view of the change (what the request says, placed where the brief v2 reads it) ---

COHERENCE_SECTION_PLACES: tuple[tuple[str, str], ...] = (
    (r"objetivo|objective|problema|problem", "1.1"),
    (r"usuario|user|actor|rol|role", "2.1"),
    (r"as-is|situacion actual|proceso actual|current", "3.1"),
    (r"proceso|process|flujo|flow|to-be|estado futuro", "3.2"),
    (r"alcance|scope", "1.3"),
    (r"preserva|preserved|se mantiene", "6.2"),
    (r"pantalla|screen|diseno|design|prototipo|ux|ui", "4.1"),
    (r"endpoint|api|contrato|contract|servicio|service", "5.7"),
    (r"dato|data|tabla|table|modelo|model", "5.4"),
    (r"integracion|integration|arquitectura|architecture", "5.1"),
    (r"error|excepcion|exception|caso borde|edge", "3.6"),
    (r"criterio|acceptance", "1.5"),
    (r"regla|rule", "2.2"),
)
COHERENCE_UNPLACED = "1.4"
COHERENCE_KIND_PLACES = {"rule": "2.2", "criterion": "1.5", "story": "3.2"}
BORDER_LENS_PLACES = {"pantalla": "4.1", "endpoint": "5.7", "dato": "5.4", "integracion": "5.6", "regla": "2.2",
                      "proceso": "3.2", "rol": "2.1"}
COHERENCE_TITLE = {"es": "Coherencia entre lentes — {change_id}", "en": "Lens coherence — {change_id}"}


def coherence_place(element: dict) -> str:
    """The v2 place where an element of the request lands for the lens view."""
    from ..extraction.inventory import _fold

    kind = str(element.get("kind") or "")
    heading = _fold(str(element.get("section") or ""))
    if kind in COHERENCE_KIND_PLACES:
        return COHERENCE_KIND_PLACES[kind]
    if kind == "decision":
        design = next(pattern for pattern, place in COHERENCE_SECTION_PLACES if place == "4.1")
        return "4.3" if str(element.get("id", "")).startswith("PD-") or re.search(design, heading) else "2.2"
    for pattern, place in COHERENCE_SECTION_PLACES:
        if re.search(pattern, heading):
            return place
    return COHERENCE_UNPLACED


def _request_elements(project_id: str, change_id: str) -> list[tuple[dict, str]]:
    """(element, its verbatim text flattened) of every current request source of the change."""
    from ..extraction.inventory import _read_text, _row_path, _split_lines, parse_request_elements, pedido_rows, span_text

    base = workspace_path(project_id)
    found: list[tuple[dict, str]] = []
    for row in pedido_rows(project_id, change_id):
        path = _row_path(row)
        text = _read_text(base, path)
        if text is None:
            continue
        lines = _split_lines(text)
        for element in parse_request_elements(text, str(row["id"]), path):
            found.append((element, " ".join(span_text(lines, element.get("spans", []), element.get("cspan")).split())))
    return found


def coherence_brief_inputs(project_id: str, change_id: str) -> tuple[BriefInputs, list[str]]:
    """The change seen by lenses: the request's elements, the border and the harvest facts, at v2 places."""
    from ..compilers.change_brief import collect_change_brief_inputs
    from ..sources import load_source_manifest

    inputs = collect_change_brief_inputs(project_id, change_id, extraction=False)
    template = _template()
    language = inputs["language"] if inputs.get("language") in ("es", "en") else "es"
    lang = _lang(language)
    copy = COPY[lang]
    tags = DELTA_TAGS[lang]
    change = inputs["change"]
    border = list(change.get("border") or [])
    facts: dict[str, list[dict[str, str]]] = {}

    def add_fact(place: str, tag: str, text: str, source: str = "", gap: str = "") -> None:
        label = f"[{tags[tag]}] " if tag else ""
        facts.setdefault(place, []).append({"text": f"{label}{text}", "source": source, "gap": gap})

    unplaced: list[str] = []
    for element, flat in _request_elements(project_id, change_id):
        place = coherence_place(element)
        if place == COHERENCE_UNPLACED:
            unplaced.append(str(element["id"]))
        add_fact(place, "preservado" if place == "6.2" else "nuevo", f"{flat} ({element['id']})", str(element["source_id"]))
    # no EARS rows here: they come from the extraction, which runs after the coherence, and would make it stale
    _border_facts(border, [], copy, add_fact)
    for item in border:
        place = BORDER_LENS_PLACES.get(str(item.get("type")))
        if place and item.get("zone") in ZONE_TAG:
            add_fact(place, ZONE_TAG[item["zone"]], f"{item.get('type', '')} — {item.get('name', '')}", gap="GAP-SCOPE")
    _harvest_facts(inputs.get("harvest") or {}, border, template, add_fact)

    manifest = load_source_manifest(project_id)
    mine = {str(i) for i in change.get("sources") or []}
    registry = [row for row in manifest.get("registry", []) if isinstance(row, dict) and str(row.get("id")) in mine]
    brief_inputs = BriefInputs(
        project_id=project_id,
        language=language,
        profiles=change_profiles(border, brief_settings(project_id)),
        genesis=GENESIS,
        validation_direction="to-build",
        raw_sources=[],
        gap_answers=[],
        gaps=[{"id": str(g["id"]).strip("`"), "severity": str(g.get("severity", "")).strip("`"),
               "status": str(g.get("status", "")).strip("`"), "origin": str(g.get("origin", "")).strip("`")}
              for g in inputs["gaps"]],
        assumptions=[],
        harvest={},
        registry=registry,
        title=COHERENCE_TITLE[lang].format(change_id=change_id),
        place_facts=facts,
        place_blocks={},
        empty_na={"reason": copy["reason"], "condition": copy["condition"]},
    )
    return brief_inputs, unplaced
