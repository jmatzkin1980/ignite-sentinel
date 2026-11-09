"""IMP-251: contradictions, echo, disguised proposals and cited-but-undelivered sources.

Runs over every source that `/ingest` or `/sync` crosses, after its F-NN row is open
(IMP-250a). Everything is deterministic over the text; nothing picks a winner.

- **Statements.** Short assertions are read line by line: `the term is 30 days`,
  `SLA: 24 h`. Each one is anchored to its F-NN row and line in
  `01_discovery/statement_ledger.json`.
- **Contradiction.** Two sources stating different values for the same subject are
  both anchored, and a blocking gap with `origin: contradiction` opens. It never
  chooses. A subject a source does not mention is **source silence**, a value of its
  own, never a contradiction.
- **Interim value.** While that gap is open, the precedence of IMP-250b says which
  version governs the body, marked `⏳` (or `⚠` when `validation_direction` is
  `built`). An unsettled clash has no interim value: the newest source never wins.
- **Echo.** A source Sentinel wrote (an own artifact) never adds facts and never
  closes a gap: it is echo, not authority.
- **Disguised proposal.** A source that declares itself not validated (draft,
  borrador, not validated...) only contributes proposals, never facts, and cannot
  close a gap. A line with a proposal cue, or a new technical name nobody ratified,
  is a proposal too.
- **Cited, never delivered.** A source that leans on another document ("según el
  contrato de API", "as defined in the SAD") that is not in the registry opens a gap
  with `origin: cited_not_delivered`, saying what to ask for and to whom.

Gap ids derive from the topic (`GAP-CTR-<hash>`, `GAP-CND-<hash>`), so the same
topic never opens twice. IMP-257 will replace this with its topic deduplication.
"""
from __future__ import annotations

import hashlib
import re
import unicodedata
from pathlib import Path
from typing import Any

from .core.io import write_text
from .source_routing import SCOPES, resolve_precedence, routing_data, row_authority
from .workspace import load_config, read_json, update_state, workspace_path, write_json

LEDGER_FILE = "01_discovery/statement_ledger.json"
REPORT_FILE = "01_discovery/contradictions.md"
ORIGIN_CONTRADICTION = "contradiction"
ORIGIN_CITED_NOT_DELIVERED = "cited_not_delivered"
AGREE, CONTRADICTION, SILENCE = "agree", "contradiction", "silence"
FACT, PROPOSAL = "fact", "proposal"
INTERIM_MARKS = {"to-build": "⏳", "built": "⚠"}

ECHO_SOURCE_NOTE = "echo-source: the only source is our own artifact; confirm it from an external source"
UNVALIDATED_SOURCE_NOTE = "unvalidated-source: the source declares itself not validated; its answers are proposals until ratified"

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_DIGIT_RE = re.compile(r"\d+(?:[.,]\d+)?")
_COPULA_RE = re.compile(
    r"\b(?P<subject>(?:el|la|los|las|the)\s+[^.;:,\n]{2,50}?)\s+"
    r"(?:es|son|sera|seran|is|are|will be)\s+(?:de\s+|of\s+)?(?P<value>[^.;,\n]{1,60})",
)
_KV_RE = re.compile(r"^(?:[-*+]\s+|\d+[.)]\s+)?(?:\*\*)?(?P<subject>[^:|#`*]{2,60}?)(?:\*\*)?\s*:\s*(?P<value>[^|]{1,80}?)\s*$")
_TECH_NAME_RE = re.compile(r"`([^`]{2,40})`|\b([a-z]+[A-Z][A-Za-z0-9]*|[A-Z][a-z0-9]+[A-Z][A-Za-z0-9]*|[a-z0-9]+_[a-z0-9_]+)\b")


# --- text helpers --------------------------------------------------------------


def _fold(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch)).lower()


def _data() -> dict[str, Any]:
    return routing_data()["conflicts"]


def _tokens(text: str) -> list[str]:
    stop = set(_data()["stopwords"])
    return [token for token in _TOKEN_RE.findall(_fold(text)) if len(token) >= 3 and token not in stop]


def _short_hash(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:6].upper()


def _cell(text: str) -> str:
    return text.replace("|", "/").replace("\n", " ").strip()


def _citable_lines(text: str) -> list[tuple[int, str]]:
    return [(number, line.strip()) for number, line in enumerate(text.splitlines(), start=1) if line.strip()]


# --- statements ----------------------------------------------------------------


def value_key(value: str) -> str:
    numbers = _DIGIT_RE.findall(value)
    if numbers:
        return "#" + ",".join(number.replace(",", ".") for number in numbers)
    return " ".join(_tokens(value)) or _fold(value).strip()


def _accept(subject_tokens: list[str], value: str, kv: bool) -> bool:
    if not subject_tokens or not value.strip():
        return False
    has_digit = bool(_DIGIT_RE.search(value))
    short = len(value.split()) <= 3
    if kv:  # "Ana: ok" is a speaker, not a subject; "SLA: 24 h" is a statement
        return has_digit or (len(subject_tokens) >= 2 and short)
    return has_digit or short


def extract_statements(text: str) -> list[dict[str, Any]]:
    """Short assertions with their line, one per subject and line."""
    found: list[dict[str, Any]] = []
    for number, line in _citable_lines(text):
        if line.startswith(("#", "|", ">")):
            continue
        folded = _fold(line)
        match = _COPULA_RE.search(folded)
        kv = False
        if match is None:
            match = _KV_RE.match(folded)
            kv = True
        if match is None:
            continue
        subject = match.group("subject").strip()
        value = match.group("value").strip().strip("*").strip()
        subject_tokens = _tokens(subject)
        if not _accept(subject_tokens, value, kv):
            continue
        found.append({
            "subject_key": "|".join(sorted(set(subject_tokens))),
            "subject": subject,
            "value": value,
            "value_key": value_key(value),
            "line": number,
            "quote": line,
        })
    return found


def classify_pair(first: dict[str, Any] | None, second: dict[str, Any] | None) -> str:
    """agree, contradiction or silence: a subject one source never states is silence."""
    if first is None or second is None:
        return SILENCE
    return AGREE if first["value_key"] == second["value_key"] else CONTRADICTION


def declares_unvalidated(text: str) -> bool:
    data = _data()
    head = [line for _, line in _citable_lines(text)][: int(data["unvalidated_header_lines"])]
    return bool(re.search(data["unvalidated_pattern"], _fold("\n".join(head))))


def new_technical_names(line: str, corpus: str) -> list[str]:
    names = []
    for match in _TECH_NAME_RE.finditer(line):
        name = (match.group(1) or match.group(2) or "").strip()
        if name and _fold(name) not in corpus:
            names.append(name)
    return names


def scope_for(subject: str) -> str:
    folded = f" {_fold(subject)} "
    for scope, words in _data()["scope_keywords"].items():
        if any(re.search(rf"(?<![a-z0-9]){re.escape(word)}(?![a-z0-9])", folded) for word in words):
            return scope
    return "rule"


def closing_block_note(row: dict[str, Any] | None, text: str) -> str | None:
    """Why a confirmed answer from this source cannot close a gap, or None when it can."""
    from .gap_resolution import EXAMPLE_SOURCE_NOTE  # local: gap_resolution imports this module

    authority = row_authority(row) if row else ""
    if authority == "own_artifact":
        return ECHO_SOURCE_NOTE
    if authority in routing_data()["never_closes"]:
        return EXAMPLE_SOURCE_NOTE
    if declares_unvalidated(text) or (row or {}).get("declared_unvalidated"):
        return UNVALIDATED_SOURCE_NOTE
    return None


# --- citations -----------------------------------------------------------------


def cited_documents(text: str) -> list[dict[str, Any]]:
    data = _data()
    nouns = set(data["document_nouns"])
    found: list[dict[str, Any]] = []
    for number, line in _citable_lines(text):
        for match in re.finditer(data["citation_pattern"], _fold(line)):
            cited = match.group("cited").strip()
            tokens = _tokens(cited)
            if not nouns.intersection(tokens):
                continue
            found.append({"cited": cited, "tokens": tokens, "line": number, "quote": line})
    return found


def _delivered(cited_tokens: list[str], rows: list[dict[str, Any]], citing_id: str) -> bool:
    """A registered row whose path shares a distinctive token with the citation."""
    nouns = set(_data()["document_nouns"])
    distinctive = [token for token in cited_tokens if token not in nouns] or cited_tokens
    for row in rows:
        if row.get("id") == citing_id:
            continue
        names = " ".join(Path(path).stem for path in row.get("paths", []))
        if set(distinctive) & set(_tokens(names.replace("-", " ").replace("_", " "))):
            return True
    return False


# --- the pass ------------------------------------------------------------------


def _ledger_path(project_id: str) -> Path:
    return workspace_path(project_id) / LEDGER_FILE


def load_ledger(project_id: str) -> dict[str, Any]:
    ledger = read_json(_ledger_path(project_id), {})
    ledger.setdefault("version", 1)
    for key in ("statements", "contradictions", "citations"):
        ledger.setdefault(key, [])
    return ledger


def _corpus(project_id: str, ledger: dict[str, Any]) -> str:
    base = workspace_path(project_id)
    chunks = [statement["quote"] for statement in ledger["statements"] if statement["kind"] == FACT]
    for relative in ("01_discovery/decisions.md", "01_discovery/identity_seeds.md", "02_requirements/requirements.md",
                     "02_requirements/project-brief.md", "03_specs/prd.md", "03_specs/specs.md"):
        path = base / relative
        if path.exists():
            chunks.append(path.read_text(encoding="utf-8"))
    return _fold("\n".join(chunks))


def _interim(contradiction: dict[str, Any], authorities: dict[str, str], config: dict[str, Any]) -> dict[str, Any]:
    candidates = [{"id": sid, "authority": authorities.get(sid, "unclassified")}
                  for sid in dict.fromkeys(item["source_id"] for item in contradiction["statements"])]
    verdict = resolve_precedence(contradiction["scope"], candidates, config)
    direction = str(config.get("validation_direction") or "to-build")
    if verdict["status"] != "resolved":
        return {"status": "unresolved", "source_id": None, "value": None, "mark": None, "rules": []}
    winner = next(item for item in contradiction["statements"] if item["source_id"] == verdict["winner"])
    return {"status": "resolved", "source_id": verdict["winner"], "value": winner["value"],
            "mark": INTERIM_MARKS.get(direction, INTERIM_MARKS["to-build"]), "rules": verdict["rules"]}


def _contradiction_gap(item: dict[str, Any]) -> dict[str, str]:
    anchors = "; ".join(f"{s['source_id']} line {s['line']}: \"{_cell(s['quote'])}\"" for s in item["statements"])
    interim = item["interim"]
    note = (f"interim {interim['mark']}: {interim['source_id']} governs the body until this closes ({', '.join(interim['rules'])})"
            if interim["status"] == "resolved" else "interim: none; no precedence rule settles it, a person decides")
    return {
        "id": item["gap_id"],
        "lens": _data()["lens_by_scope"].get(item["scope"], "business"),
        "severity": "high",
        "status": "OPEN",
        "description": _cell(f"Contradiction on '{item['subject']}' ({item['scope']}): {anchors}"),
        "question": _cell(f"Which value governs for '{item['subject']}'? Both sources stay anchored until someone decides."),
        "evidence_mention": ", ".join(dict.fromkeys(s["source_id"] for s in item["statements"])),
        "origin": ORIGIN_CONTRADICTION,
        "resolution_note": _cell(note),
    }


def _citation_gap(item: dict[str, Any]) -> dict[str, str]:
    return {
        "id": item["gap_id"],
        "lens": "business",
        "severity": "medium",
        "status": "OPEN",
        "description": _cell(
            f"{item['source_id']} cites '{item['cited']}' as authority (line {item['line']}) and it was never delivered. "
            "Until it arrives its content is source silence, not a contradiction."
        ),
        "question": _cell(f"Ask {item['ask_to']} for '{item['cited']}'."),
        "evidence_mention": item["source_id"],
        "origin": ORIGIN_CITED_NOT_DELIVERED,
        "resolution_note": "cited-not-delivered: request the document before relying on what cites it",
    }


def _merge_gaps(project_id: str, new_gaps: list[dict[str, str]], language: str | None = None) -> list[dict[str, str]]:
    from .discovery import count_gaps, parse_gap_rows, readiness_stage_after_gap_change, render_gaps

    gaps_path = workspace_path(project_id) / "01_discovery" / "gaps.md"
    if not new_gaps or not gaps_path.exists():
        return []
    existing = [gap for gap in parse_gap_rows(gaps_path.read_text(encoding="utf-8")) if gap.get("id") != "NONE"]
    known = {gap["id"] for gap in existing}
    added = [gap for gap in new_gaps if gap["id"] not in known]
    if not added:
        return []
    req_id = existing[0].get("parent", "REQ-001").strip("`") if existing else "REQ-001"
    if language not in {"es", "en"}:
        state = read_json(workspace_path(project_id) / "state.json", {})
        language = state.get("project_language") if state.get("project_language") in {"es", "en"} else "en"
    all_gaps = existing + added
    write_text(gaps_path, render_gaps(project_id, all_gaps, req_id, language))
    counts = count_gaps(all_gaps)
    update_state(project_id, gap_counts=counts, readiness_stage=readiness_stage_after_gap_change(project_id, counts))
    return added


def scan_source_conflicts(project_id: str, source_id: str, text: str, language: str | None = None) -> dict[str, Any]:
    """Anchor the source's statements, open contradiction / cited-not-delivered gaps."""
    from .sources import load_source_manifest, save_source_manifest
    from .source_registry import ensure_registry, find_row

    manifest = ensure_registry(load_source_manifest(project_id))
    rows = manifest.get("registry", [])
    row = find_row(manifest, source_id) or {"id": source_id}
    authority = row_authority(row)
    unvalidated = declares_unvalidated(text)
    if unvalidated and not row.get("declared_unvalidated") and row.get("id") in {r.get("id") for r in rows}:
        row["declared_unvalidated"] = True
        save_source_manifest(project_id, manifest)
    result: dict[str, Any] = {"source_id": source_id, "echo": authority == "own_artifact", "unvalidated": unvalidated,
                              "facts": 0, "proposals": 0, "contradictions": [], "cited_not_delivered": [], "new_gaps": []}
    if result["echo"]:
        return result  # echo, not authority: Sentinel reading itself adds nothing

    ledger = load_ledger(project_id)
    corpus = _corpus(project_id, ledger)
    proposal_cue = _data()["proposal_cue_pattern"]
    seen = {(s["source_id"], s["line"], s["subject_key"]) for s in ledger["statements"]}
    fresh: list[dict[str, Any]] = []
    for statement in extract_statements(text):
        if (source_id, statement["line"], statement["subject_key"]) in seen:
            continue
        reason = None
        if unvalidated:
            reason = "unvalidated-source"
        elif re.search(proposal_cue, _fold(statement["quote"])):
            reason = "proposal-cue"
        elif new_technical_names(statement["quote"], corpus):
            reason = "new-technical-name"
        statement.update(source_id=source_id, kind=PROPOSAL if reason else FACT, reason=reason)
        fresh.append(statement)
    result["facts"] = sum(1 for s in fresh if s["kind"] == FACT)
    result["proposals"] = sum(1 for s in fresh if s["kind"] == PROPOSAL)

    config = load_config(project_id)
    authorities = {str(r["id"]): row_authority(r) for r in rows}
    authorities.setdefault(source_id, authority)
    by_gap = {item["gap_id"]: item for item in ledger["contradictions"]}
    for statement in (s for s in fresh if s["kind"] == FACT):
        priors = [p for p in ledger["statements"]
                  if p["kind"] == FACT and p["subject_key"] == statement["subject_key"] and p["source_id"] != source_id]
        clashing = [p for p in priors if classify_pair(p, statement) == CONTRADICTION]
        if not clashing:
            continue
        gap_id = f"GAP-CTR-{_short_hash(statement['subject_key'])}"
        item = by_gap.get(gap_id)
        if item is None:
            item = {"gap_id": gap_id, "subject_key": statement["subject_key"], "subject": statement["subject"],
                    "scope": scope_for(statement["subject"]), "statements": []}
            by_gap[gap_id] = item
            ledger["contradictions"].append(item)
        for anchored in clashing + [statement]:
            ref = {k: anchored[k] for k in ("source_id", "line", "quote", "value", "value_key")}
            if ref not in item["statements"]:
                item["statements"].append(ref)
        item["interim"] = _interim(item, authorities, config)
    ledger["statements"].extend(fresh)

    ask_to = row.get("from") or f"whoever delivered {source_id}"
    known_citations = {c["gap_id"] for c in ledger["citations"]}
    for citation in cited_documents(text):
        if _delivered(citation["tokens"], rows, source_id):
            continue
        gap_id = f"GAP-CND-{_short_hash('|'.join(sorted(set(citation['tokens']))))}"
        if gap_id in known_citations:
            continue
        item = {"gap_id": gap_id, "cited": citation["cited"], "source_id": source_id, "line": citation["line"],
                "quote": citation["quote"], "ask_to": ask_to}
        ledger["citations"].append(item)
        known_citations.add(gap_id)

    write_json(_ledger_path(project_id), ledger)
    # Every ledger topic, not only this run's: a re-ingest rewrites gaps.md, and a gap
    # already present (open or closed) is never duplicated or reopened.
    added = _merge_gaps(project_id, [_contradiction_gap(item) for item in ledger["contradictions"]]
                        + [_citation_gap(item) for item in ledger["citations"]], language)
    result["new_gaps"] = added
    result["contradictions"] = [gap["id"] for gap in added if gap["origin"] == ORIGIN_CONTRADICTION]
    result["cited_not_delivered"] = [gap["id"] for gap in added if gap["origin"] == ORIGIN_CITED_NOT_DELIVERED]
    write_text(workspace_path(project_id) / REPORT_FILE, render_conflicts_report(project_id, ledger))
    return result


# --- render --------------------------------------------------------------------


def render_conflicts_report(project_id: str, ledger: dict[str, Any]) -> str:
    lines = [
        f"# Contradictions and proposals - {project_id}",
        "",
        "Generated by IMP-251 from `01_discovery/statement_ledger.json`. Both sides of a contradiction stay",
        "anchored; nothing here picks a winner. A subject a source does not mention is source silence, not a",
        "contradiction.",
        "",
        "## Contradictions",
        "",
    ]
    if not ledger["contradictions"]:
        lines.append("- None.")
    for item in ledger["contradictions"]:
        interim = item.get("interim") or {}
        lines.append(f"### `{item['gap_id']}` - {item['subject']} ({item['scope']})")
        lines.append("")
        for anchored in item["statements"]:
            lines.append(f"- `{anchored['source_id']}` line {anchored['line']}: \"{anchored['quote']}\"")
        if interim.get("status") == "resolved":
            lines.append(f"- Interim value {interim['mark']}: \"{interim['value']}\" from `{interim['source_id']}` "
                         f"({', '.join(interim['rules'])}), until the gap closes.")
        else:
            lines.append("- Interim value: none. No precedence rule settles it; a person decides.")
        lines.append("")
    lines += ["## Proposals (not facts)", ""]
    proposals = [s for s in ledger["statements"] if s["kind"] == PROPOSAL]
    if not proposals:
        lines.append("- None.")
    for statement in proposals:
        lines.append(f"- `{statement['source_id']}` line {statement['line']} ({statement['reason']}): \"{statement['quote']}\"")
    lines += ["", "## Cited, never delivered", ""]
    if not ledger["citations"]:
        lines.append("- None.")
    for item in ledger["citations"]:
        lines.append(f"- `{item['gap_id']}`: `{item['source_id']}` line {item['line']} cites \"{item['cited']}\"; ask {item['ask_to']}.")
    return "\n".join(lines) + "\n"


__all__ = [
    "AGREE", "CONTRADICTION", "SILENCE", "ECHO_SOURCE_NOTE", "UNVALIDATED_SOURCE_NOTE", "SCOPES",
    "classify_pair", "closing_block_note", "cited_documents", "declares_unvalidated", "extract_statements",
    "load_ledger", "new_technical_names", "render_conflicts_report", "scan_source_conflicts", "scope_for",
]
