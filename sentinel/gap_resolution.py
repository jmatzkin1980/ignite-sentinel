from __future__ import annotations

import re
import shutil
from pathlib import Path

from .discovery import brief_section_for_gap, count_gaps, parse_gap_rows, prd_section_for_gap, readiness_stage_for_counts, render_gaps
from .ears import classify_ears
from .gaps import DECISION_KIND, NON_GOAL_KIND, parse_gap_responses
from .knowledge.metabolism import metabolize_knowledge
from .memory import ContextBroker, reindex_workspace
from .sources import mark_source_processed
from .core.graph import add_edge, add_node, load_graph, save_graph
from .core.io import append_text
from .workspace import read_json, state_path, update_state, utc_now, workspace_path

CONFIRMED_STATUSES = {"confirmado", "confirmed", "no aplica", "not applicable", "n/a", "na"}
# IMP-185: the out-of-scope/not-applicable subset of confirmed closures. A gap
# closed with one of these is a governed Non-Goal (scope exclusion), not a
# positive answer.
NOT_APPLICABLE_STATUSES = {"no aplica", "not applicable", "n/a", "na"}
PENDING_STATUSES = {"pendiente", "pending", "en revision", "en revisión", "to confirm", "tbd"}
VAGUE_ANSWERS = {"tbd", "n/a", "na", "?", "no se", "no sé", "no sabemos", "depende", "to be defined", "pendiente", "lo vemos", "veremos"}
DOMAIN_SOURCE_TOKENS = {
    "architecture", "arquitectura", "backend", "delivery", "design", "diseño",
    "engineering", "frontend", "platform", "quality", "qa", "security",
    "seguridad", "technology", "tecnologia", "tecnología", "tech",
}
INFERENCE_SOURCE_TOKENS = {"agent", "analysis", "analisis", "análisis", "inference", "inferencia", "sentinel"}
EARS_ELIGIBLE_GAP_IDS = {"GAP-ACCEPTANCE", "GAP-BUSINESS-RULES", "GAP-PRD-FR-AC"}
EARS_ELIGIBLE_NOTE = "EARS-eligible, not normalized: confirmed prose answer needs BA-approved EARS rewrite"


def is_substantive_answer(answer: str) -> bool:
    """An answer is substantive when it carries usable content, not a deferral."""
    normalized = re.sub(r"\s+", " ", answer.strip().lower()).strip(".")
    if not normalized or normalized in VAGUE_ANSWERS:
        return False
    return len(normalized) >= 15


def is_ears_eligible_gap(gap_id: str) -> bool:
    return gap_id in EARS_ELIGIBLE_GAP_IDS


def resolve_gaps(project_id: str, source: Path) -> dict[str, object]:
    base = workspace_path(project_id)
    if not base.exists():
        raise RuntimeError(f"Workspace not found: {project_id}")
    gaps_path = base / "01_discovery" / "gaps.md"
    if not gaps_path.exists():
        raise RuntimeError("Cannot resolve gaps before /ingest creates 01_discovery/gaps.md.")

    target_dir = base / "07_changes" / "00_client_responses"
    target_dir.mkdir(parents=True, exist_ok=True)
    target = unique_target(target_dir / f"{source.stem}.md")
    shutil.copyfile(source, target)
    text = source.read_text(encoding="utf-8")
    responses = parse_gap_responses(text)
    existing = parse_gap_rows(gaps_path.read_text(encoding="utf-8"))
    req_id = existing[0].get("parent", "REQ-001").strip("`") if existing else "REQ-001"

    change_id = add_node(project_id, "CHG", "change", target, source.stem, status="pending", domain="product")
    resolution_results = apply_gap_responses(existing, responses)
    annotate_resolution_source_types(resolution_results, source)
    language = project_language(project_id)
    gaps_path.write_text(render_gaps(project_id, resolution_results["gaps"], req_id, language), encoding="utf-8")

    report_path = unique_target(target_dir / f"{source.stem}_gap_resolution_report.md")
    report_path.write_text(render_resolution_report(project_id, change_id, resolution_results), encoding="utf-8")
    report_id = add_node(project_id, "DEC", "gap_resolution_report", report_path, "Gap resolution report", status="active")
    add_edge(project_id, change_id, report_id, "produces")

    gap_report_ids = [node["id"] for node in load_graph(project_id).get("nodes", []) if node.get("type") == "gap_report"]
    for gap_report_id in gap_report_ids:
        add_edge(project_id, change_id, gap_report_id, "resolves")

    seed_ids = materialize_resolution_seeds(project_id, resolution_results["closed"], change_id)
    decision_ids = materialize_resolution_decisions(project_id, resolution_results["closed"], change_id)
    for node_id in seed_ids + decision_ids:
        add_edge(project_id, change_id, node_id, "confirms")

    # IMP-026: confirmed answers already written in EARS syntax are normalized
    # into requirements.md as testable statements. Prose answers stay as prose.
    ears_ids = materialize_ears_requirements(project_id, resolution_results["closed"], change_id)
    for node_id in ears_ids:
        add_edge(project_id, change_id, node_id, "normalizes")

    update_gap_report_node_status(project_id, resolution_results["counts"])

    broker = ContextBroker(project_id)
    metabolism = metabolize_knowledge(
        project_id,
        change_id,
        source_text=text,
        validated_gap_ids={item["id"] for item in resolution_results["closed"]},
        broker=broker,
    )
    report_path.write_text(render_resolution_report(project_id, change_id, resolution_results, metabolism), encoding="utf-8")
    broker.index_artifact(change_id, "change", target, text, trace_ids=[change_id])
    broker.index_artifact(report_id, "gap_resolution_report", report_path, report_path.read_text(encoding="utf-8"), trace_ids=[change_id, report_id])
    reindex_workspace(project_id)
    mark_source_processed(project_id, source, "gap_resolved", change_id)
    mark_source_processed(project_id, target, "gap_response_copy", change_id)
    mark_source_processed(project_id, report_path, "gap_resolution_report", report_id)

    update_state(
        project_id,
        phase="gaps_resolved",
        health="DIRTY" if resolution_results["counts"].get("blocking_open", 0) else "CLEAN",
        last_gap_resolution_id=report_id,
        last_change_id=change_id,
        gap_counts=resolution_results["counts"],
        readiness_stage=readiness_stage_for_counts(resolution_results["counts"]),
    )
    append_gap_resolution_log(project_id, change_id, report_id, resolution_results)
    return {
        "change_id": change_id,
        "gap_resolution_report_id": report_id,
        "path": str(report_path.as_posix()),
        "closed": [item["id"] for item in resolution_results["closed"]],
        "answered": [item["id"] for item in resolution_results["answered"]],
        "partially_closed": [item["id"] for item in resolution_results["partially_closed"]],
        "open": [item["id"] for item in resolution_results["open"]],
        "gap_counts": resolution_results["counts"],
        "knowledge_metabolism": metabolism,
    }


def apply_gap_responses(gaps: list[dict[str, str]], responses: dict[str, dict[str, str]]) -> dict[str, object]:
    closed: list[dict[str, str]] = []
    answered: list[dict[str, str]] = []
    partially_closed: list[dict[str, str]] = []
    open_gaps: list[dict[str, str]] = []
    updated: list[dict[str, str]] = []
    for gap in gaps:
        gap = dict(gap)
        response = responses.get(gap["id"], {})
        answer = response.get("answer", "").strip()
        decision = normalize_status(response.get("decision_status", ""))
        gap["answer"] = answer
        gap["owner"] = response.get("owner", "")
        gap["evidence"] = response.get("evidence", "")
        gap["decision_status"] = response.get("decision_status", "")
        substantive = is_substantive_answer(answer)
        if answer and decision in CONFIRMED_STATUSES and substantive:
            gap["status"] = "CLOSED"
            if is_ears_eligible_gap(gap["id"]) and not classify_ears(answer):
                gap["resolution_note"] = EARS_ELIGIBLE_NOTE
            closed.append(gap)
        elif answer and decision in CONFIRMED_STATUSES:
            # Confirmed but the answer itself is vague/deferred: do not close silently.
            gap["status"] = "PARTIALLY_CLOSED"
            gap["resolution_note"] = "confirmed-but-vague: answer lacks usable content; ask for specifics"
            partially_closed.append(gap)
        elif answer and decision in PENDING_STATUSES and substantive:
            # Clear answer awaiting confirmation: visible as ANSWERED, still blocking if severe.
            gap["status"] = "ANSWERED"
            gap["resolution_note"] = "awaiting-confirmation: substantive answer, decision still pending"
            answered.append(gap)
        elif answer:
            gap["status"] = "PARTIALLY_CLOSED"
            gap["resolution_note"] = "ambiguous: answer present but no recognizable decision status"
            partially_closed.append(gap)
        else:
            gap["status"] = gap.get("status", "OPEN")
            open_gaps.append(gap)
        updated.append(gap)
    return {
        "gaps": updated,
        "closed": closed,
        "answered": answered,
        "partially_closed": partially_closed,
        "open": [gap for gap in updated if gap.get("status") == "OPEN"],
        "counts": count_gaps(updated),
    }


def annotate_resolution_source_types(result: dict[str, object], source: Path) -> None:
    for key in ("closed", "answered", "partially_closed"):
        for gap in result.get(key, []):  # type: ignore[union-attr]
            if isinstance(gap, dict):
                gap["resolution_source_type"] = classify_resolution_source(
                    gap.get("owner", ""),
                    gap.get("evidence", ""),
                    source,
                )


def classify_resolution_source(owner: str, evidence: str = "", source: Path | None = None) -> str:
    text = f"{owner} {evidence} {source.as_posix() if source else ''}".lower()
    if any(token in text for token in INFERENCE_SOURCE_TOKENS):
        return "inference"
    if any(token in text for token in DOMAIN_SOURCE_TOKENS):
        return "domain"
    return "client"


def closed_resolution_source_counts(result: dict[str, object]) -> dict[str, int]:
    counts = {"client": 0, "domain": 0, "inference": 0}
    for gap in result.get("closed", []):  # type: ignore[union-attr]
        if not isinstance(gap, dict):
            continue
        source_type = str(gap.get("resolution_source_type", "client"))
        if source_type not in counts:
            source_type = "client"
        counts[source_type] += 1
    return counts


def normalize_status(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def materialize_resolution_seeds(project_id: str, closed: list[dict[str, str]], change_id: str) -> list[str]:
    if not closed:
        return []
    path = workspace_path(project_id) / "01_discovery" / "identity_seeds.md"
    if not path.exists():
        path.write_text("# Identity Seeds\n\n", encoding="utf-8")
    rows = [
        "\n## Gap Resolution Seeds\n\n",
        "| Seed ID | Gap ID | Status | Statement | Source | Brief Section | PRD Section |\n",
        "| --- | --- | --- | --- | --- | --- | --- |\n",
    ]
    for index, gap in enumerate(closed, start=1):
        brief_section = brief_section_for_gap(gap["id"]) or "-"
        prd_section = prd_section_for_gap(gap["id"]) or "-"
        rows.append(
            f"| AUTO-SEED-{change_id}-{index:03d} | `{gap['id']}` | CONFIRMED | {gap['answer']} | `{change_id}` | {brief_section} | {prd_section} |\n"
        )
    append_text(path, "".join(rows))
    seed_ids = []
    for gap in closed:
        seed_id = add_node(project_id, "SEED", "identity_seed", path, f"Confirmed answer for {gap['id']}", status="confirmed", domain=gap.get("lens", "product"))
        seed_ids.append(seed_id)
    return seed_ids


def materialize_resolution_decisions(project_id: str, closed: list[dict[str, str]], change_id: str) -> list[str]:
    decisions = [gap for gap in closed if normalize_status(gap.get("decision_status", "")) in CONFIRMED_STATUSES]
    if not decisions:
        return []
    path = workspace_path(project_id) / "01_discovery" / "decisions.md"
    if not path.exists():
        path.write_text("# Decision Log\n\n", encoding="utf-8")
    rows = [
        "\n## Gap Resolution Decisions\n\n",
        "| Decision ID | Gap ID | Status | Decision | Source | Kind |\n",
        "| --- | --- | --- | --- | --- | --- |\n",
    ]
    for index, gap in enumerate(decisions, start=1):
        kind = NON_GOAL_KIND if normalize_status(gap.get("decision_status", "")) in NOT_APPLICABLE_STATUSES else DECISION_KIND
        rows.append(f"| AUTO-DEC-{change_id}-{index:03d} | `{gap['id']}` | CONFIRMED | {gap['answer']} | `{change_id}` | {kind} |\n")
    append_text(path, "".join(rows))
    decision_ids = []
    for gap in decisions:
        decision_id = add_node(project_id, "DEC", "decision", path, f"Confirmed decision for {gap['id']}", status="confirmed", domain=gap.get("lens", "product"))
        decision_ids.append(decision_id)
    return decision_ids


def _count_existing_ears(text: str) -> int:
    return len(re.findall(r"REQ-EARS-\d+", text))


def materialize_ears_requirements(project_id: str, closed: list[dict[str, str]], change_id: str) -> list[str]:
    """Normalize confirmed EARS-shaped answers into requirements.md (IMP-026).

    Only answers already written in valid EARS syntax are accumulated; prose
    answers stay as seeds/decisions. The agent proposes; the runtime validates
    structure (never invents). Returns the traceability node ids created.
    """
    candidates: list[tuple[dict[str, str], str, str]] = []
    for gap in closed:
        answer = (gap.get("answer") or "").strip()
        pattern = classify_ears(answer)
        if pattern:
            candidates.append((gap, answer, pattern))
    if not candidates:
        return []
    path = workspace_path(project_id) / "02_requirements" / "requirements.md"
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8")
    start_index = _count_existing_ears(text)
    lines: list[str] = []
    if "## Normalized Requirements (EARS)" not in text:
        lines.append("\n## Normalized Requirements (EARS)\n")
        lines.append(
            "Testable statements normalized from confirmed functional answers (IMP-026). "
            "Specs and backlog cite these by `REQ-EARS-*`; prose answers stay as seeds/decisions/gaps.\n"
        )
        lines.append("| ID | Pattern | Statement | Source |")
        lines.append("| --- | --- | --- | --- |")
    node_ids: list[str] = []
    for offset, (gap, answer, pattern) in enumerate(candidates, start=1):
        req_id = f"REQ-EARS-{start_index + offset:03d}"
        lines.append(f"| {req_id} | {pattern} | {answer} | `{gap['id']}` / `{change_id}` |")
        node_ids.append(
            add_node(
                project_id, "REQ", "ears_requirement", path,
                f"{req_id} ({pattern}) from {gap['id']}",
                status="confirmed", domain=gap.get("lens", "product"),
            )
        )
    append_text(path, "\n".join(lines) + "\n")
    return node_ids


def update_gap_report_node_status(project_id: str, counts: dict[str, int]) -> None:
    graph = load_graph(project_id)
    status = "closed" if not counts.get("open", 0) and not counts.get("partially_closed", 0) else "open"
    for node in graph.get("nodes", []):
        if node.get("type") == "gap_report":
            node["status"] = status
    save_graph(project_id, graph)


def render_resolution_report(
    project_id: str,
    change_id: str,
    result: dict[str, object],
    knowledge_metabolism: dict[str, object] | None = None,
) -> str:
    closed = result["closed"]
    answered = result.get("answered", [])
    partial = result["partially_closed"]
    open_gaps = result["open"]
    knowledge_metabolism = knowledge_metabolism or {}
    unit_rows = "\n".join(
        f"- `{unit_id}`" for unit_id in knowledge_metabolism.get("impacted_knowledge_units", [])
    ) or "- None."
    validated_rows = "\n".join(
        f"- `{item}`" for item in knowledge_metabolism.get("validated_assumptions", [])
    ) or "- None."
    stale_rows = "\n".join(
        f"- `{item}`" for item in knowledge_metabolism.get("downstream_stale_artifacts", [])
    ) or "- None."
    return f"""# Gap Resolution Report - {project_id}

- Change: `{change_id}`
- Generated at: {utc_now()}

## Closed Gaps

{render_resolution_rows(closed)}

## Answered (Awaiting Confirmation)

{render_resolution_rows(answered)}

## Partially Closed Gaps

{render_resolution_rows(partial)}

## Still Open

{render_resolution_rows(open_gaps)}

## Knowledge Ledger Metabolism

- Knowledge state: `{knowledge_metabolism.get("knowledge_state", "N/A")}`
- Development readiness: `{knowledge_metabolism.get("development_readiness", "N/A")}`

Impacted knowledge units:

{unit_rows}

Validated assumptions:

{validated_rows}

Downstream stale artifacts:

{stale_rows}
"""


def render_resolution_rows(gaps: object) -> str:
    if not gaps:
        return "- None."
    return "\n".join(
        f"- `{gap['id']}`: {gap.get('answer') or gap.get('description', '')}"
        + (f" _[{gap['resolution_note']}]_" if gap.get("resolution_note") else "")
        + (f" _(source: {gap['resolution_source_type']})_" if gap.get("resolution_source_type") else "")
        for gap in gaps
    )  # type: ignore[index]


def append_gap_resolution_log(project_id: str, change_id: str, report_id: str, result: dict[str, object]) -> Path:
    path = workspace_path(project_id) / "01_discovery" / "gap_resolution_log.md"
    if not path.exists():
        path.write_text(
            f"""# Gap Resolution Log - {project_id}

| Timestamp | Change ID | Report ID | Closed | Partial | Open | Client Closed | Domain Closed | Inference Closed |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
""",
            encoding="utf-8",
        )
    source_counts = closed_resolution_source_counts(result)
    append_text(
        path,
        f"| {utc_now()} | `{change_id}` | `{report_id}` | {len(result['closed'])} | {len(result['partially_closed'])} | {len(result['open'])} | {source_counts['client']} | {source_counts['domain']} | {source_counts['inference']} |\n",
    )
    return path


def project_language(project_id: str) -> str:
    state = read_json(state_path(project_id), {})
    return state.get("project_language", "en") if state.get("project_language") in {"es", "en"} else "en"


def unique_target(path: Path) -> Path:
    if not path.exists():
        return path
    counter = 2
    while True:
        candidate = path.with_name(f"{path.stem}-{counter}{path.suffix}")
        if not candidate.exists():
            return candidate
        counter += 1

