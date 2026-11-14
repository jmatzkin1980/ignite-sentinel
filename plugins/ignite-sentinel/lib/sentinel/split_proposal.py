"""IMP-265 (H17a): /split --propose, the release-series proposal.

The agent walks the release split model (skill `sentinel-release-split`) and
writes one JSON proposal; the runtime validates its structure and its anchors to
the brief v2 and stores it in `02_requirements/series/proposal.json`. Nothing is
compiled and the brief is never touched: the series exists only after
`/split --confirm` (IMP-266).

    {"core": {"text": "...", "anchor": {"place": "1.1", "quote": "<verbatim>"}},
     "variations": [{"id": "V1", "text": "...", "anchor": {...}}],
     "criteria": [{"id": "C1", "why": "...", "anchor": {...}}],
     "base": {"pieces": [{"piece": "...", "reason": "...", "used_by": ["r2", "r3"]}],
              "not_in_base": [{"piece": "...", "goes_to": "r2", "reason": "..."}]},
     "releases": [{"id": "r1", "name": "...", "type": "functional", "wave": 0, "pattern": "P3",
                   "criteria": ["C1"], "goal": "...", "closing_check": "...",
                   "contains": [{"place": "6.1", "quote": "..."}, {"item": "C-01"}],
                   "needs": ["GAP-..."], "depends_on": [{"release": "r0", "why": "...", "strength": "hard"}],
                   "enables": [...], "condition": "GAP-...", "spike": {"questions": ["...?"], "time_box": "2w"},
                   "interleave_subtype": "late_external_dependency", "suggested_scope": false}],
     "sketches": [{"name": "...", "goal": "...", "pattern": "P5"}],
     "inheritance": [{"gap": "GAP-...", "release": "r1", "why": "..."}],
     "integrator_consumption": [{"piece": "...", "uses": "...", "from": "r2"}]}

The checks here are structure and anchors. The partition rules (the graph with
contracts as nodes, waves, n-of-n coverage, single owner, frozen contracts) are
IMP-266's, run before `/split --confirm`.
"""
from __future__ import annotations

from .errors import InputError  # IMP-302: typed errors

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from .brief_model import parse_brief
from .release_split_model import load_release_split_model

PROPOSAL_DIR = ("02_requirements", "series")
PROPOSAL_FILE = "proposal.json"
FINDING_CODES = (
    "payload_shape", "core_without_source", "variation_without_source", "criterion_without_source",
    "unknown_criterion", "criteria_without_value", "session_size_alone", "bad_release_id", "duplicate_release",
    "unknown_release_type", "unknown_pattern", "pattern_not_a_cut", "criterion_not_written", "missing_goal",
    "empty_release", "layer_cut", "contains_without_source", "unknown_release_reference", "bad_strength",
    "conditional_without_gap", "spike_contract", "interleave_contract", "base_piece_without_reason",
    "negative_list_missing", "sketch_incomplete", "misplaced_inheritance", "inheritance_unknown_gap",
    "integrator_without_consumption",
)
RELEASE_ID_RE = re.compile(r"^r(\d+)(?:\.(\d+))?$")
# an item unit: a build item C-NN of 9.1, or a screen P-N (IMP-249 family) the brief names
C_ITEM_RE = re.compile(r"^(?:C-\d{2,}|P-\d+)$")
GAP_RE = re.compile(r"^GAP-[A-Z0-9-]+$")
STRENGTHS = ("hard", "opportunistic")
# release types that may carry no unit of the brief (release_split_model: may_have_no_units)
_LAYER_NAME_RE = re.compile(
    r"\b(back[- ]?end|front[- ]?end|base de datos|database|data layer|capa de (datos|presentaci[oó]n|servicios|negocio)|"
    r"ui layer|api layer|persistence|persistencia|presentation layer|service layer)\b", re.I)


class SplitProposalError(InputError):
    pass


def _norm(text: Any) -> str:
    return " ".join(str(text).split()).lower()


def _place_text(model_text: str, lines: list[str], sections: dict, place: str) -> str | None:
    spans = [s for key, s in sections.items() if key == place or key.startswith(place + ".")]
    if not spans:
        return None
    return "\n".join(lines[min(s.start for s in spans):max(s.end for s in spans)])


def release_order(release_id: str) -> tuple[int, int]:
    match = RELEASE_ID_RE.match(release_id)
    return (int(match.group(1)), int(match.group(2) or 0)) if match else (10**6, 0)


class _Checker:
    def __init__(self, brief_text: str, open_gaps: set[str]):
        model = parse_brief(brief_text)
        if model.version != 2:
            raise SplitProposalError("a v1 brief cannot be split: a series does not mix v1 and v2 [A43]")
        self.lines = brief_text.splitlines()
        self.sections = model.sections
        self.text = brief_text
        self.items = {m.group(0).strip("`") for m in re.finditer(r"`C-\d{2,}`", brief_text)} \
            | set(re.findall(r"\bP-\d+\b", brief_text))
        self.open_gaps = open_gaps
        self.model = load_release_split_model()
        self.criteria = {c["id"] for c in self.model["cut_criteria"]["items"]}
        self.patterns = {p["id"]: p for p in self.model["patterns"]["items"]}
        self.types = {t["key"]: t for t in self.model["release_types"]["items"]}
        self.subtypes = {s["key"] for s in self.model["release_types"]["interleave_subtypes"]}
        self.findings: list[dict[str, str]] = []

    def add(self, code: str, where: str, reason: str) -> None:
        self.findings.append({"code": code, "where": where, "reason": reason})

    def anchored(self, anchor: Any) -> bool:
        if not isinstance(anchor, dict):
            return False
        body = _place_text(self.text, self.lines, self.sections, str(anchor.get("place", "")).strip())
        quote = str(anchor.get("quote", "")).strip()
        return bool(body is not None and quote and _norm(quote) in _norm(body))

    def contains_ok(self, unit: Any) -> bool:
        if isinstance(unit, dict) and unit.get("item"):
            return str(unit["item"]).strip() in self.items and bool(C_ITEM_RE.match(str(unit["item"]).strip()))
        return self.anchored(unit)


def _list(payload: dict[str, Any], key: str) -> list[Any]:
    value = payload.get(key, [])
    return value if isinstance(value, list) else []


def validate_proposal(brief_text: str, payload: dict[str, Any], open_gaps: set[str] | None = None) -> dict[str, Any]:
    """Findings (code, where, reason) for one proposal; no findings means valid. Pure."""
    c = _Checker(brief_text, set(open_gaps or ()))
    if not isinstance(payload, dict):
        c.add("payload_shape", "proposal", "the proposal must be a JSON object")
        return {"findings": c.findings, "valid": False}
    for key, kind in (("core", dict), ("criteria", list), ("releases", list)):
        if not isinstance(payload.get(key), kind) or not payload.get(key):
            c.add("payload_shape", key, f"`{key}` is required ({'an object' if kind is dict else 'a non-empty list'})")
    for key in ("variations", "sketches", "inheritance", "integrator_consumption"):
        if key in payload and not isinstance(payload[key], list):
            c.add("payload_shape", key, f"`{key}` must be a list")

    core = payload.get("core") if isinstance(payload.get("core"), dict) else {}
    if core and not c.anchored(core.get("anchor")):
        c.add("core_without_source", "core", "the core needs an anchor {place, quote} verbatim in the brief")
    for index, variation in enumerate(_list(payload, "variations"), start=1):
        if not isinstance(variation, dict) or not c.anchored(variation.get("anchor")):
            c.add("variation_without_source", f"variations[{index}]", "a variation needs an anchor verbatim in the brief")

    written: set[str] = set()
    for index, criterion in enumerate(_list(payload, "criteria"), start=1):
        cid = str(criterion.get("id", "")).strip() if isinstance(criterion, dict) else ""
        where = f"criteria[{index}] {cid}".strip()
        if cid not in c.criteria:
            c.add("unknown_criterion", where, "a cut criterion is one of C1..C14 of the model")
            continue
        written.add(cid)
        if not str(criterion.get("why", "")).strip() or not c.anchored(criterion.get("anchor")):
            c.add("criterion_without_source", where, "a criterion is written before cutting, with its why and an anchor verbatim in the brief")
    if written and "C1" not in written:
        c.add("criteria_without_value", "criteria", "verifiable value (C1) always leads the cut")
    if written == {"C14"}:
        c.add("session_size_alone", "criteria", "session size (C14) is never the only criterion")

    releases = [r for r in _list(payload, "releases") if isinstance(r, dict)]
    ids: list[str] = []
    for release in releases:
        rid = str(release.get("id", "")).strip()
        if rid in ids:
            c.add("duplicate_release", rid, "release ids are unique")
        ids.append(rid)
    known = set(ids)

    def check_ref(ref: Any, where: str) -> None:
        if str(ref).strip() not in known:
            c.add("unknown_release_reference", where, f"{ref!r} is not a release of the proposal")

    for release in releases:
        rid = str(release.get("id", "")).strip()
        rtype = str(release.get("type", "")).strip()
        if not RELEASE_ID_RE.match(rid):
            c.add("bad_release_id", rid or "?", "a release id is r<N>, or r<N>.<M> when interleaved")
        if rtype not in c.types:
            c.add("unknown_release_type", rid, f"type must be one of {', '.join(sorted(c.types))}")
        pattern = str(release.get("pattern", "")).strip()
        if pattern not in c.patterns:
            c.add("unknown_pattern", rid, "the cut pattern is one of P1..P24 of the model")
        elif c.patterns[pattern]["shape"] == "not_a_cut":
            c.add("pattern_not_a_cut", rid, f"{pattern} does not define releases")
        for cid in release.get("criteria", []) or []:
            if cid not in written:
                c.add("criterion_not_written", rid, f"{cid} is not among the criteria written before cutting")
        if not str(release.get("goal", "")).strip():
            c.add("missing_goal", rid, "a release names the behaviour change someone external accepts")
        contains = release.get("contains") or []
        may_be_empty = bool(c.types.get(rtype, {}).get("may_have_no_units"))
        if not contains and not may_be_empty:
            c.add("empty_release", rid, "a release carries units of the brief, unless it is an enabler, measuring or already built")
        for index, unit in enumerate(contains, start=1):
            if not c.contains_ok(unit):
                c.add("contains_without_source", f"{rid} contains[{index}]",
                      "each unit is {place, quote} verbatim in the brief, {item: C-NN} of 9.1 or {item: P-N} the brief names")
        if rtype != "enabler" and _LAYER_NAME_RE.search(str(release.get("name", ""))):
            c.add("layer_cut", rid, "a release named after a technical layer is a horizontal cut")
        places = [str(u.get("place", "")).split(".")[0] for u in contains if isinstance(u, dict) and u.get("place")]
        if rtype == "functional" and places and len(set(places)) == 1 and places[0] in {"4", "5"}:
            c.add("layer_cut", rid, f"every unit sits in §{places[0]} only: a functional release crosses the lenses")
        for key in ("depends_on", "enables"):
            for index, edge in enumerate(release.get(key) or [], start=1):
                if not isinstance(edge, dict):
                    c.add("payload_shape", f"{rid} {key}[{index}]", "an edge is {release, why, strength}")
                    continue
                check_ref(edge.get("release"), f"{rid} {key}[{index}]")
                if edge.get("strength", "hard") not in STRENGTHS:
                    c.add("bad_strength", f"{rid} {key}[{index}]", "strength is hard or opportunistic")
        if rtype == "conditional" and str(release.get("condition", "")).strip() not in c.open_gaps:
            c.add("conditional_without_gap", rid, "a conditional release names the open gap that decides it")
        if rtype == "measuring":
            spike = release.get("spike") if isinstance(release.get("spike"), dict) else {}
            questions = [q for q in spike.get("questions", []) if str(q).strip()]
            if not 1 <= len(questions) <= 3 or not str(spike.get("time_box", "")).strip():
                c.add("spike_contract", rid, "a measuring release carries 1-3 questions and a time-box, and closes with a DEC")
        if rtype == "interleaved":
            match = RELEASE_ID_RE.match(rid)
            if not (match and match.group(2)) or release.get("interleave_subtype") not in c.subtypes:
                c.add("interleave_contract", rid, f"an interleaved release is r<N>.<M> with a subtype ({', '.join(sorted(c.subtypes))})")

    base = payload.get("base")
    if isinstance(base, dict):
        for index, piece in enumerate(base.get("pieces") or [], start=1):
            if not isinstance(piece, dict) or not str(piece.get("reason", "")).strip():
                c.add("base_piece_without_reason", f"base.pieces[{index}]", "each base piece carries its reason")
        negative = base.get("not_in_base")
        if not isinstance(negative, list):
            c.add("negative_list_missing", "base", "the base lists what does not go in (not_in_base), with where it goes")
        else:
            for index, piece in enumerate(negative, start=1):
                if not isinstance(piece, dict) or not str(piece.get("reason", "")).strip():
                    c.add("negative_list_missing", f"base.not_in_base[{index}]", "each excluded piece carries its reason")
                else:
                    check_ref(piece.get("goes_to"), f"base.not_in_base[{index}]")

    for index, sketch in enumerate(_list(payload, "sketches"), start=1):
        if not isinstance(sketch, dict) or not str(sketch.get("goal", "")).strip() \
                or str(sketch.get("pattern", "")).strip() not in c.patterns:
            c.add("sketch_incomplete", f"sketches[{index}]", "a sketch outside the horizon is a goal and a cut pattern")

    order = {str(r.get("id", "")).strip(): (int(r.get("wave", 0) or 0), *release_order(str(r.get("id", "")).strip()))
             for r in releases}
    for index, row in enumerate(_list(payload, "inheritance"), start=1):
        if not isinstance(row, dict):
            c.add("payload_shape", f"inheritance[{index}]", "a row is {gap, release, why}")
            continue
        gap = str(row.get("gap", "")).strip()
        target = str(row.get("release", "")).strip()
        if gap not in c.open_gaps:
            c.add("inheritance_unknown_gap", f"inheritance[{index}]", f"{gap or '?'} is not an open gap of the brief")
            continue
        check_ref(target, f"inheritance[{index}]")
        needers = sorted((r for r in releases if gap in (r.get("needs") or [])),
                         key=lambda r: order[str(r.get("id", "")).strip()])
        first = str(needers[0].get("id", "")).strip() if needers else ""
        if not first:
            c.add("misplaced_inheritance", f"inheritance[{index}]", f"no release says it needs {gap}")
        elif target != first:
            c.add("misplaced_inheritance", f"inheritance[{index}]", f"{gap} goes to the first release that needs it: {first}, not {target}")

    if any(str(r.get("type", "")) == "integrator" for r in releases):
        rows = [row for row in _list(payload, "integrator_consumption") if isinstance(row, dict)]
        if not rows:
            c.add("integrator_without_consumption", "integrator_consumption", "the integrator carries its consumption table (what it uses from whom)")
        for index, row in enumerate(rows, start=1):
            check_ref(row.get("from"), f"integrator_consumption[{index}]")
    return {"findings": c.findings, "valid": not c.findings}


def _summary(payload: dict[str, Any]) -> dict[str, Any]:
    releases = [r for r in payload.get("releases", []) if isinstance(r, dict)]
    return {
        "releases": [{"id": r.get("id"), "type": r.get("type"), "wave": r.get("wave", 0), "pattern": r.get("pattern"),
                      "suggested_scope": bool(r.get("suggested_scope"))} for r in releases],
        "criteria": [c.get("id") for c in payload.get("criteria", []) if isinstance(c, dict)],
        "base": bool(payload.get("base")),
        "sketches": len(payload.get("sketches", []) or []),
        "inheritance": len(payload.get("inheritance", []) or []),
    }


def apply_proposal(project_id: str, source: Path) -> dict[str, Any]:
    """Validate and store a proposal. Every finding is reported; nothing is stored on a finding."""
    from .core.io import read_json, write_text
    from .core.paths import workspace_path
    from .discovery import parse_gap_rows
    from .split import ASSESSMENT_JSON, brief_hash, refresh_if_stale, run_assess

    base = workspace_path(project_id)
    brief_path = base / "02_requirements" / "project-brief.md"
    if not brief_path.is_file():
        raise SplitProposalError("/split --propose needs a compiled brief v2; run /maturity first")
    payload = read_json(Path(source), None)
    if not isinstance(payload, dict):
        raise SplitProposalError("the proposal must be a JSON object")
    gaps_path = base / "01_discovery" / "gaps.md"
    rows = parse_gap_rows(gaps_path.read_text(encoding="utf-8")) if gaps_path.is_file() else []
    open_gaps = {str(g.get("id", "")).strip("`") for g in rows if str(g.get("status", "")).upper() != "CLOSED"}
    result = validate_proposal(brief_path.read_text(encoding="utf-8"), payload, open_gaps)
    if result["findings"]:
        reasons = "; ".join(f"[{f['code']}] {f['where']}: {f['reason']}" for f in result["findings"])
        raise SplitProposalError(f"the proposal was refused ({len(result['findings'])} finding(s)): {reasons}")
    assessment_path = base / "01_discovery" / ASSESSMENT_JSON
    refreshed = refresh_if_stale(project_id)
    if refreshed:
        assessment = refreshed["recommendation"]
    elif assessment_path.is_file():
        assessment = (read_json(assessment_path, {}) or {}).get("recommendation", {}).get("value")
    else:
        assessment = run_assess(project_id)["recommendation"]  # evaluate before proposing
    stored = {
        "status": "proposal",
        "project_id": project_id,
        "brief_sha256": brief_hash(brief_path),
        "assessment": assessment,
        "proposal_sha256": hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest(),
        "summary": _summary(payload),
        "proposal": payload,
    }
    target = base.joinpath(*PROPOSAL_DIR, PROPOSAL_FILE)
    write_text(target, json.dumps(stored, ensure_ascii=False, indent=2) + "\n")
    out = {"status": "proposal", "path": target.as_posix(), "assessment": assessment, **stored["summary"]}
    from .release_split import PARTITION_FILE, validate_partition  # IMP-266: what --confirm will ask for

    previous = read_json(base.joinpath(*PROPOSAL_DIR, PARTITION_FILE), None)
    frozen = previous.get("contracts_frozen") if isinstance(previous, dict) else None
    preview = validate_partition(brief_path.read_text(encoding="utf-8"), payload, open_gaps, frozen or {})
    out["partition_preview"] = {"valid": preview["valid"], "codes": sorted({f["code"] for f in preview["findings"]})}
    if assessment != "split":
        out["warning"] = f"the assessment says {assessment}: the BA decides whether a series is worth it"
    return out
