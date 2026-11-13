"""IMP-273 (H17b): to-be diagrams, deterministic Mermaid from the v2 brief.

`/view PROJECT_ID --artifact diagrams`. One card per diagram, each with what changes and
what is still to define:

* §3.4 State Machine and Lifecycle -> ``stateDiagram-v2``;
* §3.3 Sequence Diagram / To-Be Flow -> ``sequenceDiagram``;
* §5.1 components plus §5.6 integration map -> ``flowchart`` with each component's status
  (new, extends, unchanged, retired), and a compared As-Is when something already exists;
* the confirmed release series -> ``flowchart`` with its waves (the guide of IMP-269).

**Nothing is inferred.** A diagram is drawn only from structured lines of its section:
``A → B: label`` (also ``->``), ``Component (new)`` or a Markdown table whose header names
its columns. A pending section draws a dashed placeholder with its GAP; a populated section
without such lines is a "no diagrammable notation" card that says how to write it. A
conditional or optional line is dashed, like everything pending.

The view inlines the vendored mermaid (``sentinel/vendor/mermaid``, pinned by sha256 and
checked by /doctor) because the views' CSP admits inline scripts only. Without it (a minimal
``.pyz``) or when its hash does not match, each card shows its code with "not rendered".
"""
from __future__ import annotations

import hashlib
import html
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .brief_model import V2_PENDING_RE, parse_brief
from .citations import CITATION_RE as STRUCTURED_CITATION_RE
from .core.io import write_text
from .core.local_browser import open_local_file
from .core.markdown import parse_table_rows
from .resources import package_resource
from .secrets_scan import assert_no_leaks
from .shell import content_fingerprint, render_shell, template_text, theme_argument_for_display
from .themes import DEFAULT_THEME, legend_html
from .workspace import read_json, workspace_path

MERMAID_VERSION = "11.17.2"
MERMAID_SHA256 = "581ed7d74bd9048d0e3a91363927d72ef22942d7722546b27f7cc29e35390eb8"
MERMAID_LICENSE_SHA256 = "ec9fb67dcb25eccc416ed56e1aab819222c805a2a4bfe4cb19e7556bf2ffde80"
VENDOR_DIR = ("vendor", "mermaid")
MERMAID_FILE = "mermaid.min.js"
LICENSE_FILE = "LICENSE"

MAX_EDGES = 24  # a bigger diagram is split in parts of at most this many edges
MAX_LABEL = 60
STATUSES = ("new", "extends", "unchanged", "retired")
STATUS_ALIASES = {
    "new": "new", "nuevo": "new", "nueva": "new",
    "extends": "extends", "extended": "extends", "extiende": "extends", "extendido": "extends",
    "unchanged": "unchanged", "sin cambios": "unchanged", "sin cambio": "unchanged",
    "retired": "retired", "retire": "retired", "se retira": "retired", "retira": "retired", "retirado": "retired",
}
# Which semantic role of the theme paints each class (the legend says it once).
CLASS_ROLE = {
    "st_new": "ok", "st_extends": "info", "st_retired": "block", "st_pending": "warn",
    "st_closed": "ok", "st_open": "info", "st_waiting": "block",
}
DASHED = "stroke-dasharray:6 4"

CITATION_RE = re.compile(r"\[\[.*?\]\]")  # strips any citation, even one with brackets inside
ARROW_RE = re.compile(r"^(?P<a>.+?)\s*(?:→|->)\s*(?P<b>.+?)(?:\s*:\s*(?P<label>.+))?$")
COMPONENT_RE = re.compile(r"^(?P<name>[^()]+?)\s*\((?P<status>[^)]+)\)\s*\.?$")
CONDITIONAL_RE = re.compile(r"\b(condicional|conditional|opcional|optional)\b", re.IGNORECASE)
NA_RE = re.compile(r"^\s*N/A\b")
LIST_RE = re.compile(r"^\s*(?:[-*]|\d+\.)\s+(.*)$")
HEADING_RE = re.compile(r"^#{1,6}\s")
UNSAFE_LABEL = re.compile(r"[\"`<>\[\]{}|;#:\\]")

# Table headers, by role (lower-case, es and en).
HEADERS = {
    "from": ("from", "de", "origen", "source", "desde", "state", "estado", "estado actual", "current state", "system", "sistema"),
    "to": ("to", "a", "hacia", "destino", "target", "next", "next state", "estado siguiente", "siguiente", "estado destino"),
    "label": ("event", "evento", "message", "mensaje", "contract", "contrato", "protocol", "protocolo", "label", "etiqueta", "trigger", "disparador"),
    "component": ("component", "componente", "name", "nombre"),
    "status": ("status", "estado"),
}

COPY = {
    "en": {
        "label": "To-Be Diagrams",
        "state": "State machine and lifecycle", "sequence": "Sequence / to-be flow", "architecture": "Architecture and integrations",
        "architecture-asis": "Architecture today (As-Is)", "series": "Release series",
        "part": "part {n} of {total}",
        "pending_node": "Pending · {gaps}", "pending_any": "Pending",
        "no_notation": "No diagrammable notation",
        "how": {
            "state": "write each transition as `STATE → STATE: event`, or a table | State | Event | Next state |",
            "sequence": "write each message as `Actor → Actor: message`, or a table | From | To | Message |",
            "architecture": "write each component as `Name (new|extends|unchanged|retired)` in §5.1 and each integration as `A → B: contract` in §5.6",
        },
        "changes": "What changes", "missing": "What is still to define", "sources": "Sources", "code": "Mermaid code",
        "nothing": "nothing", "unrendered": "Not rendered: the code is shown as is.",
        "render_error": "Not rendered (mermaid error):",
        "na": "Not applicable", "gap": "{gap}: pending",
        "external": "{name}: in the integration map but not among the §5.1 components (confirm it there)",
        "summary_state": "{states} states, {transitions} transitions", "summary_sequence": "{participants} participants, {messages} messages",
        "summary_architecture": "{components} components ({statuses}), {edges} integrations",
        "summary_series": "{releases} releases in {waves} waves", "summary_asis": "{components} components exist today",
        "conditional": "{n} conditional or optional (dashed)",
        "status": {"new": "new", "extends": "extends", "unchanged": "unchanged", "retired": "retired"},
        "release_status": {"closed": "closed", "open": "open", "waiting": "waiting on a dependency"},
        "legend": "Diagram legend", "dashed": "Dashed border or line: pending, conditional or optional",
        "wave": "Wave {n}", "renderer": "Rendered locally with the vendored mermaid {version} (MIT License, © Knut Sveidqvist and contributors).",
        "no_renderer": "No renderer available: {why}. Each diagram shows its code.",
        "why_missing": "the vendored mermaid is not bundled (minimal .pyz)", "why_hash": "the vendored mermaid failed its sha256 check",
        "why_unsafe": "the vendored mermaid cannot be inlined safely",
    },
    "es": {
        "label": "Diagramas To-Be",
        "state": "Máquina de estados y ciclo de vida", "sequence": "Secuencia / flujo to-be", "architecture": "Arquitectura e integraciones",
        "architecture-asis": "Arquitectura hoy (As-Is)", "series": "Serie de releases",
        "part": "parte {n} de {total}",
        "pending_node": "Pendiente · {gaps}", "pending_any": "Pendiente",
        "no_notation": "Sin notación diagramable",
        "how": {
            "state": "escribí cada transición como `ESTADO → ESTADO: evento`, o una tabla | Estado | Evento | Estado siguiente |",
            "sequence": "escribí cada mensaje como `Actor → Actor: mensaje`, o una tabla | Origen | Destino | Mensaje |",
            "architecture": "escribí cada componente como `Nombre (nuevo|extiende|sin cambios|se retira)` en §5.1 y cada integración como `A → B: contrato` en §5.6",
        },
        "changes": "Qué cambia", "missing": "Qué falta definir", "sources": "Fuentes", "code": "Código Mermaid",
        "nothing": "nada", "unrendered": "Sin renderizar: se muestra el código tal cual.",
        "render_error": "Sin renderizar (error de mermaid):",
        "na": "No aplica", "gap": "{gap}: pendiente",
        "external": "{name}: está en el mapa de integraciones pero no entre los componentes de §5.1 (confirmarlo ahí)",
        "summary_state": "{states} estados, {transitions} transiciones", "summary_sequence": "{participants} participantes, {messages} mensajes",
        "summary_architecture": "{components} componentes ({statuses}), {edges} integraciones",
        "summary_series": "{releases} releases en {waves} olas", "summary_asis": "{components} componentes existen hoy",
        "conditional": "{n} condicionales u opcionales (punteados)",
        "status": {"new": "nuevo", "extends": "extiende", "unchanged": "sin cambios", "retired": "se retira"},
        "release_status": {"closed": "cerrado", "open": "abierto", "waiting": "esperando una dependencia"},
        "legend": "Leyenda de los diagramas", "dashed": "Borde o línea punteada: pendiente, condicional u opcional",
        "wave": "Ola {n}", "renderer": "Renderizado localmente con mermaid {version} vendorizado (licencia MIT, © Knut Sveidqvist y colaboradores).",
        "no_renderer": "Sin renderizador disponible: {why}. Cada diagrama muestra su código.",
        "why_missing": "mermaid vendorizado no está incluido (.pyz mínimo)", "why_hash": "mermaid vendorizado no pasó la verificación sha256",
        "why_unsafe": "mermaid vendorizado no se puede incrustar de forma segura",
    },
}


class DiagramsError(ValueError):
    """The diagrams cannot be built (no brief, or a v1 brief)."""


# --- parsing the brief -------------------------------------------------------------------


def clean_label(text: str) -> str:
    """A label Mermaid accepts, without citations or syntax characters; truncated."""
    text = CITATION_RE.sub(" ", text)
    text = re.sub(r"\*\*|__", "", text)
    text = UNSAFE_LABEL.sub(" ", text)
    text = " ".join(text.split()).strip(" .,-")
    return text if len(text) <= MAX_LABEL else text[: MAX_LABEL - 1].rstrip() + "…"


def _section_lines(text: str, sid: str) -> list[str] | None:
    model = parse_brief(text)
    section = model.sections.get(sid)
    if section is None:
        return None
    return text.splitlines()[section.start + 1:section.end]


def _cited(line: str) -> list[str]:
    ids: list[str] = []
    for match in STRUCTURED_CITATION_RE.finditer(line):
        if match.group("id") not in ids:
            ids.append(match.group("id"))
    return ids


def _table_roles(header: list[str], wanted: tuple[str, ...]) -> dict[str, int] | None:
    """Column index per role, or None when the header does not name every wanted role."""
    found: dict[str, int] = {}
    for index, cell in enumerate(header):
        name = clean_label(cell).lower()
        for role in wanted:
            if role not in found and name in HEADERS[role]:
                found[role] = index
                break
    return found if all(role in found for role in wanted) else None


def read_section(text: str, sids: tuple[str, ...]) -> dict[str, Any]:
    """The facts of one or more sections: list items, table rows, gaps, sources, N/A."""
    items: list[str] = []
    tables: list[list[list[str]]] = []
    gaps: list[str] = []
    sources: list[str] = []
    populated = na = pending = False
    present = False
    for sid in sids:
        lines = _section_lines(text, sid)
        if lines is None:
            continue
        present = True
        table: list[str] = []
        for line in lines + [""]:
            if line.strip().startswith("|"):
                table.append(line)
                continue
            if table:
                rows = parse_table_rows("\n".join(table), skip_separator_rows=True)
                if len(rows) > 1:
                    tables.append(rows)
                    populated = True
                    for row in rows[1:]:
                        sources += [s for s in _cited(" ".join(row)) if s not in sources]
                table = []
            stripped = line.strip()
            if not stripped or HEADING_RE.match(stripped):
                continue
            marks = list(V2_PENDING_RE.finditer(stripped))
            if marks:
                pending = True
                for mark in marks:
                    for gap in re.split(r"[,\s]+", (mark.group("gap") or "").strip()):
                        if gap.startswith("GAP-") and gap not in gaps:
                            gaps.append(gap)
                continue
            if NA_RE.match(stripped):
                na = True
                continue
            populated = True
            match = LIST_RE.match(stripped)
            body = match.group(1) if match else stripped
            items.append(body)
            sources += [s for s in _cited(body) if s not in sources]
    return {"present": present, "items": items, "tables": tables, "gaps": gaps, "sources": sources,
            "populated": populated, "na": na, "pending": pending}


def _edge(a: str, b: str, label: str, raw: str) -> dict[str, Any] | None:
    a, b = clean_label(a), clean_label(b)
    if not a or not b:
        return None
    return {"from": a, "to": b, "label": clean_label(label or ""), "conditional": bool(CONDITIONAL_RE.search(raw))}


def parse_edges(facts: dict[str, Any]) -> list[dict[str, Any]]:
    """`A → B: label` items and From | To | Label tables, in document order, deduplicated."""
    edges: list[dict[str, Any]] = []
    for item in facts["items"]:
        plain = CITATION_RE.sub("", item).strip()
        match = ARROW_RE.match(plain)
        if match:
            edge = _edge(match.group("a"), match.group("b"), match.group("label") or "", plain)
            if edge:
                edges.append(edge)
    for rows in facts["tables"]:
        roles = _table_roles(rows[0], ("from", "to"))
        if roles is None or roles["from"] == roles["to"]:
            continue
        label_roles = _table_roles(rows[0], ("label",))
        for row in rows[1:]:
            cell = lambda i: row[i] if i < len(row) else ""  # noqa: E731
            edge = _edge(cell(roles["from"]), cell(roles["to"]), cell(label_roles["label"]) if label_roles else "",
                         CITATION_RE.sub("", " ".join(row)))
            if edge:
                edges.append(edge)
    unique: list[dict[str, Any]] = []
    for edge in edges:
        if edge not in unique:
            unique.append(edge)
    return unique


def normalize_status(text: str) -> str:
    return STATUS_ALIASES.get(" ".join(clean_label(text).lower().split()), "")


def parse_components(facts: dict[str, Any]) -> list[dict[str, str]]:
    """`Name (status)` items and Component | Status tables; the first status of a name wins."""
    found: list[dict[str, str]] = []
    for item in facts["items"]:
        match = COMPONENT_RE.match(CITATION_RE.sub("", item).strip())
        if match and normalize_status(match.group("status")):
            found.append({"name": clean_label(match.group("name")), "status": normalize_status(match.group("status"))})
    for rows in facts["tables"]:
        roles = _table_roles(rows[0], ("component", "status"))
        if roles is None or roles["component"] == roles["status"]:
            continue
        for row in rows[1:]:
            if max(roles.values()) < len(row) and normalize_status(row[roles["status"]]):
                found.append({"name": clean_label(row[roles["component"]]), "status": normalize_status(row[roles["status"]])})
    unique: dict[str, dict[str, str]] = {}
    for component in found:
        if component["name"]:
            unique.setdefault(component["name"], component)
    return list(unique.values())


# --- Mermaid -----------------------------------------------------------------------------


def _ids(names: list[str], prefix: str) -> dict[str, str]:
    return {name: f"{prefix}{index}" for index, name in enumerate(names, start=1)}


def _order(edges: list[dict[str, Any]], seed: list[str] | None = None) -> list[str]:
    names = list(seed or [])
    for edge in edges:
        for name in (edge["from"], edge["to"]):
            if name not in names:
                names.append(name)
    return names


def _class_defs(used: set[str]) -> list[str]:
    lines = []
    for name in sorted(used):
        if name in {"st_pending", "st_conditional"}:
            style = DASHED
        elif name in {"st_unchanged", "st_external"}:
            style = "stroke-width:1px"
        else:
            style = "stroke-width:2px"
        lines.append(f"  classDef {name} {style}")
    return lines


def pending_mermaid(gaps: list[str], copy: dict[str, Any]) -> str:
    text = copy["pending_node"].format(gaps=", ".join(gaps)) if gaps else copy["pending_any"]
    return "\n".join(["flowchart LR", f'  p1["⏳ {clean_label(text)}"]:::st_pending', *_class_defs({"st_pending"})]) + "\n"


def state_mermaid(edges: list[dict[str, Any]]) -> str:
    names = _order(edges)
    ids = _ids(names, "s")
    outgoing = {edge["from"] for edge in edges}
    incoming = {edge["to"] for edge in edges}
    lines = ["stateDiagram-v2"]
    lines += [f'  state "{name}" as {ids[name]}' for name in names]
    starts = [name for name in names if name not in incoming] or names[:1]
    lines += [f"  [*] --> {ids[name]}" for name in starts]
    for edge in edges:  # a state reached only conditionally is dashed (stateDiagram has no dashed transition)
        lines.append(f"  {ids[edge['from']]} --> {ids[edge['to']]}" + (f" : {edge['label']}" if edge["label"] else ""))
    lines += [f"  {ids[name]} --> [*]" for name in names if name not in outgoing]
    conditional_only = [name for name in names if name in incoming
                        and all(e["conditional"] for e in edges if e["to"] == name)]
    if conditional_only:
        lines.append("  class " + ",".join(ids[n] for n in conditional_only) + " st_conditional")
        lines += _class_defs({"st_conditional"})
    return "\n".join(lines) + "\n"


def sequence_mermaid(edges: list[dict[str, Any]]) -> str:
    names = _order(edges)
    ids = _ids(names, "p")
    lines = ["sequenceDiagram"]
    lines += [f"  participant {ids[name]} as {name}" for name in names]
    for edge in edges:
        arrow = "-->>" if edge["conditional"] else "->>"
        lines.append(f"  {ids[edge['from']]}{arrow}{ids[edge['to']]}: {edge['label'] or '…'}")
    return "\n".join(lines) + "\n"


def architecture_mermaid(components: list[dict[str, str]], edges: list[dict[str, Any]], pending: str = "") -> str:
    status = {c["name"]: c["status"] for c in components}
    names = _order(edges, [c["name"] for c in components])
    ids = _ids(names, "c")
    used: set[str] = set()
    lines = ["flowchart LR"]
    for name in names:
        klass = f"st_{status[name]}" if name in status else "st_external"
        used.add(klass)
        shape = f'{ids[name]}["{name}"]' if name in status else f'{ids[name]}(["{name}"])'
        lines.append(f"  {shape}:::{klass}")
    if pending:
        lines.append(f'  pending1["⏳ {clean_label(pending)}"]:::st_pending')
        used.add("st_pending")
    for edge in edges:
        arrow = "-.->" if edge["conditional"] else "-->"
        label = f'|"{edge["label"]}"|' if edge["label"] else ""  # quoted: a label may carry parentheses
        lines.append(f"  {ids[edge['from']]} {arrow}{label} {ids[edge['to']]}")
    return "\n".join(lines + _class_defs(used)) + "\n"


def asis_mermaid(components: list[dict[str, str]]) -> str:
    existing = [c for c in components if c["status"] != "new"]
    lines = ["flowchart LR"]
    lines += [f'  a{index}["{c["name"]}"]:::st_unchanged' for index, c in enumerate(existing, start=1)]
    return "\n".join(lines + _class_defs({"st_unchanged"})) + "\n"


def series_mermaid(waves: dict[str, list[str]], releases: list[dict[str, Any]], copy: dict[str, Any]) -> str:
    by_id = {r["id"]: r for r in releases}
    used: set[str] = set()
    lines = ["flowchart LR"]
    for wave, ids in waves.items():
        lines.append(f'  subgraph w{wave}["{clean_label(copy["wave"].format(n=wave))}"]')
        for rid in ids:
            release = by_id.get(rid, {"id": rid, "name": "", "type": "", "status": "open"})
            klass = f"st_{release['status']}"
            used.add(klass)
            label = clean_label(" · ".join(p for p in (rid, release["name"], release["type"]) if p))
            lines.append(f'    {rid.lower()}["{label}"]:::{klass}')
        lines.append("  end")
    for release in releases:
        for dep in release["depends_on"]:
            arrow = "-->" if dep["strength"] == "hard" else "-.->"
            label = f'|"{clean_label(dep["consumes"])}"|' if dep["consumes"] else ""
            lines.append(f"  {dep['release'].lower()} {arrow}{label} {release['id'].lower()}")
    return "\n".join(lines + _class_defs(used)) + "\n"


def split_edges(edges: list[dict[str, Any]], limit: int = MAX_EDGES) -> list[list[dict[str, Any]]]:
    """A big diagram is split in consecutive parts of at most `limit` edges (never zero parts)."""
    if len(edges) <= limit:
        return [edges]
    return [edges[i:i + limit] for i in range(0, len(edges), limit)]


# --- the model ---------------------------------------------------------------------------


def _card(kind: str, copy: dict[str, Any], sections: list[str], facts: dict[str, Any], **extra: Any) -> dict[str, Any]:
    card = {
        "id": kind, "kind": kind, "title": copy[kind], "sections": sections, "status": "drawn",
        "mermaid": "", "changes": [], "missing": [copy["gap"].format(gap=g) for g in facts.get("gaps", [])],
        "gaps": list(facts.get("gaps", [])), "sources": list(facts.get("sources", [])), "chips": [],
    }
    card.update(extra)
    return card


def _undrawn(kind: str, copy: dict[str, Any], sections: list[str], facts: dict[str, Any]) -> dict[str, Any] | None:
    """The card of a section without diagrammable facts, or None when it has some."""
    if facts["pending"] and not facts["populated"]:
        return _card(kind, copy, sections, facts, status="pending", mermaid=pending_mermaid(facts["gaps"], copy))
    if facts["na"] and not facts["populated"]:
        return _card(kind, copy, sections, facts, status="not_applicable", changes=[copy["na"]])
    if not facts["present"]:
        return _card(kind, copy, sections, facts, status="not_applicable", changes=[copy["na"]])
    return None


def _edge_cards(kind: str, copy: dict[str, Any], sid: str, facts: dict[str, Any]) -> list[dict[str, Any]]:
    undrawn = _undrawn(kind, copy, [sid], facts)
    if undrawn:
        return [undrawn]
    edges = parse_edges(facts)
    if not edges:
        return [_card(kind, copy, [sid], facts, status="no_notation", mermaid="",
                      missing=[copy["no_notation"] + ": " + copy["how"][kind]] + [copy["gap"].format(gap=g) for g in facts["gaps"]])]
    parts = split_edges(edges)
    cards = []
    for index, part in enumerate(parts, start=1):
        if kind == "state":
            states = _order(part)
            code, summary = state_mermaid(part), copy["summary_state"].format(states=len(states), transitions=len(part))
        else:
            names = _order(part)
            code, summary = sequence_mermaid(part), copy["summary_sequence"].format(participants=len(names), messages=len(part))
        changes = [summary]
        conditional = sum(1 for e in part if e["conditional"])
        if conditional:
            changes.append(copy["conditional"].format(n=conditional))
        card = _card(kind, copy, [sid], facts, mermaid=code, changes=changes)
        if len(parts) > 1:
            card["id"] = f"{kind}-{index}"
            card["title"] = f"{copy[kind]} — {copy['part'].format(n=index, total=len(parts))}"
        cards.append(card)
    return cards


def _architecture_cards(copy: dict[str, Any], text: str) -> list[dict[str, Any]]:
    facts = read_section(text, ("5.1", "5.6"))
    components = parse_components(read_section(text, ("5.1",)))
    edges = parse_edges(read_section(text, ("5.6",)))
    if not components and not edges:
        undrawn = _undrawn("architecture", copy, ["5.1", "5.6"], facts)
        if undrawn:
            return [undrawn]
        return [_card("architecture", copy, ["5.1", "5.6"], facts, status="no_notation",
                      missing=[copy["no_notation"] + ": " + copy["how"]["architecture"]] + [copy["gap"].format(gap=g) for g in facts["gaps"]])]
    known = {c["name"] for c in components}
    external = [n for n in _order(edges) if n not in known]
    counts = ", ".join(f"{sum(1 for c in components if c['status'] == s)} {copy['status'][s]}"
                       for s in STATUSES if any(c["status"] == s for c in components)) or copy["nothing"]
    changes = [copy["summary_architecture"].format(components=len(components), statuses=counts, edges=len(edges))]
    conditional = sum(1 for e in edges if e["conditional"])
    if conditional:
        changes.append(copy["conditional"].format(n=conditional))
    missing = [copy["external"].format(name=n) for n in external] + [copy["gap"].format(gap=g) for g in facts["gaps"]]
    cards = []
    for index, part in enumerate(split_edges(edges), start=1):
        # Part 1 carries every component; a later part only the ones its edges touch.
        drawn = components if index == 1 else [c for c in components if c["name"] in _order(part)]
        pending = ""
        if facts["pending"] and index == 1:
            pending = copy["pending_node"].format(gaps=", ".join(facts["gaps"])) if facts["gaps"] else copy["pending_any"]
        code = architecture_mermaid(drawn, part, pending)
        card = _card("architecture", copy, ["5.1", "5.6"], facts, mermaid=code, changes=changes, missing=missing,
                     chips=[{"role": CLASS_ROLE.get(f"st_{s}", ""), "text": copy["status"][s]}
                            for s in STATUSES if any(c["status"] == s for c in components)])
        parts = len(split_edges(edges))
        if parts > 1:
            card["id"] = f"architecture-{index}"
            card["title"] = f"{copy['architecture']} — {copy['part'].format(n=index, total=parts)}"
        cards.append(card)
    if any(c["status"] != "new" for c in components):  # compared mode: what exists today
        existing = [c for c in components if c["status"] != "new"]
        cards.append(_card("architecture-asis", copy, ["5.1"], {"gaps": [], "sources": facts["sources"]},
                           mermaid=asis_mermaid(components), changes=[copy["summary_asis"].format(components=len(existing))],
                           missing=[]))
    return cards


def _series_card(project_id: str, copy: dict[str, Any]) -> dict[str, Any] | None:
    from .release_guide import _series, release_status
    from .release_split import ReleaseSplitError, _dicts, _s
    from .split_proposal import release_order

    base = workspace_path(project_id)
    try:
        partition, payload = _series(base)
    except ReleaseSplitError:
        return None  # no confirmed series: no card (a series is optional)
    releases = []
    for release in sorted(_dicts(payload.get("releases")), key=lambda r: release_order(_s(r.get("id")))):
        rid = _s(release.get("id"))
        status = release_status(base, project_id, payload, partition, rid)["status"]
        releases.append({
            "id": rid, "name": _s(release.get("name")), "type": _s(release.get("type")), "status": status,
            "depends_on": [{"release": _s(e.get("release")), "strength": _s(e.get("strength")) or "hard", "consumes": _s(e.get("consumes"))}
                           for e in _dicts(release.get("depends_on"))],
        })
    waves = {str(k): [str(r) for r in v] for k, v in (partition.get("waves") or {}).items()}
    card = _card("series", copy, ["series"], {"gaps": [], "sources": []}, mermaid=series_mermaid(waves, releases, copy),
                 changes=[copy["summary_series"].format(releases=len(releases), waves=len(waves))])
    card["chips"] = [{"role": CLASS_ROLE[f"st_{r['status']}"], "text": f"{r['id']} · {copy['release_status'][r['status']]}"} for r in releases]
    return card


def build_cards(project_id: str, text: str, language: str) -> list[dict[str, Any]]:
    copy = COPY[language]
    cards = _edge_cards("state", copy, "3.4", read_section(text, ("3.4",)))
    cards += _edge_cards("sequence", copy, "3.3", read_section(text, ("3.3",)))
    cards += _architecture_cards(copy, text)
    series = _series_card(project_id, copy)
    if series:
        cards.append(series)
    return cards


def collect_diagrams_model(project_id: str) -> dict[str, Any]:
    base = workspace_path(project_id)
    brief = base / "02_requirements" / "project-brief.md"
    if not brief.is_file():
        raise DiagramsError(f"/view diagrams needs the brief: workspaces/{project_id}/02_requirements/project-brief.md (run /brief)")
    text = brief.read_text(encoding="utf-8")
    if parse_brief(text).version != 2:
        raise DiagramsError("/view diagrams reads the v2 brief (its §3.3, §3.4, §5.1 and §5.6); this workspace compiles v1")
    state = read_json(base / "state.json", {})
    language = "es" if str(state.get("project_language", "")).lower().startswith("es") else "en"
    cards = build_cards(project_id, text, language)
    sources = [brief]
    series_dir = base / "02_requirements" / "series"
    sources += sorted(p for p in (series_dir / "partition.json", series_dir / "proposal.json") if p.is_file())
    fingerprints = [{"path": f"workspaces/{project_id}/{p.relative_to(base).as_posix()}", "sha256": content_fingerprint(p.read_bytes())}
                    for p in sources]
    return {
        "project_id": project_id,
        "artifact": "diagrams",
        "label": COPY[language]["label"],
        "language": language,
        "cards": cards,
        "summary": {
            "cards": len(cards),
            "drawn": sum(1 for c in cards if c["status"] == "drawn"),
            "pending": sum(1 for c in cards if c["status"] == "pending"),
            "no_notation": sum(1 for c in cards if c["status"] == "no_notation"),
        },
        "provenance": {
            "cutoff": max(datetime.fromtimestamp(int(p.stat().st_mtime), timezone.utc).isoformat() for p in sources),
            "source_sha256": content_fingerprint("\n".join(f"{f['path']}:{f['sha256']}" for f in fingerprints).encode("utf-8")),
            "sources": fingerprints,
        },
    }


def validate_diagrams_model(model: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    cards = model.get("cards") or []
    ids = [str(c.get("id")) for c in cards]
    for dup in sorted({i for i in ids if ids.count(i) > 1}):
        errors.append(f"duplicate card id {dup!r}")
    for card in cards:
        status = card.get("status")
        if status not in {"drawn", "pending", "no_notation", "not_applicable"}:
            errors.append(f"{card.get('id')}: unknown status {status!r}")
        if status in {"drawn", "pending"} and not card.get("mermaid"):
            errors.append(f"{card.get('id')}: a {status} card needs its Mermaid code")
        if status == "pending" and DASHED not in card.get("mermaid", ""):
            errors.append(f"{card.get('id')}: a pending card must be dashed")
    summary = model.get("summary") or {}
    if summary.get("cards") != len(cards):
        errors.append(f"summary.cards is {summary.get('cards')!r}, the model has {len(cards)}")
    provenance = model.get("provenance")
    if not isinstance(provenance, dict) or not provenance.get("cutoff") or not provenance.get("source_sha256"):
        errors.append("provenance with cutoff and source_sha256 is required")
    return errors


# --- the vendored renderer ---------------------------------------------------------------


def vendored_file(name: str) -> Any:
    return package_resource(*VENDOR_DIR, name)


def mermaid_status() -> tuple[str, str]:
    """('ok', '') when the vendored mermaid is present and matches its pinned sha256; else (reason, detail)."""
    lib = vendored_file(MERMAID_FILE)
    try:
        data = lib.read_bytes()
    except (FileNotFoundError, OSError):
        return "missing", f"{'/'.join(VENDOR_DIR)}/{MERMAID_FILE} not bundled"
    digest = hashlib.sha256(data).hexdigest()
    if digest != MERMAID_SHA256:
        return "hash", f"{MERMAID_FILE} sha256 {digest[:12]}… does not match the pinned {MERMAID_SHA256[:12]}…"
    try:
        license_digest = hashlib.sha256(vendored_file(LICENSE_FILE).read_bytes()).hexdigest()
    except (FileNotFoundError, OSError):
        return "missing", f"{'/'.join(VENDOR_DIR)}/{LICENSE_FILE} (MIT notice) not bundled"
    if license_digest != MERMAID_LICENSE_SHA256:
        return "hash", f"{LICENSE_FILE} sha256 {license_digest[:12]}… does not match the pinned {MERMAID_LICENSE_SHA256[:12]}…"
    return "ok", ""


def inline_mermaid() -> tuple[str | None, str]:
    """The vendored mermaid ready for an inline <script>, with its MIT notice; or (None, reason)."""
    status, _ = mermaid_status()
    if status != "ok":
        return None, status
    source = vendored_file(MERMAID_FILE).read_text(encoding="utf-8")
    if re.search(r"<script", source, re.IGNORECASE) and "<!--" in source:
        return None, "unsafe"
    notice = vendored_file(LICENSE_FILE).read_text(encoding="utf-8").replace("*/", "* /")
    source = re.sub(r"</(script)", r"<\\/\1", source, flags=re.IGNORECASE)
    return f"/*! mermaid {MERMAID_VERSION}\n{notice}*/\n{source}", "ok"


# --- render ------------------------------------------------------------------------------


def _chip(role: str, text: str) -> str:
    klass = f"chip chip-{html.escape(role)}" if role else "chip"
    return f'<span class="{klass}">{html.escape(text)}</span>'


def _list(items: list[str], empty: str) -> str:
    if not items:
        return f"<p class=\"muted\">{html.escape(empty)}</p>"
    return "<ul>" + "".join(f"<li>{_inline(i)}</li>" for i in items) + "</ul>"


def _inline(text: str) -> str:
    escaped = html.escape(text)
    return re.sub(r"`([^`]+)`", r"<code>\1</code>", escaped)


def _card_html(card: dict[str, Any], copy: dict[str, Any]) -> str:
    chips = [_chip(c["role"], c["text"]) for c in card["chips"]]
    chips += [_chip("warn", gap) for gap in card["gaps"]]
    sections = " · ".join(("§" + s) if s != "series" else s for s in card["sections"])
    parts = [
        f'<article class="diagram-card status-{card["status"]}" id="dg-{html.escape(card["id"])}" data-diagram="{html.escape(card["id"])}">',
        f'<header><h2>{html.escape(card["title"])}</h2><span class="sections">{html.escape(sections)}</span></header>',
    ]
    if chips:
        parts.append('<div class="chips">' + "".join(chips) + "</div>")
    if card["mermaid"]:
        parts += [
            '<div class="diagram-render" hidden></div>',
            f'<p class="unrendered" data-error="{html.escape(copy["render_error"])}">{html.escape(copy["unrendered"])}</p>',
            f'<details class="diagram-code"><summary>{html.escape(copy["code"])}</summary>'
            f'<pre class="mermaid-src">{html.escape(card["mermaid"])}</pre></details>',
        ]
    parts.append(f'<div class="facts"><div><h3>{html.escape(copy["changes"])}</h3>{_list(card["changes"], copy["nothing"])}</div>'
                 f'<div><h3>{html.escape(copy["missing"])}</h3>{_list(card["missing"], copy["nothing"])}</div></div>')
    if card["sources"]:
        parts.append(f'<p class="sources">{html.escape(copy["sources"])}: ' + ", ".join(f"<code>{html.escape(s)}</code>" for s in card["sources"]) + "</p>")
    parts.append("</article>")
    return "\n".join(parts)


def _legend_html(theme: dict[str, Any], copy: dict[str, Any], language: str) -> str:
    entries = [_chip("", copy["dashed"])]
    entries += [_chip(CLASS_ROLE[f"st_{s}"] if f"st_{s}" in CLASS_ROLE else "", copy["status"][s]) for s in STATUSES]
    entries += [_chip(CLASS_ROLE[f"st_{s}"], copy["release_status"][s]) for s in ("closed", "open", "waiting")]
    title = "Leyenda de colores" if language == "es" else "Colour legend"
    return (f'<section class="view-section" id="legend"><h2>{html.escape(copy["legend"])}</h2>'
            f'<ul class="legend diagram-legend">' + "".join(f"<li>{e}</li>" for e in entries) + "</ul>"
            f"<h3>{title}</h3>{legend_html(theme, language)}</section>")


def _provenance_html(model: dict[str, Any], theme_arg: str, copy: dict[str, Any], renderer: str) -> str:
    provenance = model["provenance"]
    heading = "Procedencia" if model["language"] == "es" else "Provenance"
    command = html.escape(f"python -m sentinel /view {model['project_id']} --artifact diagrams --theme {theme_argument_for_display(theme_arg)}")
    sources = ", ".join(f"<code>{html.escape(s['path'])}</code>" for s in provenance["sources"])
    return (f'<section class="view-section" id="provenance"><h2>{heading}</h2>'
            f"<p>Sources: {sources} · sha256 <code>{html.escape(provenance['source_sha256'])}</code> · "
            f'cut-off <time datetime="{html.escape(provenance["cutoff"])}">{html.escape(provenance["cutoff"])}</time> '
            "(the newest source modification time, not the build time).</p>"
            f"<p>{html.escape(renderer)}</p><p>Regenerate: <code>{command}</code></p></section>")


LIB_PLACEHOLDER = "/*__SENTINEL_MERMAID__*/"


def render_diagrams_view(model: dict[str, Any], theme: dict[str, Any], *, theme_arg: str | None = None,
                         with_library: bool = True) -> tuple[str, str]:
    """(page with a library placeholder, the library script or "") — the placeholder is replaced at write time."""
    errors = validate_diagrams_model(model)
    if errors:
        raise DiagramsError("diagrams model is inconsistent: " + "; ".join(errors))
    language = model["language"]
    copy = COPY[language]
    library, reason = inline_mermaid() if with_library else (None, "missing")
    if library:
        renderer = copy["renderer"].format(version=MERMAID_VERSION)
    else:
        renderer = copy["no_renderer"].format(why=copy.get(f"why_{reason}", copy["why_missing"]))
    summary = model["summary"]
    toc = "".join(f'<li><a href="#dg-{html.escape(c["id"])}">{html.escape(c["title"])}</a></li>' for c in model["cards"])
    nav = (f'<div class="view-nav"><div class="stats">{summary["drawn"]} / {summary["cards"]}</div>'
           f'<ol class="toc">{toc}</ol></div>')
    content = (
        f'<header class="view-header"><div class="eyebrow">{html.escape(model["project_id"])}</div>'
        f'<h1>{html.escape(model["label"])}</h1><p class="render-status" id="renderStatus" data-ok="{1 if library else 0}">{html.escape(renderer)}</p></header>'
        + '<div class="diagram-cards">' + "\n".join(_card_html(c, copy) for c in model["cards"]) + "</div>"
        + _legend_html(theme, copy, language)
        + _provenance_html(model, theme_arg or str(theme.get("name") or DEFAULT_THEME), copy, renderer)
        + (f"<script>{LIB_PLACEHOLDER}</script>" if library else "")
    )
    page = render_shell(
        theme=theme,
        title=f"{model['project_id']} · {model['label']} — Ignite Artifact View",
        heading=html.escape(str(model["label"])),
        nav=nav,
        content=content,
        page_css=template_text("diagrams.css"),
        page_js=template_text("diagrams.js"),
        language=language,
    )
    return page, library or ""


def generate_diagrams_view(project_id: str, open_browser: bool = False, theme: str | Path | None = None) -> dict[str, Any]:
    from .view import resolve_view_theme

    loaded, theme_arg, theme_warning = resolve_view_theme(project_id, theme)
    if theme_warning:
        print(f"sentinel warning: {theme_warning}", file=sys.stderr)
    model = collect_diagrams_model(project_id)
    page, library = render_diagrams_view(model, loaded, theme_arg=theme_arg)
    # The leak scan reads the page the workspace produced; the library is third-party code pinned by sha256.
    assert_no_leaks(project_id, page, workspace_path(project_id), "/view diagrams")
    rendered = page.replace(LIB_PLACEHOLDER, library, 1) if library else page
    out_dir = workspace_path(project_id) / "08_context_packs" / "views"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / "diagrams.html"
    write_text(out, rendered, newline="\n")
    if open_browser:
        open_local_file(out)
    return {
        "path": str(out),
        "artifact": "diagrams",
        "cards": model["summary"]["cards"],
        "drawn": model["summary"]["drawn"],
        "pending": model["summary"]["pending"],
        "no_notation": model["summary"]["no_notation"],
        "rendered": bool(library),
        "cutoff": model["provenance"]["cutoff"],
        "source_sha256": model["provenance"]["source_sha256"],
        "theme": loaded["name"],
        **({"theme_warning": theme_warning} if theme_warning else {}),
    }
