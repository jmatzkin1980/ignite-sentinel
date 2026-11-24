"""IMP-410 (H27 inc 3): the earlier decisions a change's questions already have.

The side file `01_discovery/CHG-nnn/prior_decisions.json` maps a question id to the decision that already
answers it. It never rewrites `gaps.md` rows by itself: `render_gaps` reads it to prefill the section, and
the BA confirms (`/gaps --change --id --accept-prior`, or an answer file) or writes a new answer.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .core.io import read_json, write_json
from .gaps.model import PRE_DECIDED


def prior_path(base: Path, change_id: str) -> Path:
    return base / "01_discovery" / change_id / "prior_decisions.json"


def load_priors(base: Path, change_id: str) -> dict[str, dict]:
    data = read_json(prior_path(base, change_id), {})
    return {str(k): v for k, v in data.items() if isinstance(v, dict)} if isinstance(data, dict) else {}


def save_priors(base: Path, change_id: str, entries: dict[str, dict]) -> None:
    write_json(prior_path(base, change_id), entries)


def _flat(text: Any) -> str:
    return " ".join(str(text or "").split())


def prior_note(entry: dict, language: str) -> str:
    """The `resolution_note` of a PRE_DECIDED row."""
    prior, answer = entry.get("prior", ""), _flat(entry.get("answer"))[:120]
    if entry.get("changed") and entry.get("match") == "linked":
        return (f"ya decidido en {prior} (la decisión previa cambió): {answer}" if language == "es"
                else f"already decided in {prior} (the earlier decision changed): {answer}")
    if entry.get("match") == "suggested":
        return f"posible decisión previa en {prior}: {answer}" if language == "es" else f"possible earlier decision in {prior}: {answer}"
    if entry.get("match") == "design_request":
        return (f"ya registrado en el pedido como pedido a Diseño ({prior}): {answer}" if language == "es"
                else f"already registered in the request as a request to Design ({prior}): {answer}")
    return f"ya decidido en {prior}: {answer}" if language == "es" else f"already decided in {prior}: {answer}"


def prefill_lines(entry: dict, gap_id: str, project_id: str, change_id: str, language: str) -> list[str]:
    prior, answer = entry.get("prior", ""), _flat(entry.get("answer"))
    es = language == "es"
    match = entry.get("match")
    if match == "suggested":
        return [f"Posible decisión previa en {prior} (sugerida por memoria): {answer}" if es
                else f"Possible earlier decision in {prior} (suggested by memory): {answer}"]
    if match == "design_request":
        return [f"Ya registrado en el pedido como pedido a Diseño ({prior}): {answer}" if es
                else f"Already registered in the request as a request to Design ({prior}): {answer}"]
    command = f"/gaps {project_id} --change {change_id} --id {gap_id} --accept-prior"
    if es:
        return [f"Ya decidido en {prior}: {answer}" + (" (la decisión previa cambió)" if entry.get("changed") else ""),
                f"Si sigue valiendo, confirmalo con `{command}` o con «Estado de decisión: confirmado»; "
                "si cambió, escribí la respuesta nueva."]
    return [f"Already decided in {prior}: {answer}" + (" (the earlier decision changed)" if entry.get("changed") else ""),
            f"If it still holds, confirm it with `{command}` or with \"Decision status: confirmed\"; "
            "if it changed, write the new answer."]


def pre_decided_gaps(project_id: str, change_id: str) -> list[dict[str, str]]:
    """The questions of the change still waiting for the BA to confirm what was already decided."""
    from .changes import change_gaps_path
    from .gaps import parse_gap_rows
    from .workspace import workspace_path

    base = workspace_path(project_id)
    path = change_gaps_path(base, change_id)
    if not path.exists():
        return []
    priors = load_priors(base, change_id)
    return [{"id": row["id"], "prior": str(priors.get(row["id"], {}).get("prior", ""))}
            for row in parse_gap_rows(path.read_text(encoding="utf-8-sig"))
            if str(row.get("status", "")).strip("`").upper() == "PRE_DECIDED"]


# --- the lookup: before a question of the change is opened ----------------------------------------

PRIOR_MEMORY_MIN_SCORE = 0.75
PRIOR_CLOSURES = ("", "answered", "by_decision")  # a question closed any other way decided nothing for another one
_WEAK_PRIORS = ("GAP-SED-", "GAP-SRD-")  # "only in the design" / "no support" answers settle their own claim only
_LINKABLE = ("rule", "criterion", "story", "decision")
_PD = re.compile(r"\bPD-\d+(?:\.\d+)*\b")


@dataclass(frozen=True)
class PriorDecision:
    gap_id: str
    match: str  # linked | suggested
    basis: str  # quote | surface | element | memory
    answer: str
    option: str = ""
    score: float = 0.0


def candidate_from_claim(gap: dict, claim: dict) -> dict:
    cites = [{"side": str(c.get("side", "")), "source_id": str(c.get("source_id", "")),
              "quote": str(c.get("quote", "")), "line": c.get("line")} for c in claim.get("citations", [])]
    return {"id": str(gap["id"]), "citations": cites, "text": str(claim.get("text", "")), "sources": []}


def candidate_from_gap(gap: dict, sources: list[str]) -> dict:
    text = _flat(f"{gap.get('description', '')} {gap.get('question', '')}")
    return {"id": str(gap["id"]), "citations": [], "text": text, "sources": [str(s) for s in sources if s]}


def pick_memory_match(rows: list[dict], sources: set[str], min_score: float = PRIOR_MEMORY_MIN_SCORE) -> dict | None:
    """The best memory row that is a decision of the change, scores enough and shares a source with the candidate."""
    fit = [r for r in rows if r.get("artifact_type") == "change_decision" and float(r.get("score", 0) or 0) >= min_score
           and set(r.get("trace_ids") or []) & sources]
    return min(fit, key=lambda r: (-float(r["score"]), str(r.get("artifact_id", "")))) if fit else None


def _family(gap_id: str) -> str:
    return gap_id.rpartition("-")[0]


def _linkable(element_id: str) -> bool:
    from .extraction.inventory import match_element_id

    found = match_element_id(element_id)
    return bool(found) and found[1] in _LINKABLE


class _Index:
    """What the lookup reads about a change, once: its decisions, the elements of its request and its surfaces."""

    def __init__(self, project_id: str, change_id: str, decisions: bool = True) -> None:
        self.project_id, self.change_id = project_id, change_id
        self._decisions: list[dict] | None = None if decisions else []
        self._elements: list[dict] | None = None
        self._surfaces: list[tuple[str, dict, set[str]]] | None = None

    @property
    def decisions(self) -> list[dict]:
        if self._decisions is None:
            from .decision_memory import closed_decisions

            self._decisions = sorted(closed_decisions(self.project_id, self.change_id), key=lambda d: d["id"])
        return self._decisions

    @property
    def elements(self) -> list[dict]:
        if self._elements is None:
            from .decision_memory import _pedido_elements

            self._elements = _pedido_elements(self.project_id, self.change_id)
        return self._elements

    def elements_of(self, candidate: dict) -> tuple[list[str], bool]:
        """The linkable request elements a candidate touches, and whether every pedido citation of it sits in one."""
        from .extraction.inventory import element_lines, match_element_id

        found: list[str] = []
        complete = True
        for cite in candidate.get("citations", []):
            if cite.get("side") != "pedido":
                continue
            here: list[str] = []
            if cite.get("line"):
                for element in self.elements:
                    first, last = element_lines(element)
                    if element["source_id"] == cite.get("source_id") and first <= int(cite["line"]) <= last:
                        here.append(str(element["id"]))
            linkable = [e for e in here if _linkable(e)]
            complete = complete and bool(linkable)
            found.extend(linkable)
        named = match_element_id(str(candidate.get("text", "")))
        if named:
            found.append(named[0])
        return [e for e in dict.fromkeys(found) if _linkable(e)], complete

    @property
    def surfaces(self) -> list[tuple[str, dict, set[str]]]:
        """The decided surfaces and the (flattened, lower-case) design quotes each one came from."""
        if self._surfaces is None:
            from .changes import get_change
            from .crosses.record import load_cross
            from .crosses.surfaces import new_surface_candidates
            from .workspace import workspace_path

            change = get_change(self.project_id, self.change_id)
            decided = {k: v for k, v in (change.get("new_surfaces") or {}).items()
                       if isinstance(v, dict) and v.get("decision") in ("accepted", "declined")}
            found: list[tuple[str, dict, set[str]]] = []
            if decided:
                record = load_cross(workspace_path(self.project_id), self.change_id, "diseno") or {}
                texts = {c["id"]: c["text"] for c in new_surface_candidates(self.project_id, self.change_id)}
                for key in sorted(decided):
                    quotes = {_flat(c.get("quote")).lower() for claim in record.get("claims", []) if claim.get("gap") == key
                              for c in claim.get("citations", []) if c.get("side") == "diseno"}
                    if key in texts:
                        quotes.add(_flat(texts[key]).lower())
                    found.append((key, decided[key], {q for q in quotes if q}))
            self._surfaces = found
        return self._surfaces


COVER_RATIO = 0.8


def _overlap(a: Any, b: Any) -> float:
    """How much of the longer text the shorter one is, when it sits inside it (0 when it does not)."""
    a, b = _flat(a).lower(), _flat(b).lower()
    if not a or not b:
        return 0.0
    short, long = sorted((a, b), key=len)
    return len(short) / len(long) if short in long else 0.0


def _cite_matched(mine: dict, theirs: dict) -> bool:
    """The two quotes are the same text (one covers at least COVER_RATIO of the other), whatever line they sit on."""
    return _overlap(mine.get("quote"), theirs.get("quote")) >= COVER_RATIO


def _quote_link(candidate: dict, decision: dict) -> bool:
    """The prior decided on a statement the candidate is about: one of its pedido citations (any, if none is pedido) is the same quote."""
    citations = candidate.get("citations", [])
    mine = [c for c in citations if c.get("side") == "pedido"] or citations
    return any(_cite_matched(c, t) for c in mine for t in decision.get("citations", []))


def _surface_answer(decision: dict, language: str) -> str:
    es = language == "es"
    name = _flat(decision.get("name"))
    if decision.get("decision") == "accepted":
        kind = _flat(decision.get("type"))
        return f"Aceptada como superficie nueva: {kind} «{name}»" if es else f"Accepted as a new surface: {kind} “{name}”"
    reason = _flat(decision.get("reason"))
    return ("Descartada como superficie nueva" if es else "Declined as a new surface") + (f": {reason}" if reason else "")


def find_prior_decision(project_id: str, change_id: str, candidate: dict, _index: _Index | None = None) -> PriorDecision | None:
    """The earlier decision that already answers a question about to be opened: a direct link first, then memory."""
    index = _index or _Index(project_id, change_id)
    gap_id = str(candidate.get("id", ""))
    decisions = [d for d in index.decisions if d["id"] != gap_id and d.get("closure", "") in PRIOR_CLOSURES
                 and (_family(d["id"]) == _family(gap_id) or not d["id"].startswith(_WEAK_PRIORS))]

    def carried(decision: dict) -> str:
        return decision["option"] if _family(decision["id"]) == _family(gap_id) else ""

    for decision in decisions:  # (a) the same quote
        if _quote_link(candidate, decision):
            return PriorDecision(decision["id"], "linked", "quote", decision["answer"], carried(decision))
    mine = {_flat(c.get("quote")).lower() for c in candidate.get("citations", []) if c.get("side") == "diseno" and c.get("quote")}
    if mine and gap_id.startswith("GAP-SED-"):  # (b) a surface already decided
        for key, decision, quotes in index.surfaces:
            if mine & quotes:
                from .changes import change_language, get_change

                language = change_language(project_id, get_change(project_id, change_id))
                return PriorDecision(key, "linked", "surface", _surface_answer(decision, language))
    named, complete = index.elements_of(candidate)
    wanted = set(named)
    if wanted and complete:  # (c) every element the candidate touches is one the prior decided on
        for decision in decisions:
            if wanted <= {e for e in decision["elements"] if _linkable(e)}:
                return PriorDecision(decision["id"], "linked", "element", decision["answer"], carried(decision))
    sources = set(candidate.get("sources") or []) or {str(c["source_id"]) for c in candidate.get("citations", []) if c.get("source_id")}
    query = " ".join(_flat(c.get("quote")) for c in candidate.get("citations", []) if c.get("quote")) or _flat(candidate.get("text"))
    if not decisions or not sources or not query:
        return None
    from .memory import ContextBroker

    rows = ContextBroker(project_id).retrieve(query, "decision", limit=5, artifact_type="change_decision",
                                              trace_id=change_id, recency_weight=0.0)
    row = pick_memory_match(rows, sources)
    if row is None:
        return None
    found = str(row["artifact_id"]).removeprefix(f"DECISION-{change_id}-")
    decision = next((d for d in decisions if d["id"] == found), None)
    if decision is None:
        return None
    return PriorDecision(found, "suggested", "memory", decision["answer"], carried(decision), float(row["score"]))


def design_request_ref(project_id: str, change_id: str, claim: dict) -> dict | None:
    """The `PD-nn` of the request that already asks Design for what a divergence claim reports, with its text."""
    if claim.get("tag") != "divergencia":
        return None
    from .extraction.inventory import _LIST_MARKER, element_lines

    pd_elements = [e for e in _Index(project_id, change_id, decisions=False).elements if _PD.fullmatch(str(e["id"]))]

    def result(element: dict) -> dict:
        return {"ref": str(element["id"]), "text": _LIST_MARKER.sub("", _flat(element.get("excerpt")), count=1)[:160]}

    for cite in claim.get("citations", []):
        if cite.get("side") != "pedido" or not cite.get("line"):
            continue
        for element in pd_elements:
            first, last = element_lines(element)
            if element["source_id"] == cite.get("source_id") and first <= int(cite["line"]) <= last:
                return result(element)
    named = _PD.search(str(claim.get("text", "")))
    if not named:
        return None
    element = next((e for e in pd_elements if e["id"] == named.group(0)), None)
    return result(element) if element else None


def apply_prior_decisions(project_id: str, change_id: str, gaps: list[dict], candidates: dict[str, dict],
                          refs: dict[str, dict] | None = None) -> dict[str, dict]:
    """Settle the new questions of a change against what was already decided; writes the side file."""
    from .changes import change_language, get_change
    from .workspace import workspace_path

    if not gaps:
        return {}
    base = workspace_path(project_id)
    language = change_language(project_id, get_change(project_id, change_id))
    es = language == "es"
    priors = load_priors(base, change_id)
    index = _Index(project_id, change_id)
    new: dict[str, dict] = {}
    for gap in gaps:
        gap_id = str(gap["id"])
        if gap_id in priors or gap_id in new:
            continue  # an entry that exists is never overwritten
        candidate = candidates.get(gap_id)
        found = find_prior_decision(project_id, change_id, candidate, _index=index) if candidate else None
        ref = (refs or {}).get(gap_id)
        if found is not None:
            entry = {"prior": found.gap_id, "match": found.match, "basis": found.basis, "answer": found.answer,
                     "option": found.option, **({"score": found.score} if found.match == "suggested" else {})}
        elif ref:
            quoted = f"{ref['ref']}: «{ref['text']}»" if es else f"{ref['ref']}: “{ref['text']}”"
            entry = {"prior": ref["ref"], "match": "design_request", "basis": "pd", "option": "B",
                     "answer": f"Rige el pedido; Diseño ajusta según {quoted}" if es
                     else f"The request governs; Design adjusts per {quoted}"}
        else:
            continue
        if entry["match"] == "linked":
            gap["resolution_note"] = prior_note(entry, language)
            if str(gap.get("severity", "")).strip("`").lower() != "critical":
                gap["status"] = PRE_DECIDED  # a critical question keeps blocking: the prior is only prefilled
        new[gap_id] = entry
    if new:
        save_priors(base, change_id, {**priors, **new})
    return new
