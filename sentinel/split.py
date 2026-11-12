"""IMP-263 (H17a): /split --assess, the release-split assessment of a brief v2.

The release split model (IMP-264) lists 7 signals to split and 5 not to, and says
there is no numeric threshold: only signals. This module gives each signal a
deterministic detector over the compiled brief v2 and its compile report:

* ``lit``: the signal holds, with the brief lines that anchor it;
* ``off``: the places it reads are settled and the signal does not hold;
* ``undetermined``: the places it reads are still pending, so it cannot tell;
* ``on_proposal``: it judges a proposed release (an empty release, a tab of
  another screen, a phase), so the partition validation checks it on the
  proposal (IMP-266), never on the whole brief.

The recommendation follows explicit rules, never a score:

* a split signal lit and no no-split signal lit → ``split``;
* split and no-split signals lit at once → ``cannot_decide``: the BA weighs them;
* nothing lit, and the build list exists → ``no_split``: the brief fits one
  session (step 0, question 2);
* nothing lit, but the build list is still pending → ``cannot_decide``.

The assessment writes `01_discovery/split_assessment.md` and its JSON, with the
brief's sha256. When a later command changes the brief (a spike or measurer closes,
a gap is answered), `refresh_if_stale` runs the assessment again [A45]. A v1 brief
cannot be split: a series does not mix v1 and v2 [A43].

Keyword cues read only cited lines (facts with a `[[…]]` citation), never the
template text, so a cue is always something a source said.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Callable

from .brief_model import BriefModel, parse_brief
from .core.io import read_json, write_text
from .core.paths import workspace_path
from .core.state import read_state
from .release_split_model import load_release_split_model

ASSESSMENT_JSON = "split_assessment.json"
ASSESSMENT_MD = "split_assessment.md"
# S1 detector parameter: more build items than this no longer fit one writing
# session. It lights one signal; it is not a threshold on the recommendation.
SESSION_BUILD_ITEMS = 12

_CITE = re.compile(r"\[\[[^\]]+\]\]")
_BUILD_ITEM = re.compile(r"`C-\d{2,}`")
_OPERATOR = re.compile(r"\b(back[- ]?office|operador\w*|operator\w*|aprobador\w*|approver\w*|supervisor\w*|"
                       r"backoffice|otra[s]? [aá]rea[s]?|another area|other areas|mesa de ayuda|help ?desk)\b", re.I)
_STAGE = re.compile(r"\b(segunda etapa|second stage|primera etapa|first stage|etapa \d|stage \d|fase \d|phase \d|"
                    r"piloto|pilot|m[aá]s adelante|later release|in a later|posteriormente|mientras se defin\w*|"
                    r"while .{0,30} (?:is|are) defined|once .{0,30} (?:is|are) defined)\b", re.I)
_THIRD = re.compile(r"\b(terceros?|third[- ]party|proveedor(?:es)? extern\w*|external provider|vendor)\b", re.I)
_BLOCK = re.compile(r"\b(no entreg\w*|not delivered|not yet delivered|pendiente de|pending from|bloque\w*|block\w*|"
                    r"sin contrato|no contract|a[uú]n no|not .{0,12}yet)\b", re.I)
_SHARED = re.compile(r"\b(compartid[oa]s?|shared|com[uú]n a|common to|transversal\w*|cross[- ]cutting)\b", re.I)
_SUGGESTED = re.compile(r"\b(sugerid[oa]s?|suggested|opcional\w*|optional|nice to have|deseable|desirable)\b", re.I)
_BLOCKING_SEVERITIES = {"critical", "high", "crítica", "critica", "alta"}
_SCOPE_PLACES = ("1.1", "1.3", "6.1")


def brief_hash(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


# --- reading the brief ----------------------------------------------------------


def _place_lines(model: BriefModel, place: str) -> list[tuple[int, str]]:
    """(1-based line, text) inside one place, sub-blocks included."""
    section = model.sections.get(place)
    if section is None:
        return []
    lines = model.text.splitlines()
    return [(index + 1, lines[index]) for index in range(section.start + 1, section.end)]


def _cited(model: BriefModel, *places: str) -> list[tuple[str, int, str]]:
    """Cited fact lines in the places: (place, line, text without the citation)."""
    found = []
    for place in places:
        for number, text in _place_lines(model, place):
            if _CITE.search(text):
                found.append((place, number, _CITE.sub("", text).strip(" -")))
    return found


def _section_places(model: BriefModel, section: str) -> list[str]:
    return [sid for sid in model.sections if sid.startswith(section + ".")]


def _anchor(place: str, line: int, quote: str) -> dict[str, Any]:
    return {"place": place, "line": line, "quote": quote[:160]}


def _matches(rows: list[tuple[str, int, str]], *patterns: re.Pattern) -> list[dict[str, Any]]:
    return [_anchor(p, n, t) for p, n, t in rows if all(pattern.search(t) for pattern in patterns)]


def _result(status: str, why: str, anchors: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {"status": status, "why": why, "anchors": anchors or []}


# --- detectors ------------------------------------------------------------------


class _Context:
    def __init__(self, model: BriefModel, report: dict[str, Any], settings: dict[str, Any], gaps: list[dict[str, Any]]):
        self.model, self.report, self.settings = model, report, settings
        self.gaps = {str(g.get("id", "")).strip("`"): g for g in gaps}
        self.build = [(n, t) for n, t in _place_lines(model, "9.1") if _BUILD_ITEM.search(t)]


def _s1_session_size(c: _Context) -> dict[str, Any]:
    if not c.build:
        return _result("undetermined", "the build list (9.1) is still pending")
    count = f"{len(c.build)} build item{'' if len(c.build) == 1 else 's'}"
    anchor = [_anchor("9.1", c.build[-1][0], count)]
    if len(c.build) > SESSION_BUILD_ITEMS:
        return _result("lit", f"{count} in 9.1, more than one writing session holds ({SESSION_BUILD_ITEMS})", anchor)
    return _result("off", f"{count} in 9.1 fit one session", anchor)


def _s2_actor_change(c: _Context) -> dict[str, Any]:
    actors = _cited(c.model, "2.1")
    if not actors:
        return _result("undetermined", "actors (2.1) are still pending")
    operators = _matches(_cited(c.model, "2.1", "3.2"), _OPERATOR)
    if len(actors) >= 2 and operators:
        return _result("lit", "an internal operator or another area takes part besides the first actor", operators)
    return _result("off", f"{len(actors)} actor line(s) in 2.1 and no change of operator")


def _s3_different_timing(c: _Context) -> dict[str, Any]:
    hits = _matches(_cited(c.model, "1.3", "1.4", "6.1", "6.2", "9.1"), _STAGE)
    if hits:
        return _result("lit", "the sources place parts of the scope at different moments", hits)
    return _result("off", "no source places parts of the scope at different moments")


def _s4_third_party_block(c: _Context) -> dict[str, Any]:
    hits = _matches(_cited(c.model, "2.4", "5.1", "5.6", "7.1"), _THIRD, _BLOCK)
    if hits:
        return _result("lit", "a third party has not delivered what one part needs", hits)
    return _result("off", "no source says a third party blocks a part")


def _s5_missing_oracle(c: _Context) -> dict[str, Any]:
    replacement = c.settings.get("genesis") == "brownfield-replacement" or "MIG" in (c.settings.get("profiles") or [])
    if not replacement:
        return _result("off", f"genesis {c.settings.get('genesis') or '?'}: no parity with a previous system to prove")
    oracle = _cited(c.model, "5.17")
    if oracle:
        return _result("off", "parity verification (5.17) is settled", [_anchor(*oracle[0])])
    return _result("lit", "a replacement with no executable parity verification (5.17) yet", [_anchor("5.17", 0, "pending")])


def _s6_shared_surface(c: _Context) -> dict[str, Any]:
    places = ["3.6", "6.1", *_section_places(c.model, "5")]
    hits = _matches(_cited(c.model, *places), _SHARED)
    if hits:
        return _result("lit", "the sources name a shared piece several parts would touch", hits)
    return _result("off", "no source names a shared piece")


def _s7_suggested_scope(c: _Context) -> dict[str, Any]:
    inferred = [row for row in c.report.get("inferred", []) if str(row.get("place", "")).split("/")[0] in ("6.1", "9.1")]
    if inferred:
        return _result("lit", "in-scope places hold scope inferred by the analysis, not asked for",
                       [_anchor(str(r["place"]), 0, f"{r.get('assumption', '')} {r.get('gap', '')}".strip()) for r in inferred])
    hits = _matches(_cited(c.model, "6.1", "4.2"), _SUGGESTED)
    if hits:
        return _result("lit", "the sources mark part of the scope as suggested or optional", hits)
    return _result("off", "no suggested or optional scope")


def _n1_nothing_demonstrable(c: _Context) -> dict[str, Any]:
    criteria = _cited(c.model, "1.5")
    if not criteria:
        return _result("undetermined", "release acceptance (1.5) is still pending")
    if len(criteria) < 2:
        return _result("lit", "a single acceptance line: no part would have something of its own to demonstrate",
                       [_anchor(*criteria[0])])
    return _result("off", f"{len(criteria)} acceptance lines in 1.5")


def _on_proposal(c: _Context) -> dict[str, Any]:
    return _result("on_proposal", "it judges a proposed release; the partition validation checks it on the proposal")


def _n4_undecided_dependency(c: _Context) -> dict[str, Any]:
    hits = []
    for site in c.report.get("fill_sites", []):
        place = str(site.get("id", "")).split("/")[0]
        gap = c.gaps.get(str(site.get("gap", "")))
        if place in _SCOPE_PLACES and site.get("class") == "client" and site.get("gap_open") and gap \
                and str(gap.get("severity", "")).lower() in _BLOCKING_SEVERITIES:
            hits.append(_anchor(place, 0, f"{site['gap']} ({gap.get('severity')})"))
    if hits:
        return _result("lit", "the scope depends on a client decision still open", hits)
    return _result("off", "no blocking client decision open on the scope")


DETECTORS: dict[str, Callable[[_Context], dict[str, Any]]] = {
    "S1": _s1_session_size, "S2": _s2_actor_change, "S3": _s3_different_timing, "S4": _s4_third_party_block,
    "S5": _s5_missing_oracle, "S6": _s6_shared_surface, "S7": _s7_suggested_scope,
    "N1": _n1_nothing_demonstrable, "N2": _on_proposal, "N3": _on_proposal, "N4": _n4_undecided_dependency,
    "N5": _on_proposal,
}


# --- assessment -----------------------------------------------------------------


def assess_brief(text: str, report: dict[str, Any], settings: dict[str, Any], gaps: list[dict[str, Any]]) -> dict[str, Any]:
    """The assessment of one brief v2. Pure: same inputs, same result."""
    model = parse_brief(text)
    if model.version != 2:
        raise ValueError("a v1 brief cannot be split: a series does not mix v1 and v2 [A43]; "
                         "recompile it with /brief PROJECT_ID --brief-version 2")
    split_model = load_release_split_model()
    context = _Context(model, report, settings, gaps)
    signals = []
    for kind in ("split", "no_split"):
        for item in split_model["signals"][kind]:
            signals.append({"id": item["id"], "key": item["key"], "kind": kind, "text": item["text"],
                            **DETECTORS[item["id"]](context)})
    lit_split = [s["id"] for s in signals if s["kind"] == "split" and s["status"] == "lit"]
    lit_no = [s["id"] for s in signals if s["kind"] == "no_split" and s["status"] == "lit"]
    s1 = next(s for s in signals if s["id"] == "S1")
    if lit_split and lit_no:
        value = "cannot_decide"
        why = [f"split signals lit: {', '.join(lit_split)}", f"no-split signals lit: {', '.join(lit_no)}",
               "the BA weighs them, or closes what lights the no-split signals, and assesses again"]
    elif lit_split:
        value, why = "split", [f"split signals lit: {', '.join(lit_split)}", "no no-split signal lit"]
    elif s1["status"] == "undetermined":
        value, why = "cannot_decide", ["no split signal lit, but the build list (9.1) is pending, so the size is unknown"]
    else:
        value, why = "no_split", ["no split signal lit", s1["why"]]
    goal = _cited(model, "1.3")
    step_0 = [
        {"id": "Q1", "answer": "yes" if _cited(model, "1.1") else "undetermined",
         "why": "identity and value (1.1) is settled" if _cited(model, "1.1") else "identity and value (1.1) is pending"},
        {"id": "Q2", "answer": "no" if s1["status"] == "lit" else ("yes" if s1["status"] == "off" else "undetermined"),
         "why": s1["why"]},
        {"id": "Q3", "answer": "yes" if goal else "no",
         "why": "a measurable goal (1.3) is settled" if goal else "no measurable goal (1.3) yet: define it before cutting by outcome"},
    ]
    for question, item in zip(step_0, split_model["flow"]["step_0"]["questions"]):
        question["text"] = item["text"]
    return {"model_version": split_model["version"], "signals": signals, "step_0": step_0,
            "recommendation": {"value": value, "why": why}}


_COPY = {
    "en": {"title": "Split assessment", "rec": "Recommendation", "why": "Why", "signals": "Signals",
           "header": "| Signal | Kind | Status | Anchor | Why |", "step0": "Step 0 — prepare",
           "step0_header": "| Question | Answer | Why |",
           "note": "No numeric threshold: each signal is reported with its anchor. `on_proposal` signals are checked on the proposed partition. The assessment runs again when the brief changes."},
    "es": {"title": "Evaluación de partición", "rec": "Recomendación", "why": "Por qué", "signals": "Señales",
           "header": "| Señal | Tipo | Estado | Ancla | Por qué |", "step0": "Paso 0 — preparar",
           "step0_header": "| Pregunta | Respuesta | Por qué |",
           "note": "Sin umbral numérico: cada señal se informa con su ancla. Las señales `on_proposal` se chequean sobre la partición propuesta. La evaluación se repite cuando cambia el brief."},
}


def render_assessment(project_id: str, data: dict[str, Any], language: str) -> str:
    copy = _COPY["es" if language == "es" else "en"]
    lines = [f"# {copy['title']} — {project_id}", "", f"**{copy['rec']}:** `{data['recommendation']['value']}`", "",
             f"{copy['why']}:", "", *[f"- {reason}" for reason in data["recommendation"]["why"]], "",
             f"## {copy['signals']}", "", copy["header"], "|---|---|---|---|---|"]
    for signal in data["signals"]:
        anchor = "; ".join(f"§{a['place']}" + (f" L{a['line']}" if a["line"] else "") + (f": {a['quote']}" if a["quote"] else "")
                           for a in signal["anchors"][:3]) or "—"
        cell = lambda value: str(value).replace("|", "\\|")
        lines.append(f"| {signal['id']} {signal['key']} | {signal['kind']} | {signal['status']} | {cell(anchor)} | {cell(signal['why'])} |")
    lines += ["", f"## {copy['step0']}", "", copy["step0_header"], "|---|---|---|"]
    lines += [f"| {q['id']} {q['text']} | {q['answer']} | {q['why']} |" for q in data["step_0"]]
    lines += ["", copy["note"], ""]
    return "\n".join(lines)


def _inputs(project_id: str) -> tuple[Path, str, dict[str, Any], dict[str, Any], list[dict[str, Any]], str]:
    from .discovery import parse_gap_rows

    base = workspace_path(project_id)
    brief_path = base / "02_requirements" / "project-brief.md"
    if not brief_path.is_file():
        raise ValueError(f"/split --assess needs a compiled brief v2: {brief_path.as_posix()} does not exist; run /maturity first")
    report_path = base / "02_requirements" / "brief_compile_report.json"
    report = read_json(report_path, {}) or {}
    state = read_state(project_id, {}) or {}
    settings = state.get("brief_settings") or {}
    gaps_path = base / "01_discovery" / "gaps.md"
    gaps = parse_gap_rows(gaps_path.read_text(encoding="utf-8")) if gaps_path.is_file() else []
    language = state.get("project_language") if state.get("project_language") in {"es", "en"} else "en"
    return brief_path, brief_path.read_text(encoding="utf-8"), report, settings, gaps, language


def run_assess(project_id: str) -> dict[str, Any]:
    """Assess the workspace brief, write the Markdown and JSON, return a summary."""
    brief_path, text, report, settings, gaps, language = _inputs(project_id)
    data = assess_brief(text, report, settings, gaps)
    data = {"project_id": project_id, "brief_sha256": brief_hash(brief_path), **data}
    discovery = workspace_path(project_id) / "01_discovery"
    write_text(discovery / ASSESSMENT_JSON, json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    write_text(discovery / ASSESSMENT_MD, render_assessment(project_id, data, language))
    return {
        "recommendation": data["recommendation"]["value"],
        "why": data["recommendation"]["why"],
        "lit": [s["id"] for s in data["signals"] if s["status"] == "lit"],
        "undetermined": [s["id"] for s in data["signals"] if s["status"] == "undetermined"],
        "path": (discovery / ASSESSMENT_MD).as_posix(),
        "json": (discovery / ASSESSMENT_JSON).as_posix(),
    }


def refresh_if_stale(project_id: str) -> dict[str, Any] | None:
    """Assess again when an earlier assessment exists and the brief changed since [A45]."""
    base = workspace_path(project_id)
    stored_path = base / "01_discovery" / ASSESSMENT_JSON
    brief_path = base / "02_requirements" / "project-brief.md"
    if not stored_path.is_file() or not brief_path.is_file():
        return None
    stored = read_json(stored_path, {}) or {}
    if stored.get("brief_sha256") == brief_hash(brief_path):
        return None
    try:
        return run_assess(project_id)
    except ValueError:
        return None
