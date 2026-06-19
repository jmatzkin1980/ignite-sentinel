from __future__ import annotations

import html
import json
import re
import webbrowser
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .traceability import load_graph
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
    sections = split_markdown_sections(text)
    markers = collect_markers(sections)
    citations = collect_citations(sections)
    trace_nodes = trace_nodes_for_artifact(project_id, relative, artifact)
    state = read_json(base / "state.json", {})
    language = str(state.get("project_language") or "auto")
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
        "sections": sections,
        "markers": markers,
        "citations": citations,
        "trace": {
            "nodes": trace_nodes,
            "node_count": len(trace_nodes),
        },
        "summary": {
            "sections": len(sections),
            "markers": len(markers),
            "citations": len(citations),
            "trace_nodes": len(trace_nodes),
        },
    }


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


def collect_citations(sections: list[dict[str, Any]]) -> list[dict[str, Any]]:
    citations: list[dict[str, Any]] = []
    for section in sections:
        for match in CITATION_RE.finditer(section["markdown"]):
            citation = match.group(0)
            citations.append(
                {
                    "id": f"citation-{len(citations) + 1}",
                    "citation": citation,
                    "section_id": section["id"],
                    "section_path": section["section_path"],
                    "line_start": section["line_start"],
                }
            )
    return citations


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
    in_list = False
    in_code = False
    code_lines: list[str] = []
    paragraph: list[str] = []

    def flush_paragraph() -> None:
        if paragraph:
            out.append("<p>" + inline_markdown(" ".join(paragraph)) + "</p>")
            paragraph.clear()

    def close_list() -> None:
        nonlocal in_list
        if in_list:
            out.append("</ul>")
            in_list = False

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
            if not in_list:
                out.append("<ul>")
                in_list = True
            out.append("<li>" + inline_markdown(line[2:].strip()) + "</li>")
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
    .side-title { margin: 16px 0 8px; font-size: 13px; color: var(--muted); text-transform: uppercase; font-weight: 700; letter-spacing: .06em; }
    .pill-list { display: grid; gap: 8px; }
    .pill { display: block; text-decoration: none; color: var(--ink); background: #fff; border: 1px solid var(--line); border-left: 4px solid var(--accent); border-radius: 8px; padding: 9px; font-size: 13px; }
    .pill.gap { border-left-color: var(--gap); }
    .pill.pending { border-left-color: var(--warn); }
    .pill.assumption { border-left-color: var(--accent-2); }
    .empty { color: var(--muted); font-size: 13px; }
    .source-toggle { margin-top: 10px; border: 1px solid var(--line); background: #fff; border-radius: 6px; padding: 7px 10px; cursor: pointer; }
    .markdown-source { display: none; white-space: pre-wrap; margin-top: 10px; border: 1px solid var(--line); border-radius: 8px; background: #fbfcfd; padding: 12px; font-family: Consolas, monospace; font-size: 12px; overflow: auto; }
    .markdown-source.open { display: block; }
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
      <div class="side-title">Pending Markers</div>
      <div class="pill-list" id="markers"></div>
      <div class="side-title">Evidence And Trace</div>
      <div class="pill-list" id="citations"></div>
    </aside>
  </div>
  <script>
    const model = __ARTIFACT_DATA__;
    const $ = (id) => document.getElementById(id);
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
    $("markers").innerHTML = model.markers.length ? model.markers.map(m => pill(m, m.marker, m.kind)).join("") : `<div class="empty">No pending, gap, or assumption markers found.</div>`;
    const citationItems = [
      ...model.citations.map(c => pill(c, c.citation, "citation")),
      ...model.trace.nodes.map(n => `<a class="pill" href="#content"><strong>${escapeHtml(n.id || "")}</strong><br>${escapeHtml(n.type || "")} · ${escapeHtml(n.title || "")}</a>`)
    ];
    $("citations").innerHTML = citationItems.length ? citationItems.join("") : `<div class="empty">No citations or matching trace nodes found.</div>`;
    $("search").addEventListener("input", event => {
      const q = event.target.value.toLowerCase();
      document.querySelectorAll(".artifact-section").forEach(section => {
        section.classList.toggle("hidden", q && !section.textContent.toLowerCase().includes(q));
      });
    });
    document.addEventListener("click", event => {
      if (event.target.matches(".source-toggle")) {
        const target = document.getElementById(event.target.dataset.target);
        target.classList.toggle("open");
      }
    });

    function sectionHtml(s) {
      return `<section class="artifact-section" id="${s.id}">
        <div class="section-meta">${escapeHtml(s.section_path)} · lines ${s.line_start}-${s.line_end}</div>
        <div class="content">${highlight(s.html)}</div>
        <button class="source-toggle" data-target="src-${s.id}">Markdown source</button>
        <pre class="markdown-source" id="src-${s.id}">${escapeHtml(s.markdown)}</pre>
      </section>`;
    }
    function pill(item, text, kind) {
      return `<a class="pill ${kind}" href="#${item.section_id || "content"}"><strong>${escapeHtml(text)}</strong><br>${escapeHtml(item.section_path || "")}</a>`;
    }
    function highlight(value) {
      return value
        .replace(/(\[PENDING INPUT\]|\[PENDING DOMAIN CONTEXT\]|\[PENDING [^\]]+\])/g, '<mark class="marker pending">$1</mark>')
        .replace(/(GAP-[A-Z0-9-]+)/g, '<mark class="marker gap">$1</mark>')
        .replace(/(ASM-[A-Z0-9-]+|\bASSUMED\b)/g, '<mark class="marker assumption">$1</mark>');
    }
    function escapeHtml(value) {
      return String(value ?? "").replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
    }
    function label(key) {
      return key.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase());
    }
  </script>
</body>
</html>
"""
