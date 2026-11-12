"""IMP-266 (H17a): deterministic validation of the partition, and /split --confirm.

The proposal (IMP-265) passed its structure and anchor checks; this module checks the
partition itself, over the release split model (IMP-264):

* **Graph with contracts as nodes.** A shared contract (schema, API, file format,
  event, role, a spike's DEC…) is a node `{id: "K1", created_by: "r0", …}`. Every
  hard `depends_on` edge names its why and the contract it consumes, which its target
  creates. Edges come in symmetric pairs (`depends_on` ⇔ `enables`). A cycle over the
  hard edges is a gap: a contract is missing or a dependency is extra.
* **Waves.** A hard dependency always points to an earlier wave; the topological
  waves are reported.
* **Coverage n of n** per family: the scope items of §6.1, the build items `C-NN` of
  §9 and the screens `P-N` the brief names. Each goes to exactly one release or to a
  sketch outside the horizon.
* **Single owner** when created: a contract has one creator and one name. One
  extended by two or more siblings carries a cross note and a merge order [A41]; a
  shared service exposes only operations with a consumer.
* **Frozen contracts.** `/split --confirm` freezes each contract by sha256; a later
  change needs an audited delta (`contract_deltas`) [A37].
* **Relaxed rule:** never legal, regulatory or Must, and always `restored_in` a later
  release [A39].
* **Anti-patterns:** the six validated ones of the model, reported by key.
* **Pending with tentacles, two distinct signals** [C20]: the gap deciding a
  conditional repeated in several siblings is a partition defect (a finding); a gap
  that holds back the start of ≥ `UMBRAL_TRANSVERSAL` of the releases is transversal
  readiness (a signal, not a defect of the cut).
* **The integrator's premise** against its consumption table.

`/split --confirm` requires all of it green [C6] and records who confirms: the BA and
the technical team. The client's confirmation opens a gap [A46]. Nothing is compiled
here: the series compiles in IMP-267.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from .split_proposal import (
    PROPOSAL_DIR, PROPOSAL_FILE, SplitProposalError, _Checker, _norm, release_order,
    validate_proposal,
)

PARTITION_FILE = "partition.json"
CLIENT_GAP_ID = "GAP-SPLIT-CLIENT"
# share of the releases a gap must hold back to be transversal readiness [C20]
UMBRAL_TRANSVERSAL = 0.75
# siblings beyond the conditional itself that repeat its deciding gap: not isolated [C20]
TENTACLE_SIBLINGS = 2
CONTRACT_ID_RE = re.compile(r"^K\d+$")
CONTRACT_KINDS = ("schema", "api", "file_format", "table", "column", "parameter", "endpoint", "event", "role",
                  "service", "decision")
# the fields that are the contract; consumers may change without changing it
CONTRACT_HASH_FIELDS = ("name", "kind", "created_by", "definition", "operations")
PARTITION_CODES = (
    "contract_shape", "single_owner", "duplicate_owner", "extension_without_cross_note", "operation_without_consumer",
    "edge_without_why", "edge_without_contract", "unknown_contract", "contract_owner_mismatch", "asymmetric_edge",
    "missing_contract", "hard_edge_wave", "hard_edge_on_conditional", "coverage_missing", "coverage_duplicate",
    "contract_changed_without_delta", "relaxed_without_source", "relaxed_without_restore", "relaxed_forbidden",
    "enabler_without_demo", "release_without_outcome_metric", "tentacle_partition_defect", "integrator_premise",
)
# the six validated anti-patterns of the model, by the finding codes that reveal them
ANTI_PATTERN_CODES = {
    "layer_cut": ("layer_cut",),
    "enabler_without_demo": ("enabler_without_demo",),
    "empty_release": ("empty_release",),
    "spike_without_questions": ("spike_contract",),
    "release_without_outcome_metric": ("release_without_outcome_metric",),
    "cut_without_source": ("criterion_without_source", "contains_without_source", "core_without_source",
                           "variation_without_source"),
}
_LEGAL_RE = re.compile(r"\b(legal\w*|regulat\w*|regulator\w*|normativ\w*|compliance|cumplimiento|ley(?:es)?|law|"
                       r"statut\w*|obligaci[oó]n legal)\b", re.I)
_MUST_RE = re.compile(r"\b(Must|MUST)\b")


class ReleaseSplitError(SplitProposalError):
    pass


def _s(value: Any) -> str:
    return str(value if value is not None else "").strip()


def _dicts(value: Any) -> list[dict[str, Any]]:
    return [v for v in value if isinstance(v, dict)] if isinstance(value, list) else []


def contract_hash(contract: dict[str, Any]) -> str:
    body = {key: contract.get(key) for key in CONTRACT_HASH_FIELDS}
    body["operations"] = sorted(_s(op.get("name")) for op in _dicts(contract.get("operations")))
    return hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def _cited_lines(checker: _Checker, place: str) -> list[str]:
    section = checker.sections.get(place)
    if section is None:
        return []
    rows = []
    for line in checker.lines[section.start + 1:section.end]:
        if line.lstrip().startswith("- ") and "[[" in line:
            rows.append(re.sub(r"\[\[[^\]]+\]\]", "", line).strip(" -"))
    return rows


def _families(checker: _Checker) -> dict[str, list[str]]:
    build: list[str] = []
    for place in [p for p in checker.sections if p == "9" or p.startswith("9.")]:
        section = checker.sections[place]
        for line in checker.lines[section.start + 1:section.end]:
            build += [m.strip("`") for m in re.findall(r"`C-\d{2,}`", line)]
    screens: list[str] = []
    for place in [p for p in checker.sections if p == "4" or p.startswith("4.")]:
        section = checker.sections[place]
        for line in checker.lines[section.start + 1:section.end]:
            screens += re.findall(r"\bP-\d+\b", line)
    return {
        "scope_6_1": _cited_lines(checker, "6.1"),
        "build_items": sorted(set(build), key=lambda i: int(i.split("-")[1])),
        "screens": sorted(set(screens), key=lambda i: int(i.split("-")[1])),
    }


def _unit_covers(unit: dict[str, Any], family: str, member: str) -> bool:
    item = _s(unit.get("item"))
    if family in ("build_items", "screens"):
        return item == member or (family == "screens" and bool(re.search(rf"\b{re.escape(member)}\b", _s(unit.get("quote")))))
    place, quote = _s(unit.get("place")), _norm(unit.get("quote", ""))
    return (place == "6" or place == "6.1" or place.startswith("6.1.")) and bool(quote) and quote in _norm(member)


def _cycles(nodes: list[str], edges: dict[str, list[str]]) -> list[list[str]]:
    """Every elementary cycle over the hard edges, each once, rotated to its smallest id."""
    found: set[tuple[str, ...]] = set()
    ordered = sorted(nodes, key=release_order)

    def walk(start: str, node: str, path: list[str]) -> None:
        for nxt in edges.get(node, []):
            if nxt == start:
                cycle = path[:]
                pivot = min(range(len(cycle)), key=lambda i: release_order(cycle[i]))
                found.add(tuple(cycle[pivot:] + cycle[:pivot]))
            elif nxt not in path and release_order(nxt) > release_order(start):
                walk(start, nxt, path + [nxt])

    for start in ordered:
        walk(start, start, [start])
    return [list(c) for c in sorted(found, key=lambda c: [release_order(x) for x in c])]


def _waves(nodes: list[str], edges: dict[str, list[str]]) -> dict[str, list[str]]:
    memo: dict[str, int] = {}

    def depth(node: str) -> int:
        if node not in memo:
            memo[node] = 0
            memo[node] = 1 + max((depth(d) for d in edges.get(node, []) if d in nodes), default=-1)
        return memo[node]

    waves: dict[str, list[str]] = {}
    for node in sorted(nodes, key=release_order):
        waves.setdefault(str(depth(node)), []).append(node)
    return dict(sorted(waves.items(), key=lambda kv: int(kv[0])))


def validate_partition(brief_text: str, payload: dict[str, Any], open_gaps: set[str] | None = None,
                       frozen: dict[str, str] | None = None) -> dict[str, Any]:
    """The proposal checks plus the partition rules. Pure; no findings means /split --confirm may run."""
    gaps = set(open_gaps or ())
    proposal = validate_proposal(brief_text, payload, gaps)
    c = _Checker(brief_text, gaps)
    c.findings = list(proposal["findings"])
    if not isinstance(payload, dict):
        return {"findings": c.findings, "valid": False, "waves": {}, "coverage": {}, "signals": [], "anti_patterns": {},
                "contracts": {}, "deltas": []}
    releases = _dicts(payload.get("releases"))
    by_id = {_s(r.get("id")): r for r in releases if _s(r.get("id"))}
    ids = list(by_id)
    rank = {rid: (int(r.get("wave", 0) or 0), *release_order(rid)) for rid, r in by_id.items()}

    # --- contracts as nodes, single owner -------------------------------------------------
    contracts: dict[str, dict[str, Any]] = {}
    names: dict[str, str] = {}
    for index, contract in enumerate(_dicts(payload.get("contracts")), start=1):
        kid = _s(contract.get("id"))
        where = f"contracts[{index}] {kid}".strip()
        if not CONTRACT_ID_RE.match(kid) or kid in contracts or not _s(contract.get("name")) \
                or _s(contract.get("kind")) not in CONTRACT_KINDS:
            c.add("contract_shape", where, f"a contract is {{id: K<N> (unique), name, kind ({', '.join(CONTRACT_KINDS)}), "
                                           "created_by, definition}")
            if not CONTRACT_ID_RE.match(kid) or kid in contracts:
                continue
        contracts[kid] = contract
        owner = contract.get("created_by")
        if not isinstance(owner, str) or owner.strip() not in by_id:
            c.add("single_owner", where, "a contract is created by exactly one release of the series (created_by: rN)")
        name = _norm(contract.get("name", ""))
        if name and name in names:
            c.add("duplicate_owner", where, f"{names[name]} already creates {contract.get('name')!r}: one creator, the others use it under the same name")
        elif name:
            names[name] = kid
        extended = [_s(r) for r in contract.get("extended_by") or []]
        for ref in extended:
            if ref not in by_id:
                c.add("unknown_release_reference", f"{where} extended_by", f"{ref!r} is not a release of the proposal")
        if len(set(extended)) >= 2 and (not _s(contract.get("cross_note"))
                                         or sorted(_s(r) for r in contract.get("merge_order") or []) != sorted(set(extended))):
            c.add("extension_without_cross_note", where, "an artifact extended by two or more siblings carries a cross note and a merge order of exactly those siblings [A41]")
        for op_index, op in enumerate(_dicts(contract.get("operations")), start=1):
            consumers = [_s(r) for r in op.get("consumers") or []]
            if not consumers:
                c.add("operation_without_consumer", f"{where} operations[{op_index}]",
                      "a shared service exposes only the operations with a consumer inside the series")
            for ref in consumers:
                if ref not in by_id:
                    c.add("unknown_release_reference", f"{where} operations[{op_index}]", f"{ref!r} is not a release of the proposal")

    # --- edges: why, contract consumed, symmetry ------------------------------------------
    hard: dict[str, list[str]] = {rid: [] for rid in ids}
    pairs: dict[str, set[tuple[str, str, str]]] = {"depends_on": set(), "enables": set()}
    for rid, release in by_id.items():
        for key in ("depends_on", "enables"):
            for index, edge in enumerate(_dicts(release.get(key)), start=1):
                target = _s(edge.get("release"))
                where = f"{rid} {key}[{index}]"
                strength = _s(edge.get("strength")) or "hard"
                if not _s(edge.get("why")):
                    c.add("edge_without_why", where, "every edge carries its reason per target")
                if target not in by_id:
                    continue  # unknown_release_reference, from the proposal checks
                if key == "depends_on":
                    pairs["depends_on"].add((rid, target, strength))
                    if strength == "hard":
                        hard[rid].append(target)
                        consumed = _s(edge.get("consumes"))
                        if not consumed:
                            c.add("edge_without_contract", where, "a hard dependency names the contract it consumes (consumes: K<N>)")
                        elif consumed not in contracts:
                            c.add("unknown_contract", where, f"{consumed} is not a contract of the proposal")
                        elif _s(contracts[consumed].get("created_by")) != target:
                            c.add("contract_owner_mismatch", where, f"{consumed} is created by {contracts[consumed].get('created_by')}, not by {target}")
                        if _s(by_id[target].get("type")) == "conditional" and _s(release.get("type")) != "conditional":
                            c.add("hard_edge_on_conditional", where, f"{target} is conditional (dotted until its gap is decided): a committed release cannot hard-depend on it")
                else:
                    pairs["enables"].add((target, rid, strength))
    for a, b, strength in sorted(pairs["depends_on"] ^ pairs["enables"]):
        side = "depends_on" if (a, b, strength) in pairs["depends_on"] else "enables"
        missing = f"{b} enables {a}" if side == "depends_on" else f"{a} depends_on {b}"
        c.add("asymmetric_edge", f"{a} → {b}", f"edges come in symmetric pairs with the same strength: {missing} is missing ({strength})")

    # --- cycles and waves -------------------------------------------------------------------
    cycles = _cycles(ids, hard)
    for cycle in cycles:
        c.add("missing_contract", " → ".join(cycle + [cycle[0]]),
              "a cycle over hard edges is a gap: a contract is missing or a dependency is extra (back to the pattern step)")
    if not cycles:
        for rid in ids:
            for target in hard[rid]:
                if rank[target][0] >= rank[rid][0]:
                    c.add("hard_edge_wave", f"{rid} → {target}", f"a hard dependency points to an earlier wave: {target} is wave {rank[target][0]}, {rid} is wave {rank[rid][0]}")
    waves = _waves(ids, hard) if not cycles else {}

    # --- coverage n of n --------------------------------------------------------------------
    holders: list[tuple[str, list[dict[str, Any]]]] = [(rid, _dicts(r.get("contains"))) for rid, r in by_id.items()]
    for index, sketch in enumerate(_dicts(payload.get("sketches")), start=1):
        units = _dicts(sketch.get("contains"))
        for u_index, unit in enumerate(units, start=1):
            if not c.contains_ok(unit):
                c.add("contains_without_source", f"sketches[{index}] contains[{u_index}]",
                      "each unit is {place, quote} verbatim in the brief, {item: C-NN} or {item: P-N}")
        holders.append((f"sketch:{_s(sketch.get('name')) or index}", units))
    coverage: dict[str, dict[str, int]] = {}
    for family, members in _families(c).items():
        covered = 0
        for member in members:
            owners = [holder for holder, units in holders if any(_unit_covers(u, family, member) for u in units)]
            if not owners:
                c.add("coverage_missing", f"{family}: {member[:80]}", "each piece goes to exactly one release or to a sketch outside the horizon")
            elif len(owners) > 1:
                c.add("coverage_duplicate", f"{family}: {member[:80]}", f"the piece goes to {', '.join(owners)}: exactly one owner")
            else:
                covered += 1
        coverage[family] = {"covered": covered, "total": len(members)}

    # --- frozen contracts -------------------------------------------------------------------
    hashes = {kid: contract_hash(k) for kid, k in contracts.items()}
    delta_rows = {_s(d.get("contract")): d for d in _dicts(payload.get("contract_deltas"))}
    deltas: list[dict[str, str]] = []
    for kid, old in sorted((frozen or {}).items()):
        new = hashes.get(kid, "")
        if new == old:
            continue
        row = delta_rows.get(kid)
        if not row or not _s(row.get("why")):
            c.add("contract_changed_without_delta", kid, f"{kid} was frozen at confirmation and changed ({'removed' if not new else 'new hash'}): an audited delta {{contract, why, finding}} is required [A37]")
        else:
            deltas.append({"contract": kid, "from_sha256": old, "to_sha256": new, "why": _s(row.get("why")),
                           "finding": _s(row.get("finding"))})

    # --- relaxed rules ----------------------------------------------------------------------
    for index, rule in enumerate(_dicts(payload.get("relaxed_rules")), start=1):
        where = f"relaxed_rules[{index}]"
        if not c.anchored(rule.get("anchor")):
            c.add("relaxed_without_source", where, "a relaxed rule cites the brief rule it relaxes, verbatim")
        release, restored = _s(rule.get("release")), _s(rule.get("restored_in"))
        if release not in by_id or restored not in by_id or rank[restored] <= rank[release]:
            c.add("relaxed_without_restore", where, "a relaxed rule names the release that relaxes it and restored_in, a later release [A39]")
        text = " ".join([_s(rule.get("rule")), _s((rule.get("anchor") or {}).get("quote") if isinstance(rule.get("anchor"), dict) else "")])
        if _s(rule.get("kind")).lower() in ("legal", "regulatory") or _s(rule.get("priority")).lower() == "must" \
                or _LEGAL_RE.search(text) or _MUST_RE.search(text):
            c.add("relaxed_forbidden", where, "a legal, regulatory or Must rule is never relaxed [A39]")

    # --- anti-patterns the proposal checks do not cover ------------------------------------
    for rid, release in by_id.items():
        rtype = _s(release.get("type"))
        if rtype == "enabler" and not _s(release.get("closing_check")):
            c.add("enabler_without_demo", rid, "an enabler says how it is shown done (closing_check): a demonstrable result")
        elif rtype not in ("enabler", "measuring") and not _s(release.get("closing_check")):
            c.add("release_without_outcome_metric", rid, "a release names the closing check someone external runs to accept it")

    # --- pending with tentacles: two distinct signals [C20] ---------------------------------
    signals: list[dict[str, Any]] = []
    for rid, release in by_id.items():
        if _s(release.get("type")) != "conditional":
            continue
        gap = _s(release.get("condition"))
        others = [o for o, r in by_id.items() if o != rid and (gap in (r.get("needs") or []) or _s(r.get("condition")) == gap)]
        if gap and len(others) >= TENTACLE_SIBLINGS:
            c.add("tentacle_partition_defect", rid, f"{gap} decides {rid} and repeats in {', '.join(sorted(others, key=release_order))}: the conditional is not isolated; cut again")
    if len(ids) >= 2:
        needed: dict[str, list[str]] = {}
        for rid, release in by_id.items():
            for gap in {_s(g) for g in release.get("needs") or []}:
                needed.setdefault(gap, []).append(rid)
        for gap, holders_ in sorted(needed.items()):
            share = len(holders_) / len(ids)
            if gap in gaps and share >= UMBRAL_TRANSVERSAL:
                signals.append({"code": "transversal_readiness", "gap": gap, "share": round(share, 3),
                                "releases": sorted(holders_, key=release_order),
                                "reason": f"{gap} holds back the start of {len(holders_)} of {len(ids)} releases: resolve it before the series starts (readiness, not a cut defect)"})

    # --- the integrator's premise -----------------------------------------------------------
    all_edges = {rid: [_s(e.get("release")) for e in _dicts(r.get("depends_on")) if _s(e.get("release")) in by_id]
                 for rid, r in by_id.items()}
    for rid, release in by_id.items():
        if _s(release.get("type")) != "integrator":
            continue
        reach: set[str] = set()
        stack = list(all_edges[rid])
        while stack:
            node = stack.pop()
            if node not in reach:
                reach.add(node)
                stack += all_edges.get(node, [])
        for other, r in by_id.items():
            if other != rid and _s(r.get("type")) not in ("conditional", "integrator") and other not in reach:
                c.add("integrator_premise", rid, f"the integrator depends directly or transitively on every non-conditional release: {other} is not reached")
        rows = _dicts(payload.get("integrator_consumption"))
        sources = {_s(row.get("from")) for row in rows}
        for target in hard[rid]:
            if target not in sources:
                c.add("integrator_premise", rid, f"{rid} depends on {target} but its consumption table uses nothing from it")
        for index, row in enumerate(rows, start=1):
            origin, uses = _s(row.get("from")), _s(row.get("uses"))
            if origin in by_id and origin not in reach:
                c.add("integrator_premise", f"integrator_consumption[{index}]", f"{rid} consumes from {origin} without depending on it")
            if CONTRACT_ID_RE.match(uses) and (uses not in contracts or origin not in
                                               {_s(contracts[uses].get("created_by")), *[_s(x) for x in contracts[uses].get("extended_by") or []]}):
                c.add("integrator_premise", f"integrator_consumption[{index}]", f"{uses} is not a contract {origin} creates or extends")

    present = {f["code"] for f in c.findings}
    anti = {key: sorted(present & set(codes)) for key, codes in ANTI_PATTERN_CODES.items() if present & set(codes)}
    return {"findings": c.findings, "valid": not c.findings, "waves": waves, "coverage": coverage, "signals": signals,
            "anti_patterns": anti, "contracts": hashes, "deltas": deltas}


# --- /split --confirm ---------------------------------------------------------------------


def open_split_gap(project_id: str, row: dict[str, str], language: str) -> None:
    """Open a gap of the series in gaps.md once; reopen it if it was closed. A workspace without gaps.md is left alone."""
    from .core.io import write_text
    from .discovery import count_gaps, parse_gap_rows, readiness_stage_after_gap_change, render_gaps
    from .workspace import update_state, workspace_path

    path = workspace_path(project_id) / "01_discovery" / "gaps.md"
    if not path.exists():
        return
    rows = [r for r in parse_gap_rows(path.read_text(encoding="utf-8")) if r.get("id") != "NONE"]
    current = next((r for r in rows if r.get("id", "").strip("`") == row["id"]), None)
    if current is not None and str(current.get("status", "")).upper() != "CLOSED":
        return
    if current is not None:
        current.update(status="OPEN", resolution_note="")
    else:
        rows.append(row)
    req_id = rows[0].get("parent", "REQ-001").strip("`") if rows else "REQ-001"
    write_text(path, render_gaps(project_id, rows, req_id, language))
    counts = count_gaps(rows)
    update_state(project_id, gap_counts=counts, readiness_stage=readiness_stage_after_gap_change(project_id, counts))


def _open_client_gap(project_id: str, ba: str, tech: str, language: str) -> None:
    """The client's confirmation of the series is a gap [A46]; opened once, reopened if it was closed."""
    open_split_gap(project_id, {
        # medium: visible, never blocking; the BA and the technical team already confirmed (IMP-267b)
        "id": CLIENT_GAP_ID, "lens": "business", "severity": "medium", "status": "OPEN",
        "description": f"The client has not confirmed the release series (confirmed by the BA {ba} and the technical team {tech}).",
        "question": "Does the client confirm the release series in 02_requirements/series/partition.json?",
        "evidence_mention": "02_requirements/series/partition.json", "origin": "split", "resolution_note": "",
    }, language)


def confirm_partition(project_id: str, ba: str, tech: str) -> dict[str, Any]:
    """Confirm the stored proposal: the validation must be green; the BA and the technical team sign."""
    from .core.io import read_json, write_text
    from .core.paths import workspace_path
    from .discovery import parse_gap_rows
    from .gap_resolution import project_language
    from .split import brief_hash

    if not _s(ba) or not _s(tech):
        raise ReleaseSplitError("/split --confirm records who confirms: --ba NAME and --tech NAME (the technical team) are both required")
    base = workspace_path(project_id)
    series = base.joinpath(*PROPOSAL_DIR)
    stored = read_json(series / PROPOSAL_FILE, None)
    if not isinstance(stored, dict) or not isinstance(stored.get("proposal"), dict):
        raise ReleaseSplitError("/split --confirm needs a stored proposal; run /split --propose first")
    brief_path = base / "02_requirements" / "project-brief.md"
    if not brief_path.is_file():
        raise ReleaseSplitError("/split --confirm needs the compiled brief v2")
    if brief_hash(brief_path) != stored.get("brief_sha256"):
        raise ReleaseSplitError("the brief changed since the proposal was stored; run /split --propose again")
    gaps_path = base / "01_discovery" / "gaps.md"
    rows = parse_gap_rows(gaps_path.read_text(encoding="utf-8")) if gaps_path.is_file() else []
    open_gaps = {_s(g.get("id")).strip("`") for g in rows if _s(g.get("status")).upper() != "CLOSED"}
    previous = read_json(series / PARTITION_FILE, None)
    previous = previous if isinstance(previous, dict) else {}
    frozen = previous.get("contracts_frozen") or {}
    payload = stored["proposal"]
    result = validate_partition(brief_path.read_text(encoding="utf-8"), payload, open_gaps, frozen)
    if result["findings"]:
        reasons = "; ".join(f"[{f['code']}] {f['where']}: {f['reason']}" for f in result["findings"])
        raise ReleaseSplitError(f"the partition is not green ({len(result['findings'])} finding(s)); nothing was confirmed: {reasons}")
    releases = sorted((_s(r.get("id")) for r in _dicts(payload.get("releases"))), key=release_order)
    partition = {
        "status": "confirmed",
        "project_id": project_id,
        "brief_sha256": stored.get("brief_sha256"),
        "proposal_sha256": stored.get("proposal_sha256"),
        "confirmed_by": {"ba": _s(ba), "technical_team": _s(tech)},
        "client_confirmation": {"status": "pending", "gap": CLIENT_GAP_ID},
        "releases": releases,
        "waves": result["waves"],
        "coverage": result["coverage"],
        "signals": result["signals"],
        "contracts_frozen": result["contracts"],
        "contract_deltas": list(previous.get("contract_deltas") or []) + result["deltas"],
    }
    target = series / PARTITION_FILE
    write_text(target, json.dumps(partition, ensure_ascii=False, indent=2) + "\n")
    _open_client_gap(project_id, _s(ba), _s(tech), project_language(project_id))
    from .release_series import compile_series  # IMP-267a: the confirmed partition compiles the series

    series = compile_series(project_id)
    return {"status": "confirmed", "path": target.as_posix(), "confirmed_by": partition["confirmed_by"],
            "client_confirmation_gap": CLIENT_GAP_ID, "releases": releases, "waves": result["waves"],
            "coverage": result["coverage"], "signals": result["signals"], "contract_deltas": len(result["deltas"]),
            "series": series}
