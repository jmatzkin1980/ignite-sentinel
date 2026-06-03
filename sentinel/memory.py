from __future__ import annotations

import math
import re
from hashlib import blake2b
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .workspace import graph_path, memory_path, read_json, write_json, workspace_path


TOKEN_RE = re.compile(r"\w+", re.UNICODE)
VECTOR_DIMENSIONS = 128
CONTEXT_FOLDERS = {
    "00_raw/00_client_requirement": ("raw_context", "product"),
    "00_raw/01_business_context": ("business_context", "business"),
    "00_raw/02_technology_context": ("technology_context", "technical"),
    "00_raw/03_design_context": ("design_context", "design"),
    "00_raw/04_quality_context": ("quality_context", "quality"),
    "00_raw/05_interactions": ("interaction_context", "product"),
    "07_changes": ("change_context", "product"),
}


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


def hash_embedding(text: str, dimensions: int = VECTOR_DIMENSIONS) -> list[float]:
    """Small deterministic local embedding used when no model service is configured."""
    vector = [0.0] * dimensions
    for token in tokenize(text):
        bucket = int.from_bytes(blake2b(token.encode("utf-8"), digest_size=4).digest(), "big") % dimensions
        vector[bucket] += 1.0
    norm = math.sqrt(sum(value * value for value in vector))
    if not norm:
        return vector
    return [round(value / norm, 6) for value in vector]


class ContextBroker:
    """Local-first retrieval broker backed by LanceDB when available.

    Versionable workspace artifacts remain the source of truth. The vector store
    is a retrieval aid and can be rebuilt from the graph and context folders.
    """

    def __init__(self, project_id: str):
        self.project_id = project_id
        self.path = memory_path(project_id)
        self.data = read_json(self.path, {"chunks": [], "artifacts": [], "trace_edges": []})
        self.lance_dir = self.path.parent / "lance"
        self.table_name = "sentinel_memory"
        self._lancedb = None
        self._table = None
        self.backend = "json-hybrid"
        self._connect_lancedb()

    def _connect_lancedb(self) -> None:
        try:
            import lancedb  # type: ignore

            self.lance_dir.mkdir(parents=True, exist_ok=True)
            self._lancedb = lancedb.connect(str(self.lance_dir))
            if self.table_name in self._lancedb.list_tables():
                self._table = self._lancedb.open_table(self.table_name)
            else:
                self._table = self._lancedb.create_table(
                    self.table_name,
                    data=[
                        {
                            "project_id": self.project_id,
                            "chunk_id": "__bootstrap__",
                            "artifact_id": "__bootstrap__",
                            "artifact_type": "bootstrap",
                            "source_path": "",
                            "domain": "system",
                            "trace_ids": "",
                            "indexed_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
                            "summary": "bootstrap",
                            "text": "bootstrap",
                            "status": "inactive",
                            "vector": hash_embedding("bootstrap"),
                        }
                    ],
                    mode="overwrite",
                )
            self.backend = "lancedb-hybrid"
        except Exception:
            self._lancedb = None
            self._table = None
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
        self._upsert_lancedb_chunks(artifact_id)

    def _upsert_lancedb_chunks(self, artifact_id: str) -> None:
        if self._table is None:
            return
        rows = []
        for chunk in self.data.get("chunks", []):
            if chunk.get("artifact_id") != artifact_id:
                continue
            rows.append(
                {
                    "project_id": chunk["project_id"],
                    "chunk_id": chunk["chunk_id"],
                    "artifact_id": chunk["artifact_id"],
                    "artifact_type": chunk["artifact_type"],
                    "source_path": chunk["source_path"],
                    "domain": chunk["domain"],
                    "trace_ids": ",".join(chunk.get("trace_ids", [])),
                    "indexed_at": chunk["indexed_at"],
                    "summary": chunk["summary"],
                    "text": chunk["text"],
                    "status": chunk["status"],
                    "vector": hash_embedding(chunk["text"]),
                }
            )
        try:
            existing = self._table.to_list()
            retained = [
                row
                for row in existing
                if row.get("artifact_id") != artifact_id
                and row.get("chunk_id") != "__bootstrap__"
                and row.get("project_id") == self.project_id
            ]
            all_rows = retained + rows
            if all_rows:
                self._table = self._lancedb.create_table(self.table_name, data=all_rows, mode="overwrite")
        except Exception:
            self.backend = "json-hybrid"

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
        vector_candidates = self._lancedb_candidates(query, limit=max(limit * 4, 20))
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
            vector = vector_candidates.get(chunk["chunk_id"], 0.0)
            workflow_boost = 0.05 if workflow.lower() in text.lower() else 0.0
            score = lexical + semantic + vector + workflow_boost
            if score > 0:
                scored.append({"score": round(score, 4), **chunk})
        return sorted(scored, key=lambda row: row["score"], reverse=True)[:limit]

    def _lancedb_candidates(self, query: str, limit: int) -> dict[str, float]:
        if self._table is None:
            return {}
        try:
            rows = self._table.search(hash_embedding(query)).limit(limit).to_list()
        except Exception:
            return {}
        candidates: dict[str, float] = {}
        for row in rows:
            if row.get("project_id") != self.project_id or row.get("status") != "active":
                continue
            distance = float(row.get("_distance", 1.0))
            candidates[row["chunk_id"]] = max(0.0, 1.0 - distance)
        return candidates

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
    indexed.extend(index_context_folders(project_id, broker))
    broker.index_trace_edges(graph.get("edges", []))
    return {"project_id": project_id, "indexed": indexed, "count": len(indexed)}


def index_context_folders(project_id: str, broker: ContextBroker | None = None) -> list[str]:
    broker = broker or ContextBroker(project_id)
    base = workspace_path(project_id)
    indexed: list[str] = []
    for relative, (artifact_type, domain) in CONTEXT_FOLDERS.items():
        folder = base / relative
        if not folder.exists():
            continue
        for path in sorted(folder.rglob("*")):
            if path.suffix.lower() not in {".md", ".txt"} or not path.is_file():
                continue
            artifact_id = context_artifact_id(project_id, path)
            broker.index_artifact(
                artifact_id,
                artifact_type,
                path,
                path.read_text(encoding="utf-8"),
                domain=domain,
                trace_ids=[artifact_id],
            )
            indexed.append(artifact_id)
    return indexed


def context_artifact_id(project_id: str, path: Path) -> str:
    base = workspace_path(project_id)
    try:
        relative = path.relative_to(base).as_posix()
    except ValueError:
        relative = path.as_posix()
    slug = re.sub(r"[^A-Za-z0-9]+", "-", relative).strip("-").upper()
    return f"CTX-{slug[:80]}"


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
