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
RU_ID_RE = re.compile(r"RU-\d{3}")
VECTOR_DIMENSIONS = 128
# v2 (IMP-122): chunks carry a deterministic situational context prefix used only for
# embedding/FTS indexing; the cited content and read_plan anchors are unchanged.
CHUNKING_VERSION = "heading-table:v2"
# IMP-123: deterministic, network-free second-stage re-score over the merged
# shortlist. Weights recency (iteration, then indexed_at) and domain coverage so
# fresh, on-domain context outranks stale context with equivalent vocabulary.
# Bounded so the re-score breaks near-ties without overriding strong relevance
# signals; an optional neural reranker stays off by default and is never required.
RECENCY_WEIGHT = 0.15
COVERAGE_WEIGHT = 0.05
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
INDEXABLE_SUFFIXES = {".md", ".txt", ".html", ".htm"}


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


def _probe_model2vec(model_ref: str) -> tuple[Embedder | None, dict[str, str]]:
    """Try to load a local model2vec model, recording why it did or did not activate.

    Never reaches the network: remote refs are refused and ``local_files_only`` is
    enforced; the only path that drops the flag requires an existing local path.
    """
    diag: dict[str, str] = {"level": "model2vec", "model_ref": model_ref}
    if not _looks_local_model_ref(model_ref):
        diag.update(outcome="skipped", detail="model ref looks like a remote URL; refusing to fetch (local-first)")
        return None, diag
    try:
        from model2vec import StaticModel  # type: ignore
    except Exception as exc:  # noqa: BLE001 - report any import failure as package-missing
        diag.update(outcome="package-missing", detail=f"model2vec package not importable ({exc.__class__.__name__})")
        return None, diag
    try:
        try:
            model = StaticModel.from_pretrained(model_ref, local_files_only=True)
        except TypeError:
            if not Path(model_ref).expanduser().exists():
                diag.update(
                    outcome="model-not-local",
                    detail="installed model2vec cannot enforce local_files_only and the ref is not a local path; no download attempted",
                )
                return None, diag
            model = StaticModel.from_pretrained(model_ref)
        embedder = Model2VecEmbedder(model, model_ref)
        diag.update(outcome="active", detail=f"local model2vec model loaded: {model_ref}")
        return embedder, diag
    except Exception as exc:  # noqa: BLE001 - any load failure stays local and falls back
        diag.update(
            outcome="model-unavailable",
            detail=f"model2vec installed but model not available locally ({exc.__class__.__name__}); no download attempted",
        )
        return None, diag


def _probe_sentence_transformers(model_ref: str) -> tuple[Embedder | None, dict[str, str]]:
    """Try to load a local sentence-transformers model, recording the outcome. No network."""
    diag: dict[str, str] = {"level": "sentence-transformers", "model_ref": model_ref}
    if not _looks_local_model_ref(model_ref):
        diag.update(outcome="skipped", detail="model ref looks like a remote URL; refusing to fetch (local-first)")
        return None, diag
    try:
        from sentence_transformers import SentenceTransformer  # type: ignore
    except Exception as exc:  # noqa: BLE001
        diag.update(outcome="package-missing", detail=f"sentence-transformers package not importable ({exc.__class__.__name__})")
        return None, diag
    try:
        try:
            model = SentenceTransformer(model_ref, local_files_only=True)
        except TypeError:
            if not Path(model_ref).expanduser().exists():
                diag.update(
                    outcome="model-not-local",
                    detail="installed sentence-transformers cannot enforce local_files_only and the ref is not a local path; no download attempted",
                )
                return None, diag
            model = SentenceTransformer(model_ref)
        embedder = SentenceTransformersEmbedder(model, model_ref)
        diag.update(outcome="active", detail=f"local sentence-transformers model loaded: {model_ref}")
        return embedder, diag
    except Exception as exc:  # noqa: BLE001
        diag.update(
            outcome="model-unavailable",
            detail=f"sentence-transformers installed but model not available locally ({exc.__class__.__name__}); no download attempted",
        )
        return None, diag


def _probe_embedder() -> tuple[Embedder, list[dict[str, str]]]:
    """Resolve the active local embedder and the per-candidate diagnostic trail.

    Order: model2vec → sentence-transformers → deterministic hash fallback. The hash
    fallback is first-class and always succeeds, so detection never raises or hits the
    network. Returns the embedder plus an ordered list of candidate outcomes.
    """
    diagnostics: list[dict[str, str]] = []

    model2vec_ref = os.environ.get("SENTINEL_MODEL2VEC_MODEL", DEFAULT_MODEL2VEC_MODEL)
    embedder, diag = _probe_model2vec(model2vec_ref)
    diagnostics.append(diag)
    if embedder is not None:
        return embedder, diagnostics

    st_ref = os.environ.get("SENTINEL_SENTENCE_TRANSFORMERS_MODEL", DEFAULT_SENTENCE_TRANSFORMERS_MODEL)
    embedder, diag = _probe_sentence_transformers(st_ref)
    diagnostics.append(diag)
    if embedder is not None:
        return embedder, diagnostics

    return HashEmbedder(), diagnostics


def detect_embedder() -> Embedder:
    return _probe_embedder()[0]


def _embedder_recommendation(candidates: list[dict[str, str]]) -> str:
    """Actionable next step when no semantic embedder is active, derived from outcomes."""
    outcomes = {candidate.get("outcome") for candidate in candidates}
    if "package-missing" in outcomes:
        return (
            "Install optional local models with `python -m pip install -e .[memory-semantic]`, "
            "then pre-seed the model cache offline or set SENTINEL_MODEL2VEC_MODEL / "
            "SENTINEL_SENTENCE_TRANSFORMERS_MODEL to a local model path."
        )
    if outcomes & {"model-not-local", "model-unavailable"}:
        return (
            "Semantic packages are installed but no model is available locally. Pre-seed the model "
            "cache offline or set SENTINEL_MODEL2VEC_MODEL / SENTINEL_SENTENCE_TRANSFORMERS_MODEL to a "
            "local model path. Sentinel never downloads a model at runtime."
        )
    if outcomes and outcomes <= {"skipped"}:
        return (
            "Configured model refs look remote and were refused (local-first). Point "
            "SENTINEL_MODEL2VEC_MODEL / SENTINEL_SENTENCE_TRANSFORMERS_MODEL at a local model path."
        )
    return (
        "Install optional local models with `python -m pip install -e .[memory-semantic]` and provide "
        "a local model path or pre-seeded cache."
    )


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


def embedder_diagnostics() -> dict[str, Any]:
    """Diagnose local semantic embedder availability without ever using the network.

    Returns the active embedder status, whether semantic retrieval is active, the
    ordered per-candidate outcomes, and an actionable recommendation when the
    deterministic hash fallback is in effect.
    """
    embedder, candidates = _probe_embedder()
    status = embedder.status
    return {
        "active": {
            "name": status.name,
            "level": status.level,
            "version": status.version,
            "dimensions": status.dimensions,
            "detail": status.detail,
            "semantic": status.semantic,
        },
        "semantic": status.semantic,
        "candidates": candidates,
        "recommendation": "" if status.semantic else _embedder_recommendation(candidates),
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
        self.lancedb_degraded_reason = ""
        self.fts_ready = False
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
                            "chunking_version": CHUNKING_VERSION,
                            "section_path": "",
                            "line_start": 1,
                            "line_end": 1,
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
            self._ensure_fts_index()
            self.backend = "lancedb-hybrid"
        except Exception as exc:
            self._lancedb = None
            self._table = None
            self.backend = "json-hybrid"
            self.lancedb_degraded_reason = f"{type(exc).__name__}: {exc}"

    def _degrade_lancedb(self, exc: Exception) -> None:
        self._table = None
        self.backend = "json-hybrid"
        self.lancedb_degraded_reason = f"{type(exc).__name__}: {exc}"

    def _ensure_fts_index(self) -> None:
        if self._table is None:
            return
        try:
            self._table.create_fts_index("text", replace=False)
            self.fts_ready = True
        except Exception as exc:
            message = str(exc).lower()
            if "already exists" in message or "already been created" in message:
                self.fts_ready = True
                return
            self.fts_ready = False
            self.lancedb_degraded_reason = f"FTS index unavailable: {type(exc).__name__}: {exc}"

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
        skip_unchanged: bool = False,
    ) -> bool:
        trace_ids = trace_ids or [artifact_id]
        metadata = metadata or {}
        language = metadata.get("language", "unknown")
        confidence = metadata.get("confidence", "unknown")
        sensitivity = metadata.get("sensitivity", "internal")
        source_hash = content_hash(text)
        if skip_unchanged and self.artifact_is_current(artifact_id, source_hash):
            return False
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
            "chunking_version": CHUNKING_VERSION,
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
        for index, chunk in enumerate(chunk_records(text)):
            chunk_text = chunk["text"]
            context_prefix = build_context_prefix(
                title=artifact["title"],
                artifact_type=artifact_type,
                domain=domain,
                iteration=iteration,
                section_path=chunk["section_path"],
                trace_ids=trace_ids,
            )
            context_text = contextualize_chunk_text(context_prefix, chunk_text)
            self.data["chunks"].append(
                {
                    **artifact,
                    "chunk_id": f"{artifact_id}::chunk-{index + 1:03d}",
                    "section_path": chunk["section_path"],
                    "line_start": chunk["line_start"],
                    "line_end": chunk["line_end"],
                    "text": chunk_text,
                    "content": chunk_text,
                    "summary": chunk_text[:180],
                    "context_text": context_text,
                    "status": "active",
                    "embedding": self.embedder.embed(context_text),
                }
            )
        write_json(self.path, self.data)
        write_json(self.manifest_path, {"project_id": self.project_id, "artifacts": self.data["artifacts"]})
        self._upsert_lancedb_chunks(artifact_id)
        return True

    def artifact_is_current(self, artifact_id: str, source_hash: str) -> bool:
        for artifact in self.data.get("artifacts", []):
            if artifact.get("artifact_id") != artifact_id:
                continue
            return (
                artifact.get("source_hash") == source_hash
                and artifact.get("embedding_version") == self.embedder_status.version
                and artifact.get("chunking_version") == CHUNKING_VERSION
            )
        return False

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
                    "chunking_version": chunk.get("chunking_version", CHUNKING_VERSION),
                    "section_path": chunk.get("section_path", ""),
                    "line_start": int(chunk.get("line_start", 0)),
                    "line_end": int(chunk.get("line_end", 0)),
                    "language": chunk.get("language", "unknown"),
                    "confidence": chunk.get("confidence", "unknown"),
                    "sensitivity": chunk.get("sensitivity", "internal"),
                    "indexed_at": chunk["indexed_at"],
                    "summary": chunk["summary"],
                    # FTS indexes the `text` column: feed the contextualized text so the
                    # situational prefix improves full-text recall. The cited content stays
                    # in `content`; retrieve() returns rows from JSON, never this column.
                    "text": chunk.get("context_text") or chunk["text"],
                    "content": chunk["content"],
                    "status": chunk["status"],
                    "embedder": chunk.get("embedder", self.embedder_status.name),
                    "embedding_version": chunk.get("embedding_version", self.embedder_status.version),
                    "vector": chunk.get("embedding") or self.embedder.embed(chunk.get("context_text") or chunk["text"]),
                }
            )
        try:
            self._table.delete(
                f"project_id = '{lancedb_literal(self.project_id)}' "
                f"AND artifact_id = '{lancedb_literal(artifact_id)}'"
            )
            if rows:
                self._table.add(rows)
                self._ensure_fts_index()
        except Exception as exc:
            self._degrade_lancedb(exc)

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
        lancedb_candidates = self._lancedb_candidates(
            query,
            limit=max(limit * 4, 20),
            artifact_type=artifact_type,
            domain=domain,
            iteration_min=iteration_min,
            status=status,
            language=language,
            sensitivity=sensitivity,
            section=section,
        )
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
            # Score against the contextualized text (situational prefix + chunk) so the
            # prefix lifts lexical/FTS/semantic recall; the verbatim chunk text is still
            # what gets returned and cited (IMP-122).
            index_text = chunk.get("context_text") or chunk["text"]
            overlap = len(query_tokens.intersection(tokenize(index_text))) / max(len(query_tokens), 1)
            lexical = max(overlap, cosine(query_vector, text_vector(index_text)))
            lancedb_signal = lancedb_candidates.get(chunk["chunk_id"], {})
            vector = float(lancedb_signal.get("score", 0.0))
            local_embedding = 0.0
            if self.embedder_status.semantic and chunk.get("embedding_version") == self.embedder_status.version:
                local_embedding = embedding_cosine(query_embedding, chunk.get("embedding", []))
            workflow_boost = 0.05 if workflow.lower() in index_text.lower() else 0.0
            score = lexical + vector + local_embedding + workflow_boost
            if score > 0:
                row = {"score": round(score, 4), **chunk}
                row.pop("embedding", None)
                # The situational prefix is an indexing aid only; never expose it to the agent.
                row.pop("context_text", None)
                row["why_retrieved"] = why_retrieved(
                    lexical,
                    vector,
                    local_embedding,
                    workflow_boost,
                    artifact_type,
                    domain,
                    trace_id,
                    self.embedder_status.name,
                    lancedb_signal.get("vector_rank"),
                    lancedb_signal.get("fts_rank"),
                )
                if summary_only:
                    row["text"] = row["summary"]
                    row["content"] = row["summary"]
                row["read_plan"] = {
                    "source_path": row.get("source_path", row.get("file_path", "")),
                    "section_path": row.get("section_path", ""),
                    "line_start": int(row.get("line_start", 0) or 0),
                    "line_end": int(row.get("line_end", 0) or 0),
                }
                scored.append(row)
        # IMP-123: deterministic recency + domain-coverage re-score over the merged
        # shortlist before truncation, so fresh context wins lexical ties.
        results = apply_recency_coverage_rescore(scored, query_tokens)[:limit]
        if max_chars is not None:
            results = apply_char_budget(results, max_chars)
        return results

    def _lancedb_candidates(
        self,
        query: str,
        limit: int,
        artifact_type: str | None = None,
        domain: str | None = None,
        iteration_min: int = 1,
        status: str | None = None,
        language: str | None = None,
        sensitivity: str | None = None,
        section: str | None = None,
    ) -> dict[str, dict[str, float | int]]:
        if self._table is None:
            return {}
        where = lancedb_where(
            self.project_id,
            artifact_type=artifact_type,
            domain=domain,
            iteration_min=iteration_min,
            status=status,
            language=language,
            sensitivity=sensitivity,
            section=section,
        )
        candidates: dict[str, dict[str, float | int]] = {}
        try:
            rows = self._table.search(self.embedder.embed(query)).where(where, prefilter=True).limit(limit).to_list()
            for rank, row in enumerate(rows, start=1):
                if row.get("project_id") != self.project_id or row.get("status") != "active":
                    continue
                chunk_id = row["chunk_id"]
                candidates.setdefault(chunk_id, {"score": 0.0})
                candidates[chunk_id]["vector_rank"] = rank
                candidates[chunk_id]["score"] = float(candidates[chunk_id]["score"]) + reciprocal_rank(rank)
        except Exception as exc:
            self.lancedb_degraded_reason = f"vector search unavailable: {type(exc).__name__}: {exc}"

        if self.fts_ready:
            try:
                rows = self._table.search(query, query_type="fts").where(where, prefilter=True).limit(limit).to_list()
                for rank, row in enumerate(rows, start=1):
                    if row.get("project_id") != self.project_id or row.get("status") != "active":
                        continue
                    chunk_id = row["chunk_id"]
                    candidates.setdefault(chunk_id, {"score": 0.0})
                    candidates[chunk_id]["fts_rank"] = rank
                    candidates[chunk_id]["score"] = float(candidates[chunk_id]["score"]) + reciprocal_rank(rank)
            except Exception as exc:
                self.lancedb_degraded_reason = f"FTS search unavailable: {type(exc).__name__}: {exc}"

        for payload in candidates.values():
            payload["score"] = round(float(payload.get("score", 0.0)) * 10, 6)
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
            "backend_degradation_reason": self.lancedb_degraded_reason or None,
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


def reindex_workspace(project_id: str, full: bool = False) -> dict[str, Any]:
    graph = read_json(graph_path(project_id), {"nodes": [], "edges": []})
    broker = ContextBroker(project_id)
    indexed = []
    skipped = []
    for node in graph.get("nodes", []):
        path_value = node.get("path")
        if not path_value:
            continue
        path = Path(path_value)
        if not path.is_absolute():
            path = Path.cwd() / path
        if not path.exists() or path.suffix.lower() not in INDEXABLE_SUFFIXES:
            continue
        changed = broker.index_artifact(
            node["id"],
            node.get("type", "artifact"),
            path,
            path.read_text(encoding="utf-8"),
            domain=node.get("domain", "product"),
            trace_ids=[node["id"]],
            skip_unchanged=not full,
        )
        if changed:
            indexed.append(node["id"])
        else:
            skipped.append(node["id"])
    context_result = index_context_folders(project_id, broker, full=full)
    indexed.extend(context_result["indexed"])
    skipped.extend(context_result["skipped"])
    broker.index_trace_edges(graph.get("edges", []))
    return {
        "project_id": project_id,
        "indexed": indexed,
        "skipped": skipped,
        "count": len(indexed),
        "embedded_count": len(indexed),
        "skipped_count": len(skipped),
        "full": full,
    }


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


def index_context_folders(project_id: str, broker: ContextBroker | None = None, full: bool = False) -> dict[str, list[str]]:
    broker = broker or ContextBroker(project_id)
    base = workspace_path(project_id)
    indexed: list[str] = []
    skipped: list[str] = []
    for relative, (artifact_type, domain) in CONTEXT_FOLDERS.items():
        folder = base / relative
        if not folder.exists():
            continue
        for path in sorted(folder.rglob("*")):
            if path.suffix.lower() not in INDEXABLE_SUFFIXES or not path.is_file():
                continue
            artifact_id = context_artifact_id(project_id, path)
            changed = broker.index_artifact(
                artifact_id,
                artifact_type,
                path,
                path.read_text(encoding="utf-8"),
                domain=domain,
                trace_ids=[artifact_id],
                skip_unchanged=not full,
            )
            if changed:
                indexed.append(artifact_id)
            else:
                skipped.append(artifact_id)
    return {"indexed": indexed, "skipped": skipped}


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


def lancedb_literal(value: str) -> str:
    return value.replace("'", "''")


def lancedb_where(
    project_id: str,
    artifact_type: str | None = None,
    domain: str | None = None,
    iteration_min: int = 1,
    status: str | None = None,
    language: str | None = None,
    sensitivity: str | None = None,
    section: str | None = None,
) -> str:
    clauses = [
        f"project_id = '{lancedb_literal(project_id)}'",
        f"status = '{lancedb_literal(status or 'active')}'",
        f"iteration >= {int(iteration_min)}",
    ]
    if artifact_type:
        clauses.append(f"artifact_type = '{lancedb_literal(artifact_type)}'")
    if domain:
        clauses.append(f"domain = '{lancedb_literal(domain)}'")
    if language:
        clauses.append(f"language = '{lancedb_literal(language)}'")
    if sensitivity:
        clauses.append(f"sensitivity = '{lancedb_literal(sensitivity)}'")
    if section:
        clauses.append(f"section_path LIKE '%{lancedb_literal(section)}%'")
    return " AND ".join(clauses)


def reciprocal_rank(rank: int, k: int = 60) -> float:
    return 1.0 / (k + rank)


def section_path_for_chunk(text: str) -> str:
    headings = [line.strip("# ").strip() for line in text.splitlines() if line.startswith("#")]
    return " > ".join(headings[-3:]) if headings else ""


def why_retrieved(
    lexical: float,
    vector: float,
    local_embedding: float,
    workflow_boost: float,
    artifact_type: str | None,
    domain: str | None,
    trace_id: str | None,
    embedder_name: str = "hash_embedding",
    vector_rank: float | int | None = None,
    fts_rank: float | int | None = None,
) -> str:
    reasons = []
    if lexical:
        reasons.append("lexical match")
    if vector:
        rank_bits = []
        if vector_rank:
            rank_bits.append(f"vector_rank={int(vector_rank)}")
        if fts_rank:
            rank_bits.append(f"fts_rank={int(fts_rank)}")
        suffix = f" ({', '.join(rank_bits)})" if rank_bits else ""
        reasons.append(f"LanceDB RRF match via {embedder_name}{suffix}")
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


def _recency_key(chunk: dict[str, Any]) -> tuple[int, str]:
    """Deterministic recency ordering key: higher iteration first, then a later
    ``indexed_at``. ``indexed_at`` is an ISO-8601 string, so lexical order already
    matches chronological order — no parsing or network needed."""
    return (int(chunk.get("iteration", 1) or 1), str(chunk.get("indexed_at", "")))


def domain_coverage(chunk: dict[str, Any], query_tokens: set[str]) -> float:
    """Deterministic domain-coverage signal in [0, 1].

    Rewards a chunk whose ``domain`` the query explicitly references (the query
    "covers" that domain). Tokenization is consistent with ``retrieve`` and the
    check is purely local."""
    if not query_tokens:
        return 0.0
    domain_tokens = set(tokenize(str(chunk.get("domain", ""))))
    if domain_tokens and domain_tokens.issubset(query_tokens):
        return 1.0
    return 0.0


def apply_recency_coverage_rescore(
    rows: list[dict[str, Any]],
    query_tokens: set[str],
    recency_weight: float = RECENCY_WEIGHT,
    coverage_weight: float = COVERAGE_WEIGHT,
) -> list[dict[str, Any]]:
    """Second-stage deterministic re-score (IMP-123).

    Adds a bounded recency + domain-coverage bonus to each row's base score so
    fresh, on-domain context outranks stale context with equivalent vocabulary,
    then returns the rows sorted by the re-scored value. Recency is pool-relative:
    the newest chunk in the shortlist scores 1.0 and the oldest 0.0, so a single
    distinct recency yields no differentiation. Network-free; ties are broken by
    recency then ``chunk_id`` for fully deterministic ordering."""
    if not rows:
        return rows
    distinct_keys = sorted({_recency_key(row) for row in rows})
    span = len(distinct_keys) - 1
    recency_norm = {key: (index / span if span else 0.0) for index, key in enumerate(distinct_keys)}
    for row in rows:
        recency = recency_norm[_recency_key(row)]
        coverage = domain_coverage(row, query_tokens)
        bonus = recency_weight * recency + coverage_weight * coverage
        row["base_score"] = row["score"]
        row["recency_score"] = round(recency, 4)
        row["coverage_score"] = round(coverage, 4)
        row["score"] = round(row["score"] + bonus, 4)
        extra = []
        if recency > 0:
            extra.append(f"recency boost (iteration {int(row.get('iteration', 1) or 1)})")
        if coverage > 0:
            extra.append("domain coverage")
        if extra and row.get("why_retrieved"):
            row["why_retrieved"] = f"{row['why_retrieved']}; " + "; ".join(extra)
    return sorted(
        rows,
        key=lambda row: (row["score"], _recency_key(row), row["chunk_id"]),
        reverse=True,
    )


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
    return [chunk["text"] for chunk in chunk_records(text, max_chars=max_chars)]


def build_context_prefix(
    *,
    title: str = "",
    artifact_type: str = "",
    domain: str = "",
    iteration: int = 1,
    section_path: str = "",
    trace_ids: list[str] | None = None,
) -> str:
    """Deterministic, local situational prefix for a chunk (Contextual Retrieval, IMP-122).

    The prefix names the document, type, section, domain, iteration, and any Requirement
    Units (RU-NNN) the chunk belongs to. It is used only to embed and full-text index the
    chunk; it never enters the cited content the agent reads, nor the read_plan anchors.
    No network and no model are involved — the metadata already exists from chunking.
    """
    parts: list[str] = []
    if title:
        parts.append(f"document: {title}")
    if artifact_type:
        parts.append(f"type: {artifact_type}")
    if section_path:
        parts.append(f"section: {section_path}")
    if domain:
        parts.append(f"domain: {domain}")
    parts.append(f"iteration: {iteration}")
    units: list[str] = []
    for trace_id in trace_ids or []:
        for match in RU_ID_RE.findall(str(trace_id)):
            if match not in units:
                units.append(match)
    for match in RU_ID_RE.findall(section_path or ""):
        if match not in units:
            units.append(match)
    if units:
        parts.append(f"units: {', '.join(sorted(units))}")
    return "[" + " | ".join(parts) + "]"


def contextualize_chunk_text(prefix: str, text: str) -> str:
    """Compose the indexing text from the situational prefix and the verbatim chunk text."""
    return f"{prefix}\n{text}" if prefix else text


def chunk_records(text: str, max_chars: int = 900, overlap_ratio: float = 0.12) -> list[dict[str, Any]]:
    blocks = markdown_blocks(text)
    chunks: list[dict[str, Any]] = []
    current: list[dict[str, Any]] = []
    current_chars = 0
    heading_stack: list[str] = []
    overlap_chars = int(max_chars * overlap_ratio)

    def flush() -> None:
        nonlocal current, current_chars
        if not current:
            return
        chunk_text = "\n\n".join(block["text"] for block in current).strip()
        section_path = next((block.get("section_path", "") for block in reversed(current) if block.get("section_path")), "")
        chunks.append(
            {
                "text": chunk_text,
                "section_path": section_path or section_path_for_chunk(chunk_text),
                "line_start": min(block["line_start"] for block in current),
                "line_end": max(block["line_end"] for block in current),
            }
        )
        overlap = prose_overlap_block(current, overlap_chars)
        current = [overlap] if overlap else []
        current_chars = len(overlap["text"]) if overlap else 0

    for block in blocks:
        heading = markdown_heading(block["text"])
        if heading:
            level, title = heading
            heading_stack = heading_stack[: level - 1]
            heading_stack.append(title)
            if current:
                flush()
                current = []
                current_chars = 0

        block_section = " > ".join(heading_stack)
        block["section_path"] = block_section
        separator = 2 if current else 0
        if current and current_chars + separator + len(block["text"]) > max_chars:
            flush()
        current.append(block)
        current_chars += separator + len(block["text"])
        if block["kind"] == "table" and len(block["text"]) > max_chars:
            flush()
            current = []
            current_chars = 0

    if current:
        flush()
    return chunks


def markdown_blocks(text: str) -> list[dict[str, Any]]:
    lines = text.splitlines()
    blocks: list[dict[str, Any]] = []
    index = 0
    while index < len(lines):
        while index < len(lines) and not lines[index].strip():
            index += 1
        if index >= len(lines):
            break
        start = index
        if is_table_line(lines[index]):
            while index < len(lines) and (is_table_line(lines[index]) or is_table_separator(lines[index])):
                index += 1
            kind = "table"
        else:
            index += 1
            while index < len(lines) and lines[index].strip() and not is_table_line(lines[index]):
                if markdown_heading(lines[index]):
                    break
                index += 1
            kind = "heading" if markdown_heading(lines[start]) else "prose"
        block_text = "\n".join(lines[start:index]).strip()
        if block_text:
            blocks.append({"text": block_text, "line_start": start + 1, "line_end": index, "kind": kind})
    return blocks


def markdown_heading(text: str) -> tuple[int, str] | None:
    first = text.splitlines()[0].strip() if text.strip() else ""
    match = re.match(r"^(#{1,6})\s+(.+)$", first)
    if not match:
        return None
    return len(match.group(1)), match.group(2).strip()


def is_table_line(line: str) -> bool:
    stripped = line.strip()
    return stripped.startswith("|") and stripped.endswith("|") and stripped.count("|") >= 2


def is_table_separator(line: str) -> bool:
    stripped = line.strip()
    return bool(re.match(r"^\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?$", stripped))


def prose_overlap_block(blocks: list[dict[str, Any]], max_chars: int) -> dict[str, Any] | None:
    if max_chars <= 0:
        return None
    for block in reversed(blocks):
        if block.get("kind") != "prose":
            continue
        text = block["text"]
        if len(text) > max_chars:
            text = text[-max_chars:].lstrip()
        return {
            "text": text,
            "line_start": block["line_start"],
            "line_end": block["line_end"],
            "kind": "overlap",
            "section_path": block.get("section_path", ""),
        }
    return None
