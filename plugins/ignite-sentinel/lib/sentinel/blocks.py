from __future__ import annotations

import hashlib
import re
from typing import Any


BLOCK_CATALOG = (
    "section",
    "requirement-table",
    "persona",
    "ears-statement",
    "decision",
    "traceability",
    "pending",
    "assumption",
)

HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
TABLE_SEPARATOR_RE = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$")
EARS_RE = re.compile(r"\b(when|while|where|if|then|shall|cuando|mientras|donde|si|entonces|deber)\b", re.IGNORECASE)


def markdown_to_blocks(text: str, *, artifact: str = "") -> dict[str, Any]:
    """Build the derived artifact block model used between Markdown and views.

    The Markdown remains the source of truth. Every block preserves its exact
    source slice so `blocks_to_markdown(markdown_to_blocks(text)) == text`.
    """

    sections = split_markdown_sections(text)
    blocks = []
    for index, section in enumerate(sections, start=1):
        section_id = f"block-{index:03d}"
        blocks.append(
            {
                "id": section_id,
                "type": "section",
                "level": section["level"],
                "title": section["title"],
                "section_path": section["section_path"],
                "line_start": section["line_start"],
                "line_end": section["line_end"],
                "markdown": section["markdown"],
                "children": content_blocks(section["markdown"], section["line_start"], section_id),
            }
        )
    return {
        "version": 1,
        "artifact": artifact,
        "catalog": list(BLOCK_CATALOG),
        "source_line_count": len(text.splitlines()),
        "source_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "roundtrip": {
            "idempotent": blocks_to_markdown({"blocks": blocks}) == text,
            "mode": "lossless-markdown-slices",
        },
        "blocks": blocks,
    }


def blocks_to_markdown(model_or_blocks: dict[str, Any] | list[dict[str, Any]]) -> str:
    blocks = model_or_blocks.get("blocks", []) if isinstance(model_or_blocks, dict) else model_or_blocks
    if not isinstance(blocks, list):
        return ""
    return "\n".join(str(block.get("markdown", "")) for block in blocks if isinstance(block, dict))


def sections_from_blocks(block_model: dict[str, Any]) -> list[dict[str, Any]]:
    sections = []
    for index, block in enumerate(block_model.get("blocks", []), start=1):
        if not isinstance(block, dict):
            continue
        markdown = str(block.get("markdown", ""))
        sections.append(
            {
                "id": f"section-{index}",
                "block_id": block.get("id", f"block-{index:03d}"),
                "block_type": block.get("type", "section"),
                "level": int(block.get("level") or 1),
                "title": str(block.get("title") or "Document"),
                "section_path": str(block.get("section_path") or block.get("title") or "Document"),
                "line_start": int(block.get("line_start") or 0),
                "line_end": int(block.get("line_end") or 0),
                "markdown": markdown,
                "blocks": block.get("children", []),
            }
        )
    return sections


def split_markdown_sections(text: str) -> list[dict[str, Any]]:
    lines = text.splitlines()
    heading_indexes = [idx for idx, line in enumerate(lines) if HEADING_RE.match(line)]
    sections: list[dict[str, Any]] = []
    if not heading_indexes:
        body = "\n".join(lines)
        if text.endswith("\n"):
            body += "\n"
        return [
            {
                "level": 1,
                "title": "Document",
                "section_path": "Document",
                "line_start": 1 if lines else 0,
                "line_end": len(lines),
                "markdown": body,
            }
        ]

    if heading_indexes[0] > 0:
        body = "\n".join(lines[: heading_indexes[0]])
        if body.strip():
            sections.append(
                {
                    "level": 1,
                    "title": "Preamble",
                    "section_path": "Preamble",
                    "line_start": 1,
                    "line_end": heading_indexes[0],
                    "markdown": body,
                }
            )

    stack: list[tuple[int, str]] = []
    for position, start in enumerate(heading_indexes):
        end = heading_indexes[position + 1] - 1 if position + 1 < len(heading_indexes) else len(lines) - 1
        match = HEADING_RE.match(lines[start])
        if not match:
            continue
        level = len(match.group(1))
        title = strip_inline_markdown(match.group(2))
        while stack and stack[-1][0] >= level:
            stack.pop()
        stack.append((level, title))
        body = "\n".join(lines[start : end + 1])
        sections.append(
            {
                "level": level,
                "title": title,
                "section_path": " > ".join(item[1] for item in stack),
                "line_start": start + 1,
                "line_end": end + 1,
                "markdown": body,
            }
        )
    if sections and text.endswith("\n"):
        sections[-1]["markdown"] += "\n"
    return sections


def content_blocks(markdown: str, section_line_start: int, section_block_id: str) -> list[dict[str, Any]]:
    lines = markdown.splitlines()
    chunks: list[tuple[int, int, list[str]]] = []
    start: int | None = None
    current: list[str] = []
    in_code = False
    for idx, line in enumerate(lines):
        if line.startswith("```"):
            in_code = not in_code
        if not in_code and not line.strip():
            if current:
                chunks.append((start if start is not None else idx, idx - 1, current))
                current = []
                start = None
            continue
        if start is None:
            start = idx
        current.append(line)
    if current:
        chunks.append((start if start is not None else 0, len(lines) - 1, current))

    blocks = []
    for index, (start_idx, end_idx, chunk_lines) in enumerate(chunks, start=1):
        chunk = "\n".join(chunk_lines)
        blocks.append(
            {
                "id": f"{section_block_id}.{index:03d}",
                "type": classify_block(chunk),
                "line_start": section_line_start + start_idx,
                "line_end": section_line_start + end_idx,
                "markdown": chunk,
            }
        )
    return blocks


def classify_block(markdown: str) -> str:
    lowered = markdown.lower()
    if "[pending input]" in lowered or "[pending domain context]" in lowered or re.search(r"\[pending [^\]]+\]", lowered):
        return "pending"
    if "asm-" in lowered or "assumed" in lowered:
        return "assumption"
    if "decision" in lowered or re.search(r"\bdec-[a-z0-9-]+\b", lowered):
        return "decision"
    if is_markdown_table(markdown):
        return "requirement-table"
    if "trace" in lowered or re.search(r"\b(req|fr|jtbd|spec-u|us|ac|tc|klu|chg|raw|gap)-[a-z0-9-]+\b", lowered):
        return "traceability"
    if "persona" in lowered or "user:" in lowered or "usuario:" in lowered:
        return "persona"
    if EARS_RE.search(markdown):
        return "ears-statement"
    return "section"


def is_markdown_table(markdown: str) -> bool:
    lines = [line for line in markdown.splitlines() if line.strip()]
    return len(lines) >= 2 and "|" in lines[0] and any(TABLE_SEPARATOR_RE.match(line) for line in lines[1:3])


def strip_inline_markdown(text: str) -> str:
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    return text.strip()
