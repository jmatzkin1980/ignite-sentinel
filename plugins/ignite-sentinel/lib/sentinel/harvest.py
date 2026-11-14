"""IMP-262: brownfield harvest into the brief v2.

An agent reads the existing system's code (the `sentinel-brownfield-harvest`
skill, local only) and writes a tagged Markdown harvest, by blocks:

    ## B0 Inventory
    - repo: billing-api — services/billing
    ## B1 Architecture and components
    - [HECHO billing-api:src/app.py] The API is a Flask app with three blueprints.
    - [INFERIDO] Jobs run hourly, because the scheduler config names "hourly".
    - [NO ENCONTRADO src/config/] No timeout is set for the ledger client.
    - [FUERA DEL CÓDIGO owners] Who owns the ledger integration.
    - [DIVERGENCIA billing-api:README.md] README says v2 API; code serves v1 routes.

Tags are accepted in Spanish or English: HECHO/FACT, INFERIDO/INFERRED,
NO ENCONTRADO/NOT FOUND, FUERA DEL CÓDIGO/OUT OF CODE, DIVERGENCIA/DIVERGENCE.

The runtime:
- validates the tags. A fact names `repo:file` with a repo from B0. A "not found"
  says where it should be. "Out of code" uses a topic of the closed list. A
  divergence names `repo:file`;
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
_BLOCK_RE = re.compile(r"^#{2,3}\s*(?P<block>B[0-5])\b")
_REPO_RE = re.compile(r"^\s*[-*]\s*repo\s*:\s*(?P<name>[\w.\-/]+)", re.I)


class HarvestError(InputError):
    pass


def parse_harvest(text: str) -> dict[str, Any]:
    """Repos of B0, tagged entries with their block, and the errors found. Pure."""
    repos: list[str] = []
    entries: list[dict[str, str]] = []
    errors: list[str] = []
    block = ""
    for number, line in enumerate(text.splitlines(), start=1):
        heading = _BLOCK_RE.match(line)
        if heading:
            block = heading.group("block")
            continue
        repo = _REPO_RE.match(line)
        if repo and block == "B0":
            repos.append(repo.group("name"))
            continue
        match = _TAG_RE.match(line)
        if not match:
            continue
        kind = TAGS.get(match.group("tag").strip().upper())
        if kind is None:
            errors.append(f"line {number}: unknown tag [{match.group('tag')}]")
            continue
        if not block:
            errors.append(f"line {number}: a tagged line outside any block B0-B5")
            continue
        entries.append({"line": str(number), "block": block, "kind": kind,
                        "ref": (match.group("ref") or "").strip(), "text": match.group("text").strip()})
    for entry in entries:
        ref, kind, where = entry["ref"], entry["kind"], f"line {entry['line']}"
        if kind in {"fact", "divergence"}:
            repo, _, path = ref.partition(":")
            if not repo or not path:
                errors.append(f"{where}: [{kind}] needs `repo:file`")
            elif repo not in repos:
                errors.append(f"{where}: repo {repo!r} is not in the B0 inventory")
        elif kind == "not_found" and not ref:
            errors.append(f"{where}: [not found] says where it should be")
        elif kind == "out_of_code" and ref.lower() not in OUT_OF_CODE_TOPICS:
            errors.append(f"{where}: out-of-code topic must be one of {', '.join(sorted(OUT_OF_CODE_TOPICS))}")
    if not repos:
        errors.append("B0 lists no repository (`- repo: name — path`)")
    coverage = {kind: sum(1 for e in entries if e["kind"] == kind) for kind in ("fact", "inferred", "not_found", "out_of_code", "divergence")}
    return {"repos": repos, "entries": entries, "errors": errors, "coverage": coverage}


def _gap(entry: dict[str, str], language: str) -> dict[str, str] | None:
    digest = hashlib.sha256(f"{entry['kind']}|{entry['ref']}|{entry['text']}".encode("utf-8")).hexdigest()[:8].upper()
    es = language == "es"
    if entry["kind"] == "out_of_code":
        return {"id": f"GAP-HRV-{digest}", "lens": "technical", "severity": "low", "status": "OPEN", "kind": "domain",
                "description": f"Out of code ({entry['ref']}): {entry['text']}"[:240],
                "question": (f"¿Quién confirma: {entry['text']}?" if es else f"Who confirms: {entry['text']}?"),
                "evidence_mention": f"harvest {entry['block']}", "origin": "harvest", "resolution_note": ""}
    if entry["kind"] == "divergence":
        return {"id": f"GAP-HRV-{digest}", "lens": "technical", "severity": "high", "status": "OPEN",
                "description": f"⚠ README vs code divergence ({entry['ref']}): {entry['text']}"[:240],
                "question": ("¿Cuál rige: lo documentado o lo construido?" if es else "Which governs: what is documented or what is built?"),
                "evidence_mention": entry["ref"], "origin": "harvest", "resolution_note": ""}
    return None


def apply_harvest(project_id: str, source: Path) -> dict[str, Any]:
    from .core.io import write_json, write_text
    from .discovery import count_gaps, parse_gap_rows, readiness_stage_after_gap_change, render_gaps
    from .gaps import merge_gaps_by_topic
    from .secrets_scan import sanitize_text
    from .sources import mark_source_processed, open_source_row
    from .workspace import read_state, update_state, workspace_path

    base = workspace_path(project_id)
    if not base.exists():
        raise HarvestError(f"Workspace not found: {project_id}")
    raw = source.read_text(encoding="utf-8")
    parsed = parse_harvest(raw)
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
    record = {"artifact": "harvest", "source_id": source_id, "direction": "built", "repos": parsed["repos"],
              "coverage": parsed["coverage"], "entries": parsed["entries"], "secrets_redacted": len(sanitized.findings)}
    write_json(base / "01_discovery" / "harvest.json", record)
    gaps = [g for g in (_gap(e, language) for e in parsed["entries"]) if g]
    gaps_path = base / "01_discovery" / "gaps.md"
    opened: list[str] = []
    if gaps and gaps_path.exists():
        existing = [g for g in parse_gap_rows(gaps_path.read_text(encoding="utf-8")) if g.get("id") != "NONE"]
        merged = merge_gaps_by_topic(existing, gaps)
        opened = [g["id"] for g in merged["added"]]
        req_id = existing[0].get("parent", "REQ-001").strip("`") if existing else "REQ-001"
        write_text(gaps_path, render_gaps(project_id, merged["gaps"], req_id, language))
        counts = count_gaps(merged["gaps"])
        update_state(project_id, gap_counts=counts, readiness_stage=readiness_stage_after_gap_change(project_id, counts))
    return {"project_id": project_id, "source_id": source_id, "repos": parsed["repos"], "coverage": parsed["coverage"],
            "gaps_opened": opened, "secrets_redacted": len(sanitized.findings), "path": str(target.as_posix())}


def load_harvest(base: Path) -> dict[str, Any]:
    from .core.io import read_json

    data = read_json(base / "01_discovery" / "harvest.json", {}) or {}
    return data if isinstance(data, dict) else {}
