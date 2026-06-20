"""Specs compiler and Spec Unit helpers."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from ..core.graph import add_edge, add_node
from ..core.markdown import frontmatter_list, parse_frontmatter, parse_table_rows
from ..memory import ContextBroker
from ..workspace import read_json, state_path, update_state, workspace_path, write_json
from .prd import render_ears_requirements_table, render_prd_section_context


EARS_REQUIREMENT_ID_RE = re.compile(r"^REQ-EARS-\d{3}$")


def spec_unit_snapshot(base: Path) -> dict[str, dict[str, Any]]:
    units_dir = base / "03_specs" / "units"
    if not units_dir.exists():
        return {}
    snapshot: dict[str, dict[str, Any]] = {}
    for path in sorted(units_dir.glob("SPEC-U-*.md")):
        text = path.read_text(encoding="utf-8")
        unit_id = path.stem
        snapshot[unit_id] = {
            "id": unit_id,
            "path": path,
            "text": text,
            "frontmatter": parse_frontmatter(text),
        }
    return snapshot


def read_spec_units(project_id: str) -> list[dict[str, Any]]:
    base = workspace_path(project_id)
    units_dir = base / "03_specs" / "units"
    units: list[dict[str, Any]] = []
    for path in sorted(units_dir.glob("SPEC-U-*.md")) if units_dir.exists() else []:
        text = path.read_text(encoding="utf-8")
        frontmatter = parse_frontmatter(text)
        unit_id = str(frontmatter.get("id", path.stem)).strip()
        if not re.match(r"^SPEC-U-\d{3}$", unit_id):
            continue
        status = str(frontmatter.get("status", "")).strip().lower()
        if status and status not in {"evidence-backed", "confirmed", "ready"}:
            continue
        units.append(
            {
                "id": unit_id,
                "title": spec_unit_title(text, unit_id),
                "status": status or "evidence-backed",
                "path": path,
                "relative_path": path.relative_to(base).as_posix(),
                "trace_ids": [str(item) for item in frontmatter.get("trace_ids", []) if str(item).strip()],
                "ears": [str(item) for item in frontmatter.get("ears", []) if str(item).strip()],
                "sources": [str(item) for item in frontmatter.get("sources", []) if str(item).strip()],
                "statement": spec_unit_statement(text),
                "pattern": spec_unit_pattern(text),
            }
        )
    return units


def spec_unit_title(text: str, fallback: str) -> str:
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip() or fallback
    return fallback


def spec_unit_statement(text: str) -> str:
    in_requirement = False
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if line.startswith("## "):
            in_requirement = line == "## Normalized Requirement"
            continue
        if not in_requirement or not line.startswith("|"):
            continue
        cells = parse_table_rows(line)[0]
        if len(cells) < 2 or cells[0] in {"EARS ID", "---"}:
            continue
        return cells[1]
    return ""


def spec_unit_pattern(text: str) -> str:
    for line in text.splitlines():
        if line.startswith("- Pattern:"):
            return line.split(":", 1)[1].strip().strip("`")
    return ""


def record_spec_unit_delta(
    project_id: str,
    previous_units: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    if not previous_units:
        return None
    base = workspace_path(project_id)
    current_snapshot = spec_unit_snapshot(base)
    all_ids = sorted(set(previous_units) | set(current_snapshot))
    entries: list[dict[str, Any]] = []
    for unit_id in all_ids:
        previous = previous_units.get(unit_id)
        current = current_snapshot.get(unit_id)
        if previous and not current:
            status = "REMOVED"
        elif current and not previous:
            status = "ADDED"
        elif previous and current and previous["text"] != current["text"]:
            status = "MODIFIED"
        else:
            status = "UNCHANGED"
        entries.append(spec_unit_delta_entry(unit_id, status, previous, current))
    changed = [entry for entry in entries if entry["status"] != "UNCHANGED"]
    path, delta_id = write_spec_unit_delta_report(project_id, entries, changed)
    update_implementation_readiness_stale_units(project_id, changed, path)
    update_state(
        project_id,
        stale_spec_units=changed,
        last_spec_unit_delta_id=delta_id,
        last_spec_unit_delta_path=str(path.as_posix()),
    )
    return {"path": path, "delta_id": delta_id, "entries": entries, "changed": changed}


def spec_unit_delta_entry(
    unit_id: str,
    status: str,
    previous: dict[str, Any] | None,
    current: dict[str, Any] | None,
) -> dict[str, Any]:
    previous_fm = previous.get("frontmatter", {}) if previous else {}
    current_fm = current.get("frontmatter", {}) if current else {}
    frontmatter_changes = changed_frontmatter_fields(previous_fm, current_fm)
    return {
        "unit_id": unit_id,
        "status": status,
        "path": spec_unit_relative_path(current or previous),
        "frontmatter_changes": frontmatter_changes,
        "previous_ears": previous_fm.get("ears", []) if previous_fm else [],
        "current_ears": current_fm.get("ears", []) if current_fm else [],
        "previous_sources": previous_fm.get("sources", []) if previous_fm else [],
        "current_sources": current_fm.get("sources", []) if current_fm else [],
    }


def changed_frontmatter_fields(previous: dict[str, Any], current: dict[str, Any]) -> list[str]:
    keys = sorted(set(previous) | set(current))
    return [key for key in keys if previous.get(key) != current.get(key)]


def spec_unit_relative_path(unit: dict[str, Any] | None) -> str:
    if not unit:
        return ""
    path = Path(str(unit.get("path", ""))).as_posix()
    if "03_specs/" in path:
        return path[path.index("03_specs/") :]
    return path


def write_spec_unit_delta_report(
    project_id: str,
    entries: list[dict[str, Any]],
    changed: list[dict[str, Any]],
) -> tuple[Path, str]:
    base = workspace_path(project_id)
    out_dir = base / "07_changes" / "04_regeneration"
    out_dir.mkdir(parents=True, exist_ok=True)
    state = read_json(state_path(project_id), {})
    change_id = state.get("last_change_id") or "N/A"
    existing = sorted(out_dir.glob("*.md"))
    path = out_dir / f"regen-{len(existing) + 1:03d}-spec-units-delta.md"

    def rows(items: list[dict[str, Any]]) -> str:
        if not items:
            return "| N/A | N/A | N/A | N/A | N/A | N/A |"
        rendered = []
        for item in items:
            rendered.append(
                "| {unit} | {status} | {frontmatter} | {ears} | {sources} | `{path}` |".format(
                    unit=f"`{item['unit_id']}`",
                    status=item["status"],
                    frontmatter=", ".join(f"`{field}`" for field in item["frontmatter_changes"]) or "none",
                    ears=delta_value(item["previous_ears"], item["current_ears"]),
                    sources=delta_value(item["previous_sources"], item["current_sources"]),
                    path=item["path"],
                )
            )
        return "\n".join(rendered)

    path.write_text(
        f"""# Spec Unit Delta - {project_id}

- Project: `{project_id}`
- Triggering change: `{change_id}`
- Changed units: {len(changed)}
- Total units compared: {len(entries)}

## Changed Units

| Unit | Status | Frontmatter Changes | EARS Delta | Source Pointer Delta | Path |
| --- | --- | --- | --- | --- | --- |
{rows(changed)}

## Full Unit Status

| Unit | Status | Frontmatter Changes | EARS Delta | Source Pointer Delta | Path |
| --- | --- | --- | --- | --- | --- |
{rows(entries)}

Use this report to decide which backlog stories or implementation readiness entries need review after regenerating specs. Workspace artifacts remain the source of truth.
""",
        encoding="utf-8",
    )
    delta_id = add_node(project_id, "DEC", "regeneration_diff", path, "Spec unit regeneration delta", domain="product")
    if change_id != "N/A":
        add_edge(project_id, change_id, delta_id, "triggers_regeneration")
    ContextBroker(project_id).index_artifact(
        delta_id,
        "regeneration_diff",
        path,
        path.read_text(encoding="utf-8"),
        domain="product",
        trace_ids=[delta_id] if change_id == "N/A" else [change_id, delta_id],
    )
    return path, delta_id


def delta_value(previous: Any, current: Any) -> str:
    previous_values = previous if isinstance(previous, list) else ([] if previous in (None, "") else [str(previous)])
    current_values = current if isinstance(current, list) else ([] if current in (None, "") else [str(current)])
    if previous_values == current_values:
        return ", ".join(f"`{item}`" for item in current_values) or "none"
    old = ", ".join(f"`{item}`" for item in previous_values) or "none"
    new = ", ".join(f"`{item}`" for item in current_values) or "none"
    return f"{old} -> {new}"


def update_implementation_readiness_stale_units(project_id: str, changed: list[dict[str, Any]], delta_path: Path) -> None:
    path = workspace_path(project_id) / "08_context_packs" / "implementation_readiness.json"
    if not path.exists():
        return
    pack = read_json(path, {})
    if not isinstance(pack, dict):
        return
    pack["stale_spec_units"] = [
        {
            "unit_id": item["unit_id"],
            "status": item["status"],
            "path": item["path"],
            "delta_report": delta_path.relative_to(workspace_path(project_id)).as_posix(),
        }
        for item in changed
    ]
    write_json(path, pack)


def write_spec_units(project_id: str, context: dict[str, object], source_name: str) -> list[dict[str, object]]:
    base = workspace_path(project_id)
    units_dir = base / "03_specs" / "units"
    units_dir.mkdir(parents=True, exist_ok=True)
    units = build_spec_units(context, source_name)
    active_paths: set[Path] = set()
    for unit in units:
        path = units_dir / f"{unit['id']}.md"
        unit["path"] = path
        path.write_text(render_spec_unit(project_id, unit), encoding="utf-8")
        active_paths.add(path)
    for stale in units_dir.glob("SPEC-U-*.md"):
        if stale not in active_paths:
            stale.unlink()
    return units


def build_spec_units(context: dict[str, object], source_name: str) -> list[dict[str, object]]:
    rows = context.get("ears_requirements", []) if isinstance(context, dict) else []
    if not isinstance(rows, list):
        return []
    units: list[dict[str, object]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        ears_id = str(row.get("id", "")).strip()
        statement = str(row.get("statement", "")).strip()
        if not EARS_REQUIREMENT_ID_RE.match(ears_id) or not statement:
            continue
        unit_id = f"SPEC-U-{len(units) + 1:03d}"
        units.append(
            {
                "id": unit_id,
                "title": f"{unit_id} - {ears_id}",
                "status": "evidence-backed",
                "trace_ids": ["REQ-001", "PRD-001", "SPEC-001", ears_id],
                "ears": [ears_id],
                "sources": [
                    "02_requirements/requirements.md#normalized-requirements-ears",
                    f"02_requirements/{source_name}",
                    "03_specs/prd.md#4-functional-requirements",
                ],
                "pattern": str(row.get("pattern", "")).strip(),
                "statement": statement,
                "source": str(row.get("source", "")).strip(),
            }
        )
    return units


def render_spec_unit(project_id: str, unit: dict[str, object]) -> str:
    trace_ids = [str(item) for item in unit.get("trace_ids", []) if str(item).strip()]
    ears_ids = [str(item) for item in unit.get("ears", []) if str(item).strip()]
    sources = [str(item) for item in unit.get("sources", []) if str(item).strip()]
    source_rows = "\n".join(f"| `{source}` | Pointer |" for source in sources)
    ears_rows = "\n".join(f"| `{ears_id}` | {safe_cell(str(unit.get('statement', '')), 280)} |" for ears_id in ears_ids)
    return f"""---
id: {unit['id']}
status: {unit['status']}
trace_ids:
{frontmatter_list(trace_ids)}
ears:
{frontmatter_list(ears_ids)}
sources:
{frontmatter_list(sources)}
---

# {unit['title']}

## Evidence Basis

| Source | Anchor |
| --- | --- |
{source_rows or "| `[PENDING INPUT]` | No source anchor was available. |"}

## Normalized Requirement

| EARS ID | Statement |
| --- | --- |
{ears_rows or "| `[PENDING INPUT]` | No confirmed EARS row was available. |"}

## Execution Pointer

- Project: `{project_id}`
- Pattern: `{unit.get('pattern', 'unknown')}`
- Source answer: {unit.get('source', '`02_requirements/requirements.md`')}
- Use this unit as the bounded execution context for backlog slicing. Retrieve domain context only for the surfaces, risks, and validation evidence needed by this statement.
- Missing implementation detail remains a `GAP-*` or `[PENDING DOMAIN CONTEXT]`; do not infer contracts, screens, data ownership, or rollout from this unit alone.
"""


def render_spec_units_index(spec_units: list[dict[str, object]] | None) -> str:
    if not spec_units:
        return "`[PENDING INPUT]` - no evidence-backed spec units exist yet. Confirm EARS rows or source-backed functional statements before treating specs as decomposed."
    rows = []
    for unit in spec_units:
        ears = ", ".join(f"`{item}`" for item in unit.get("ears", [])) or "`N/A`"
        path = Path(str(unit.get("path", ""))).as_posix()
        if "03_specs/" in path:
            path = path[path.index("03_specs/") :]
        rows.append(f"| `{unit['id']}` | {safe_cell(str(unit.get('statement', '')), 180)} | {ears} | `{path}` |")
    return "| Unit ID | Execution Slice | EARS Trace | File |\n| --- | --- | --- | --- |\n" + "\n".join(rows)


def render_backlog_seed_rows(spec_units: list[dict[str, object]] | None) -> str:
    if not spec_units:
        return "| `[PENDING INPUT]` | No evidence-backed unit exists yet. Resolve functional/acceptance evidence before deriving backlog items. | Follow-up | `GAP-PRD-FR-AC` |"
    rows = []
    for unit in spec_units:
        ears = ", ".join(f"`{item}`" for item in unit.get("ears", [])) or "`N/A`"
        rows.append(
            f"| `{unit['id']}` | Slice the behavior described by this unit into the smallest meaningful value story. | User Story Candidate | {ears} |"
        )
    return "\n".join(rows)


def render_specs(project_id: str, req_text: str, context: dict[str, object], source_name: str, spec_units: list[dict[str, object]] | None = None) -> str:
    ears_block = render_ears_requirements_table(context)
    ears_ids = ears_trace_ids(context)
    ears_trace = ", ".join(f"`{item}`" for item in ears_ids) or "`N/A`"
    unit_index = render_spec_units_index(spec_units)
    return f"""# Specs - {project_id}

## Spec Contract

- Purpose: provide an agent-friendly execution contract for backlog generation.
- Human PRD: `03_specs/prd.md`
- Mature source: `02_requirements/{source_name}`
- Trace anchors: `REQ-001`, `PRD-001`, `SPEC-001`
- Context pack: `08_context_packs/specs_generation.json`
- Rule: agents must retrieve focused context before expanding backlog slices. Do not reread the whole workspace unless the retrieval pack is insufficient.
- Unit rule: execution detail lives in `03_specs/units/SPEC-U-NNN.md`; this file is the index and handoff contract.

## Requirement Snapshot

The mature requirement remains authoritative in `02_requirements/{source_name}`. This spec keeps only the execution signals agents need before progressive disclosure.

{bounded_text(req_text, 2200)}

## Backlog-Relevant Contract

| Contract Item | Rule |
| --- | --- |
| Source hierarchy | Workspace files win over memory. PRD/specs summarize, they do not replace source evidence. |
| Traceability | Every epic/story/AC must cite `REQ-001`, `PRD-001`, `SPEC-001`, and at least one FR/JTBD/rule where applicable. When confirmed EARS rows exist, cite the relevant `REQ-EARS-*` IDs too. |
| Missing evidence | Keep `[PENDING INPUT]` or create/follow a `GAP-*`; do not invent. |
| Story size | `Small` means the smallest independently meaningful, testable, useful slice. Do not split into micro-stories that no longer produce value or reduce a named risk. |
| Cross-cutting enablers | Enablers may live in a separate epic only when they are implementation work built in advance to support confirmed functionality across stories, epics, FRs, or implementation surfaces. They must reduce concrete risk/dependency and have objective acceptance evidence. |
| Preconditions | Generic access, environment availability, broad infrastructure readiness, or vague setup are preconditions/external tasks unless tied to confirmed project functionality and implementation evidence. |
| Privacy | Do not include sensitive client data, credentials, URLs, account IDs, or raw payloads in backlog artifacts. |

## Spec Units

{unit_index}

## Confirmed EARS Requirements

These rows are parsed from `02_requirements/requirements.md` and remain source-of-truth there. Specs and backlog cite their `REQ-EARS-*` IDs so testable statements survive downstream handoff.

{ears_block or "`[PENDING INPUT]` - no confirmed EARS statements are present in `02_requirements/requirements.md`."}

## Progressive Disclosure Context Map

{render_prd_section_context(context)}

## Retrieval Plan For Backlog Agents

| Need | Suggested `/retrieve` Query | Filters | Use In Backlog |
| --- | --- | --- | --- |
| Epic value and MVP | `business outcome scope mvp kpi users` | `--workflow backlog --domain business --summary-only` | Epic outcome and priority |
| FR and AC slicing | `functional requirements acceptance criteria given when then business rules` | `--workflow backlog --domain product` | Story boundaries and ACs |
| Technical dependencies | `architecture integrations dependencies data ownership contracts failure behavior` | `--workflow backlog --domain technical` | Backend/technical stories and blockers |
| UX stories | `journey screens states validations copy accessibility unchanged behavior` | `--workflow backlog --domain design` | Frontend stories and UX acceptance |
| Quality coverage | `acceptance testability edge cases regression test data evidence` | `--workflow backlog --domain quality` | ACs, TC seeds, readiness audit |
| Open gaps | `pending input prd gaps dependencies roadmap nfr kpi` | `--workflow backlog --artifact-type gap_report` | Blockers, spikes, follow-up stories |
| Enabler boundary | `SAD architecture as-is to-be frontend backend prototype auth data integration audit observability enabler precondition` | `--workflow backlog --summary-only` | Decide whether a cross-cutting enabler epic is valid |

## Backlog Seeds

Backlog seeds are derived from evidence-backed spec units. If no unit exists, backlog agents must work from pending inputs and focused retrieval rather than fixed placeholder stories.

| Source Unit | Candidate Item | Type | Trace |
| --- | --- | --- | --- |
{render_backlog_seed_rows(spec_units)}

## Decision And Assumption Trail

| Source | Type | Statement | Risk If Wrong |
| --- | --- | --- | --- |
| Sentinel invariant | Rule | Any detail not present in seeds, source input, spec units, or domain context remains pending confirmation. | Downstream backlog may require rework after `/sync`. |
| PRD readiness | Rule | PRD-generated FR/JTBD/NFR structure must be checked against evidence before slicing. | Stories may need refinement if PRD readiness gaps remain. |

## Traceability

- Parent requirement: `REQ-001`
- EARS requirements: {ears_trace}
- Parent PRD: `PRD-001`
- Spec units: {", ".join(f"`{unit['id']}`" for unit in (spec_units or [])) or "`[PENDING INPUT]`"}
- Mature brief: `02_requirements/project-brief.md` when present
- Context pack: `08_context_packs/specs_generation.json`
- Downstream artifacts: epics, user stories, acceptance criteria, tests, and traceability matrix.
"""


def ears_trace_ids(context: dict[str, object]) -> list[str]:
    rows = context.get("ears_requirements", []) if isinstance(context, dict) else []
    ids: list[str] = []
    if isinstance(rows, list):
        for row in rows:
            ears_id = row.get("id") if isinstance(row, dict) else None
            if isinstance(ears_id, str) and EARS_REQUIREMENT_ID_RE.match(ears_id):
                ids.append(ears_id)
    return ids


def bounded_text(text: str, limit: int) -> str:
    cleaned = text.strip()
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[:limit].rstrip() + "\n\n[TRUNCATED IN GENERATED ARTIFACT - retrieve focused source context if needed]"


def safe_cell(value: Any, limit: int) -> str:
    text = str(value).replace("\n", " ").replace("|", "/").strip()
    return text[:limit]
