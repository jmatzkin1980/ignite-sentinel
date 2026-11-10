from __future__ import annotations

import html
import re
import sys
from pathlib import PurePosixPath, PureWindowsPath
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .assumptions import load_assumptions
from .core.local_browser import open_local_file
from .blocks import markdown_to_blocks, sections_from_blocks
from .discovery import expected_format_for_gap, parse_gap_rows, unblocks_for_gap, why_gap_matters
from .core.graph import load_graph
from .shell import content_fingerprint, fill, json_for_script, render_shell, template_text, theme_argument_for_display
from .themes import DEFAULT_THEME, ThemeError, legend_html, load_theme, user_theme_dirs
from .workspace import load_config, read_json, workspace_path
from .core.io import write_text
from .citations import is_v2_artifact
from .secrets_scan import assert_no_leaks


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
# IMP-254: a v2 artifact also cites with structured `[[doc § section # ID]]`.
V2_CITATION_RE = re.compile(r"\[\[[^\]\n]+\]\]|" + CITATION_RE.pattern)
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
ORDERED_LIST_RE = re.compile(r"^\d+\.\s+(.*)$")


def citation_pattern(text: str) -> re.Pattern[str]:
    return V2_CITATION_RE if is_v2_artifact(text) else CITATION_RE


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
    citations, graph_nodes, source_fragments = collect_citations(project_id, sections, citation_pattern(text))
    trace_nodes = trace_nodes_for_artifact(project_id, relative, artifact)
    trace_edges = trace_edges_for_citations(project_id, citations)
    section_summary = summarize_section_readiness(sections)
    for section in sections:
        section.pop("blocks", None)
        section["markdown"] = relativize_text(project_id, section["markdown"])
        section["html"] = relativize_text(project_id, section["html"])
    for fragment in source_fragments.values():
        if "text" in fragment:
            fragment["text"] = relativize_text(project_id, fragment["text"])
    return {
        "project_id": project_id,
        "artifact": artifact,
        "label": config["label"],
        "phase": config["phase"],
        "language": language,
        "provenance": {
            "cutoff": datetime.fromtimestamp(int(path.stat().st_mtime), timezone.utc).isoformat(),
            "source_sha256": content_fingerprint(path.read_bytes()),
        },
        "source_path": f"workspaces/{project_id}/{relative}",
        "source_relative_path": relative,
        "source_line_count": len(text.splitlines()),
        "sections": sections,
        "markers": markers,
        "guided_response": guided_response,
        "citations": citations,
        "graph_nodes": graph_nodes,
        "source_fragments": source_fragments,
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


def collect_citations(
    project_id: str, sections: list[dict[str, Any]], pattern: re.Pattern[str] = CITATION_RE
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    """Citations plus the shared tables they point into (IMP-240).

    Trace-node summaries and source fragments used to be copied into every
    citation (and every mini-graph); they now live once in ``graph_nodes`` and
    ``source_fragments`` keyed by node id, and each citation keeps only ids.
    """
    citations: list[dict[str, Any]] = []
    graph_nodes: dict[str, dict[str, Any]] = {}
    source_fragments: dict[str, dict[str, Any]] = {}
    graph = load_graph(project_id)
    node_lookup = {str(node.get("id", "")): node for node in graph.get("nodes", [])}
    for section in sections:
        for match in pattern.finditer(section["markdown"]):
            citation = match.group(0)
            trace_id = citation_trace_id(citation)
            trace_node = node_lookup.get(trace_id, {}) if trace_id else {}
            related = mini_graph_for_node(trace_id, graph)
            for node in related["nodes"]:
                graph_nodes.setdefault(node["id"], display_node(project_id, node))
            mini_graph = {"node_ids": [node["id"] for node in related["nodes"]], "edges": related["edges"]}
            if trace_node:
                graph_nodes.setdefault(trace_id, display_node(project_id, trace_node_summary(trace_node)))
                if trace_id not in source_fragments:
                    source_fragments[trace_id] = source_fragment_for_node(project_id, trace_node)
            citations.append(
                {
                    "id": f"citation-{len(citations) + 1}",
                    "citation": citation,
                    "trace_id": trace_id,
                    "section_id": section["id"],
                    "section_path": section["section_path"],
                    "line_start": section["line_start"],
                    "mini_graph": mini_graph,
                }
            )
    return citations, dict(sorted(graph_nodes.items())), dict(sorted(source_fragments.items()))


def display_path(project_id: str, raw_path: str) -> str:
    """A path safe to embed: never absolute, never machine-specific (IMP-240)."""
    text = str(raw_path or "").replace("\\", "/").strip()
    if not text:
        return ""
    posix_abs, windows_abs = PurePosixPath(text).is_absolute(), PureWindowsPath(text).is_absolute()
    if not (posix_abs or windows_abs):
        return text
    if not Path(text).is_absolute():
        # Absolute for the *other* OS (e.g. C:/... on Linux): never resolvable here,
        # and resolving it would glue it under cwd. Keep only the file name (IMP-246).
        return PureWindowsPath(text).name if windows_abs else PurePosixPath(text).name
    candidate = Path(text)
    root = workspace_path(project_id).resolve().parent.parent
    try:
        return candidate.resolve().relative_to(root).as_posix()
    except (ValueError, OSError):
        return candidate.name


def relativize_text(project_id: str, text: str) -> str:
    """Strip the machine-specific project root from embedded text (IMP-240 review).

    Generated artifacts can carry absolute anchors (e.g. backlog `Anchor: <root>/workspaces/...`).
    The governed Markdown is not touched; only the copy embedded in the page becomes relative.
    """
    workspace = workspace_path(project_id)
    roots = {workspace.resolve().parent.parent, workspace.absolute().parent.parent}
    forms = set()
    for root in roots:  # both spellings of the root (8.3 short names, junctions; IMP-246)
        forms |= {str(root), root.as_posix(), str(root).replace("\\", "/")}
    for form in sorted(forms, key=len, reverse=True):
        for sep in ("/", "\\"):
            text = text.replace(form + sep, "")
    return text


def display_node(project_id: str, node: dict[str, Any]) -> dict[str, Any]:
    return {**node, "path": display_path(project_id, node.get("path", ""))}


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
        return {"path": display_path(project_id, raw_path), "available": False}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except UnicodeDecodeError:
        return {"path": display_path(project_id, raw_path), "available": False}
    end = min(len(lines), max_lines)
    return {
        "path": display_path(project_id, str(path)),
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
                    "path": display_path(project_id, node_path),
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


class ViewModelError(ValueError):
    """The /view model is inconsistent; the HTML is not written."""


def validate_view_model(model: dict[str, Any]) -> list[str]:
    """Consistency checks before rendering (IMP-240): unique ids, resolvable refs, derived counts."""
    errors: list[str] = []
    sections = model.get("sections") or []
    markers = model.get("markers") or []
    citations = model.get("citations") or []
    for label, items in (("section", sections), ("marker", markers), ("citation", citations)):
        ids = [str(item.get("id")) for item in items]
        for item_id in sorted({value for value in ids if ids.count(value) > 1}):
            errors.append(f"duplicate {label} id {item_id!r}")
    graph_nodes = model.get("graph_nodes") or {}
    fragments = model.get("source_fragments") or {}
    for citation in citations:
        for node_id in (citation.get("mini_graph") or {}).get("node_ids", []):
            if node_id not in graph_nodes:
                errors.append(f"{citation.get('id')}: mini-graph node {node_id!r} is not in graph_nodes")
        trace_id = citation.get("trace_id")
        if trace_id and trace_id in graph_nodes and trace_id not in fragments:
            errors.append(f"{citation.get('id')}: no source fragment entry for {trace_id!r}")
    summary = model.get("summary") or {}
    for key, actual in (("sections", len(sections)), ("markers", len(markers)), ("citations", len(citations))):
        if summary.get(key) != actual:
            errors.append(f"summary.{key} is {summary.get(key)!r}, the model has {actual}")
    provenance = model.get("provenance")
    if not isinstance(provenance, dict) or not provenance.get("cutoff") or not provenance.get("source_sha256"):
        errors.append("provenance with cutoff and source_sha256 is required")
    return errors


def render_artifact_view(model: dict[str, Any], theme: dict[str, Any], *, theme_arg: str | None = None) -> str:
    """Validate, then render the artifact inside the common shell (IMP-240).

    Deterministic for a given model and theme: no clock, no absolute paths.
    """
    errors = validate_view_model(model)
    if errors:
        raise ViewModelError("view model is inconsistent: " + "; ".join(errors))
    language = "es" if str(model.get("language", "")).lower().startswith("es") else "en"
    content = (
        fill("view-page.html", data_json=json_for_script(model))
        + _legend_section(theme, language)
        + _provenance_section(model, theme_arg or str(theme.get("name") or DEFAULT_THEME))
    )
    return render_shell(
        theme=theme,
        title=f"{model['project_id']} · {model['label']} — Ignite Artifact View",
        heading=str(model["label"]),
        nav=template_text("view-nav.html"),
        content=content,
        page_css=template_text("view.css"),
        page_js=template_text("view.js"),
        language=language,
    )


def render_artifact_html(model: dict[str, Any]) -> str:
    """Backward-compatible entry point: render with the built-in neutral theme."""
    return render_artifact_view(model, load_theme())


def _legend_section(theme: dict[str, Any], language: str) -> str:
    title = "Leyenda de colores" if language == "es" else "Colour legend"
    return f'<section class="view-section" id="legend"><h2>{title}</h2>{legend_html(theme, language)}</section>'


def _provenance_section(model: dict[str, Any], theme_arg: str) -> str:
    provenance = model["provenance"]
    command = html.escape(
        f"python -m sentinel /view {model['project_id']} --artifact {model['artifact']} --theme {theme_argument_for_display(theme_arg)}"
    )
    heading = "Procedencia" if str(model.get("language", "")).lower().startswith("es") else "Provenance"
    return (
        f'<section class="view-section" id="provenance"><h2>{heading}</h2>'
        f"<p>Source: <code>{html.escape(model['source_path'])}</code> · sha256 <code>{html.escape(provenance['source_sha256'])}</code> · "
        f'cut-off <time datetime="{html.escape(provenance["cutoff"])}">{html.escape(provenance["cutoff"])}</time> '
        "(the source file's modification time, not the build time).</p>"
        f"<p>Regenerate: <code>{command}</code></p></section>"
    )


def resolve_view_theme(project_id: str, theme: str | Path | None) -> tuple[dict[str, Any], str | None, str | None]:
    """Theme priority for /view: --theme > workspace config `theme:` > neutral (IMP-238 spec).

    An explicit --theme that fails is a hard error. A configured theme that fails falls back
    to neutral with a warning, so one bad config line never breaks /view for the whole team.
    Returns (theme, theme_arg, warning).
    """
    dirs = user_theme_dirs(workspace_path(project_id))
    if theme:
        return load_theme(theme, search_dirs=dirs), str(theme), None
    configured = _clean_config_scalar(load_config(project_id).get("theme"))
    if not configured:
        return load_theme(), None, None
    candidates = [configured]
    if not (PurePosixPath(configured).is_absolute() or PureWindowsPath(configured).is_absolute()) and any(ch in configured for ch in "/\\"):
        candidates.insert(0, str(workspace_path(project_id) / configured))
    errors = []
    for candidate in candidates:
        try:
            return load_theme(candidate, search_dirs=dirs), configured, None
        except ThemeError as exc:
            errors.append(str(exc))
    return load_theme(), None, f"workspace config theme {configured!r} could not be loaded ({errors[-1]}); using {DEFAULT_THEME}"


def _clean_config_scalar(value: object) -> str:
    """`theme: "x"  # note` -> `x` (the simple YAML reader keeps quotes and inline comments)."""
    text = str(value or "").strip()
    if " #" in text:
        text = text.split(" #", 1)[0].strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "\"'":
        text = text[1:-1].strip()
    return text


def generate_artifact_view(project_id: str, artifact: str, open_browser: bool = False, theme: str | Path | None = None) -> dict[str, Any]:
    if artifact == "readiness":  # IMP-247: not a Markdown artifact; its own model
        from .readiness_view import generate_readiness_view

        return generate_readiness_view(project_id, open_browser=open_browser, theme=theme)
    loaded, theme_arg, theme_warning = resolve_view_theme(project_id, theme)
    if theme_warning:
        print(f"sentinel warning: {theme_warning}", file=sys.stderr)
    model = collect_artifact_model(project_id, artifact)
    rendered = render_artifact_view(model, loaded, theme_arg=theme_arg)
    out_dir = workspace_path(project_id) / "08_context_packs" / "views"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{artifact}.html"
    assert_no_leaks(project_id, rendered, workspace_path(project_id), f"/view {artifact}")
    write_text(out, rendered, newline="\n")
    if open_browser:
        open_local_file(out)
    return {
        "path": str(out),
        "artifact": artifact,
        "source_path": model["source_path"],
        "sections": model["summary"]["sections"],
        "markers": model["summary"]["markers"],
        "citations": model["summary"]["citations"],
        "trace_nodes": model["summary"]["trace_nodes"],
        "cutoff": model["provenance"]["cutoff"],
        "source_sha256": model["provenance"]["source_sha256"],
        "theme": loaded["name"],
        **({"theme_warning": theme_warning} if theme_warning else {}),
    }


def strip_inline_markdown(text: str) -> str:
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    return text.strip()


def markdown_to_html(markdown: str) -> str:
    lines = markdown.splitlines()
    out: list[str] = []
    # F-VIEW-2: nested lists. Each open list is a level [indent, kind, li_index,
    # has_child]; ``li_index`` is where the level's current <li> lives in ``out``
    # so a leaf can be closed inline (byte-identical to the old single-level
    # render) while a parent that gained a nested list closes on its own line.
    list_stack: list[list] = []
    in_code = False
    code_lines: list[str] = []
    paragraph: list[str] = []

    def flush_paragraph() -> None:
        if paragraph:
            out.append("<p>" + inline_markdown(" ".join(paragraph)) + "</p>")
            paragraph.clear()

    def close_li(level: list) -> None:
        # A leaf li keeps its close inline (<li>x</li> on one line, matching the
        # pre-nesting output); a parent whose nested list already closed above
        # gets its </li> on a fresh line so the markup stays well-formed.
        if level[3]:
            out.append("</li>")
        else:
            out[level[2]] += "</li>"

    def close_level(level: list) -> None:
        close_li(level)
        out.append(f"</{level[1]}>")

    def close_list() -> None:
        while list_stack:
            close_level(list_stack.pop())

    def emit_item(indent: int, kind: str, content: str) -> None:
        # Dedent: close every list deeper than this item.
        while list_stack and indent < list_stack[-1][0]:
            close_level(list_stack.pop())
        if not list_stack or indent > list_stack[-1][0]:
            # Deeper (or first) list: it nests inside the parent's still-open li.
            if list_stack:
                list_stack[-1][3] = True
            out.append(f"<{kind}>")
            list_stack.append([indent, kind, -1, False])
        else:
            # Same level: close the previous sibling, switching the container
            # when the marker style changes (bullets -> <ul>, numbers -> <ol>).
            close_li(list_stack[-1])
            if kind != list_stack[-1][1]:
                out.append(f"</{list_stack[-1][1]}>")
                out.append(f"<{kind}>")
                list_stack[-1][1] = kind
        out.append("<li>" + inline_markdown(content))
        list_stack[-1][2] = len(out) - 1
        list_stack[-1][3] = False

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
        stripped = line.lstrip(" ")
        indent = len(line) - len(stripped)
        if stripped.startswith(("- ", "* ")):
            flush_paragraph()
            emit_item(indent, "ul", stripped[2:].strip())
            continue
        ordered = ORDERED_LIST_RE.match(stripped)
        if ordered:
            flush_paragraph()
            emit_item(indent, "ol", ordered.group(1).strip())
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
    escaped = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<span class="linkish">\1</span>', escaped)
    return wrap_provenance(escaped)


PROVENANCE_HTML_RE = re.compile(r"_\((?:<code>[^<]*</code>|[^<()])*\)_|\[(?:Fuente|Source):[^\]<]+\]")


def wrap_provenance(rendered: str) -> str:
    """IMP-240 reader edition: inline provenance becomes toggleable, never removed."""
    return PROVENANCE_HTML_RE.sub(lambda m: f'<span class="prov">{m.group(0)}</span>', rendered)
