from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Any

from .discovery import (
    AnnotationError,
    count_gaps,
    parse_gap_rows,
    readiness_stage_for_counts,
    render_gaps,
    validate_agent_gaps,
)
from .memory import ContextBroker, reindex_workspace
from .sources import mark_source_processed
from .traceability import add_edge, add_node, load_graph
from .workspace import read_json, update_state, workspace_path


DECISION_RISKS = {"low", "med", "medium", "high"}
REVERSIBILITY_VALUES = {"easy", "moderate", "hard-to-reverse", "irreversible"}


def apply_self_review(project_id: str, source: Path) -> dict[str, object]:
    base = workspace_path(project_id)
    if not base.exists():
        raise RuntimeError(f"Workspace not found: {project_id}")
    if not specs_sources_exist(base):
        raise RuntimeError("Cannot self-review before /specs creates PRD/spec artifacts.")

    data = load_self_review_source(source)
    grounding_text = self_review_grounding_text(base)
    gaps = validate_agent_gaps(data, grounding_text, origin="self-review")
    decisions = validate_self_review_decisions(data, grounding_text)

    gaps_path = base / "01_discovery" / "gaps.md"
    if not gaps_path.exists():
        raise RuntimeError("Cannot self-review before /ingest creates 01_discovery/gaps.md.")
    existing = parse_gap_rows(gaps_path.read_text(encoding="utf-8"))
    real_existing = [gap for gap in existing if gap.get("id") != "NONE"]
    existing_ids = {gap["id"] for gap in real_existing}
    req_id = real_existing[0].get("parent", "REQ-001").strip("`") if real_existing else "REQ-001"

    merged_new: list[dict[str, str]] = []
    skipped: list[str] = []
    for gap in gaps:
        if gap["id"] in existing_ids:
            skipped.append(gap["id"])
            continue
        merged_new.append(gap)
        existing_ids.add(gap["id"])

    language = project_language(project_id)
    merged = real_existing + merged_new
    gaps_path.write_text(render_gaps(project_id, merged, req_id, language), encoding="utf-8")

    review_dir = base / "03_specs" / "self_review"
    review_dir.mkdir(parents=True, exist_ok=True)
    stored_source = unique_path(review_dir / f"{source.stem}.json")
    shutil.copyfile(source, stored_source)
    report_path = review_dir / "self_review_report.md"
    register_path = review_dir / "decision_register.md"
    report_path.write_text(render_self_review_report(project_id, source.stem, merged_new, skipped, decisions), encoding="utf-8")
    register_path.write_text(render_decision_register(project_id, decisions), encoding="utf-8")

    graph_nodes = load_graph(project_id).get("nodes", [])
    review_id = add_node(
        project_id,
        "DEC",
        "self_review",
        report_path,
        f"Skeptical self-review: {source.stem}",
        status="pending",
        domain="product",
    )
    for node in graph_nodes:
        if node.get("type") in {"prd", "spec", "spec_unit"}:
            add_edge(project_id, node["id"], review_id, "reviewed_by")
        if node.get("type") == "gap_report":
            add_edge(project_id, review_id, node["id"], "raises")

    decision_ids: list[str] = []
    for decision in decisions:
        decision_id = add_node(
            project_id,
            "DEC",
            "hard_to_reverse_decision",
            register_path,
            decision["title"],
            status="pending_review",
            domain=decision["lens"],
        )
        decision_ids.append(decision_id)
        add_edge(project_id, review_id, decision_id, "records_decision")

    broker = ContextBroker(project_id)
    broker.index_artifact(review_id, "self_review", report_path, report_path.read_text(encoding="utf-8"), trace_ids=[review_id])
    broker.index_artifact("SELF-REVIEW-DECISIONS", "decision_register", register_path, register_path.read_text(encoding="utf-8"), trace_ids=[review_id, *decision_ids])
    reindex_workspace(project_id)
    mark_source_processed(project_id, source, "self_review_applied", review_id)
    mark_source_processed(project_id, report_path, "self_review_report", review_id)
    mark_source_processed(project_id, register_path, "self_review_decision_register", review_id)

    counts = count_gaps(merged)
    counts["self_review_origin"] = sum(1 for gap in merged if gap.get("origin") == "self-review")
    update_state(
        project_id,
        phase="self_reviewed",
        health="DIRTY" if merged_new else read_json(base / "state.json", {}).get("health", "CLEAN"),
        gap_counts=counts,
        readiness_stage=readiness_stage_for_counts(counts),
        last_self_review_id=review_id,
    )

    return {
        "project_id": project_id,
        "self_review_id": review_id,
        "path": str(gaps_path.as_posix()),
        "self_review_report": str(report_path.as_posix()),
        "decision_register": str(register_path.as_posix()),
        "merged": [gap["id"] for gap in merged_new],
        "skipped_duplicates": skipped,
        "decisions": decision_ids,
        "gap_counts": counts,
    }


def load_self_review_source(source: Path) -> dict[str, Any]:
    try:
        data = json.loads(source.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise AnnotationError(f"Invalid JSON in self-review source: {exc}") from exc
    if not isinstance(data, dict):
        raise AnnotationError("Self-review source must be a JSON object.")
    return data


def validate_self_review_decisions(data: dict[str, Any], grounding_text: str) -> list[dict[str, str]]:
    raw = data.get("decisions", [])
    if raw is None:
        raw = []
    if not isinstance(raw, list):
        raise AnnotationError("self-review decisions must be a list.")
    decisions: list[dict[str, str]] = []
    for item in raw:
        if not isinstance(item, dict):
            raise AnnotationError("Each self-review decision must be an object.")
        decision_id = str(item.get("id", "")).strip().upper()
        if not re.match(r"^DEC-[A-Z0-9-]+$", decision_id):
            raise AnnotationError(f"{decision_id or '<missing>'}: decision id must start with DEC-.")
        title = str(item.get("title", "")).strip() or decision_id
        decision = str(item.get("decision", "")).strip()
        if not decision:
            raise AnnotationError(f"{decision_id}: decision text is required.")
        lens = str(item.get("lens", "product")).strip().lower() or "product"
        risk = str(item.get("risk", "")).strip().lower()
        if risk not in DECISION_RISKS:
            raise AnnotationError(f"{decision_id}: risk must be one of {', '.join(sorted(DECISION_RISKS))}.")
        reversibility = str(item.get("reversibility", "")).strip().lower()
        if reversibility not in REVERSIBILITY_VALUES:
            raise AnnotationError(
                f"{decision_id}: reversibility must be one of {', '.join(sorted(REVERSIBILITY_VALUES))}."
            )
        evidence = str(item.get("evidence", "")).strip()
        if not evidence:
            raise AnnotationError(f"{decision_id}: evidence is required.")
        if evidence not in grounding_text:
            raise AnnotationError(f"{decision_id}: evidence quote is not found verbatim in PRD/spec evidence.")
        consequence = str(item.get("consequence", "")).strip()
        decisions.append(
            {
                "id": decision_id,
                "title": title,
                "lens": lens,
                "risk": "med" if risk == "medium" else risk,
                "reversibility": reversibility,
                "decision": decision,
                "evidence": evidence,
                "consequence": consequence,
            }
        )
    return decisions


def specs_sources_exist(base: Path) -> bool:
    return (base / "03_specs" / "prd.md").exists() or (base / "03_specs" / "specs.md").exists()


def self_review_grounding_text(base: Path) -> str:
    paths: list[Path] = []
    for relative in (
        "02_requirements/project-brief.md",
        "03_specs/prd.md",
        "03_specs/specs.md",
    ):
        path = base / relative
        if path.exists():
            paths.append(path)
    units = base / "03_specs" / "units"
    if units.exists():
        paths.extend(sorted(units.glob("*.md")))
    context = base / "08_context_packs"
    if context.exists():
        paths.extend(sorted(context.glob("**/*.md")))
    chunks = []
    for path in paths:
        try:
            chunks.append(path.read_text(encoding="utf-8"))
        except OSError:
            continue
    return "\n\n".join(chunks)


def render_self_review_report(
    project_id: str,
    label: str,
    merged: list[dict[str, str]],
    skipped: list[str],
    decisions: list[dict[str, str]],
) -> str:
    gap_rows = "\n".join(
        f"| `{gap['id']}` | {gap['lens']} | {gap['severity']} | {gap['question']} | {gap.get('evidence_mention', '')} |"
        for gap in merged
    ) or "| N/A | N/A | N/A | No new self-review gaps merged. | N/A |"
    decision_rows = "\n".join(
        f"| `{item['id']}` | {item['risk']} | {item['reversibility']} | {item['decision']} | {item['evidence']} |"
        for item in decisions
    ) or "| N/A | N/A | N/A | No hard-to-reverse decisions registered. | N/A |"
    skipped_block = ", ".join(f"`{gap_id}`" for gap_id in skipped) or "None."
    return f"""# Skeptical Self-Review - {project_id}

Source: `{label}`. Origin: `self-review`.

This report records adversarial review findings over generated PRD/spec artifacts.
The runtime accepted only findings and decisions with verbatim local citations.
It does not rewrite PRD/specs automatically.

## Self-Review Gaps

| Gap ID | Lens | Severity | Question | Evidence Cited |
| --- | --- | --- | --- | --- |
{gap_rows}

Skipped duplicate gaps: {skipped_block}

## Hard-To-Reverse Decisions

| Decision ID | Risk | Reversibility | Decision | Evidence Cited |
| --- | --- | --- | --- | --- |
{decision_rows}
"""


def render_decision_register(project_id: str, decisions: list[dict[str, str]]) -> str:
    blocks = []
    for item in decisions:
        blocks.append(
            f"""## {item['id']} - {item['title']}

- Lens: `{item['lens']}`
- Risk: `{item['risk']}`
- Reversibility: `{item['reversibility']}`
- Status: `pending_review`
- Evidence: {item['evidence']}

Decision:
{item['decision']}

Consequence:
{item['consequence'] or 'TBD'}
"""
        )
    body = "\n".join(blocks) or "_No hard-to-reverse decisions registered._\n"
    return f"""# Hard-To-Reverse Decision Register - {project_id}

This register is generated by `/self-review`. It records decisions that deserve
BA/Product review before downstream agents treat them as stable execution facts.

{body}
"""


def project_language(project_id: str) -> str:
    state = read_json(workspace_path(project_id) / "state.json", {})
    language = str(state.get("project_language") or "en")
    return language if language in {"es", "en"} else "en"


def unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    stem, suffix = path.stem, path.suffix
    for index in range(2, 1000):
        candidate = path.with_name(f"{stem}-{index}{suffix}")
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"Cannot create unique path for {path}")
