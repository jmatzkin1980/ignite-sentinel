from __future__ import annotations

import math
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .workspace import graph_path, memory_path, read_json, write_json, workspace_path


TOKEN_RE = re.compile(r"\w+", re.UNICODE)


def tokenize(text: str) -> list[str]:
    return [token.lower() for token in TOKEN_RE.findall(text)]


def text_vector(text: str) -> Counter[str]:
    return Counter(tokenize(text))


def cosine(a: Counter[str], b: Counter[str]) -> float:
    if not a or not b:
        return 0.0
    dot = sum(a[token] * b.get(token, 0) for token in a)
    norm_a = math.sqrt(sum(value * value for value in a.values()))
    norm_b = math.sqrt(sum(value * value for value in b.values()))
    return dot / (norm_a * norm_b) if norm_a and norm_b else 0.0


class ContextBroker:
    """Local-first retrieval broker. Uses a JSON hybrid fallback even when LanceDB is absent."""

    def __init__(self, project_id: str):
        self.project_id = project_id
        self.path = memory_path(project_id)
        self.data = read_json(self.path, {"chunks": [], "artifacts": [], "trace_edges": []})
        self.backend = "json-hybrid"

    def index_artifact(
        self,
        artifact_id: str,
        artifact_type: str,
        source_path: Path,
        text: str,
        domain: str = "product",
        trace_ids: list[str] | None = None,
    ) -> None:
        trace_ids = trace_ids or [artifact_id]
        artifact = {
            "project_id": self.project_id,
            "artifact_id": artifact_id,
            "artifact_type": artifact_type,
            "source_path": str(source_path.as_posix()),
            "domain": domain,
            "trace_ids": trace_ids,
            "indexed_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        }
        self.data["artifacts"] = [
            current for current in self.data["artifacts"] if current["artifact_id"] != artifact_id
        ]
        self.data["artifacts"].append(artifact)
        self.data["chunks"] = [
            chunk for chunk in self.data["chunks"] if chunk["artifact_id"] != artifact_id
        ]
        for index, chunk_text in enumerate(chunk_texts(text)):
            self.data["chunks"].append(
                {
                    **artifact,
                    "chunk_id": f"{artifact_id}::chunk-{index + 1:03d}",
                    "text": chunk_text,
                    "summary": chunk_text[:180],
                    "status": "active",
                }
            )
        write_json(self.path, self.data)

    def index_trace_edges(self, edges: list[dict[str, Any]]) -> None:
        self.data["trace_edges"] = edges
        write_json(self.path, self.data)

    def retrieve(
        self,
        query: str,
        workflow: str,
        limit: int = 5,
        artifact_type: str | None = None,
        domain: str | None = None,
        trace_id: str | None = None,
    ) -> list[dict[str, Any]]:
        query_tokens = set(tokenize(query))
        query_vector = text_vector(query)
        scored = []
        for chunk in self.data.get("chunks", []):
            if artifact_type and chunk.get("artifact_type") != artifact_type:
                continue
            if domain and chunk.get("domain") != domain:
                continue
            if trace_id and trace_id not in chunk.get("trace_ids", []):
                continue
            text = chunk["text"]
            lexical = len(query_tokens.intersection(tokenize(text))) / max(len(query_tokens), 1)
            semantic = cosine(query_vector, text_vector(text))
            workflow_boost = 0.05 if workflow.lower() in text.lower() else 0.0
            score = lexical + semantic + workflow_boost
            if score > 0:
                scored.append({"score": round(score, 4), **chunk})
        return sorted(scored, key=lambda row: row["score"], reverse=True)[:limit]

    def build_context_pack(
        self,
        query: str,
        workflow: str,
        limit: int = 5,
        artifact_type: str | None = None,
        domain: str | None = None,
        trace_id: str | None = None,
    ) -> dict[str, Any]:
        results = self.retrieve(query, workflow, limit, artifact_type, domain, trace_id)
        pack = {
            "project_id": self.project_id,
            "workflow": workflow,
            "query": query,
            "backend": self.backend,
            "filters": {
                "artifact_type": artifact_type,
                "domain": domain,
                "trace_id": trace_id,
            },
            "results": results,
        }
        safe_workflow = re.sub(r"[^A-Za-z0-9_-]+", "-", workflow).strip("-") or "context"
        pack_path = workspace_path(self.project_id) / "08_context_packs" / f"{safe_workflow}.json"
        write_json(pack_path, pack)
        pack["path"] = str(pack_path.as_posix())
        return pack


def reindex_workspace(project_id: str) -> dict[str, Any]:
    graph = read_json(graph_path(project_id), {"nodes": [], "edges": []})
    broker = ContextBroker(project_id)
    indexed = []
    for node in graph.get("nodes", []):
        path_value = node.get("path")
        if not path_value:
            continue
        path = Path(path_value)
        if not path.is_absolute():
            path = Path.cwd() / path
        if not path.exists() or path.suffix.lower() != ".md":
            continue
        broker.index_artifact(
            node["id"],
            node.get("type", "artifact"),
            path,
            path.read_text(encoding="utf-8"),
            domain=node.get("domain", "product"),
            trace_ids=[node["id"]],
        )
        indexed.append(node["id"])
    broker.index_trace_edges(graph.get("edges", []))
    return {"project_id": project_id, "indexed": indexed, "count": len(indexed)}


def chunk_texts(text: str, max_chars: int = 900) -> list[str]:
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs or [text]:
        if len(current) + len(paragraph) + 2 > max_chars and current:
            chunks.append(current)
            current = paragraph
        else:
            current = f"{current}\n\n{paragraph}".strip()
    if current:
        chunks.append(current)
    return chunks
