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
    V2_GAP_COMPLEMENTS,
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

# IMP-253b: where an open contradiction's interim value lives, by its scope
# (`source_routing.json` conflicts scopes).
SCOPE_PLACE = {"business": "2.2", "rule": "2.2", "scope": "6.1", "stack_to_be": "5.2", "behavior": "3.2",
               "api": "5.7", "compliance": "5.11", "legacy": "5.13", "design": "4.1"}
# Transcription rules: a source TBD stays TBD (and the place stays pending); a
# doubled word is reproduced as is and marked [sic]. Quotes are never edited,
# so contracted enumerations and capped values ("up to 30") keep their form.
_TBD_RE = re.compile(r"(?<![\w-])(TBD|TBC|TBA|a definir|por definir|to be defined)(?![\w-])", re.I)
_DOUBLED_RE = re.compile(r"\b([^\W\d_]{3,})\s+(\1)\b", re.I)
_DOUBLED_OK = {"that", "had", "very"}


def transcribe(text: str) -> str:
    return _DOUBLED_RE.sub(
        lambda m: m.group(0) if m.group(1).lower() in _DOUBLED_OK else f"{m.group(0)} [sic]", text)


def source_says_tbd(text: str) -> bool:
    return _TBD_RE.search(text) is not None

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
        "cascade_no_propagation": "no other document",
        "provenance_header": "| Source | Facts cited |",
        "na_generic": "N/A — it does not apply to the {profiles} profile. If the profile or the genesis changes, it opens.",
        "na_see": "N/A — see {first}.",
        "states": "states",
        "harvest_repos": "Harvested repositories",
        "harvest_coverage": "Harvest coverage",
        "harvest_tags": {"fact": "facts", "inferred": "inferred", "not_found": "not found", "out_of_code": "out of code",
                         "divergence": "divergences"},
        "not_given": "(not given)",
        "glossary_header": "| Term | Definition | Canonical name | Do not confuse with | Source |",
        "cc_header": "| Scenario | Lens | Where it is specified | Status |",
        "cc_specified": "specified",
        "cc_pending": "pending there",
        "cc_na": "N/A there",
        "divergence_count": "{n} divergences between what is documented and what is built (⚠).",
        "debt": "Debt",
        "defect": "Defect",
        "replaced_title": "Replaced by a confirmed answer:",
        "replaced_header": "| Place | Previous statement | Source | Replaced by |",
        "inferred_title": "Inferences (each with its ledger row):",
        "inferred_header": "| Place | Assumption | Gap it waits on |",
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
        "cascade_no_propagation": "ningún otro documento",
        "provenance_header": "| Fuente | Hechos citados |",
        "na_generic": "N/A — no aplica al perfil {profiles}. Si cambia el perfil o la génesis, se abre.",
        "na_see": "N/A — ver {first}.",
        "states": "estados",
        "harvest_repos": "Repositorios cosechados",
        "harvest_coverage": "Cobertura del harvest",
        "harvest_tags": {"fact": "hechos", "inferred": "inferidos", "not_found": "no encontrados", "out_of_code": "fuera del código",
                         "divergence": "divergencias"},
        "not_given": "(no indicado)",
        "glossary_header": "| Término | Definición | Nombre canónico | No confundir con | Fuente |",
        "cc_header": "| Escenario | Lente | Dónde se especifica | Estado |",
        "cc_specified": "especificado",
        "cc_pending": "pendiente allí",
        "cc_na": "N/A allí",
        "divergence_count": "{n} divergencias entre lo documentado y lo construido (⚠).",
        "debt": "Deuda",
        "defect": "Defecto",
        "replaced_title": "Reemplazado por una respuesta confirmada:",
        "replaced_header": "| Lugar | Afirmación anterior | Fuente | Reemplazada por |",
        "inferred_title": "Inferencias (cada una con su fila en el ledger):",
        "inferred_header": "| Lugar | Supuesto | Gap que espera |",
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
    assumptions: list[dict[str, str]] = field(default_factory=list)  # id, statement, status, closes_gap
    contradictions: list[dict[str, Any]] = field(default_factory=list)  # gap, scope, value, source, resolved
    harvest: dict[str, Any] = field(default_factory=dict)  # IMP-262: 01_discovery/harvest.json
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
        # IMP-296: every scope sentence of the source, not only the first (9.1 grows one item per 6.1 item)
        out_scope = [s for s in sentences if any(c in s.lower() for c in _OUT_SCOPE_CUES)]
        in_scope = [s for s in sentences if s not in out_scope and any(c in s.lower() for c in _IN_SCOPE_CUES)]
        for sentence in in_scope:
            add("6.1", sentence, source_id)
        for sentence in out_scope:
            add("6.2", sentence, source_id)
    return facts


_PLACE_PREFIX_RE = re.compile(r"(?:^|(?<=\s))(\d+\.\d+|A\.[a-z_]+):\s+")


def umbrella_places(gap_id: str, statement: str) -> dict[str, str]:
    """IMP-26u: an answer to an umbrella gap `GAP-BRIEF-S<n>` fills its places one by one
    (`1.2: … 1.4: …`); a place outside the umbrella's section, or text with no place, is ignored."""
    if not gap_id.startswith(UMBRELLA_PREFIX):
        return {}
    section = gap_id[len(UMBRELLA_PREFIX):]
    parts = _PLACE_PREFIX_RE.split(" ".join(statement.split()))
    places: dict[str, str] = {}
    for place, text in zip(parts[1::2], parts[2::2]):
        text = text.strip().rstrip(";|").strip()
        if _section_of(place) == section and text:
            places[place] = text
    return places


def answer_facts(gap_answers: list[dict[str, str]], extra_routes: dict[str, str] | None = None,
                 routes: dict[str, str] | None = None) -> dict[str, list[_Fact]]:
    facts: dict[str, list[_Fact]] = {}

    def add(sid: str, text: str, answer: dict[str, str]) -> None:
        if text and all(f.text != text for f in facts.get(sid, [])):
            facts.setdefault(sid, []).append(_Fact(text, answer.get("source", ""), answer["gap"]))

    for answer in gap_answers:
        if routes is not None:  # IMP-26u: complements only
            if answer["gap"] in routes:
                add(routes[answer["gap"]], " ".join(answer["statement"].split()), answer)
            continue
        sid = V2_GAP_ROUTES.get(answer["gap"]) or (extra_routes or {}).get(answer["gap"])
        if sid:
            add(sid, " ".join(answer["statement"].split()), answer)
            continue
        for place, text in umbrella_places(answer["gap"], answer["statement"]).items():
            add(place, text, answer)
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
        self.contradiction_places = {c["gap"]: SCOPE_PLACE.get(c.get("scope", ""), "") for c in inputs.contradictions}
        raw = raw_facts(inputs.raw_sources)
        answers = answer_facts(inputs.gap_answers, {g: p for g, p in self.contradiction_places.items() if p})
        # IMP-253b, in-place rewrite (inverts IMP-145): a confirmed answer replaces
        # what the raw input said about the same place; the replaced quote moves to
        # provenance. The answer keeps its gap id, so the self-correction gate holds.
        self.replaced: list[dict[str, str]] = []
        facts: dict[str, list[_Fact]] = {}
        for sid in sorted(set(raw) | set(answers), key=_sort_key):
            if sid in answers:
                facts[sid] = answers[sid]
                for fact in raw.get(sid, []):
                    self.replaced.append({"place": sid, "statement": fact.text, "source": fact.source,
                                          "by": answers[sid][0].gap})
            else:
                facts[sid] = raw[sid]
        # IMP-26u: a counterpart answer completes its place, after what the source says
        for sid, extra in answer_facts(inputs.gap_answers, routes=V2_GAP_COMPLEMENTS).items():
            for fact in extra:
                if all(f.text != fact.text for f in facts.get(sid, [])):
                    facts.setdefault(sid, []).append(fact)
        # IMP-262: code facts of a brownfield harvest feed §5 by block, citing the harvest row
        from ..harvest import BLOCK_PLACES

        harvest_source = str(inputs.harvest.get("source_id") or "")
        self.harvest_inferred: dict[str, list[dict[str, str]]] = {}
        for entry in inputs.harvest.get("entries", []) if harvest_source else []:
            target = BLOCK_PLACES.get(entry.get("block", ""))
            if not target:
                continue
            if entry.get("kind") == "fact":
                text = f"{entry['text']} ({entry['ref']})"
                if all(f.text != text for f in facts.get(target, [])):
                    facts.setdefault(target, []).append(_Fact(text, harvest_source))
            elif entry.get("kind") == "inferred":
                self.harvest_inferred.setdefault(target, []).append(entry)
        self.facts = facts
        self.built = inputs.validation_direction == "built"
        self.inferred: dict[str, list[dict[str, str]]] = {}
        for assumption in inputs.assumptions:
            status = str(assumption.get("status", "")).strip().upper()
            target = V2_GAP_ROUTES.get(str(assumption.get("closes_gap", "")).strip("` ").upper())
            if target and status in {"ASSUMED", "INFERRED", "ASSUMPTION"}:
                self.inferred.setdefault(target, []).append(assumption)
        self.inferred_rows: list[dict[str, str]] = []
        self.umbrellas: dict[str, set[str]] = {}
        from ..glossary import build_glossary

        self.glossary = build_glossary(inputs.raw_sources, inputs.gap_answers)  # IMP-261
        self.interims: dict[str, list[dict[str, Any]]] = {}
        self.unplaced_contradictions: list[dict[str, Any]] = []
        for item in inputs.contradictions:
            target = self.contradiction_places.get(item["gap"])
            if target and target not in {a["gap"] for a in inputs.gap_answers}:
                self.interims.setdefault(target, []).append(item)
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

    def place_body(self, sid: str, title: str) -> tuple[list[str], bool, bool]:
        """(lines, has a settled fact, already carries a pending mark) for one place."""
        lines: list[str] = []
        settled = pending = False
        for fact in self.facts.get(sid, []):
            gap = f" (`{fact.gap}`)" if fact.gap else ""
            line = f"- {transcribe(fact.text)}{gap} {self.cite(fact, title)}"
            if source_says_tbd(fact.text):
                line += " " + self.pending(sid, sid, "client")
                pending = True
            else:
                settled = True
            lines.append(line)
        if settled:
            self.covered(sid, sid, sum(1 for f in self.facts.get(sid, []) if not source_says_tbd(f.text)))
        else:
            # the value to build with meanwhile exists only as an inference with its ledger row
            for assumption in self.inferred.get(sid, []):
                lines.append(f"- {self.markers['inferred'][self.lang]} {assumption['statement']} (`{assumption['id']}`)")
                self.inferred_rows.append({"place": sid, "assumption": assumption["id"], "statement": assumption["statement"],
                                           "gap": str(assumption.get("closes_gap", "")).strip("` ").upper()})
        for entry in self.harvest_inferred.get(sid, []):  # IMP-262: an inference read from the code
            lines.append(f"- {self.markers['inferred'][self.lang]} {entry['text']} (harvest {entry['block']})")
            self.inferred_rows.append({"place": sid, "assumption": "", "statement": entry["text"], "gap": ""})
        for item in self.interims.get(sid, []):
            fact = _Fact(str(item.get("value") or ""), str(item.get("source") or ""), item["gap"])
            if item.get("resolved") and fact.text:
                if self.built:
                    self.places.append({"id": sid, "fill": "divergence", "class": "divergence", "gap": item["gap"],
                                        "gap_open": item["gap"] in self.open_gaps, "section": _section_of(sid)})
                    lines.append(f"- {self.markers['built_divergence'][self.lang]} {fact.text} (`{item['gap']}`) {self.cite(fact, title)}")
                else:
                    lines.append(f"- {fact.text} {self.cite(fact, title)} {self.pending(sid, sid, 'client', item['gap'])}")
            else:
                lines.append(self.pending(sid, sid, "client", item["gap"]))
            pending = True
        return lines, settled, pending

    def open_gap_for(self, sid: str) -> str:
        """IMP-255: a mark points to an open gap: the routed one, the lens default, else the section umbrella."""
        candidates = sorted(g for g, target in V2_GAP_ROUTES.items() if target == sid) + [default_gap_for(sid)]
        for candidate in candidates:
            if candidate in self.open_gaps:
                return candidate
        umbrella = umbrella_gap_id(_section_of(sid))
        self.umbrellas.setdefault(umbrella, set()).add(sid)
        return umbrella

    def glossary_lines(self, title: str) -> list[str]:
        """IMP-261: term · definition · canonical name · do not confuse with · source."""
        given = self.copy["not_given"]
        rows = [self.copy["glossary_header"], "|---|---|---|---|---|"]
        for term in self.glossary:
            definition = f"{self.markers['inferred'][self.lang]} {term['definition']}" if term.get("inferred") else term["definition"]
            fact = _Fact(term["definition"], term.get("source", ""), "" if term.get("source") else "GAP-PRD-GLOSSARY-GOVERNANCE")
            canonical = f"`{term['canonical']}`" if term.get("canonical") else given
            rows.append(f"| {term['term']} | {definition} | {canonical} | {term.get('not_confuse') or given} | {self.cite(fact, title)} |")
            if term.get("inferred"):
                self.inferred_rows.append({"place": "A.glossary", "assumption": "", "statement": f"{term['term']}: {term['definition']}",
                                           "gap": "GAP-PRD-GLOSSARY-GOVERNANCE"})
        self.covered("A.glossary", "A.glossary", len(self.glossary))
        return rows

    def pending(self, place: str, sid: str, klass: str, gap: str | None = None) -> str:
        gap = gap if gap and gap in self.open_gaps else self.open_gap_for(sid)
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
        if sid == "A.glossary" and self.glossary:
            return out + self.glossary_lines(title) + [""]
        if mark == "n/a":
            out += [self.na(sid, sid), ""]
            return out
        lines, facts, marked = self.place_body(sid, title)
        if lines:
            out += lines + [""]
        blocks = item.get("blocks", [])
        if not blocks:
            if not facts and not marked:
                out += [self.pending(sid, sid, klass), ""]
            return out
        for block in blocks:
            place = f"{sid}/{block['key']}"
            out += [f"#### {block['title'][self.lang]}", ""]
            block_app = (app_entry or {}).get("blocks", {}).get(block["key"], {})
            block_mark = block_app.get("mark", mark)
            if block_mark == "n/a":
                out += [self.na(place, sid), ""]
            elif place == CROSS_CUTTING_PLACE:
                # IMP-256: an index of the 16 scenarios, filled once every place is known
                self.places.append({"id": place, "fill": "covered_by_reference", "section": sid.split(".")[0]})
                out += [CROSS_CUTTING_PLACEHOLDER, ""]
            elif not facts:
                block_class = "domain" if block_mark == "conditional" else klass
                mark = self.pending(place, sid, block_class)
                if place == SCREEN_STATES_PLACE:  # IMP-256: the 8 fixed states the place must cover
                    mark += " — " + self.copy["states"] + ": " + "; ".join(cross_cutting_data()["screen_states"][self.lang])
                    mark += " (" + "; ".join(cross_cutting_data()["distinctions"][self.lang]) + ")"
                out += [mark, ""]
            else:
                self.places.append({"id": place, "fill": "covered_by_parent", "section": sid.split(".")[0]})
                out += [f"→ {sid}", ""]
        return out


CROSS_CUTTING_PLACE = "3.6/cross_cutting"
SCREEN_STATES_PLACE = "4.1/screen_states"
CROSS_CUTTING_PLACEHOLDER = "<<cross-cutting scenarios>>"


def cross_cutting_data() -> dict[str, Any]:
    from ..resources import read_package_json

    return read_package_json("templates/cross_cutting.json")


def _fill_cross_cutting(w: "_Writer", body: dict[str, list[str]]) -> None:
    """3.6: one row per scenario with the state of the places that specify it (refers, never repeats)."""
    fills: dict[str, set[str]] = {}
    for place in w.places:
        fills.setdefault(place["id"], set()).add(place["fill"])
    rows = [w.copy["cc_header"], "|---|---|---|---|"]
    for scenario in cross_cutting_data()["scenarios"]:
        where = ", ".join(
            f"§{target.split('/')[0]} › {_block_title(w, *target.split('/'))}" if "/" in target else f"§{target}"
            for target in scenario["where"])
        states = [fills.get(target, set()) | fills.get(target.split("/")[0], set()) for target in scenario["where"]]
        if any(state & {"covered", "covered_by_parent"} for state in states):
            status = w.copy["cc_specified"]
        elif states and all(state == {"na"} for state in states):
            status = w.copy["cc_na"]
        else:
            status = w.copy["cc_pending"]
        rows.append(f"| {scenario['id']} {scenario[w.lang]} | {scenario['lens']} | {where} | {status} |")
    for lines in body.values():
        if CROSS_CUTTING_PLACEHOLDER in lines:
            index = lines.index(CROSS_CUTTING_PLACEHOLDER)
            lines[index:index + 1] = rows


def _harvest_status(harvest: dict[str, Any], copy: dict[str, Any]) -> list[str]:
    """IMP-262: §0.2 lists the harvested repositories and the coverage per tag."""
    if not harvest.get("repos"):
        return []
    cov = harvest.get("coverage", {})
    return [
        f"- {copy['harvest_repos']}: {', '.join(f'`{r}`' for r in harvest['repos'])}",
        f"- {copy['harvest_coverage']}: " + " · ".join(
            f"{copy['harvest_tags'][k]} {cov.get(k, 0)}" for k in ("fact", "inferred", "not_found", "out_of_code", "divergence")),
    ]


def _section_of(sid: str) -> str:
    return "A" if sid.startswith("A.") else sid.split(".")[0]


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
    items = list(w.facts.get("6.1", []))  # IMP-260: 9.1 ⊆ 6.1, every build item traces to an in-scope item
    if items:
        build = []
        kind = f"{copy['debt']}: " if w.built else ""  # with `built`, §9 carries only Debt and Defect
        for number, fact in enumerate(items, start=1):
            build.append(f"- `C-{number:02d}` {kind}{fact.text} {w.cite(fact, sections[9]['subsections'][0]['title'][lang])} — {copy['depends']}: {copy['none']}")
        w.covered("9.1/items", "9.1", len(build))
    else:
        build = [w.pending("9.1/items", "9.1", "client")]
    # IMP-26u: a confirmed delivery answer (slicing, readiness, enablers) is said under the items
    title_91 = sections[9]["subsections"][0]["title"][lang]
    build += [f"- {fact.text}{f' (`{fact.gap}`)' if fact.gap else ''} {w.cite(fact, title_91)}" for fact in w.facts.get("9.1", [])]
    if w.built:
        offset = len(items)
        for number, item in enumerate((c for c in inputs.contradictions if c.get("gap") in w.open_gaps), start=offset + 1):
            build.append(f"- `C-{number:02d}` {copy['defect']}: `{item['gap']}` — {copy['depends']}: {copy['none']}")
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
    divergences = [p for p in w.places if p["fill"] == "divergence"]
    if divergences:
        seeded += ["", copy["divergence_count"].format(n=len(divergences)), "", copy["seeded_header"], "|---|---|---|"]
        seeded += [f"| {p['id']} | ⚠ | `{p['gap']}` |" for p in divergences]
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
        *_harvest_status(inputs.harvest, copy),
        "", f"{copy['sources']}:", "", *sources, "",
        f"{copy['certainty']}:", "", *cert, "", reliability,
    ]
    _fill(body["0"], "0.2", [f"#### {_block_title(w, '0.2', 'status')}", "", *status, "",
                             f"#### {_block_title(w, '0.2', 'ready')}", "", ready])

    # annex provenance
    provenance = [copy["provenance_header"], "|---|---|"] + [f"| `{sid}` | {n} |" for sid, n in sorted(w.cited.items())]
    if w.replaced:
        provenance += ["", copy["replaced_title"], "", copy["replaced_header"], "|---|---|---|---|"]
        provenance += [f"| {r['place']} | {r['statement']} | `{r['source']}` | `{r['by']}` |" for r in w.replaced]
    if w.inferred_rows:
        provenance += ["", copy["inferred_title"], "", copy["inferred_header"], "|---|---|---|"]
        provenance += [f"| {r['place']} | `{r['assumption']}` | `{r['gap']}` |" for r in w.inferred_rows]
    _fill(annex_lines, "A.provenance", provenance, annex=True)

    # §6.3 cascade against the previous v2 brief
    marker = w.schema["artifact_marker"]
    head = [marker, f"# Project Brief — {inputs.project_id}", ""]
    _fill_cross_cutting(w, body)
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
            "inferred": len(w.inferred_rows),
            "divergences": sum(1 for p in w.places if p["fill"] == "divergence"),
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
        "replaced": w.replaced,
        "umbrella_gaps": {gap: sorted(places, key=_sort_key) for gap, places in sorted(w.umbrellas.items())},
        "inferred": w.inferred_rows,
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
        rows.append(f"| {sid} | `{delta_marker(status)}` | {(_PROPAGATION.get(lenses[0]) if lenses else None) or copy['cascade_no_propagation']} |")  # an em dash is a forbidden value (IMP-255)
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
    from ..harvest import load_harvest
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
    assumptions = [{"id": a["id"], "statement": a["statement"], "status": a.get("status", ""),
                    "closes_gap": a.get("closes_gap", "")}
                   for a in assumption_rows(read("assumptions.md"))]
    ledger = read_json(discovery / "statement_ledger.json", {}) or {}
    open_ids = {g["id"] for g in gaps if str(g.get("status", "")).upper() != "CLOSED"}
    contradictions = []
    for item in ledger.get("contradictions", []) if isinstance(ledger, dict) else []:
        if not isinstance(item, dict) or item.get("gap_id") not in open_ids:
            continue
        interim = item.get("interim") or {}
        contradictions.append({"gap": item["gap_id"], "scope": item.get("scope", ""), "value": interim.get("value"),
                               "source": interim.get("source_id"), "resolved": interim.get("status") == "resolved"})
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
        contradictions=contradictions,
        harvest=load_harvest(base),
        registry=registry,
        source_log_title=title,
        previous_text=brief_path.read_text(encoding="utf-8") if brief_path.exists() else "",
    )


def compile_brief_v2(project_id: str, settings: dict[str, Any], language: str) -> dict[str, Any]:
    from ..core.io import write_text
    from ..workspace import workspace_path

    inputs = collect_inputs(project_id, settings, language)
    text, report = render_brief_v2(inputs)
    if sync_umbrella_gaps(project_id, report["umbrella_gaps"], language):
        # the umbrella rows are now open gaps; render once more so §7.1 lists them (fixed point)
        previous = inputs.previous_text
        inputs = collect_inputs(project_id, settings, language)
        inputs.previous_text = previous
        text, report = render_brief_v2(inputs)
    base = workspace_path(project_id) / "02_requirements"
    write_text(base / "project-brief.md", text)
    write_text(base / "brief_compile_report.json", json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    record_brief_inferences(project_id, report["inferred"])
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
    from ..release_scope import active_release

    if active_release():
        # Inside a release scope the brief is the release brief, compiled by the series from the
        # whole brief (IMP-267a); recompiling it from the mirror's sources would replace it with the
        # whole project's brief. Never compile here.
        return None
    settings = brief_settings(project_id)
    if int(settings.get("brief_version", 1) or 1) != 2:
        return None
    status = settings_status(project_id)
    if not status["confirmed"]:
        _set_profile_gap(project_id, status["gap"], language)
        return None
    _set_profile_gap(project_id, None, language)
    return compile_brief_v2(project_id, settings, language)


# --- IMP-253b: the self-correction gate, rewrite on gap close, ledger rows ---------------


def v2_self_correction_findings(brief_text: str, gap_answers: dict[str, dict[str, str]]) -> list[str]:
    """IMP-145 inverted for v2: each confirmed answer sits in its own place with its gap id."""
    model = parse_brief(brief_text)
    lines = brief_text.splitlines()
    findings: list[str] = []
    for gap_id, payload in gap_answers.items():
        sid = V2_GAP_ROUTES.get(gap_id) or V2_GAP_COMPLEMENTS.get(gap_id)
        statement = " ".join(str(payload.get("statement", "")).split())
        if not sid or not statement:
            continue
        section = model.sections.get(sid)
        body = " ".join("\n".join(lines[section.start:section.end]).split()) if section else ""
        if gap_id not in body or statement not in body:
            findings.append(
                f"Self-correction: confirmed answer for `{gap_id}` is not in its place §{sid} of the brief v2 "
                f'(criterion: "{statement[:160]}").'
            )
    return findings


def rewrite_after_gap_close(project_id: str, closed: list[str]) -> dict[str, Any] | None:
    """Recompile a v2 brief after /resolve-gaps so the answers replace the marks in place."""
    from ..brief_model import load_brief_model
    from ..workspace import read_json as read_state_json, state_path, workspace_path

    if not closed:
        return None
    brief_path = workspace_path(project_id) / "02_requirements" / "project-brief.md"
    model = load_brief_model(brief_path)
    if model is None or model.version != 2:
        return None
    state = read_state_json(state_path(project_id), {})
    language = state.get("project_language") if state.get("project_language") in {"es", "en"} else "en"
    before = parse_brief(brief_path.read_text(encoding="utf-8"))
    result = compile_v2_if_opted_in(project_id, language)
    if result is None:
        return None
    after_text = brief_path.read_text(encoding="utf-8")
    after = parse_brief(after_text)
    old_lines, new_lines = before.text.splitlines(), after_text.splitlines()
    changed = sorted(
        (sid for sid in set(before.sections) | set(after.sections)
         if "." in sid and sid not in {"0.2", "6.3", "7.1", "7.2", "9.1", "A.provenance"}
         and (old_lines[before.sections[sid].start:before.sections[sid].end] if sid in before.sections else None)
         != (new_lines[after.sections[sid].start:after.sections[sid].end] if sid in after.sections else None)),
        key=_sort_key,
    )
    return {**result, "rewritten_places": changed}


BRIEF_PLACE_LINK = "brief_place"


def record_brief_inferences(project_id: str, inferred: list[dict[str, str]]) -> None:
    """Keep one INFERRED ledger unit per inference the brief v2 writes (replaces the previous set)."""
    from ..core.io import write_json
    from ..workspace import workspace_path

    path = workspace_path(project_id) / "01_discovery" / "knowledge_state.json"
    payload = read_json(path, {}) or {}
    if not isinstance(payload, dict) or "units" not in payload:
        return
    units = [u for u in payload.get("units", [])
             if not any(link.get("type") == BRIEF_PLACE_LINK for link in u.get("links", []) if isinstance(link, dict))]
    for number, row in enumerate(inferred, start=1):
        units.append({
            "id": f"KLU-BRIEF-{number:03d}",
            "lens": "product",
            "statement": row["statement"],
            "status": "INFERRED",
            "evidence": {"trace_id": "brief_compile_report", "quote": row["assumption"]},
            "links": [{"type": BRIEF_PLACE_LINK, "target": row["place"]},
                      *([{"type": "assumption", "target": row["assumption"]}] if row.get("assumption") else []),
                      *([{"type": "gap", "target": row["gap"]}] if row.get("gap") else [])],
        })
    from ..knowledge.ledger import summarize_units

    payload["units"] = units
    payload["summary"] = summarize_units(units)
    write_json(path, payload)


# --- IMP-255: umbrella gaps for pending places with no open gap of their own ---------------

UMBRELLA_PREFIX = "GAP-BRIEF-S"


def umbrella_gap_id(section: str) -> str:
    return f"{UMBRELLA_PREFIX}{section}"


def sync_umbrella_gaps(project_id: str, umbrellas: dict[str, list[str]], language: str) -> bool:
    """Open one non-blocking gap per section whose pending places have no open gap; close the rest."""
    from ..core.io import write_text
    from ..discovery import count_gaps, parse_gap_rows, readiness_stage_after_gap_change, render_gaps
    from ..workspace import update_state, workspace_path

    path = workspace_path(project_id) / "01_discovery" / "gaps.md"
    if not path.exists():
        return False
    rows = [row for row in parse_gap_rows(path.read_text(encoding="utf-8")) if row.get("id") != "NONE"]
    by_id = {row.get("id", "").strip("`"): row for row in rows}
    changed = False
    for gap_id, places in umbrellas.items():
        # IMP-26u: the answer fills the places one by one, so the question says how
        question = ("Completar en el brief v2, una línea por lugar (`1.2: …`): " if language == "es"
                    else "Fill in the brief v2, one line per place (`1.2: …`): ") + ", ".join(places)
        row = by_id.get(gap_id)
        if row is None:
            rows.append({"id": gap_id, "lens": "product", "severity": "medium", "status": "OPEN",
                         "description": f"Brief v2 places with no open gap of their own ({', '.join(places)}).",
                         "question": question, "evidence_mention": "", "origin": "checklist", "resolution_note": ""})
            changed = True
        elif str(row.get("status", "")).upper() == "CLOSED" or row.get("question") != question:
            row.update(status="OPEN", question=question, resolution_note="")
            changed = True
    for gap_id, row in by_id.items():
        if gap_id.startswith(UMBRELLA_PREFIX) and gap_id not in umbrellas and str(row.get("status", "")).upper() != "CLOSED":
            row.update(status="CLOSED", resolution_note="No brief v2 place points here any more.")
            changed = True
    if not changed:
        return False
    req_id = rows[0].get("parent", "REQ-001").strip("`") if rows else "REQ-001"
    write_text(path, render_gaps(project_id, rows, req_id, language))
    counts = count_gaps(rows)
    update_state(project_id, gap_counts=counts, readiness_stage=readiness_stage_after_gap_change(project_id, counts))
    return True
