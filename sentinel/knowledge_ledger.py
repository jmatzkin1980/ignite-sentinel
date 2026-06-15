from __future__ import annotations

from pathlib import Path
from typing import Any

from .workspace import read_json, write_json, workspace_path

LEDGER_STATUSES = {"CONFIRMED", "ASSUMED", "OPEN", "INFERRED"}


def materialize_knowledge_ledger(
    project_id: str,
    seeds_text: str,
    gaps: list[dict[str, str]],
    decisions_text: str,
    trace_refs: dict[str, str],
    assumptions_text: str = "",
) -> dict[str, Any]:
    """Write the lens knowledge ledger from governed discovery artifacts.

    The ledger consolidates existing source-of-truth artifacts. It does not infer
    new facts; unsupported knowledge remains OPEN with explicit pending input.
    """
    units = build_knowledge_units(seeds_text, gaps, decisions_text, trace_refs, assumptions_text)
    summary = summarize_units(units)
    payload = {
        "project_id": project_id,
        "artifact": "knowledge_state",
        "version": 1,
        "statuses": sorted(LEDGER_STATUSES),
        "summary": summary,
        "units": units,
    }
    base = workspace_path(project_id)
    json_path = base / "01_discovery" / "knowledge_state.json"
    md_path = base / "01_discovery" / "knowledge_state.md"
    write_json(json_path, payload)
    md_path.write_text(render_knowledge_state(project_id, units, summary), encoding="utf-8")
    return {"json_path": json_path, "md_path": md_path, "payload": payload}


def build_knowledge_units(
    seeds_text: str,
    gaps: list[dict[str, str]],
    decisions_text: str,
    trace_refs: dict[str, str],
    assumptions_text: str = "",
) -> list[dict[str, Any]]:
    units: list[dict[str, Any]] = []
    sequence = 1

    for seed in parse_seed_rows(seeds_text):
        unit = {
            "id": f"KLU-{sequence:03d}",
            "lens": normalize_lens(seed.get("lens", "product")),
            "statement": seed.get("statement", ""),
            "status": normalize_knowledge_status(seed.get("status", "")),
            "evidence": evidence_for_seed(seed, trace_refs),
            "links": links_for_seed(seed, trace_refs),
        }
        if unit["statement"]:
            units.append(unit)
            sequence += 1

    for gap in gaps:
        status = normalize_gap_status(gap.get("status", "OPEN"))
        statement = gap.get("description") or gap.get("question") or gap.get("id", "Unresolved discovery gap")
        evidence = {"note": "[PENDING INPUT]"}
        if gap.get("evidence_mention"):
            evidence = {"trace_id": trace_refs.get("gap_report"), "quote": gap["evidence_mention"]}
        elif status == "CONFIRMED" and gap.get("resolution_note"):
            evidence = {"trace_id": trace_refs.get("gap_report"), "quote": gap["resolution_note"]}
        unit = {
            "id": f"KLU-{sequence:03d}",
            "lens": normalize_lens(gap.get("lens", "product")),
            "statement": statement,
            "status": status,
            "evidence": evidence,
            "links": compact_links(
                [
                    {"type": "gap", "target": gap.get("id")},
                    {"type": "artifact", "target": trace_refs.get("gap_report")},
                ]
            ),
        }
        units.append(unit)
        sequence += 1

    for decision in parse_decision_rows(decisions_text):
        unit = {
            "id": f"KLU-{sequence:03d}",
            "lens": "product",
            "statement": decision.get("statement", ""),
            "status": normalize_knowledge_status(decision.get("status", "")),
            "evidence": evidence_for_decision(decision, trace_refs),
            "links": compact_links(
                [
                    {"type": "decision", "target": decision.get("id")},
                    {"type": "artifact", "target": trace_refs.get("decision_log")},
                    {"type": "parent", "target": decision.get("parent")},
                ]
            ),
        }
        if unit["statement"]:
            units.append(unit)
            sequence += 1

    for assumption in parse_assumption_rows(assumptions_text):
        unit = {
            "id": f"KLU-{sequence:03d}",
            "lens": normalize_lens(assumption.get("lens", "product")),
            "statement": assumption.get("statement", ""),
            "status": "ASSUMED",
            "evidence": {
                "trace_id": trace_refs.get("assumption_register", ""),
                "quote": assumption.get("justification", ""),
            },
            "links": compact_links(
                [
                    {"type": "assumption", "target": assumption.get("id")},
                    {"type": "gap", "target": assumption.get("closes_gap")},
                    {"type": "owner", "target": assumption.get("owner")},
                    {"type": "risk", "target": assumption.get("risk")},
                    {"type": "artifact", "target": trace_refs.get("assumption_register")},
                ]
            ),
        }
        if unit["statement"]:
            units.append(unit)
            sequence += 1

    return units


def render_knowledge_state(project_id: str, units: list[dict[str, Any]], summary: dict[str, Any]) -> str:
    rows = "\n".join(
        "| {id} | {lens} | {status} | {statement} | {evidence} | {links} |".format(
            id=unit["id"],
            lens=unit["lens"],
            status=unit["status"],
            statement=escape_table(unit["statement"]),
            evidence=escape_table(format_evidence(unit.get("evidence", {}))),
            links=escape_table(format_links(unit.get("links", []))),
        )
        for unit in units
    ) or "| N/A | N/A | N/A | No knowledge units found. | N/A | N/A |"
    by_status = ", ".join(f"{status}: {count}" for status, count in sorted(summary.get("by_status", {}).items()))
    by_lens = ", ".join(f"{lens}: {count}" for lens, count in sorted(summary.get("by_lens", {}).items()))
    return f"""# Knowledge State - {project_id}

Canonical discovery knowledge ledger by lens. It consolidates seeds, gaps, and
decisions from governed workspace artifacts; it does not invent missing content.
Every confirmed or inferred statement keeps evidence, and unresolved knowledge is
explicitly marked `[PENDING INPUT]`.

## Summary

- Total units: {summary.get("total", 0)}
- By status: {by_status or "None"}
- By lens: {by_lens or "None"}

## Knowledge Units

| Unit ID | Lens | Status | Statement | Evidence | Links |
| --- | --- | --- | --- | --- | --- |
{rows}
"""


def knowledge_ledger_summary(project_id: str) -> dict[str, Any]:
    path = workspace_path(project_id) / "01_discovery" / "knowledge_state.json"
    if not path.exists():
        return {"total": 0, "by_status": {}, "by_lens": {}, "path": None}
    data = read_json(path, {})
    summary = data.get("summary", {}) if isinstance(data, dict) else {}
    return {
        "total": int(summary.get("total", 0) or 0),
        "by_status": dict(summary.get("by_status", {}) or {}),
        "by_lens": dict(summary.get("by_lens", {}) or {}),
        "path": str(path.as_posix()),
    }


def summarize_units(units: list[dict[str, Any]]) -> dict[str, Any]:
    by_status: dict[str, int] = {}
    by_lens: dict[str, int] = {}
    for unit in units:
        by_status[unit["status"]] = by_status.get(unit["status"], 0) + 1
        by_lens[unit["lens"]] = by_lens.get(unit["lens"], 0) + 1
    return {"total": len(units), "by_status": by_status, "by_lens": by_lens}


def parse_seed_rows(text: str) -> list[dict[str, str]]:
    seeds: list[dict[str, str]] = []
    for cells in markdown_table_rows(text):
        if len(cells) >= 7 and cells[0].startswith("SEED-"):
            seeds.append(
                {
                    "id": cells[0],
                    "lens": cells[1],
                    "origin_type": cells[2],
                    "origin_ref": strip_ticks(cells[3]),
                    "statement": cells[4],
                    "status": cells[5],
                    "node_type": cells[6],
                }
            )
        elif len(cells) >= 7 and cells[0].startswith("AUTO-SEED-"):
            seeds.append(
                {
                    "id": cells[0],
                    "lens": "",
                    "gap_id": strip_ticks(cells[1]),
                    "statement": cells[3],
                    "status": cells[2],
                    "origin_ref": strip_ticks(cells[4]),
                    "node_type": "GAP_RESOLUTION",
                }
            )
    return seeds


def parse_decision_rows(text: str) -> list[dict[str, str]]:
    decisions: list[dict[str, str]] = []
    for cells in markdown_table_rows(text):
        if len(cells) >= 4 and (cells[0].startswith("DEC-") or cells[0].startswith("AUTO-DEC-")):
            decisions.append(
                {
                    "id": cells[0],
                    "status": cells[1] if cells[0].startswith("DEC-") else cells[2],
                    "parent": strip_ticks(cells[2]) if cells[0].startswith("DEC-") else strip_ticks(cells[1]),
                    "statement": cells[3] if cells[0].startswith("DEC-") else cells[3],
                }
            )
    return decisions


def parse_assumption_rows(text: str) -> list[dict[str, str]]:
    assumptions: list[dict[str, str]] = []
    for cells in markdown_table_rows(text):
        if len(cells) >= 8 and cells[0].startswith("ASM-"):
            assumptions.append(
                {
                    "id": cells[0],
                    "lens": cells[1],
                    "statement": cells[2],
                    "owner": cells[3],
                    "risk": cells[4],
                    "justification": cells[5],
                    "closes_gap": strip_ticks(cells[6]) if cells[6] not in {"-", "N/A"} else "",
                    "status": cells[7],
                }
            )
    return assumptions


def markdown_table_rows(text: str) -> list[list[str]]:
    rows: list[list[str]] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|") or "---" in stripped:
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if not cells or cells[0] in {"Seed ID", "Decision ID", "Assumption ID"}:
            continue
        rows.append(cells)
    return rows


def normalize_knowledge_status(status: str) -> str:
    value = status.strip().upper().replace("-", "_").replace(" ", "_")
    if value in {"KNOWN", "CONFIRMED", "CLOSED", "ANSWERED"}:
        return "CONFIRMED"
    if value in {"ASSUMED", "ASSUMPTION"}:
        return "ASSUMED"
    if value in {"INFERRED", "INFERRED_FROM_INPUT"}:
        return "INFERRED"
    return "OPEN"


def normalize_gap_status(status: str) -> str:
    value = status.strip().upper().replace("-", "_").replace(" ", "_")
    if value == "CLOSED":
        return "CONFIRMED"
    if value == "ASSUMED":
        return "ASSUMED"
    if value == "INFERRED":
        return "INFERRED"
    return "OPEN"


def normalize_lens(lens: str) -> str:
    value = lens.strip().lower()
    if value in {"", "n/a", "-"}:
        return "product"
    if value == "technology":
        return "technical"
    if "/" in value:
        return value.split("/", 1)[0]
    return value


def evidence_for_seed(seed: dict[str, str], trace_refs: dict[str, str]) -> dict[str, str]:
    status = normalize_knowledge_status(seed.get("status", ""))
    if status == "OPEN":
        return {"note": "[PENDING INPUT]"}
    origin_ref = seed.get("origin_ref") or trace_refs.get("raw_input")
    return {"trace_id": origin_ref, "quote": seed.get("statement", "")}


def evidence_for_decision(decision: dict[str, str], trace_refs: dict[str, str]) -> dict[str, str]:
    status = normalize_knowledge_status(decision.get("status", ""))
    if status == "OPEN":
        return {"note": "[PENDING INPUT]"}
    return {"trace_id": trace_refs.get("decision_log", ""), "quote": decision.get("statement", "")}


def links_for_seed(seed: dict[str, str], trace_refs: dict[str, str]) -> list[dict[str, str]]:
    return compact_links(
        [
            {"type": "seed", "target": seed.get("id")},
            {"type": "gap", "target": seed.get("gap_id")},
            {"type": "artifact", "target": trace_refs.get("identity_seed_bank")},
            {"type": "source", "target": seed.get("origin_ref") or trace_refs.get("raw_input")},
        ]
    )


def compact_links(links: list[dict[str, str | None]]) -> list[dict[str, str]]:
    compacted: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for link in links:
        target = str(link.get("target") or "").strip()
        link_type = str(link.get("type") or "").strip()
        if not target or target in {"-", "N/A"} or not link_type:
            continue
        key = (link_type, target)
        if key in seen:
            continue
        seen.add(key)
        compacted.append({"type": link_type, "target": target})
    return compacted


def format_evidence(evidence: dict[str, str]) -> str:
    if evidence.get("note"):
        return evidence["note"]
    trace_id = evidence.get("trace_id", "")
    quote = evidence.get("quote", "")
    if trace_id and quote:
        return f"`{trace_id}`: {quote}"
    return trace_id or quote or "[PENDING INPUT]"


def format_links(links: list[dict[str, str]]) -> str:
    return ", ".join(f"{link['type']}=`{link['target']}`" for link in links) or "None"


def escape_table(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ").strip()


def strip_ticks(value: str) -> str:
    return value.strip().strip("`")
