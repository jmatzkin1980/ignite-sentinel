"""IMP-262: brownfield harvest into the brief v2.

An agent reads the existing system's code (the `sentinel-brownfield-harvest`
skill, local only) and writes a tagged Markdown harvest, by blocks:

    ## B0 Inventory
    - repo: billing-api — services/billing
    - doc: manual-compras — 00_raw/01_business_context/manual-compras.md
    ## B1 Architecture and components
    - [HECHO billing-api:src/app.py] The API is a Flask app with three blueprints.
    - [INFERIDO] Jobs run hourly, because the scheduler config names "hourly".
    - [NO ENCONTRADO src/config/] No timeout is set for the ledger client.
    - [FUERA DEL CÓDIGO owners] Who owns the ledger integration.
    - [DIVERGENCIA billing-api:README.md] README says v2 API; code serves v1 routes.

Tags are accepted in Spanish or English: HECHO/FACT, INFERIDO/INFERRED,
NO ENCONTRADO/NOT FOUND, FUERA DEL CÓDIGO/OUT OF CODE, DIVERGENCIA/DIVERGENCE.

The runtime:
- validates the tags. A fact names `name:file` with a repo or a doc from B0 (IMP-384:
  `- doc: name — path` inventories a document; B0 needs at least one repo or one doc;
  B6 screens, B7 flows and B8 rules and roles are functional blocks read from documents
  and feed no brief place). A "not found"
  says where it should be. "Out of code" uses a topic of the closed list. A
  divergence names `name:file`;
- redacts secrets (IMP-285) and stores the harvest under
  `00_raw/02_technology_context/harvest/` as a governed F-NN row (`built`);
- routes "out of code" to the domain (a non-blocking gap: never ask the code
  again) and opens a high gap for each README/code divergence;
- writes `01_discovery/harvest.json`, which the brief v2 compiler reads: facts
  feed §5 by block, inferences become `(inferred)` lines with ledger rows, and §0.2
  shows the repository inventory and the coverage per tag.
"""
from __future__ import annotations

from .errors import InputError  # IMP-302: typed errors

import hashlib
import re
from pathlib import Path
from typing import Any
from .gaps import count_gaps, merge_gaps_by_topic, parse_gap_rows, readiness_stage_after_gap_change, render_gaps

TAGS = {
    "HECHO": "fact", "FACT": "fact",
    "INFERIDO": "inferred", "INFERRED": "inferred",
    "NO ENCONTRADO": "not_found", "NOT FOUND": "not_found",
    "FUERA DEL CÓDIGO": "out_of_code", "FUERA DEL CODIGO": "out_of_code", "OUT OF CODE": "out_of_code",
    "DIVERGENCIA": "divergence", "DIVERGENCE": "divergence",
}
OUT_OF_CODE_TOPICS = {
    "owners", "sla", "why_without_adr", "volume", "purpose_and_retention", "regulation", "negotiability",
    "role_administration", "flag_removal_date", "latency_targets",
}
# block -> brief v2 place a fact of that block feeds
BLOCK_PLACES = {"B0": "5.1", "B1": "5.1", "B2": "5.4", "B3": "5.6", "B4": "5.11", "B5": "5.16"}
# Known tags first (longest first, so "NO ENCONTRADO" is not read as "NO"); any other
# bracketed word is captured as an unknown tag.
_KNOWN = "|".join(re.escape(tag) for tag in sorted(TAGS, key=len, reverse=True))
_TAG_RE = re.compile(rf"^\s*[-*]\s*\[(?P<tag>{_KNOWN}|[A-ZÁÉÍÓÚÑ]+)(?:\s+(?P<ref>[^\]]+))?\]\s*(?P<text>.+?)\s*$", re.I)
_BLOCK_RE = re.compile(r"^#{2,3}\s*(?P<block>B[0-8])\b")
_ANY_BLOCK_RE = re.compile(r"^#{2,3}\s*B\d+\b")  # a block heading outside B0-B8 closes the current block
_REPO_RE = re.compile(r"^\s*[-*]\s*repo\s*:\s*(?P<name>[\w.\-/]+)", re.I)
_DOC_RE = re.compile(r"^\s*[-*]\s*doc\s*:\s*(?P<name>[\w.\-/]+)", re.I)


class HarvestError(InputError):
    pass


def parse_harvest(text: str, known_repos: tuple[str, ...] | list[str] = (),
                  known_docs: tuple[str, ...] | list[str] = ()) -> dict[str, Any]:
    """Repos and docs of B0, tagged entries with their block, and the errors found. Pure.

    IMP-326: `known_repos` are the repos an earlier harvest of the project already listed, so
    a later file may deliver B1-B8 without repeating B0 (`known_docs` likewise).
    """
    repos: list[str] = []
    docs: list[str] = []
    entries: list[dict[str, str]] = []
    errors: list[str] = []
    block = ""
    for number, line in enumerate(text.splitlines(), start=1):
        heading = _BLOCK_RE.match(line)
        if heading:
            block = heading.group("block")
            continue
        if _ANY_BLOCK_RE.match(line):
            block = ""
            continue
        repo = _REPO_RE.match(line)
        if repo and block == "B0":
            repos.append(repo.group("name"))
            continue
        doc = _DOC_RE.match(line)
        if doc and block == "B0":
            docs.append(doc.group("name"))
            continue
        match = _TAG_RE.match(line)
        if not match:
            continue
        kind = TAGS.get(match.group("tag").strip().upper())
        if kind is None:
            errors.append(f"line {number}: unknown tag [{match.group('tag')}]")
            continue
        if not block:
            errors.append(f"line {number}: a tagged line outside any block B0-B8")
            continue
        entries.append({"line": str(number), "block": block, "kind": kind,
                        "ref": (match.group("ref") or "").strip(), "text": match.group("text").strip()})
    for entry in entries:
        ref, kind, where = entry["ref"], entry["kind"], f"line {entry['line']}"
        if kind in {"fact", "divergence"}:
            repo, _, path = ref.partition(":")
            if not repo or not path:
                errors.append(f"{where}: [{kind}] needs `repo:file` or `doc:file`")
            elif repo not in repos and repo not in known_repos and repo not in docs and repo not in known_docs:
                errors.append(f"{where}: repo or doc {repo!r} is not in the B0 inventory")
        elif kind == "not_found" and not ref:
            errors.append(f"{where}: [not found] says where it should be")
        elif kind == "out_of_code" and ref.lower() not in OUT_OF_CODE_TOPICS:
            errors.append(f"{where}: out-of-code topic must be one of {', '.join(sorted(OUT_OF_CODE_TOPICS))}")
    if not repos and not known_repos and not docs and not known_docs:
        errors.append("B0 lists no repository or document (`- repo: name — path` or `- doc: name — path`)")
    coverage = {kind: sum(1 for e in entries if e["kind"] == kind) for kind in ("fact", "inferred", "not_found", "out_of_code", "divergence")}
    return {"repos": repos, "docs": docs, "entries": entries, "errors": errors, "coverage": coverage}


def _gap(entry: dict[str, str], language: str, change: bool = False) -> dict[str, str] | None:
    digest = hashlib.sha256(f"{entry['kind']}|{entry['ref']}|{entry['text']}".encode("utf-8")).hexdigest()[:8].upper()
    es = language == "es"
    if entry["kind"] == "out_of_code":
        return {"id": f"GAP-HRV-{digest}", "lens": "technical", "severity": "low", "status": "OPEN", "kind": "domain",
                "description": f"Out of code ({entry['ref']}): {entry['text']}"[:240],
                "question": (f"¿Quién confirma: {entry['text']}?" if es else f"Who confirms: {entry['text']}?"),
                "evidence_mention": f"harvest {entry['block']}", "origin": "harvest", "resolution_note": ""}
    if entry["kind"] == "divergence":
        if change:  # IMP-398: the change harvest speaks the change language and offers "build or fix it in this change"
            description = (f"⚠ Divergencia entre lo documentado y lo construido ({entry['ref']}): {entry['text']}" if es
                           else f"⚠ Divergence between what is documented and what is built ({entry['ref']}): {entry['text']}")
            question = ("¿Qué rige: lo construido, lo que dice el pedido, o hay que construirlo o corregirlo en este cambio?" if es
                        else "Which governs: what is built, what the request says, or does it have to be built or fixed in this change?")
        else:
            description = f"⚠ README vs code divergence ({entry['ref']}): {entry['text']}"
            question = "¿Cuál rige: lo documentado o lo construido?" if es else "Which governs: what is documented or what is built?"
        return {"id": f"GAP-HRV-{digest}", "lens": "technical", "severity": "high", "status": "OPEN",
                "description": description[:240],
                "question": question,
                "evidence_mention": entry["ref"], "origin": "harvest", "resolution_note": ""}
    return None


def apply_harvest(project_id: str, source: Path, change_id: str | None = None) -> dict[str, Any]:
    from .core.io import write_json, write_text
    from .secrets_scan import sanitize_text
    from .sources import mark_source_processed, open_source_row
    from .workspace import read_state, update_state, workspace_path

    base = workspace_path(project_id)
    if not base.exists():
        raise HarvestError(f"Workspace not found: {project_id}")
    # IMP-384: where the harvest's gaps go is settled before anything is written. The harvest
    # itself (harvest.json, the raw copy) belongs to the workspace: the baseline is shared.
    change = None
    if change_id:
        from .changes import get_change

        change = get_change(project_id, change_id)
    elif not (base / "01_discovery" / "gaps.md").exists():
        from .changes import list_changes
        from .core.text import project_language
        from .errors import GateRefusal

        open_changes = sorted(list_changes(project_id))
        if open_changes:
            raise GateRefusal(
                (f"{project_id} sólo tiene cambios: los gaps del harvest necesitan un cambio"
                 if project_language(project_id) == "es"
                 else f"{project_id} only has changes: the harvest gaps need a change"),
                next_step=f"/harvest {project_id} --source {source} --change {open_changes[0]}",
            )
    raw = source.read_text(encoding="utf-8")
    previous = load_harvest(base)
    previous_repos = [str(repo) for repo in previous.get("repos", [])]
    previous_docs = [str(doc) for doc in previous.get("docs", [])]
    # IMP-336: parse the redacted text, so harvest.json entries never carry a secret
    # (alerts are recorded below, once the harvest is accepted).
    from .secrets_scan import detect_secrets, load_allowlist, redact

    parsed = parse_harvest(redact(raw, detect_secrets(raw, load_allowlist(base))), previous_repos, previous_docs)
    if parsed["errors"]:
        raise HarvestError("Harvest rejected:\n- " + "\n- ".join(parsed["errors"]))
    source_id = open_source_row(project_id, source, "harvested")
    target = base / "00_raw" / "02_technology_context" / "harvest" / source.name
    sanitized = sanitize_text(base, source.name, raw)
    write_text(target, sanitized.text)
    source_id = mark_source_processed(project_id, source, "harvested", source_id=source_id) or source_id
    mark_source_processed(project_id, target, "raw_copy", source_id=source_id)
    state = read_state(project_id, {})
    language = state.get("project_language") if state.get("project_language") in {"es", "en"} else "en"
    # IMP-326: a harvest delivered block by block accumulates. The blocks this file brings
    # replace the same blocks of earlier harvests (a re-delivery corrects them); the other
    # blocks are kept. It used to overwrite harvest.json, so a second run lost the first.
    delivered = {entry["block"] for entry in parsed["entries"]}
    for entry in parsed["entries"]:
        entry["source_id"] = source_id
    kept = [entry for entry in previous.get("entries", []) if entry.get("block") not in delivered]
    entries = sorted([*kept, *parsed["entries"]], key=lambda entry: (entry.get("block", ""), int(entry.get("line", 0) or 0)))
    repos = list(dict.fromkeys([*previous_repos, *parsed["repos"]]))
    docs = list(dict.fromkeys([*previous_docs, *parsed["docs"]]))
    coverage = {kind: sum(1 for e in entries if e["kind"] == kind) for kind in parsed["coverage"]}
    sources = list(dict.fromkeys([*previous.get("source_ids", [previous.get("source_id")] if previous.get("source_id") else []), source_id]))
    record = {"artifact": "harvest", "source_id": source_id, "source_ids": sources, "direction": "built", "repos": repos,
              **({"docs": docs} if docs else {}),
              "coverage": coverage, "entries": entries,
              "secrets_redacted": int(previous.get("secrets_redacted", 0) or 0) + len(sanitized.findings)}
    write_json(base / "01_discovery" / "harvest.json", record)
    if change is not None:
        from .changes import change_language

        language = change_language(project_id, change)
    gaps = [g for g in (_gap(e, language, change is not None) for e in parsed["entries"]) if g]
    gaps_path = base / "01_discovery" / "gaps.md"
    opened: list[str] = []
    if change is not None:
        from .changes import change_gaps_path, list_changes

        changes = {key: dict(value) for key, value in list_changes(project_id).items()}
        if gaps:
            change_path = change_gaps_path(base, str(change_id))
            existing = [g for g in parse_gap_rows(change_path.read_text(encoding="utf-8")) if g.get("id") != "NONE"] if change_path.exists() else []
            merged = merge_gaps_by_topic(existing, gaps)
            opened = [g["id"] for g in merged["added"]]
            write_text(change_path, render_gaps(project_id, merged["gaps"], str(change_id), language,
                                                change_path.with_name("gap_elicitation.json")))
            changes[str(change_id)]["gap_counts"] = count_gaps(merged["gaps"])
        # IMP-404: the change's harvest is its baseline cross, even when it opens no question.
        harvests = [str(i) for i in changes[str(change_id)].get("harvests") or []]
        if str(source_id) not in harvests:
            harvests.append(str(source_id))
        changes[str(change_id)]["harvests"] = harvests
        update_state(project_id, changes=changes)
        from .crosses.state import write_cross_report

        write_cross_report(project_id, str(change_id))
        from .decision_memory import index_change_decisions

        index_change_decisions(project_id, str(change_id))  # IMP-410
    elif gaps and gaps_path.exists():
        existing = [g for g in parse_gap_rows(gaps_path.read_text(encoding="utf-8")) if g.get("id") != "NONE"]
        merged = merge_gaps_by_topic(existing, gaps)
        opened = [g["id"] for g in merged["added"]]
        req_id = existing[0].get("parent", "REQ-001").strip("`") if existing else "REQ-001"
        write_text(gaps_path, render_gaps(project_id, merged["gaps"], req_id, language))
        counts = count_gaps(merged["gaps"])
        update_state(project_id, gap_counts=counts, readiness_stage=readiness_stage_after_gap_change(project_id, counts))
    result = {"project_id": project_id, "source_id": source_id, "repos": repos, "docs": docs, "coverage": coverage,
              "blocks_delivered": sorted(delivered), "blocks_total": sorted({e["block"] for e in entries}),
              "gaps_opened": opened, "secrets_redacted": len(sanitized.findings), "path": str(target.as_posix())}
    if change_id:
        result["change_id"] = change_id
    return result


def load_harvest(base: Path) -> dict[str, Any]:
    from .core.io import read_json

    data = read_json(base / "01_discovery" / "harvest.json", {}) or {}
    return data if isinstance(data, dict) else {}
