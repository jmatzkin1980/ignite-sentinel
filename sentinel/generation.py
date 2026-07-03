from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import re
from typing import Any

from .memory import ContextBroker, apply_pack_disclosure_budget, get_multi_domain_context
from .backlog.hooks import assert_backlog_privacy_clean
from .backlog.status import apply_lifecycle_to_stories, audit_acceptance_criteria_freezes
from .backlog.gates import evaluate_story_gates, update_story_gate_state
from .backlog.rollup import backlog_status
from .assumptions import persist_assumptions_projection
from .core.markdown import parse_table_rows
from .compilers.backlog import (
    build_agent_execution_contract,
    build_domain_context_coverage,
    render_backlog_context_summary,
    render_enabler_boundary,
    render_enabler_epic,
    render_epic,
    render_slicing_strategy_table,
    render_story,
)
from .compilers.prd import (
    compile_prd_sections,
    first_sentence_with,
    project_title,
    render_prd,
    render_prd_full,
)
from .compilers.specs import (
    build_spec_units,
    changed_frontmatter_fields,
    delta_value,
    read_spec_units,
    record_spec_unit_delta,
    render_backlog_seed_rows,
    render_spec_unit,
    render_spec_units_index,
    render_specs,
    spec_unit_delta_entry,
    spec_unit_pattern,
    spec_unit_relative_path,
    spec_unit_snapshot,
    spec_unit_statement,
    spec_unit_title,
    update_implementation_readiness_stale_units,
    write_spec_unit_delta_report,
    write_spec_units,
)
from .compilers.slicing import (
    BACKLOG_STORY_SEEDS,
    ENABLER_CANDIDATES,
    acceptance_criteria_for_enabler,
    acceptance_criteria_for_pending_story,
    acceptance_criteria_for_spec_unit_story,
    acceptance_criteria_for_story,
    build_backlog_story_specs,
    build_cross_cutting_enabler_specs,
    build_story_backlog_context,
    context_row_for_spec_unit,
    context_row_for_story,
    cross_cutting_enabler_evidence,
    domain_for_spec_unit,
    goal_for_spec_unit,
    pending_backlog_story,
    slicing_decision_for_spec_unit,
    slicing_fallback_decision,
    spec_unit_query_context,
    story_dependencies,
    story_domain,
    title_for_spec_unit_story,
    trace_ids_for_spec_unit,
)
from .maturity import evaluate, parse_gap_answers, prd_gate_warnings, prd_section_readiness
from .prd import render_prd_compositions
from .retrieval_plans import compose_plan_query, load_retrieval_plan, select_source_context
from .slice_plan import generate_slice_plan
from .core.graph import add_edge, add_node, nodes_by_type, upsert_node
from .drift import record_derived_source_fingerprint
from .workspace import load_config, read_json, state_path, update_state, workspace_path, write_json


DOMAIN_CONTEXT_FOLDERS = {
    "Product": ("00_raw/00_client_requirement", "00_raw/01_business_context", "00_raw/05_interactions", "07_changes"),
    "Technology": ("00_raw/02_technology_context",),
    "Design": ("00_raw/03_design_context",),
    "Quality": ("00_raw/04_quality_context",),
    "Delivery": ("07_changes",),
}

EARS_REQUIREMENT_ID_RE = re.compile(r"^REQ-EARS-\d{3}$")

def record_regeneration_diff(project_id: str, artifact_label: str, old_text: str, new_text: str) -> str | None:
    """Record a human-readable summary of what changed when an artifact is regenerated (IMP-011).

    Returns the trace node id of the diff record, or None on first generation / no change.
    """
    if not old_text or old_text == new_text:
        return None
    import difflib

    def headings(text: str) -> list[str]:
        return [line.strip() for line in text.splitlines() if line.startswith("#")]

    old_sections, new_sections = headings(old_text), headings(new_text)
    added_sections = [s for s in new_sections if s not in old_sections]
    removed_sections = [s for s in old_sections if s not in new_sections]
    diff = list(difflib.unified_diff(old_text.splitlines(), new_text.splitlines(), lineterm=""))
    added_lines = sum(1 for line in diff if line.startswith("+") and not line.startswith("+++"))
    removed_lines = sum(1 for line in diff if line.startswith("-") and not line.startswith("---"))

    base = workspace_path(project_id)
    out_dir = base / "07_changes" / "04_regeneration"
    out_dir.mkdir(parents=True, exist_ok=True)
    state = read_json(state_path(project_id), {})
    change_id = state.get("last_change_id") or "N/A"
    existing = sorted(out_dir.glob("*.md"))
    out_path = out_dir / f"regen-{len(existing) + 1:03d}-{artifact_label.replace('.', '-')}.md"

    def section_rows(items: list[str]) -> str:
        return "\n".join(f"- {item}" for item in items) or "- None."

    out_path.write_text(
        f"""# Regeneration Diff - {artifact_label}

- Project: `{project_id}`
- Triggering change: `{change_id}`
- Lines added: {added_lines}
- Lines removed: {removed_lines}

## Sections Added

{section_rows(added_sections)}

## Sections Removed

{section_rows(removed_sections)}

Review this artifact against the triggering change before downstream handoff. The regenerated file is the source of truth; this diff is visibility, not authority.
""",
        encoding="utf-8",
    )
    diff_id = add_node(project_id, "DEC", "regeneration_diff", out_path, f"Regeneration diff for {artifact_label}", domain="product")
    if change_id != "N/A":
        add_edge(project_id, change_id, diff_id, "triggers_regeneration")
    ContextBroker(project_id).index_artifact(
        diff_id,
        "regeneration_diff",
        out_path,
        out_path.read_text(encoding="utf-8"),
        domain="product",
        trace_ids=[diff_id] if change_id == "N/A" else [change_id, diff_id],
    )
    return diff_id


def generate_specs(project_id: str) -> dict[str, object]:
    maturity = evaluate(project_id)
    if maturity["readiness"] == "BLOCKED":
        raise RuntimeError("Cannot generate specs while requirement maturity is BLOCKED.")
    base = workspace_path(project_id)
    config = load_config(project_id)
    req_path = base / "02_requirements" / "requirements.md"
    brief_path = base / "02_requirements" / "project-brief.md"
    source_path = brief_path if brief_path.exists() else req_path
    req_text = source_path.read_text(encoding="utf-8")
    raw_dir = base / "00_raw"
    raw_parts = []
    if raw_dir.exists():
        for raw_file in sorted(raw_dir.rglob("*")):
            if raw_file.is_file() and raw_file.suffix.lower() in {".md", ".txt"}:
                raw_parts.append(raw_file.read_text(encoding="utf-8", errors="ignore"))
    evidence_text = "\n\n".join(raw_parts) or req_text
    context = get_multi_domain_context(req_text, project_id)
    generation_context = build_specs_generation_context(project_id, req_text)
    context["prd_sections"] = generation_context["sections"]
    context["ears_requirements"] = load_ears_requirements(project_id)
    seed_text = read_artifact_text(base / "01_discovery" / "identity_seeds.md")
    decision_text = read_artifact_text(base / "01_discovery" / "decisions.md")
    context["gap_answers"] = parse_gap_answers(seed_text + "\n" + decision_text)
    context["raw_text"] = evidence_text
    state = read_json(state_path(project_id), {})
    language = str(state.get("project_language", "es")).lower()
    prd_path = base / "03_specs" / "prd.md"
    specs_path = base / "03_specs" / "specs.md"
    previous_prd = prd_path.read_text(encoding="utf-8") if prd_path.exists() else ""
    previous_specs = specs_path.read_text(encoding="utf-8") if specs_path.exists() else ""
    previous_spec_units = spec_unit_snapshot(base)
    prd_text = render_prd(project_id, req_text, context, source_path.name, language, evidence_text)
    prd_path.write_text(render_prd_compositions(project_id, prd_text), encoding="utf-8")
    prd_readiness = prd_section_readiness(prd_path.read_text(encoding="utf-8"))
    specs_gate = config.get("specs_gate", {}) if isinstance(config.get("specs_gate", {}), dict) else {}
    specs_threshold = float(specs_gate.get("threshold", 0.75))
    specs_strict = bool(specs_gate.get("strict", False))
    below_specs_threshold = float(prd_readiness["coverage_score"]) < specs_threshold
    specs_warnings = prd_gate_warnings(prd_readiness, language) if below_specs_threshold else []
    if specs_strict and below_specs_threshold:
        update_state(
            project_id,
            phase="specs_below_threshold",
            readiness_stage="SPECS_BELOW_THRESHOLD",
            health="DIRTY",
            prd_section_readiness=prd_readiness,
            specs_gate={"threshold": specs_threshold, "strict": specs_strict, "below_threshold": below_specs_threshold},
            specs_gate_warnings=specs_warnings,
        )
        raise RuntimeError("Cannot complete /specs while PRD section readiness is below specs_gate threshold.")
    spec_units = write_spec_units(project_id, context, source_path.name)
    spec_unit_delta = record_spec_unit_delta(project_id, previous_spec_units)
    specs_path.write_text(render_specs(project_id, req_text, context, source_path.name, spec_units), encoding="utf-8")
    record_regeneration_diff(project_id, "prd.md", previous_prd, prd_path.read_text(encoding="utf-8"))
    record_regeneration_diff(project_id, "specs.md", previous_specs, specs_path.read_text(encoding="utf-8"))
    prd_id = add_node(project_id, "PRD", "prd", prd_path, "Human-readable PRD", domain="product")
    spec_id = add_node(project_id, "SPEC", "spec", specs_path, "AI-friendly specification", domain="product")
    parent_trace_ids: list[str] = []
    for req in nodes_by_type(project_id, "requirement"):
        add_edge(project_id, req["id"], prd_id, "elaborates")
        parent_trace_ids.append(req["id"])
    for brief in nodes_by_type(project_id, "project_brief"):
        add_edge(project_id, brief["id"], prd_id, "elaborates")
        parent_trace_ids.append(brief["id"])
    add_edge(project_id, prd_id, spec_id, "agentizes")
    trace_ids = [*parent_trace_ids, prd_id, spec_id]
    broker = ContextBroker(project_id)
    broker.index_artifact(
        prd_id, "prd", prd_path, prd_path.read_text(encoding="utf-8"), trace_ids=trace_ids
    )
    broker.index_artifact(
        spec_id, "spec", specs_path, specs_path.read_text(encoding="utf-8"), trace_ids=trace_ids
    )
    req_path_for_units = base / "02_requirements" / "requirements.md"
    for unit in spec_units:
        unit_id = str(unit["id"])
        unit_path = Path(str(unit["path"]))
        unit_node = upsert_node(
            project_id,
            unit_id,
            "spec_unit",
            unit_path,
            str(unit["title"]),
            status=str(unit["status"]),
            domain="product",
        )
        add_edge(project_id, prd_id, unit_node, "decomposes")
        add_edge(project_id, spec_id, unit_node, "indexes")
        unit_trace_ids = [*trace_ids, unit_node]
        for ears_id in unit.get("ears", []):
            if isinstance(ears_id, str) and EARS_REQUIREMENT_ID_RE.match(ears_id):
                ears_node = upsert_node(
                    project_id,
                    ears_id,
                    "ears_requirement",
                    req_path_for_units,
                    f"{ears_id} normalized EARS requirement",
                    status="confirmed",
                    domain="product",
                )
                add_edge(project_id, unit_node, ears_node, "traces_to")
                unit_trace_ids.append(ears_node)
        broker.index_artifact(
            unit_node,
            "spec_unit",
            unit_path,
            unit_path.read_text(encoding="utf-8"),
            trace_ids=unit_trace_ids,
        )
    gate_result = {"threshold": specs_threshold, "strict": specs_strict, "below_threshold": below_specs_threshold}
    update_state(
        project_id,
        phase="specs_completed",
        health="CLEAN",
        readiness_stage="READY_FOR_BACKLOG",
        prd_section_readiness=prd_readiness,
        specs_gate=gate_result,
        specs_gate_warnings=specs_warnings,
    )
    # IMP-148: snapshot the fingerprint of the sources specs was generated from,
    # so /health can later flag specs that drifted from the brief/requirements.
    record_derived_source_fingerprint(project_id, "specs")
    return {
        "prd_id": prd_id,
        "spec_id": spec_id,
        "prd_path": str(prd_path),
        "path": str(specs_path),
        "prd_section_readiness": prd_readiness,
        "warnings": specs_warnings,
        "specs_gate": gate_result,
        "spec_unit_delta": {
            "path": str(spec_unit_delta["path"].as_posix()),
            "changed": spec_unit_delta["changed"],
        } if spec_unit_delta else None,
    }


def read_artifact_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def generate_backlog(project_id: str, with_task_seeds: bool = False) -> dict[str, str]:
    maturity = evaluate(project_id)
    if maturity["readiness"] == "BLOCKED":
        raise RuntimeError("Cannot generate backlog while requirement maturity is BLOCKED.")
    specs = nodes_by_type(project_id, "spec")
    if not specs:
        generate_specs(project_id)
        specs = nodes_by_type(project_id, "spec")
    base = workspace_path(project_id)
    spec_path = base / "03_specs" / "specs.md"
    prd_path = base / "03_specs" / "prd.md"
    spec_text = spec_path.read_text(encoding="utf-8") if spec_path.exists() else ""
    prd_text = prd_path.read_text(encoding="utf-8") if prd_path.exists() else ""
    backlog_context = build_backlog_generation_context(project_id, spec_text, prd_text)
    story_specs = build_backlog_story_specs(project_id, backlog_context)
    enabler_specs = build_cross_cutting_enabler_specs(project_id, story_specs, backlog_context)
    all_story_specs = [*story_specs, *enabler_specs]
    apply_lifecycle_to_stories(project_id, all_story_specs)
    audit_acceptance_criteria_freezes(project_id, all_story_specs)
    if with_task_seeds:
        attach_task_seed_contracts(all_story_specs)
    readiness_pack = build_implementation_readiness_pack(project_id, all_story_specs, backlog_context)
    slice_plan = generate_slice_plan(project_id, all_story_specs, readiness_pack)
    backlog_context["implementation_readiness"] = {
        "path": "08_context_packs/implementation_readiness.json",
        "verdict": readiness_pack["verdict"],
    }
    backlog_context["slice_plan"] = {
        "path": "04_backlog/SLICE-PLAN.md",
        "json_path": "08_context_packs/slice_plan.json",
    }
    write_json(base / "08_context_packs" / "backlog_generation.json", backlog_context)

    epic_path = base / "04_backlog" / "EPIC-001.md"
    previous_epic = epic_path.read_text(encoding="utf-8") if epic_path.exists() else ""
    epic_path.write_text(render_epic(project_id, story_specs, backlog_context), encoding="utf-8")
    record_regeneration_diff(project_id, "EPIC-001.md", previous_epic, epic_path.read_text(encoding="utf-8"))
    epic_id = add_node(project_id, "EPIC", "epic", epic_path, "Deliver validated requirement value", domain="product")
    for spec in specs:
        add_edge(project_id, spec["id"], epic_id, "decomposes_to")

    story_ids: list[str] = []
    acceptance_ids: list[str] = []
    active_story_paths: set[Path] = set()
    for index, story_spec in enumerate(story_specs, start=1):
        story_path = base / "04_backlog" / f"US-{index:03d}.md"
        story_path.write_text(render_story(project_id, epic_id, story_spec), encoding="utf-8")
        active_story_paths.add(story_path)
        story_id = add_node(project_id, "US", "user_story", story_path, story_spec["title"], domain=story_spec["domain"])
        story_ids.append(story_id)
        add_edge(project_id, epic_id, story_id, "contains")
        for spec in specs:
            add_edge(project_id, spec["id"], story_id, "decomposes_to")
        for trace_id in story_spec.get("trace", []):
            if re.match(r"^SPEC-U-\d{3}$", str(trace_id)):
                add_edge(project_id, str(trace_id), story_id, "decomposes_to")

        ac_id = add_node(project_id, "AC", "acceptance_criteria", story_path, f"Acceptance criteria for {story_id}", domain="quality")
        acceptance_ids.append(ac_id)
        add_edge(project_id, story_id, ac_id, "validated_by")

    epic_ids = [epic_id]
    if enabler_specs:
        enabler_epic_path = base / "04_backlog" / "EPIC-002-cross-cutting-enablers.md"
        enabler_epic_path.write_text(
            render_enabler_epic(project_id, enabler_specs, story_specs, backlog_context),
            encoding="utf-8",
        )
        enabler_epic_id = add_node(
            project_id,
            "EPIC",
            "epic",
            enabler_epic_path,
            "Cross-cutting enablers for validated requirement value",
            domain="technical",
        )
        epic_ids.append(enabler_epic_id)
        for spec in specs:
            add_edge(project_id, spec["id"], enabler_epic_id, "decomposes_to")
        for index, enabler_spec in enumerate(enabler_specs, start=len(story_specs) + 1):
            story_path = base / "04_backlog" / f"US-{index:03d}.md"
            story_path.write_text(render_story(project_id, enabler_epic_id, enabler_spec), encoding="utf-8")
            active_story_paths.add(story_path)
            story_id = add_node(project_id, "US", "user_story", story_path, enabler_spec["title"], domain="technical")
            story_ids.append(story_id)
            add_edge(project_id, enabler_epic_id, story_id, "contains")
            for enabled in enabler_spec["enables"]:
                add_edge(project_id, story_id, enabled, "enables")
            for spec in specs:
                add_edge(project_id, spec["id"], story_id, "decomposes_to")
            ac_id = add_node(project_id, "AC", "acceptance_criteria", story_path, f"Acceptance criteria for {story_id}", domain="quality")
            acceptance_ids.append(ac_id)
            add_edge(project_id, story_id, ac_id, "validated_by")
        ContextBroker(project_id).index_artifact(
            enabler_epic_id,
            "epic",
            enabler_epic_path,
            enabler_epic_path.read_text(encoding="utf-8"),
            domain="technical",
            trace_ids=[enabler_epic_id, *[item["id"] for item in enabler_specs]],
        )

    for stale_story_path in (base / "04_backlog").glob("US-*.md"):
        if stale_story_path not in active_story_paths:
            stale_story_path.unlink()

    assert_backlog_privacy_clean(project_id)

    broker = ContextBroker(project_id)
    broker.index_artifact(epic_id, "epic", epic_path, epic_path.read_text(encoding="utf-8"), trace_ids=[epic_id, *story_ids])
    for story_id, ac_id, story_spec in zip(story_ids, acceptance_ids, all_story_specs):
        story_path = base / "04_backlog" / f"{story_id}.md"
        if not story_path.exists():
            numeric = int(story_id.split("-", 1)[1])
            story_path = base / "04_backlog" / f"US-{numeric:03d}.md"
        broker.index_artifact(
            story_id,
            "user_story",
            story_path,
            story_path.read_text(encoding="utf-8"),
            domain=story_spec["domain"],
            trace_ids=[epic_id, story_id, ac_id, *story_spec["trace"]],
        )
    board = backlog_status(project_id)
    update_state(
        project_id,
        phase="backlog_completed",
        health="CLEAN",
        metrics={"requirements": 1, "gaps_open": 0, "decisions_pending": 1, "user_stories": len(story_ids), "epics": len(epic_ids)},
    )
    # IMP-148: snapshot the fingerprint of the specs the backlog was derived from.
    record_derived_source_fingerprint(project_id, "backlog")
    return {
        "epic_id": epic_id,
        "story_id": story_ids[0],
        "acceptance_id": acceptance_ids[0],
        "path": str(epic_path),
        "story_count": str(len(story_ids)),
        "epic_count": str(len(epic_ids)),
        "implementation_readiness": str(base / "08_context_packs" / "implementation_readiness.json"),
        "backlog_board": board["path"],
        "slice_plan": slice_plan["path"],
        "slice_plan_json": slice_plan["json_path"],
        "task_seed_contracts": "enabled" if with_task_seeds else "disabled",
    }


def build_backlog_generation_context(
    project_id: str,
    spec_text: str,
    prd_text: str,
    retrieval_plans_dir: Path | str | None = None,
    plan_override: dict[str, Any] | None = None,
) -> dict[str, Any]:
    broker = ContextBroker(project_id)
    plan = load_retrieval_plan("backlog_generation", retrieval_plans_dir, plan_override)
    source_documents = {"specs.md": spec_text, "prd.md": prd_text}
    sections: dict[str, Any] = {}
    for section, retrieval in plan["sections"].items():
        query = str(retrieval["query"])
        domain = retrieval.get("domain")
        filters = dict(retrieval.get("filters", {}))
        source_context = select_source_context(source_documents, retrieval)
        results = broker.retrieve(
            compose_plan_query(retrieval, source_context),
            "backlog_generation",
            limit=int(retrieval["limit"]),
            domain=domain,
            artifact_type=filters.get("artifact_type"),
            status=filters.get("status"),
            language=filters.get("language"),
            sensitivity=filters.get("sensitivity"),
            section=filters.get("section"),
            max_chars=int(retrieval["budget_chars"]),
            summary_only=True,
        )
        sections[section] = {
            "query": query,
            "domain": domain or "any",
            "filters": filters,
            "limit": retrieval["limit"],
            "budget_chars": retrieval["budget_chars"],
            "summary_chars": retrieval["summary_chars"],
            "lenses": retrieval["lenses"],
            "source_sections": retrieval["source_sections"],
            "results": [
                {
                    "artifact_id": row.get("artifact_id", "N/A"),
                    "artifact_type": row.get("artifact_type", "artifact"),
                    "domain": row.get("domain", "unknown"),
                    "section_path": row.get("section_path", ""),
                    "chunk_id": row.get("chunk_id", ""),
                    "summary": row.get("summary", row.get("text", ""))[: int(retrieval["summary_chars"])],
                    "why_retrieved": row.get("why_retrieved", ""),
                    "trace_ids": row.get("trace_ids", []),
                    "source_hash": row.get("source_hash", ""),
                    "read_plan": row.get("read_plan", read_plan_for_row(row)),
                }
                for row in results
            ],
        }
    disclosure_budget = apply_pack_disclosure_budget(sections, int(plan.get("global_budget_chars", 0)))
    domain_snapshot = domain_context_snapshot(project_id)
    pack = {
        "project_id": project_id,
        "workflow": "backlog_generation",
        "retrieval_plan": {"workflow": plan["workflow"], "version": plan["version"]},
        "slicing_model": "vertical_value_slices_with_spidr_lawrence_invest",
        "domain_context_snapshot": domain_snapshot,
        "ears_requirements": load_ears_requirements(project_id),
        "sections": sections,
        "disclosure_budget": disclosure_budget,
        "domain_context_coverage": [],
        "per_story": {},
    }
    pack["domain_context_coverage"] = build_domain_context_coverage(pack)
    write_json(workspace_path(project_id) / "08_context_packs" / "backlog_generation.json", pack)
    return pack


def build_implementation_readiness_pack(
    project_id: str,
    stories: list[dict[str, Any]],
    backlog_context: dict[str, Any],
) -> dict[str, Any]:
    readiness_items: list[dict[str, Any]] = []
    for story in stories:
        item = implementation_readiness_for_story(story)
        gate_result = evaluate_story_gates(project_id, story, item)
        item["dor"] = gate_result["dor"]
        item["dod"] = gate_result["dod"]
        item["backlog_gate"] = {"threshold": gate_result["threshold"], "strict": gate_result["strict"]}
        story["dor"] = gate_result["dor"]
        story["dod"] = gate_result["dod"]
        update_story_gate_state(project_id, str(story["id"]), gate_result)
        readiness_items.append(item)
    blocker_count = sum(1 for item in readiness_items if item["status"] != "ready")
    verdict = "READY" if blocker_count == 0 else "PARTIAL"
    pending_by_domain: dict[str, int] = {}
    for item in readiness_items:
        for blocker in item["pending"]:
            if blocker.startswith("Pending domain context: "):
                domain = blocker.split(": ", 1)[1]
                pending_by_domain[domain] = pending_by_domain.get(domain, 0) + 1
    summary = {
        "stories_total": len(readiness_items),
        "stories_ready": len(readiness_items) - blocker_count,
        "stories_needing_context": blocker_count,
        "avg_readiness_score": round(
            sum(item["readiness_score"] for item in readiness_items) / len(readiness_items), 3
        ) if readiness_items else 0.0,
        "pending_context_by_domain": pending_by_domain,
    }
    pack = {
        "project_id": project_id,
        "workflow": "implementation_readiness",
        "verdict": verdict,
        "summary": summary,
        "generated_from": {
            "backlog_context_pack": "08_context_packs/backlog_generation.json",
            "domain_context_snapshot": backlog_context.get("domain_context_snapshot", domain_context_snapshot(project_id)),
        },
        "retrieval_contract": {
            "rule": "Execution agents should use these queries before planning, implementing, or testing. Workspace files remain source of truth; memory is only retrieval evidence.",
            "freshness_rule": "If the current domain context snapshot differs from this pack, rerun /reindex and /backlog before implementation handoff.",
        },
        "stories": readiness_items,
    }
    state = read_json(state_path(project_id), {})
    pack["stale_spec_units"] = state.get("stale_spec_units", [])
    path = workspace_path(project_id) / "08_context_packs" / "implementation_readiness.json"
    write_json(path, pack)
    persist_assumptions_projection(project_id)
    ContextBroker(project_id).index_artifact(
        "IMPL-READINESS",
        "implementation_readiness",
        path,
        path.read_text(encoding="utf-8"),
        domain="delivery",
        trace_ids=[story["id"] for story in stories] or ["IMPL-READINESS"],
    )
    return pack


def read_plan_for_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_path": row.get("source_path", row.get("file_path", "")),
        "section_path": row.get("section_path", ""),
        "line_start": int(row.get("line_start", 0) or 0),
        "line_end": int(row.get("line_end", 0) or 0),
    }


def implementation_readiness_for_story(story: dict[str, Any]) -> dict[str, Any]:
    execution = story.get("execution_contract", {})
    coverage = story.get("domain_coverage", [])
    pending_domains = [
        row.get("domain", "Unknown")
        for row in coverage
        if row.get("status") == "Pending" and row.get("domain") in required_domains_for_story(story)
    ]
    pending_contract = pending_execution_fields(execution)
    blockers = [f"Pending domain context: {domain}" for domain in pending_domains]
    blockers.extend(f"Pending execution field: {field}" for field in pending_contract)
    status = "ready" if not blockers else "needs-context"
    score_basis = len(required_domains_for_story(story)) + 3  # domains + execution contract fields
    readiness_score = round(max(0.0, 1.0 - len(blockers) / score_basis), 3)
    item = {
        "story_id": story["id"],
        "title": story["title"],
        "type": story["type"],
        "domain": story.get("domain", "functional"),
        "status": status,
        "story_status": story.get("status", "Draft"),
        "owner": story.get("owner", ""),
        "readiness_score": readiness_score,
        "readiness": execution.get("readiness", "Needs Domain Context"),
        "required_domains": required_domains_for_story(story),
        "pending": blockers,
        "dependencies": story.get("dependencies", []),
        "enables": story.get("enables", []),
        "parallelization": execution.get("parallelization", ""),
        "execution_contract": execution,
        "retrieval_plan": execution.get("retrieval_plan", []),
        "validation": execution.get("validation", {}),
        "blast_radius": execution.get("blast_radius", []),
        "trace": story.get("trace", []),
        "source_unit": story.get("source_unit", "[PENDING INPUT]"),
        "slicing": story.get("slicing", "[PENDING INPUT]"),
        "slicing_rationale": story.get("slicing_rationale", "[PENDING INPUT]"),
        "context_pack": story.get("context_pack", "08_context_packs/backlog_generation.json"),
        "context_pack_section": story.get("context_pack_section", ""),
    }
    if story.get("task_seed_contract"):
        item["task_seed_contract"] = story["task_seed_contract"]
    return item


TASK_SEED_BOUNDARY_NOTE = (
    "Task seeds are optional implementation intentions for downstream agents. "
    "Ignite does not execute, estimate, assign, schedule or manage these tasks; "
    "downstream planning may expand, reorder or discard them while preserving story scope and traceability."
)


def attach_task_seed_contracts(stories: list[dict[str, Any]]) -> None:
    for story in stories:
        story["task_seed_contract"] = task_seed_contract_for_story(story)


def task_seed_contract_for_story(story: dict[str, Any]) -> dict[str, Any]:
    ac_refs = [str(item.get("id", "")).strip() for item in story.get("acceptance", []) if item.get("id")]
    fail_to_pass = [
        str(item.get("id", "")).strip()
        for item in story.get("acceptance", [])
        if item.get("id") and item.get("classification") == "fail-to-pass"
    ]
    pass_to_pass = [
        str(item.get("id", "")).strip()
        for item in story.get("acceptance", [])
        if item.get("id") and item.get("classification") == "pass-to-pass"
    ]
    evidence = [
        str(item.get("id", "")).strip()
        for item in story.get("acceptance", [])
        if item.get("id") and item.get("classification") == "evidence"
    ]
    surfaces = task_seed_surfaces(story)
    story_id = str(story.get("id", "US-000"))
    seeds = [
        task_seed(
            story_id,
            1,
            "data-contract-intent",
            "Clarify the data, external dependency, or state contract needed before implementing the acceptance path.",
            fail_to_pass or ac_refs,
            surfaces,
            parallelizable=False,
            depends_on=[],
        ),
        task_seed(
            story_id,
            2,
            "service-behavior-intent",
            "Plan the smallest domain/service behavior that satisfies the fail-to-pass acceptance path without expanding scope.",
            fail_to_pass or ac_refs,
            surfaces,
            parallelizable=False,
            depends_on=[f"TSEED-{story_id}-01"],
        ),
        task_seed(
            story_id,
            3,
            "interface-or-workflow-intent",
            "Plan the smallest user-observable interface or workflow change needed for the story boundary.",
            pass_to_pass or fail_to_pass or ac_refs,
            surfaces,
            parallelizable=True,
            depends_on=[f"TSEED-{story_id}-01"],
        ),
        task_seed(
            story_id,
            4,
            "evidence-intent",
            "Prepare downstream test, regression, or acceptance evidence before proposing the story as Done.",
            evidence or ac_refs,
            surfaces,
            parallelizable=True,
            depends_on=[f"TSEED-{story_id}-02", f"TSEED-{story_id}-03"],
        ),
    ]
    return {
        "emitted": True,
        "scope_boundary": TASK_SEED_BOUNDARY_NOTE,
        "source": "Derived from acceptance criteria and Agent Execution Contract critical surfaces.",
        "seeds": seeds,
    }


def task_seed(
    story_id: str,
    order: int,
    kind: str,
    intention: str,
    ac_refs: list[str],
    surfaces: list[str],
    parallelizable: bool,
    depends_on: list[str],
) -> dict[str, Any]:
    return {
        "id": f"TSEED-{story_id}-{order:02d}",
        "order": order,
        "kind": kind,
        "intention": intention,
        "acceptance_criteria": ac_refs,
        "critical_surfaces": surfaces,
        "parallelizable": parallelizable,
        "depends_on": depends_on,
        "not_tasking": "No execution, estimates, assignment, scheduling, or project-task ownership is implied.",
    }


def task_seed_surfaces(story: dict[str, Any]) -> list[str]:
    signal = story.get("execution_contract", {}).get("critical_surfaces", {})
    if not isinstance(signal, dict):
        return ["[PENDING DOMAIN CONTEXT] Critical surfaces are not confirmed."]
    status = str(signal.get("status", "Pending"))
    summary = str(signal.get("summary", "")).strip()
    source = str(signal.get("source", "")).strip()
    if status == "Confirmed" and summary:
        return [safe_cell(f"{source}: {summary}" if source else summary, 220)]
    return ["[PENDING DOMAIN CONTEXT] Critical surfaces are not confirmed."]


def required_domains_for_story(story: dict[str, Any]) -> list[str]:
    required = ["Product", "Quality"]
    if story.get("domain") in {"technical"} or story.get("type") == "cross_cutting_enabler":
        required.append("Technology")
    if story.get("domain") == "design":
        required.append("Design")
    return required


def pending_execution_fields(execution: dict[str, Any]) -> list[str]:
    pending: list[str] = []
    for field in ("commands", "critical_surfaces", "engineering_practices"):
        signal = execution.get(field, {})
        if isinstance(signal, dict) and signal.get("status") == "Pending":
            pending.append(field)
    design_signal = execution.get("design_match", {})
    if isinstance(design_signal, dict) and design_signal.get("status") == "Pending":
        pending.append("design_match")
    return pending


def domain_context_snapshot(project_id: str) -> dict[str, Any]:
    base = workspace_path(project_id)
    domains: dict[str, Any] = {}
    all_hash = sha256()
    for domain, folders in DOMAIN_CONTEXT_FOLDERS.items():
        files: list[dict[str, str]] = []
        domain_hash = sha256()
        for folder in folders:
            path = base / folder
            if not path.exists():
                continue
            for item in sorted(path.rglob("*")):
                if "04_regeneration" in item.parts:
                    continue
                if item.is_file() and item.suffix.lower() in {".md", ".txt", ".json", ".yaml", ".yml"}:
                    text = item.read_text(encoding="utf-8")
                    digest = sha256(text.encode("utf-8")).hexdigest()
                    relative = item.relative_to(base).as_posix()
                    files.append({"path": relative, "hash": digest})
                    domain_hash.update(relative.encode("utf-8"))
                    domain_hash.update(digest.encode("utf-8"))
        aggregate = domain_hash.hexdigest() if files else "empty"
        domains[domain] = {"aggregate_hash": aggregate, "file_count": len(files), "files": files}
        all_hash.update(domain.encode("utf-8"))
        all_hash.update(aggregate.encode("utf-8"))
    return {"aggregate_hash": all_hash.hexdigest(), "domains": domains}


def load_ears_requirements(project_id: str) -> list[dict[str, str]]:
    req_path = workspace_path(project_id) / "02_requirements" / "requirements.md"
    if not req_path.exists():
        return []
    return parse_ears_requirements(req_path.read_text(encoding="utf-8"))


def parse_ears_requirements(requirements_text: str) -> list[dict[str, str]]:
    in_section = False
    rows: list[dict[str, str]] = []
    for raw_line in requirements_text.splitlines():
        line = raw_line.strip()
        if line.startswith("## "):
            in_section = line == "## Normalized Requirements (EARS)"
            continue
        if not in_section or not line.startswith("|"):
            continue
        cells = parse_table_rows(line)[0]
        if len(cells) < 4 or cells[0] in {"ID", "---"} or not EARS_REQUIREMENT_ID_RE.match(cells[0]):
            continue
        rows.append(
            {
                "id": cells[0],
                "pattern": cells[1],
                "statement": cells[2],
                "source": cells[3],
            }
        )
    return rows


def ears_trace_ids(context: dict[str, object]) -> list[str]:
    rows = context.get("ears_requirements", []) if isinstance(context, dict) else []
    if not isinstance(rows, list):
        return []
    ids: list[str] = []
    for row in rows:
        if isinstance(row, dict):
            req_id = str(row.get("id", ""))
            if EARS_REQUIREMENT_ID_RE.match(req_id):
                ids.append(req_id)
    return ids


def build_specs_generation_context(
    project_id: str,
    req_text: str,
    retrieval_plans_dir: Path | str | None = None,
    plan_override: dict[str, Any] | None = None,
) -> dict[str, Any]:
    broker = ContextBroker(project_id)
    plan = load_retrieval_plan("specs_generation", retrieval_plans_dir, plan_override)
    source_documents = {"requirements-context": req_text}
    sections: dict[str, Any] = {}
    for section, retrieval in plan["sections"].items():
        query = str(retrieval["query"])
        filters = dict(retrieval.get("filters", {}))
        source_context = select_source_context(source_documents, retrieval)
        results = broker.retrieve(
            compose_plan_query(retrieval, source_context),
            "specs_generation",
            limit=int(retrieval["limit"]),
            domain=retrieval.get("domain"),
            artifact_type=filters.get("artifact_type"),
            status=filters.get("status"),
            language=filters.get("language"),
            sensitivity=filters.get("sensitivity"),
            section=filters.get("section"),
            max_chars=int(retrieval["budget_chars"]),
            summary_only=True,
        )
        sections[section] = {
            "query": query,
            "domain": retrieval.get("domain") or "any",
            "filters": filters,
            "limit": retrieval["limit"],
            "budget_chars": retrieval["budget_chars"],
            "summary_chars": retrieval["summary_chars"],
            "lenses": retrieval["lenses"],
            "source_sections": retrieval["source_sections"],
            "results": [
                {
                    "artifact_id": row.get("artifact_id", "N/A"),
                    "artifact_type": row.get("artifact_type", "artifact"),
                    "domain": row.get("domain", "unknown"),
                    "section_path": row.get("section_path", ""),
                    "chunk_id": row.get("chunk_id", ""),
                    "summary": row.get("summary", row.get("text", ""))[: int(retrieval["summary_chars"])],
                    "why_retrieved": row.get("why_retrieved", ""),
                    "trace_ids": row.get("trace_ids", []),
                    "source_hash": row.get("source_hash", ""),
                    "read_plan": row.get("read_plan", read_plan_for_row(row)),
                }
                for row in results
            ],
        }
    disclosure_budget = apply_pack_disclosure_budget(sections, int(plan.get("global_budget_chars", 0)))
    coverage_map: dict[str, str] = {}
    for section, payload in sections.items():
        count = len(payload.get("results", []))
        payload["result_count"] = count
        payload["evidence_strength"] = "strong" if count >= 3 else ("weak" if count else "none")
        coverage_map[section] = payload["evidence_strength"]
    covered = sum(1 for strength in coverage_map.values() if strength != "none")
    pack = {
        "project_id": project_id,
        "workflow": "specs_generation",
        "retrieval_plan": {"workflow": plan["workflow"], "version": plan["version"]},
        "coverage_map": coverage_map,
        "coverage_score": round(covered / len(coverage_map), 3) if coverage_map else 0.0,
        "sections_total": len(coverage_map),
        "sections_with_evidence": covered,
        "disclosure_budget": disclosure_budget,
        "sections": sections,
    }
    write_json(workspace_path(project_id) / "08_context_packs" / "specs_generation.json", pack)
    return pack


def render_context_summary(context: dict[str, object]) -> str:
    domains = context.get("domains", {}) if isinstance(context, dict) else {}
    rows: list[str] = []
    for domain, results in domains.items():
        if not results:
            rows.append(f"| {domain} | No focused context retrieved. | N/A |")
            continue
        top = results[0]
        rows.append(
            f"| {domain} | {safe_cell(top.get('summary', 'Context retrieved'), 160)} | `{top.get('artifact_id', 'N/A')}` |"
        )
    return "| Domain | Retrieved Signal | Artifact |\n| --- | --- | --- |\n" + "\n".join(rows)


def render_prd_section_context(context: dict[str, object]) -> str:
    sections = context.get("prd_sections", {}) if isinstance(context, dict) else {}
    if not isinstance(sections, dict) or not sections:
        return render_context_summary(context)
    rows: list[str] = []
    for section, payload in sections.items():
        if not isinstance(payload, dict):
            continue
        results = payload.get("results", [])
        if not results:
            rows.append(f"| {section} | No focused context retrieved. | N/A | N/A |")
            continue
        top = results[0]
        if not isinstance(top, dict):
            continue
        trace_ids = top.get("trace_ids", [])
        trace = ", ".join(trace_ids) if isinstance(trace_ids, list) else str(trace_ids)
        rows.append(
            f"| {section} | {safe_cell(top.get('summary', 'Context retrieved'), 180)} | `{top.get('artifact_id', 'N/A')}` | {safe_cell(trace or 'N/A', 80)} |"
        )
    return "| PRD / Specs Need | Retrieved Signal | Artifact | Trace |\n| --- | --- | --- | --- |\n" + "\n".join(rows)


def bounded_text(text: str, limit: int) -> str:
    cleaned = text.strip()
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[:limit].rstrip() + "\n\n[TRUNCATED IN GENERATED ARTIFACT - retrieve focused source context if needed]"


def safe_cell(value: Any, limit: int) -> str:
    text = str(value).replace("\n", " ").replace("|", "/").strip()
    return text[:limit]
