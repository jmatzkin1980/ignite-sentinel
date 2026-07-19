from __future__ import annotations

import html
import json
import re
import webbrowser
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .assumptions import load_assumptions
from .blocks import markdown_to_blocks, sections_from_blocks
from .discovery import expected_format_for_gap, parse_gap_rows, unblocks_for_gap, why_gap_matters
from .core.graph import load_graph
from .workspace import read_json, workspace_path


ARTIFACTS = {
    "gaps": {
        "label": "Discovery Gaps",
        "relative": "01_discovery/gaps.md",
        "phase": "Discovery",
    },
    "brief": {
        "label": "Project Brief",
        "relative": "02_requirements/project-brief.md",
        "phase": "Discovery",
    },
    "prd": {
        "label": "PRD",
        "relative": "03_specs/prd.md",
        "phase": "Specifications",
    },
    "specs": {
        "label": "Specs",
        "relative": "03_specs/specs.md",
        "phase": "Specifications",
    },
    "backlog": {
        "label": "Backlog",
        "relative": "04_backlog/BACKLOG.md",
        "fallback_relative": "04_backlog/EPIC-001.md",
        "phase": "Backlog",
    },
}

MARKER_RE = re.compile(r"\[(?:PENDING INPUT|PENDING DOMAIN CONTEXT|PENDING [^\]]+)\]|GAP-[A-Z0-9-]+|ASM-[A-Z0-9-]+|\bASSUMED\b")
CITATION_RE = re.compile(r"\[(?:Fuente|Source):[^\]]+\]|`(?:REQ|FR|JTBD|SPEC-U|US|AC|TC|KLU|DEC|CHG|RAW|GAP|ASM)-[^`]+`")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
ORDERED_LIST_RE = re.compile(r"^\d+\.\s+(.*)$")


def collect_artifact_model(project_id: str, artifact: str) -> dict[str, Any]:
    if artifact not in ARTIFACTS:
        raise ValueError(f"Unsupported artifact: {artifact}. Expected one of: {', '.join(sorted(ARTIFACTS))}.")
    base = workspace_path(project_id)
    config = ARTIFACTS[artifact]
    relative = str(config["relative"])
    path = base / relative
    if not path.exists() and config.get("fallback_relative"):
        relative = str(config["fallback_relative"])
        path = base / relative
    if not path.exists():
        raise FileNotFoundError(f"Artifact not found for /view: workspaces/{project_id}/{relative}")

    text = path.read_text(encoding="utf-8")
    block_model = markdown_to_blocks(text, artifact=artifact)
    sections = attach_section_html(sections_from_blocks(block_model))
    state = read_json(base / "state.json", {})
    language = str(state.get("project_language") or "auto")
    development_readiness = read_json(base / "01_discovery" / "development_readiness.json", {})
    marker_metadata = collect_marker_metadata(project_id, language, development_readiness)
    markers = enrich_markers(collect_markers(sections), marker_metadata)
    sections = attach_section_readiness(sections, markers, development_readiness)
    guided_response = collect_guided_response(markers)
    citations = collect_citations(project_id, sections)
    trace_nodes = trace_nodes_for_artifact(project_id, relative, artifact)
    trace_edges = trace_edges_for_citations(project_id, citations)
    section_summary = summarize_section_readiness(sections)
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    return {
        "project_id": project_id,
        "artifact": artifact,
        "label": config["label"],
        "phase": config["phase"],
        "language": language,
        "generated_at": generated_at,
        "source_path": f"workspaces/{project_id}/{relative}",
        "source_relative_path": relative,
        "source_line_count": len(text.splitlines()),
        "blocks": block_model,
        "sections": sections,
        "markers": markers,
        "guided_response": guided_response,
        "citations": citations,
        "trace": {
            "nodes": trace_nodes,
            "edges": trace_edges,
            "node_count": len(trace_nodes),
            "edge_count": len(trace_edges),
        },
        "readiness": {
            "summary": development_readiness.get("summary", {}),
            "section_summary": section_summary,
        },
        "summary": {
            "sections": len(sections),
            "sections_populated": section_summary["populated"],
            "sections_pending": section_summary["pending"],
            "sections_assumed": section_summary["assumed"],
            "markers": len(markers),
            "pending": sum(1 for marker in markers if marker["kind"] in {"pending", "gap"}),
            "assumed": sum(1 for marker in markers if marker["kind"] == "assumption"),
            "client_questions": guided_response["summary"]["client"],
            "citations": len(citations),
            "trace_nodes": len(trace_nodes),
            "trace_edges": len(trace_edges),
        },
    }


def attach_section_html(sections: list[dict[str, Any]]) -> list[dict[str, Any]]:
    for section in sections:
        section["html"] = markdown_to_html(section["markdown"])
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
                "id": "section-1",
                "level": 1,
                "title": "Document",
                "section_path": "Document",
                "line_start": 1 if lines else 0,
                "line_end": len(lines),
                "markdown": body,
                "html": markdown_to_html(body),
            }
        ]

    if heading_indexes[0] > 0:
        body = "\n".join(lines[: heading_indexes[0]])
        if body.strip():
            sections.append(
                {
                    "id": "section-1",
                    "level": 1,
                    "title": "Preamble",
                    "section_path": "Preamble",
                    "line_start": 1,
                    "line_end": heading_indexes[0],
                    "markdown": body,
                    "html": markdown_to_html(body),
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
        section_number = len(sections) + 1
        sections.append(
            {
                "id": f"section-{section_number}",
                "level": level,
                "title": title,
                "section_path": " > ".join(item[1] for item in stack),
                "line_start": start + 1,
                "line_end": end + 1,
                "markdown": body,
                "html": markdown_to_html(body),
            }
        )
    if sections and text.endswith("\n"):
        sections[-1]["markdown"] += "\n"
        sections[-1]["html"] = markdown_to_html(sections[-1]["markdown"])
    return sections


def collect_markers(sections: list[dict[str, Any]]) -> list[dict[str, Any]]:
    markers: list[dict[str, Any]] = []
    for section in sections:
        for match in MARKER_RE.finditer(section["markdown"]):
            marker = match.group(0)
            markers.append(
                {
                    "id": f"marker-{len(markers) + 1}",
                    "marker": marker,
                    "kind": marker_kind(marker),
                    "section_id": section["id"],
                    "section_path": section["section_path"],
                    "line_start": section["line_start"],
                }
            )
    return markers


def collect_marker_metadata(
    project_id: str,
    language: str,
    development_readiness: dict[str, Any] | None = None,
) -> dict[str, dict[str, Any]]:
    base = workspace_path(project_id)
    metadata: dict[str, dict[str, Any]] = {}
    gaps_path = base / "01_discovery" / "gaps.md"
    if gaps_path.exists():
        for row in parse_gap_rows(gaps_path.read_text(encoding="utf-8")):
            gap_id = row["id"]
            metadata[gap_id] = {
                "source": "gaps.md",
                "lens": row.get("lens", ""),
                "severity": row.get("severity", ""),
                "status": row.get("status", ""),
                "description": row.get("description", ""),
                "question": row.get("question", ""),
                "why": why_gap_matters(gap_id, language),
                "unblocks": unblocks_for_gap(gap_id, language),
                "expected_format": expected_format_for_gap(gap_id, language),
            }
    for row in load_assumptions(project_id):
        metadata[row["id"]] = {
            "source": "assumptions.md",
            "lens": row.get("lens", ""),
            "statement": row.get("statement", ""),
            "owner": row.get("owner", ""),
            "risk": row.get("risk", ""),
            "justification": row.get("justification", ""),
            "closes_gap": row.get("closes_gap", ""),
            "status": row.get("status", "ASSUMED"),
        }
    for marker_id, cells in readiness_cells_by_marker(development_readiness or {}).items():
        metadata.setdefault(marker_id, {})["readiness_cells"] = cells
    return metadata


def readiness_cells_by_marker(development_readiness: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    by_marker: dict[str, list[dict[str, Any]]] = {}
    for area in development_readiness.get("matrix", []):
        if not isinstance(area, dict):
            continue
        for cell in area.get("lenses", []):
            if not isinstance(cell, dict):
                continue
            marker_ids = {
                str(link.get("target", "")).strip()
                for link in cell.get("links", [])
                if isinstance(link, dict) and str(link.get("target", "")).startswith("GAP-")
            }
            evidence = cell.get("evidence", {})
            if isinstance(evidence, dict) and str(evidence.get("assumption_id", "")).startswith("ASM-"):
                marker_ids.add(str(evidence["assumption_id"]).strip())
            for marker_id in marker_ids:
                by_marker.setdefault(marker_id, []).append(
                    {
                        "area_id": area.get("area_id", ""),
                        "area": area.get("area", ""),
                        "lens": cell.get("lens", ""),
                        "status": cell.get("status", area.get("status", "")),
                        "score": cell.get("score", area.get("score", 0.0)),
                    }
                )
    return by_marker


def enrich_markers(markers: list[dict[str, Any]], metadata: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    for marker in markers:
        marker["metadata"] = metadata.get(marker["marker"], {})
    return markers


def collect_guided_response(markers: list[dict[str, Any]]) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    seen: set[str] = set()
    for marker in markers:
        marker_id = str(marker.get("marker", ""))
        if marker_id in seen:
            continue
        seen.add(marker_id)
        metadata = marker.get("metadata", {})
        audience = guided_audience_for_marker(marker)
        status = str(metadata.get("status", "")).upper()
        item = {
            "id": marker_id,
            "marker_id": marker.get("id", ""),
            "kind": marker.get("kind", ""),
            "audience": audience,
            "audience_label": guided_audience_label(audience),
            "response_needed": response_needed_for_guided_item(audience, status),
            "section_id": marker.get("section_id", ""),
            "section_path": marker.get("section_path", ""),
            "line_start": marker.get("line_start", ""),
            "lens": metadata.get("lens", ""),
            "severity": metadata.get("severity", ""),
            "status": metadata.get("status", ""),
            "question": metadata.get("question", ""),
            "expected_format": metadata.get("expected_format", ""),
            "owner": metadata.get("owner", ""),
            "risk": metadata.get("risk", ""),
            "statement": metadata.get("statement", ""),
        }
        items.append(item)
    summary = {
        "client": sum(1 for item in items if item["audience"] == "client" and item["response_needed"]),
        "domain": sum(1 for item in items if item["audience"] == "domain" and item["response_needed"]),
        "ba_assumption": sum(1 for item in items if item["audience"] == "ba_assumption"),
        "total": len(items),
    }
    return {"items": items, "summary": summary}


def guided_audience_for_marker(marker: dict[str, Any]) -> str:
    if marker.get("kind") == "assumption":
        return "ba_assumption"
    metadata = marker.get("metadata", {})
    lens = str(metadata.get("lens", "")).strip().lower()
    if lens in {"business", "product"}:
        return "client"
    if str(marker.get("marker", "")).startswith("GAP-"):
        return "domain"
    return "ba_assumption"


def guided_audience_label(audience: str) -> str:
    labels = {
        "client": "Client",
        "domain": "Domain",
        "ba_assumption": "BA / Assumption",
    }
    return labels.get(audience, "Review")


def response_needed_for_guided_item(audience: str, status: str) -> bool:
    if audience == "ba_assumption":
        return False
    return status not in {"CLOSED", "CONFIRMED", "NOT APPLICABLE"}


def attach_section_readiness(
    sections: list[dict[str, Any]],
    markers: list[dict[str, Any]],
    development_readiness: dict[str, Any],
) -> list[dict[str, Any]]:
    markers_by_section: dict[str, list[dict[str, Any]]] = {}
    for marker in markers:
        markers_by_section.setdefault(marker["section_id"], []).append(marker)
    for section in sections:
        section_markers = markers_by_section.get(section["id"], [])
        pending = sum(1 for marker in section_markers if marker["kind"] in {"pending", "gap"})
        assumed = sum(1 for marker in section_markers if marker["kind"] == "assumption")
        if pending:
            status = "pending"
        elif assumed:
            status = "assumed"
        else:
            status = "populated"
        section["readiness"] = {
            "status": status,
            "pending_markers": pending,
            "assumption_markers": assumed,
            "development_cells": sum(len(marker.get("metadata", {}).get("readiness_cells", [])) for marker in section_markers),
            "certainty_source": "development_readiness.json" if development_readiness else "artifact_markers",
        }
    return sections


def summarize_section_readiness(sections: list[dict[str, Any]]) -> dict[str, int]:
    summary = {"populated": 0, "pending": 0, "assumed": 0}
    for section in sections:
        status = section.get("readiness", {}).get("status", "populated")
        summary[status] = summary.get(status, 0) + 1
    return summary


def collect_citations(project_id: str, sections: list[dict[str, Any]]) -> list[dict[str, Any]]:
    citations: list[dict[str, Any]] = []
    graph = load_graph(project_id)
    node_lookup = {str(node.get("id", "")): node for node in graph.get("nodes", [])}
    for section in sections:
        for match in CITATION_RE.finditer(section["markdown"]):
            citation = match.group(0)
            trace_id = citation_trace_id(citation)
            trace_node = node_lookup.get(trace_id, {}) if trace_id else {}
            citations.append(
                {
                    "id": f"citation-{len(citations) + 1}",
                    "citation": citation,
                    "trace_id": trace_id,
                    "section_id": section["id"],
                    "section_path": section["section_path"],
                    "line_start": section["line_start"],
                    "trace_node": trace_node_summary(trace_node),
                    "source_fragment": source_fragment_for_node(project_id, trace_node),
                    "mini_graph": mini_graph_for_node(trace_id, graph),
                }
            )
    return citations


def citation_trace_id(citation: str) -> str:
    backtick = re.search(r"`([A-Z]+(?:-[A-Z]+)*-\d+)`", citation)
    if backtick:
        return backtick.group(1)
    source = re.search(r"\b((?:REQ|FR|JTBD|SPEC-U|US|AC|TC|KLU|DEC|CHG|RAW|GAP|ASM)-[A-Z0-9-]+)\b", citation)
    return source.group(1) if source else ""


def trace_node_summary(node: dict[str, Any]) -> dict[str, Any]:
    if not node:
        return {}
    return {
        "id": node.get("id", ""),
        "type": node.get("type", ""),
        "title": node.get("title", ""),
        "path": str(node.get("path", "")).replace("\\", "/"),
        "status": node.get("status", ""),
        "domain": node.get("domain", ""),
    }


def source_fragment_for_node(project_id: str, node: dict[str, Any], *, max_lines: int = 80) -> dict[str, Any]:
    if not node:
        return {}
    raw_path = str(node.get("path", "")).strip()
    if not raw_path:
        return {}
    base = workspace_path(project_id)
    candidates = [Path(raw_path)]
    if not Path(raw_path).is_absolute():
        candidates.append(base / raw_path)
    path = next((candidate for candidate in candidates if candidate.exists() and candidate.is_file()), None)
    if path is None:
        return {"path": raw_path.replace("\\", "/"), "available": False}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except UnicodeDecodeError:
        return {"path": raw_path.replace("\\", "/"), "available": False}
    end = min(len(lines), max_lines)
    return {
        "path": str(path.as_posix()),
        "available": True,
        "line_start": 1 if lines else 0,
        "line_end": end,
        "truncated": len(lines) > end,
        "text": "\n".join(lines[:end]),
    }


def mini_graph_for_node(trace_id: str, graph: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    if not trace_id:
        return {"nodes": [], "edges": []}
    node_lookup = {str(node.get("id", "")): node for node in graph.get("nodes", [])}
    related_ids = {trace_id}
    edges: list[dict[str, Any]] = []
    for edge in graph.get("edges", []):
        source = str(edge.get("from", ""))
        target = str(edge.get("to", ""))
        if source != trace_id and target != trace_id:
            continue
        related_ids.update({source, target})
        edges.append({"from": source, "to": target, "relation": edge.get("relation", "")})
    nodes = [trace_node_summary(node_lookup[node_id]) for node_id in sorted(related_ids) if node_id in node_lookup]
    return {"nodes": nodes, "edges": edges}


def trace_edges_for_citations(project_id: str, citations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    graph = load_graph(project_id)
    cited = {citation.get("trace_id") for citation in citations if citation.get("trace_id")}
    edges = []
    for edge in graph.get("edges", []):
        if edge.get("from") in cited or edge.get("to") in cited:
            edges.append({"from": edge.get("from"), "to": edge.get("to"), "relation": edge.get("relation")})
    return edges


def trace_nodes_for_artifact(project_id: str, relative_path: str, artifact: str) -> list[dict[str, Any]]:
    graph = load_graph(project_id)
    candidates: list[dict[str, Any]] = []
    normalized = relative_path.replace("\\", "/")
    artifact_type_aliases = {
        "gaps": {"gap_report"},
        "brief": {"project_brief"},
        "prd": {"prd"},
        "specs": {"specification", "spec_unit"},
        "backlog": {"epic", "user_story", "acceptance_criteria"},
    }.get(artifact, set())
    for node in graph.get("nodes", []):
        node_path = str(node.get("path", "")).replace("\\", "/")
        node_type = str(node.get("type", ""))
        if normalized in node_path or node_type in artifact_type_aliases:
            candidates.append(
                {
                    "id": node.get("id"),
                    "type": node_type,
                    "title": node.get("title"),
                    "path": node_path,
                    "status": node.get("status"),
                    "domain": node.get("domain"),
                }
            )
    return candidates


def marker_kind(marker: str) -> str:
    if marker.startswith("GAP-"):
        return "gap"
    if marker.startswith("ASM-") or marker == "ASSUMED":
        return "assumption"
    return "pending"


def render_artifact_html(model: dict[str, Any]) -> str:
    data_json = json.dumps(model, ensure_ascii=False).replace("</", "<\\/")
    return HTML_TEMPLATE.replace("__ARTIFACT_DATA__", data_json)


def generate_artifact_view(project_id: str, artifact: str, open_browser: bool = False) -> dict[str, Any]:
    model = collect_artifact_model(project_id, artifact)
    out_dir = workspace_path(project_id) / "08_context_packs" / "views"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{artifact}.html"
    out.write_text(render_artifact_html(model), encoding="utf-8")
    if open_browser:
        webbrowser.open(out.resolve().as_uri())
    return {
        "path": str(out),
        "artifact": artifact,
        "source_path": model["source_path"],
        "sections": model["summary"]["sections"],
        "markers": model["summary"]["markers"],
        "citations": model["summary"]["citations"],
        "trace_nodes": model["summary"]["trace_nodes"],
        "generated_at": model["generated_at"],
    }


def strip_inline_markdown(text: str) -> str:
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    return text.strip()


def markdown_to_html(markdown: str) -> str:
    lines = markdown.splitlines()
    out: list[str] = []
    list_type: str | None = None
    in_code = False
    code_lines: list[str] = []
    paragraph: list[str] = []

    def flush_paragraph() -> None:
        if paragraph:
            out.append("<p>" + inline_markdown(" ".join(paragraph)) + "</p>")
            paragraph.clear()

    def close_list() -> None:
        nonlocal list_type
        if list_type:
            out.append(f"</{list_type}>")
            list_type = None

    def open_list(kind: str) -> None:
        # Switch list container when the marker style changes so ordered items
        # render inside <ol> and bullets inside <ul> (F-VIEW-1: ordered lists
        # previously fell through to <p>, losing their numbering).
        nonlocal list_type
        if list_type != kind:
            close_list()
            out.append(f"<{kind}>")
            list_type = kind

    for line in lines:
        if line.startswith("```"):
            flush_paragraph()
            close_list()
            if in_code:
                out.append("<pre><code>" + html.escape("\n".join(code_lines)) + "</code></pre>")
                code_lines = []
                in_code = False
            else:
                in_code = True
            continue
        if in_code:
            code_lines.append(line)
            continue
        if not line.strip():
            flush_paragraph()
            close_list()
            continue
        heading = HEADING_RE.match(line)
        if heading:
            flush_paragraph()
            close_list()
            level = min(len(heading.group(1)), 6)
            out.append(f"<h{level}>{inline_markdown(heading.group(2))}</h{level}>")
            continue
        if line.startswith(("- ", "* ")):
            flush_paragraph()
            open_list("ul")
            out.append("<li>" + inline_markdown(line[2:].strip()) + "</li>")
            continue
        ordered = ORDERED_LIST_RE.match(line)
        if ordered:
            flush_paragraph()
            open_list("ol")
            out.append("<li>" + inline_markdown(ordered.group(1).strip()) + "</li>")
            continue
        paragraph.append(line.strip())
    flush_paragraph()
    close_list()
    if in_code:
        out.append("<pre><code>" + html.escape("\n".join(code_lines)) + "</code></pre>")
    return "\n".join(out)


def inline_markdown(text: str) -> str:
    escaped = html.escape(text)
    escaped = re.sub(r"`([^`]+)`", r"<code>\1</code>", escaped)
    escaped = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", escaped)
    escaped = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"<span class=\"linkish\">\1</span>", escaped)
    return escaped


HTML_TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Ignite Artifact View</title>
  <style>
    :root {
      color-scheme: light;
      --ink: #172026;
      --muted: #5b6871;
      --line: #d8dee4;
      --panel: #f7f9fb;
      --accent: #0f766e;
      --accent-2: #7c3aed;
      --warn: #b45309;
      --gap: #b91c1c;
      --ok: #1d4ed8;
      font-family: "Segoe UI", Arial, sans-serif;
    }
    * { box-sizing: border-box; }
    body { margin: 0; color: var(--ink); background: #ffffff; }
    header { padding: 22px 28px 18px; border-bottom: 1px solid var(--line); background: #f9fbfc; }
    .eyebrow { color: var(--accent); font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: .06em; }
    h1 { margin: 6px 0 8px; font-size: 28px; line-height: 1.15; letter-spacing: 0; }
    .meta { display: flex; flex-wrap: wrap; gap: 10px 18px; color: var(--muted); font-size: 13px; }
    .layout { display: grid; grid-template-columns: minmax(210px, 260px) minmax(0, 1fr) minmax(250px, 310px); min-height: calc(100vh - 94px); }
    nav, aside { position: sticky; top: 0; align-self: start; max-height: 100vh; overflow: auto; padding: 18px; background: var(--panel); border-right: 1px solid var(--line); }
    aside { border-right: 0; border-left: 1px solid var(--line); }
    main { min-width: 0; padding: 22px 30px 60px; }
    input[type="search"] { width: 100%; height: 34px; border: 1px solid var(--line); border-radius: 6px; padding: 0 10px; font: inherit; background: #fff; }
    .toc { margin-top: 16px; display: grid; gap: 4px; }
    .toc a { color: var(--ink); text-decoration: none; font-size: 13px; padding: 7px 8px; border-radius: 6px; border: 1px solid transparent; }
    .toc a:hover { border-color: var(--line); background: #fff; }
    .toc .level-2 { padding-left: 16px; }
    .toc .level-3, .toc .level-4, .toc .level-5, .toc .level-6 { padding-left: 24px; color: var(--muted); }
    .stats { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; margin: 16px 0; }
    .stat { border: 1px solid var(--line); border-radius: 8px; background: #fff; padding: 10px; }
    .stat strong { display: block; font-size: 21px; }
    .stat span { color: var(--muted); font-size: 12px; }
    section.artifact-section { padding: 14px 0 24px; border-bottom: 1px solid var(--line); scroll-margin-top: 16px; }
    section.artifact-section.hidden { display: none; }
    .section-meta { color: var(--muted); font-size: 12px; margin-bottom: 8px; }
    .content h1, .content h2, .content h3 { letter-spacing: 0; }
    .content h1 { font-size: 25px; }
    .content h2 { font-size: 21px; }
    .content h3 { font-size: 18px; }
    .content p, .content li { line-height: 1.55; }
    code { background: #eef2f6; padding: 1px 5px; border-radius: 4px; }
    pre { overflow: auto; background: #101820; color: #f4f7fa; border-radius: 8px; padding: 12px; }
    mark.marker { border-radius: 4px; padding: 1px 3px; }
    mark.pending { background: #fef3c7; color: #7c2d12; }
    mark.gap { background: #fee2e2; color: #7f1d1d; }
    mark.assumption { background: #ede9fe; color: #4c1d95; }
    mark.marker:target { outline: 2px solid var(--accent); outline-offset: 2px; }
    .badge { display: inline-flex; align-items: center; min-height: 22px; border-radius: 999px; padding: 2px 8px; font-size: 11px; font-weight: 700; text-transform: uppercase; }
    .badge.populated { background: #dcfce7; color: #14532d; }
    .badge.pending { background: #fef3c7; color: #7c2d12; }
    .badge.assumed { background: #ede9fe; color: #4c1d95; }
    .side-title { margin: 16px 0 8px; font-size: 13px; color: var(--muted); text-transform: uppercase; font-weight: 700; letter-spacing: .06em; }
    select { width: 100%; height: 34px; border: 1px solid var(--line); border-radius: 6px; padding: 0 8px; font: inherit; background: #fff; }
    .pill-list { display: grid; gap: 8px; }
    .pill { display: block; text-decoration: none; color: var(--ink); background: #fff; border: 1px solid var(--line); border-left: 4px solid var(--accent); border-radius: 8px; padding: 9px; font-size: 13px; }
    .pill.gap { border-left-color: var(--gap); }
    .pill.pending { border-left-color: var(--warn); }
    .pill.assumption { border-left-color: var(--accent-2); }
    .pill[hidden] { display: none; }
    .pill-meta { margin-top: 6px; color: var(--muted); display: grid; gap: 4px; }
    .pill-meta b { color: var(--ink); }
    .evidence-card { background: #fff; border: 1px solid var(--line); border-radius: 8px; padding: 9px; font-size: 13px; }
    .evidence-card summary { cursor: pointer; font-weight: 700; }
    .evidence-card summary span { color: var(--muted); font-weight: 400; }
    .mini-graph { margin-top: 8px; display: grid; gap: 5px; }
    .mini-node, .mini-edge { border: 1px solid var(--line); border-radius: 6px; padding: 6px; background: #fbfcfd; }
    .mini-edge { color: var(--muted); }
    .source-fragment { max-height: 220px; white-space: pre-wrap; overflow: auto; background: #101820; color: #f4f7fa; border-radius: 8px; padding: 10px; font-family: Consolas, monospace; font-size: 12px; }
    .empty { color: var(--muted); font-size: 13px; }
    button { font: inherit; }
    .source-toggle, .feedback-target, .feedback-action { margin-top: 10px; border: 1px solid var(--line); background: #fff; border-radius: 6px; padding: 7px 10px; cursor: pointer; }
    .feedback-target { margin-right: 6px; }
    .feedback-action.primary { background: var(--accent); color: #fff; border-color: var(--accent); }
    .markdown-source { display: none; white-space: pre-wrap; margin-top: 10px; border: 1px solid var(--line); border-radius: 8px; background: #fbfcfd; padding: 12px; font-family: Consolas, monospace; font-size: 12px; overflow: auto; }
    .markdown-source.open { display: block; }
    .feedback-panel { display: grid; gap: 8px; background: #fff; border: 1px solid var(--line); border-radius: 8px; padding: 9px; font-size: 13px; }
    .feedback-panel label { display: grid; gap: 4px; color: var(--muted); font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: .04em; }
    .feedback-panel input, .feedback-panel textarea { width: 100%; border: 1px solid var(--line); border-radius: 6px; padding: 8px; font: inherit; background: #fff; }
    .feedback-panel textarea { min-height: 88px; resize: vertical; }
    .feedback-target-note { color: var(--muted); font-size: 12px; }
    .feedback-list { display: grid; gap: 7px; }
    .feedback-item { border: 1px solid var(--line); border-radius: 6px; padding: 7px; background: #fbfcfd; }
    .feedback-export { display: none; max-height: 180px; white-space: pre-wrap; overflow: auto; border: 1px solid var(--line); border-radius: 6px; background: #101820; color: #f4f7fa; padding: 8px; font-family: Consolas, monospace; font-size: 11px; }
    .feedback-export.open { display: block; }
    .pill a { color: var(--ink); text-decoration: none; }
    .guided-panel { display: grid; gap: 8px; }
    .guided-progress { color: var(--muted); font-size: 12px; }
    .guided-item { background: #fff; border: 1px solid var(--line); border-left: 4px solid var(--ok); border-radius: 8px; padding: 9px; font-size: 13px; }
    .guided-item.domain { border-left-color: var(--warn); }
    .guided-item.ba_assumption { border-left-color: var(--accent-2); }
    .guided-item textarea { width: 100%; min-height: 70px; margin-top: 7px; border: 1px solid var(--line); border-radius: 6px; padding: 8px; font: inherit; resize: vertical; }
    .guided-item a { color: var(--ink); text-decoration: none; font-weight: 700; }
    @media (max-width: 960px) {
      .layout { grid-template-columns: 1fr; }
      nav, aside { position: static; max-height: none; border: 0; border-bottom: 1px solid var(--line); }
      main { padding: 18px; }
    }
  </style>
</head>
<body>
  <header>
    <div class="eyebrow" id="phase"></div>
    <h1 id="title"></h1>
    <div class="meta" id="meta"></div>
  </header>
  <div class="layout">
    <nav>
      <input id="search" type="search" placeholder="Search sections">
      <div class="stats" id="stats"></div>
      <div class="side-title">Sections</div>
      <div class="toc" id="toc"></div>
    </nav>
    <main id="content"></main>
    <aside>
      <div class="side-title">Pending And Assumptions</div>
      <select id="markerFilter" aria-label="Filter markers">
        <option value="all">All markers</option>
        <option value="gap">Gaps</option>
        <option value="pending">Pending input</option>
        <option value="assumption">Assumptions</option>
      </select>
      <div class="pill-list" id="markers"></div>
      <div class="side-title">Guided Response</div>
      <div class="guided-panel">
        <select id="guidedAudienceFilter" aria-label="Filter guided responses">
          <option value="client">Client questions</option>
          <option value="domain">Domain questions</option>
          <option value="ba_assumption">BA / assumptions</option>
          <option value="all">All guided items</option>
        </select>
        <div class="guided-progress" id="guidedProgress"></div>
        <div class="pill-list" id="guidedResponses"></div>
      </div>
      <div class="side-title">Feedback Loop</div>
      <div class="feedback-panel">
        <div class="feedback-target-note" id="feedbackTarget"></div>
        <label>Owner / source<input id="feedbackOwner" value="Artifact review comment"></label>
        <label>Decision status
          <select id="feedbackDecision">
            <option value="pending">pending</option>
            <option value="confirmed">confirmed</option>
            <option value="not applicable">not applicable</option>
          </select>
        </label>
        <textarea id="feedbackText" placeholder="Write a local anchored comment"></textarea>
        <button class="feedback-action primary" id="saveFeedback">Save Comment</button>
        <button class="feedback-action" id="exportFeedback">Export Markdown</button>
        <button class="feedback-action" id="mailFeedback">Draft Email To BA</button>
        <button class="feedback-action" id="clearFeedback">Clear Comments</button>
        <pre class="feedback-export" id="feedbackExportText"></pre>
        <div class="feedback-list" id="feedbackList"></div>
      </div>
      <div class="side-title">Evidence And Trace</div>
      <div class="pill-list" id="citations"></div>
    </aside>
  </div>
  <script>
    const model = __ARTIFACT_DATA__;
    const $ = (id) => document.getElementById(id);
    const feedbackKey = "ignite-sentinel:view-feedback:" + [model.project_id, model.artifact, model.source_relative_path].join(":");
    const guidedKey = "ignite-sentinel:view-guided-response:" + [model.project_id, model.artifact, model.source_relative_path].join(":");
    let feedbackComments = loadFeedback();
    let feedbackTarget = { type: "section", id: model.sections[0]?.id || "content" };
    let guidedAnswers = loadGuidedAnswers();
    $("phase").textContent = model.phase + " · read-only derived view";
    $("title").textContent = model.project_id + " · " + model.label;
    $("meta").innerHTML = [
      "Source: <code>" + escapeHtml(model.source_path) + "</code>",
      "Generated: " + escapeHtml(model.generated_at),
      "Language: " + escapeHtml(model.language)
    ].join("<span>·</span>");
    $("stats").innerHTML = Object.entries(model.summary).map(([k, v]) => `<div class="stat"><strong>${v}</strong><span>${label(k)}</span></div>`).join("");
    $("toc").innerHTML = model.sections.map(s => `<a class="level-${s.level}" href="#${s.id}">${escapeHtml(s.title)}</a>`).join("");
    $("content").innerHTML = model.sections.map(sectionHtml).join("");
    $("markers").innerHTML = model.markers.length ? model.markers.map(markerPill).join("") : `<div class="empty">No pending, gap, or assumption markers found.</div>`;
    const citationItems = [
      ...model.citations.map(evidenceCard),
      ...model.trace.nodes.map(n => `<a class="pill" href="#content"><strong>${escapeHtml(n.id || "")}</strong><br>${escapeHtml(n.type || "")} · ${escapeHtml(n.title || "")}</a>`)
    ];
    $("citations").innerHTML = citationItems.length ? citationItems.join("") : `<div class="empty">No citations or matching trace nodes found.</div>`;
    renderFeedbackTarget();
    renderFeedbackList();
    renderGuidedResponses();
    $("search").addEventListener("input", event => {
      const q = event.target.value.toLowerCase();
      document.querySelectorAll(".artifact-section").forEach(section => {
        section.classList.toggle("hidden", q && !section.textContent.toLowerCase().includes(q));
      });
    });
    $("markerFilter").addEventListener("change", event => {
      const value = event.target.value;
      document.querySelectorAll("#markers .pill").forEach(item => {
        item.hidden = value !== "all" && item.dataset.kind !== value;
      });
    });
    $("guidedAudienceFilter").addEventListener("change", renderGuidedResponses);
    document.addEventListener("input", event => {
      if (event.target.matches(".guided-answer")) {
        guidedAnswers[event.target.dataset.guidedId] = event.target.value;
        persistGuidedAnswers();
        renderGuidedProgress();
      }
    });
    document.addEventListener("click", event => {
      if (event.target.matches(".source-toggle")) {
        const target = document.getElementById(event.target.dataset.target);
        target.classList.toggle("open");
      }
      if (event.target.matches(".feedback-target")) {
        feedbackTarget = {
          type: event.target.dataset.targetType || "section",
          id: event.target.dataset.targetId || "content",
          marker: event.target.dataset.marker || "",
          gapId: event.target.dataset.gapId || "",
        };
        renderFeedbackTarget();
        $("feedbackText").focus();
      }
    });
    $("saveFeedback").addEventListener("click", saveFeedbackComment);
    $("exportFeedback").addEventListener("click", exportFeedbackMarkdown);
    $("mailFeedback").addEventListener("click", draftFeedbackEmail);
    $("clearFeedback").addEventListener("click", () => {
      feedbackComments = [];
      persistFeedback();
      renderFeedbackList();
      $("feedbackExportText").classList.remove("open");
    });

    function sectionHtml(s) {
      const readiness = s.readiness || { status: "populated" };
      return `<section class="artifact-section" id="${s.id}">
        <div class="section-meta">${escapeHtml(s.section_path)} · lines ${s.line_start}-${s.line_end} · <span class="badge ${escapeHtml(readiness.status)}">${escapeHtml(readiness.status)}</span></div>
        <div class="content">${highlightSection(s)}</div>
        <button class="feedback-target" data-target-type="section" data-target-id="${s.id}">Add feedback</button>
        <button class="source-toggle" data-target="src-${s.id}">Markdown source</button>
        <pre class="markdown-source" id="src-${s.id}">${escapeHtml(s.markdown)}</pre>
      </section>`;
    }
    function markerPill(item) {
      const gapId = item.marker.startsWith("GAP-") ? item.marker : "";
      return `<div class="pill ${item.kind}" data-kind="${item.kind}">
        <a href="#${item.id}"><strong>${escapeHtml(item.marker)}</strong><br>${escapeHtml(item.section_path || "")}</a>
        ${metadataHtml(item)}
        <button class="feedback-target" data-target-type="marker" data-target-id="${item.id}" data-marker="${escapeHtml(item.marker)}" data-gap-id="${escapeHtml(gapId)}">Add feedback</button>
      </div>`;
    }
    function pill(item, text, kind) {
      return `<a class="pill ${kind}" href="#${item.section_id || "content"}"><strong>${escapeHtml(text)}</strong><br>${escapeHtml(item.section_path || "")}</a>`;
    }
    function evidenceCard(item) {
      const node = item.trace_node || {};
      const fragment = item.source_fragment || {};
      const graph = item.mini_graph || { nodes: [], edges: [] };
      return `<details class="evidence-card" id="evidence-${item.id}">
        <summary>${escapeHtml(item.citation)} <span>${escapeHtml(node.type || "citation")} · ${escapeHtml(item.section_path || "")}</span></summary>
        <div class="pill-meta">
          ${node.id ? `<span><b>Trace node:</b> ${escapeHtml(node.id)} · ${escapeHtml(node.title || "")}</span>` : `<span><b>Trace node:</b> No matching graph node</span>`}
          ${node.path ? `<span><b>Path:</b> ${escapeHtml(node.path)}</span>` : ""}
          ${fragment.available ? `<span><b>Source Fragment:</b> lines ${fragment.line_start}-${fragment.line_end}${fragment.truncated ? " · truncated" : ""}</span><pre class="source-fragment">${escapeHtml(fragment.text)}</pre>` : `<span><b>Source Fragment:</b> not available in local graph path</span>`}
          ${miniGraphHtml(graph)}
        </div>
      </details>`;
    }
    function miniGraphHtml(graph) {
      const nodes = graph.nodes || [];
      const edges = graph.edges || [];
      if (!nodes.length && !edges.length) return `<span><b>Mini Trace:</b> no direct graph relations found.</span>`;
      return `<div class="mini-graph"><b>Mini Trace</b>
        ${nodes.map(n => `<div class="mini-node"><strong>${escapeHtml(n.id || "")}</strong><br>${escapeHtml(n.type || "")} · ${escapeHtml(n.title || "")}</div>`).join("")}
        ${edges.map(e => `<div class="mini-edge">${escapeHtml(e.from || "")} → ${escapeHtml(e.to || "")} · ${escapeHtml(e.relation || "")}</div>`).join("")}
      </div>`;
    }
    function metadataHtml(item) {
      const meta = item.metadata || {};
      const rows = [];
      if (meta.lens || meta.severity || meta.status) rows.push(`<span><b>Lens/status:</b> ${escapeHtml([meta.lens, meta.severity, meta.status].filter(Boolean).join(" · "))}</span>`);
      if (meta.why) rows.push(`<span><b>Why it matters:</b> ${escapeHtml(meta.why)}</span>`);
      if (meta.unblocks) rows.push(`<span><b>Unblocks:</b> ${escapeHtml(meta.unblocks)}</span>`);
      if (meta.expected_format) rows.push(`<span><b>Expected format:</b> ${escapeHtml(meta.expected_format)}</span>`);
      if (meta.owner || meta.risk) rows.push(`<span><b>Owner/risk:</b> ${escapeHtml([meta.owner, meta.risk].filter(Boolean).join(" · "))}</span>`);
      if (meta.statement) rows.push(`<span><b>Assumption:</b> ${escapeHtml(meta.statement)}</span>`);
      if (meta.closes_gap) rows.push(`<span><b>Closes gap:</b> ${escapeHtml(meta.closes_gap)}</span>`);
      if (meta.readiness_cells?.length) rows.push(`<span><b>Readiness:</b> ${escapeHtml(meta.readiness_cells.map(c => [c.area, c.lens, c.status].filter(Boolean).join(" / ")).join("; "))}</span>`);
      return rows.length ? `<span class="pill-meta">${rows.join("")}</span>` : "";
    }
    function highlightSection(section) {
      let value = section.html;
      model.markers.filter(m => m.section_id === section.id).forEach(marker => {
        const pattern = new RegExp(escapeRegExp(marker.marker));
        value = value.replace(pattern, `<mark id="${marker.id}" class="marker ${marker.kind}">${escapeHtml(marker.marker)}</mark>`);
      });
      return value;
    }
    function loadGuidedAnswers() {
      try {
        const value = JSON.parse(localStorage.getItem(guidedKey) || "{}");
        return value && typeof value === "object" && !Array.isArray(value) ? value : {};
      } catch {
        return {};
      }
    }
    function persistGuidedAnswers() {
      localStorage.setItem(guidedKey, JSON.stringify(guidedAnswers));
    }
    function renderGuidedResponses() {
      const filter = $("guidedAudienceFilter").value;
      const items = (model.guided_response?.items || []).filter(item => filter === "all" || item.audience === filter);
      $("guidedResponses").innerHTML = items.length
        ? items.map(guidedItemHtml).join("")
        : `<div class="empty">No guided items for this audience.</div>`;
      renderGuidedProgress();
    }
    function renderGuidedProgress() {
      const clientItems = (model.guided_response?.items || []).filter(item => item.audience === "client" && item.response_needed);
      const answered = clientItems.filter(item => String(guidedAnswers[item.id] || "").trim()).length;
      $("guidedProgress").textContent = `Client progress: ${answered}/${clientItems.length}`;
    }
    function guidedItemHtml(item) {
      const answer = guidedAnswers[item.id] || "";
      const details = [
        item.lens,
        item.severity,
        item.status,
        item.audience_label
      ].filter(Boolean).join(" · ");
      const prompt = item.question || item.statement || item.expected_format || item.id;
      const expected = item.expected_format ? `<span><b>Expected format:</b> ${escapeHtml(item.expected_format)}</span>` : "";
      const owner = item.owner || item.risk ? `<span><b>Owner/risk:</b> ${escapeHtml([item.owner, item.risk].filter(Boolean).join(" · "))}</span>` : "";
      const textarea = item.audience === "client" && item.response_needed
        ? `<textarea class="guided-answer" data-guided-id="${escapeHtml(item.id)}" placeholder="Draft local response">${escapeHtml(answer)}</textarea>`
        : "";
      return `<div class="guided-item ${escapeHtml(item.audience)}">
        <a href="#${escapeHtml(item.marker_id || item.section_id || "content")}">${escapeHtml(item.id)}</a>
        <div class="pill-meta">
          <span>${escapeHtml(details)}</span>
          <span>${escapeHtml(prompt)}</span>
          ${expected}
          ${owner}
        </div>
        ${textarea}
      </div>`;
    }
    function loadFeedback() {
      try {
        const value = JSON.parse(localStorage.getItem(feedbackKey) || "[]");
        return Array.isArray(value) ? value : [];
      } catch {
        return [];
      }
    }
    function persistFeedback() {
      localStorage.setItem(feedbackKey, JSON.stringify(feedbackComments));
    }
    function saveFeedbackComment() {
      const text = $("feedbackText").value.trim();
      if (!text) return;
      const section = sectionForTarget(feedbackTarget);
      const comment = {
        id: "FBC-" + Date.now(),
        target_type: feedbackTarget.type,
        target_id: feedbackTarget.id,
        marker: feedbackTarget.marker || "",
        gap_id: feedbackTarget.gapId || "",
        section_id: section?.id || "",
        section_path: section?.section_path || "",
        line_start: section?.line_start || "",
        line_end: section?.line_end || "",
        owner_source: $("feedbackOwner").value.trim() || "Artifact review comment",
        decision_status: $("feedbackDecision").value,
        text,
        created_at: new Date().toISOString()
      };
      feedbackComments.push(comment);
      persistFeedback();
      $("feedbackText").value = "";
      renderFeedbackList();
    }
    function renderFeedbackTarget() {
      const section = sectionForTarget(feedbackTarget);
      const marker = feedbackTarget.marker ? " / " + feedbackTarget.marker : "";
      $("feedbackTarget").textContent = "Target: " + feedbackTarget.type + " " + feedbackTarget.id + marker + (section ? " · " + section.section_path : "");
    }
    function renderFeedbackList() {
      $("feedbackList").innerHTML = feedbackComments.length
        ? feedbackComments.map(item => `<div class="feedback-item"><strong>${escapeHtml(item.target_type)} ${escapeHtml(item.marker || item.target_id)}</strong><br>${escapeHtml(item.text)}</div>`).join("")
        : `<div class="empty">No local comments saved.</div>`;
    }
    function exportFeedbackMarkdown() {
      const markdown = buildFeedbackExport(feedbackComments);
      $("feedbackExportText").textContent = markdown;
      $("feedbackExportText").classList.add("open");
      const blob = new Blob([markdown], { type: "text/markdown;charset=utf-8" });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `${model.project_id}-${model.artifact}-feedback.md`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    }
    function draftFeedbackEmail() {
      // IMP-211 (H10, H-JOSE-1): restore the mailto draft the approved prototype
      // had (it was lost in the runtime). Local-first: it only opens a pre-filled
      // draft in the user's own mail client, it never sends. mailto cannot carry
      // attachments, so remind the reviewer to attach the downloaded .md.
      const hasGuided = (model.guided_response?.items || []).some(item => String(guidedAnswers[item.id] || "").trim());
      if (!feedbackComments.length && !hasGuided) {
        alert("Save at least one comment or guided answer before drafting the email.");
        return;
      }
      const subject = `Artifact review feedback - ${model.project_id} - ${model.artifact}`;
      const body = buildFeedbackExport(feedbackComments) + "\n\n(If possible, also attach the downloaded .md file - mailto cannot include attachments.)";
      const recipient = model.ba_email || "";
      window.location.href = `mailto:${recipient}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;
    }
    function buildFeedbackExport(comments) {
      const lines = [
        `# Artifact Review Feedback Export - ${model.project_id}`,
        "",
        `- Source artifact: ${model.source_path}`,
        `- Generated at: ${new Date().toISOString()}`,
        `- Resolve gaps command: sentinel /resolve-gaps ${model.project_id} --source PATH`,
        `- Sync command: sentinel /sync ${model.project_id} --source PATH --note "Artifact review feedback"`,
        "",
      ];
      const guidedLines = buildGuidedResponseExport();
      if (!comments.length && !guidedLines.length) {
        lines.push("No local comments or guided responses were saved before export.", "");
        return lines.join("\n");
      }
      comments.forEach(comment => {
        const gapId = comment.gap_id || (String(comment.marker || "").startsWith("GAP-") ? comment.marker : "");
        const evidence = `${model.source_path}#${comment.target_id}${comment.line_start ? " lines " + comment.line_start + "-" + comment.line_end : ""}`;
        if (gapId) {
          lines.push(`### ${gapId}`);
          lines.push(`- Answer: ${singleLine(comment.text)}`);
          lines.push(`- Owner / source: ${singleLine(comment.owner_source || "Artifact review comment")}`);
          lines.push(`- Evidence or reference: ${singleLine(evidence)}`);
          lines.push(`- Decision status: ${singleLine(comment.decision_status || "pending")}`);
          lines.push("");
        } else {
          lines.push(`### Review Comment: ${comment.id}`);
          lines.push(`- Target: ${comment.target_type} \`${comment.target_id}\``);
          lines.push(`- Source artifact: \`${model.source_path}\``);
          if (comment.section_path) lines.push(`- Section: ${comment.section_path}`);
          lines.push(`- Comment: ${singleLine(comment.text)}`);
          lines.push(`- Suggested command: \`sentinel /sync ${model.project_id} --source PATH --note "Artifact review feedback"\``);
          lines.push("");
        }
      });
      if (guidedLines.length) {
        lines.push("## Guided Responses", "");
        guidedLines.forEach(line => lines.push(line));
      }
      return lines.join("\n");
    }
    function buildGuidedResponseExport() {
      // IMP-211 (H10, H-JOSE-1): the client's drafted guided answers used to
      // stay trapped in localStorage — the exported .md only carried
      // feedbackComments. Fold them in so the round-trip to /resolve-gaps works.
      const items = model.guided_response?.items || [];
      const out = [];
      items.forEach(item => {
        const answer = String(guidedAnswers[item.id] || "").trim();
        if (!answer) return;
        const prompt = item.question || item.statement || item.expected_format || item.id;
        if (String(item.id).startsWith("GAP-")) {
          out.push(`### ${item.id}`);
          out.push(`- Question: ${singleLine(prompt)}`);
          out.push(`- Answer: ${singleLine(answer)}`);
          out.push("- Owner / source: Client guided response");
          out.push("- Decision status: pending");
          out.push("");
        } else {
          out.push(`### Guided Response: ${item.id}`);
          out.push(`- Question: ${singleLine(prompt)}`);
          out.push(`- Answer: ${singleLine(answer)}`);
          out.push("");
        }
      });
      return out;
    }
    function sectionForTarget(target) {
      if (target.type === "section") return model.sections.find(section => section.id === target.id);
      const marker = model.markers.find(item => item.id === target.id);
      if (marker) return model.sections.find(section => section.id === marker.section_id);
      return model.sections[0];
    }
    function singleLine(value) {
      return String(value ?? "").replace(/\s+/g, " ").trim();
    }
    function escapeHtml(value) {
      return String(value ?? "").replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
    }
    function escapeRegExp(value) {
      return String(value).replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    }
    function label(key) {
      return key.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase());
    }
  </script>
</body>
</html>
"""
