from __future__ import annotations

import math
import re
import json
import os
from hashlib import blake2b, sha256
from collections import Counter
from datetime import datetime, timezone
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .workspace import graph_path, memory_path, read_json, write_json, workspace_path


TOKEN_RE = re.compile(r"\w+", re.UNICODE)
VECTOR_DIMENSIONS = 128
DEFAULT_MODEL2VEC_MODEL = "minishlab/potion-multilingual-128M"
DEFAULT_SENTENCE_TRANSFORMERS_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
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


@dataclass(frozen=True)
class EmbedderStatus:
    name: str
    level: str
    version: str
    dimensions: int
    detail: str
    semantic: bool


class Embedder:
    """Local-only embedding abstraction with deterministic fallback."""

    status = EmbedderStatus(
        name="hash_embedding",
        level="hash",
        version=f"hash_embedding:v1:{VECTOR_DIMENSIONS}",
        dimensions=VECTOR_DIMENSIONS,
        detail="deterministic local hash fallback",
        semantic=False,
    )

    def embed(self, text: str) -> list[float]:
        return hash_embedding(text, self.status.dimensions)


class HashEmbedder(Embedder):
    pass


class Model2VecEmbedder(Embedder):
    def __init__(self, model: Any, model_ref: str):
        self.model = model
        dimensions = len(self.embed("dimension probe"))
        self.status = EmbedderStatus(
            name="model2vec",
            level="model2vec",
            version=f"model2vec:{model_ref}",
            dimensions=dimensions,
            detail=f"local model2vec model: {model_ref}",
            semantic=True,
        )

    def embed(self, text: str) -> list[float]:
        return normalize_embedding(self.model.encode([text])[0])


class SentenceTransformersEmbedder(Embedder):
    def __init__(self, model: Any, model_ref: str):
        self.model = model
        dimensions = len(self.embed("dimension probe"))
        self.status = EmbedderStatus(
            name="sentence-transformers",
            level="sentence-transformers",
            version=f"sentence-transformers:{model_ref}",
            dimensions=dimensions,
            detail=f"local sentence-transformers model: {model_ref}",
            semantic=True,
        )

    def embed(self, text: str) -> list[float]:
        return normalize_embedding(self.model.encode([text])[0])


def normalize_embedding(values: Any) -> list[float]:
    vector = [float(value) for value in values]
    norm = math.sqrt(sum(value * value for value in vector))
    if not norm:
        return [0.0 for _ in vector]
    return [round(value / norm, 6) for value in vector]


def embedding_cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    return sum(left * right for left, right in zip(a, b))


def _looks_local_model_ref(model_ref: str) -> bool:
    path = Path(model_ref).expanduser()
    if path.exists():
        return True
    # Hugging Face cache IDs are allowed only when the library can enforce
    # local-files-only loading; no runtime download is attempted by Sentinel.
    return not any(marker in model_ref.lower() for marker in ("http://", "https://"))


def detect_embedder() -> Embedder:
    model2vec_ref = os.environ.get("SENTINEL_MODEL2VEC_MODEL", DEFAULT_MODEL2VEC_MODEL)
    if _looks_local_model_ref(model2vec_ref):
        try:
            from model2vec import StaticModel  # type: ignore

            try:
                model = StaticModel.from_pretrained(model2vec_ref, local_files_only=True)
            except TypeError:
                if not Path(model2vec_ref).expanduser().exists():
                    raise RuntimeError("model2vec local_files_only is unavailable and model ref is not a local path")
                model = StaticModel.from_pretrained(model2vec_ref)
            return Model2VecEmbedder(model, model2vec_ref)
        except Exception:
            pass

    st_ref = os.environ.get("SENTINEL_SENTENCE_TRANSFORMERS_MODEL", DEFAULT_SENTENCE_TRANSFORMERS_MODEL)
    if _looks_local_model_ref(st_ref):
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore

            try:
                model = SentenceTransformer(st_ref, local_files_only=True)
            except TypeError:
                if not Path(st_ref).expanduser().exists():
                    raise RuntimeError("sentence-transformers local_files_only is unavailable and model ref is not a local path")
                model = SentenceTransformer(st_ref)
            return SentenceTransformersEmbedder(model, st_ref)
        except Exception:
            pass

    return HashEmbedder()


def active_embedder_status() -> dict[str, Any]:
    status = detect_embedder().status
    return {
        "name": status.name,
        "level": status.level,
        "version": status.version,
        "dimensions": status.dimensions,
        "detail": status.detail,
        "semantic": status.semantic,
    }


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
        self.manifest_path = self.path.parent / "artifact_manifest.json"
        self.table_name = "ba_memory"
        self._lancedb = None
        self._table = None
        self.backend = "json-hybrid"
        self.embedder = detect_embedder()
        self.embedder_status = self.embedder.status
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
                            "id": "__bootstrap__",
                            "type": "bootstrap",
                            "title": "bootstrap",
                            "source_path": "",
                            "file_path": "",
                            "domain": "system",
                            "trace_ids": "",
                            "iteration": 1,
                            "metadata": "{}",
                            "source_hash": content_hash("bootstrap"),
                            "section_path": "",
                            "language": "unknown",
                            "confidence": "unknown",
                            "sensitivity": "internal",
                            "indexed_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
                            "summary": "bootstrap",
                            "text": "bootstrap",
                            "content": "bootstrap",
                            "status": "inactive",
                            "embedder": self.embedder_status.name,
                            "embedding_version": self.embedder_status.version,
                            "vector": self.embedder.embed("bootstrap"),
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
        title: str | None = None,
        iteration: int = 1,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        trace_ids = trace_ids or [artifact_id]
        metadata = metadata or {}
        language = metadata.get("language", "unknown")
        confidence = metadata.get("confidence", "unknown")
        sensitivity = metadata.get("sensitivity", "internal")
        source_hash = content_hash(text)
        artifact = {
            "project_id": self.project_id,
            "artifact_id": artifact_id,
            "artifact_type": artifact_type,
            "id": artifact_id,
            "type": artifact_type,
            "title": title or source_path.stem,
            "source_path": str(source_path.as_posix()),
            "file_path": str(source_path.as_posix()),
            "domain": domain,
            "trace_ids": trace_ids,
            "iteration": iteration,
            "metadata": metadata,
            "embedder": self.embedder_status.name,
            "embedding_version": self.embedder_status.version,
            "language": language,
            "confidence": confidence,
            "sensitivity": sensitivity,
            "source_hash": source_hash,
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
                    "section_path": section_path_for_chunk(chunk_text),
                    "text": chunk_text,
                    "content": chunk_text,
                    "summary": chunk_text[:180],
                    "status": "active",
                    "embedding": self.embedder.embed(chunk_text),
                }
            )
        write_json(self.path, self.data)
        write_json(self.manifest_path, {"project_id": self.project_id, "artifacts": self.data["artifacts"]})
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
                    "id": chunk["id"],
                    "type": chunk["type"],
                    "title": chunk["title"],
                    "source_path": chunk["source_path"],
                    "file_path": chunk["file_path"],
                    "domain": chunk["domain"],
                    "trace_ids": ",".join(chunk.get("trace_ids", [])),
                    "iteration": int(chunk.get("iteration", 1)),
                    "metadata": json.dumps(chunk.get("metadata", {}), ensure_ascii=False),
                    "source_hash": chunk.get("source_hash", ""),
                    "section_path": chunk.get("section_path", ""),
                    "language": chunk.get("language", "unknown"),
                    "confidence": chunk.get("confidence", "unknown"),
                    "sensitivity": chunk.get("sensitivity", "internal"),
                    "indexed_at": chunk["indexed_at"],
                    "summary": chunk["summary"],
                    "text": chunk["text"],
                    "content": chunk["content"],
                    "status": chunk["status"],
                    "embedder": chunk.get("embedder", self.embedder_status.name),
                    "embedding_version": chunk.get("embedding_version", self.embedder_status.version),
                    "vector": chunk.get("embedding") or self.embedder.embed(chunk["text"]),
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
        iteration_min: int = 1,
        status: str | None = None,
        language: str | None = None,
        sensitivity: str | None = None,
        section: str | None = None,
        max_chars: int | None = None,
        summary_only: bool = False,
    ) -> list[dict[str, Any]]:
        vector_candidates = self._lancedb_candidates(query, limit=max(limit * 4, 20))
        query_tokens = set(tokenize(query))
        query_vector = text_vector(query)
        query_embedding = self.embedder.embed(query)
        scored = []
        for chunk in self.data.get("chunks", []):
            if artifact_type and chunk.get("artifact_type") != artifact_type:
                continue
            if domain and chunk.get("domain") != domain:
                continue
            if trace_id and trace_id not in chunk.get("trace_ids", []):
                continue
            if int(chunk.get("iteration", 1)) < iteration_min:
                continue
            if status and str(chunk.get("status", "")).lower() != status.lower():
                continue
            if language and str(chunk.get("language", "")).lower() != language.lower():
                continue
            if sensitivity and str(chunk.get("sensitivity", "")).lower() != sensitivity.lower():
                continue
            if section and section.lower() not in str(chunk.get("section_path", "")).lower():
                continue
            text = chunk["text"]
            lexical = len(query_tokens.intersection(tokenize(text))) / max(len(query_tokens), 1)
            semantic = cosine(query_vector, text_vector(text))
            vector = vector_candidates.get(chunk["chunk_id"], 0.0)
            local_embedding = 0.0
            if self.embedder_status.semantic and chunk.get("embedding_version") == self.embedder_status.version:
                local_embedding = embedding_cosine(query_embedding, chunk.get("embedding", []))
            workflow_boost = 0.05 if workflow.lower() in text.lower() else 0.0
            score = lexical + semantic + vector + local_embedding + workflow_boost
            if score > 0:
                row = {"score": round(score, 4), **chunk}
                row.pop("embedding", None)
                row["why_retrieved"] = why_retrieved(
                    lexical,
                    semantic,
                    vector,
                    local_embedding,
                    workflow_boost,
                    artifact_type,
                    domain,
                    trace_id,
                    self.embedder_status.name,
                )
                if summary_only:
                    row["text"] = row["summary"]
                    row["content"] = row["summary"]
                scored.append(row)
        results = sorted(scored, key=lambda row: row["score"], reverse=True)[:limit]
        if max_chars is not None:
            results = apply_char_budget(results, max_chars)
        return results

    def _lancedb_candidates(self, query: str, limit: int) -> dict[str, float]:
        if self._table is None:
            return {}
        try:
            rows = self._table.search(self.embedder.embed(query)).limit(limit).to_list()
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
        iteration_min: int = 1,
        status: str | None = None,
        language: str | None = None,
        sensitivity: str | None = None,
        section: str | None = None,
        max_chars: int | None = None,
        summary_only: bool = False,
    ) -> dict[str, Any]:
        results = self.retrieve(
            query,
            workflow,
            limit,
            artifact_type,
            domain,
            trace_id,
            iteration_min,
            status,
            language,
            sensitivity,
            section,
            max_chars,
            summary_only,
        )
        pack = {
            "project_id": self.project_id,
            "workflow": workflow,
            "query": query,
            "backend": self.backend,
            "embedder": {
                "name": self.embedder_status.name,
                "level": self.embedder_status.level,
                "version": self.embedder_status.version,
                "dimensions": self.embedder_status.dimensions,
            },
            "filters": {
                "artifact_type": artifact_type,
                "domain": domain,
                "trace_id": trace_id,
                "iteration_min": iteration_min,
                "status": status,
                "language": language,
                "sensitivity": sensitivity,
                "section": section,
                "max_chars": max_chars,
                "summary_only": summary_only,
            },
            "source_hashes": sorted({row.get("source_hash", "") for row in results if row.get("source_hash")}),
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


def init_lancedb(project_id: str) -> dict[str, str]:
    broker = ContextBroker(project_id)
    return {"project_id": project_id, "backend": broker.backend, "table": broker.table_name}


def ingest_file(file_path: Path, project_id: str, domain: str, item_type: str, iteration: int = 1) -> str:
    broker = ContextBroker(project_id)
    artifact_id = context_artifact_id(project_id, file_path)
    broker.index_artifact(
        artifact_id,
        item_type,
        file_path,
        file_path.read_text(encoding="utf-8"),
        domain=domain,
        trace_ids=[artifact_id],
        iteration=iteration,
    )
    return artifact_id


def hybrid_search(
    project_id: str,
    query: str,
    domains: list[str] | None = None,
    iteration_min: int = 1,
    limit: int = 12,
) -> list[dict[str, Any]]:
    broker = ContextBroker(project_id)
    if not domains:
        return broker.retrieve(query, "hybrid_search", limit=limit, iteration_min=iteration_min)
    results: list[dict[str, Any]] = []
    per_domain_limit = max(limit, 1)
    for domain in domains:
        results.extend(
            broker.retrieve(query, "hybrid_search", limit=per_domain_limit, domain=domain, iteration_min=iteration_min)
        )
    return sorted(results, key=lambda row: row["score"], reverse=True)[:limit]


def get_multi_domain_context(query: str, project_id: str, iteration_min: int = 1) -> dict[str, Any]:
    domains = ["business", "technical", "design", "quality", "product"]
    return {
        "project_id": project_id,
        "query": query,
        "iteration_min": iteration_min,
        "domains": {
            domain: ContextBroker(project_id).retrieve(
                query,
                "multi_domain_context",
                limit=4,
                domain=domain,
                iteration_min=iteration_min,
            )
            for domain in domains
        },
    }


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


def content_hash(text: str) -> str:
    return sha256(text.encode("utf-8")).hexdigest()


def section_path_for_chunk(text: str) -> str:
    headings = [line.strip("# ").strip() for line in text.splitlines() if line.startswith("#")]
    return " > ".join(headings[:3]) if headings else ""


def why_retrieved(
    lexical: float,
    semantic: float,
    vector: float,
    local_embedding: float,
    workflow_boost: float,
    artifact_type: str | None,
    domain: str | None,
    trace_id: str | None,
    embedder_name: str = "hash_embedding",
) -> str:
    reasons = []
    if lexical:
        reasons.append("lexical match")
    if semantic:
        reasons.append("local semantic similarity")
    if vector:
        reasons.append(f"LanceDB/{embedder_name} vector match")
    if local_embedding:
        reasons.append(f"local semantic embedding match ({embedder_name})")
    if workflow_boost:
        reasons.append("workflow hint")
    if artifact_type:
        reasons.append(f"artifact_type={artifact_type}")
    if domain:
        reasons.append(f"domain={domain}")
    if trace_id:
        reasons.append(f"trace_id={trace_id}")
    return "; ".join(reasons) or "retrieved by local ranking"


def apply_char_budget(results: list[dict[str, Any]], max_chars: int) -> list[dict[str, Any]]:
    remaining = max(max_chars, 0)
    budgeted = []
    for row in results:
        if remaining <= 0:
            break
        text = row.get("text", "")
        if len(text) > remaining:
            row = dict(row)
            row["text"] = text[:remaining]
            row["content"] = row["text"]
        remaining -= len(row.get("text", ""))
        budgeted.append(row)
    return budgeted


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
