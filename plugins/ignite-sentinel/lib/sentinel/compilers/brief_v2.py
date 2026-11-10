"""IMP-253a: the brief v2 compiler (en/es).

It writes §0–§9 and the annexes of `templates/brief_v2.json` for the profiles and
genesis the BA confirmed (IMP-252). The compiler is deterministic, so two runs over
the same inputs give the same bytes, and it never invents. Every place it writes
is one of:

- a **fact**: a sentence quoted from a source, with a `[[sources § … # F-NN]]`
  citation of the governed source row (a confirmed gap answer cites the row of the
  response that closed it and names the gap);
- a **pending mark**: `⏳ PENDING (GAP-X)` when the client owes the data, or
  `⏳ PENDING DOMAIN (GAP-X)` when domain context does (also every conditional
  place with no evidence);
- an **N/A** with its counterfactual: grouped lines from the schema, or the
  generic "does not apply to the profile" line.

§0.2 and §7 count the same marks, so they agree by construction. §6.3 lists what
changed against the previous v2 brief with the closed delta vocabulary
(`deltas.py`), and keeps its previous text when nothing changed so a re-run is
byte-identical. The compile report (`02_requirements/brief_compile_report.json`)
lists every place with its fill, the `fill_sites` still to fill, and the sources
the brief never cites.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..brief_model import (
    V2_GAP_ROUTES,
    default_gap_for,
    lenses_for_v2_id,
    parse_brief,
)
from ..brief_schema import applicability, load_brief_schema
from ..core.io import read_json
from ..core.markdown import parse_table_rows
from ..deltas import DeltaStatus, delta_marker

_OBJECTIVE_CUES = ("the goal", "goal is", "objetivo", "objective", "aim to", "purpose", "so that", "in order to")
_ASIS_CUES = ("today", "currently", "right now", "hoy", "actualmente", "proceso actual", "by hand", "a mano", "manual")
_OUT_SCOPE_CUES = ("out of scope", "out-of-scope", "fuera de alcance")
_IN_SCOPE_CUES = ("in scope", "scope:", "scope is", "alcance")

LOW_RELIABILITY_SHARE = 0.5

COPY = {
    "en": {
        "supports": "supports",
        "legend": [
            "Every statement is one of these. A fact carries a structured citation (document, section, id and what it supports) of the source that says it.",
            "`⏳` PENDING (gap): the client owes this data; it blocks.",
            "`⏳` PENDING DOMAIN (gap): domain context owes it; it can be deferred.",
            "`N/A — reason. If condition, it opens.`: it does not apply to this project, and says what would open it.",
            "`(inferred)`: an inference, marked in the same sentence.",
        ],
        "profile": "Profile",
        "genesis": "Genesis",
        "direction": "Validation direction",
        "sources": "Sources",
        "no_sources": "No governed source rows yet.",
        "certainty": "Certainty by section",
        "cert_header": "| Section | Facts | ⏳ client | ⏳ domain | N/A |",
        "reliability_low": "⚠ Low reliability: {pending} of {applicable} applicable places are still pending.",
        "reliability_ok": "Reliability: {covered} of {applicable} applicable places carry a cited fact.",
        "ready_no": "Ready to build: no. {n} pending marks block (§7).",
        "ready_yes": "Ready to build: yes. No pending mark blocks.",
        "open_header": "| Gap | Severity | Origin |",
        "open_count": "{n} open gaps in `gaps.md`.",
        "seeded_count": "{client} client marks (block) and {domain} domain marks (deferrable) in the body.",
        "seeded_header": "| Place | Class | Gap |",
        "no_assumptions": "No assumptions recorded.",
        "depends": "depends on",
        "none": "none",
        "no_items": "No build item has a cited source yet.",
        "cascade_first": "First v2 compilation: every section is `ADDED`. PRD, specs and backlog regenerate from this brief.",
        "cascade_none": "No section changed against the previous v2 brief.",
        "cascade_header": "| Place | Change | Propagate to |",
        "provenance_header": "| Source | Facts cited |",
        "na_generic": "N/A — it does not apply to the {profiles} profile. If the profile or the genesis changes, it opens.",
        "na_see": "N/A — see {first}.",
    },
    "es": {
        "supports": "sostiene",
        "legend": [
            "Cada afirmación es una de estas. Un hecho lleva una cita estructurada (documento, sección, id y qué sostiene) de la fuente que lo dice.",
            "`⏳` PENDIENTE (gap): el dato lo debe el cliente; bloquea.",
            "`⏳` PENDIENTE DOMINIO (gap): lo debe el contexto de dominio; puede diferirse.",
            "`N/A — motivo. Si condición, se abre.`: no aplica a este proyecto, y dice qué lo abriría.",
            "`(inferido)`: una inferencia, marcada en la misma frase.",
        ],
        "profile": "Perfil",
        "genesis": "Génesis",
        "direction": "Dirección de validación",
        "sources": "Fuentes",
        "no_sources": "Todavía no hay filas de fuentes gobernadas.",
        "certainty": "Certeza por sección",
        "cert_header": "| Sección | Hechos | ⏳ cliente | ⏳ dominio | N/A |",
        "reliability_low": "⚠ Confiabilidad baja: {pending} de {applicable} lugares aplicables siguen pendientes.",
        "reliability_ok": "Confiabilidad: {covered} de {applicable} lugares aplicables llevan un hecho citado.",
        "ready_no": "Listo para construir: no. Bloquean {n} marcas pendientes (§7).",
        "ready_yes": "Listo para construir: sí. Ninguna marca pendiente bloquea.",
        "open_header": "| Gap | Severidad | Origen |",
        "open_count": "{n} gaps abiertos en `gaps.md`.",
        "seeded_count": "{client} marcas de cliente (bloquean) y {domain} de dominio (diferibles) en el cuerpo.",
        "seeded_header": "| Lugar | Clase | Gap |",
        "no_assumptions": "Sin supuestos registrados.",
        "depends": "depende de",
        "none": "ninguna",
        "no_items": "Todavía ningún ítem de construcción tiene una fuente citada.",
        "cascade_first": "Primera compilación v2: todas las secciones son `ADDED`. PRD, specs y backlog se regeneran desde este brief.",
        "cascade_none": "Ninguna sección cambió respecto del brief v2 anterior.",
        "cascade_header": "| Lugar | Cambio | Propagar a |",
        "provenance_header": "| Fuente | Hechos citados |",
        "na_generic": "N/A — no aplica al perfil {profiles}. Si cambia el perfil o la génesis, se abre.",
        "na_see": "N/A — ver {first}.",
    },
}

# where a change in each lens propagates
_PROPAGATION = {"1": "prd", "2": "prd, specs", "3": "prd, specs, backlog", "4": "specs, backlog",
                "5": "specs, backlog", "6": "prd, backlog"}
_SPECIAL = {"0.1", "0.2", "6.3", "7.1", "7.2", "8.1", "9.1", "A.provenance"}


@dataclass
class BriefInputs:
    project_id: str
    language: str
    profiles: list[str]
    genesis: str
    validation_direction: str = "to-build"
    raw_sources: list[tuple[str, str, str]] = field(default_factory=list)  # (F-NN, relative path, text)
    gap_answers: list[dict[str, str]] = field(default_factory=list)  # gap, statement, source (F-NN or "")
    gaps: list[dict[str, str]] = field(default_factory=list)  # id, severity, status, origin
    assumptions: list[dict[str, str]] = field(default_factory=list)  # id, statement, status
    registry: list[dict[str, Any]] = field(default_factory=list)  # F-NN rows (id, paths, validity)
    source_log_title: str = ""
    previous_text: str = ""


@dataclass
class _Fact:
    text: str
    source: str
    gap: str = ""


# --- evidence ------------------------------------------------------------------


def _first_with(sentences: list[str], cues: tuple[str, ...]) -> str:
    return next((s for s in sentences if any(cue in s.lower() for cue in cues)), "")


def raw_facts(raw_sources: list[tuple[str, str, str]]) -> dict[str, list[_Fact]]:
    """Facts quoted from raw sources, by the v2 subsection that owns them."""
    from ..discovery import extract_functional_signals, extract_metric_signals, extract_personas, split_evidence_sentences

    facts: dict[str, list[_Fact]] = {}

    def add(sid: str, text: str, source: str) -> None:
        text = " ".join(text.split())
        if text and all(f.text != text for f in facts.get(sid, [])):
            facts.setdefault(sid, []).append(_Fact(text, source))

    for source_id, _path, text in raw_sources:
        sentences = split_evidence_sentences(text)
        add("1.1", _first_with(sentences, _OBJECTIVE_CUES), source_id)
        for metric in extract_metric_signals(text):
            add("1.3", metric["evidence"], source_id)
        for persona in extract_personas(text):
            add("2.1", persona["evidence"], source_id)
        add("3.1", _first_with(sentences, _ASIS_CUES), source_id)
        for signal in extract_functional_signals(text)[:3]:
            add("3.2", signal["statement"], source_id)
        out_scope = next((s for s in sentences if any(c in s.lower() for c in _OUT_SCOPE_CUES)), "")
        in_scope = next((s for s in sentences if s != out_scope and any(c in s.lower() for c in _IN_SCOPE_CUES)), "")
        add("6.1", in_scope, source_id)
        add("6.2", out_scope, source_id)
    return facts


def answer_facts(gap_answers: list[dict[str, str]]) -> dict[str, list[_Fact]]:
    facts: dict[str, list[_Fact]] = {}
    for answer in gap_answers:
        sid = V2_GAP_ROUTES.get(answer["gap"])
        if not sid:
            continue
        text = " ".join(answer["statement"].split())
        if text and all(f.text != text for f in facts.get(sid, [])):
            facts.setdefault(sid, []).append(_Fact(text, answer.get("source", ""), answer["gap"]))
    return facts


# --- rendering -------------------------------------------------------------------


class _Writer:
    def __init__(self, inputs: BriefInputs):
        self.inputs = inputs
        self.lang = "es" if inputs.language == "es" else "en"
        self.copy = COPY[self.lang]
        self.schema = load_brief_schema()
        self.markers = self.schema["markers"]
        self.app = applicability(inputs.profiles, inputs.genesis)
        facts = raw_facts(inputs.raw_sources)
        for sid, items in answer_facts(inputs.gap_answers).items():
            facts.setdefault(sid, []).extend(items)  # answers after raw quotes, IMP-145 keeps both
        self.facts = facts
        self.open_gaps = {g["id"] for g in inputs.gaps if str(g.get("status", "")).upper() != "CLOSED"}
        self.places: list[dict[str, Any]] = []  # one per rendered mark or fact block
        self.na_first: dict[str, str] = {}
        for line in self.app["na_lines"]:
            for member in line["members"]:
                self.na_first[member] = line["members"][0]
        self.na_lines = {line["members"][0]: line["line"][self.lang] for line in self.app["na_lines"]}
        self.cited: dict[str, int] = {}

    # marks
    def cite(self, fact: _Fact, title: str) -> str:
        supports = f"{title}" + (f" ({fact.gap})" if fact.gap else "")
        if fact.source:
            self.cited[fact.source] = self.cited.get(fact.source, 0) + 1
            section = self.inputs.source_log_title or "Source log"
            return f"[[sources § {section} # {fact.source} — {self.copy['supports']}: {supports}]]"
        return f"[[gaps § {fact.gap} # {fact.gap} — {self.copy['supports']}: {supports}]]"

    def fact_lines(self, sid: str, title: str) -> list[str]:
        lines = []
        for fact in self.facts.get(sid, []):
            gap = f" (`{fact.gap}`)" if fact.gap else ""
            lines.append(f"- {fact.text}{gap} {self.cite(fact, title)}")
        return lines

    def pending(self, place: str, sid: str, klass: str) -> str:
        gap = default_gap_for(sid)
        key = "pending_domain" if klass == "domain" else "pending"
        self.places.append({"id": place, "fill": key, "class": klass, "gap": gap, "gap_open": gap in self.open_gaps,
                            "section": sid.split(".")[0] if not sid.startswith("A.") else "A"})
        return self.markers[key][self.lang].format(gap=gap)

    def na(self, place: str, sid: str) -> str:
        self.places.append({"id": place, "fill": "na", "section": sid.split(".")[0] if not sid.startswith("A.") else "A"})
        first = self.na_first.get(place)
        if first and first != place:
            return self.copy["na_see"].format(first=first)
        if first:
            return self.na_lines[first]
        return self.copy["na_generic"].format(profiles="+".join(self.inputs.profiles))

    def covered(self, place: str, sid: str, count: int) -> None:
        self.places.append({"id": place, "fill": "covered", "facts": count,
                            "section": sid.split(".")[0] if not sid.startswith("A.") else "A"})

    # one numbered subsection (or annex) with its sub-blocks
    def entry(self, item: dict[str, Any], app_entry: dict[str, Any] | None) -> list[str]:
        sid = item["id"]
        title = item["title"][self.lang]
        heading = f"### {sid} {title}" if not sid.startswith("A.") else f"## {sid} {title}"
        out = [heading, ""]
        mark = (app_entry or {}).get("mark", "required")
        klass = "domain" if mark == "conditional" else item.get("contract", {}).get("missing", "client")
        if sid in _SPECIAL:
            return out  # filled by the section writers
        if mark == "n/a":
            out += [self.na(sid, sid), ""]
            return out
        facts = self.fact_lines(sid, title)
        if facts:
            self.covered(sid, sid, len(facts))
            out += facts + [""]
        blocks = item.get("blocks", [])
        if not blocks:
            if not facts:
                out += [self.pending(sid, sid, klass), ""]
            return out
        for block in blocks:
            place = f"{sid}/{block['key']}"
            out += [f"#### {block['title'][self.lang]}", ""]
            block_app = (app_entry or {}).get("blocks", {}).get(block["key"], {})
            block_mark = block_app.get("mark", mark)
            if block_mark == "n/a":
                out += [self.na(place, sid), ""]
            elif not facts:
                block_class = "domain" if block_mark == "conditional" else klass
                out += [self.pending(place, sid, block_class), ""]
            else:
                self.places.append({"id": place, "fill": "covered_by_parent", "section": sid.split(".")[0]})
                out += [f"→ {sid}", ""]
        return out


def _section_counts(places: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    counts: dict[str, dict[str, int]] = {}
    for place in places:
        row = counts.setdefault(place["section"], {"covered": 0, "pending": 0, "pending_domain": 0, "na": 0})
        fill = place["fill"]
        if fill in row:
            row[fill] += 1
    return counts


def render_brief_v2(inputs: BriefInputs) -> tuple[str, dict[str, Any]]:
    """The brief v2 text and its compile report. Pure: same inputs, same bytes."""
    w = _Writer(inputs)
    lang, copy = w.lang, w.copy
    body: dict[str, list[str]] = {}
    sections = w.schema["sections"]
    for section in sections:
        lines = [f"## {section['id']}. {section['title'][lang]}", ""]
        if section.get("opening"):
            opening = section["opening"]
            lines += [f"### {opening['id']} {opening['title'][lang]}", "", w.pending(opening["id"], opening["id"], opening["contract"].get("missing", "domain")), ""]
        for item in section["subsections"]:
            lines += w.entry(item, w.app["entries"].get(item["id"]))
        body[section["id"]] = lines
    annex_lines: list[str] = []
    for annex in w.schema["annexes"]:
        annex_lines += w.entry(annex, None)

    # §8 assumptions
    assumption_lines = [f"- `{a['id']}` — {a['statement']} ({a.get('status', '')})" for a in inputs.assumptions] or [copy["no_assumptions"]]
    _fill(body["8"], "8.1", assumption_lines)

    # §9 build list (acyclic: an item may depend only on an earlier one)
    items = [fact for sid in ("6.1", "3.2") for fact in w.facts.get(sid, [])]
    if items:
        build = []
        for number, fact in enumerate(items, start=1):
            build.append(f"- `C-{number:02d}` {fact.text} {w.cite(fact, sections[9]['subsections'][0]['title'][lang])} — {copy['depends']}: {copy['none']}")
        w.covered("9.1/items", "9.1", len(build))
    else:
        build = [w.pending("9.1/items", "9.1", "client")]
    non_software = w.pending("9.1/non_software", "9.1", "domain")

    # §0.1 legend
    _fill(body["0"], "0.1", [f"- {line}" for line in copy["legend"]])

    # every mark is written by now; §7.2, §7.1 and §0.2 count the same places
    risks = w.pending("7.1/risks", "7.1", "domain")
    pending_places = [p for p in w.places if p["fill"] in ("pending", "pending_domain")]
    client = sum(1 for p in pending_places if p["fill"] == "pending")
    domain = len(pending_places) - client
    seeded = [copy["seeded_count"].format(client=client, domain=domain), "", copy["seeded_header"], "|---|---|---|"]
    seeded += [f"| {p['id']} | {p['class']} | `{p['gap']}` |" for p in pending_places]
    _fill(body["7"], "7.2", seeded)
    open_rows = sorted((g for g in inputs.gaps if str(g.get("status", "")).upper() != "CLOSED"), key=lambda g: g["id"])
    open_items = [copy["open_count"].format(n=len(open_rows)), "", copy["open_header"], "|---|---|---|"]
    open_items += [f"| `{g['id']}` | {g.get('severity', '')} | {g.get('origin', '') or 'checklist'} |" for g in open_rows]
    _fill(body["7"], "7.1", [f"#### {_block_title(w, '7.1', 'open_items')}", "", *open_items, "",
                             f"#### {_block_title(w, '7.1', 'risks')}", "", risks])

    counts = _section_counts(w.places)
    covered_total = sum(1 for p in w.places if p["fill"] == "covered")
    applicable = covered_total + len(pending_places)
    reliability = (copy["reliability_low"].format(pending=len(pending_places), applicable=applicable)
                   if applicable and len(pending_places) / applicable > LOW_RELIABILITY_SHARE
                   else copy["reliability_ok"].format(covered=covered_total, applicable=applicable))
    ready = copy["ready_no"].format(n=client) if client else copy["ready_yes"]
    _fill(body["9"], "9.1", [f"#### {_block_title(w, '9.1', 'items')}", "", *build, "",
                             f"#### {_block_title(w, '9.1', 'non_software')}", "", non_software, "",
                             f"#### {_block_title(w, '9.1', 'conclusion')}", "", ready])
    sources = [f"- `{row['id']}` {', '.join(f'`{p}`' for p in row.get('paths', []))} ({row.get('validity', '')})"
               for row in inputs.registry] or [copy["no_sources"]]
    cert = [copy["cert_header"], "|---|---|---|---|---|"]
    for key in [s["id"] for s in sections] + ["A"]:
        row = counts.get(key, {"covered": 0, "pending": 0, "pending_domain": 0, "na": 0})
        cert.append(f"| {key} | {row['covered']} | {row['pending']} | {row['pending_domain']} | {row['na']} |")
    status = [
        f"- {copy['profile']}: {'+'.join(inputs.profiles)}",
        f"- {copy['genesis']}: {inputs.genesis}",
        f"- {copy['direction']}: {inputs.validation_direction}",
        "", f"{copy['sources']}:", "", *sources, "",
        f"{copy['certainty']}:", "", *cert, "", reliability,
    ]
    _fill(body["0"], "0.2", [f"#### {_block_title(w, '0.2', 'status')}", "", *status, "",
                             f"#### {_block_title(w, '0.2', 'ready')}", "", ready])

    # annex provenance
    provenance = [copy["provenance_header"], "|---|---|"] + [f"| `{sid}` | {n} |" for sid, n in sorted(w.cited.items())]
    _fill(annex_lines, "A.provenance", provenance, annex=True)

    # §6.3 cascade against the previous v2 brief
    marker = w.schema["artifact_marker"]
    head = [marker, f"# Project Brief — {inputs.project_id}", ""]
    draft = "\n".join(head + [line for sid in body for line in body[sid]] + annex_lines)
    cascade = _cascade(w, draft, inputs.previous_text)
    _fill(body["6"], "6.3", cascade)
    text = "\n".join(head + [line for sid in body for line in body[sid]] + annex_lines).rstrip() + "\n"

    report = {
        "brief_version": 2,
        "profiles": inputs.profiles,
        "genesis": inputs.genesis,
        "validation_direction": inputs.validation_direction,
        "summary": {
            "covered": covered_total,
            "inferred": 0,
            "pending_client": client,
            "pending_domain": domain,
            "na": sum(1 for p in w.places if p["fill"] == "na"),
            "applicable": applicable,
            "low_reliability": bool(applicable and len(pending_places) / applicable > LOW_RELIABILITY_SHARE),
        },
        "by_section": counts,
        "places": w.places,
        "fill_sites": [
            {"id": p["id"], "class": p["class"], "gap": p["gap"], "gap_open": p["gap_open"],
             "produces": _produces(w.schema, p["id"])}
            for p in pending_places
        ],
        "sources_cited": dict(sorted(w.cited.items())),
        "unused_sources": [row["id"] for row in inputs.registry
                           if row["id"] not in w.cited and row.get("validity", "current") == "current"],
    }
    return text, report


def _block_title(w: _Writer, sid: str, key: str) -> str:
    for section in w.schema["sections"]:
        for item in section["subsections"]:
            if item["id"] == sid:
                for block in item.get("blocks", []):
                    if block["key"] == key:
                        return block["title"][w.lang]
    return key


def _produces(schema: dict[str, Any], place: str) -> str:
    sid, _, key = place.partition("/")
    for section in schema["sections"]:
        candidates = list(section["subsections"]) + ([section["opening"]] if section.get("opening") else [])
        for item in candidates:
            if item["id"] == sid:
                for block in item.get("blocks", []):
                    if block["key"] == key and block.get("contract", {}).get("produces"):
                        return block["contract"]["produces"]
                return item.get("contract", {}).get("produces", "")
    for annex in schema["annexes"]:
        if annex["id"] == sid:
            return annex.get("contract", {}).get("produces", "")
    return ""


def _fill(lines: list[str], sid: str, content: list[str], annex: bool = False) -> None:
    prefix = f"## {sid} " if annex else f"### {sid} "
    index = next(i for i, line in enumerate(lines) if line.startswith(prefix))
    lines[index + 2:index + 2] = [*content, ""]


def _section_bodies(text: str) -> dict[str, str]:
    model = parse_brief(text)
    lines = text.splitlines()
    bodies = {}
    for sid, section in model.sections.items():
        if "." in sid and sid != "6.3":
            bodies[sid] = "\n".join(lines[section.start + 1:section.end]).strip()
    return bodies


def _cascade(w: _Writer, draft: str, previous: str) -> list[str]:
    copy = w.copy
    if not previous or parse_brief(previous).version != 2:
        return [copy["cascade_first"]]
    before, after = _section_bodies(previous), _section_bodies(draft)
    rows = []
    for sid in sorted(set(before) | set(after), key=_sort_key):
        if sid not in before:
            status = DeltaStatus.ADDED
        elif sid not in after:
            status = DeltaStatus.REMOVED
        elif before[sid] != after[sid]:
            status = DeltaStatus.MODIFIED
        else:
            continue
        lenses = lenses_for_v2_id(sid)
        rows.append(f"| {sid} | `{delta_marker(status)}` | {_PROPAGATION.get(lenses[0], '—') if lenses else '—'} |")
    if not rows:
        prev_model = parse_brief(previous)
        kept = prev_model.sections.get("6.3")
        if kept:
            lines = previous.splitlines()[kept.start + 1:kept.end]
            return [line for line in "\n".join(lines).strip().splitlines()]
        return [copy["cascade_none"]]
    return [copy["cascade_header"], "|---|---|---|", *rows]


def _sort_key(sid: str) -> tuple:
    return tuple(int(part) if part.isdigit() else 999 for part in re.split(r"[./]", sid))


# --- workspace I/O -----------------------------------------------------------------


def confirmed_answers(text: str, registry: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Every confirmed gap answer (not only the first per gap), with the F-NN row that delivered it."""
    by_event = {}
    for row in registry:
        for event in row.get("events") or []:
            if event.get("event_id"):
                by_event.setdefault(str(event["event_id"]), row["id"])
    answers = []
    for row in parse_table_rows(text, skip_separator_rows=True):
        if len(row) >= 5 and row[1].strip("`").startswith("GAP-") and row[2].upper() == "CONFIRMED":
            change = row[4].strip("` ")
            answers.append({"gap": row[1].strip("`"), "statement": row[3], "source": by_event.get(change, "")})
    return answers


def collect_inputs(project_id: str, settings: dict[str, Any], language: str) -> BriefInputs:
    from ..assumptions import assumption_rows
    from ..discovery import parse_gap_rows
    from ..workspace import workspace_path

    base = workspace_path(project_id)
    manifest_path = base / "00_raw" / "source_manifest.json"
    manifest = read_json(manifest_path, {}) or {}
    registry = [row for row in manifest.get("registry", []) if isinstance(row, dict) and row.get("id")]
    raw_sources = []
    raw_dir = base / "00_raw"
    for pattern in ("*.md", "*.txt"):
        for path in sorted(raw_dir.glob(pattern)) if raw_dir.exists() else []:
            source = next((row["id"] for row in registry if path.name in [Path(p).name for p in row.get("paths", [])]), "")
            raw_sources.append((source, path.name, path.read_text(encoding="utf-8")))
    discovery = base / "01_discovery"

    def read(name: str) -> str:
        path = discovery / name
        return path.read_text(encoding="utf-8") if path.exists() else ""

    gaps = [{"id": g.get("id", "").strip("`"), "severity": g.get("severity", ""), "status": g.get("status", ""),
             "origin": g.get("origin", "")} for g in parse_gap_rows(read("gaps.md")) if g.get("id") not in (None, "", "NONE")]
    assumptions = [{"id": a["id"], "statement": a["statement"], "status": a.get("status", "")}
                   for a in assumption_rows(read("assumptions.md"))]
    log_path = base / "07_changes" / "source_log.md"
    title = ""
    if log_path.exists():
        first = next((line for line in log_path.read_text(encoding="utf-8").splitlines() if line.startswith("# ")), "")
        title = first[2:].strip()
    brief_path = base / "02_requirements" / "project-brief.md"
    return BriefInputs(
        project_id=project_id,
        language=language,
        profiles=list(settings.get("profiles") or []),
        genesis=str(settings.get("genesis") or ""),
        validation_direction=str(settings.get("validation_direction") or "to-build"),
        raw_sources=[s for s in raw_sources if s[0]] or raw_sources,
        gap_answers=confirmed_answers(read("identity_seeds.md") + "\n" + read("decisions.md"), registry),
        gaps=gaps,
        assumptions=assumptions,
        registry=registry,
        source_log_title=title,
        previous_text=brief_path.read_text(encoding="utf-8") if brief_path.exists() else "",
    )


def compile_brief_v2(project_id: str, settings: dict[str, Any], language: str) -> dict[str, Any]:
    from ..core.io import write_text
    from ..workspace import workspace_path

    inputs = collect_inputs(project_id, settings, language)
    text, report = render_brief_v2(inputs)
    base = workspace_path(project_id) / "02_requirements"
    write_text(base / "project-brief.md", text)
    write_text(base / "brief_compile_report.json", json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    return {"path": str(base / "project-brief.md"), "report": str(base / "brief_compile_report.json"),
            "summary": report["summary"]}


# --- opt-in and the profile gap ------------------------------------------------------


def _profile_gap_row(gap: dict[str, Any]) -> dict[str, str]:
    return {
        "id": gap["id"],
        "lens": "product",
        "severity": gap.get("severity", "critical"),
        "status": "OPEN",
        "description": f"Brief v2 needs a confirmed profile and genesis ({gap.get('reason', '')}).",
        "question": gap.get("question", ""),
        "evidence_mention": "",
        "origin": "checklist",
        "resolution_note": "",
    }


def _set_profile_gap(project_id: str, gap: dict[str, Any] | None, language: str) -> None:
    """Open GAP-BRIEF-PROFILE (gap given) or close it (gap None) in gaps.md."""
    from ..brief_schema import SETTINGS_GAP_ID
    from ..core.io import write_text
    from ..discovery import count_gaps, parse_gap_rows, readiness_stage_after_gap_change, render_gaps
    from ..workspace import update_state, workspace_path

    path = workspace_path(project_id) / "01_discovery" / "gaps.md"
    if not path.exists():
        return
    rows = [row for row in parse_gap_rows(path.read_text(encoding="utf-8")) if row.get("id") != "NONE"]
    current = next((row for row in rows if row.get("id", "").strip("`") == SETTINGS_GAP_ID), None)
    if gap is not None:
        if current is not None and str(current.get("status", "")).upper() != "CLOSED":
            return
        if current is not None:
            current.update(status="OPEN", resolution_note="")
        else:
            rows.append(_profile_gap_row(gap))
    else:
        if current is None or str(current.get("status", "")).upper() == "CLOSED":
            return
        current.update(status="CLOSED", resolution_note="Confirmed with /brief --profile --genesis.")
    req_id = rows[0].get("parent", "REQ-001").strip("`") if rows else "REQ-001"
    write_text(path, render_gaps(project_id, rows, req_id, language))
    counts = count_gaps(rows)
    update_state(project_id, gap_counts=counts, readiness_stage=readiness_stage_after_gap_change(project_id, counts))


def compile_v2_if_opted_in(project_id: str, language: str) -> dict[str, Any] | None:
    """Compile the v2 brief when the project opted in and the settings are confirmed."""
    from ..brief_schema import brief_settings, settings_status

    settings = brief_settings(project_id)
    if int(settings.get("brief_version", 1) or 1) != 2:
        return None
    status = settings_status(project_id)
    if not status["confirmed"]:
        _set_profile_gap(project_id, status["gap"], language)
        return None
    _set_profile_gap(project_id, None, language)
    return compile_brief_v2(project_id, settings, language)
