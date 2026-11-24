"""IMP-410 (H27 inc 3): the decisions of a change are indexed in memory, one document each.

Memory indexes files and graph nodes, but a decision lives inside a row of `gaps.md`, of the
state and of a JSON record. Here each closed question, the border, each registered cross-read,
each decided surface, the cross report and the coherence report become a document with its own
`trace_ids`, so a later question can retrieve what was already decided.
"""
from __future__ import annotations

import re
from pathlib import Path

from .memory import ContextBroker

DECISION_TYPES = ("change_decision", "change_border", "change_cross", "change_cross_report", "change_coherence")
_FNN = re.compile(r"\bF-\d+\b")
_NA = {"", "n/a", "na", "-"}
_LENS_DOMAINS = ("business", "product", "design", "technical")


def decision_id(change_id: str, item_id: str) -> str:
    return f"DECISION-{change_id}-{item_id}"


def _squash(text: object) -> str:
    return " ".join(str(text or "").split())


def _value(raw: object) -> str:
    text = str(raw or "").strip().strip("`").strip()
    return "" if text.lower() in _NA else text


def _quotes(language: str) -> tuple[str, str]:
    return ("«", "»") if language == "es" else ("“", "”")


def _pedido_elements(project_id: str, change_id: str) -> list[dict]:
    from .extraction.inventory import _read_text, _row_path, parse_request_elements, pedido_rows
    from .workspace import workspace_path

    base = workspace_path(project_id)
    found: list[dict] = []
    for row in pedido_rows(project_id, change_id):
        path = _row_path(row)
        text = _read_text(base, path)
        if text is not None:
            found.extend(parse_request_elements(text, str(row["id"]), path))
    return found


def _cross_claims(project_id: str, change_id: str) -> list[tuple[str, dict]]:
    from .crosses import CROSS_KINDS
    from .crosses.record import load_cross
    from .workspace import workspace_path

    base = workspace_path(project_id)
    out: list[tuple[str, dict]] = []
    for kind in CROSS_KINDS:
        record = load_cross(base, change_id, kind)
        if record and record.get("status") == "done":
            out.extend((kind, claim) for claim in record.get("claims", []) if isinstance(claim, dict))
    return out


def _coherence_claims(project_id: str, change_id: str) -> list[tuple[str, dict]]:
    """The recorded semantic crosses of the lens view, shaped like claims: their quotes located in the request."""
    from .change_coherence import coherence_citations, coherence_dir
    from .core.io import read_json
    from .workspace import workspace_path

    record = read_json(coherence_dir(workspace_path(project_id), change_id) / "coherence.json", None)
    if not isinstance(record, dict) or record.get("status") != "done":
        return []
    texts: dict = {}
    return [("coherence", {"gap": cross["gap"], "text": "",
                           "citations": coherence_citations(project_id, change_id, cross, texts)})
            for cross in record.get("crosses") or [] if isinstance(cross, dict) and cross.get("gap")]


def closed_decisions(project_id: str, change_id: str) -> list[dict]:
    """The closed questions of a change that someone decided (not the ones a re-recording withdrew)."""
    from .changes import change_gaps_path, get_change
    from .compilers.change_brief import _answers
    from .crosses.record import RETIRE_NOTE
    from .extraction.inventory import element_lines, match_element_id
    from .gap_resolution import normalize_option
    from .gaps import parse_gap_rows
    from .prior_decisions import load_priors
    from .workspace import workspace_path

    base = workspace_path(project_id)
    change = get_change(project_id, change_id)
    path = change_gaps_path(base, change_id)
    if not path.exists():
        return []
    retired = set(RETIRE_NOTE.values())
    answers = _answers(base, change)
    priors = load_priors(base, change_id)
    claims = [*_cross_claims(project_id, change_id), *_coherence_claims(project_id, change_id)]
    elements = _pedido_elements(project_id, change_id)
    out: list[dict] = []
    for row in parse_gap_rows(path.read_text(encoding="utf-8-sig")):
        gap_id = str(row.get("id", "")).strip()
        if gap_id in ("", "NONE") or str(row.get("status", "")).strip("`").strip().upper() != "CLOSED":
            continue
        note = str(row.get("resolution_note", "")).strip()
        if note in retired:
            continue
        entry = priors.get(gap_id)
        response = answers.get(gap_id) or (
            {"answer": entry["answer"], "option": entry.get("option", "")} if entry and entry.get("accepted_at") else {})
        option = str(response.get("option", "")).strip()
        citations: list[dict] = []
        element_ids: list[str] = []
        for _kind, claim in claims:
            if claim.get("gap") != gap_id:
                continue
            for cite in claim.get("citations", []):
                item = {"source_id": str(cite.get("source_id", "")), "line": cite.get("line"),
                        "quote": _squash(cite.get("quote")), "side": str(cite.get("side", ""))}
                citations.append(item)
                if item["side"] == "pedido" and item["line"]:
                    for element in elements:
                        first, last = element_lines(element)
                        if element["source_id"] == item["source_id"] and first <= int(item["line"]) <= last:
                            element_ids.append(str(element["id"]))
            found = match_element_id(str(claim.get("text", "")))
            if found:
                element_ids.append(found[0])
        evidence = str(response.get("evidence", "")).strip()
        sources = [c["source_id"] for c in citations if c["source_id"]] + _FNN.findall(evidence)
        out.append({
            "id": gap_id,
            "lens": str(row.get("lens", "")).strip(),
            "question": _squash(row.get("question")),
            "answer": str(response.get("answer", "")).strip() or note,
            "option": normalize_option(option) if option else "",
            "owner": str(response.get("owner", "")).strip(),
            "evidence": evidence,
            "closure": _value(row.get("closure_reason")),
            "citations": citations,
            "elements": list(dict.fromkeys(element_ids)),
            "sources": list(dict.fromkeys(sources)),
        })
    return out


_LABELS = {
    "es": {"decision": "decisión de", "question": "Pregunta", "answer": "Respuesta", "option": "Opción",
           "owner": "Decidido por", "evidence": "Evidencia", "closure": "Cierre", "quotes": "Citas"},
    "en": {"decision": "decision of", "question": "Question", "answer": "Answer", "option": "Option",
           "owner": "Decided by", "evidence": "Evidence", "closure": "Closure", "quotes": "Quotes"},
}


def _cite_line(cite: dict, language: str, indent: str = "  ") -> str:
    opening, closing = _quotes(language)
    where = f"{cite['source_id']}:{cite['line']}" if cite.get("line") else str(cite["source_id"])
    return f"{indent}- {where} {opening}{cite['quote']}{closing}"


def render_decision(item: dict, change_id: str, language: str) -> str:
    lang = "es" if language == "es" else "en"
    t = _LABELS[lang]
    lines = [f"# {item['id']} — {t['decision']} {change_id}", "",
             f"- {t['question']}: {item['question']}",
             f"- {t['answer']}: {item['answer']}"]
    if item.get("option"):
        lines.append(f"- {t['option']}: {item['option']}")
    lines.append(f"- {t['owner']}: {item['owner']}")
    lines.append(f"- {t['evidence']}: {item['evidence']}")
    if item.get("closure"):
        lines.append(f"- {t['closure']}: {item['closure']}")
    if item.get("citations"):
        lines.append(f"- {t['quotes']}:")
        lines.extend(_cite_line(c, lang) for c in item["citations"])
    return "\n".join(lines) + "\n"


def _border_text(change: dict, change_id: str, language: str) -> str:
    title = f"# Borde de {change_id}" if language == "es" else f"# Border of {change_id}"
    lines = [title, ""]
    for item in change.get("border") or []:
        lines.append(f"- {item.get('zone', '')} | {item.get('type', '')} | {item.get('name', '')}")
    return "\n".join(lines) + "\n"


def _cross_text(kind: str, record: dict, change_id: str, language: str) -> str:
    from .crosses.claims import TAG_NAMES
    from .crosses.state import KIND_LABELS

    names = TAG_NAMES[language]
    head = (f"# Cruce {KIND_LABELS[language][kind]} de {change_id}" if language == "es"
            else f"# Cross-read {KIND_LABELS[language][kind]} of {change_id}")
    lines = [head, ""]
    for claim in record.get("claims", []):
        tail = f" ({claim['gap']})" if claim.get("gap") else ""
        lines.append(f"- [{names[claim['tag']]}] {_squash(claim['text'])}{tail}")
        for cite in claim.get("citations", []):
            lines.append(_cite_line({"source_id": cite.get("source_id", ""), "line": cite.get("line"),
                                     "quote": _squash(cite.get("quote"))}, language))
    return "\n".join(lines) + "\n"


def _surface_text(candidate: str, decision: dict, change_id: str, language: str) -> str:
    es = language == "es"
    accepted = decision.get("decision") == "accepted"
    verb = ("acepta" if accepted else "descarta") if es else ("accepts" if accepted else "declines")
    head = f"# {candidate} — superficie de {change_id}" if es else f"# {candidate} — surface of {change_id}"
    lines = [head, "", f"- {'Decisión' if es else 'Decision'}: {verb}"]
    if decision.get("type"):
        lines.append(f"- {'Tipo' if es else 'Type'}: {decision['type']}")
    if decision.get("name"):
        lines.append(f"- {'Nombre' if es else 'Name'}: {decision['name']}")
    if decision.get("reason"):
        lines.append(f"- {'Motivo' if es else 'Reason'}: {decision['reason']}")
    return "\n".join(lines) + "\n"


def _index_change(project_id: str, change_id: str, broker: ContextBroker, full: bool) -> tuple[list[str], list[str], set[str]]:
    from .changes import change_gaps_path, change_language, get_change
    from .crosses import CROSS_KINDS, cross_path, crosses_dir
    from .crosses.record import load_cross
    from .workspace import workspace_path

    base = workspace_path(project_id)
    change = get_change(project_id, change_id)
    language = "es" if change_language(project_id, change) == "es" else "en"
    gaps_path = change_gaps_path(base, change_id)
    indexed: list[str] = []
    skipped: list[str] = []
    wanted: set[str] = set()

    def put(item_id: str, kind: str, source: Path, text: str, trace: list[str], domain: str = "product") -> None:
        artifact_id = decision_id(change_id, item_id)
        wanted.add(artifact_id)
        trace_ids = list(dict.fromkeys([change_id, *trace]))
        title = text.splitlines()[0].lstrip("# ").strip() if text else artifact_id
        done = broker.index_artifact(
            artifact_id, kind, source, text, domain=domain, trace_ids=trace_ids, title=title,
            metadata={"language": language, "change_id": change_id}, skip_unchanged=not full)
        (indexed if done else skipped).append(artifact_id)

    for item in closed_decisions(project_id, change_id):
        put(item["id"], "change_decision", gaps_path, render_decision(item, change_id, language),
            [item["id"], *item["sources"], *item["elements"]],
            domain=item["lens"] if item["lens"] in _LENS_DOMAINS else "product")
    if change.get("border"):
        put("BORDER", "change_border", gaps_path, _border_text(change, change_id, language), ["GAP-SCOPE"])
    for kind in CROSS_KINDS:
        record = load_cross(base, change_id, kind)
        if record and record.get("status") == "done":
            cites = [str(c.get("source_id", "")) for claim in record.get("claims", []) for c in claim.get("citations", [])]
            gaps = [str(g) for g in record.get("gaps") or []]
            put(f"CROSS-{kind}", "change_cross", cross_path(base, change_id, kind),
                _cross_text(kind, record, change_id, language), [*gaps, *[c for c in cites if c]])
    report = crosses_dir(base, change_id) / "crosses.md"
    if report.is_file():
        put("CROSSES", "change_cross_report", report, report.read_text(encoding="utf-8"), [])
    for candidate, decision in sorted((change.get("new_surfaces") or {}).items()):
        if isinstance(decision, dict) and decision.get("decision") in ("accepted", "declined"):
            put(f"SURFACE-{candidate}", "change_border", gaps_path,
                _surface_text(str(candidate), decision, change_id, language), [str(candidate)])
    coherence = base / "01_discovery" / change_id / "coherence" / "coherence.md"
    if coherence.is_file():
        put("COHERENCE", "change_coherence", coherence, coherence.read_text(encoding="utf-8"), [])
    return indexed, skipped, wanted


def index_change_decisions(project_id: str, change_id: str | None = None, broker: ContextBroker | None = None,
                           full: bool = False) -> dict[str, list[str]]:
    """Index the decisions of one change (or of every change) and forget the ones that no longer stand."""
    from .changes import list_changes

    broker = broker or ContextBroker(project_id)
    changes = [change_id] if change_id else sorted(list_changes(project_id))
    indexed: list[str] = []
    skipped: list[str] = []
    wanted: set[str] = set()
    with broker.deferred_saves():
        for current in changes:
            done, same, keep = _index_change(project_id, current, broker, full)
            indexed += done
            skipped += same
            wanted |= keep
        prefixes = tuple(f"DECISION-{current}-" for current in changes)
        stale = {
            str(a["artifact_id"]) for a in broker.data.get("artifacts", [])
            if str(a["artifact_id"]).startswith("DECISION-" if change_id is None else prefixes)
            and a["artifact_id"] not in wanted
        }
        removed = broker.forget_artifacts(stale) if stale else []
    return {"indexed": indexed, "skipped": skipped, "removed": removed}
