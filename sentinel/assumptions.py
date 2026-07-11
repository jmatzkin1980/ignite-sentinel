from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from .lens_registry import known_lenses
from .risk_category_registry import known_risk_categories
from .memory import ContextBroker
from .core.graph import add_edge, add_node, load_graph
from .core.io import read_json as core_read_json
from .core.markdown import parse_table_rows
from .workspace import read_json, state_path, update_state, workspace_path, write_json


class AssumptionError(RuntimeError):
    """Raised when a governed assumption source cannot be accepted."""


RISK_LEVELS = {"low", "med", "medium", "high"}
UNCERTAINTY_LEVELS = {"low", "med", "medium", "high"}


def normalize_level(value: object, *, default: str = "med") -> str:
    level = str(value or default).strip().lower()
    if level == "medium":
        return "med"
    return level


def assumption_priority_signal(risk: str, uncertainty: str) -> str:
    if risk == "high" and uncertainty == "high":
        return "test before advancing"
    if risk == "high" or uncertainty == "high":
        return "watch closely"
    return "monitor"


def load_assumption_source(source: Path) -> dict[str, Any]:
    if not source.exists():
        raise AssumptionError(f"Assumption source not found: {source}")
    try:
        data = core_read_json(source, {})
    except json.JSONDecodeError as exc:
        raise AssumptionError(f"Assumption source is not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise AssumptionError("Assumption source must be a JSON object.")
    return data


def assumption_grounding_text(base: Path) -> str:
    roots = [
        base / "00_raw",
        base / "01_discovery",
        base / "02_requirements",
        base / "07_changes",
    ]
    chunks: list[str] = []
    for root in roots:
        if not root.exists():
            continue
        for path in sorted(root.rglob("*")):
            if path.is_file() and path.suffix.lower() in {".md", ".txt", ".json"}:
                chunks.append(path.read_text(encoding="utf-8", errors="ignore"))
    return "\n\n".join(chunks)


def normalize_for_match(text: str) -> str:
    return " ".join(text.split()).lower()


def validate_assumptions(data: dict[str, Any], grounding_text: str) -> list[dict[str, str]]:
    items = data.get("assumptions")
    if not isinstance(items, list) or not items:
        raise AssumptionError("Assumption source must contain a non-empty assumptions array.")
    valid_lenses = known_lenses()
    haystack = normalize_for_match(grounding_text)
    validated: list[dict[str, str]] = []
    seen: set[str] = set()
    for index, raw in enumerate(items, start=1):
        if not isinstance(raw, dict):
            raise AssumptionError(f"ASSUMPTION-{index:03d}: item must be an object.")
        assumption_id = str(raw.get("id") or f"ASM-{index:03d}").strip().upper()
        if not assumption_id.startswith("ASM-"):
            raise AssumptionError(f"{assumption_id}: id must start with ASM-.")
        if assumption_id in seen:
            raise AssumptionError(f"{assumption_id}: duplicate assumption id in source.")
        seen.add(assumption_id)
        lens = str(raw.get("lens", "")).strip().lower()
        if lens == "technology":
            lens = "technical"
        if lens not in valid_lenses:
            raise AssumptionError(
                f"{assumption_id}: lens '{raw.get('lens')}' is not declared "
                f"({', '.join(sorted(valid_lenses))})."
            )
        statement = str(raw.get("statement", "")).strip()
        if not statement:
            raise AssumptionError(f"{assumption_id}: statement is required.")
        owner = str(raw.get("owner", "")).strip()
        if not owner:
            raise AssumptionError(f"{assumption_id}: owner is required and must be human-owned.")
        risk = normalize_level(raw.get("risk"), default="")
        if risk not in {"low", "med", "high"}:
            raise AssumptionError(f"{assumption_id}: risk must be low, med, or high.")
        uncertainty = normalize_level(raw.get("uncertainty"), default="med")
        if uncertainty not in {"low", "med", "high"}:
            raise AssumptionError(f"{assumption_id}: uncertainty must be low, med, or high.")
        justification = str(raw.get("justification", raw.get("evidence", ""))).strip()
        if not justification:
            raise AssumptionError(f"{assumption_id}: justification/evidence quote is required.")
        if normalize_for_match(justification) not in haystack:
            raise AssumptionError(
                f"{assumption_id}: justification quote is not found verbatim in local evidence. "
                "Assumptions need a cited basis; otherwise keep the gap open."
            )
        closes_gap = str(raw.get("closes_gap", "")).strip().upper()
        if closes_gap and not closes_gap.startswith("GAP-"):
            raise AssumptionError(f"{assumption_id}: closes_gap must be a GAP-* id when present.")
        risk_category = str(raw.get("risk_category", "")).strip().lower()
        if risk_category:
            valid_risk_categories = known_risk_categories()
            if risk_category not in valid_risk_categories:
                raise AssumptionError(
                    f"{assumption_id}: risk_category '{raw.get('risk_category')}' is not declared "
                    f"({', '.join(sorted(valid_risk_categories))})."
                )
        validated.append(
            {
                "id": assumption_id,
                "lens": lens,
                "statement": statement,
                "owner": owner,
                "risk": risk,
                "uncertainty": uncertainty,
                "priority_signal": assumption_priority_signal(risk, uncertainty),
                "justification": justification,
                "closes_gap": closes_gap,
                "risk_category": risk_category,
                "status": "ASSUMED",
            }
        )
    return validated


def assumption_rows(text: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|") or "---" in stripped:
            continue
        cells = parse_table_rows(stripped)[0]
        if len(cells) < 8 or not cells[0].startswith("ASM-"):
            continue
        if len(cells) >= 10:
            uncertainty = normalize_level(cells[5])
            priority_signal = cells[6]
            justification = cells[7]
            closes_gap = cells[8]
            status = cells[9]
        else:
            uncertainty = "med"
            priority_signal = assumption_priority_signal(normalize_level(cells[4]), uncertainty)
            justification = cells[5]
            closes_gap = cells[6]
            status = cells[7]
        risk = normalize_level(cells[4])
        risk_category = cells[10].strip().lower() if len(cells) >= 11 else ""
        if risk_category in {"-", "n/a"}:
            risk_category = ""
        rows.append(
            {
                "id": cells[0],
                "lens": cells[1],
                "statement": cells[2].replace("\\|", "|"),
                "owner": cells[3],
                "risk": risk,
                "uncertainty": uncertainty,
                "priority_signal": priority_signal,
                "justification": justification.replace("\\|", "|"),
                "closes_gap": "" if closes_gap in {"-", "N/A"} else closes_gap,
                "status": status,
                "risk_category": risk_category,
            }
        )
    return rows


def load_assumptions(project_id: str) -> list[dict[str, str]]:
    path = workspace_path(project_id) / "01_discovery" / "assumptions.md"
    if not path.exists():
        return []
    return assumption_rows(path.read_text(encoding="utf-8"))


def assumption_projection_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    projected: list[dict[str, str]] = []
    for row in rows:
        if row.get("status", "").upper() != "ASSUMED":
            continue
        risk = normalize_level(row.get("risk"))
        uncertainty = normalize_level(row.get("uncertainty"))
        projected.append(
            {
                "id": row.get("id", ""),
                "statement": row.get("statement", ""),
                "risk": risk,
                "uncertainty": uncertainty,
                "priority_signal": assumption_priority_signal(risk, uncertainty),
                "owner": row.get("owner", ""),
                "closes_gap": row.get("closes_gap", ""),
                "status": row.get("status", ""),
                "basis_quote": row.get("justification", ""),
            }
        )
    order = {"high": 0, "med": 1, "low": 2}
    return sorted(
        projected,
        key=lambda row: (
            order.get(row.get("risk", "med"), 1),
            order.get(row.get("uncertainty", "med"), 1),
            row.get("id", ""),
        ),
    )


def assumptions_projection(project_id: str) -> dict[str, Any]:
    rows = load_assumptions(project_id)
    assumptions = assumption_projection_rows(rows)
    high_risk = [row["id"] for row in assumptions if row.get("risk", "").lower() == "high"]
    test_before_advancing = [
        row["id"]
        for row in assumptions
        if row.get("risk") == "high" and row.get("uncertainty") == "high"
    ]
    return {
        "project_id": project_id,
        "source": "01_discovery/assumptions.md",
        "source_of_truth": "01_discovery/assumptions.md",
        "artifact": "08_context_packs/assumptions_projection.json",
        "assumptions": assumptions,
        "summary": {
            "total_assumptions": len(rows),
            "assumed": len(assumptions),
            "high_risk_assumed": len(high_risk),
            "high_risk_assumption_ids": high_risk,
            "test_before_advancing": len(test_before_advancing),
            "test_before_advancing_ids": test_before_advancing,
        },
    }


def persist_assumptions_projection(project_id: str) -> Path:
    path = workspace_path(project_id) / "08_context_packs" / "assumptions_projection.json"
    write_json(path, assumptions_projection(project_id))
    return path


def persist_assumptions(project_id: str, rows: list[dict[str, str]]) -> Path:
    path = workspace_path(project_id) / "01_discovery" / "assumptions.md"
    path.write_text(render_assumptions(project_id, rows), encoding="utf-8")
    return path


def update_assumption_statuses(
    project_id: str,
    *,
    validated_gap_ids: set[str] | None = None,
    invalidated_assumption_ids: set[str] | None = None,
    evidence: str = "",
    source_id: str = "",
) -> dict[str, Any]:
    """Move governed assumptions when BA-owned evidence confirms or invalidates them."""
    rows = load_assumptions(project_id)
    if not rows:
        return {"validated": [], "invalidated": [], "path": None, "summary": summarize_assumptions([])}
    validated_gap_ids = {gap_id.upper() for gap_id in (validated_gap_ids or set())}
    invalidated_assumption_ids = {assumption_id.upper() for assumption_id in (invalidated_assumption_ids or set())}
    validated: list[str] = []
    invalidated: list[str] = []
    for row in rows:
        assumption_id = row.get("id", "").upper()
        closes_gap = row.get("closes_gap", "").upper()
        if assumption_id in invalidated_assumption_ids:
            if row.get("status") != "INVALIDATED":
                invalidated.append(assumption_id)
            row["status"] = "INVALIDATED"
        elif closes_gap and closes_gap in validated_gap_ids and row.get("status") == "ASSUMED":
            validated.append(assumption_id)
            row["status"] = "VALIDATED"
    path = persist_assumptions(project_id, rows) if validated or invalidated else workspace_path(project_id) / "01_discovery" / "assumptions.md"
    summary = summarize_assumptions(rows)
    update_state(project_id, assumption_summary=summary)
    return {
        "validated": validated,
        "invalidated": invalidated,
        "path": str(path.as_posix()),
        "summary": summary,
    }


def _format_assumption_row(row: dict[str, str], *, include_category: bool) -> str:
    risk = normalize_level(row["risk"])
    uncertainty = normalize_level(row.get("uncertainty"))
    line = "| {id} | {lens} | {statement} | {owner} | {risk} | {uncertainty} | {priority_signal} | {justification} | {closes_gap} | {status} |".format(
        id=row["id"],
        lens=row["lens"],
        statement=escape_table(row["statement"]),
        owner=escape_table(row["owner"]),
        risk=risk,
        uncertainty=uncertainty,
        priority_signal=assumption_priority_signal(risk, uncertainty),
        justification=escape_table(row["justification"]),
        closes_gap=row.get("closes_gap") or "-",
        status=row.get("status", "ASSUMED"),
    )
    if not include_category:
        return line
    return f"{line[:-1]}| {row.get('risk_category') or '-'} |"


def _assumption_table(rows: list[dict[str, str]], *, include_category: bool) -> str:
    header = "| Assumption ID | Lens | Statement | Owner | Risk | Uncertainty | Priority Signal | Justification / Evidence | Closes Gap | Status |"
    separator = "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"
    if include_category:
        header = f"{header[:-1]}| Risk Category |"
        separator = f"{separator[:-1]}| --- |"
    body = "\n".join(_format_assumption_row(row, include_category=include_category) for row in rows) or (
        "| N/A | N/A | No assumptions registered. | N/A | N/A | N/A | N/A | N/A | N/A | N/A |"
        + (" N/A |" if include_category else "")
    )
    return f"{header}\n{separator}\n{body}"


def render_assumptions(project_id: str, rows: list[dict[str, str]]) -> str:
    intro = f"""# Assumptions - {project_id}

Governed assumptions are explicit BA-owned decisions used when a gap cannot be
confirmed yet but the team chooses to proceed with visible risk. They do not
turn uncertainty into confirmed scope. Each row has human owner, importance
(`risk`), uncertainty, local cited basis, and optional provisional gap link.
`high` risk plus `high` uncertainty is a non-blocking "test before advancing"
signal for BA prioritization.

"""
    if not any(row.get("risk_category") for row in rows):
        return intro + _assumption_table(rows, include_category=False) + "\n"

    from .risk_category_registry import RISK_CATEGORY_ORDER, risk_category_label

    grouped: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        grouped.setdefault(row.get("risk_category") or "", []).append(row)
    ordered_categories = [category for category in RISK_CATEGORY_ORDER if category in grouped]
    ordered_categories += [
        category for category in sorted(grouped) if category and category not in ordered_categories
    ]
    if "" in grouped:
        ordered_categories.append("")

    sections = [
        "Grouped by Cagan risk category (`risk_category`); rows without one are listed under Uncategorized.",
    ]
    for category in ordered_categories:
        label = risk_category_label(category) if category else "Uncategorized"
        sections.append(f"## {label}\n\n{_assumption_table(grouped[category], include_category=True)}")
    return intro + "\n\n".join(sections) + "\n"


def summarize_assumptions(rows: list[dict[str, str]]) -> dict[str, Any]:
    by_risk = {"low": 0, "med": 0, "high": 0}
    by_uncertainty = {"low": 0, "med": 0, "high": 0}
    high_risk_blocking: list[str] = []
    test_before_advancing: list[str] = []
    by_lens: dict[str, int] = {}
    by_status: dict[str, int] = {}
    by_risk_category: dict[str, int] = {}
    for row in rows:
        risk = normalize_level(row.get("risk"))
        uncertainty = normalize_level(row.get("uncertainty"))
        by_risk[risk] = by_risk.get(risk, 0) + 1
        by_uncertainty[uncertainty] = by_uncertainty.get(uncertainty, 0) + 1
        by_lens[row.get("lens", "product")] = by_lens.get(row.get("lens", "product"), 0) + 1
        status = row.get("status", "ASSUMED").upper()
        by_status[status] = by_status.get(status, 0) + 1
        risk_category = row.get("risk_category") or "uncategorized"
        by_risk_category[risk_category] = by_risk_category.get(risk_category, 0) + 1
        if risk == "high" and row.get("closes_gap"):
            high_risk_blocking.append(row["closes_gap"])
        if risk == "high" and uncertainty == "high":
            test_before_advancing.append(row["id"])
    return {
        "total": len(rows),
        "by_risk": by_risk,
        "by_uncertainty": by_uncertainty,
        "by_lens": by_lens,
        "by_status": by_status,
        "by_risk_category": by_risk_category,
        "high_risk_gap_ids": sorted(set(high_risk_blocking)),
        "test_before_advancing_ids": sorted(set(test_before_advancing)),
    }


def assumptions_by_brief_section(project_id: str) -> dict[str, list[dict[str, str]]]:
    from .discovery import brief_section_for_gap

    by_section: dict[str, list[dict[str, str]]] = {}
    for row in load_assumptions(project_id):
        section = brief_section_for_gap(row.get("closes_gap", ""))
        by_section.setdefault(section, []).append(row)
    return by_section


def render_assumption_bullets(rows: list[dict[str, str]], language: str = "en") -> str:
    if not rows:
        return ""
    label = "supuesto gobernado" if language == "es" else "governed assumption"
    return "\n".join(
        "- {statement} _({label}: `{id}`, owner: {owner}, risk: {risk}, basis: \"{justification}\")_".format(
            statement=row["statement"],
            label=label,
            id=row["id"],
            owner=row["owner"],
            risk=row["risk"],
            justification=row["justification"],
        )
        for row in rows
    )


def render_prd_assumption_rows(project_id: str) -> str:
    rows = load_assumptions(project_id)
    if not rows:
        return ""
    return "\n".join(
        f"| `{row['id']}` | {escape_table(row['statement'])} | {row['risk']} | {escape_table(row['owner'])} | {escape_table(row['justification'])} | `{row.get('closes_gap') or 'N/A'}` | {row.get('status', 'ASSUMED')} |"
        for row in rows
    )


def apply_assumptions(project_id: str, source: Path) -> dict[str, Any]:
    base = workspace_path(project_id)
    if not base.exists():
        raise AssumptionError(f"Workspace not found: {project_id}")
    gaps_path = base / "01_discovery" / "gaps.md"
    if not gaps_path.exists():
        raise AssumptionError("Cannot register assumptions before /ingest creates 01_discovery/gaps.md.")
    data = load_assumption_source(source)
    rows = validate_assumptions(data, assumption_grounding_text(base))
    assumption_path = base / "01_discovery" / "assumptions.md"
    existing = load_assumptions(project_id)
    existing_ids = {row["id"] for row in existing}
    accepted = [row for row in rows if row["id"] not in existing_ids]
    skipped = [row["id"] for row in rows if row["id"] in existing_ids]
    merged = existing + accepted
    assumption_path.write_text(render_assumptions(project_id, merged), encoding="utf-8")

    source_dir = base / "01_discovery" / "assumptions"
    source_dir.mkdir(parents=True, exist_ok=True)
    archived = unique_path(source_dir / f"{source.stem}.json")
    shutil.copyfile(source, archived)

    assumption_id = add_node(
        project_id,
        "DISC",
        "assumption_register",
        assumption_path,
        "Governed assumptions register",
        domain="product",
    )
    graph_nodes = load_graph(project_id).get("nodes", [])
    for gap_node in [node for node in graph_nodes if node.get("type") == "gap_report"]:
        add_edge(project_id, assumption_id, gap_node["id"], "provisionally_addresses")
    for raw_node in [node for node in graph_nodes if node.get("type") == "raw_input"]:
        add_edge(project_id, raw_node["id"], assumption_id, "basis_for_assumption")

    broker = ContextBroker(project_id)
    broker.index_artifact(
        assumption_id,
        "assumption_register",
        assumption_path,
        assumption_path.read_text(encoding="utf-8"),
        trace_ids=[assumption_id],
    )
    summary = summarize_assumptions(merged)
    projection_path = persist_assumptions_projection(project_id)
    state = read_json(state_path(project_id), {})
    updates = {
        "last_assumption_id": assumption_id,
        "assumption_summary": summary,
        "last_assumption_source": str(archived.as_posix()),
    }
    artifacts = dict(state.get("artifacts", {}))
    artifacts["assumptions"] = str(assumption_path.as_posix())
    artifacts["assumptions_projection"] = str(projection_path.as_posix())
    updates["artifacts"] = artifacts
    update_state(project_id, **updates)
    from .discovery import refresh_knowledge_ledger

    ledger = refresh_knowledge_ledger(project_id, broker)
    update_state(project_id, knowledge_ledger_summary=ledger["payload"].get("summary", {}))
    return {
        "project_id": project_id,
        "assumption_id": assumption_id,
        "path": str(assumption_path.as_posix()),
        "knowledge_state": str(ledger["md_path"].as_posix()),
        "accepted": [row["id"] for row in accepted],
        "skipped_duplicates": skipped,
        "assumption_summary": summary,
    }


def unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    counter = 2
    while True:
        candidate = path.with_name(f"{path.stem}-{counter}{path.suffix}")
        if not candidate.exists():
            return candidate
        counter += 1


def escape_table(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ").strip()
