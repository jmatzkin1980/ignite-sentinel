from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Any

from .core.graph import add_edge, add_node, nodes_by_type
from .core.io import write_json
from .memory import ContextBroker
from .workspace import read_json, state_path, update_state, workspace_path


class ComposeError(RuntimeError):
    """Raised when a PRD composition draft has no valid blocks."""


PRD_SECTION_RE = re.compile(r"^## (\d+)\.", re.MULTILINE)
PENDING_MARKERS = ("[PENDING INPUT]", "GAP-PRD-", "GAP-METRIC-SOURCE")


def apply_prd_composition(project_id: str, source: Path) -> dict[str, object]:
    base = workspace_path(project_id)
    prd_path = base / "03_specs" / "prd.md"
    if not prd_path.exists():
        raise ComposeError("Cannot compose PRD before /specs creates 03_specs/prd.md.")
    if not source.exists():
        raise ComposeError(f"Composition source not found: {source}")

    data = read_json(source, {})
    prd_text = prd_path.read_text(encoding="utf-8")
    sections = prd_sections(prd_text)
    evidence_text = composition_evidence_text(base)
    accepted, rejected = validate_composition_blocks(data, sections, evidence_text)

    comp_dir = base / "03_specs" / "compositions"
    comp_dir.mkdir(parents=True, exist_ok=True)
    archived = unique_path(comp_dir / source.name)
    shutil.copyfile(source, archived)

    accepted_path = comp_dir / "accepted_blocks.json"
    existing = read_json(accepted_path, [])
    existing_blocks = existing if isinstance(existing, list) else []
    merged_blocks = [*existing_blocks, *accepted]
    write_json(accepted_path, merged_blocks)
    report_path = write_composition_report(project_id, accepted, rejected, archived)

    if accepted:
        prd_path.write_text(render_prd_compositions(project_id, prd_text), encoding="utf-8")

    composition_id = add_node(project_id, "PRD", "prd_composition", report_path, f"PRD composition from {source.name}", domain="product")
    prd_nodes = nodes_by_type(project_id, "prd")
    if prd_nodes:
        add_edge(project_id, prd_nodes[0]["id"], composition_id, "composed_by")
    ContextBroker(project_id).index_artifact(
        composition_id,
        "prd_composition",
        report_path,
        report_path.read_text(encoding="utf-8"),
        domain="product",
        trace_ids=[composition_id],
    )
    update_state(
        project_id,
        prd_composition_count=len(merged_blocks),
        last_prd_composition_id=composition_id,
        last_prd_composition_source=str(archived.as_posix()),
    )

    if not accepted:
        raise ComposeError("No PRD composition blocks were accepted. See 03_specs/compositions/composition_report.md.")
    return {
        "composition_id": composition_id,
        "accepted": [block["id"] for block in accepted],
        "rejected": rejected,
        "source": str(archived.as_posix()),
        "report": str(report_path.as_posix()),
        "prd": str(prd_path.as_posix()),
    }


def validate_composition_blocks(
    data: dict[str, Any],
    sections: dict[str, str],
    evidence_text: str,
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    blocks = data.get("blocks")
    if not isinstance(blocks, list) or not blocks:
        raise ComposeError("Composition source must contain a non-empty blocks array.")
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, str]] = []
    for index, block in enumerate(blocks, start=1):
        section = str(block.get("section", "")).strip()
        block_id = str(block.get("id") or f"COMP-{index:03d}")
        reason = validate_block_shape(block, section, sections, evidence_text)
        if reason:
            rejected.append({"id": block_id, "section": section or "?", "reason": reason})
            continue
        paragraphs = []
        for paragraph in block["paragraphs"]:
            paragraphs.append(
                {
                    "text": str(paragraph["text"]).strip(),
                    "citations": [str(item).strip() for item in paragraph["citations"]],
                }
            )
        accepted.append({"id": block_id, "section": section, "origin": "agent", "paragraphs": paragraphs})
    return accepted, rejected


def validate_block_shape(block: Any, section: str, sections: dict[str, str], evidence_text: str) -> str:
    if not isinstance(block, dict):
        return "block must be an object"
    if section not in sections:
        return f"section {section or '?'} does not exist in prd.md"
    if any(marker in sections[section] for marker in PENDING_MARKERS):
        return f"section {section} still contains pending input; resolve the feeding gap before composing narrative"
    paragraphs = block.get("paragraphs")
    if not isinstance(paragraphs, list) or not paragraphs:
        return "block must contain non-empty paragraphs"
    for paragraph in paragraphs:
        if not isinstance(paragraph, dict):
            return "paragraph must be an object"
        text = str(paragraph.get("text", "")).strip()
        citations = paragraph.get("citations")
        if not text:
            return "paragraph text is required"
        if any(marker in text for marker in PENDING_MARKERS):
            return "paragraph cannot narrate pending input"
        if not isinstance(citations, list) or not citations:
            return "paragraph citations must be a non-empty array"
        for citation in citations:
            quote = str(citation).strip()
            if not quote:
                return "empty citation"
            if quote not in evidence_text:
                return f"citation not found verbatim in source of truth: {quote}"
    return ""


def render_prd_compositions(project_id: str, prd_text: str) -> str:
    prd_text = strip_agent_compositions(prd_text)
    base = workspace_path(project_id)
    comp_dir = base / "03_specs" / "compositions"
    accepted_path = comp_dir / "accepted_blocks.json"
    blocks = read_json(accepted_path, [])
    if not isinstance(blocks, list) or not blocks:
        return prd_text
    evidence_text = composition_evidence_text(base)
    sections = prd_sections(prd_text)
    valid: list[dict[str, Any]] = []
    discarded: list[dict[str, str]] = []
    for block in blocks:
        section = str(block.get("section", "")).strip()
        reason = validate_block_shape(block, section, sections, evidence_text)
        if reason:
            discarded.append({"id": str(block.get("id", "?")), "section": section or "?", "reason": reason})
        else:
            valid.append(block)
    write_composition_regeneration_report(project_id, valid, discarded)
    if not valid:
        return prd_text
    by_section: dict[str, list[dict[str, Any]]] = {}
    for block in valid:
        by_section.setdefault(str(block["section"]), []).append(block)
    return insert_composition_blocks(prd_text, by_section)


def strip_agent_compositions(prd_text: str) -> str:
    lines = prd_text.splitlines()
    output: list[str] = []
    skipping = False
    for line in lines:
        if line == "### Agent Composition":
            skipping = True
            continue
        if skipping and line.startswith("## "):
            skipping = False
        if not skipping:
            output.append(line)
    return "\n".join(output).rstrip() + "\n"


def insert_composition_blocks(prd_text: str, by_section: dict[str, list[dict[str, Any]]]) -> str:
    lines = prd_text.splitlines()
    output: list[str] = []
    current_section = ""
    inserted: set[str] = set()
    for line in lines:
        match = PRD_SECTION_RE.match(line)
        if match:
            current_section = match.group(1)
        output.append(line)
        if match and current_section in by_section and current_section not in inserted:
            output.append("")
            output.append("### Agent Composition")
            output.append("")
            output.append("_Origin: agent. Validated by `/compose` against local source-of-truth citations._")
            output.append("")
            for block in by_section[current_section]:
                output.append(f"#### {block['id']}")
                output.append("")
                for paragraph in block["paragraphs"]:
                    citations = "; ".join(f"`{quote}`" for quote in paragraph["citations"])
                    output.append(f"{paragraph['text']} _Citations: {citations}_")
                    output.append("")
            inserted.add(current_section)
    return "\n".join(output).rstrip() + "\n"


def prd_sections(prd_text: str) -> dict[str, str]:
    matches = list(PRD_SECTION_RE.finditer(prd_text))
    sections: dict[str, str] = {}
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(prd_text)
        sections[match.group(1)] = prd_text[start:end]
    return sections


def composition_evidence_text(base: Path) -> str:
    roots = [
        base / "00_raw",
        base / "01_discovery",
        base / "02_requirements",
        base / "07_changes",
    ]
    parts: list[str] = []
    for root in roots:
        if not root.exists():
            continue
        for path in sorted(root.rglob("*")):
            if path.is_file() and path.suffix.lower() in {".md", ".txt", ".json"}:
                parts.append(path.read_text(encoding="utf-8", errors="ignore"))
    return "\n\n".join(parts)


def write_composition_report(project_id: str, accepted: list[dict[str, Any]], rejected: list[dict[str, str]], source: Path) -> Path:
    path = workspace_path(project_id) / "03_specs" / "compositions" / "composition_report.md"
    accepted_rows = "\n".join(f"| {block['id']} | {block['section']} | agent |" for block in accepted) or "| N/A | N/A | N/A |"
    rejected_rows = "\n".join(f"| {item['id']} | {item['section']} | {item['reason']} |" for item in rejected) or "| N/A | N/A | N/A |"
    path.write_text(
        f"""# PRD Composition Report - {project_id}

Source: `{source.as_posix()}`

## Accepted Blocks

| Block | PRD Section | Origin |
| --- | --- | --- |
{accepted_rows}

## Rejected Blocks

| Block | PRD Section | Reason |
| --- | --- | --- |
{rejected_rows}
""",
        encoding="utf-8",
    )
    return path


def write_composition_regeneration_report(project_id: str, valid: list[dict[str, Any]], discarded: list[dict[str, str]]) -> Path:
    path = workspace_path(project_id) / "03_specs" / "compositions" / "regeneration_report.md"
    valid_rows = "\n".join(f"| {block['id']} | {block['section']} | kept |" for block in valid) or "| N/A | N/A | N/A |"
    discarded_rows = "\n".join(f"| {item['id']} | {item['section']} | {item['reason']} |" for item in discarded) or "| N/A | N/A | N/A |"
    path.write_text(
        f"""# PRD Composition Regeneration Report - {project_id}

## Kept Blocks

| Block | PRD Section | Status |
| --- | --- | --- |
{valid_rows}

## Discarded Blocks

| Block | PRD Section | Reason |
| --- | --- | --- |
{discarded_rows}
""",
        encoding="utf-8",
    )
    return path


def unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    for index in range(2, 1000):
        candidate = path.with_name(f"{stem}-{index}{suffix}")
        if not candidate.exists():
            return candidate
    raise ComposeError(f"Could not allocate unique path for {path}")
