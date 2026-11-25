"""Agent channels: /annotate, /challenge, /scrutinize, and gap dispositions."""
from __future__ import annotations

import json
import re
from pathlib import Path

from ..core.graph import add_edge, add_node, load_graph
from ..core.io import append_text, read_json, write_text
from ..core.markdown import parse_table_rows
from ..domain_context import respondent_profile_from_domain_context
from ..errors import GateRefusal, InputError
from ..gaps import count_gaps, merge_gaps_by_topic, parse_gap_rows, readiness_stage_after_gap_change, render_gaps
from ..knowledge.ledger import materialize_knowledge_ledger
from ..lens_registry import known_lenses
from ..memory import ContextBroker
from ..payload_hygiene import archive_payload, sanitize_payload
from ..sources import mark_source_processed
from ..technique_registry import default_challenge_technique_ids, default_technique_summary, technique_label, technique_prompt, technique_risk_taxonomy
from ..workspace import load_config, update_state, workspace_path

from .intake import RU_ID_RE, load_domain_context


def record_gap_disposition(project_id: str, gap_id: str, disposition: str, reason: str = "") -> dict[str, object]:
    """IMP-271 / F7: the BA's disposition on a gap an agentic channel raised."""
    from ..agent_sweep import SweepProtocolError, channel_dispositions, set_disposition

    base = workspace_path(project_id)
    gaps_path = base / "01_discovery" / "gaps.md"
    if not gaps_path.exists():
        raise GateRefusal("Cannot record a disposition before /ingest creates 01_discovery/gaps.md.")
    gaps = [gap for gap in parse_gap_rows(gaps_path.read_text(encoding="utf-8")) if gap.get("id") != "NONE"]
    gap = next((item for item in gaps if item["id"] == gap_id.strip().upper()), None)
    if gap is None:
        raise InputError(f"{gap_id} is not in 01_discovery/gaps.md.")
    applied = None
    if gap["id"].startswith("GAP-CHG-"):
        # IMP-337 (337c): on a GAP-CHG the disposition has an effect. accepted applies the
        # change (reopen the gap / invalidate the assumption); rejected closes it as a
        # false alarm. Checked first, so a refused disposition writes nothing.
        from ..agent_sweep import DISPOSITIONS, FALSE_ALARM
        from ..sync_analysis import apply_change_disposition

        if disposition not in DISPOSITIONS:
            raise ValueError(f"--disposition must be one of {', '.join(DISPOSITIONS)}.")
        if disposition in FALSE_ALARM and not reason.strip():
            raise ValueError(f"--disposition {disposition} needs --reason: say why it was a false alarm.")
        applied = apply_change_disposition(project_id, gap, disposition, reason)
    try:
        record = set_disposition(base, gap, disposition, reason)
    except SweepProtocolError as exc:
        raise ValueError(str(exc)) from exc
    if applied is not None:
        gaps = [item for item in parse_gap_rows(gaps_path.read_text(encoding="utf-8")) if item.get("id") != "NONE"]
    result: dict[str, object] = {"gap_id": gap["id"], **record, "channels": channel_dispositions(base, gaps)}
    if applied is not None:
        result["applied"] = applied
    return result


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


class AnnotationError(InputError):
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
    # IMP-271: the sweep protocol (AUSENTE re-verified, untouched, blocks, no agent figures).
    from ..agent_sweep import SweepProtocolError, validate_sweep_extras

    try:
        validate_sweep_extras(data, haystack, _normalize_for_match)
    except SweepProtocolError as exc:
        raise AnnotationError(str(exc)) from exc
    return validated


def _record_sweep(base: Path, channel: str, data: dict, gaps: list[dict[str, str]], log_path: Path | None = None) -> None:
    from ..agent_sweep import record_sweep

    record_sweep(base, channel, data, [gap["id"] for gap in gaps], log_path)


def _clean_agent_payload(base: Path, data: dict, gaps: list[dict[str, str]]) -> tuple[dict, list[dict[str, str]]]:
    """IMP-347: the payload and its validated gaps as they may be stored and rendered.

    Validation has already run on the payload as written. Every string is redacted and
    every injection-shaped line becomes `<NEUTRALIZADO:type>` (IMP-342). The evidence
    shown in `gaps.md` is cleaned from the full quote and only then cut to 160
    characters, so a cut cannot leave half a secret the scanner no longer recognizes.
    No field here is checked verbatim again later, so none is kept verbatim.
    """
    clean_data = sanitize_payload(base, data)
    evidence: dict[str, str] = {}
    for item in clean_data.get("gaps") or []:
        if isinstance(item, dict):
            evidence[str(item.get("id", "")).strip().upper()] = str(item.get("evidence", "")).strip()
    clean_gaps = sanitize_payload(base, gaps)
    for gap in clean_gaps:
        quote = evidence.get(gap["id"])
        if quote:
            gap["evidence_mention"] = quote if len(quote) <= 160 else quote[:157] + "..."
    return clean_data, clean_gaps


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
        raise GateRefusal("Cannot refresh knowledge ledger before gaps.md exists.")
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
    language: str | None = None,
) -> None:
    """Appends one entry; `language` (a change's log, IMP-418) speaks Spanish when the change does."""
    es = language == "es"
    if not log_path.exists():
        header = f"""# Agent Annotation Log - {project_id}

Sanctioned record of agentic (`origin: agent`) discovery analysis (IMP-021).
Each entry below was validated and merged by the runtime; source files remain
the authority. The agent proposes with evidence; it never writes artifacts by hand.

"""
        write_text(log_path, _speak(header, _ANNOTATION_LOG_ES) if es else header)
    entry = render_annotation_log_entry(label, merged, skipped, data) + "\n"
    append_text(log_path, _speak(entry, _ANNOTATION_LOG_ES) if es else entry)


_ANNOTATION_LOG_ES = (
    ("# Agent Annotation Log - ", "# Registro de anotaciones del agente - "),
    ("Sanctioned record of agentic (`origin: agent`) discovery analysis (IMP-021).\n"
     "Each entry below was validated and merged by the runtime; source files remain\n"
     "the authority. The agent proposes with evidence; it never writes artifacts by hand.",
     "Registro autorizado del análisis agéntico (`origin: agent`) del descubrimiento (IMP-021).\n"
     "El runtime validó e incorporó cada entrada; las fuentes siguen siendo la autoridad.\n"
     "El agente propone con evidencia; nunca escribe artefactos a mano."),
    ("## Annotation: ", "## Anotación: "),
    ("Origin: `agent`. The runtime validated each gap (declared lens, severity range, and a verbatim evidence citation) before merging.",
     "Origen: `agent`. El runtime validó cada gap (lente declarada, rango de severidad y una cita textual de evidencia) antes de incorporarlo."),
    ("### Merged Semantic Gaps", "### Gaps semánticos incorporados"),
    ("| Gap ID | Lens | Severity | Question | Evidence Cited |", "| Gap | Lente | Severidad | Pregunta | Evidencia citada |"),
    ("No new gaps merged (all duplicates).", "Ningún gap nuevo (todos duplicados)."),
    ("Skipped (already present in gaps.md)", "Omitidos (ya están en gaps.md)"),
    ("### Ambiguities Reported", "### Ambigüedades informadas"),
    ("### Implicit Assumptions Reported", "### Supuestos implícitos informados"),
    ("- None reported.", "- Nada informado."),
    ("None.", "Ninguno."),
)


def _speak(text: str, table: tuple[tuple[str, str], ...]) -> str:
    for english, spanish in table:
        text = text.replace(english, spanish)
    return text


def apply_annotation(project_id: str, source: Path, change_id: str | None = None) -> dict[str, object]:
    """Validate, merge, and trace an agentic annotation of the raw input (IMP-021).

    With `change_id` (IMP-418) the run annotates that change's request, brief and gaps and leaves
    everything under `01_discovery/<CHG>/`; the project's files, state and ledger are not touched.
    """
    base = workspace_path(project_id)
    if not base.exists():
        raise GateRefusal(f"Workspace not found: {project_id}")
    language = "en"
    if change_id is not None:
        from .change_scope import change_channel_gate, change_channel_paths, change_grounding_text

        _change, gaps_path, language = change_channel_gate(project_id, change_id, "annotate")
        paths = change_channel_paths(base, change_id)
        raw_text = change_grounding_text(project_id, change_id)
    else:
        from ..changes import refuse_change_only_channel

        refuse_change_only_channel(project_id, "annotate")
        gaps_path = base / "01_discovery" / "gaps.md"
        if not gaps_path.exists():
            raise GateRefusal("Cannot annotate before /ingest creates 01_discovery/gaps.md.")
        raw_text = raw_input_text(base)
        if not raw_text.strip():
            raise GateRefusal("No raw input found under 00_raw/ to ground the annotation against.")

    data = load_agent_annotation(source)
    agent_gaps = validate_agent_gaps(data, raw_text)
    # IMP-347: validated as written; stored and rendered redacted and neutralized
    data, agent_gaps = _clean_agent_payload(base, data, agent_gaps)
    if change_id is not None:
        from ..changes import merge_change_gaps
        from ..extraction.inventory import pedido_rows

        _record_sweep(base, "annotate", data, agent_gaps, paths["sweep_log"])
        sunk = merge_change_gaps(project_id, change_id, agent_gaps,
                                 [str(row["id"]) for row in pedido_rows(project_id, change_id)])
        added = set(sunk["opened"])
        merged_new = [gap for gap in sunk["gaps"] if gap["id"] in added]
        skipped = sunk["skipped"]
        merged = sunk["gaps"]
        annotations_dir = paths["annotations"]
        log_path = paths["annotation_log"]
    else:
        _record_sweep(base, "annotate", data, agent_gaps)

        existing = parse_gap_rows(gaps_path.read_text(encoding="utf-8"))
        real_existing = [gap for gap in existing if gap.get("id") != "NONE"]
        req_id = real_existing[0].get("parent", "REQ-001").strip("`") if real_existing else "REQ-001"

        topic_merge = merge_gaps_by_topic(real_existing, agent_gaps)  # IMP-257: id, then topic
        merged_new = topic_merge["added"]
        skipped = topic_merge["skipped"]
        merged = topic_merge["gaps"]
        language = _annotation_project_language(project_id, base)
        write_text(gaps_path, render_gaps(project_id, merged, req_id, language))
        annotations_dir = base / "01_discovery" / "annotations"
        log_path = base / "01_discovery" / "agent_annotation_log.md"

    annotations_dir.mkdir(parents=True, exist_ok=True)
    stored = _unique_path(annotations_dir / f"{source.stem}.json")
    archive_payload(base, source, stored)

    write_annotation_log(log_path, project_id, source.stem, merged_new, skipped, data,
                         language if change_id is not None else None)

    graph_nodes = load_graph(project_id).get("nodes", [])
    annotation_id = add_node(
        project_id,
        "DISC",
        "agent_annotation",
        log_path,
        f"Agent annotation: {source.stem}",
        domain="product",
    )
    if change_id is not None:
        add_edge(project_id, change_id, annotation_id, "annotated_by")  # the change's id is its node
    else:
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
    if change_id is None:
        updates: dict[str, object] = {
            "gap_counts": counts,
            "readiness_stage": readiness_stage_after_gap_change(project_id, counts),
            "last_annotation_id": annotation_id,
        }
        if counts.get("blocking_open", 0):
            updates["health"] = "DIRTY"
        update_state(project_id, **updates)

    result: dict[str, object] = {
        "project_id": project_id,
        "annotation_id": annotation_id,
        "path": str(gaps_path.as_posix()),
        "annotation_log": str(log_path.as_posix()),
        "merged": [gap["id"] for gap in merged_new],
        "skipped_duplicates": skipped,
        "gap_counts": counts,
    }
    if change_id is not None:
        result["change_id"] = change_id
    return result


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


_CHALLENGE_REPORT_ES = (
    ("# Challenge Report - ", "# Informe de Challenge - "),
    ("Source: `", "Fuente: `"),
    ("`. Origin: `challenge`.", "`. Origen: `challenge`."),
    ("## Challenge Findings By Lens", "## Hallazgos del Challenge por lente"),
    ("### Lens: `", "### Lente: `"),
    ("| Gap ID | Severity | Technique | Question | Evidence Cited |", "| Gap | Severidad | Técnica | Pregunta | Evidencia citada |"),
    ("_No new challenge gaps merged (all duplicates)._", "_Ningún gap nuevo del challenge (todos duplicados)._"),
    ("Skipped (already present in gaps.md)", "Omitidos (ya están en gaps.md)"),
    ("## Pre-Mortem (imagined failure modes)", "## Pre-mortem (modos de falla imaginados)"),
    ("## Inverted Assumptions", "## Supuestos invertidos"),
    ("- None reported.", "- Nada informado."),
)


def render_challenge_report(
    project_id: str,
    label: str,
    merged: list[dict[str, str]],
    skipped: list[str],
    data: dict,
    language: str = "en",
    respondent_profile: str | None = None,
    localized: bool = False,
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
    taxonomy = technique_risk_taxonomy("pre-mortem")
    if taxonomy:
        taxonomy_rows = "\n".join(
            f"| {row['label']} | {row['definition']} | {row['response']} |" for row in taxonomy
        )
        taxonomy_block = (
            "Classify each imagined failure mode so the BA knows where to spend "
            "scarce discovery effort:\n\n"
            "| Class | What it is | How to respond |\n| --- | --- | --- |\n"
            f"{taxonomy_rows}"
        )
    else:
        taxonomy_block = ""
    inverted_block = "\n".join(f"- {item}" for item in inverted) or "- None reported."
    skipped_block = ", ".join(f"`{gap_id}`" for gap_id in skipped) or "None."
    report = f"""# Challenge Report - {project_id}

Source: `{label}`. Origin: `challenge`. Advanced elicitation (IMP-023): the agent
ran pre-mortem, per-lens role-play, and assumption inversion over the maturing
requirement. Every finding below was validated by the runtime (declared lens,
severity range, verbatim evidence) before merging as a gap — never written by hand.

## Challenge Findings By Lens

{catalog_line}

{lens_section}

Skipped (already present in gaps.md): {skipped_block}

## Pre-Mortem (imagined failure modes)

{taxonomy_block}

{premortem_block}

## Inverted Assumptions

{inverted_block}
"""
    if localized and language == "es":  # IMP-418: a change's report speaks the change's language
        for english, spanish in _CHALLENGE_REPORT_ES:
            report = report.replace(english, spanish)
    return report


def apply_challenge(project_id: str, source: Path, change_id: str | None = None) -> dict[str, object]:
    """Validate, merge, and trace advanced-elicitation findings (IMP-023).

    Reuses the IMP-021 validation protocol but tags gaps `origin: challenge` and
    writes a versionable `01_discovery/challenge_report.md`. With `change_id` (IMP-418) the
    run reviews that change's request, brief and gaps and leaves everything under
    `01_discovery/<CHG>/`; the project's files, state and ledger are not touched.
    """
    base = workspace_path(project_id)
    if not base.exists():
        raise GateRefusal(f"Workspace not found: {project_id}")
    respondent_profile = respondent_profile_from_domain_context(base)
    if change_id is not None:
        from .change_scope import change_channel_gate, change_channel_paths, change_grounding_text

        _change, gaps_path, language = change_channel_gate(project_id, change_id, "challenge")
        paths = change_channel_paths(base, change_id)
        raw_text = change_grounding_text(project_id, change_id)
    else:
        from ..changes import refuse_change_only_channel

        refuse_change_only_channel(project_id, "challenge")
        gaps_path = base / "01_discovery" / "gaps.md"
        if not gaps_path.exists():
            raise GateRefusal("Cannot challenge before /ingest creates 01_discovery/gaps.md.")
        raw_text = raw_input_text(base)
        if not raw_text.strip():
            raise GateRefusal("No raw input found under 00_raw/ to ground the challenge against.")

    data = load_agent_annotation(source)
    challenge_gaps = validate_agent_gaps(data, raw_text, origin="challenge")
    # IMP-347: validated as written; stored and rendered redacted and neutralized
    data, challenge_gaps = _clean_agent_payload(base, data, challenge_gaps)
    if change_id is not None:
        from ..changes import merge_change_gaps
        from ..extraction.inventory import pedido_rows

        _record_sweep(base, "challenge", data, challenge_gaps, paths["sweep_log"])
        sunk = merge_change_gaps(project_id, change_id, challenge_gaps,
                                 [str(row["id"]) for row in pedido_rows(project_id, change_id)])
        added = set(sunk["opened"])
        merged_new = [gap for gap in sunk["gaps"] if gap["id"] in added]
        skipped = sunk["skipped"]
        merged = sunk["gaps"]
        challenges_dir = paths["challenges"]
        report_path = paths["challenge_report"]
    else:
        _record_sweep(base, "challenge", data, challenge_gaps)

        existing = parse_gap_rows(gaps_path.read_text(encoding="utf-8"))
        real_existing = [gap for gap in existing if gap.get("id") != "NONE"]
        req_id = real_existing[0].get("parent", "REQ-001").strip("`") if real_existing else "REQ-001"

        topic_merge = merge_gaps_by_topic(real_existing, challenge_gaps)  # IMP-257: id, then topic
        merged_new = topic_merge["added"]
        skipped = topic_merge["skipped"]
        merged = topic_merge["gaps"]
        language = _annotation_project_language(project_id, base)
        write_text(gaps_path, render_gaps(project_id, merged, req_id, language))
        challenges_dir = base / "01_discovery" / "challenges"
        report_path = base / "01_discovery" / "challenge_report.md"

    challenges_dir.mkdir(parents=True, exist_ok=True)
    stored = _unique_path(challenges_dir / f"{source.stem}.json")
    archive_payload(base, source, stored)

    write_text(report_path, render_challenge_report(project_id, source.stem, merged_new, skipped, data, language,
                                                    respondent_profile, localized=change_id is not None))

    graph_nodes = load_graph(project_id).get("nodes", [])
    challenge_id = add_node(
        project_id,
        "DISC",
        "challenge_report",
        report_path,
        f"Challenge report: {source.stem}",
        domain="product",
    )
    if change_id is not None:
        add_edge(project_id, change_id, challenge_id, "challenged_by")  # the change's id is its node
    else:
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
    if change_id is None:
        updates: dict[str, object] = {
            "gap_counts": counts,
            "readiness_stage": readiness_stage_after_gap_change(project_id, counts),
            "last_challenge_id": challenge_id,
        }
        if counts.get("blocking_open", 0):
            updates["health"] = "DIRTY"
        update_state(project_id, **updates)

    result: dict[str, object] = {
        "project_id": project_id,
        "challenge_id": challenge_id,
        "path": str(gaps_path.as_posix()),
        "challenge_report": str(report_path.as_posix()),
        "merged": [gap["id"] for gap in merged_new],
        "skipped_duplicates": skipped,
        "gap_counts": counts,
    }
    if change_id is not None:
        result["change_id"] = change_id
    return result


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


_SCRUTINY_REPORT_ES = (
    ("# Scrutiny Report - ", "# Informe de Scrutiny - "),
    ("Source: `", "Fuente: `"),
    ("`. Origin: `scrutiny`. ", "`. Origen: `scrutiny`. "),
    ("Lens filter: all declared lenses.", "Filtro de lente: todas las lentes declaradas."),
    ("Lens filter: `", "Filtro de lente: `"),
    ("The agent scrutinized raw requirement evidence plus local domain context through\n"
     "the Ignite lens model. Every finding below was validated by the runtime\n"
     "(declared lens, severity range, valid finding type, and a verbatim local\n"
     "citation) before merging as a gap. The agent proposes; the BA remains in control.",
     "El agente escrutó la evidencia del pedido a través del modelo de lentes de Ignite.\n"
     "El runtime validó cada hallazgo (lente declarada, rango de severidad, tipo de hallazgo válido\n"
     "y una cita local textual) antes de incorporarlo como gap. El agente propone; el BA conserva el control."),
    ("## Scrutiny Findings By Lens", "## Hallazgos del Scrutiny por lente"),
    ("### Lens: `", "### Lente: `"),
    ("| Gap ID | Severity | Finding Type | Question | Evidence Cited |", "| Gap | Severidad | Tipo de hallazgo | Pregunta | Evidencia citada |"),
    ("_No new scrutiny gaps merged (all duplicates)._", "_Ningún gap nuevo del scrutiny (todos duplicados)._"),
    ("Skipped (already present in gaps.md)", "Omitidos (ya están en gaps.md)"),
    ("None.", "Ninguno."),
)


def render_scrutiny_report(
    project_id: str,
    label: str,
    merged: list[dict[str, str]],
    skipped: list[str],
    data: dict,
    lens_filter: str | None = None,
    language: str | None = None,
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
    report = f"""# Scrutiny Report - {project_id}

Source: `{label}`. Origin: `scrutiny`. {lens_note}

The agent scrutinized raw requirement evidence plus local domain context through
the Ignite lens model. Every finding below was validated by the runtime
(declared lens, severity range, valid finding type, and a verbatim local
citation) before merging as a gap. The agent proposes; the BA remains in control.

## Scrutiny Findings By Lens

{lens_section}

Skipped (already present in gaps.md): {skipped_block}
"""
    return _speak(report, _SCRUTINY_REPORT_ES) if language == "es" else report  # IMP-418: a change's report speaks its language


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
    change_id: str | None = None,
) -> dict[str, object]:
    """Validate and merge systematic multi-lens scrutiny findings (IMP-066).

    With ``mode="implementability-probe"`` (IMP-119) the same machinery runs the
    pre-flight implementability probe: per-RU cited gaps, probe finding types,
    and ``origin: implementability-probe``. With ``change_id`` (IMP-418) the run scrutinizes that
    change's request, brief and gaps (the probe is per project unit and refuses); everything stays under
    ``01_discovery/<CHG>/`` and the project's files, state and knowledge ledger are not touched.
    """
    spec = _scrutiny_mode(mode)
    is_probe = spec["origin"] == "implementability-probe"
    base = workspace_path(project_id)
    if not base.exists():
        raise GateRefusal(f"Workspace not found: {project_id}")
    language = "en"
    if change_id is not None:
        from .change_scope import change_channel_gate, change_channel_paths, change_grounding_text

        if is_probe:
            from ..changes import refusal_language

            es = refusal_language(project_id, change_id) == "es"
            file_word = "ARCHIVO" if es else "FILE"
            raise InputError(
                (f"--mode implementability-probe no va con --change: el sondeo es por unidad RU del proyecto; "
                 f"en el cambio usá /scrutinize {project_id} --source {file_word} --change {change_id}") if es
                else (f"--mode implementability-probe does not go with --change: the probe is per RU unit of the project; "
                      f"in the change use /scrutinize {project_id} --source {file_word} --change {change_id}"),
                next_step=f"/scrutinize {project_id} --source {file_word} --change {change_id}")
        _change, gaps_path, language = change_channel_gate(project_id, change_id, "scrutinize")
        paths = change_channel_paths(base, change_id)
        grounding_text = change_grounding_text(project_id, change_id)
    else:
        from ..changes import refuse_change_only_channel

        refuse_change_only_channel(project_id, "scrutinize")
        gaps_path = base / "01_discovery" / "gaps.md"
        if not gaps_path.exists():
            raise GateRefusal("Cannot scrutinize before /ingest creates 01_discovery/gaps.md.")

        grounding_text = scrutiny_grounding_text(base)
        if not grounding_text.strip():
            raise GateRefusal("No raw or domain context evidence found under 00_raw/ to ground scrutiny against.")

    lens_filter = lens.strip().lower() if lens else None
    data = load_agent_annotation(source)
    known_units = known_requirement_unit_ids(base) if spec["require_unit"] else None
    scrutiny_gaps = validate_scrutiny_gaps(data, grounding_text, lens_filter, mode=mode, known_units=known_units)
    # IMP-347: validated as written; stored and rendered redacted and neutralized
    data, scrutiny_gaps = _clean_agent_payload(base, data, scrutiny_gaps)
    if change_id is not None:
        from ..changes import merge_change_gaps
        from ..extraction.inventory import pedido_rows

        _record_sweep(base, str(spec["origin"]), data, scrutiny_gaps, paths["sweep_log"])
        sunk = merge_change_gaps(project_id, change_id, scrutiny_gaps,
                                 [str(row["id"]) for row in pedido_rows(project_id, change_id)])
        added = set(sunk["opened"])
        merged_new: list[dict[str, str]] = [gap for gap in sunk["gaps"] if gap["id"] in added]
        skipped: list[str] = sunk["skipped"]
        merged = sunk["gaps"]
        store_dir = paths["scrutiny"]
        report_path = paths["scrutiny_report"]
    else:
        _record_sweep(base, str(spec["origin"]), data, scrutiny_gaps)

        existing = parse_gap_rows(gaps_path.read_text(encoding="utf-8"))
        real_existing = [gap for gap in existing if gap.get("id") != "NONE"]
        req_id = real_existing[0].get("parent", "REQ-001").strip("`") if real_existing else "REQ-001"

        topic_merge = merge_gaps_by_topic(real_existing, scrutiny_gaps)  # IMP-257: id, then topic
        merged_new = topic_merge["added"]
        skipped = topic_merge["skipped"]
        merged = topic_merge["gaps"]
        language = _annotation_project_language(project_id, base)
        write_text(gaps_path, render_gaps(project_id, merged, req_id, language))
        store_dir = base / "01_discovery" / str(spec["store_dir"])
        report_path = base / "01_discovery" / str(spec["report_name"])

    store_dir.mkdir(parents=True, exist_ok=True)
    stored = _unique_path(store_dir / f"{source.stem}.json")
    archive_payload(base, source, stored)

    if is_probe:
        report_text = render_probe_report(project_id, source.stem, merged_new, skipped, data)
    else:
        report_text = render_scrutiny_report(project_id, source.stem, merged_new, skipped, data, lens_filter,
                                             language if change_id is not None else None)
    write_text(report_path, report_text)

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
    if change_id is not None:
        add_edge(project_id, change_id, report_id, str(spec["raw_relation"]))  # the change's id is its node
    else:
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
    ledger = refresh_knowledge_ledger(project_id, broker) if change_id is None else None  # the ledger is the project's
    mark_source_processed(project_id, source, f"{spec['origin']}_applied", report_id)

    counts = count_gaps(merged)
    origin = str(spec["origin"])
    counts[str(spec["origin_count_key"])] = sum(1 for gap in merged if gap.get("origin") == origin)
    if ledger is not None:
        updates: dict[str, object] = {
            "gap_counts": counts,
            "readiness_stage": readiness_stage_after_gap_change(project_id, counts),
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
        **({"knowledge_state": str(ledger["md_path"].as_posix())} if ledger is not None else {}),
        "merged": [gap["id"] for gap in merged_new],
        "skipped_duplicates": skipped,
        "gap_counts": counts,
    }
    if ledger is None:
        result["change_id"] = change_id
    if is_probe:
        result["probe_id"] = report_id
        result["implementability_probe_report"] = str(report_path.as_posix())
    else:
        result["scrutiny_id"] = report_id
        result["scrutiny_report"] = str(report_path.as_posix())
    return result
