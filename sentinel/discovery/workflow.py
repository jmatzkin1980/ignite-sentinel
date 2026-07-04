from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

from ..lens_registry import known_lenses, load_lens_checks, load_smell_catalog
from ..domain_context import respondent_profile_from_domain_context
from ..technique_registry import default_challenge_technique_ids, default_technique_summary, technique_label, technique_prompt
from ..core.graph import add_edge, add_node, load_graph, upsert_node
from ..core.io import append_text, read_json
from ..core.markdown import parse_table_rows
from ..gaps import parse_gap_table
from ..knowledge.ledger import materialize_knowledge_ledger
from ..memory import ContextBroker, index_context_folders
from ..sources import mark_source_processed
from ..workspace import ensure_workspace, load_config, update_state, workspace_path

METRIC_RE = re.compile(
    r"(\d+(?:[.,]\d+)?\s?(?:%|percent|por ciento|porcentaje)|\$\s?\d+|\d+\s?(?:usd|ars|eur|hours|horas|days|dias))",
    re.I,
)
RAW_SYNTHESIS_EXTENSIONS = {".md", ".txt", ".html", ".htm"}


def ingest(project_id: str, source: Path) -> dict[str, str]:
    ensure_workspace(project_id)
    base = workspace_path(project_id)
    # IMP-150: snapshot the previous Requirement Units before this ingest
    # overwrites them, so a re-ingest can emit a governed ADDED/MODIFIED/REMOVED
    # delta view of what capabilities changed.
    previous_requirement_units = requirement_unit_snapshot(base)
    text = source.read_text(encoding="utf-8")
    language = resolve_project_language(load_config(project_id).get("project_language", "auto"), text)
    context = load_domain_context(base)
    raw_target = base / "00_raw" / f"{source.stem}{source.suffix.lower() if source.suffix.lower() in {'.md', '.txt', '.html', '.htm'} else '.md'}"
    shutil.copyfile(source, raw_target)
    mark_source_processed(project_id, source, "initial_ingested")
    mark_source_processed(project_id, raw_target, "raw_copy")
    raw_id = add_node(project_id, "RAW", "raw_input", raw_target, source.stem, domain="product")
    source_synthesis_path = base / "01_discovery" / "source_synthesis.md"
    source_synthesis_path.write_text(render_source_synthesis(project_id, base), encoding="utf-8")
    requirement_units = extract_requirement_units(text, raw_id, raw_target)
    units_path = base / "01_discovery" / "requirement_units.md"
    units_path.write_text(render_requirement_units(project_id, requirement_units), encoding="utf-8")

    req_text = extract_requirement(text)
    req_path = base / "02_requirements" / "requirements.md"
    req_path.write_text(render_requirement(project_id, req_text, raw_id), encoding="utf-8")
    req_id = add_node(project_id, "REQ", "requirement", req_path, "Primary requirement", domain="product")
    add_edge(project_id, raw_id, req_id, "extracts")
    unit_node_ids: list[str] = []
    for unit in requirement_units:
        unit_id = upsert_node(project_id, unit["id"], "requirement_unit", units_path, unit["label"], domain="product")
        unit["trace_id"] = unit_id
        unit_node_ids.append(unit_id)
        add_edge(project_id, raw_id, unit_id, "decomposes_into")
        add_edge(project_id, unit_id, req_id, "analyzes")
    units_path.write_text(render_requirement_units(project_id, requirement_units), encoding="utf-8")
    # IMP-150: on re-ingest, emit the read-only RU delta view (governed signal only).
    requirement_unit_delta_path = write_requirement_unit_delta(
        project_id, base, previous_requirement_units, requirement_units
    )

    gaps = detect_unit_anchored_gaps(text, context, requirement_units)
    gap_path = base / "01_discovery" / "gaps.md"
    gap_path.write_text(render_gaps(project_id, gaps, req_id, language), encoding="utf-8")
    gap_id = add_node(
        project_id,
        "GAP",
        "gap_report",
        gap_path,
        "Discovery gaps",
        status="open" if gaps else "closed",
        domain="product",
    )
    add_edge(project_id, req_id, gap_id, "has_gap")

    dec_path = base / "01_discovery" / "decisions.md"
    dec_path.write_text(render_decisions(project_id, text, req_id), encoding="utf-8")
    dec_id = add_node(project_id, "DEC", "decision_log", dec_path, "Pending decisions", status="pending")
    add_edge(project_id, req_id, dec_id, "requires_decision")

    digest_path = base / "01_discovery" / "raw_input_digest.md"
    digest_path.write_text(render_digest(project_id, text, raw_id, req_id, gap_id), encoding="utf-8")

    seeds_path = base / "01_discovery" / "identity_seeds.md"
    seeds_path.write_text(render_identity_seeds(project_id, text, raw_id, gaps), encoding="utf-8")
    seed_id = add_node(project_id, "SEED", "identity_seed_bank", seeds_path, "Identity seeds", domain="product")
    add_edge(project_id, raw_id, seed_id, "produces_seed")
    add_edge(project_id, seed_id, req_id, "grounds")

    discovery_log_path = base / "01_discovery" / "discovery_log.md"
    discovery_log_path.write_text(render_discovery_log(project_id, text, raw_id, req_id, gaps, context), encoding="utf-8")
    discovery_log_id = add_node(project_id, "DISC", "discovery_log", discovery_log_path, "Discovery log", domain="product")
    add_edge(project_id, raw_id, discovery_log_id, "analyzed_by")
    add_edge(project_id, discovery_log_id, gap_id, "identifies")

    lens_review_path = base / "01_discovery" / "lens_review.md"
    lens_review_path.write_text(render_lens_review(project_id, text, raw_id, req_id, gaps, context), encoding="utf-8")
    lens_review_id = add_node(project_id, "DISC", "lens_review", lens_review_path, "Multi-lens critical review", domain="product")
    add_edge(project_id, raw_id, lens_review_id, "scrutinized_by")
    add_edge(project_id, lens_review_id, gap_id, "raises")

    ledger = materialize_knowledge_ledger(
        project_id,
        seeds_path.read_text(encoding="utf-8"),
        gaps,
        dec_path.read_text(encoding="utf-8"),
        {
            "raw_input": raw_id,
            "requirement": req_id,
            "gap_report": gap_id,
            "decision_log": dec_id,
            "identity_seed_bank": seed_id,
            "lens_review": lens_review_id,
        },
    )
    ledger_md_path = ledger["md_path"]
    ledger_json_path = ledger["json_path"]
    ledger_id = add_node(
        project_id,
        "DISC",
        "knowledge_ledger",
        ledger_md_path,
        "Lens knowledge ledger",
        domain="product",
    )
    add_edge(project_id, seed_id, ledger_id, "consolidated_by")
    add_edge(project_id, gap_id, ledger_id, "consolidated_by")
    add_edge(project_id, dec_id, ledger_id, "consolidated_by")
    add_edge(project_id, lens_review_id, ledger_id, "informs")
    add_edge(project_id, ledger_id, req_id, "grounds")
    source_synthesis_id = add_node(
        project_id,
        "DISC",
        "source_synthesis",
        source_synthesis_path,
        "Per-source synthesis",
        domain="product",
    )
    add_edge(project_id, raw_id, source_synthesis_id, "summarized_by")
    add_edge(project_id, source_synthesis_id, req_id, "grounds")

    broker = ContextBroker(project_id)
    broker.index_artifact(raw_id, "raw_input", raw_target, text, trace_ids=[raw_id])
    if requirement_units:
        broker.index_artifact(
            "RU-INDEX",
            "requirement_units",
            units_path,
            units_path.read_text(encoding="utf-8"),
            trace_ids=[raw_id, *unit_node_ids],
        )
    broker.index_artifact(req_id, "requirement", req_path, req_path.read_text(encoding="utf-8"), trace_ids=[raw_id, req_id])
    broker.index_artifact(gap_id, "gap_report", gap_path, gap_path.read_text(encoding="utf-8"), trace_ids=[req_id, gap_id])
    broker.index_artifact(dec_id, "decision_log", dec_path, dec_path.read_text(encoding="utf-8"), trace_ids=[req_id, dec_id])
    broker.index_artifact(seed_id, "identity_seed_bank", seeds_path, seeds_path.read_text(encoding="utf-8"), trace_ids=[raw_id, seed_id])
    broker.index_artifact(
        discovery_log_id,
        "discovery_log",
        discovery_log_path,
        discovery_log_path.read_text(encoding="utf-8"),
        trace_ids=[raw_id, discovery_log_id, gap_id],
    )
    broker.index_artifact(
        lens_review_id,
        "lens_review",
        lens_review_path,
        lens_review_path.read_text(encoding="utf-8"),
        trace_ids=[raw_id, lens_review_id, gap_id],
    )
    broker.index_artifact(
        ledger_id,
        "knowledge_ledger",
        ledger_md_path,
        ledger_md_path.read_text(encoding="utf-8"),
        trace_ids=[raw_id, seed_id, gap_id, dec_id, ledger_id],
    )
    # IMP-160: the per-source synthesis is a derived lineage artifact composed of
    # verbatim citations of already-indexed raw sources. Indexing it would duplicate
    # that evidence in memory and let the derived document displace the real source
    # in the retrieval shortlist (observed under lancedb-ann candidates), so it is
    # deliberately NOT indexed — the graph nodes/edges carry its traceability.
    index_context_folders(project_id, broker)

    # IMP-127: discovery is the highest-volume phase; emit a focused, pointer-only
    # context pack so downstream review consults focus instead of reading whole
    # artifacts. Read-only and degradation-safe (empty pack if nothing retrievable).
    focus_pack = broker.build_focus_pack(
        "discovery_focus",
        req_text[:600],
        limit=6,
        max_chars=1600,
        global_budget_chars=4000,
    )

    update_state(
        project_id,
        phase="discovery_completed",
        health="DIRTY" if gaps else "CLEAN",
        project_language=language,
        privacy_mode="local-only",
        readiness_stage="CLIENT_RESPONSE_NEEDED" if gaps else "READY_FOR_PROJECT_BRIEF",
        gap_counts=count_gaps(gaps),
        artifacts={
            "raw_input": str(raw_target.as_posix()),
            "requirements": str(req_path.as_posix()),
            "gaps": str(gap_path.as_posix()),
            "decisions": str(dec_path.as_posix()),
            "identity_seeds": str(seeds_path.as_posix()),
            "discovery_log": str(discovery_log_path.as_posix()),
            "lens_review": str(lens_review_path.as_posix()),
            "requirement_units": str(units_path.as_posix()),
            "source_synthesis": str(source_synthesis_path.as_posix()),
            "knowledge_state": str(ledger_md_path.as_posix()),
            "knowledge_state_json": str(ledger_json_path.as_posix()),
        },
        metrics={
            "requirements": 1,
            "gaps_open": len(gaps),
            "decisions_pending": 1,
            "user_stories": 0,
            "knowledge_units": ledger["payload"]["summary"]["total"],
            "requirement_units": len(requirement_units),
        },
    )
    return {
        "raw_id": raw_id,
        "requirement_id": req_id,
        "gap_id": gap_id,
        "decision_id": dec_id,
        "seed_id": seed_id,
        "discovery_log_id": discovery_log_id,
        "lens_review_id": lens_review_id,
        "knowledge_ledger_id": ledger_id,
        "source_synthesis_id": source_synthesis_id,
        "requirement_unit_ids": unit_node_ids,
        "requirement_unit_deltas": (
            str(requirement_unit_delta_path.as_posix()) if requirement_unit_delta_path else None
        ),
        "context_pack": focus_pack.get("path"),
    }


def extract_requirement(text: str) -> str:
    lines = [line.strip(" -\t") for line in text.splitlines() if line.strip()]
    for line in lines:
        if any(word in line.lower() for word in ("need", "necesit", "require", "objetivo", "queremos", "must")):
            return line
    return lines[0] if lines else "Requirement to be refined."


UNIT_TRIGGER_RE = re.compile(
    r"\b("
    r"dashboard|tablero|panel|card|cards|tarjeta|tarjetas|metric|metrics|metrica|metricas|kpi|indicador|indicadores|"
    r"login|logueo|auth|autenticacion|autenticación|roles?|permisos?|permission|permissions?|"
    r"workflow|flujo|journey|form|formulario|screen|pantalla|api|endpoint|integration|integracion|integración|"
    r"sync|sincronizacion|sincronización|export|reporte|report"
    r")\b",
    re.I,
)

STOP_LABELS = {
    "need",
    "necesitamos",
    "queremos",
    "must",
    "should",
    "system",
    "sistema",
    "usuario",
    "user",
    "users",
    "cliente",
    "client",
}


def extract_requirement_units(text: str, raw_id: str = "RAW-001", source: Path | None = None) -> list[dict[str, str]]:
    units: list[dict[str, str]] = []
    seen: set[str] = set()
    for sentence in requirement_sentences(text):
        for match in UNIT_TRIGGER_RE.finditer(sentence):
            mention = match.group(0).strip()
            label = unit_label_from_sentence(sentence, mention)
            key = label.lower()
            if key in seen:
                continue
            seen.add(key)
            unit_id = f"RU-{len(units) + 1:03d}"
            units.append(
                {
                    "id": unit_id,
                    "label": label,
                    "evidence_mention": mention,
                    "source": source.as_posix() if source else "",
                    "raw_id": raw_id,
                    "trace_id": unit_id,
                }
            )
    return units


def requirement_sentences(text: str) -> list[str]:
    cleaned = re.sub(r"\s+", " ", text.replace("\n", " ")).strip()
    if not cleaned:
        return []
    parts = re.split(r"(?<=[.!?])\s+|;\s+|\s+-\s+", cleaned)
    return [part.strip(" .\t") for part in parts if part.strip(" .\t")]


def unit_label_from_sentence(sentence: str, mention: str) -> str:
    words = re.findall(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ0-9_-]+", sentence)
    if not words:
        return mention
    idx = next((i for i, word in enumerate(words) if word.lower() == mention.lower()), 0)
    start = max(0, idx - 2)
    end = min(len(words), idx + 4)
    label_words = [word for word in words[start:end] if word.lower() not in STOP_LABELS]
    if not label_words:
        label_words = [mention]
    return " ".join(label_words).strip()[:80]


def render_requirement_units(project_id: str, units: list[dict[str, str]]) -> str:
    rows = "\n".join(
        f"| `{unit['id']}` | {unit['label']} | `{unit['evidence_mention']}` | `{unit.get('raw_id', 'RAW-001')}` | `{unit.get('trace_id', unit['id'])}` |"
        for unit in units
    )
    if not rows:
        rows = "| N/A | No cited requirement units detected. | N/A | N/A | N/A |"
    return f"""# Requirement Units - {project_id}

Requirement Units are discovery-time analysis units. They are cited from raw input and do not replace Spec Units, user stories, or backlog slicing.

| RU ID | Label | Evidence Mention | Raw Source | Trace ID |
| --- | --- | --- | --- | --- |
{rows}
"""


def requirement_unit_snapshot(base: Path) -> dict[str, dict[str, str]]:
    """Parse the current requirement_units.md into a label-keyed snapshot (IMP-150).

    Keyed by the RU label (the named capability), not the positional RU id, so a
    re-ingest that renumbers units still diffs by *what capability* changed.
    """
    units_path = base / "01_discovery" / "requirement_units.md"
    if not units_path.exists():
        return {}
    snapshot: dict[str, dict[str, str]] = {}
    for row in parse_table_rows(units_path.read_text(encoding="utf-8")):
        if not row or not RU_ID_RE.match(row[0].strip().strip("`")):
            continue
        label = row[1].strip() if len(row) > 1 else ""
        key = " ".join(label.lower().split())
        if key:
            snapshot[key] = {
                "id": row[0].strip().strip("`"),
                "label": label,
                "evidence": row[2].strip().strip("`") if len(row) > 2 else "",
            }
    return snapshot


def requirement_unit_delta_entries(
    previous: dict[str, dict[str, str]], units: list[dict[str, str]]
) -> list[dict[str, str]]:
    """ADDED/MODIFIED/REMOVED/UNCHANGED per RU label between two ingest iterations."""
    current: dict[str, dict[str, str]] = {}
    for unit in units:
        key = " ".join(str(unit.get("label", "")).lower().split())
        if key:
            current[key] = {
                "id": str(unit.get("id", "")),
                "label": str(unit.get("label", "")),
                "evidence": str(unit.get("evidence_mention", "")),
            }
    entries: list[dict[str, str]] = []
    for key in sorted(set(previous) | set(current)):
        was, now = previous.get(key), current.get(key)
        if was and not now:
            status, ref = "REMOVED", was
        elif now and not was:
            status, ref = "ADDED", now
        elif was and now and was.get("evidence") != now.get("evidence"):
            status, ref = "MODIFIED", now
        else:
            status, ref = "UNCHANGED", (now or was)
        entries.append(
            {
                "status": status,
                "id": ref.get("id", ""),
                "label": ref.get("label", ""),
                "evidence": ref.get("evidence", ""),
            }
        )
    return entries


def render_requirement_unit_delta(project_id: str, entries: list[dict[str, str]]) -> str:
    def rows(status: str) -> str:
        rendered = [
            f"| `{e['id']}` | {e['label']} | `{e['evidence']}` |"
            for e in entries
            if e["status"] == status
        ]
        return "\n".join(rendered) or "| N/A | None. | N/A |"

    return f"""# Requirement Unit Deltas - {project_id}

Read-only governed view of how the cited Requirement Units changed between the previous and the latest ingest iteration (IMP-150). It signals ADDED / MODIFIED / REMOVED capabilities with their verbatim evidence so divergent iterations stay visible. It never opens, closes, or rewrites gaps or units — the BA reconciles.

## Added

| RU ID | Label | Evidence Mention |
| --- | --- | --- |
{rows("ADDED")}

## Modified

| RU ID | Label | Evidence Mention |
| --- | --- | --- |
{rows("MODIFIED")}

## Removed

| RU ID | Label | Evidence Mention |
| --- | --- | --- |
{rows("REMOVED")}
"""


def write_requirement_unit_delta(
    project_id: str,
    base: Path,
    previous: dict[str, dict[str, str]],
    units: list[dict[str, str]],
) -> Path | None:
    """Write the RU delta view on re-ingest (IMP-150); None on the first ingest.

    Always rewritten on re-ingest so the view reflects the latest iteration (a
    stale delta never lingers); an unchanged re-ingest yields an empty-section
    view rather than no file.
    """
    if not previous:
        return None
    entries = requirement_unit_delta_entries(previous, units)
    path = base / "01_discovery" / "requirement_unit_deltas.md"
    path.write_text(render_requirement_unit_delta(project_id, entries), encoding="utf-8")
    return path


PERSONA_HINTS = (
    "user", "usuario", "usuarios", "actor", "actores", "persona", "lead", "leads",
    "analyst", "analista", "manager", "operator", "operador", "cliente", "customer",
    "equipo", "team", "back office", "stakeholder", "supervisor",
)

REQUIREMENT_HINTS = (
    "must", "shall", "should", "need", "want", "require", "expect",
    "queremos", "necesit", "debe", "deber", "se requiere", "permitir", "esperamos",
)

MISSING_CONTEXT_HINTS = (
    "no ",
    "not ",
    "without ",
    "missing ",
    "unclear ",
    "undefined ",
    "not defined",
    "did not define",
    "does not define",
    "do not define",
    "lacks ",
    "lack ",
    "unknown ",
    "sin ",
    "no se defin",
    "no defin",
    "falta ",
    "pendiente ",
)

CLAUSE_BOUNDARY_HINTS = (
    ".",
    ";",
    "\n",
    " but ",
    " however ",
    " yet ",
    " pero ",
    " aunque ",
    " sin embargo ",
)


def split_evidence_sentences(text: str) -> list[str]:
    """Split raw evidence into clean sentences, dropping markdown noise."""
    import re as _re

    cleaned_lines = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        line = line.lstrip("-*>0123456789. \t")
        if line:
            cleaned_lines.append(line)
    blob = " ".join(cleaned_lines)
    parts = _re.split(r"(?<=[.!?])\s+", blob)
    return [part.strip() for part in parts if len(part.strip()) >= 15]


def extract_personas(text: str, limit: int = 5) -> list[dict[str, str]]:
    """Extract persona/actor evidence sentences from raw client input."""
    results: list[dict[str, str]] = []
    seen: set[str] = set()
    for sentence in split_evidence_sentences(text):
        lowered = sentence.lower()
        if any(hint in lowered for hint in PERSONA_HINTS):
            key = lowered[:80]
            if key in seen:
                continue
            seen.add(key)
            results.append({"evidence": sentence})
            if len(results) >= limit:
                break
    return results


def extract_functional_signals(text: str, limit: int = 7) -> list[dict[str, str]]:
    """Extract requirement-like statements (modal/need language) from raw input."""
    results: list[dict[str, str]] = []
    seen: set[str] = set()
    for sentence in split_evidence_sentences(text):
        lowered = sentence.lower()
        if any(hint in lowered for hint in REQUIREMENT_HINTS):
            key = lowered[:80]
            if key in seen:
                continue
            seen.add(key)
            results.append({"statement": sentence})
            if len(results) >= limit:
                break
    return results


def extract_metric_signals(text: str, limit: int = 5) -> list[dict[str, str]]:
    """Extract quantitative metric mentions with their evidence sentence."""
    results: list[dict[str, str]] = []
    seen: set[str] = set()
    for sentence in split_evidence_sentences(text):
        match = METRIC_RE.search(sentence)
        if not match:
            continue
        key = sentence.lower()[:80]
        if key in seen:
            continue
        seen.add(key)
        results.append({"metric": match.group(0), "evidence": sentence})
        if len(results) >= limit:
            break
    return results


def has_positive_token_evidence(evidence: str, tokens: tuple[str, ...] | list[str]) -> bool:
    """Return true when a token appears outside a missing/negated context."""
    sentences = split_evidence_sentences(evidence)
    if not sentences:
        sentences = [evidence]
    for sentence in sentences:
        lowered = sentence.lower()
        for token in tokens:
            token_text = str(token).lower()
            index = lowered.find(token_text)
            while index >= 0:
                clause_start = 0
                clause_end = len(lowered)
                for boundary in CLAUSE_BOUNDARY_HINTS:
                    previous = lowered.rfind(boundary, 0, index)
                    if previous >= 0:
                        clause_start = max(clause_start, previous + len(boundary))
                    following = lowered.find(boundary, index + len(token_text))
                    if following >= 0:
                        clause_end = min(clause_end, following)
                window_start = max(clause_start, index - 48)
                window_end = min(clause_end, index + len(token_text) + 48)
                window = lowered[window_start:window_end]
                if not any(hint in window for hint in MISSING_CONTEXT_HINTS):
                    return True
                index = lowered.find(token_text, index + len(token_text))
    return False


def weak_word_terms(check: dict) -> list[dict[str, str]]:
    catalog_id = check.get("catalog", "weak_words")
    catalogs = load_smell_catalog()
    catalog = catalogs.get(catalog_id, {})
    categories = check.get("categories", ())
    selected = categories or catalog.get("categories", {}).keys()
    terms: list[dict[str, str]] = []
    for category in selected:
        for term in catalog.get("categories", {}).get(category, ()):
            if isinstance(term, str):
                terms.append({"term": term, "mechanism": category})
            elif isinstance(term, dict) and term.get("term"):
                terms.append(
                    {
                        "term": str(term["term"]),
                        "mechanism": str(term.get("mechanism", category)),
                    }
                )
    terms.extend({"term": str(token), "mechanism": "custom"} for token in check.get("tokens", ()))
    return terms


def first_weak_word_smell(text: str, evidence: str, check: dict) -> tuple[str, str] | None:
    for item in weak_word_terms(check):
        term = item["term"].strip().lower()
        if not term or term not in evidence:
            continue
        sentence = next(
            (candidate for candidate in split_evidence_sentences(text) if term in candidate.lower()),
            term,
        )
        return sentence, item["mechanism"]
    return None


def detect_gaps(text: str, context: dict[str, str] | None = None, lenses_dir=None) -> list[dict[str, str]]:
    """Detect gaps by applying the declarative lens checklist (IMP-033).

    The lens knowledge (checks, severities, tokens, inquisitive rules) lives in
    ``sentinel/lenses/*.json`` via :mod:`sentinel.lens_registry`, not hardcoded
    here. Each check declares a ``rule`` that decides how it fires; behavior is
    identical to the previous in-code checklist. ``lenses_dir`` overrides the
    source directory (used by tests to add a check without touching Python).
    """
    lowered = text.lower()
    context = context or {}
    tech_evidence = " ".join([text, context.get("technical", "")]).lower()
    design_evidence = " ".join([text, context.get("design", "")]).lower()
    quality_evidence = " ".join([text, context.get("quality", "")]).lower()
    frontend_evidence = " ".join([text, context.get("design", ""), context.get("technical", "")]).lower()
    scopes = {
        "source": lowered,
        "technical": tech_evidence,
        "design": design_evidence,
        "quality": quality_evidence,
        "frontend": frontend_evidence,
        "all": " ".join([lowered, tech_evidence, design_evidence, quality_evidence]),
    }
    gaps: list[dict[str, str]] = []
    for check in load_lens_checks(lenses_dir):
        rule = check.get("rule")
        evidence = scopes.get(check.get("evidence_scope", "source"), lowered)
        gap = {
            "id": check["id"],
            "lens": check["lens"],
            "severity": check["severity"],
            "description": check["description"],
        }
        if rule == "absent_tokens":
            if not has_positive_token_evidence(evidence, check.get("tokens", ())):
                gaps.append(gap)
        elif rule == "mention_without_counterpart":
            # Inquisitive tier (IMP-015): a surface is mentioned but its
            # counterpart detail is absent; a bare mention anchors the question
            # to the input instead of suppressing it.
            if any(token in evidence for token in check.get("counterparts", ())):
                continue
            mention = next((token.strip() for token in check.get("triggers", ()) if token in evidence), None)
            if mention:
                gap["evidence_mention"] = mention
            gaps.append(gap)
        elif rule == "mention_requires_counterpart":
            # IMP-117: end false maturity for surface concepts. Unlike
            # ``mention_without_counterpart`` (which fires unless a counterpart is
            # present, trigger optional), this rule fires ONLY when the concept is
            # actually named (trigger present) and its counterpart is absent, so a
            # bare mention of a metric/auth concept anchors the question instead of
            # passing as coverage. No trigger -> nothing to ask.
            mention = next((token.strip() for token in check.get("triggers", ()) if token in evidence), None)
            if not mention:
                continue
            if any(token in evidence for token in check.get("counterparts", ())):
                continue
            gap["evidence_mention"] = mention
            gaps.append(gap)
        elif rule == "metric_without_source":
            metric_match = METRIC_RE.search(text)
            metric_sentence = ""
            if metric_match:
                metric_sentence = next(
                    (sentence for sentence in split_evidence_sentences(text) if METRIC_RE.search(sentence)),
                    metric_match.group(0),
                ).lower()
            if metric_match and not any(token in metric_sentence for token in check.get("suppressors", ())):
                gap["evidence_mention"] = metric_match.group(0)
                gaps.append(gap)
        if rule == "weak_word_smell":
            smell = first_weak_word_smell(text, evidence, check)
            if not smell:
                continue
            sentence, mechanism = smell
            gap["evidence_mention"] = sentence
            gap["smell_mechanism"] = mechanism
            gaps.append(gap)
        if rule == "hypothetical_without_event":
            trigger = next((token.strip() for token in check.get("triggers", ()) if token in evidence), None)
            if not trigger:
                continue
            if any(token in evidence for token in check.get("event_anchors", ())):
                continue
            sentence = next(
                (sentence for sentence in split_evidence_sentences(text) if trigger in sentence.lower()),
                trigger,
            )
            gap["evidence_mention"] = sentence
            gaps.append(gap)
    return gaps


def unit_scope_text(unit: dict[str, str], text: str) -> str:
    """Cited evidence scope for a Requirement Unit (IMP-116).

    Returns the source sentence(s) that mention the unit, so lens checks can be
    evaluated against the unit's own cited text instead of the whole document.
    Falls back to the unit label when no sentence carries the mention verbatim.
    """
    mention = str(unit.get("evidence_mention", "")).strip().lower()
    sentences = [
        sentence
        for sentence in requirement_sentences(text)
        if mention and mention in sentence.lower()
    ]
    if sentences:
        return " ".join(sentences)
    return str(unit.get("label", "")).strip()


def anchoring_unit_for_gap(gap: dict[str, str], units: list[dict[str, str]], text: str) -> str:
    """Return the RU id whose cited scope explains an inquisitive gap (IMP-116).

    Only gaps carrying a detected trigger (``evidence_mention``) are anchored;
    document-level ``absent_tokens`` gaps stay unanchored. The first unit (stable
    RU order) whose scoped text contains the trigger wins.
    """
    mention = str(gap.get("evidence_mention", "")).strip().lower()
    if not mention or mention == "n/a":
        return ""
    for unit in units:
        if mention in unit_scope_text(unit, text).lower():
            return str(unit.get("id", ""))
    return ""


def detect_unit_anchored_gaps(
    text: str,
    context: dict[str, str] | None = None,
    units: list[dict[str, str]] | None = None,
    lenses_dir=None,
) -> list[dict[str, str]]:
    """Run lens checks globally and per Requirement Unit (IMP-116).

    Document-level detection is unchanged: every gap ``detect_gaps`` would emit
    is still produced. When Requirement Units (IMP-115) exist, each unit's cited
    evidence is also scoped on its own, so a trigger token present in one unit
    can no longer suppress an inquisitive gap that belongs to another unit. Each
    emitted gap carries the RU that explains it in an additive ``unit`` field;
    document-level gaps without a unit scope stay unanchored. Without units the
    result is identical to ``detect_gaps`` (back-compat for existing workspaces).
    """
    base_gaps = detect_gaps(text, context, lenses_dir)
    if not units:
        return base_gaps
    by_id = {gap["id"]: gap for gap in base_gaps}
    for gap in base_gaps:
        gap["unit"] = anchoring_unit_for_gap(gap, units, text)
    for unit in units:
        scope = unit_scope_text(unit, text)
        for gap in detect_gaps(scope, context, lenses_dir):
            if gap["id"] in by_id:
                continue
            # Only inquisitive (trigger-bearing) gaps are surfaced per unit;
            # document-level absent_tokens gaps remain a single global signal.
            if not str(gap.get("evidence_mention", "")).strip():
                continue
            gap["unit"] = str(unit.get("id", ""))
            by_id[gap["id"]] = gap
            base_gaps.append(gap)
    return base_gaps


def count_gaps(gaps: list[dict[str, str]]) -> dict[str, int]:
    counts = {
        "open": 0,
        "closed": 0,
        "partially_closed": 0,
        "answered": 0,
        "blocking_open": 0,
        "total": len(gaps),
    }
    for gap in gaps:
        status = str(gap.get("status", "OPEN")).upper()
        severity = str(gap.get("severity", "")).lower()
        if status == "OPEN":
            counts["open"] += 1
            if severity in {"critical", "high"}:
                counts["blocking_open"] += 1
        elif status == "ANSWERED":
            counts["answered"] += 1
            if severity in {"critical", "high"}:
                counts["blocking_open"] += 1
        elif status == "PARTIALLY_CLOSED":
            counts["partially_closed"] += 1
            if severity in {"critical", "high"}:
                counts["blocking_open"] += 1
        elif status == "CLOSED":
            counts["closed"] += 1
    return counts


def parse_gap_rows(text: str) -> list[dict[str, str]]:
    return parse_gap_table(text)


def regenerate_gaps(project_id: str) -> dict[str, object]:
    base = workspace_path(project_id)
    gaps_path = base / "01_discovery" / "gaps.md"
    if not gaps_path.exists():
        raise RuntimeError("Cannot regenerate gaps before /ingest creates 01_discovery/gaps.md.")
    existing = parse_gap_rows(gaps_path.read_text(encoding="utf-8"))
    req_id = existing[0].get("parent", "REQ-001").strip("`") if existing else "REQ-001"
    state_language = load_config(project_id).get("project_language", "auto")
    state_path = base / "state.json"
    if state_path.exists():
        try:
            state = read_json(state_path, {})
            state_language = state.get("project_language", state_language)
        except Exception:
            pass
    language = str(state_language if state_language in {"es", "en"} else "en")
    gaps_path.write_text(render_gaps(project_id, existing, req_id, language), encoding="utf-8")
    counts = count_gaps(existing)
    update_state(project_id, gap_counts=counts, readiness_stage=readiness_stage_for_counts(counts))
    return {"project_id": project_id, "path": str(gaps_path), "gap_counts": counts}


def readiness_stage_for_counts(counts: dict[str, int]) -> str:
    if counts.get("blocking_open", 0):
        return "CLIENT_RESPONSE_NEEDED"
    if counts.get("open", 0) or counts.get("partially_closed", 0) or counts.get("answered", 0):
        return "DOMAIN_RESPONSE_NEEDED"
    return "READY_FOR_PROJECT_BRIEF"


# --- IMP-021: agentic analysis protocol (/annotate) ---------------------------
#
# The lexical checklist (detect_gaps) reaches a ceiling: a single token present
# in the input suppresses a whole gap even when the substance is missing. The
# agent operating the framework is the only component with semantic capability,
# but "never edit artifacts by hand" left it no sanctioned channel. /annotate is
# that channel: the agent proposes semantic gaps WITH a verbatim evidence quote;
# the runtime validates (schema, declared lens, severity range, citation must be
# real), tags them `origin: agent`, merges them into gaps.md, and records
# traceability. The runtime stays the authority; the agent never writes directly.
# Invariants honored: evidence-or-silence (#3, the quote must exist in the raw
# input — the agent cites, never invents), lens identity (#1, lens validated
# against the same knowledge base as detect_gaps), BA-in-control (#5, gaps enter
# the normal resolve/maturity/gate lifecycle).

GAP_ID_RE = re.compile(r"^GAP-[A-Z0-9-]+$")
RU_ID_RE = re.compile(r"^RU-[0-9]{3}$")


class AnnotationError(RuntimeError):
    """Raised when an agentic annotation fails validation (IMP-021)."""


def _normalize_for_match(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def raw_input_text(base: Path) -> str:
    """Concatenate the raw client input copied into 00_raw/ (top level only)."""
    raw_dir = base / "00_raw"
    chunks: list[str] = []
    if raw_dir.exists():
        for pattern in ("*.md", "*.txt", "*.html", "*.htm"):
            for path in sorted(raw_dir.glob(pattern)):
                chunks.append(path.read_text(encoding="utf-8"))
    return "\n\n".join(chunks)


def scrutiny_grounding_text(base: Path) -> str:
    """Raw input plus domain-owned context folders for citation validation."""
    context = load_domain_context(base)
    chunks = [raw_input_text(base)]
    chunks.extend(text for text in context.values() if text.strip())
    return "\n\n".join(chunks)


def load_agent_annotation(source: Path) -> dict:
    try:
        data = read_json(source, {})
    except json.JSONDecodeError as exc:
        raise AnnotationError(f"Annotation source is not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise AnnotationError("Annotation must be a JSON object with a 'gaps' array.")
    return data


def validate_agent_gaps(data: dict, raw_text: str, lenses_dir=None, origin: str = "agent") -> list[dict[str, str]]:
    """Validate the agent's structured analysis; reject anything ungrounded.

    Returns normalized gap dicts ready to merge into gaps.md. Raises
    :class:`AnnotationError` with a clear message on the first violation. ``origin``
    tags the provenance (``agent`` for /annotate, ``challenge`` for /challenge).
    """
    gaps_in = data.get("gaps")
    if not isinstance(gaps_in, list) or not gaps_in:
        raise AnnotationError("Annotation must contain a non-empty 'gaps' array.")
    valid_lenses = known_lenses(lenses_dir)
    valid_severities = {"critical", "high", "medium", "low"}
    haystack = _normalize_for_match(raw_text)
    validated: list[dict[str, str]] = []
    seen: set[str] = set()
    for index, item in enumerate(gaps_in, start=1):
        if not isinstance(item, dict):
            raise AnnotationError(f"Gap #{index} must be an object.")
        gap_id = str(item.get("id", "")).strip().upper()
        if not GAP_ID_RE.match(gap_id):
            raise AnnotationError(
                f"Gap #{index} has an invalid id '{item.get('id')}': must match ^GAP-[A-Z0-9-]+$."
            )
        if gap_id in seen:
            raise AnnotationError(f"Duplicate gap id within the annotation: {gap_id}.")
        seen.add(gap_id)
        lens = str(item.get("lens", "")).strip().lower()
        if lens not in valid_lenses:
            raise AnnotationError(
                f"{gap_id}: lens '{item.get('lens')}' is not a declared lens "
                f"({', '.join(sorted(valid_lenses))})."
            )
        severity = str(item.get("severity", "")).strip().lower()
        if severity not in valid_severities:
            raise AnnotationError(
                f"{gap_id}: severity '{item.get('severity')}' must be one of "
                f"{', '.join(sorted(valid_severities))}."
            )
        question = str(item.get("question", "")).strip()
        if not question:
            raise AnnotationError(f"{gap_id}: a 'question' is required.")
        evidence = str(item.get("evidence", "")).strip()
        if not evidence:
            raise AnnotationError(
                f"{gap_id}: a verbatim 'evidence' quote from the raw input is required "
                "(evidence or explicit silence — invariant #3)."
            )
        if _normalize_for_match(evidence) not in haystack:
            raise AnnotationError(
                f"{gap_id}: the evidence quote is not found verbatim in the raw input. "
                "An agent must cite real text, never invent it."
            )
        description = str(item.get("description", "")).strip() or question
        gap = {
            "id": gap_id,
            "lens": lens,
            "severity": severity,
            "status": "OPEN",
            "description": description,
            "question": question,
            "evidence_mention": evidence if len(evidence) <= 160 else evidence[:157] + "...",
            "origin": origin,
        }
        unit = str(item.get("unit", "")).strip().upper()
        if unit:
            if not RU_ID_RE.match(unit):
                raise AnnotationError(
                    f"{gap_id}: unit '{item.get('unit')}' must match ^RU-[0-9]{{3}}$ "
                    "(a Requirement Unit id, IMP-116)."
                )
            gap["unit"] = unit
        validated.append(gap)
    return validated


def _trace_refs_from_graph(project_id: str) -> dict[str, str]:
    refs: dict[str, str] = {}
    for node in load_graph(project_id).get("nodes", []):
        node_type = node.get("type")
        if node_type and node_type not in refs:
            refs[str(node_type)] = str(node.get("id", ""))
    return {
        "raw_input": refs.get("raw_input", ""),
        "requirement": refs.get("requirement", ""),
        "gap_report": refs.get("gap_report", ""),
        "decision_log": refs.get("decision_log", ""),
        "identity_seed_bank": refs.get("identity_seed_bank", ""),
        "lens_review": refs.get("lens_review", ""),
        "assumption_register": refs.get("assumption_register", ""),
    }


def refresh_knowledge_ledger(project_id: str, broker: ContextBroker | None = None) -> dict[str, object]:
    """Rebuild the discovery ledger from current governed artifacts."""
    base = workspace_path(project_id)
    seeds_path = base / "01_discovery" / "identity_seeds.md"
    gaps_path = base / "01_discovery" / "gaps.md"
    decisions_path = base / "01_discovery" / "decisions.md"
    assumptions_path = base / "01_discovery" / "assumptions.md"
    if not gaps_path.exists():
        raise RuntimeError("Cannot refresh knowledge ledger before gaps.md exists.")
    ledger = materialize_knowledge_ledger(
        project_id,
        seeds_path.read_text(encoding="utf-8") if seeds_path.exists() else "",
        parse_gap_rows(gaps_path.read_text(encoding="utf-8")),
        decisions_path.read_text(encoding="utf-8") if decisions_path.exists() else "",
        _trace_refs_from_graph(project_id),
        assumptions_path.read_text(encoding="utf-8") if assumptions_path.exists() else "",
    )
    ledger_md_path = ledger["md_path"]
    refs = _trace_refs_from_graph(project_id)
    ledger_id = add_node(
        project_id,
        "DISC",
        "knowledge_ledger",
        ledger_md_path,
        "Lens knowledge ledger",
        domain="product",
    )
    for source_id in (refs.get("identity_seed_bank"), refs.get("gap_report"), refs.get("decision_log"), refs.get("lens_review"), refs.get("assumption_register")):
        if source_id:
            add_edge(project_id, source_id, ledger_id, "consolidated_by")
    if refs.get("requirement"):
        add_edge(project_id, ledger_id, refs["requirement"], "grounds")
    broker = broker or ContextBroker(project_id)
    broker.index_artifact(
        ledger_id,
        "knowledge_ledger",
        ledger_md_path,
        ledger_md_path.read_text(encoding="utf-8"),
        trace_ids=[trace_id for trace_id in [refs.get("raw_input"), refs.get("gap_report"), ledger_id] if trace_id],
    )
    return {"ledger_id": ledger_id, **ledger}


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    counter = 2
    while True:
        candidate = path.with_name(f"{path.stem}-{counter}{path.suffix}")
        if not candidate.exists():
            return candidate
        counter += 1


def _annotation_project_language(project_id: str, base: Path) -> str:
    language = load_config(project_id).get("project_language", "auto")
    state_file = base / "state.json"
    if state_file.exists():
        try:
            language = read_json(state_file, {}).get("project_language", language)
        except (ValueError, OSError):
            pass
    return str(language if language in {"es", "en"} else "en")


def render_annotation_log_entry(
    label: str,
    merged: list[dict[str, str]],
    skipped: list[str],
    data: dict,
) -> str:
    gap_rows = "\n".join(
        f"| `{gap['id']}` | `{gap['lens']}` | {gap['severity']} | {gap['question']} | {gap.get('evidence_mention', '')} |"
        for gap in merged
    ) or "| N/A | N/A | N/A | No new gaps merged (all duplicates). | N/A |"
    ambiguities = _string_list(data.get("ambiguities"))
    assumptions = _string_list(data.get("assumptions"))
    ambiguity_block = "\n".join(f"- {item}" for item in ambiguities) or "- None reported."
    assumption_block = "\n".join(f"- {item}" for item in assumptions) or "- None reported."
    skipped_block = ", ".join(f"`{gap_id}`" for gap_id in skipped) or "None."
    return f"""## Annotation: {label}

Origin: `agent`. The runtime validated each gap (declared lens, severity range, and a verbatim evidence citation) before merging.

### Merged Semantic Gaps

| Gap ID | Lens | Severity | Question | Evidence Cited |
| --- | --- | --- | --- | --- |
{gap_rows}

Skipped (already present in gaps.md): {skipped_block}

### Ambiguities Reported

{ambiguity_block}

### Implicit Assumptions Reported

{assumption_block}
"""


def write_annotation_log(
    log_path: Path,
    project_id: str,
    label: str,
    merged: list[dict[str, str]],
    skipped: list[str],
    data: dict,
) -> None:
    if not log_path.exists():
        log_path.write_text(
            f"""# Agent Annotation Log - {project_id}

Sanctioned record of agentic (`origin: agent`) discovery analysis (IMP-021).
Each entry below was validated and merged by the runtime; source files remain
the authority. The agent proposes with evidence; it never writes artifacts by hand.

""",
            encoding="utf-8",
        )
    append_text(log_path, render_annotation_log_entry(label, merged, skipped, data) + "\n")


def apply_annotation(project_id: str, source: Path) -> dict[str, object]:
    """Validate, merge, and trace an agentic annotation of the raw input (IMP-021)."""
    base = workspace_path(project_id)
    if not base.exists():
        raise RuntimeError(f"Workspace not found: {project_id}")
    gaps_path = base / "01_discovery" / "gaps.md"
    if not gaps_path.exists():
        raise RuntimeError("Cannot annotate before /ingest creates 01_discovery/gaps.md.")

    raw_text = raw_input_text(base)
    if not raw_text.strip():
        raise RuntimeError("No raw input found under 00_raw/ to ground the annotation against.")

    data = load_agent_annotation(source)
    agent_gaps = validate_agent_gaps(data, raw_text)

    existing = parse_gap_rows(gaps_path.read_text(encoding="utf-8"))
    real_existing = [gap for gap in existing if gap.get("id") != "NONE"]
    existing_ids = {gap["id"] for gap in real_existing}
    req_id = real_existing[0].get("parent", "REQ-001").strip("`") if real_existing else "REQ-001"

    merged_new: list[dict[str, str]] = []
    skipped: list[str] = []
    for gap in agent_gaps:
        if gap["id"] in existing_ids:
            skipped.append(gap["id"])
            continue
        merged_new.append(gap)
        existing_ids.add(gap["id"])

    merged = real_existing + merged_new
    language = _annotation_project_language(project_id, base)
    gaps_path.write_text(render_gaps(project_id, merged, req_id, language), encoding="utf-8")

    annotations_dir = base / "01_discovery" / "annotations"
    annotations_dir.mkdir(parents=True, exist_ok=True)
    stored = _unique_path(annotations_dir / f"{source.stem}.json")
    shutil.copyfile(source, stored)

    log_path = base / "01_discovery" / "agent_annotation_log.md"
    write_annotation_log(log_path, project_id, source.stem, merged_new, skipped, data)

    graph_nodes = load_graph(project_id).get("nodes", [])
    annotation_id = add_node(
        project_id,
        "DISC",
        "agent_annotation",
        log_path,
        f"Agent annotation: {source.stem}",
        domain="product",
    )
    for raw_node in [node for node in graph_nodes if node.get("type") == "raw_input"]:
        add_edge(project_id, raw_node["id"], annotation_id, "annotated_by")
    for gap_node in [node for node in graph_nodes if node.get("type") == "gap_report"]:
        add_edge(project_id, annotation_id, gap_node["id"], "raises")

    broker = ContextBroker(project_id)
    broker.index_artifact(
        annotation_id,
        "agent_annotation",
        log_path,
        log_path.read_text(encoding="utf-8"),
        trace_ids=[annotation_id],
    )
    mark_source_processed(project_id, source, "agent_annotated", annotation_id)

    counts = count_gaps(merged)
    counts["agent_origin"] = sum(1 for gap in merged if gap.get("origin") == "agent")
    updates: dict[str, object] = {
        "gap_counts": counts,
        "readiness_stage": readiness_stage_for_counts(counts),
        "last_annotation_id": annotation_id,
    }
    if counts.get("blocking_open", 0):
        updates["health"] = "DIRTY"
    update_state(project_id, **updates)

    return {
        "project_id": project_id,
        "annotation_id": annotation_id,
        "path": str(gaps_path.as_posix()),
        "annotation_log": str(log_path.as_posix()),
        "merged": [gap["id"] for gap in merged_new],
        "skipped_duplicates": skipped,
        "gap_counts": counts,
    }


# --- IMP-023: advanced elicitation (/challenge) -------------------------------
#
# /challenge materializes "understanding what is NOT being said": the agent runs
# BMAD-style techniques over the maturing requirement — pre-mortem ("the project
# failed at 6 months: what did we fail to ask?"), role-play per lens (operator,
# auditor, attacker...), and assumption inversion. Findings are NOT written
# directly: they go through the same validation as /annotate (declared lens,
# severity range, verbatim evidence) and are merged as gaps tagged
# `origin: challenge`. Techniques run per lens (invariant #1), not as generic
# personas. The runtime stays the authority; the agent proposes with evidence.
# IMP-112 moves the default technique catalog to sentinel/techniques/*.json.

CHALLENGE_TECHNIQUES = default_challenge_technique_ids()


def _technique_by_gap(data: dict) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for item in data.get("gaps", []) if isinstance(data.get("gaps"), list) else []:
        if isinstance(item, dict):
            gid = str(item.get("id", "")).strip().upper()
            tech = str(item.get("technique", "")).strip()
            if gid and tech:
                mapping[gid] = tech
    return mapping


def _technique_name(raw: str) -> str:
    normalized = str(raw or "").strip()
    return technique_label(normalized) if normalized else "n/a"


def render_challenge_report(
    project_id: str,
    label: str,
    merged: list[dict[str, str]],
    skipped: list[str],
    data: dict,
    language: str = "en",
    respondent_profile: str | None = None,
) -> str:
    techniques = _technique_by_gap(data)
    catalog_line = f"Technique catalog: `sentinel/techniques/*.json`. Default set: {default_technique_summary()}."
    if respondent_profile:
        calibrated_prompts = "\n".join(
            f"- `{technique_id}`: {technique_prompt(technique_id, respondent_profile=respondent_profile)}"
            for technique_id in default_challenge_technique_ids()
        )
        catalog_line = (
            f"{catalog_line}\n\nDeclared respondent profile: `{respondent_profile}`.\n\n"
            f"Calibrated technique prompts:\n{calibrated_prompts}"
        )
    by_lens: dict[str, list[dict[str, str]]] = {}
    for gap in merged:
        by_lens.setdefault(gap["lens"], []).append(gap)
    lens_blocks = []
    for lens in sorted(by_lens):
        rows = "\n".join(
            f"| `{gap['id']}` | {gap['severity']} | {_technique_name(techniques.get(gap['id'], ''))} | {gap['question']} | {gap.get('evidence_mention', '')} |"
            for gap in by_lens[lens]
        )
        lens_blocks.append(f"### Lens: `{lens}`\n\n| Gap ID | Severity | Technique | Question | Evidence Cited |\n| --- | --- | --- | --- | --- |\n{rows}")
    lens_section = "\n\n".join(lens_blocks) or "_No new challenge gaps merged (all duplicates)._"
    premortem = _string_list(data.get("premortem"))
    inverted = _string_list(data.get("assumptions_inverted"))
    premortem_block = "\n".join(f"- {item}" for item in premortem) or "- None reported."
    inverted_block = "\n".join(f"- {item}" for item in inverted) or "- None reported."
    skipped_block = ", ".join(f"`{gap_id}`" for gap_id in skipped) or "None."
    return f"""# Challenge Report - {project_id}

Source: `{label}`. Origin: `challenge`. Advanced elicitation (IMP-023): the agent
ran pre-mortem, per-lens role-play, and assumption inversion over the maturing
requirement. Every finding below was validated by the runtime (declared lens,
severity range, verbatim evidence) before merging as a gap — never written by hand.

## Challenge Findings By Lens

{catalog_line}

{lens_section}

Skipped (already present in gaps.md): {skipped_block}

## Pre-Mortem (imagined failure modes)

{premortem_block}

## Inverted Assumptions

{inverted_block}
"""


def apply_challenge(project_id: str, source: Path) -> dict[str, object]:
    """Validate, merge, and trace advanced-elicitation findings (IMP-023).

    Reuses the IMP-021 validation protocol but tags gaps `origin: challenge` and
    writes a versionable `01_discovery/challenge_report.md`.
    """
    base = workspace_path(project_id)
    if not base.exists():
        raise RuntimeError(f"Workspace not found: {project_id}")
    respondent_profile = respondent_profile_from_domain_context(base)
    gaps_path = base / "01_discovery" / "gaps.md"
    if not gaps_path.exists():
        raise RuntimeError("Cannot challenge before /ingest creates 01_discovery/gaps.md.")

    raw_text = raw_input_text(base)
    if not raw_text.strip():
        raise RuntimeError("No raw input found under 00_raw/ to ground the challenge against.")

    data = load_agent_annotation(source)
    challenge_gaps = validate_agent_gaps(data, raw_text, origin="challenge")

    existing = parse_gap_rows(gaps_path.read_text(encoding="utf-8"))
    real_existing = [gap for gap in existing if gap.get("id") != "NONE"]
    existing_ids = {gap["id"] for gap in real_existing}
    req_id = real_existing[0].get("parent", "REQ-001").strip("`") if real_existing else "REQ-001"

    merged_new: list[dict[str, str]] = []
    skipped: list[str] = []
    for gap in challenge_gaps:
        if gap["id"] in existing_ids:
            skipped.append(gap["id"])
            continue
        merged_new.append(gap)
        existing_ids.add(gap["id"])

    merged = real_existing + merged_new
    language = _annotation_project_language(project_id, base)
    gaps_path.write_text(render_gaps(project_id, merged, req_id, language), encoding="utf-8")

    challenges_dir = base / "01_discovery" / "challenges"
    challenges_dir.mkdir(parents=True, exist_ok=True)
    stored = _unique_path(challenges_dir / f"{source.stem}.json")
    shutil.copyfile(source, stored)

    report_path = base / "01_discovery" / "challenge_report.md"
    report_path.write_text(
        render_challenge_report(project_id, source.stem, merged_new, skipped, data, language, respondent_profile),
        encoding="utf-8",
    )

    graph_nodes = load_graph(project_id).get("nodes", [])
    challenge_id = add_node(
        project_id,
        "DISC",
        "challenge_report",
        report_path,
        f"Challenge report: {source.stem}",
        domain="product",
    )
    for raw_node in [node for node in graph_nodes if node.get("type") == "raw_input"]:
        add_edge(project_id, raw_node["id"], challenge_id, "challenged_by")
    for gap_node in [node for node in graph_nodes if node.get("type") == "gap_report"]:
        add_edge(project_id, challenge_id, gap_node["id"], "raises")

    broker = ContextBroker(project_id)
    broker.index_artifact(
        challenge_id,
        "challenge_report",
        report_path,
        report_path.read_text(encoding="utf-8"),
        trace_ids=[challenge_id],
    )
    mark_source_processed(project_id, source, "challenge_applied", challenge_id)

    counts = count_gaps(merged)
    counts["challenge_origin"] = sum(1 for gap in merged if gap.get("origin") == "challenge")
    updates: dict[str, object] = {
        "gap_counts": counts,
        "readiness_stage": readiness_stage_for_counts(counts),
        "last_challenge_id": challenge_id,
    }
    if counts.get("blocking_open", 0):
        updates["health"] = "DIRTY"
    update_state(project_id, **updates)

    return {
        "project_id": project_id,
        "challenge_id": challenge_id,
        "path": str(gaps_path.as_posix()),
        "challenge_report": str(report_path.as_posix()),
        "merged": [gap["id"] for gap in merged_new],
        "skipped_duplicates": skipped,
        "gap_counts": counts,
    }


# --- IMP-066: systematic multi-lens scrutiny (/scrutinize) --------------------
#
# /scrutinize is the governed channel for a systematic per-lens agent pass over
# raw requirement + domain context. It reuses the same citation validation as
# /annotate, but allows evidence to come from local context folders too, tags
# findings `origin: scrutiny`, writes a report, and refreshes the knowledge
# ledger so the new open units are visible to downstream progressive disclosure.

SCRUTINY_FINDING_TYPES = {
    "unstated-assumption",
    "contradiction",
    "mention-without-counterpart",
    "domain-conflict",
}

# --- IMP-119: agentic implementability probe (pre-flight) ---------------------
#
# The probe is a sub-mode of /scrutinize (not a new command — it reuses the same
# citation/merge machinery and adds no command surface, mirroring IMP-112). An
# agent declares, per Requirement Unit, whether it has enough to implement or
# what it is missing — materialized as cited gaps anchored to `RU-*`, the
# pre-flight mirror of the downstream `/implementation-feedback`. Findings carry
# a probe-specific finding_type vocabulary and `origin: implementability-probe`;
# nothing is auto-resolved, and every finding still requires a verbatim local
# citation, exactly like scrutiny.

PROBE_FINDING_TYPES = {
    "missing-context",
    "non-inferable-gap",
    "ambiguous-for-implementation",
}

SCRUTINY_MODES = {
    "scrutiny": {
        "origin": "scrutiny",
        "finding_types": SCRUTINY_FINDING_TYPES,
        "report_name": "scrutiny_report.md",
        "store_dir": "scrutiny",
        "node_type": "scrutiny_report",
        "node_label": "Scrutiny report",
        "raw_relation": "scrutinized_by",
        "state_key": "last_scrutiny_id",
        "origin_count_key": "scrutiny_origin",
        "require_unit": False,
    },
    "implementability-probe": {
        "origin": "implementability-probe",
        "finding_types": PROBE_FINDING_TYPES,
        "report_name": "implementability_probe_report.md",
        "store_dir": "implementability_probe",
        "node_type": "implementability_probe",
        "node_label": "Implementability probe",
        "raw_relation": "probed_by",
        "state_key": "last_probe_id",
        "origin_count_key": "implementability_probe_origin",
        "require_unit": True,
    },
}


def _scrutiny_mode(mode: str | None) -> dict[str, object]:
    key = (mode or "scrutiny").strip().lower()
    if key not in SCRUTINY_MODES:
        raise AnnotationError(
            f"Unknown scrutiny mode '{mode}': must be one of {', '.join(sorted(SCRUTINY_MODES))}."
        )
    return SCRUTINY_MODES[key]


def _finding_type_by_gap(data: dict) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for item in data.get("gaps", []) if isinstance(data.get("gaps"), list) else []:
        if isinstance(item, dict):
            gid = str(item.get("id", "")).strip().upper()
            finding_type = str(item.get("finding_type", item.get("type", ""))).strip()
            if gid and finding_type:
                mapping[gid] = finding_type
    return mapping


def validate_scrutiny_gaps(
    data: dict,
    grounding_text: str,
    lens: str | None = None,
    mode: str | None = "scrutiny",
    known_units: set[str] | None = None,
) -> list[dict[str, str]]:
    spec = _scrutiny_mode(mode)
    gaps = validate_agent_gaps(data, grounding_text, origin=str(spec["origin"]))
    valid_lenses = known_lenses()
    if lens:
        lens = lens.strip().lower()
        if lens not in valid_lenses:
            raise AnnotationError(
                f"Scrutiny lens '{lens}' is not a declared lens ({', '.join(sorted(valid_lenses))})."
            )
        mismatched = [gap["id"] for gap in gaps if gap.get("lens") != lens]
        if mismatched:
            raise AnnotationError(
                f"Scrutiny source includes gaps outside --lens {lens}: {', '.join(mismatched)}."
            )
    finding_types = spec["finding_types"]
    raw_items = data.get("gaps", [])
    for item in raw_items if isinstance(raw_items, list) else []:
        if not isinstance(item, dict):
            continue
        finding_type = str(item.get("finding_type", item.get("type", ""))).strip()
        if finding_type and finding_type not in finding_types:
            gap_id = str(item.get("id", "<unknown>")).strip().upper()
            raise AnnotationError(
                f"{gap_id}: finding_type '{finding_type}' must be one of "
                f"{', '.join(sorted(finding_types))}."
            )
    if spec["require_unit"]:
        # The probe is per-RU: every finding must anchor to a Requirement Unit,
        # and (when the unit register exists) to a real one — it cites, never
        # invents the unit it claims is unimplementable.
        for gap in gaps:
            unit = gap.get("unit", "")
            if not unit:
                raise AnnotationError(
                    f"{gap['id']}: the implementability probe requires a 'unit' (RU-NNN) "
                    "so each finding anchors to the Requirement Unit it blocks."
                )
            if known_units is not None and unit not in known_units:
                raise AnnotationError(
                    f"{gap['id']}: unit '{unit}' is not a known Requirement Unit "
                    "(run discovery to extract RUs; the probe cites real units, never invents them)."
                )
    return gaps


def render_scrutiny_report(
    project_id: str,
    label: str,
    merged: list[dict[str, str]],
    skipped: list[str],
    data: dict,
    lens_filter: str | None = None,
) -> str:
    finding_types = _finding_type_by_gap(data)
    by_lens: dict[str, list[dict[str, str]]] = {}
    for gap in merged:
        by_lens.setdefault(gap["lens"], []).append(gap)
    lens_blocks = []
    for lens in sorted(by_lens):
        rows = "\n".join(
            f"| `{gap['id']}` | {gap['severity']} | {finding_types.get(gap['id'], 'n/a')} | {gap['question']} | {gap.get('evidence_mention', '')} |"
            for gap in by_lens[lens]
        )
        lens_blocks.append(f"### Lens: `{lens}`\n\n| Gap ID | Severity | Finding Type | Question | Evidence Cited |\n| --- | --- | --- | --- | --- |\n{rows}")
    lens_section = "\n\n".join(lens_blocks) or "_No new scrutiny gaps merged (all duplicates)._"
    skipped_block = ", ".join(f"`{gap_id}`" for gap_id in skipped) or "None."
    lens_note = f"Lens filter: `{lens_filter}`." if lens_filter else "Lens filter: all declared lenses."
    return f"""# Scrutiny Report - {project_id}

Source: `{label}`. Origin: `scrutiny`. {lens_note}

The agent scrutinized raw requirement evidence plus local domain context through
the Ignite lens model. Every finding below was validated by the runtime
(declared lens, severity range, valid finding type, and a verbatim local
citation) before merging as a gap. The agent proposes; the BA remains in control.

## Scrutiny Findings By Lens

{lens_section}

Skipped (already present in gaps.md): {skipped_block}
"""


def known_requirement_unit_ids(base: Path) -> set[str]:
    """RU ids declared in 01_discovery/requirement_units.md (IMP-115), or empty."""
    units_path = base / "01_discovery" / "requirement_units.md"
    if not units_path.exists():
        return set()
    ids: set[str] = set()
    for row in parse_table_rows(units_path.read_text(encoding="utf-8")):
        if row and RU_ID_RE.match(row[0].strip().strip("`")):
            ids.add(row[0].strip().strip("`"))
    return ids


def render_probe_report(
    project_id: str,
    label: str,
    merged: list[dict[str, str]],
    skipped: list[str],
    data: dict,
) -> str:
    """Per-RU implementability probe report (IMP-119)."""
    finding_types = _finding_type_by_gap(data)
    by_unit: dict[str, list[dict[str, str]]] = {}
    for gap in merged:
        by_unit.setdefault(gap.get("unit", "—"), []).append(gap)
    unit_blocks = []
    for unit in sorted(by_unit):
        rows = "\n".join(
            f"| `{gap['id']}` | {gap['lens']} | {gap['severity']} | {finding_types.get(gap['id'], 'n/a')} | {gap['question']} | {gap.get('evidence_mention', '')} |"
            for gap in by_unit[unit]
        )
        unit_blocks.append(
            f"### Unit: `{unit}`\n\n"
            "| Gap ID | Lens | Severity | Finding Type | Missing To Implement | Evidence Cited |\n"
            "| --- | --- | --- | --- | --- | --- |\n"
            f"{rows}"
        )
    unit_section = "\n\n".join(unit_blocks) or "_No new probe gaps merged (all duplicates)._"
    skipped_block = ", ".join(f"`{gap_id}`" for gap_id in skipped) or "None."
    return f"""# Implementability Probe Report - {project_id}

Source: `{label}`. Origin: `implementability-probe`.

A coding agent probed, per Requirement Unit, whether it has enough to implement
each unit before any work begins — the pre-flight mirror of
`/implementation-feedback`. Every finding below was validated by the runtime
(declared lens, severity range, a probe finding type, an anchoring `RU-*`, and a
verbatim local citation) before merging as a gap. The agent declares what is
missing; nothing is auto-resolved and the BA remains in control.

## Probe Findings By Requirement Unit

{unit_section}

Skipped (already present in gaps.md): {skipped_block}
"""


def apply_scrutiny(
    project_id: str,
    source: Path,
    lens: str | None = None,
    mode: str | None = "scrutiny",
) -> dict[str, object]:
    """Validate and merge systematic multi-lens scrutiny findings (IMP-066).

    With ``mode="implementability-probe"`` (IMP-119) the same machinery runs the
    pre-flight implementability probe: per-RU cited gaps, probe finding types,
    and ``origin: implementability-probe``.
    """
    spec = _scrutiny_mode(mode)
    is_probe = spec["origin"] == "implementability-probe"
    base = workspace_path(project_id)
    if not base.exists():
        raise RuntimeError(f"Workspace not found: {project_id}")
    gaps_path = base / "01_discovery" / "gaps.md"
    if not gaps_path.exists():
        raise RuntimeError("Cannot scrutinize before /ingest creates 01_discovery/gaps.md.")

    grounding_text = scrutiny_grounding_text(base)
    if not grounding_text.strip():
        raise RuntimeError("No raw or domain context evidence found under 00_raw/ to ground scrutiny against.")

    lens_filter = lens.strip().lower() if lens else None
    data = load_agent_annotation(source)
    known_units = known_requirement_unit_ids(base) if spec["require_unit"] else None
    scrutiny_gaps = validate_scrutiny_gaps(data, grounding_text, lens_filter, mode=mode, known_units=known_units)

    existing = parse_gap_rows(gaps_path.read_text(encoding="utf-8"))
    real_existing = [gap for gap in existing if gap.get("id") != "NONE"]
    existing_ids = {gap["id"] for gap in real_existing}
    req_id = real_existing[0].get("parent", "REQ-001").strip("`") if real_existing else "REQ-001"

    merged_new: list[dict[str, str]] = []
    skipped: list[str] = []
    for gap in scrutiny_gaps:
        if gap["id"] in existing_ids:
            skipped.append(gap["id"])
            continue
        merged_new.append(gap)
        existing_ids.add(gap["id"])

    merged = real_existing + merged_new
    language = _annotation_project_language(project_id, base)
    gaps_path.write_text(render_gaps(project_id, merged, req_id, language), encoding="utf-8")

    store_dir = base / "01_discovery" / str(spec["store_dir"])
    store_dir.mkdir(parents=True, exist_ok=True)
    stored = _unique_path(store_dir / f"{source.stem}.json")
    shutil.copyfile(source, stored)

    report_path = base / "01_discovery" / str(spec["report_name"])
    if is_probe:
        report_text = render_probe_report(project_id, source.stem, merged_new, skipped, data)
    else:
        report_text = render_scrutiny_report(project_id, source.stem, merged_new, skipped, data, lens_filter)
    report_path.write_text(report_text, encoding="utf-8")

    graph_nodes = load_graph(project_id).get("nodes", [])
    node_type = str(spec["node_type"])
    report_id = add_node(
        project_id,
        "DISC",
        node_type,
        report_path,
        f"{spec['node_label']}: {source.stem}",
        domain="product",
    )
    for raw_node in [node for node in graph_nodes if node.get("type") == "raw_input"]:
        add_edge(project_id, raw_node["id"], report_id, str(spec["raw_relation"]))
    for gap_node in [node for node in graph_nodes if node.get("type") == "gap_report"]:
        add_edge(project_id, report_id, gap_node["id"], "raises")

    broker = ContextBroker(project_id)
    broker.index_artifact(
        report_id,
        node_type,
        report_path,
        report_path.read_text(encoding="utf-8"),
        trace_ids=[report_id],
    )
    ledger = refresh_knowledge_ledger(project_id, broker)
    mark_source_processed(project_id, source, f"{spec['origin']}_applied", report_id)

    counts = count_gaps(merged)
    origin = str(spec["origin"])
    counts[str(spec["origin_count_key"])] = sum(1 for gap in merged if gap.get("origin") == origin)
    updates: dict[str, object] = {
        "gap_counts": counts,
        "readiness_stage": readiness_stage_for_counts(counts),
        str(spec["state_key"]): report_id,
        "knowledge_ledger_summary": ledger["payload"]["summary"],
    }
    if counts.get("blocking_open", 0):
        updates["health"] = "DIRTY"
    update_state(project_id, **updates)

    result: dict[str, object] = {
        "project_id": project_id,
        "mode": origin,
        "path": str(gaps_path.as_posix()),
        "report": str(report_path.as_posix()),
        "knowledge_state": str(ledger["md_path"].as_posix()),
        "merged": [gap["id"] for gap in merged_new],
        "skipped_duplicates": skipped,
        "gap_counts": counts,
    }
    if is_probe:
        result["probe_id"] = report_id
        result["implementability_probe_report"] = str(report_path.as_posix())
    else:
        result["scrutiny_id"] = report_id
        result["scrutiny_report"] = str(report_path.as_posix())
    return result


def render_requirement(project_id: str, req_text: str, raw_id: str) -> str:
    return f"""# Requirement Register - {project_id}

## REQ-001 Primary Requirement

- Source: `{raw_id}`
- Status: `draft`
- Domains: product, functional, quality

{req_text}
"""


def resolve_project_language(configured_language: object, text: str) -> str:
    configured = str(configured_language or "auto").lower()
    if configured in {"es", "en"}:
        return configured
    return detect_language(text)


def detect_language(text: str) -> str:
    lowered = text.lower()
    spanish_markers = (
        " objetivo",
        " usuario",
        " usuarios",
        " alcance",
        " criterio",
        " criterios",
        " calidad",
        " requerimiento",
        " pantalla",
        " flujo",
        " diseño",
        " tecnología",
        " integración",
        " validación",
        " negocio",
        " fuente",
        " datos",
        " qué",
        " cómo",
        " para ",
        " con ",
        " debe ",
        " deberán ",
    )
    english_markers = (
        " goal",
        " user",
        " users",
        " scope",
        " acceptance",
        " quality",
        " requirement",
        " screen",
        " flow",
        " design",
        " technology",
        " integration",
        " validation",
        " business",
        " source",
        " data",
        " what",
        " how",
        " should",
        " must",
    )
    spanish_score = sum(1 for marker in spanish_markers if marker in f" {lowered} ")
    english_score = sum(1 for marker in english_markers if marker in f" {lowered} ")
    if any(char in lowered for char in "áéíóúñ¿¡"):
        spanish_score += 2
    return "es" if spanish_score > english_score else "en"


def no_gaps_text(language: str) -> str:
    if language == "es":
        return """## No se detectaron gaps abiertos

El escaneo determinístico de discovery no detectó gaps bloqueantes ni de seguimiento. Si el cliente o los equipos de dominio tienen contexto adicional, agregarlo en `Notas adicionales` y devolverlo como input de cambio.
"""
    return """## No Open Gaps Detected

No blocking or follow-up gaps were detected by the deterministic discovery scan. If the client or domain teams have additional context, add it under `Additional Notes` and send it back as a change input.
"""


def source_consulted_text(language: str) -> str:
    return "Carpetas de contexto e input fuente." if language == "es" else "Context folders and source input."


def none_gap_row(language: str) -> str:
    if language == "es":
        return "| NONE | Todos | none | CLOSED | N/A | No se detectaron gaps bloqueantes por escaneo determinístico. | N/A | Input fuente. | N/A | checklist | N/A | N/A |"
    return "| NONE | All | none | CLOSED | N/A | No blocking gaps detected by deterministic scan. | N/A | Source input. | N/A | checklist | N/A | N/A |"


def gap_trace_row(gap: dict[str, str], req_id: str, language: str) -> str:
    cells = [
        gap["id"],
        gap.get("lens", lens_for_gap(gap["id"])),
        gap["severity"],
        gap.get("status", "OPEN"),
        f"`{req_id}`",
        description_for_gap(gap, language),
        gap.get("question") or question_for_gap(gap["id"], language),
        source_consulted_text(language),
        gap.get("evidence_mention") or "N/A",
        gap.get("origin", "checklist"),
        gap.get("resolution_note") or "N/A",
        gap.get("unit") or "N/A",
    ]
    return "| " + " | ".join(cells) + " |"


def description_for_gap(gap: dict[str, str], language: str = "en") -> str:
    if language != "es":
        return gap["description"]
    descriptions = {
        "GAP-OBJECTIVE": "El objetivo de negocio o resultado esperado no está explícito.",
        "GAP-USERS": "Los usuarios, personas o actores objetivo no están explícitos.",
        "GAP-SCOPE": "Los límites de alcance no están explícitos.",
        "GAP-ACCEPTANCE": "Faltan criterios de aceptación o condiciones de éxito.",
        "GAP-QUALITY": "Las expectativas de calidad o testeabilidad no están explícitas.",
        "GAP-METRIC-SOURCE": "Aparece una métrica cuantitativa sin fuente o baseline explícito.",
        "GAP-TECH-DATA-SOURCE": "La fuente de datos, integración u ownership de sistema no está explícito en el input o contexto técnico.",
        "GAP-TECH-NFR": "No están explícitas restricciones de performance, seguridad, observabilidad u operación.",
        "GAP-DESIGN-FLOW": "El journey de usuario, flujo de pantallas o modelo de interacción no está explícito en el input o contexto de diseño.",
        "GAP-DESIGN-STATES": "No están explícitos los estados requeridos de UI: loading, empty, error y recuperación.",
        "GAP-DESIGN-PROTOTYPE-INPUT": "No queda claro qué debe prototipar o validar Diseño en los flujos de usuario.",
        "GAP-PRODUCT-ASIS-TOBE": "El estado actual y el estado objetivo no están suficientemente claros para comparar impacto.",
        "GAP-BUSINESS-RULES": "Las reglas de negocio, exclusiones o reglas de decisión no están suficientemente explícitas para slicing downstream.",
        "GAP-FRONTEND-SURFACE": "La superficie de implementación frontend no está suficientemente explícita: pantallas, estados, validaciones, copy, roles o bindings de API.",
        "GAP-BACKEND-SURFACE": "La superficie de implementación backend no está suficientemente explícita: capacidades, integraciones, reglas, persistencia, contratos o comportamiento ante fallas.",
        "GAP-TECH-DEEP-DIVE-INPUT": "Tecnología no cuenta con suficiente input para análisis de repositorios, arquitectura, endpoints/eventos, source of truth o riesgos.",
        "GAP-GOVERNANCE-CONSTRAINTS": "No están explícitas restricciones de gobernanza, seguridad, privacidad, compliance u operación.",
        "GAP-DELIVERY-READINESS": "No están explícitas dependencias, ambientes, ownership, fechas o restricciones de rollout.",
        "GAP-BACKLOG-SLICING-READINESS": "No estan explicitas las senales necesarias para slicing de backlog: primer slice de valor, paths, variantes, reglas diferibles o limites de historia.",
        "GAP-BACKLOG-ENABLERS": "No estan claros los enablers transversales validos: trabajo de implementacion frontend/backend o arquitectura que debe construirse antes para soportar funcionalidades confirmadas dentro del boundary del proyecto.",
        "GAP-QUALITY-HANDOFF": "El handoff a Calidad no está suficientemente explícito: flujos críticos, casos borde, datos de prueba, riesgos de regresión o evidencia esperada.",
        "GAP-METRIC-DEFINITION": "Se nombra una métrica, KPI o indicador sin su definición, fórmula, unidad, fuente ni umbral.",
        "GAP-AUTH-MODEL": "Se mencionan autenticación, permisos o roles sin el método de autenticación, el modelo de permisos ni el catálogo de roles.",
    }
    return descriptions.get(gap["id"], gap["description"])


def render_gaps(project_id: str, gaps: list[dict[str, str]], req_id: str, language: str = "en") -> str:
    response_sections = "\n\n".join(render_gap_response_section(gap, req_id, language) for gap in gaps)
    if not response_sections:
        response_sections = no_gaps_text(language)

    rows = "\n".join(gap_trace_row(gap, req_id, language) for gap in gaps)
    if not rows:
        rows = none_gap_row(language)
    if language == "es":
        return f"""# Gaps de Discovery - {project_id}

Versión del documento: `1.0`
Proyecto: `{project_id}`
Requerimiento padre: `{req_id}`
Audiencia: stakeholders del cliente, Producto, Tecnología, Diseño, Calidad y Delivery.
Propósito: recopilar información faltante o ambigua para madurar el requerimiento y poder generar project brief, PRD, specs, backlog, criterios de aceptación y tests.

## Cómo responder

Por favor responder directamente debajo de cada gap. Una respuesta breve sirve si es precisa. Si la respuesta corresponde a otro equipo, indicar el owner y cualquier información parcial disponible.

Formato sugerido de respuesta:

- Respuesta:
- Owner / fuente:
- Evidencia o referencia:
- Estado de decisión: confirmado / pendiente / no aplica

## Secciones para respuesta del cliente

{response_sections}

## Notas adicionales

Agregar cualquier nuevo requerimiento, restricción, decisión, screenshot, diagrama o ejemplo que no haya quedado cubierto arriba.

## Tabla de trazabilidad del framework

Esta tabla se mantiene para trazabilidad y procesamiento automático de Sentinel.

| Gap ID | Lente | Severidad | Estado | Padre | Descripción | Pregunta para cliente/dominio | Fuente consultada | Disparador detectado | Origen | Nota de resolución | Unidad |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
{rows}

## Trazabilidad de resolución

| Gap ID | Fuente de resolución | Seed promovida | Artefactos impactados |
| --- | --- | --- | --- |
| TBD | TBD | TBD | TBD |
"""
    return f"""# Discovery Gaps - {project_id}

Document version: `1.0`
Project: `{project_id}`
Parent requirement: `{req_id}`
Audience: Client stakeholders, Product, Technology, Design, Quality, and Delivery.
Purpose: collect missing or ambiguous information so the requirement can mature into a project brief, PRD, specs, backlog, acceptance criteria, and tests.

## How To Respond

Please answer directly under each gap. A short answer is fine if it is precise. If a question belongs to another team, name the owner and add any known partial answer.

Suggested response format:

- Answer:
- Owner / source:
- Evidence or reference:
- Decision status: confirmed / pending / not applicable

## Client Response Sections

{response_sections}

## Additional Notes

Add any new requirement, constraint, decision, screenshot, diagram, or example that was not covered above.

## Framework Trace Table

This table is kept for Sentinel traceability and automated processing.

| Gap ID | Lens | Severity | Status | Parent | Description | Question For Client/Domain | Source Consulted | Detected Trigger | Origin | Resolution Note | Unit |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
{rows}

## Resolution Trace

| Gap ID | Resolution Source | Promoted Seed | Impacted Artifacts |
| --- | --- | --- | --- |
| TBD | TBD | TBD | TBD |
"""


def evidence_note_for_gap(gap: dict[str, str], language: str = "en") -> str:
    mention = str(gap.get("evidence_mention", "")).strip()
    if not mention:
        return ""
    if language == "es":
        notes = {
            "GAP-DESIGN-FLOW": f'El input menciona "{mention}" pero no describe el journey, la navegación ni el flujo de interacción alrededor.',
            "GAP-DESIGN-STATES": f'El input menciona "{mention}" pero no describe los estados de carga, vacío, error y recuperación.',
            "GAP-DESIGN-PROTOTYPE-INPUT": f'El input menciona "{mention}" pero no indica qué debe prototipar o validar Diseño.',
            "GAP-FRONTEND-SURFACE": f'El input menciona "{mention}" pero no detalla validaciones, roles, copy ni binding de datos de esa superficie.',
            "GAP-BACKEND-SURFACE": f'El input menciona "{mention}" pero no describe contratos, persistencia ni comportamiento ante fallas.',
            "GAP-TECH-DEEP-DIVE-INPUT": f'El input menciona "{mention}" pero no aporta arquitectura, repositorios ni source of truth para profundizar.',
            "GAP-METRIC-SOURCE": f'La métrica "{mention}" aparece sin fuente, baseline ni método de medición.',
            "GAP-METRIC-DEFINITION": f'El input menciona "{mention}" pero no define la métrica: falta fórmula/unidad, fuente o umbral.',
            "GAP-AUTH-MODEL": f'El input menciona "{mention}" pero no describe el método de autenticación, el modelo de permisos ni el catálogo de roles.',
        }
        return notes.get(gap["id"], f'El input menciona "{mention}" pero no describe la información faltante de este gap.')
    notes = {
        "GAP-DESIGN-FLOW": f'The input mentions "{mention}" but does not describe the journey, navigation, or interaction flow around it.',
        "GAP-DESIGN-STATES": f'The input mentions "{mention}" but does not describe loading, empty, error, and recovery states.',
        "GAP-DESIGN-PROTOTYPE-INPUT": f'The input mentions "{mention}" but does not state what Design must prototype or validate.',
        "GAP-FRONTEND-SURFACE": f'The input mentions "{mention}" but does not detail validations, roles, copy, or data binding for that surface.',
        "GAP-BACKEND-SURFACE": f'The input mentions "{mention}" but does not describe contracts, persistence, or failure behavior.',
        "GAP-TECH-DEEP-DIVE-INPUT": f'The input mentions "{mention}" but provides no architecture, repository, or source-of-truth input to deepen it.',
        "GAP-METRIC-SOURCE": f'The metric "{mention}" appears without a source, baseline, or measurement method.',
        "GAP-METRIC-DEFINITION": f'The input mentions "{mention}" but does not define the metric: missing formula/unit, source, or threshold.',
        "GAP-AUTH-MODEL": f'The input mentions "{mention}" but does not describe the auth method, permission model, or role catalog.',
    }
    return notes.get(gap["id"], f'The input mentions "{mention}" but does not describe the missing information for this gap.')


def candidate_options_for_gap(gap: dict[str, str], language: str = "en") -> list[dict[str, str]]:
    """Return cited, non-selected answer candidates for gaps with local evidence."""
    if gap.get("status", "OPEN") == "CLOSED":
        return []
    mention = str(gap.get("evidence_mention", "")).strip()
    if not mention or mention.upper() == "N/A":
        return []
    gap_id = gap["id"]
    title = human_title_for_gap(gap_id, language)
    if language == "es":
        if gap_id == "GAP-METRIC-SOURCE":
            texts = [
                f"Confirmar que `{mention}` es la meta de exito y aportar fuente, baseline, owner y metodo de medicion.",
                f"Tratar `{mention}` como objetivo direccional hasta confirmar fuente/baseline, indicando que evidencia falta.",
            ]
        elif gap_id in {"GAP-DESIGN-STATES", "GAP-FRONTEND-SURFACE"}:
            texts = [
                f"Aplicar el detalle faltante de `{title}` a la superficie mencionada `{mention}`.",
                f"Declarar que `{mention}` queda fuera del alcance MVP y nombrar la alternativa o diferimiento.",
            ]
        else:
            texts = [
                f"Confirmar que `{mention}` esta dentro del alcance y responder el detalle faltante de `{title}`.",
                f"Confirmar que `{mention}` es solo contexto, fuera de alcance o pendiente, y explicitar el limite.",
            ]
        return [{"label": chr(65 + idx), "text": text, "citation": mention} for idx, text in enumerate(texts)]
    if gap_id == "GAP-METRIC-SOURCE":
        texts = [
            f"Confirm `{mention}` is the success target and provide source, baseline, owner, and measurement method.",
            f"Treat `{mention}` as a directional target until source/baseline are confirmed, naming the missing evidence.",
        ]
    elif gap_id in {"GAP-DESIGN-STATES", "GAP-FRONTEND-SURFACE"}:
        texts = [
            f"Apply the missing `{title}` detail to the mentioned surface `{mention}`.",
            f"Declare `{mention}` out of MVP scope and name the alternative or deferral.",
        ]
    else:
        texts = [
            f"Confirm `{mention}` is in scope and answer the missing `{title}` detail.",
            f"Confirm `{mention}` is context-only, out of scope, or pending, and state the boundary.",
        ]
    return [{"label": chr(65 + idx), "text": text, "citation": mention} for idx, text in enumerate(texts)]


def candidate_options_markdown(gap: dict[str, str], language: str = "en") -> str:
    options = candidate_options_for_gap(gap, language)
    if not options:
        return ""
    if language == "es":
        lines = ["Opciones candidatas citadas (no seleccionadas):"]
        for option in options:
            lines.append(f"- Opcion {option['label']}: {option['text']} Cita local: `{option['citation']}`.")
        lines.append("Estas opciones no cierran el gap; el BA/owner debe confirmar una respuesta.")
        return "\n".join(lines)
    lines = ["Cited candidate options (not selected):"]
    for option in options:
        lines.append(f"- Option {option['label']}: {option['text']} Local citation: `{option['citation']}`.")
    lines.append("These options do not close the gap; the BA/owner must confirm an answer.")
    return "\n".join(lines)


def render_gap_response_section(gap: dict[str, str], req_id: str, language: str = "en") -> str:
    gap_id = gap["id"]
    lens = gap.get("lens", lens_for_gap(gap_id))
    evidence_note = evidence_note_for_gap(gap, language)
    evidence_label = "Evidencia que dispara la pregunta:" if language == "es" else "Evidence that triggers the question:"
    evidence_block = f"\n{evidence_label}\n{evidence_note}\n" if evidence_note else ""
    candidate_options = candidate_options_markdown(gap, language)
    candidate_block = f"\n{candidate_options}\n" if candidate_options else ""
    if language == "es":
        return f"""### {gap_id} - {human_title_for_gap(gap_id, language)}

- Lente: `{lens}`
- Severidad: `{gap['severity']}`
- Estado: `{gap.get('status', 'OPEN')}`
- Requerimiento relacionado: `{req_id}`

Descripción breve:
{description_for_gap(gap, language)}
{evidence_block}
Por qué importa (riesgo si queda abierto):
{why_gap_matters(gap_id, language)}

Qué desbloquea esta respuesta:
{unblocks_for_gap(gap_id, language)}

Pregunta:
{gap.get('question') or question_for_gap(gap_id, language)}

Formato de respuesta esperado:
{expected_format_for_gap(gap_id, language)}

Ejemplo de respuesta útil:
{example_response_for_gap(gap_id, language)}
{candidate_block}

Respuesta del cliente / dominio:

- Respuesta:
- Owner / fuente:
- Evidencia o referencia:
- Estado de decisión:
"""
    return f"""### {gap_id} - {human_title_for_gap(gap_id)}

- Lens: `{lens}`
- Severity: `{gap['severity']}`
- Status: `{gap.get('status', 'OPEN')}`
- Related requirement: `{req_id}`

Brief description:
{gap['description']}
{evidence_block}
Why it matters (risk if left open):
{why_gap_matters(gap_id)}

What answering this unblocks:
{unblocks_for_gap(gap_id)}

Question:
{gap.get('question') or question_for_gap(gap_id)}

Expected response format:
{expected_format_for_gap(gap_id)}

Example of a useful answer:
{example_response_for_gap(gap_id)}
{candidate_block}

Client / domain response:

- Answer:
- Owner / source:
- Evidence or reference:
- Decision status:
"""


def human_title_for_gap(gap_id: str, language: str = "en") -> str:
    prd_titles_es = {
        "GAP-PRD-PERSONA-DETAIL": "Detalle de personas para PRD",
        "GAP-PRD-FR-AC": "Requerimientos funcionales y criterios de aceptacion",
        "GAP-PRD-NFR-KPI": "NFRs, KPIs y medicion",
        "GAP-PRD-DEPENDENCIES-ROADMAP": "Dependencias y roadmap",
        "GAP-PRD-ROLLOUT-ENVIRONMENTS": "Rollout y ambientes",
        "GAP-PRD-GLOSSARY-GOVERNANCE": "Glosario y gobernanza",
    }
    prd_titles_en = {
        "GAP-PRD-PERSONA-DETAIL": "PRD Persona Detail",
        "GAP-PRD-FR-AC": "Functional Requirements And ACs",
        "GAP-PRD-NFR-KPI": "NFRs, KPIs, And Measurement",
        "GAP-PRD-DEPENDENCIES-ROADMAP": "Dependencies And Roadmap",
        "GAP-PRD-ROLLOUT-ENVIRONMENTS": "Rollout And Environments",
        "GAP-PRD-GLOSSARY-GOVERNANCE": "Glossary And Governance",
    }
    if language == "es" and gap_id in prd_titles_es:
        return prd_titles_es[gap_id]
    if gap_id in prd_titles_en:
        return prd_titles_en[gap_id]
    if language == "es":
        titles = {
            "GAP-OBJECTIVE": "Resultado esperado",
            "GAP-USERS": "Usuarios y actores",
            "GAP-SCOPE": "Límites de alcance",
            "GAP-ACCEPTANCE": "Señal de aceptación",
            "GAP-QUALITY": "Expectativas de calidad",
            "GAP-METRIC-SOURCE": "Fuente de métrica",
            "GAP-TECH-DATA-SOURCE": "Sistemas y ownership de datos",
            "GAP-TECH-NFR": "Restricciones operativas",
            "GAP-DESIGN-FLOW": "Journey y pantallas",
            "GAP-DESIGN-STATES": "Estados de UX",
            "GAP-DESIGN-PROTOTYPE-INPUT": "Foco del prototipo",
            "GAP-PRODUCT-ASIS-TOBE": "Proceso actual y objetivo",
            "GAP-BUSINESS-RULES": "Reglas de negocio",
            "GAP-FRONTEND-SURFACE": "Superficie frontend",
            "GAP-BACKEND-SURFACE": "Superficie backend",
            "GAP-TECH-DEEP-DIVE-INPUT": "Profundización técnica",
            "GAP-GOVERNANCE-CONSTRAINTS": "Restricciones de gobernanza",
            "GAP-DELIVERY-READINESS": "Preparación de delivery",
            "GAP-BACKLOG-SLICING-READINESS": "Preparacion de slicing de backlog",
            "GAP-BACKLOG-ENABLERS": "Enablers transversales validos",
            "GAP-QUALITY-HANDOFF": "Handoff de calidad",
            "GAP-METRIC-DEFINITION": "Definición de métrica",
            "GAP-AUTH-MODEL": "Modelo de auth y permisos",
        }
        return titles.get(gap_id, "Información necesaria")
    titles = {
        "GAP-OBJECTIVE": "Expected Outcome",
        "GAP-USERS": "Users And Actors",
        "GAP-SCOPE": "Scope Boundaries",
        "GAP-ACCEPTANCE": "Acceptance Signal",
        "GAP-QUALITY": "Quality Expectations",
        "GAP-METRIC-SOURCE": "Metric Source",
        "GAP-TECH-DATA-SOURCE": "Systems And Data Ownership",
        "GAP-TECH-NFR": "Operational Constraints",
        "GAP-DESIGN-FLOW": "User Journey And Screens",
        "GAP-DESIGN-STATES": "UX States",
        "GAP-DESIGN-PROTOTYPE-INPUT": "Prototype Focus",
        "GAP-PRODUCT-ASIS-TOBE": "Current And Target Process",
        "GAP-BUSINESS-RULES": "Business Rules",
        "GAP-FRONTEND-SURFACE": "Frontend Surface",
        "GAP-BACKEND-SURFACE": "Backend Surface",
        "GAP-TECH-DEEP-DIVE-INPUT": "Technology Deep Dive",
        "GAP-GOVERNANCE-CONSTRAINTS": "Governance Constraints",
        "GAP-DELIVERY-READINESS": "Delivery Readiness",
        "GAP-BACKLOG-SLICING-READINESS": "Backlog Slicing Readiness",
        "GAP-BACKLOG-ENABLERS": "Valid Cross-Cutting Enablers",
        "GAP-QUALITY-HANDOFF": "Quality Handoff",
        "GAP-METRIC-DEFINITION": "Metric Definition",
        "GAP-AUTH-MODEL": "Auth And Permission Model",
    }
    return titles.get(gap_id, "Information Needed")


def why_gap_matters(gap_id: str, language: str = "en") -> str:
    prd_reasons_es = {
        "GAP-PRD-PERSONA-DETAIL": "El PRD necesita personas con objetivos, dolores, frecuencia y habilidad para orientar experiencia, adopcion y soporte.",
        "GAP-PRD-FR-AC": "El PRD debe listar requerimientos funcionales con criterios de aceptacion trazables para que backlog y QA no inventen alcance.",
        "GAP-PRD-NFR-KPI": "NFRs y KPIs con targets, metodo de medicion y ventana temporal permiten validar valor y calidad objetivamente.",
        "GAP-PRD-DEPENDENCIES-ROADMAP": "Dependencias, owners, MVP y roadmap sostienen la planificacion y evitan historias bloqueadas por supuestos.",
        "GAP-PRD-ROLLOUT-ENVIRONMENTS": "Rollout, ambientes y restricciones de release evitan que specs y backlog inventen secuencia o condiciones de salida.",
        "GAP-PRD-GLOSSARY-GOVERNANCE": "Glosario, restricciones mandatorias, pending inputs y audit trail preservan entendimiento compartido y trazabilidad.",
    }
    prd_reasons_en = {
        "GAP-PRD-PERSONA-DETAIL": "The PRD needs personas with goals, pain points, frequency, and proficiency to guide experience, adoption, and support decisions.",
        "GAP-PRD-FR-AC": "The PRD must list functional requirements with traceable acceptance criteria so backlog and QA do not invent scope.",
        "GAP-PRD-NFR-KPI": "NFRs and KPIs with targets, measurement method, and timeframe make value and quality objectively verifiable.",
        "GAP-PRD-DEPENDENCIES-ROADMAP": "Dependencies, owners, MVP, and roadmap support planning and prevent stories from being blocked by assumptions.",
        "GAP-PRD-ROLLOUT-ENVIRONMENTS": "Rollout, environments, and release constraints prevent specs and backlog from inventing sequencing or exit conditions.",
        "GAP-PRD-GLOSSARY-GOVERNANCE": "Glossary, mandatory constraints, pending inputs, and audit trail preserve shared understanding and traceability.",
    }
    if language == "es" and gap_id in prd_reasons_es:
        return prd_reasons_es[gap_id]
    if gap_id in prd_reasons_en:
        return prd_reasons_en[gap_id]
    if language == "es":
        reasons = {
            "GAP-OBJECTIVE": "Sin el resultado esperado, los agentes downstream podrían optimizar la solución pedida en lugar del objetivo real de negocio.",
            "GAP-USERS": "Diseño, permisos, journeys, criterios de aceptación y rollout pueden cambiar según quién usa u opera la capacidad.",
            "GAP-SCOPE": "Los límites claros evitan que PRD, specs y backlog incluyan trabajo no previsto.",
            "GAP-ACCEPTANCE": "Calidad e implementación necesitan condiciones observables para saber cuándo el requerimiento está terminado.",
            "GAP-QUALITY": "Las expectativas de calidad orientan el análisis de riesgo, la profundidad de pruebas y la evidencia requerida.",
            "GAP-METRIC-SOURCE": "Las métricas necesitan fuente o baseline para medir el éxito de manera consistente.",
            "GAP-TECH-DATA-SOURCE": "Tecnología necesita suficiente contexto de sistemas y ownership para analizar arquitectura sin inventar integraciones.",
            "GAP-TECH-NFR": "Las restricciones operativas afectan arquitectura, implementación, monitoreo y readiness de salida.",
            "GAP-DESIGN-FLOW": "Diseño necesita journeys y pantallas afectadas para crear flujos o prototipos significativos.",
            "GAP-DESIGN-STATES": "Los estados UX faltantes suelen convertirse en ambigüedad de implementación o casos borde sin testear.",
            "GAP-DESIGN-PROTOTYPE-INPUT": "Un prototipo solo es útil si Diseño sabe qué decisión, flujo o interacción debe validar.",
            "GAP-PRODUCT-ASIS-TOBE": "El delta entre comportamiento actual y objetivo guía el análisis de impacto y el slicing de backlog.",
            "GAP-BUSINESS-RULES": "Las reglas y excepciones determinan validaciones, casos borde y criterios de aceptación.",
            "GAP-FRONTEND-SURFACE": "Frontend necesita superficies, estados, copy y bindings afectados antes de estimar o implementar responsablemente.",
            "GAP-BACKEND-SURFACE": "Backend necesita contexto de capacidades, integraciones, persistencia y comportamiento ante fallas antes de diseñar servicios.",
            "GAP-TECH-DEEP-DIVE-INPUT": "Los agentes técnicos necesitan dirección suficiente para inspeccionar repositorios, componentes, endpoints y riesgos eficientemente.",
            "GAP-GOVERNANCE-CONSTRAINTS": "Seguridad, privacidad, compliance y auditoría pueden cambiar diseño, implementación y testing.",
            "GAP-DELIVERY-READINESS": "Dependencias, owners, ambientes y fechas determinan secuencia y factibilidad de salida.",
            "GAP-BACKLOG-SLICING-READINESS": "El backlog necesita saber cual es el primer slice de valor, que variantes pueden diferirse y donde no conviene cortar por debajo del valor.",
            "GAP-BACKLOG-ENABLERS": "Los enablers transversales solo son validos si son implementacion previa/cross que soporta funcionalidad confirmada dentro del boundary del proyecto.",
            "GAP-QUALITY-HANDOFF": "QA necesita flujos críticos, casos borde, datos y expectativas de evidencia para profundizar cobertura.",
            "GAP-METRIC-DEFINITION": "Una métrica nombrada sin definición, fuente ni umbral no es medible ni comprometible y arrastra ambigüedad a KPIs y criterios de éxito.",
            "GAP-AUTH-MODEL": "Sin método de autenticación, modelo de permisos ni catálogo de roles, la superficie de acceso queda indefinida para diseño, backend y seguridad.",
        }
        return reasons.get(gap_id, "Esta información es necesaria para evitar supuestos en artefactos downstream.")
    reasons = {
        "GAP-OBJECTIVE": "Without the expected outcome, downstream agents may optimize for the requested feature instead of the real business result.",
        "GAP-USERS": "Design, permissions, journeys, acceptance criteria, and rollout can change depending on who uses or operates the capability.",
        "GAP-SCOPE": "Clear boundaries prevent the PRD, specs, and backlog from including unintended work.",
        "GAP-ACCEPTANCE": "Quality and implementation agents need observable conditions to know when the requirement is done.",
        "GAP-QUALITY": "Quality expectations guide risk analysis, test depth, and required evidence.",
        "GAP-METRIC-SOURCE": "Metrics need a source or baseline so success can be measured consistently.",
        "GAP-TECH-DATA-SOURCE": "Technology needs enough system and ownership context to analyze architecture without inventing integrations.",
        "GAP-TECH-NFR": "Operational constraints affect architecture, implementation choices, monitoring, and release readiness.",
        "GAP-DESIGN-FLOW": "Design needs affected journeys and screens to create meaningful flows or prototypes.",
        "GAP-DESIGN-STATES": "Missing UX states often become implementation ambiguity or untested edge cases.",
        "GAP-DESIGN-PROTOTYPE-INPUT": "A prototype is useful only if Design knows what decision, flow, or interaction it must validate.",
        "GAP-PRODUCT-ASIS-TOBE": "The delta between current and target behavior drives impact analysis and backlog slicing.",
        "GAP-BUSINESS-RULES": "Rules and exceptions determine validations, edge cases, and acceptance criteria.",
        "GAP-FRONTEND-SURFACE": "Frontend agents need affected surfaces, states, copy, and bindings before estimating or implementing responsibly.",
        "GAP-BACKEND-SURFACE": "Backend agents need capability, integration, persistence, and failure-behavior context before designing services.",
        "GAP-TECH-DEEP-DIVE-INPUT": "Technical agents need enough direction to inspect repositories, components, endpoints, and risks efficiently.",
        "GAP-GOVERNANCE-CONSTRAINTS": "Security, privacy, compliance, and audit constraints can change design, implementation, and testing.",
        "GAP-DELIVERY-READINESS": "Dependencies, owners, environments, and timing determine sequencing and release feasibility.",
        "GAP-BACKLOG-SLICING-READINESS": "Backlog needs the first value slice, deferrable variants, and the boundary where splitting smaller would stop producing value.",
        "GAP-BACKLOG-ENABLERS": "Cross-cutting enablers are valid only when they are advance/cross implementation work that supports confirmed functionality inside the project boundary.",
        "GAP-QUALITY-HANDOFF": "QA needs critical flows, edge cases, data, and evidence expectations to deepen coverage.",
        "GAP-METRIC-DEFINITION": "A metric named without a definition, source, or threshold is not measurable or commitable and drags ambiguity into KPIs and success criteria.",
        "GAP-AUTH-MODEL": "Without an auth method, permission model, or role catalog, the access surface stays undefined for design, backend, and security.",
    }
    return reasons.get(gap_id, "This information is needed to avoid assumptions in downstream artifacts.")


def example_response_for_gap(gap_id: str, language: str = "en") -> str:
    prd_examples_es = {
        "GAP-PRD-PERSONA-DETAIL": "Persona primaria: operador central. Objetivo: resolver casos sin TI. Dolor: proceso manual riesgoso. Frecuencia: diaria. Habilidad: herramienta interna avanzada.",
        "GAP-PRD-FR-AC": "FR-01: el sistema debe listar elementos pendientes. AC: Given existen pendientes, When el operador consulta, Then ve ID, estado, responsable y fecha con fuente trazable.",
        "GAP-PRD-NFR-KPI": "NFR: auditoria disponible por 2 anios. KPI: 0 operaciones incorrectas, medido por incidentes post-release diarios durante el primer mes.",
        "GAP-PRD-DEPENDENCIES-ROADMAP": "MVP: consulta, regla principal y auditoria. Dependencias: servicio X owner Equipo A, copy owner Diseno, credenciales owner Seguridad. Fase 2: reportes.",
        "GAP-PRD-ROLLOUT-ENVIRONMENTS": "Rollout: feature flag primero en ambiente staging, luego piloto con supervisores. Produccion requiere ventana aprobada y plan de rollback.",
        "GAP-PRD-GLOSSARY-GOVERNANCE": "Glosario: 'estado grisado' significa no operable. Restriccion: no exponer datos sensibles en logs. Pending input: owner de metrica.",
    }
    prd_examples_en = {
        "GAP-PRD-PERSONA-DETAIL": "Primary persona: central operator. Goal: resolve cases without IT. Pain: risky manual process. Frequency: daily. Proficiency: advanced internal tool.",
        "GAP-PRD-FR-AC": "FR-01: the system must list pending items. AC: Given pending items exist, When the operator opens the list, Then ID, status, owner, and date are visible with source trace.",
        "GAP-PRD-NFR-KPI": "NFR: audit records available for 2 years. KPI: 0 incorrect operations, measured through daily post-release incidents during month one.",
        "GAP-PRD-DEPENDENCIES-ROADMAP": "MVP: query, main rule, and audit. Dependencies: service X owner Team A, copy owner Design, credentials owner Security. Phase 2: reporting.",
        "GAP-PRD-ROLLOUT-ENVIRONMENTS": "Rollout: feature flag first in staging, then pilot with supervisors. Production requires approved window and rollback plan.",
        "GAP-PRD-GLOSSARY-GOVERNANCE": "Glossary: 'disabled state' means not operable. Constraint: do not expose sensitive data in logs. Pending input: metric owner.",
    }
    if language == "es" and gap_id in prd_examples_es:
        return prd_examples_es[gap_id]
    if gap_id in prd_examples_en:
        return prd_examples_en[gap_id]
    if language == "es":
        examples = {
            "GAP-OBJECTIVE": "El objetivo es reducir el tiempo de revisión manual de analistas operativos mostrando casos de alto riesgo antes de la reunión diaria.",
            "GAP-USERS": "Usuarios primarios: analistas de operaciones. Supervisores solo revisan estado resumido. Compliance consume evidencia de auditoría pero no usa la pantalla.",
            "GAP-SCOPE": "In scope: indicador de riesgo en dashboard diario. Out of scope: reportes históricos, facturación y planificación de dotación. Los filtros existentes deben mantenerse.",
            "GAP-ACCEPTANCE": "Dado que una cola tiene casos por encima del umbral de SLA, cuando carga el dashboard, entonces la cola se marca como alto riesgo y el analista puede identificarla sin abrir el detalle.",
            "GAP-QUALITY": "QA debe cubrir happy path, sin datos, datos desactualizados, falla de servicio externo y permisos insuficientes.",
            "GAP-METRIC-SOURCE": "El baseline sale del reporte semanal de operaciones, owner Support Ops; el target es detectar colas de alto riesgo antes de las 9:30 AM.",
            "GAP-TECH-DATA-SOURCE": "Reutilizar `GET /queues`; modificarlo para incluir `slaRisk`. La fuente de verdad de riesgo es Case Management, owner Operations Platform.",
            "GAP-TECH-NFR": "La respuesta del dashboard debe mantenerse debajo de 2 segundos p95. Loguear fallas de cálculo y exponer métricas de datos faltantes/desactualizados.",
            "GAP-DESIGN-FLOW": "El indicador aparece en la lista del dashboard diario. Los usuarios entran por Home > Operaciones > Colas diarias y deciden qué cola revisar primero.",
            "GAP-DESIGN-STATES": "Mostrar skeleton durante carga, estado neutral sin colas, warning para datos desactualizados y error genérico existente ante fallas de servicio.",
            "GAP-DESIGN-PROTOTYPE-INPUT": "Prototipar la lista del dashboard con estados normal, alto riesgo, datos desactualizados y vacío para validar escaneabilidad con analistas.",
            "GAP-PRODUCT-ASIS-TOBE": "Hoy los analistas abren cada cola para inferir riesgo. To-be: la lista muestra riesgo directamente para priorizar antes de abrir detalle.",
            "GAP-BUSINESS-RULES": "Una cola es de alto riesgo cuando más de 10 casos están a menos de 30 minutos de breach de SLA o cuando cualquier caso ya está vencido.",
            "GAP-FRONTEND-SURFACE": "Superficie afectada: dashboard diario de Operaciones. Agregar badge de riesgo, preservar filtros existentes, bindear `slaRisk` y trackear `risk_badge_clicked`.",
            "GAP-BACKEND-SURFACE": "Backend enriquece summaries de cola con SLA risk, maneja indisponibilidad de Case Management como `riskUnknown` y no persiste riesgo localmente.",
            "GAP-TECH-DEEP-DIVE-INPUT": "Tecnología debe revisar `ops-dashboard-web`, `queue-summary-api` y documentación de integración de Case Management antes de proponer arquitectura.",
            "GAP-GOVERNANCE-CONSTRAINTS": "No agregar PII en la lista del dashboard. Logs de auditoría no deben incluir nombres de clientes ni números de documento.",
            "GAP-DELIVERY-READINESS": "Dependencia: Case Management debe exponer umbral de SLA antes del 15 de junio. Rollout con feature flag primero para supervisores de Operaciones.",
            "GAP-BACKLOG-SLICING-READINESS": "Primer slice: usuario autorizado ve un caso de alto riesgo con datos vigentes. Diferir exportacion, bulk actions y reglas avanzadas. No dividir en crear boton/endpoint/tabla porque ninguna parte sola valida valor.",
            "GAP-BACKLOG-ENABLERS": "Enabler valido: soporte backend compartido para consultas de riesgo y permisos por rol del flujo, con validacion objetiva. No enabler: 'asegurar que una herramienta interna sea accesible'; eso es precondicion operacional.",
            "GAP-QUALITY-HANDOFF": "Tests críticos: alto riesgo, riesgo normal, datos de fuente desactualizados, permisos faltantes, cola vacía y regresión de filtros existentes.",
            "GAP-METRIC-DEFINITION": "La métrica 'tiempo de resolución' se define como promedio de horas entre apertura y cierre, fuente Case Management, baseline 8h, umbral objetivo 6h.",
            "GAP-AUTH-MODEL": "Autenticación vía SSO corporativo (OIDC). Permisos por RBAC con roles 'lead' (lectura total) y 'agent' (solo su cola); catálogo de roles owner Seguridad.",
        }
        return examples.get(gap_id, "Una respuesta útil indica decisión, owner/fuente, evidencia y si está confirmado o pendiente.")
    examples = {
        "GAP-OBJECTIVE": "The goal is to reduce manual review time for operations analysts by making high-risk cases visible before the daily standup.",
        "GAP-USERS": "Primary users are operations analysts. Supervisors only review summary status. The compliance team consumes audit evidence but does not use the screen.",
        "GAP-SCOPE": "In scope: daily dashboard risk indicator. Out of scope: historical reporting, billing, and workforce scheduling. Existing filters must keep working.",
        "GAP-ACCEPTANCE": "Given a queue has cases above the SLA threshold, when the dashboard loads, then the queue is marked as high risk and the analyst can identify it without opening case details.",
        "GAP-QUALITY": "QA should cover happy path, no data, stale data, external service failure, and permission denied scenarios.",
        "GAP-METRIC-SOURCE": "Baseline comes from the weekly operations report owned by Support Ops; target is to detect high-risk queues before 9:30 AM daily.",
        "GAP-TECH-DATA-SOURCE": "Reuse `GET /queues`; modify it to include `slaRisk`. Risk source of truth is the Case Management service owned by Operations Platform.",
        "GAP-TECH-NFR": "Dashboard response should stay under 2 seconds p95. Log risk-calculation failures and expose metrics for missing/stale source data.",
        "GAP-DESIGN-FLOW": "The indicator appears on the daily dashboard list. Users enter from Home > Operations > Daily queues and decide which queue to inspect first.",
        "GAP-DESIGN-STATES": "Show skeleton while loading, neutral state when there are no queues, warning state for stale data, and existing generic error for service failures.",
        "GAP-DESIGN-PROTOTYPE-INPUT": "Prototype the dashboard list with normal, high-risk, stale-data, and empty states to validate scanability with analysts.",
        "GAP-PRODUCT-ASIS-TOBE": "Today analysts open each queue to infer risk. To-be: the list shows risk directly so they can prioritize before opening details.",
        "GAP-BUSINESS-RULES": "A queue is high risk when more than 10 cases are within 30 minutes of SLA breach or any case is already breached.",
        "GAP-FRONTEND-SURFACE": "Affected surface is the Daily Operations dashboard. Add risk badge, preserve existing filters, bind to `slaRisk`, and track `risk_badge_clicked`.",
        "GAP-BACKEND-SURFACE": "Backend enriches queue summaries with SLA risk, handles unavailable Case Management data as `riskUnknown`, and does not persist risk locally.",
        "GAP-TECH-DEEP-DIVE-INPUT": "Technology should inspect `ops-dashboard-web`, `queue-summary-api`, and Case Management integration docs before proposing architecture.",
        "GAP-GOVERNANCE-CONSTRAINTS": "No PII should be added to the dashboard list. Audit logs must not include customer names or document numbers.",
        "GAP-DELIVERY-READINESS": "Dependency: Case Management team must expose SLA threshold by June 15. Rollout behind feature flag for Operations supervisors first.",
        "GAP-BACKLOG-SLICING-READINESS": "First slice: authorized user sees one high-risk case with current data. Defer export, bulk actions, and advanced rules. Do not split into button/endpoint/table because none validates value alone.",
        "GAP-BACKLOG-ENABLERS": "Valid enabler: shared backend support for risk queries and role permissions for the flow, with objective validation. Not an enabler: 'make an internal tool accessible'; that is an operational precondition.",
        "GAP-QUALITY-HANDOFF": "Critical tests: high risk, normal risk, stale source data, missing permissions, empty queue, and regression of existing filters.",
        "GAP-METRIC-DEFINITION": "The 'resolution time' metric is the average hours between open and close, source Case Management, baseline 8h, target threshold 6h.",
        "GAP-AUTH-MODEL": "Authentication via corporate SSO (OIDC). Permissions via RBAC with roles 'lead' (full read) and 'agent' (own queue only); role catalog owned by Security.",
    }
    return examples.get(gap_id, "A useful answer names the decision, owner/source, evidence, and whether the answer is confirmed or pending.")


# --- IMP-022: gaps as elicitation, not as statement ---------------------------
#
# A gap question is far more answerable when the client/domain also sees WHY it
# matters (risk if left open), WHAT it unblocks (the downstream brief/PRD/spec
# section that consumes the answer), and the EXPECTED FORMAT of a closing answer.
# `why_gap_matters` already covers the first factor; the two functions below add
# the other two. The gap->section mapping inverts what lived implicitly in the
# "PRD Coverage Readiness" and "Backlog Readiness Signals" tables (maturity.py)
# and moves it to the gap's origin. These render in both gaps.md response
# sections and the domain context-request packs. The trace table is unchanged,
# so render_gaps -> parse_gap_rows stays a clean roundtrip.


def unblocks_for_gap(gap_id: str, language: str = "en") -> str:
    """What downstream brief/PRD/spec section the gap's answer unblocks."""
    if language == "es":
        unblocks = {
            "GAP-OBJECTIVE": "Sección 1 del brief (identidad y objetivo) y el problem statement del PRD; todo lo downstream optimiza hacia esto.",
            "GAP-USERS": "Sección 2 del brief (actores) y las personas del PRD; condiciona journeys, permisos y criterios de aceptación.",
            "GAP-SCOPE": "Los límites de alcance del brief y el alcance/no-objetivos del PRD; evita que specs y backlog absorban trabajo no previsto.",
            "GAP-ACCEPTANCE": "Los criterios de aceptación del PRD, las ACs de specs y los test cases de Calidad.",
            "GAP-QUALITY": "Los NFRs del PRD y la estrategia de handoff/testing de Calidad.",
            "GAP-METRIC-SOURCE": "Los KPIs del brief y la sección de NFRs/KPIs y medición del PRD.",
            "GAP-TECH-DATA-SOURCE": "La sección 5 del brief (técnica) y los boundaries de sistema y ownership de datos de specs.",
            "GAP-TECH-NFR": "Los NFRs del PRD y la sección de restricciones operativas de specs.",
            "GAP-DESIGN-FLOW": "La sección 4 del brief (diseño), los flujos UX de specs y el context pack de Diseño.",
            "GAP-DESIGN-STATES": "Los estados UX de specs y la cobertura de casos borde de Calidad.",
            "GAP-DESIGN-PROTOTYPE-INPUT": "El context pack de Diseño y el alcance del prototipo.",
            "GAP-PRODUCT-ASIS-TOBE": "La sección 3 del brief (as-is/to-be) y el slicing del backlog.",
            "GAP-BUSINESS-RULES": "Los FRs/ACs del PRD, las reglas de negocio de specs y los casos borde de Calidad.",
            "GAP-FRONTEND-SURFACE": "La superficie frontend de specs y el context pack Frontend / historias del backlog.",
            "GAP-BACKEND-SURFACE": "La superficie backend de specs y el context pack Backend / historias del backlog.",
            "GAP-TECH-DEEP-DIVE-INPUT": "El context pack de Tecnología y la arquitectura de solución (SAD).",
            "GAP-GOVERNANCE-CONSTRAINTS": "La sección 6 del brief (gobernanza) y la sección de gobernanza del PRD.",
            "GAP-DELIVERY-READINESS": "El plan de ejecución del PRD y la secuencia/rollout del backlog.",
            "GAP-BACKLOG-SLICING-READINESS": "El primer slice de valor y los límites de slicing del backlog.",
            "GAP-BACKLOG-ENABLERS": "Los enablers transversales del backlog.",
            "GAP-QUALITY-HANDOFF": "Los test cases y el coverage map de Calidad.",
            "GAP-PRD-PERSONA-DETAIL": "La sección de Personas del PRD.",
            "GAP-PRD-FR-AC": "La sección de Requerimientos Funcionales del PRD (FRs con criterios de aceptación).",
            "GAP-PRD-NFR-KPI": "La sección de NFRs y KPIs del PRD.",
            "GAP-PRD-DEPENDENCIES-ROADMAP": "El plan de ejecución del PRD (dependencias, MVP, roadmap).",
            "GAP-PRD-ROLLOUT-ENVIRONMENTS": "El plan de ejecución del PRD (rollout, ambientes y restricciones de release).",
            "GAP-PRD-GLOSSARY-GOVERNANCE": "La sección de Gobernanza del PRD (glosario, restricciones, audit trail).",
            "GAP-METRIC-DEFINITION": "Los KPIs del brief y la sección de NFRs/KPIs y medición del PRD.",
            "GAP-AUTH-MODEL": "Los actores/permisos del brief, la sección de gobernanza/seguridad del PRD y la superficie de acceso de specs.",
        }
        return unblocks.get(gap_id, "Una sección downstream de brief/PRD/spec que hoy no tiene evidencia confirmada para consumir.")
    unblocks = {
        "GAP-OBJECTIVE": "Brief section 1 (identity & objective) and the PRD problem statement; everything downstream optimizes toward this.",
        "GAP-USERS": "Brief section 2 (actors) and PRD personas; it drives journeys, permissions, and acceptance criteria.",
        "GAP-SCOPE": "Brief scope boundaries and PRD scope/non-goals; it keeps specs and backlog from absorbing unintended work.",
        "GAP-ACCEPTANCE": "PRD acceptance criteria, specs ACs, and Quality test cases.",
        "GAP-QUALITY": "PRD NFRs and the Quality handoff/test strategy.",
        "GAP-METRIC-SOURCE": "Brief KPIs and the PRD NFRs/KPIs and measurement section.",
        "GAP-TECH-DATA-SOURCE": "Brief section 5 (technical) and the specs system boundaries and data ownership.",
        "GAP-TECH-NFR": "PRD NFRs and the specs operational-constraints section.",
        "GAP-DESIGN-FLOW": "Brief section 4 (design), specs UX flows, and the Design context pack.",
        "GAP-DESIGN-STATES": "Specs UX states and Quality edge-case coverage.",
        "GAP-DESIGN-PROTOTYPE-INPUT": "The Design context pack and the prototype scope.",
        "GAP-PRODUCT-ASIS-TOBE": "Brief section 3 (as-is/to-be) and backlog slicing.",
        "GAP-BUSINESS-RULES": "PRD functional requirements/ACs, specs business rules, and Quality edge cases.",
        "GAP-FRONTEND-SURFACE": "The specs frontend surface and the Frontend context pack / backlog stories.",
        "GAP-BACKEND-SURFACE": "The specs backend surface and the Backend context pack / backlog stories.",
        "GAP-TECH-DEEP-DIVE-INPUT": "The Technology context pack and the solution architecture (SAD).",
        "GAP-GOVERNANCE-CONSTRAINTS": "Brief section 6 (governance) and the PRD governance section.",
        "GAP-DELIVERY-READINESS": "The PRD execution plan and backlog sequencing/rollout.",
        "GAP-BACKLOG-SLICING-READINESS": "The backlog's first value slice and slice boundaries.",
        "GAP-BACKLOG-ENABLERS": "The backlog's cross-cutting enablers.",
        "GAP-QUALITY-HANDOFF": "Quality test cases and the coverage map.",
        "GAP-PRD-PERSONA-DETAIL": "The PRD Personas section.",
        "GAP-PRD-FR-AC": "The PRD Functional Requirements section (FRs with acceptance criteria).",
        "GAP-PRD-NFR-KPI": "The PRD NFRs and KPIs section.",
        "GAP-PRD-DEPENDENCIES-ROADMAP": "The PRD Execution Plan (dependencies, MVP, roadmap).",
        "GAP-PRD-ROLLOUT-ENVIRONMENTS": "The PRD Execution Plan (rollout, environments, and release constraints).",
        "GAP-PRD-GLOSSARY-GOVERNANCE": "The PRD Governance section (glossary, constraints, audit trail).",
        "GAP-METRIC-DEFINITION": "Brief KPIs and the PRD NFRs/KPIs and measurement section.",
        "GAP-AUTH-MODEL": "Brief actors/permissions, the PRD governance/security section, and the specs access surface.",
    }
    return unblocks.get(gap_id, "A downstream brief/PRD/spec section that currently has no confirmed evidence to consume.")


def expected_format_for_gap(gap_id: str, language: str = "en") -> str:
    """The shape of an answer that closes the gap (distinct from a worked example)."""
    if language == "es":
        formats = {
            "GAP-OBJECTIVE": "Una frase que nombre el resultado de negocio (no la feature) y cómo se reconoce el éxito.",
            "GAP-USERS": "Lista de actores primarios/secundarios con rol e indicando si usan u operan la capacidad.",
            "GAP-SCOPE": "Bullets de in-scope vs out-of-scope y qué debe seguir funcionando.",
            "GAP-ACCEPTANCE": "Uno o más enunciados EARS o Dado/Cuando/Entonces con condiciones observables. Ejemplo EARS: Cuando ocurre <disparador>, el sistema debe <respuesta observable>.",
            "GAP-QUALITY": "Expectativas de calidad como bullets: áreas de riesgo, profundidad de pruebas y evidencia requerida.",
            "GAP-METRIC-SOURCE": "Nombre de la métrica + fuente/owner del baseline + valor objetivo + ventana de medición.",
            "GAP-TECH-DATA-SOURCE": "Sistemas/endpoints involucrados, source of truth y equipo owner.",
            "GAP-TECH-NFR": "NFRs nombrados con umbrales concretos (latencia, retención, disponibilidad) y cómo se observan.",
            "GAP-DESIGN-FLOW": "Punto de entrada y journey paso a paso hasta la(s) pantalla(s) afectada(s).",
            "GAP-DESIGN-STATES": "Los estados de carga, vacío, error y recuperación de la superficie.",
            "GAP-DESIGN-PROTOTYPE-INPUT": "La decisión/flujo/interacción que el prototipo debe validar.",
            "GAP-PRODUCT-ASIS-TOBE": "Comportamiento actual vs objetivo, expresado como delta.",
            "GAP-BUSINESS-RULES": "Reglas en formato EARS cuando describen comportamiento: Si <condición/regla>, entonces el sistema debe <respuesta>; incluir umbrales y excepciones.",
            "GAP-FRONTEND-SURFACE": "Superficie(s) afectada(s), estados, validaciones, copy y eventos de analytics.",
            "GAP-BACKEND-SURFACE": "Capacidades, contratos, persistencia/source of truth y comportamiento ante fallas.",
            "GAP-TECH-DEEP-DIVE-INPUT": "Repositorios/componentes, endpoints y source of truth a inspeccionar.",
            "GAP-GOVERNANCE-CONSTRAINTS": "Restricciones nombradas de seguridad/privacidad/compliance/auditoría que aplican.",
            "GAP-DELIVERY-READINESS": "Dependencias con owners, ambientes, fechas y enfoque de rollout.",
            "GAP-BACKLOG-SLICING-READINESS": "El primer slice de valor más qué se difiere y dónde no conviene cortar.",
            "GAP-BACKLOG-ENABLERS": "Cada enabler con el boundary de capacidad que soporta y la evidencia objetiva de completitud.",
            "GAP-QUALITY-HANDOFF": "Flujos críticos, casos borde, datos de prueba y expectativas de evidencia.",
            "GAP-PRD-PERSONA-DETAIL": "Por persona: objetivo, dolores, frecuencia y habilidad.",
            "GAP-PRD-FR-AC": "FR-NN con statement EARS trazable (Cuando/Si/Mientras/Donde/El sistema debe...) más criterio de aceptación y prioridad.",
            "GAP-PRD-NFR-KPI": "NFR/KPI con target, método de medición y ventana temporal.",
            "GAP-PRD-DEPENDENCIES-ROADMAP": "MVP, dependencias con owner y fases del roadmap.",
            "GAP-PRD-ROLLOUT-ENVIRONMENTS": "Ambientes objetivo, estrategia de rollout, restricciones de release y criterio de rollback.",
            "GAP-PRD-GLOSSARY-GOVERNANCE": "Términos de glosario, restricciones mandatorias y pending inputs con owner.",
            "GAP-METRIC-DEFINITION": "Por métrica: definición/fórmula, unidad, fuente/owner del dato, baseline y umbral objetivo.",
            "GAP-AUTH-MODEL": "Método de autenticación, modelo de permisos (p. ej. RBAC) y catálogo de roles con sus alcances.",
        }
        return formats.get(gap_id, "Una decisión más owner/fuente, evidencia y si está confirmada o pendiente.")
    formats = {
        "GAP-OBJECTIVE": "One sentence naming the business outcome (not the feature) and how success is recognized.",
        "GAP-USERS": "List of primary/secondary actors with role and whether they use or operate the capability.",
        "GAP-SCOPE": "In-scope vs out-of-scope bullets and what must keep working.",
        "GAP-ACCEPTANCE": "One or more EARS or Given/When/Then statements with observable conditions. EARS example: When <trigger>, the system shall <observable response>.",
        "GAP-QUALITY": "Quality expectations as bullets: risk areas, test depth, and required evidence.",
        "GAP-METRIC-SOURCE": "Metric name + baseline source/owner + target value + measurement window.",
        "GAP-TECH-DATA-SOURCE": "Systems/endpoints involved, source of truth, and owning team.",
        "GAP-TECH-NFR": "Named NFRs with concrete thresholds (latency, retention, availability) and how they are observed.",
        "GAP-DESIGN-FLOW": "Entry point and step-by-step journey to the affected screen(s).",
        "GAP-DESIGN-STATES": "The loading, empty, error, and recovery states for the surface.",
        "GAP-DESIGN-PROTOTYPE-INPUT": "The decision/flow/interaction the prototype must validate.",
        "GAP-PRODUCT-ASIS-TOBE": "Current behavior vs target behavior, stated as a delta.",
        "GAP-BUSINESS-RULES": "Rules in EARS form when they describe behavior: If <condition/rule>, then the system shall <response>; include thresholds and exceptions.",
        "GAP-FRONTEND-SURFACE": "Affected surface(s), states, validations, copy, and analytics events.",
        "GAP-BACKEND-SURFACE": "Capabilities, contracts, persistence/source of truth, and failure behavior.",
        "GAP-TECH-DEEP-DIVE-INPUT": "Repositories/components, endpoints, and source of truth to inspect.",
        "GAP-GOVERNANCE-CONSTRAINTS": "Named security/privacy/compliance/audit constraints that apply.",
        "GAP-DELIVERY-READINESS": "Dependencies with owners, environments, dates, and rollout approach.",
        "GAP-BACKLOG-SLICING-READINESS": "The first value slice plus what can be deferred and where not to split.",
        "GAP-BACKLOG-ENABLERS": "Each enabler with the capability boundary it supports and objective completion evidence.",
        "GAP-QUALITY-HANDOFF": "Critical flows, edge cases, test data, and evidence expectations.",
        "GAP-PRD-PERSONA-DETAIL": "Per persona: goal, pains, usage frequency, and proficiency.",
        "GAP-PRD-FR-AC": "FR-NN with a traceable EARS statement (When/If/While/Where/The system shall...) plus acceptance criterion and priority.",
        "GAP-PRD-NFR-KPI": "NFR/KPI with target, measurement method, and timeframe.",
        "GAP-PRD-DEPENDENCIES-ROADMAP": "MVP, dependencies with owner, and roadmap phases.",
        "GAP-PRD-ROLLOUT-ENVIRONMENTS": "Target environments, rollout strategy, release constraints, and rollback criterion.",
        "GAP-PRD-GLOSSARY-GOVERNANCE": "Glossary terms, mandatory constraints, and pending inputs with owner.",
        "GAP-METRIC-DEFINITION": "Per metric: definition/formula, unit, data source/owner, baseline, and target threshold.",
        "GAP-AUTH-MODEL": "Authentication method, permission model (e.g. RBAC), and role catalog with their scopes.",
    }
    return formats.get(gap_id, "A decision plus owner/source, evidence, and whether it is confirmed or pending.")


# --- IMP-024: gap -> brief narrative section map ------------------------------
#
# Structured inverse of the IMP-022 prose mapping: which of the project brief's
# narrative sections (1-6) a gap's confirmed answer feeds. The brief compiler
# (maturity.py) uses it to route closed-gap answers into the right section, and
# /resolve-gaps tags resolution seeds with it. Gaps that feed PRD/specs/quality
# rather than a brief 1-6 anchor map to None.
#
#   1 Identidad y Valor       4 Lente de Diseño
#   2 Lente de Negocio        5 Lente Técnico
#   3 Lente de Producto       6 Gobernanza y Restricciones

BRIEF_SECTION_FOR_GAP = {
    "GAP-OBJECTIVE": "1",
    "GAP-METRIC-SOURCE": "1",
    "GAP-USERS": "2",
    "GAP-SCOPE": "3",
    "GAP-PRODUCT-ASIS-TOBE": "3",
    "GAP-BUSINESS-RULES": "3",
    "GAP-DESIGN-FLOW": "4",
    "GAP-DESIGN-STATES": "4",
    "GAP-DESIGN-PROTOTYPE-INPUT": "4",
    "GAP-TECH-DATA-SOURCE": "5",
    "GAP-TECH-NFR": "5",
    "GAP-TECH-DEEP-DIVE-INPUT": "5",
    "GAP-FRONTEND-SURFACE": "5",
    "GAP-BACKEND-SURFACE": "5",
    "GAP-GOVERNANCE-CONSTRAINTS": "6",
    "GAP-DELIVERY-READINESS": "6",
}


def brief_section_for_gap(gap_id: str) -> str | None:
    """Which brief narrative section (1-6) a gap's confirmed answer feeds, or None."""
    return BRIEF_SECTION_FOR_GAP.get(gap_id)


# --- IMP-039: gap -> PRD narrative section map --------------------------------
#
# PRD sections are broader than the brief sections and consume both discovery
# signals and confirmed gap answers. The PRD compiler uses this map to route
# closed-gap answers without inventing missing content.

PRD_SECTION_FOR_GAP = {
    "GAP-OBJECTIVE": "1",
    "GAP-METRIC-SOURCE": "6",
    "GAP-USERS": "3",
    "GAP-PRD-PERSONA-DETAIL": "3",
    "GAP-SCOPE": "2",
    "GAP-PRODUCT-ASIS-TOBE": "2",
    "GAP-BUSINESS-RULES": "4",
    "GAP-ACCEPTANCE": "4",
    "GAP-PRD-FR-AC": "4",
    "GAP-QUALITY": "5",
    "GAP-QUALITY-HANDOFF": "5",
    "GAP-TECH-NFR": "5",
    "GAP-PRD-NFR-KPI": "5",
    "GAP-GOVERNANCE-CONSTRAINTS": "11",
    "GAP-PRD-GLOSSARY-GOVERNANCE": "13",
    "GAP-DELIVERY-READINESS": "10",
    "GAP-PRD-DEPENDENCIES-ROADMAP": "10",
    "GAP-PRD-ROLLOUT-ENVIRONMENTS": "10",
}


def prd_section_for_gap(gap_id: str) -> str | None:
    """Which PRD section (1-13) a gap's confirmed answer feeds, or None."""
    return PRD_SECTION_FOR_GAP.get(gap_id)


def render_decisions(project_id: str, text: str, req_id: str) -> str:
    decision = "Confirm scope, success criteria, and implementation constraints with stakeholders."
    if "decid" in text.lower() or "decision" in text.lower():
        decision = "Validate stated decisions and record their downstream impact."
    return f"""# Decision Log - {project_id}

| Decision ID | Status | Parent | Decision Needed |
| --- | --- | --- | --- |
| DEC-001 | PENDING | `{req_id}` | {decision} |
"""


def render_digest(project_id: str, text: str, raw_id: str, req_id: str, gap_id: str) -> str:
    return f"""# Raw Input Digest - {project_id}

- Raw source: `{raw_id}`
- Requirement: `{req_id}`
- Gap report: `{gap_id}`
- Character count: {len(text)}

## Summary

{extract_requirement(text)}
"""


def markdown_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ").strip()


def raw_sources_for_synthesis(base: Path) -> list[Path]:
    raw_dir = base / "00_raw"
    if not raw_dir.exists():
        return []
    return [
        path
        for path in sorted(raw_dir.iterdir(), key=lambda item: item.name.lower())
        if path.is_file() and path.suffix.lower() in RAW_SYNTHESIS_EXTENSIONS
    ]


def citation_for_source(text: str) -> str:
    sentences = split_evidence_sentences(text)
    if sentences:
        return sentences[0]
    for line in text.splitlines():
        clean = line.strip(" -\t")
        if clean:
            return clean
    return "[PENDING INPUT]"


def citation_for_unit(text: str, unit: dict[str, str]) -> str:
    mention = str(unit.get("evidence_mention", "")).strip().lower()
    if mention:
        for sentence in split_evidence_sentences(text):
            if mention in sentence.lower():
                return sentence
        for sentence in requirement_sentences(text):
            if mention in sentence.lower():
                return sentence
    return str(unit.get("evidence_mention", "")).strip() or citation_for_source(text)


def source_synthesis_entries(base: Path) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    for path in raw_sources_for_synthesis(base):
        text = path.read_text(encoding="utf-8")
        source_ref = f"00_raw/{path.name}"
        units = extract_requirement_units(text, raw_id=source_ref, source=path)
        if units:
            for unit in units:
                entries.append(
                    {
                        "source": source_ref,
                        "unit": unit["label"],
                        "citation": citation_for_unit(text, unit),
                    }
                )
        else:
            entries.append(
                {
                    "source": source_ref,
                    "unit": extract_requirement(text),
                    "citation": citation_for_source(text),
                }
            )
    return entries


def render_source_synthesis(project_id: str, base: Path) -> str:
    entries = source_synthesis_entries(base)
    per_source_rows = "\n".join(
        f"| `{entry['source']}` | {markdown_cell(entry['unit'])} | {markdown_cell(entry['citation'])} |"
        for entry in entries
    )
    cross_source_rows = "\n".join(
        f"| {index} | `{entry['source']}` | {markdown_cell(entry['unit'])} | {markdown_cell(entry['citation'])} |"
        for index, entry in enumerate(entries, start=1)
    )
    if not per_source_rows:
        per_source_rows = "| N/A | No source synthesis available. | N/A |"
    if not cross_source_rows:
        cross_source_rows = "| N/A | N/A | No source synthesis available. | N/A |"
    return f"""# Source Synthesis - {project_id}

Sentinel synthesizes each raw source separately before cross-source review. Cross-source rows keep their own source and verbatim citation so divergent inputs are not merged into one uncited claim.

## Per-Source Synthesis

| Source | Source-local unit | Verbatim citation |
| --- | --- | --- |
{per_source_rows}

## Cross-Source Review Inputs

| Item | Source | Preserved unit | Preserved citation |
| --- | --- | --- | --- |
{cross_source_rows}
"""


def render_identity_seeds(project_id: str, text: str, raw_id: str, gaps: list[dict[str, str]]) -> str:
    seed_rows = "\n".join(
        f"| SEED-{index:03d} | {seed['lens']} | INPUT | `{raw_id}` | {seed['truth']} | {seed['status']} | {seed['type']} |"
        for index, seed in enumerate(extract_seed_candidates(text, gaps), start=1)
    )
    return f"""# Identity Seeds - {project_id}

Seeds are atomic truths or pending truths extracted from evidence. Source files remain authoritative; memory is retrieval only.

| Seed ID | Lens | Origin Type | Origin Ref | Atomic Statement | Status | Node Type |
| --- | --- | --- | --- | --- | --- | --- |
{seed_rows}
"""


def render_discovery_log(project_id: str, text: str, raw_id: str, req_id: str, gaps: list[dict[str, str]], context: dict[str, str]) -> str:
    return f"""# Discovery Log - {project_id}

- Source: `{raw_id}`
- Requirement: `{req_id}`

## Input Census

| Source ID | Status |
| --- | --- |
| `{raw_id}` | FORENSIC_SCAN_COMPLETE |

## Business Lens / JTBD

| JTBD ID | Context | Need | Expected Result | Certainty |
| --- | --- | --- | --- | --- |
| JTBD-001 | {extract_context(text)} | {extract_need(text)} | {extract_result(text)} | INFERRED_FROM_INPUT |

## Technology Context Lens

| Area | Discovery Signal | Required Follow-Up |
| --- | --- | --- |
| Data / Integration | {lens_signal('technical', context)} | Confirm any missing integration, data ownership, security, performance, or observability gaps. |

## Design Context Lens

| Area | Discovery Signal | Required Follow-Up |
| --- | --- | --- |
| UX / UI | {lens_signal('design', context)} | Confirm missing states, navigation, accessibility, or experience constraints. |

## Quality Lens

| Area | Discovery Signal | Required Follow-Up |
| --- | --- | --- |
| Testability | {quality_signal(text)} | Convert unresolved quality expectations into acceptance criteria or gaps. |

## Atomic Inventory

| ID | Type | Domain | Description |
| --- | --- | --- | --- |
| ATOM-001 | REQUIREMENT | product | {extract_requirement(text)} |

## Refinement Hooks

{render_refinement_hooks(gaps)}
"""


def render_lens_review(
    project_id: str,
    text: str,
    raw_id: str,
    req_id: str,
    gaps: list[dict[str, str]],
    context: dict[str, str],
) -> str:
    lens_rows = "\n".join(
        f"| {lens['lens']} | {lens['role']} | {lens['evidence']} | {lens['critical_questions']} | {lens['gap_ids']} |"
        for lens in build_lens_reviews(text, gaps, context)
    )
    rubric_rows = "\n".join(
        f"| {item['area']} | {item['mature_signal']} | {item['lens']} | {item['gap_when_missing']} |"
        for item in mature_requirement_rubric()
    )
    return f"""# Multi-Lens Critical Review - {project_id}

- Raw source: `{raw_id}`
- Requirement: `{req_id}`

This artifact forces discovery to scrutinize the request from Product, Technology, Design, and Quality before downstream PRD/spec/backlog work.

| Lens | Reviewer Stance | Evidence Found | Critical Questions | Related Gaps |
| --- | --- | --- | --- | --- |
{lens_rows}

## Mature Requirement Coverage Rubric

| Area | Mature Signal | Primary Lens | Gap When Missing |
| --- | --- | --- | --- |
{rubric_rows}

## Crystallization Gate

- Product must confirm outcome, users, scope, and priority.
- Technology must confirm data sources, integrations, constraints, security, and observability when relevant.
- Design must confirm journey, screens, states, accessibility, and interaction expectations when relevant.
- Quality must confirm acceptance strategy, testability, risk scenarios, and metric fidelity.
- Any unanswered critical or high gap blocks maturity; medium gaps stay visible for PRD/spec/backlog assumptions.
"""


def build_lens_reviews(text: str, gaps: list[dict[str, str]], context: dict[str, str]) -> list[dict[str, str]]:
    return [
        lens_review(
            "business/product",
            "Senior BA / Product Lead",
            text,
            context.get("business", ""),
            gaps,
            ("GAP-OBJECTIVE", "GAP-USERS", "GAP-SCOPE", "GAP-METRIC-SOURCE"),
            "What outcome, user, scope boundary, metric source, or priority remains ambiguous?",
        ),
        lens_review(
            "product",
            "Product Strategist",
            text,
            context.get("business", ""),
            gaps,
            ("GAP-PRODUCT-ASIS-TOBE", "GAP-BUSINESS-RULES", "GAP-DELIVERY-READINESS", "GAP-BACKLOG-SLICING-READINESS"),
            "Is the as-is/to-be delta, rule set, dependency map, and rollout path clear enough to shape PRD and backlog?",
        ),
        lens_review(
            "technical",
            "Tech Lead",
            text,
            context.get("technical", ""),
            gaps,
            ("GAP-TECH-DATA-SOURCE", "GAP-TECH-NFR", "GAP-FRONTEND-SURFACE", "GAP-BACKEND-SURFACE", "GAP-TECH-DEEP-DIVE-INPUT", "GAP-BACKLOG-ENABLERS"),
            "Which systems, endpoint/event surfaces, create/modify/reuse decisions, security, observability, or ownership constraints are required before Technology can deepen the design?",
        ),
        lens_review(
            "design",
            "UX/UI Designer",
            text,
            context.get("design", ""),
            gaps,
            ("GAP-DESIGN-FLOW", "GAP-DESIGN-STATES", "GAP-DESIGN-PROTOTYPE-INPUT"),
            "Which journey, screens, states, error/empty/loading behavior, or accessibility requirements are unresolved?",
        ),
        lens_review(
            "quality",
            "Quality Lead",
            text,
            context.get("quality", ""),
            gaps,
            ("GAP-ACCEPTANCE", "GAP-QUALITY", "GAP-QUALITY-HANDOFF"),
            "What acceptance criteria, risks, negative paths, stale/missing data cases, or test evidence are missing?",
        ),
    ]


def mature_requirement_rubric() -> list[dict[str, str]]:
    return [
        {
            "area": "Identity and value",
            "mature_signal": "Initiative name, pain, target outcome, measurable success, and metric source are explicit.",
            "lens": "Business/Product",
            "gap_when_missing": "GAP-OBJECTIVE or GAP-METRIC-SOURCE",
        },
        {
            "area": "Actors and responsibilities",
            "mature_signal": "Stakeholders, users, external teams, owners, and role-level objectives are identified.",
            "lens": "Business/Product",
            "gap_when_missing": "GAP-USERS",
        },
        {
            "area": "Scope boundaries",
            "mature_signal": "In scope, out of scope, unchanged behavior, and non-goals are stated.",
            "lens": "Product",
            "gap_when_missing": "GAP-SCOPE",
        },
        {
            "area": "As-is / to-be delta",
            "mature_signal": "Current process, target process, and functional delta are comparable.",
            "lens": "Product",
            "gap_when_missing": "GAP-PRODUCT-ASIS-TOBE",
        },
        {
            "area": "Business rules and edge cases",
            "mature_signal": "Decision rules, exceptions, fallbacks, and boundary cases are explicit.",
            "lens": "Business/Quality",
            "gap_when_missing": "GAP-BUSINESS-RULES",
        },
        {
            "area": "Data and integrations",
            "mature_signal": "Systems, APIs/events, create/modify/reuse decisions, ownership, source of truth, and critical fields are clear enough for Technology to produce detailed context packs.",
            "lens": "Technology",
            "gap_when_missing": "GAP-TECH-DATA-SOURCE",
        },
        {
            "area": "Technology deep-dive readiness",
            "mature_signal": "Repositories or components to inspect, architecture questions, endpoint/event inventory, dependencies, and technical risks are explicit enough for a technical context pack.",
            "lens": "Technology",
            "gap_when_missing": "GAP-TECH-DEEP-DIVE-INPUT",
        },
        {
            "area": "Frontend implementation readiness",
            "mature_signal": "Affected surfaces, roles, UI states, validations, copy, analytics/telemetry needs, and API binding expectations are visible.",
            "lens": "Frontend/Design",
            "gap_when_missing": "GAP-FRONTEND-SURFACE",
        },
        {
            "area": "Backend implementation readiness",
            "mature_signal": "Capabilities, business rules, integrations, persistence/source-of-truth needs, exposed contracts, observability, and failure behavior are visible.",
            "lens": "Backend/Technology",
            "gap_when_missing": "GAP-BACKEND-SURFACE",
        },
        {
            "area": "Non-functional constraints",
            "mature_signal": "Security, privacy, performance, observability, availability, and compliance constraints are visible.",
            "lens": "Technology/Compliance",
            "gap_when_missing": "GAP-TECH-NFR or GAP-GOVERNANCE-CONSTRAINTS",
        },
        {
            "area": "UX journey and states",
            "mature_signal": "User flows, affected screens, copy/messaging, empty/loading/error states, and unchanged UX are clear.",
            "lens": "Design",
            "gap_when_missing": "GAP-DESIGN-FLOW or GAP-DESIGN-STATES",
        },
        {
            "area": "Design prototype readiness",
            "mature_signal": "The brief states what Design should validate or prototype, including target users, journey moments, decisions, states, and visual evidence references.",
            "lens": "Design",
            "gap_when_missing": "GAP-DESIGN-PROTOTYPE-INPUT",
        },
        {
            "area": "Acceptance and quality",
            "mature_signal": "Happy path, negative paths, stale/missing data, test data, and acceptance criteria are testable.",
            "lens": "Quality",
            "gap_when_missing": "GAP-ACCEPTANCE or GAP-QUALITY",
        },
        {
            "area": "Quality handoff readiness",
            "mature_signal": "Critical flows, edge cases, regression areas, test data needs, and evidence expectations are explicit enough for QA to deepen coverage.",
            "lens": "Quality",
            "gap_when_missing": "GAP-QUALITY-HANDOFF",
        },
        {
            "area": "Delivery readiness",
            "mature_signal": "Dependencies, environments, pending approvals, timing, rollout, and open uncertainties are tracked.",
            "lens": "Delivery/Product",
            "gap_when_missing": "GAP-DELIVERY-READINESS",
        },
        {
            "area": "Backlog slicing readiness",
            "mature_signal": "First value slice, meaningful story boundary, deferred variants/rules, and valid cross-cutting enablers are explicit enough to avoid micro-stories or loose infrastructure work.",
            "lens": "Product/Technology/Quality",
            "gap_when_missing": "GAP-BACKLOG-SLICING-READINESS or GAP-BACKLOG-ENABLERS",
        },
    ]


def lens_review(
    lens: str,
    role: str,
    text: str,
    context_text: str,
    gaps: list[dict[str, str]],
    gap_ids: tuple[str, ...],
    question: str,
) -> dict[str, str]:
    evidence = "Source + domain context" if context_text.strip() else "Source only; no domain context folder evidence"
    related = [gap["id"] for gap in gaps if gap["id"] in gap_ids or gap.get("lens") in {lens, lens.split("/")[0]}]
    return {
        "lens": lens,
        "role": role,
        "evidence": evidence if text.strip() else "No source evidence",
        "critical_questions": question,
        "gap_ids": ", ".join(f"`{gap_id}`" for gap_id in sorted(set(related))) or "None",
    }


def extract_seed_candidates(text: str, gaps: list[dict[str, str]]) -> list[dict[str, str]]:
    seeds: list[dict[str, str]] = []
    for line in [line.strip(" -\t") for line in text.splitlines() if line.strip()]:
        lowered = line.lower()
        if any(token in lowered for token in ("objetivo", "goal", "outcome")):
            seeds.append({"lens": "business", "truth": line, "status": "KNOWN", "type": "BIZ_OBJECTIVE"})
        elif any(token in lowered for token in ("usuario", "user", "persona", "actor")):
            seeds.append({"lens": "business", "truth": line, "status": "KNOWN", "type": "USER_CONTEXT"})
        elif any(token in lowered for token in ("alcance", "scope", "out of scope")):
            seeds.append({"lens": "product", "truth": line, "status": "KNOWN", "type": "SCOPE_RULE"})
        elif any(token in lowered for token in ("quality", "calidad", "qa", "test")):
            seeds.append({"lens": "quality", "truth": line, "status": "KNOWN", "type": "QUALITY_EXPECTATION"})
        elif METRIC_RE.search(line):
            status = "KNOWN" if any(token in lowered for token in ("source", "fuente", "baseline", "medido", "measured")) else "PENDING_SOURCE"
            seeds.append({"lens": "business", "truth": line, "status": status, "type": "METRIC"})
    for gap in gaps:
        seeds.append({"lens": lens_for_gap(gap["id"]), "truth": gap["description"], "status": "PENDING", "type": "GAP_PLACEHOLDER"})
    return seeds or [{"lens": "product", "truth": extract_requirement(text), "status": "INFERRED", "type": "PRIMARY_REQUIREMENT"}]


def load_domain_context(base: Path) -> dict[str, str]:
    folders = {
        "business": base / "00_raw" / "01_business_context",
        "technical": base / "00_raw" / "02_technology_context",
        "design": base / "00_raw" / "03_design_context",
        "quality": base / "00_raw" / "04_quality_context",
        "interactions": base / "00_raw" / "05_interactions",
    }
    context: dict[str, str] = {}
    for domain, folder in folders.items():
        chunks = []
        if folder.exists():
            for pattern in ("*.md", "*.txt", "*.html", "*.htm"):
                for path in sorted(folder.rglob(pattern)):
                    chunks.append(path.read_text(encoding="utf-8"))
        context[domain] = "\n\n".join(chunks)
    return context


def lens_signal(domain: str, context: dict[str, str]) -> str:
    text = context.get(domain, "").strip()
    if text:
        return f"{domain.title()} context folder contains evidence ({len(text)} chars)."
    return f"No {domain} context folder evidence was found during discovery."


def lens_for_gap(gap_id: str) -> str:
    if "TECH" in gap_id or "AUTH" in gap_id:
        return "technical"
    if "DESIGN" in gap_id:
        return "design"
    if "GOVERNANCE" in gap_id:
        return "compliance"
    if "DELIVERY" in gap_id:
        return "delivery"
    if "QUALITY" in gap_id or "ACCEPTANCE" in gap_id:
        return "quality"
    if "USERS" in gap_id or "SCOPE" in gap_id or "OBJECTIVE" in gap_id or "BUSINESS" in gap_id:
        return "business"
    if "METRIC" in gap_id:
        return "business"
    return "product"


def question_for_gap(gap_id: str, language: str = "en") -> str:
    if language == "es":
        questions = {
            "GAP-OBJECTIVE": "¿Qué resultado de negocio debería lograr este requerimiento?",
            "GAP-USERS": "¿Qué usuarios, personas o roles están dentro del alcance?",
            "GAP-SCOPE": "¿Qué está explícitamente dentro y fuera del alcance?",
            "GAP-ACCEPTANCE": "¿Qué condiciones observables demuestran que el requerimiento está terminado?",
            "GAP-QUALITY": "¿Qué expectativas de calidad, testeabilidad, riesgo o compliance aplican?",
            "GAP-METRIC-SOURCE": "¿Cuál es la fuente o baseline de la métrica cuantitativa?",
            "GAP-TECH-DATA-SOURCE": "¿Qué sistemas, endpoints, eventos, decisiones de crear/modificar/reutilizar, owners, fuente de verdad y campos críticos están involucrados?",
            "GAP-TECH-NFR": "¿Qué restricciones de seguridad, performance, observabilidad, disponibilidad u operación aplican?",
            "GAP-DESIGN-FLOW": "¿Qué journey, pantallas, flujos, copy o cambios de interacción están dentro del alcance?",
            "GAP-DESIGN-STATES": "¿Qué estados de loading, empty, error, recuperación y accesibilidad deben contemplarse?",
            "GAP-DESIGN-PROTOTYPE-INPUT": "¿Qué debería prototipar o validar Diseño, y qué usuarios, momentos del journey, estados y referencias visuales deberían guiarlo?",
            "GAP-PRODUCT-ASIS-TOBE": "¿Cuál es el proceso actual, el proceso objetivo y el delta exacto entre ambos?",
            "GAP-BUSINESS-RULES": "¿Qué reglas, excepciones, validaciones, fallbacks o exclusiones gobiernan el comportamiento?",
            "GAP-FRONTEND-SURFACE": "¿Qué superficies frontend, roles, estados, validaciones, copy, analytics y bindings de API se ven afectados?",
            "GAP-BACKEND-SURFACE": "¿Qué capacidades backend, integraciones, reglas, persistencia/source of truth, contratos y comportamiento ante fallas se ven afectados?",
            "GAP-TECH-DEEP-DIVE-INPUT": "¿Qué repositorios/componentes, preguntas de arquitectura, inventario de endpoints/eventos, dependencias y riesgos debería inspeccionar Tecnología?",
            "GAP-GOVERNANCE-CONSTRAINTS": "¿Qué restricciones de seguridad, privacidad, compliance, auditoría u operación deben respetarse?",
            "GAP-DELIVERY-READINESS": "¿Qué dependencias, ambientes, aprobaciones, owners, fechas o restricciones de rollout quedan pendientes?",
            "GAP-PRD-ROLLOUT-ENVIRONMENTS": "¿Qué ambientes, estrategia de rollout, restricciones de release y criterio de rollback deben quedar confirmados en el PRD?",
            "GAP-BACKLOG-SLICING-READINESS": "¿Cuál es el primer slice de valor observable, qué variantes o reglas pueden diferirse y dónde cortar más pequeño dejaría de aportar valor?",
            "GAP-BACKLOG-ENABLERS": "¿Qué enablers transversales de implementación frontend/backend o arquitectura deben construirse antes para soportar esta funcionalidad, qué scope habilitan y cómo se distinguen de una precondición operacional genérica?",
            "GAP-QUALITY-HANDOFF": "¿Qué flujos críticos, casos borde, datos de prueba, riesgos de regresión y evidencia esperada debería usar Calidad para profundizar cobertura?",
            "GAP-METRIC-DEFINITION": "¿Cómo se define cada métrica/KPI (fórmula, unidad), de qué fuente sale y cuál es su baseline y umbral objetivo?",
            "GAP-AUTH-MODEL": "¿Qué método de autenticación, modelo de permisos y catálogo de roles aplican para esta capacidad?",
        }
        return questions.get(gap_id, "¿Qué información confirmada resuelve esta incertidumbre?")
    questions = {
        "GAP-OBJECTIVE": "What business outcome should this requirement achieve?",
        "GAP-USERS": "Which users, personas, or roles are in scope?",
        "GAP-SCOPE": "What is explicitly in scope and out of scope?",
        "GAP-ACCEPTANCE": "What observable conditions prove the requirement is done?",
        "GAP-QUALITY": "What quality, testability, risk, or compliance expectations apply?",
        "GAP-METRIC-SOURCE": "What is the source or baseline for the quantitative metric?",
        "GAP-TECH-DATA-SOURCE": "Which systems, endpoints, events, create/modify/reuse decisions, owners, source-of-truth data, and critical fields are involved?",
        "GAP-TECH-NFR": "What security, performance, observability, availability, or operational constraints apply?",
        "GAP-DESIGN-FLOW": "Which user journey, screens, flows, copy, or interaction changes are in scope?",
        "GAP-DESIGN-STATES": "What loading, empty, error, recovery, and accessibility states must be handled?",
        "GAP-DESIGN-PROTOTYPE-INPUT": "What should Design prototype or validate, and which users, journey moments, states, and visual references should guide it?",
        "GAP-PRODUCT-ASIS-TOBE": "What is the current process, target process, and exact delta between them?",
        "GAP-BUSINESS-RULES": "Which rules, exceptions, validations, fallbacks, or exclusions govern the behavior?",
        "GAP-FRONTEND-SURFACE": "Which frontend surfaces, roles, states, validations, copy, analytics, and API binding needs are affected?",
        "GAP-BACKEND-SURFACE": "Which backend capabilities, integrations, rules, persistence/source-of-truth needs, contracts, and failure behaviors are affected?",
        "GAP-TECH-DEEP-DIVE-INPUT": "Which repositories/components, architecture questions, endpoint/event inventory, dependencies, and technical risks should Technology inspect?",
        "GAP-GOVERNANCE-CONSTRAINTS": "Which security, privacy, compliance, audit, or operational restrictions must be respected?",
        "GAP-DELIVERY-READINESS": "Which dependencies, environments, approvals, owners, dates, or rollout constraints remain pending?",
        "GAP-PRD-ROLLOUT-ENVIRONMENTS": "Which environments, rollout strategy, release constraints, and rollback criterion must be confirmed in the PRD?",
        "GAP-BACKLOG-SLICING-READINESS": "What is the first observable value slice, which variants or rules can be deferred, and where would a smaller split stop producing value?",
        "GAP-BACKLOG-ENABLERS": "Which frontend/backend or architecture implementation enablers must be built in advance to support this functionality, what scope do they enable, and how are they different from a generic operational precondition?",
        "GAP-QUALITY-HANDOFF": "Which critical flows, edge cases, test data, regression risks, and evidence expectations should Quality use for deeper coverage?",
        "GAP-METRIC-DEFINITION": "How is each metric/KPI defined (formula, unit), what source does it come from, and what is its baseline and target threshold?",
        "GAP-AUTH-MODEL": "Which authentication method, permission model, and role catalog apply to this capability?",
    }
    return questions.get(gap_id, "What confirmed information resolves this uncertainty?")


def extract_context(text: str) -> str:
    return "When the target user faces the operational situation described in the source input"


def extract_need(text: str) -> str:
    return extract_requirement(text)


def extract_result(text: str) -> str:
    for line in text.splitlines():
        if any(token in line.lower() for token in ("resultado", "success", "outcome", "para", "so that")):
            return line.strip(" -\t")
    return "Obtain the expected business outcome without unresolved ambiguity."


def quality_signal(text: str) -> str:
    return "Quality expectations are present in source input." if any(
        token in text.lower() for token in ("quality", "calidad", "qa", "test")
    ) else "Quality expectations are not explicit enough."


def render_refinement_hooks(gaps: list[dict[str, str]]) -> str:
    if not gaps:
        return "- No blocking refinement hooks detected."
    return "\n".join(f"- {gap['id']}: {question_for_gap(gap['id'])}" for gap in gaps)
