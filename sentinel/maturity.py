from __future__ import annotations

import re
from pathlib import Path

from .discovery import (
    BRIEF_SECTION_FOR_GAP,
    PRD_SECTION_FOR_GAP,
    brief_section_for_gap,
    extract_functional_signals,
    extract_metric_signals,
    extract_personas,
    parse_gap_rows,
    raw_input_text,
    split_evidence_sentences,
)
from .core.markdown import parse_table_rows
from .memory import ContextBroker
from .core.graph import add_edge, add_node, nodes_by_type
from .workspace import load_config, read_json, state_path, update_state, workspace_path


# --- IMP-025: per-section brief readiness + soft /brief gate ------------------
#
# A quantified "definition of ready" for discovery: which narrative brief
# sections (1-6) are evidence-backed vs still pending, the overall coverage
# score, and — for each poor section — the gaps that feed it (inverse of the
# IMP-024 gap→section map). Exposed in /maturity and /status (via maturity_metrics)
# and used by the soft /brief gate.

_BRIEF_SECTION_RE = re.compile(r"^## (\d+)\.", re.M)
_BRIEF_TRACKED_SECTIONS = ("1", "2", "3", "4", "5", "6")
_BRIEF_PENDING_MARKERS = ("[PENDING INPUT]", "TBD", "PENDING DOMAIN", "No structured evidence", "Documentar el", "Documentar la")
_BRIEF_SECTION_TITLES = {
    "1": "Identidad y Valor",
    "2": "Lente de Negocio (actores)",
    "3": "Lente de Producto (proceso/journey)",
    "4": "Lente de Diseño",
    "5": "Lente Técnico",
    "6": "Gobernanza y Restricciones",
}
_GAPS_FOR_BRIEF_SECTION: dict[str, list[str]] = {}
for _gap, _sec in BRIEF_SECTION_FOR_GAP.items():
    _GAPS_FOR_BRIEF_SECTION.setdefault(_sec, []).append(_gap)

_PRD_SECTION_RE = re.compile(r"^## (\d+)\.", re.M)
_PRD_TRACKED_SECTIONS = tuple(str(i) for i in range(1, 14))
_PRD_PENDING_MARKERS = (
    "[PENDING INPUT]",
    "GAP-PRD-",
    "GAP-METRIC-SOURCE",
    "GAP-TECH-",
    "GAP-DESIGN-",
    "GAP-QUALITY",
    "GAP-DELIVERY",
    "GAP-GOVERNANCE",
)
_PRD_SECTION_TITLES = {
    "1": "Executive Summary / Problem",
    "2": "Scope",
    "3": "Users And Personas",
    "4": "Functional Requirements",
    "5": "Non-Functional Requirements",
    "6": "Business Success Criteria (KPIs)",
    "7": "Jobs To Be Done",
    "8": "Dependency Map",
    "9": "Risks And Assumptions",
    "10": "MVP, Roadmap, And Rollout",
    "11": "Mandatory Constraints",
    "12": "Suggested Or Assigned Team",
    "13": "Glossary",
}
_GAPS_FOR_PRD_SECTION: dict[str, list[str]] = {}
for _gap, _sec in PRD_SECTION_FOR_GAP.items():
    _GAPS_FOR_PRD_SECTION.setdefault(_sec, []).append(_gap)


def brief_section_readiness(brief_text: str) -> dict[str, object]:
    """Classify narrative sections 1-6 as populated/pending and score coverage."""
    bodies: dict[str, list[str]] = {}
    current = None
    for line in brief_text.splitlines():
        match = _BRIEF_SECTION_RE.match(line)
        if match:
            current = match.group(1)
            bodies.setdefault(current, [])
        elif current is not None:
            bodies[current].append(line)
    sections: dict[str, dict[str, object]] = {}
    poor: list[dict[str, object]] = []
    populated = 0
    for sec in _BRIEF_TRACKED_SECTIONS:
        body = "\n".join(bodies.get(sec, []))
        is_pending = (not body.strip()) or any(marker in body for marker in _BRIEF_PENDING_MARKERS)
        citations = body.count("00_raw/") + body.count("`GAP-") + body.count("`CHG-")
        status = "pending" if is_pending else "populated"
        sections[sec] = {"status": status, "evidence_citations": citations}
        if is_pending:
            feeding = sorted(_GAPS_FOR_BRIEF_SECTION.get(sec, []))
            sections[sec]["feeding_gaps"] = feeding
            poor.append({"section": sec, "title": _BRIEF_SECTION_TITLES[sec], "feeding_gaps": feeding})
        else:
            populated += 1
    coverage_score = round(populated / len(_BRIEF_TRACKED_SECTIONS), 3)
    return {
        "coverage_score": coverage_score,
        "sections_populated": populated,
        "sections_total": len(_BRIEF_TRACKED_SECTIONS),
        "sections": sections,
        "poor_sections": poor,
    }


def brief_gate_warnings(readiness: dict[str, object], language: str = "en") -> list[str]:
    """Human-readable warnings naming poor sections and the gaps that feed them."""
    warnings: list[str] = []
    for poor in readiness.get("poor_sections", []):  # type: ignore[union-attr]
        gaps = ", ".join(f"`{g}`" for g in poor["feeding_gaps"]) or ("contexto de dominio" if language == "es" else "domain context")
        if language == "es":
            warnings.append(f"Sección {poor['section']} ({poor['title']}) sin evidencia suficiente; alimentarla vía {gaps}.")
        else:
            warnings.append(f"Section {poor['section']} ({poor['title']}) lacks enough evidence; feed it via {gaps}.")
    return warnings


def prd_section_readiness(prd_text: str) -> dict[str, object]:
    """Classify numbered PRD sections as populated/pending and score coverage."""
    bodies: dict[str, list[str]] = {}
    current = None
    for line in prd_text.splitlines():
        match = _PRD_SECTION_RE.match(line)
        if match:
            current = match.group(1)
            bodies.setdefault(current, [])
        elif line.startswith("# ") and current is not None:
            current = None
        elif current is not None:
            bodies[current].append(line)
    sections: dict[str, dict[str, object]] = {}
    poor: list[dict[str, object]] = []
    populated = 0
    for sec in _PRD_TRACKED_SECTIONS:
        body = "\n".join(bodies.get(sec, []))
        is_pending = (not body.strip()) or any(marker in body for marker in _PRD_PENDING_MARKERS)
        citations = count_prd_evidence_citations(body)
        status = "pending" if is_pending else "populated"
        sections[sec] = {"status": status, "evidence_citations": citations}
        if is_pending:
            feeding = sorted(_GAPS_FOR_PRD_SECTION.get(sec, []))
            sections[sec]["feeding_gaps"] = feeding
            poor.append({"section": sec, "title": _PRD_SECTION_TITLES[sec], "feeding_gaps": feeding})
        else:
            populated += 1
    coverage_score = round(populated / len(_PRD_TRACKED_SECTIONS), 3)
    return {
        "coverage_score": coverage_score,
        "sections_populated": populated,
        "sections_total": len(_PRD_TRACKED_SECTIONS),
        "sections": sections,
        "poor_sections": poor,
    }


def count_prd_evidence_citations(body: str) -> int:
    citation_patterns = (
        r"`REQ-[A-Z0-9-]+`",
        r"`REQ-\d+`",
        r"`CHG-\d+`",
        r"`DEC-\d+`",
        r"`GAP-[A-Z0-9-]+`",
        r"`SPEC-[A-Z0-9-]+`",
        r"`00_raw/`",
        r"`identity_seeds\.md`",
        r"`02_requirements/[^`]+`",
        r"\(source: `[^`]+`\)",
        r"\(fuente: `[^`]+`\)",
    )
    return sum(len(re.findall(pattern, body)) for pattern in citation_patterns)


def prd_gate_warnings(readiness: dict[str, object], language: str = "en") -> list[str]:
    """Human-readable warnings naming poor PRD sections and feeding gaps."""
    warnings: list[str] = []
    for poor in readiness.get("poor_sections", []):  # type: ignore[union-attr]
        gaps = ", ".join(f"`{g}`" for g in poor["feeding_gaps"]) or ("contexto de dominio" if language == "es" else "domain context")
        if language == "es":
            warnings.append(f"SecciÃ³n PRD {poor['section']} ({poor['title']}) bajo umbral; alimentarla vÃ­a {gaps}.")
        else:
            warnings.append(f"PRD section {poor['section']} ({poor['title']}) is below threshold; feed it via {gaps}.")
    return warnings


# --- IMP-028: maturation-cycle telemetry --------------------------------------
#
# Visibility into where maturation stalls: how many /resolve-gaps rounds ran, how
# closed gaps split by provenance (checklist vs agent vs challenge), and how long
# the oldest blocking gap has survived (in resolve rounds). All fields are optional
# and additive — existing workspaces are unaffected.

def maturation_telemetry(project_id: str) -> dict[str, object]:
    base = workspace_path(project_id)
    gaps_path = base / "01_discovery" / "gaps.md"
    gaps = parse_gap_rows(gaps_path.read_text(encoding="utf-8")) if gaps_path.exists() else []
    log_path = base / "01_discovery" / "gap_resolution_log.md"
    iterations = 0
    closed_by_response_source = {"client": 0, "domain": 0, "inference": 0}
    if log_path.exists():
        for line in log_path.read_text(encoding="utf-8").splitlines():
            if not line.startswith("| ") or "CHG-" not in line:
                continue
            iterations += 1
            cells = parse_table_rows(line)[0]
            if len(cells) >= 9:
                closed_by_response_source["client"] += parse_int(cells[6])
                closed_by_response_source["domain"] += parse_int(cells[7])
                closed_by_response_source["inference"] += parse_int(cells[8])
    closed_by_origin: dict[str, int] = {}
    closed_total = 0
    open_blocking = 0
    ears_eligible_not_normalized: list[str] = []
    for gap in gaps:
        status = str(gap.get("status", "OPEN")).upper()
        severity = str(gap.get("severity", "")).lower()
        origin = str(gap.get("origin", "checklist")).strip() or "checklist"
        if status == "CLOSED":
            closed_total += 1
            closed_by_origin[origin] = closed_by_origin.get(origin, 0) + 1
            if "EARS-eligible" in str(gap.get("resolution_note", "")):
                ears_eligible_not_normalized.append(gap["id"])
        elif status in {"OPEN", "ANSWERED", "PARTIALLY_CLOSED"} and severity in {"critical", "high"}:
            open_blocking += 1
    closed_by_origin_pct = {
        origin: round(count / closed_total, 3) for origin, count in closed_by_origin.items()
    } if closed_total else {}
    response_source_total = sum(closed_by_response_source.values())
    closed_by_response_source_pct = {
        source: round(count / response_source_total, 3)
        for source, count in closed_by_response_source.items()
        if count
    } if response_source_total else {}
    reopened_ids = reopened_gap_ids_from_sync_reports(base)
    return {
        "resolve_iterations": iterations,
        "closed_total": closed_total,
        "closed_by_origin": closed_by_origin,
        "closed_by_origin_pct": closed_by_origin_pct,
        "closed_by_response_source": closed_by_response_source,
        "closed_by_response_source_pct": closed_by_response_source_pct,
        "reopened_by_sync_total": len(reopened_ids),
        "reopened_by_sync_gap_ids": reopened_ids,
        "ears_eligible_not_normalized_total": len(ears_eligible_not_normalized),
        "ears_eligible_not_normalized_gap_ids": sorted(set(ears_eligible_not_normalized)),
        "open_blocking_gaps": open_blocking,
        # Age proxy: a still-open blocking gap has survived every resolve round.
        "oldest_blocking_age_rounds": iterations if open_blocking else 0,
    }


def parse_int(value: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def reopened_gap_ids_from_sync_reports(base: Path) -> list[str]:
    ids: list[str] = []
    for path in sorted((base / "07_changes").rglob("*_impact_report.md")):
        text = path.read_text(encoding="utf-8", errors="ignore")
        section = text.split("## Reopened Closed Gaps", 1)
        if len(section) < 2:
            continue
        body = section[1].split("\n## ", 1)[0]
        for match in re.finditer(r"`(GAP-[A-Z0-9-]+)`", body):
            ids.append(match.group(1))
    return sorted(set(ids))


def maturity_metrics(project_id: str, persist_development_readiness: bool = False) -> dict[str, object]:
    """Quantified maturity: gap closure by severity plus evidence scores of generated artifacts."""
    from .validation import score_artifact_text

    base = workspace_path(project_id)
    gaps_path = base / "01_discovery" / "gaps.md"
    gaps = parse_gap_rows(gaps_path.read_text(encoding="utf-8")) if gaps_path.exists() else []
    open_by_severity: dict[str, int] = {}
    closed = 0
    for gap in gaps:
        status = str(gap.get("status", "OPEN")).upper()
        severity = str(gap.get("severity", "unknown")).lower()
        if status == "CLOSED":
            closed += 1
        else:
            open_by_severity[severity] = open_by_severity.get(severity, 0) + 1
    total = len(gaps)
    gap_closure_rate = round(closed / total, 3) if total else 1.0

    artifact_scores: dict[str, float] = {}
    targets = {
        "project-brief.md": base / "02_requirements" / "project-brief.md",
        "prd.md": base / "03_specs" / "prd.md",
        "specs.md": base / "03_specs" / "specs.md",
    }
    for name, path in targets.items():
        if path.exists():
            artifact_scores[name] = float(score_artifact_text(path.read_text(encoding="utf-8"))["score"])
    evidence_score = round(sum(artifact_scores.values()) / len(artifact_scores), 3) if artifact_scores else None

    if evidence_score is None:
        maturity_score = gap_closure_rate
    else:
        maturity_score = round((gap_closure_rate + evidence_score) / 2, 3)
    metrics: dict[str, object] = {
        "gap_total": total,
        "gaps_closed": closed,
        "gap_closure_rate": gap_closure_rate,
        "open_gaps_by_severity": open_by_severity,
        "artifact_evidence_scores": artifact_scores,
        "evidence_score": evidence_score,
        "maturity_score": maturity_score,
    }
    # IMP-025: per-section brief readiness once a brief exists.
    brief_path = base / "02_requirements" / "project-brief.md"
    if brief_path.exists():
        metrics["brief_section_readiness"] = brief_section_readiness(brief_path.read_text(encoding="utf-8"))
    prd_path = base / "03_specs" / "prd.md"
    if prd_path.exists():
        metrics["prd_section_readiness"] = prd_section_readiness(prd_path.read_text(encoding="utf-8"))
    # IMP-028: maturation-cycle telemetry.
    metrics["maturation_telemetry"] = maturation_telemetry(project_id)
    assumptions_path = base / "01_discovery" / "assumptions.md"
    if assumptions_path.exists():
        from .assumptions import assumption_rows, summarize_assumptions

        metrics["assumptions"] = summarize_assumptions(assumption_rows(assumptions_path.read_text(encoding="utf-8")))
    from .development_readiness import compute_development_readiness

    metrics["development_readiness"] = compute_development_readiness(
        project_id,
        persist=persist_development_readiness,
    )
    return metrics


def evaluate(project_id: str) -> dict[str, object]:
    base = workspace_path(project_id)
    gaps_path = base / "01_discovery" / "gaps.md"
    requirements_path = base / "02_requirements" / "requirements.md"
    gaps_text = gaps_path.read_text(encoding="utf-8") if gaps_path.exists() else ""
    req_text = requirements_path.read_text(encoding="utf-8") if requirements_path.exists() else ""
    config = load_config(project_id)
    blocking = set(config.get("maturity", {}).get("blocking_gap_severities", ["critical", "high"]))
    blocking_gaps = parse_blocking_gaps(gaps_text, blocking)
    readiness = "READY_FOR_SPECS" if not blocking_gaps and req_text else "BLOCKED"
    project_brief = None
    if readiness == "READY_FOR_SPECS":
        project_brief = materialize_project_brief(project_id, req_text, gaps_text)
    report_path = base / "01_discovery" / "requirement_maturity_report.md"
    report_path.write_text(render_report(project_id, readiness, blocking_gaps, project_brief), encoding="utf-8")
    ContextBroker(project_id).index_artifact(
        "MATURITY-001",
        "maturity_report",
        report_path,
        report_path.read_text(encoding="utf-8"),
        trace_ids=["MATURITY-001"],
    )
    metrics = maturity_metrics(project_id, persist_development_readiness=True)
    previous = read_json(state_path(project_id), {}).get("maturity_metrics") or {}
    if isinstance(previous, dict) and "maturity_score" in previous:
        metrics["trend_vs_previous_run"] = round(
            float(metrics["maturity_score"]) - float(previous["maturity_score"]), 3
        )
    update_state(
        project_id,
        phase="maturity_evaluated",
        health="CLEAN" if readiness.startswith("READY") else "DIRTY",
        maturity_metrics=metrics,
    )
    return {
        "readiness": readiness,
        "blocking_gaps": blocking_gaps,
        "metrics": metrics,
        "report": str(report_path),
        "project_brief": str(project_brief) if project_brief else None,
    }


def generate_project_brief(project_id: str) -> dict[str, object]:
    base = workspace_path(project_id)
    gaps_path = base / "01_discovery" / "gaps.md"
    requirements_path = base / "02_requirements" / "requirements.md"
    if not requirements_path.exists():
        raise RuntimeError("Cannot generate project brief before /ingest creates requirements.md.")
    req_text = requirements_path.read_text(encoding="utf-8")
    gaps_text = gaps_path.read_text(encoding="utf-8") if gaps_path.exists() else ""
    brief_path = materialize_project_brief(project_id, req_text, gaps_text)
    # IMP-025: soft readiness gate. Default warns; opt-in strict mode blocks the
    # advance to READY_FOR_SPECS when section coverage is below threshold.
    config = load_config(project_id)
    gate = config.get("brief_gate", {}) if isinstance(config.get("brief_gate", {}), dict) else {}
    threshold = float(gate.get("threshold", 0.5))
    strict = bool(gate.get("strict", False))
    language = config.get("project_language") if config.get("project_language") in {"es", "en"} else "en"
    readiness = brief_section_readiness(brief_path.read_text(encoding="utf-8"))
    below = float(readiness["coverage_score"]) < threshold
    warnings = brief_gate_warnings(readiness, language) if below else []
    result = {
        "project_id": project_id,
        "project_brief": str(brief_path),
        "path": str(brief_path),
        "brief_section_readiness": readiness,
        "warnings": warnings,
        "brief_gate": {"threshold": threshold, "strict": strict, "below_threshold": below},
    }
    if strict and below:
        update_state(project_id, phase="brief_below_threshold", readiness_stage="BRIEF_BELOW_THRESHOLD")
        result["blocked"] = True
        return result
    update_state(project_id, phase="brief_completed", readiness_stage="READY_FOR_SPECS", health="CLEAN")
    result["blocked"] = False
    return result


def parse_blocking_gaps(text: str, blocking_severities: set[str]) -> list[str]:
    blocking_gaps = []
    for line in text.splitlines():
        rows = parse_table_rows(line, strip_code_ticks=False)
        cells = rows[0] if rows else []
        if not cells or not cells[0].startswith("GAP-"):
            continue
        if len(cells) >= 4:
            severity = cells[2] if cells[1].lower() not in blocking_severities else cells[1]
            status = cells[3] if cells[1].lower() not in blocking_severities else cells[2]
            if status.upper() in {"OPEN", "PARTIALLY_CLOSED", "ANSWERED"} and severity.lower() in blocking_severities:
                blocking_gaps.append(cells[0])
    return blocking_gaps


def materialize_project_brief(project_id: str, req_text: str, gaps_text: str) -> Path:
    base = workspace_path(project_id)
    discovery = base / "01_discovery"
    brief_path = base / "02_requirements" / "project-brief.md"
    seeds_text = read_optional(discovery / "identity_seeds.md")
    decisions_text = read_optional(discovery / "decisions.md")
    lens_review_text = read_optional(discovery / "lens_review.md")
    assumptions_text = read_optional(discovery / "assumptions.md")
    # IMP-024: compile sections 1-6 from real evidence (raw client input plus
    # confirmed answers of closed gaps) instead of leaving template TBDs.
    raw_text = raw_input_text(base)
    gap_answers = parse_gap_answers(seeds_text + "\n" + decisions_text)
    state = read_json(state_path(project_id), {})
    language = state.get("project_language") if state.get("project_language") in {"es", "en"} else "en"
    brief_path.write_text(
        render_project_brief(
            project_id, req_text, gaps_text, seeds_text, decisions_text, lens_review_text,
            raw_text=raw_text, gap_answers=gap_answers, language=language,
            assumptions_text=assumptions_text,
        ),
        encoding="utf-8",
    )

    existing = nodes_by_type(project_id, "project_brief")
    if existing:
        brief_id = existing[0]["id"]
    else:
        brief_id = add_node(project_id, "REQ", "project_brief", brief_path, "Mature project brief", domain="product")
        for req in nodes_by_type(project_id, "requirement"):
            add_edge(project_id, req["id"], brief_id, "crystallizes")
        for seed in nodes_by_type(project_id, "identity_seed_bank"):
            add_edge(project_id, seed["id"], brief_id, "grounds")
        for review in nodes_by_type(project_id, "lens_review"):
            add_edge(project_id, review["id"], brief_id, "informs")

    ContextBroker(project_id).index_artifact(
        brief_id,
        "project_brief",
        brief_path,
        brief_path.read_text(encoding="utf-8"),
        trace_ids=[brief_id],
    )
    state = read_json(state_path(project_id), {})
    artifacts = dict(state.get("artifacts", {}))
    artifacts["project_brief"] = str(brief_path.as_posix())
    update_state(project_id, artifacts=artifacts)
    return brief_path


def read_optional(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


# --- IMP-024: brief compiler helpers ------------------------------------------
#
# The brief's narrative sections (1-6) are compiled from real evidence with a
# citation, never left as generic TBD. Evidence sources, in priority order:
# confirmed answers of closed gaps (routed by brief_section_for_gap), then the
# raw client input (objective, actors, scope, as-is/to-be, metric signals). A
# section with no anchor evidence renders an explicit [PENDING INPUT] pointing to
# the gap that tracks it (sections 4-6 at discovery time). No invented text: a
# claim is either backed by a quoted evidence sentence + path, or it is pending.

PENDING_INPUT = "[PENDING INPUT]"

_OBJECTIVE_CUES = ("the goal", "goal is", "objetivo", "objective", "aim to", "purpose", "so that", "in order to")
_ASIS_CUES = ("today", "currently", "right now", "hoy", "actualmente", "proceso actual", "by hand", "a mano", "manual")
_OUT_SCOPE_CUES = ("out of scope", "out-of-scope", "fuera de alcance")
_IN_SCOPE_CUES = ("in scope", "scope:", "scope is", "alcance")


def parse_gap_answers(text: str) -> dict[str, dict[str, str]]:
    """Map gap_id -> confirmed answer from the gap-resolution seed/decision tables."""
    answers: dict[str, dict[str, str]] = {}
    for line in text.splitlines():
        rows = parse_table_rows(line)
        cells = rows[0] if rows else []
        if len(cells) >= 5 and cells[1].startswith("GAP-") and cells[2].upper() == "CONFIRMED":
            gap_id = cells[1]
            answers.setdefault(gap_id, {"statement": cells[3], "source": cells[4]})
    return answers


def _first_sentence_with(sentences: list[str], cues: tuple[str, ...]) -> str:
    for sentence in sentences:
        lowered = sentence.lower()
        if any(cue in lowered for cue in cues):
            return sentence
    return ""


def _cite(sentence: str, language: str) -> str:
    label = "fuente" if language == "es" else "source"
    return f'"{sentence}" _({label}: `00_raw/`)_'


def _initiative_name(raw_text: str) -> str:
    prefixes = ("client request:", "pedido del cliente:", "client req:", "requerimiento:")
    for line in raw_text.splitlines():
        line = line.strip()
        if line.startswith("# "):
            name = line.lstrip("# ").strip()
            low = name.lower()
            for pre in prefixes:
                if low.startswith(pre):
                    return name[len(pre):].strip()
            return name
    return ""


def _gap_answer_block(gap_answers: dict[str, dict[str, str]], section: str, language: str) -> str:
    """Render confirmed gap answers routed to a brief section, or '' if none."""
    lines = []
    for gap_id, payload in gap_answers.items():
        if brief_section_for_gap(gap_id) == section:
            src = payload.get("source", "")
            tag = f" _(`{gap_id}` / `{src}`)_" if src else f" _(`{gap_id}`)_"
            lines.append(f"- {payload['statement']}{tag}")
    return "\n".join(lines)


def _assumption_block(project_id: str, section: str, language: str) -> str:
    from .assumptions import assumptions_by_brief_section, render_assumption_bullets

    return render_assumption_bullets(assumptions_by_brief_section(project_id).get(section, []), language)


def _pending(section_gap: str, language: str) -> str:
    if language == "es":
        return f"- {PENDING_INPUT}: sin evidencia en el input; se rastrea en `{section_gap}`. Aportar en el context pack del dominio."
    return f"- {PENDING_INPUT}: no evidence in client input yet; tracked by `{section_gap}`. Provide via the domain context pack."


def compile_brief_sections(
    raw_text: str,
    gap_answers: dict[str, dict[str, str]],
    req_text: str,
    language: str,
    project_id: str = "",
) -> dict[str, str]:
    """Compile narrative sections 1-6 from evidence. Returns rendered blocks."""
    es = language == "es"
    sentences = split_evidence_sentences(raw_text)
    name = _initiative_name(raw_text)
    objective = _first_sentence_with(sentences, _OBJECTIVE_CUES)
    personas = extract_personas(raw_text)
    functionals = extract_functional_signals(raw_text)
    metrics = extract_metric_signals(raw_text)
    asis = _first_sentence_with(sentences, _ASIS_CUES)
    in_scope = ""
    out_scope = ""
    for sentence in sentences:
        low = sentence.lower()
        if not out_scope and any(c in low for c in _OUT_SCOPE_CUES):
            out_scope = sentence
        elif not in_scope and any(c in low for c in _IN_SCOPE_CUES):
            in_scope = sentence

    blocks: dict[str, str] = {}

    # --- Section 1: Identidad y Valor ---
    name_line = (
        (f"Iniciativa: {name}" if es else f"Initiative: {name}") + f" _({'fuente' if es else 'source'}: `00_raw/`)_"
        if name else (f"Iniciativa: {primary_requirement(req_text)}" if es else f"Initiative: {primary_requirement(req_text)}")
    )
    pain_line = primary_requirement(req_text)
    s1_answers = _gap_answer_block(gap_answers, "1", language)
    if objective:
        outcome_line = (f"- Resultado esperado: {_cite(objective, language)}" if es
                        else f"- Expected outcome: {_cite(objective, language)}")
    elif s1_answers:
        outcome_line = s1_answers
    else:
        outcome_line = _pending("GAP-OBJECTIVE", language)
    if metrics:
        m = metrics[0]
        metric_line = (f"- Métrica: `{m['metric']}` — {_cite(m['evidence'], language)}" if es
                       else f"- Metric: `{m['metric']}` — {_cite(m['evidence'], language)}")
    else:
        metric_line = ("- Métrica: aún no cuantificada; baseline, fuente y target se rastrean en `GAP-METRIC-SOURCE`."
                       if es else
                       "- Metric: not yet quantified; baseline, source, and target tracked by `GAP-METRIC-SOURCE`.")
    blocks["1"] = f"{name_line}\n\n{('Dolor principal' if es else 'Main pain')}:\n{pain_line}\n\n{('Resultado y métricas' if es else 'Outcome and metrics')}:\n{outcome_line}\n{metric_line}"

    # --- Section 2: Lente de Negocio: Actores y Necesidades ---
    s2_answers = _gap_answer_block(gap_answers, "2", language)
    if personas:
        actor_lines = "\n".join(f"- {p['evidence']} _({'fuente' if es else 'source'}: `00_raw/`)_" for p in personas)
    elif s2_answers:
        actor_lines = s2_answers
    else:
        actor_lines = _pending("GAP-USERS", language)
    blocks["2"] = actor_lines

    # --- Section 3: Lente de Producto: Proceso y Journey ---
    s3_answers = _gap_answer_block(gap_answers, "3", language)
    if asis:
        asis_line = (f"- Situación actual (as-is): {_cite(asis, language)}" if es
                     else f"- Current state (as-is): {_cite(asis, language)}")
    else:
        asis_line = ("- Situación actual (as-is): no descrita en el input; se rastrea en `GAP-PRODUCT-ASIS-TOBE`."
                     if es else
                     "- Current state (as-is): not described in client input; tracked by `GAP-PRODUCT-ASIS-TOBE`.")
    if functionals:
        tobe_line = (("- Proceso objetivo (to-be):\n" if es else "- Target process (to-be):\n")
                     + "\n".join(f"  - {f['statement']} _({'fuente' if es else 'source'}: `00_raw/`)_" for f in functionals[:3]))
    elif s3_answers:
        tobe_line = s3_answers
    else:
        tobe_line = ("- Proceso objetivo (to-be): se rastrea en `GAP-PRODUCT-ASIS-TOBE`." if es
                     else "- Target process (to-be): tracked by `GAP-PRODUCT-ASIS-TOBE`.")
    scope_in = (f"- In scope: {_cite(in_scope, language)}" if in_scope
                else ("- In scope: se rastrea en `GAP-SCOPE`." if es else "- In scope: tracked by `GAP-SCOPE`."))
    scope_out = (f"- Out of scope: {_cite(out_scope, language)}" if out_scope
                 else ("- Out of scope: se rastrea en `GAP-SCOPE`." if es else "- Out of scope: tracked by `GAP-SCOPE`."))
    blocks["3"] = f"{asis_line}\n{tobe_line}\n{scope_in}\n{scope_out}"

    # --- Sections 4-6: populated only from confirmed gap answers; else PENDING ---
    blocks["4"] = _gap_answer_block(gap_answers, "4", language) or (project_id and _assumption_block(project_id, "4", language)) or _pending("GAP-DESIGN-FLOW", language)
    blocks["5"] = _gap_answer_block(gap_answers, "5", language) or (project_id and _assumption_block(project_id, "5", language)) or _pending("GAP-TECH-DATA-SOURCE", language)
    blocks["6"] = _gap_answer_block(gap_answers, "6", language) or (project_id and _assumption_block(project_id, "6", language)) or _pending("GAP-GOVERNANCE-CONSTRAINTS", language)
    return blocks


def render_project_brief(
    project_id: str,
    req_text: str,
    gaps_text: str,
    seeds_text: str,
    decisions_text: str,
    lens_review_text: str,
    raw_text: str = "",
    gap_answers: dict[str, dict[str, str]] | None = None,
    language: str = "en",
    assumptions_text: str = "",
) -> str:
    open_gaps = summarize_open_gaps(gaps_text)
    seeds = summarize_table_artifact(seeds_text, "Seed ID", max_rows=10)
    decisions = summarize_table_artifact(decisions_text, "Decision ID", max_rows=8)
    coverage = summarize_table_artifact(lens_review_text, "Lens", max_rows=6)
    sec = compile_brief_sections(raw_text, gap_answers or {}, req_text, language, project_id=project_id)
    assumptions = summarize_table_artifact(assumptions_text, "Assumption ID", max_rows=8)
    return f"""# Project Brief - {project_id}

This brief is the mature discovery output. It reflects iterated requirement evidence and is the source handoff for PRD, specs, backlog, acceptance criteria, and tests.

Depth principle: the brief should be complete enough to guide domain work without becoming the domain deliverable itself. Design, Technology, and Quality may deepen the analysis later in dedicated context packs.

## 1. Identidad y Valor

{sec['1']}

## 2. Lente de Negocio: Actores y Necesidades

{sec['2']}

## 3. Lente de Producto: Proceso y Journey

{sec['3']}

## 4. Lente de Diseno: Flujos y Resiliencia UX

{sec['4']}

Sweet spot: identify affected journeys, screens, decisions, states, and UX constraints; detailed prototypes and final interaction specs belong in the design context pack.

## 5. Lente Tecnico: Datos, Conectividad y Arquitectura

{sec['5']}

Data and contract depth: include key entities, critical fields, and contract direction only when needed; exhaustive dictionaries, schemas, and sequence diagrams belong in the technology context pack.

## 6. Gobernanza y Restricciones

{sec['6']}

Auditability and traceability expectations: all downstream artifacts must cite this brief and raw evidence.

## 7. Decisiones, Seeds e Inferencias

### Seeds Confirmadas o Pendientes

{seeds}

### Decisiones

{decisions}

### Supuestos Gobernados

{assumptions}

### Cobertura Multi-Lente

{coverage}

### Inferencias Controladas

- Any inference must name the source signal and the risk if wrong.
- Inferences cannot close critical or high gaps without client/domain confirmation.

## 8. Radar de Incertidumbres: GAPs

{open_gaps}

## 9. Preparacion para PRD, Specs y Backlog

- PRD can expand this brief only from confirmed seeds, decisions, context folders, and traceable source material.
- Specs must preserve system boundaries, data ownership, UX states, NFRs, and acceptance strategy.
- Backlog must be dev-ready, testable, vertically sliced, and linked to requirement, brief, PRD, acceptance criteria, tests, and changes.
- Backlog slicing must not split below the value boundary. A small story must remain meaningful, testable, and useful by itself.
- Cross-cutting enablers are implementation work, frontend/backend/architecture, that must be built in advance to support confirmed functionality across stories, epics, FRs, or implementation surfaces.
- A valid enabler names the capability boundary it supports, why it must be built earlier, which risk/dependency it reduces, and what objective evidence proves completion.
- Generic setup, environment availability, broad infrastructure hardening, or statements such as "make an internal tool accessible" are operational preconditions or external tasks unless tied to confirmed project functionality and implementation evidence.

### Backlog Readiness Signals

| Signal | Expected Evidence | If Missing |
| --- | --- | --- |
| First value slice | The smallest observable increment that validates user/business value. | Open `GAP-BACKLOG-SLICING-READINESS`. |
| Slice boundaries | Paths, variants, rule deferral, and the point where smaller splits stop producing value. | Open `GAP-BACKLOG-SLICING-READINESS`. |
| Cross-cutting enablers | Frontend/backend/architecture work from SAD, as-is/to-be architecture, design prototypes, or specs that must be built in advance to support confirmed functionality. | Open `GAP-BACKLOG-ENABLERS`. |
| Preconditions vs backlog | Operational setup that must exist but should not become a loose backlog item. | Keep as dependency/precondition, not a user story. |

## 10. PRD Coverage Readiness

| PRD Section | Required Discovery Signal | Evidence Source | If Missing |
| --- | --- | --- | --- |
| Personas | Primary/secondary personas, goals, pains, proficiency, usage frequency, impacted teams. | `01_discovery/identity_seeds.md`, `00_raw/01_business_context/` | Open `GAP-PRD-PERSONA-DETAIL`. |
| Functional Requirements | Source-backed FRs, priority, and acceptance criteria per FR. | `02_requirements/requirements.md`, `01_discovery/lens_review.md`, quality context | Open `GAP-PRD-FR-AC`. |
| NFRs and KPIs | Security, privacy, reliability, auditability, compatibility, targets, measurement method, timeframe. | `00_raw/04_quality_context/`, governance notes, decisions | Open `GAP-PRD-NFR-KPI`. |
| JTBD Traceability | Core, secondary, emotional/social jobs mapped to FRs. | `01_discovery/discovery_log.md`, `identity_seeds.md` | Keep traceability gap visible. |
| Execution Plan | Dependencies, owners, MVP, nice-to-haves, roadmap, rollout constraints. | `00_raw/01_business_context/`, `07_changes/03_domain_updates/` | Open `GAP-PRD-DEPENDENCIES-ROADMAP`. |
| Governance | Mandatory constraints, glossary, pending inputs, decisions, assumptions, audit trail. | `01_discovery/decisions.md`, `gaps.md`, context folders | Open `GAP-PRD-GLOSSARY-GOVERNANCE`. |

PRD generation must retrieve focused context for each row instead of rereading the full workspace. Any section that lacks enough evidence should be explicit as `[PENDING INPUT]`, not invented.

## 11. Domain Context Pack Requests

| Domain | Minimum Brief Signal | Expected Deepening Outside This Brief |
| --- | --- | --- |
| Design | Affected users, journeys, screens, states, copy constraints, and visual evidence references. | User flows, prototypes, accessibility notes, interaction specs, and visual QA criteria. |
| Technology | Systems, endpoint/event inventory, create/modify/reuse decision, ownership, source of truth, constraints, and risks. | Architecture diagrams, sequence diagrams, contracts, schemas, data dictionaries, deployment concerns, and NFR implementation detail. |
| Frontend | Affected surfaces, roles, states, validations, copy, analytics, and compatibility constraints. | Component mapping, API binding detail, state management, error handling implementation, and UI test plan. |
| Backend | Capabilities, integrations, rules, persistence/source-of-truth needs, security, observability, and failure behavior. | Service design, database/schema changes, API contracts, orchestration detail, and integration test strategy. |
| Quality | Acceptance strategy, critical paths, edge cases, risk areas, test data needs, and trace expectations. | Test cases, automation approach, regression suite, coverage map, and evidence requirements. |
"""


def primary_requirement(req_text: str) -> str:
    for line in req_text.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and not stripped.startswith("- Source:") and not stripped.startswith("- Status:"):
            return stripped
    return "TBD from source requirement."


def summarize_open_gaps(gaps_text: str) -> str:
    rows = []
    for line in gaps_text.splitlines():
        parsed_rows = parse_table_rows(line, strip_code_ticks=False)
        cells = parsed_rows[0] if parsed_rows else []
        if not cells or not cells[0].startswith("GAP-"):
            continue
        if len(cells) >= 6 and cells[3].upper() in {"OPEN", "PARTIALLY_CLOSED", "ANSWERED"}:
            rows.append(f"- `{cells[0]}` ({cells[1]}, {cells[2]}): {cells[5]}")
    return "\n".join(rows) if rows else "- No open blocking gaps detected at maturity evaluation time."


def summarize_table_artifact(text: str, first_header: str, max_rows: int) -> str:
    rows = []
    capture = False
    for line in text.splitlines():
        if line.startswith("|") and first_header in line:
            capture = True
            rows.append(line)
            continue
        if capture and line.startswith("| ---"):
            rows.append(line)
            continue
        if capture and line.startswith("|"):
            rows.append(line)
            if len(rows) >= max_rows + 2:
                break
        elif capture and rows:
            break
    return "\n".join(rows) if rows else "- No structured evidence found yet."


def render_report(project_id: str, readiness: str, blocking_gaps: list[str], project_brief: Path | None) -> str:
    gaps = ", ".join(f"`{gap}`" for gap in blocking_gaps) or "None"
    brief_line = f"- Project brief: `{project_brief.as_posix()}`" if project_brief else "- Project brief: not generated while maturity is blocked."
    return f"""# Requirement Maturity Report - {project_id}

- Readiness: `{readiness}`
- Blocking gaps: {gaps}
{brief_line}

## Domain Readiness

| Domain | Status |
| --- | --- |
| product | {'READY' if readiness != 'BLOCKED' else 'BLOCKED'} |
| functional | {'READY' if readiness != 'BLOCKED' else 'BLOCKED'} |
| quality | {'READY' if readiness != 'BLOCKED' else 'BLOCKED'} |

## Verdict

{'The requirement can move into specs and backlog generation.' if readiness != 'BLOCKED' else 'Resolve blocking gaps before generating specs or backlog.'}
"""
