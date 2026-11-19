"""Discovery ingest: source intake, requirement units, discovery artifacts and lens reviews."""
from __future__ import annotations

import re
from pathlib import Path

from ..core.graph import add_edge, add_node, upsert_node
from ..core.io import read_json, write_text
from ..core.markdown import parse_table_rows
from ..deltas import DeltaStatus
from ..errors import GateRefusal, InputError
from ..gaps import count_gaps, lens_for_gap, parse_gap_rows, question_for_gap, readiness_stage_after_gap_change, render_gaps
from ..injection import shield_source
from ..knowledge.ledger import materialize_knowledge_ledger
from ..memory import ContextBroker, index_context_folders
from ..secrets_scan import ingest_source, pii_report_enabled
from ..source_formats import read_source, target_suffix
from ..sources import mark_source_processed, open_source_row
from ..workspace import ensure_workspace, load_config, read_state, update_state, workspace_path

from .detection import METRIC_RE, detect_unit_anchored_gaps, gap_question_warnings, requirement_sentences, split_evidence_sentences


RAW_SYNTHESIS_EXTENSIONS = {".md", ".txt", ".html", ".htm"}


_GAP_STATUS_RE = re.compile(r"^- Status: `([A-Z_]+)`", re.M)


def _answered_gap_count(base: Path) -> int:
    """Gaps in gaps.md that are no longer OPEN (answered, partially or fully closed)."""
    gaps_path = base / "01_discovery" / "gaps.md"
    if not gaps_path.is_file():
        return 0
    statuses = _GAP_STATUS_RE.findall(gaps_path.read_text(encoding="utf-8"))
    return sum(1 for status in statuses if status != "OPEN")


def ingest(project_id: str, source: Path, replace: bool = False, change: bool = False) -> dict[str, str]:
    if change:
        # IMP-382: a change opens beside the project; replacing the primary requirement is another act.
        if replace:
            raise InputError(
                "--change y --replace no van juntos: un cambio no reemplaza el requerimiento principal.",
                next_step=f"Quitá uno: /ingest {project_id} --source {source.as_posix()} --change, o sin --change para reemplazar.",
            )
        from ..changes import ingest_change

        return ingest_change(project_id, source)
    ensure_workspace(project_id)
    base = workspace_path(project_id)
    # IMP-320: /ingest builds the project's primary requirement. On a workspace that
    # already has one, a second /ingest used to rewrite requirements, gaps, decisions
    # and seeds from the new file and reopen every answered gap with exit 0. Adding a
    # file is /sync's job; replacing the primary requirement must be asked for.
    existing_raw = read_state(project_id).get("artifacts", {}).get("raw_input")
    replaced: dict | None = None
    if existing_raw:
        if not replace:
            raise GateRefusal(
                f"{project_id} already has its primary requirement ({Path(existing_raw).name}); "
                "a second /ingest would replace it and reopen every answered gap.",
                next_step=(
                    f"To add this file, run /sync {project_id} --source {source.as_posix()}. "
                    f"To replace the primary requirement on purpose, run /ingest {project_id} "
                    f"--source {source.as_posix()} --replace."
                ),
            )
        from ..gap_resolution import saved_response_files

        saved = saved_response_files(base)
        replaced = {
            "previous_raw_input": existing_raw,
            "answered_gaps_reopened": _answered_gap_count(base),
            "saved_answers": saved,
            "next_step": (
                f"Re-apply the saved answers with /resolve-gaps {project_id} --source FILE, one file at a time: "
                + ", ".join(saved)
                if saved
                else "No saved answers to re-apply; send the client a new interview script (/export --artifact gaps --format interview)."
            ),
        }
    raw_target = base / "00_raw" / f"{source.stem}{target_suffix(source)}"
    extracted = read_source(source, media_stem=raw_target.stem)  # IMP-270: typed error before the row opens
    source_id = open_source_row(project_id, source, "initial_ingested")  # IMP-250a
    # IMP-150: snapshot the previous Requirement Units before this ingest
    # overwrites them, so a re-ingest can emit a governed ADDED/MODIFIED/REMOVED
    # delta view of what capabilities changed.
    previous_requirement_units = requirement_unit_snapshot(base)
    config = load_config(project_id)
    # IMP-285: secrets are redacted before anything is extracted; the original is only read.
    text, sanitized = ingest_source(base, source, raw_target, pii_report_enabled(config), extracted)
    # IMP-286: source content is data; instruction-shaped lines go to the BA, not to the compilers.
    text, injection_ids = shield_source(base, source.name, text)
    language = resolve_project_language(config.get("project_language", "auto"), text)
    context = load_domain_context(base)
    mark_source_processed(project_id, source, "initial_ingested", source_id=source_id)
    mark_source_processed(project_id, raw_target, "raw_copy", source_id=source_id)
    raw_id = add_node(project_id, "RAW", "raw_input", raw_target, source.stem, domain="product")
    source_synthesis_path = base / "01_discovery" / "source_synthesis.md"
    write_text(source_synthesis_path, render_source_synthesis(project_id, base))
    requirement_units = extract_requirement_units(text, raw_id, raw_target)
    units_path = base / "01_discovery" / "requirement_units.md"
    write_text(units_path, render_requirement_units(project_id, requirement_units))

    req_text = extract_requirement(text)
    req_path = base / "02_requirements" / "requirements.md"
    write_text(req_path, render_requirement(project_id, req_text, raw_id))
    req_id = add_node(project_id, "REQ", "requirement", req_path, "Primary requirement", domain="product")
    add_edge(project_id, raw_id, req_id, "extracts")
    unit_node_ids: list[str] = []
    for unit in requirement_units:
        unit_id = upsert_node(project_id, unit["id"], "requirement_unit", units_path, unit["label"], domain="product")
        unit["trace_id"] = unit_id
        unit_node_ids.append(unit_id)
        add_edge(project_id, raw_id, unit_id, "decomposes_into")
        add_edge(project_id, unit_id, req_id, "analyzes")
    write_text(units_path, render_requirement_units(project_id, requirement_units))
    # IMP-150: on re-ingest, emit the read-only RU delta view (governed signal only).
    requirement_unit_delta_path = write_requirement_unit_delta(
        project_id, base, previous_requirement_units, requirement_units
    )

    gaps = detect_unit_anchored_gaps(text, context, requirement_units)
    gap_path = base / "01_discovery" / "gaps.md"
    write_text(gap_path, render_gaps(project_id, gaps, req_id, language))
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
    # IMP-251: anchor the statements; a cited, undelivered document opens a gap.
    from ..source_conflicts import scan_source_conflicts

    source_conflicts = scan_source_conflicts(project_id, source_id, text, language)
    governed_gaps = gaps + source_conflicts.pop("new_gaps")

    dec_path = base / "01_discovery" / "decisions.md"
    write_text(dec_path, render_decisions(project_id, text, req_id))
    dec_id = add_node(project_id, "DEC", "decision_log", dec_path, "Pending decisions", status="pending")
    add_edge(project_id, req_id, dec_id, "requires_decision")

    digest_path = base / "01_discovery" / "raw_input_digest.md"
    write_text(digest_path, render_digest(project_id, text, raw_id, req_id, gap_id))

    seeds_path = base / "01_discovery" / "identity_seeds.md"
    write_text(seeds_path, render_identity_seeds(project_id, text, raw_id, gaps))
    seed_id = add_node(project_id, "SEED", "identity_seed_bank", seeds_path, "Identity seeds", domain="product")
    add_edge(project_id, raw_id, seed_id, "produces_seed")
    add_edge(project_id, seed_id, req_id, "grounds")

    discovery_log_path = base / "01_discovery" / "discovery_log.md"
    write_text(discovery_log_path, render_discovery_log(project_id, text, raw_id, req_id, gaps, context))
    discovery_log_id = add_node(project_id, "DISC", "discovery_log", discovery_log_path, "Discovery log", domain="product")
    add_edge(project_id, raw_id, discovery_log_id, "analyzed_by")
    add_edge(project_id, discovery_log_id, gap_id, "identifies")

    lens_review_path = base / "01_discovery" / "lens_review.md"
    write_text(lens_review_path, render_lens_review(project_id, text, raw_id, req_id, gaps, context))
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
        health="DIRTY" if governed_gaps else "CLEAN",
        project_language=language,
        privacy_mode="local-only",
        readiness_stage="CLIENT_RESPONSE_NEEDED" if governed_gaps else "READY_FOR_PROJECT_BRIEF",
        gap_counts=count_gaps(governed_gaps),
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
        "secret_redactions": sanitized.redactions,
        "injection_signals": injection_ids,
        "source_conflicts": source_conflicts,
        "source_format": {"kind": extracted.kind, "images": len(extracted.images),
                          "comments": extracted.comments, "warning": extracted.warning},
        "secret_alerts": str(sanitized.alerts_path.as_posix()) if sanitized.alerts_path else None,
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
        "replaced": replaced,
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
            status, ref = DeltaStatus.REMOVED.value, was
        elif now and not was:
            status, ref = DeltaStatus.ADDED.value, now
        elif was and now and was.get("evidence") != now.get("evidence"):
            status, ref = DeltaStatus.MODIFIED.value, now
        else:
            status, ref = DeltaStatus.UNCHANGED.value, (now or was)
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
    write_text(path, render_requirement_unit_delta(project_id, entries))
    return path


def regenerate_gaps(project_id: str) -> dict[str, object]:
    base = workspace_path(project_id)
    gaps_path = base / "01_discovery" / "gaps.md"
    if not gaps_path.exists():
        from ..changes import list_changes

        open_changes = sorted(list_changes(project_id))
        if open_changes:
            raise GateRefusal(
                f"{project_id} sólo tiene cambios: no hay 01_discovery/gaps.md del proyecto",
                next_step=f"/gaps {project_id} --change {open_changes[0]}",
            )
        raise GateRefusal("Cannot regenerate gaps before /ingest creates 01_discovery/gaps.md.")
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
    write_text(gaps_path, render_gaps(project_id, existing, req_id, language))
    counts = count_gaps(existing)
    update_state(project_id, gap_counts=counts, readiness_stage=readiness_stage_after_gap_change(project_id, counts))
    return {
        "project_id": project_id,
        "path": str(gaps_path),
        "gap_counts": counts,
        # IMP-180: non-blocking Mom-Test warnings over the elicited questions.
        "momtest_warnings": gap_question_warnings(existing, language),
    }


RU_ID_RE = re.compile(r"^RU-[0-9]{3}$")


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
