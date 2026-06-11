from __future__ import annotations

import re
import shutil
from pathlib import Path

from .discovery import brief_section_for_gap, count_gaps, parse_gap_rows, readiness_stage_for_counts, render_gaps
from .memory import ContextBroker, reindex_workspace
from .sources import mark_source_processed
from .traceability import add_edge, add_node, load_graph, save_graph
from .workspace import read_json, state_path, update_state, utc_now, workspace_path

CONFIRMED_STATUSES = {"confirmado", "confirmed", "no aplica", "not applicable", "n/a", "na"}
PENDING_STATUSES = {"pendiente", "pending", "en revision", "en revisión", "to confirm", "tbd"}
VAGUE_ANSWERS = {"tbd", "n/a", "na", "?", "no se", "no sé", "no sabemos", "depende", "to be defined", "pendiente", "lo vemos", "veremos"}


def is_substantive_answer(answer: str) -> bool:
    """An answer is substantive when it carries usable content, not a deferral."""
    normalized = re.sub(r"\s+", " ", answer.strip().lower()).strip(".")
    if not normalized or normalized in VAGUE_ANSWERS:
        return False
    return len(normalized) >= 15


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

    update_gap_report_node_status(project_id, resolution_results["counts"])

    broker = ContextBroker(project_id)
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
    }


def parse_gap_responses(text: str) -> dict[str, dict[str, str]]:
    pattern = re.compile(r"^###\s+(GAP-[A-Z0-9-]+).*?(?=^###\s+GAP-[A-Z0-9-]+|\Z)", re.M | re.S)
    responses: dict[str, dict[str, str]] = {}
    for match in pattern.finditer(text):
        gap_id = match.group(1).strip()
        block = match.group(0)
        responses[gap_id] = {
            "answer": extract_field(block, ("Respuesta", "Answer")),
            "owner": extract_field(block, ("Owner / fuente", "Owner / source")),
            "evidence": extract_field(block, ("Evidencia o referencia", "Evidence or reference")),
            "decision_status": extract_field(block, ("Estado de decisión", "Decision status")),
        }
    return responses


def extract_field(block: str, labels: tuple[str, ...]) -> str:
    for label in labels:
        pattern = re.compile(rf"^\s*-\s*{re.escape(label)}\s*:\s*(.*)$", re.I | re.M)
        match = pattern.search(block)
        if match:
            return match.group(1).strip()
    return ""


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


def normalize_status(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def materialize_resolution_seeds(project_id: str, closed: list[dict[str, str]], change_id: str) -> list[str]:
    if not closed:
        return []
    path = workspace_path(project_id) / "01_discovery" / "identity_seeds.md"
    if not path.exists():
        path.write_text("# Identity Seeds\n\n", encoding="utf-8")
    with path.open("a", encoding="utf-8") as handle:
        # IMP-024: tag each confirmed answer with the brief section it feeds, so
        # the brief compiler can route it (synergy with the IMP-022 gap→section map).
        handle.write("\n## Gap Resolution Seeds\n\n")
        handle.write("| Seed ID | Gap ID | Status | Statement | Source | Brief Section |\n")
        handle.write("| --- | --- | --- | --- | --- | --- |\n")
        for index, gap in enumerate(closed, start=1):
            section = brief_section_for_gap(gap["id"]) or "-"
            handle.write(f"| AUTO-SEED-{change_id}-{index:03d} | `{gap['id']}` | CONFIRMED | {gap['answer']} | `{change_id}` | {section} |\n")
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
    with path.open("a", encoding="utf-8") as handle:
        handle.write("\n## Gap Resolution Decisions\n\n")
        handle.write("| Decision ID | Gap ID | Status | Decision | Source |\n")
        handle.write("| --- | --- | --- | --- | --- |\n")
        for index, gap in enumerate(decisions, start=1):
            handle.write(f"| AUTO-DEC-{change_id}-{index:03d} | `{gap['id']}` | CONFIRMED | {gap['answer']} | `{change_id}` |\n")
    decision_ids = []
    for gap in decisions:
        decision_id = add_node(project_id, "DEC", "decision", path, f"Confirmed decision for {gap['id']}", status="confirmed", domain=gap.get("lens", "product"))
        decision_ids.append(decision_id)
    return decision_ids


def update_gap_report_node_status(project_id: str, counts: dict[str, int]) -> None:
    graph = load_graph(project_id)
    status = "closed" if not counts.get("open", 0) and not counts.get("partially_closed", 0) else "open"
    for node in graph.get("nodes", []):
        if node.get("type") == "gap_report":
            node["status"] = status
    save_graph(project_id, graph)


def render_resolution_report(project_id: str, change_id: str, result: dict[str, object]) -> str:
    closed = result["closed"]
    answered = result.get("answered", [])
    partial = result["partially_closed"]
    open_gaps = result["open"]
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
"""


def render_resolution_rows(gaps: object) -> str:
    if not gaps:
        return "- None."
    return "\n".join(
        f"- `{gap['id']}`: {gap.get('answer') or gap.get('description', '')}"
        + (f" _[{gap['resolution_note']}]_" if gap.get("resolution_note") else "")
        for gap in gaps
    )  # type: ignore[index]


def append_gap_resolution_log(project_id: str, change_id: str, report_id: str, result: dict[str, object]) -> Path:
    path = workspace_path(project_id) / "01_discovery" / "gap_resolution_log.md"
    if not path.exists():
        path.write_text(
            f"""# Gap Resolution Log - {project_id}

| Timestamp | Change ID | Report ID | Closed | Partial | Open |
| --- | --- | --- | ---: | ---: | ---: |
""",
            encoding="utf-8",
        )
    with path.open("a", encoding="utf-8") as handle:
        handle.write(
            f"| {utc_now()} | `{change_id}` | `{report_id}` | {len(result['closed'])} | {len(result['partially_closed'])} | {len(result['open'])} |\n"
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

