# Traceability and memory

This page explains how Sentinel keeps every statement tied to its evidence (the traceability graph), how it finds the right context again (memory and retrieval), and how paths are stored so a workspace can be moved or cloned. Read it if you review traceability, hand work to coding agents, version your workspaces in git, or wonder why `/retrieve` returns what it returns.

For the files themselves see the [artifact reference](02-artifact-reference.md). Terms such as trace, context pack or governed artifact are in the [glossary](00-user-guide.md).

## The three layers

```mermaid
flowchart LR
    truth["Truth<br/>workspace artifacts<br/>(gaps, brief, specs, backlog...)"] --> graph["Traceability<br/>graph + matrix"]
    truth --> mem["Memory<br/>search index"]
    mem --> packs["Context packs<br/>for agents"]
```

| Layer | Where | Role | If it disagrees with the truth |
|---|---|---|---|
| **Truth** | `workspaces/<PROJECT_ID>/` | The versionable artifacts. Authority for requirements, gaps, decisions, specs, backlog, tests and changes. | It wins. |
| **Traceability** | `06_traceability/` | Who derives from what: raw input to gap to requirement to spec unit to story to test. | Rebuilt by the next mutating command. |
| **Memory** | `memory.lancedb/` | A local search index over the truth, so an agent loads only the context it needs. | Rebuild with `/reindex`. |

> [!IMPORTANT]
> Memory is never authority. If memory and a source file disagree, the source file wins.

## Paths: workspace-relative storage and `workspaces/<ID>/...` citations

Two rules keep a workspace portable.

1. **Citations are repo-relative.** Every path a generated artifact cites (backlog anchors, the traceability matrix, reports, exports, context packs, `read_plan` anchors) is written as `workspaces/<PROJECT_ID>/...`, relative to the repository root. The same text works wherever the workspace lives, and you can open it as is from the repo root.
2. **Storage is workspace-relative.** The graph (`traceability_graph.json`), the memory files and the artifact pointers in `state.json` store paths relative to the workspace folder, never absolute ones.

### Moving or cloning a workspace

Because nothing absolute is stored, you can move a workspace folder, clone it from git, or copy it to another machine.

1. Put the folder at `workspaces/<PROJECT_ID>/` in the new repository.
2. Run `/reindex PROJECT_ID`. This rewrites any absolute path left by an older workspace or by the old location, and rebuilds the index. `memory.lancedb/` is git-ignored, so after a clone the index must be rebuilt anyway.
3. Run `/health PROJECT_ID`. It names any node that still points outside the workspace.
4. Run `/doctor`. It reports how many absolute paths remain in the graph or memory of each workspace and tells you to run `/reindex`.

A path that lies outside the workspace is kept as it is and reported, not guessed. Release mirrors under `.series_work/` are rebuilt by the release commands; they do not need moving.

## Traceability

The graph lives in `06_traceability/traceability_graph.json`. The human views are:

- `traceability_matrix.md`: a table of source-to-target links;
- `traceability_graph.md`: the graph as a Mermaid diagram;
- `health_report.md` and `.json`: findings such as stale artifacts, hand edits and missing evidence;
- `command_protocol_log.md`: the last 25 commands, in plain text. The full log is `.sentinel/command_log.jsonl`.

```bash
/trace ACME_PORTAL
python -m sentinel /trace ACME_PORTAL
```

`/trace` is a mutating command: it rewrites the matrix and the graph view. The graph is also refreshed automatically after any other mutating command, so you rarely need to run `/trace` by hand. With `--release rN` it writes under `06_traceability/<rN>/`, and the release graph is merged into the project graph.

### What enters the graph

| Event | Node | Link |
|---|---|---|
| `/ingest` | raw input, seeds, gaps, decisions, the knowledge ledger | linked from the raw input |
| `/annotate`, `/challenge`, `/scrutinize` | an agent record per pass | the raw input to the gap report |
| `/story-status` | `story_status_change` | `updates_story_status`; with `--evidence PATH` also `story_acceptance_evidence`, `acceptance_evidence_for` |
| `/sync` | change event, impact report, `story_staleness` when a spec unit changed | `may_impact` |
| `/implementation-feedback` | `implementation_feedback` | `feedback_from_implementation`; may open a feedback gap |
| `/specs`, `/backlog` regeneration | `regeneration_diff` | `triggers_regeneration` |

Sentinel records evidence, staleness and feedback. It does not run your tests and it does not rewrite backlog scope on its own.

### Knowledge ledger and metabolism

`01_discovery/knowledge_state.md` consolidates what is known by lens (`CONFIRMED`, `ASSUMED`, `OPEN`, `INFERRED`). `/resolve-gaps` and `/sync` rebuild it after confirmations or explicit invalidations. Impact reports name the affected `KLU-*` units and the stale downstream artifacts. Sentinel never invents a replacement fact: a validated assumption becomes confirmed because a gap answer closed it, and an invalidated assumption goes back to open until a BA supplies new evidence.

When a change note carries scope cues such as "no longer", "replace", "out of scope" or "instead", `/sync` marks the affected links as suspicious and lists them in the impact report and in `/health`. A BA decides whether to regenerate. If a semantic embedder is active, `/sync` also lists assumptions that look related to the change by meaning, as **Associative Impact Candidates (BA review)**. These are suggestions only; nothing is closed or invalidated automatically.

## Memory and retrieval

`/ingest`, `/sync` and `/reindex` fill the index. It holds:

- every artifact that has a path in the graph (except `source_synthesis.md`, which only repeats already-indexed citations);
- the context folders: `00_raw/00_client_requirement`, `00_raw/01_business_context`, `00_raw/02_technology_context`, `00_raw/03_design_context`, `00_raw/04_quality_context`, `00_raw/05_interactions` and `07_changes`;
- the trace edges.

These context folders are inputs owned by the relevant domains. Sentinel retrieves and cites them; it does not replace them with generated technical or design specs.

### `/retrieve`

`/retrieve` is read-only. It returns ranked chunks with the reason each was returned and where to read more.

```bash
/retrieve ACME_PORTAL --query "SLA risk" --workflow sync
python -m sentinel /retrieve ACME_PORTAL --query "SLA risk" --workflow sync
```

| Option | Effect |
|---|---|
| `--query`, `--workflow` | What to look for and for which workflow. |
| `--limit N` | Number of results (default 5). |
| `--domain`, `--trace-id`, `--artifact-type` | Filter by domain, trace id or artifact type. |
| `--status`, `--language`, `--sensitivity`, `--section` | Progressive-disclosure filters. |
| `--max-chars N`, `--summary-only` | Keep the answer short. |
| `--order relevance` (default) or `recency` | Rank by relevance, or reorder newest-first. |
| `--timeline` | A newest-first list of what changed and when (changes, impact reports, gap resolutions, interactions). Needs no `--query`. |
| `--write-pack` | Also save the result as `08_context_packs/<workflow>.json`. |

Each result has `why_retrieved` and a **`read_plan`**: `source_path`, `section_path`, `line_start` and `line_end`. When the summary is not enough, open that exact section. `source_path` follows the `workspaces/<ID>/...` rule above.

### `/reindex`

```bash
/reindex ACME_PORTAL
/reindex ACME_PORTAL --full
```

`/reindex` is mutating. By default it is incremental: an artifact with the same hash and chunking version is skipped, unless the LanceDB table has lost its rows, in which case it is embedded again. `--full` rebuilds every chunk. Run it after a clone, after adding files to the context folders, and when `/health` reports a freshness warning.

`/health` warns when context changed after the backlog was generated, names stories marked `Stale` because a spec unit changed, reports knowledge staleness after `/sync` or `/resolve-gaps`, and names stories whose Definition of Done is blocked by open implementation feedback. Re-index and retrieve before handing work to implementation; regenerate artifacts only for a material change to scope, acceptance criteria, dependencies or execution contracts.

### Context packs

A context pack is a snapshot of what was retrieved for a workflow, so a downstream agent (or a reviewer) can audit the context used. It records the query, filters, backend, source hashes, retrieved rows and the active embedder.

| Pack | Written by | Content |
|---|---|---|
| `08_context_packs/<workflow>.json` | `/retrieve --write-pack` | Whatever you asked for. |
| `discovery_focus.json`, `sync_focus.json` | `/ingest`, `/sync` | Pointer-only packs: summaries plus `read_plan` anchors. |
| `specs_generation.json` | `/specs` | Section-level retrieval behind the PRD, with `coverage_map` and `coverage_score`. |
| `backlog_generation.json` | `/backlog` | Retrieval behind epics and stories, plus a mini-context per story. |
| `implementation_readiness.json` | `/backlog` | Per-story handoff: readiness, required domains, execution contract, validation contract. |
| `slice_plan.json` | `/backlog` | Implementation order: enabler phase, waves, checkpoints, per-story handoff. |

Use packs when a workspace is too large to load fully, when a skill needs only part of it, when you want to keep what informed a workflow, or when you review change impact. Multi-section packs share one character budget and de-duplicate chunks across sections; the pack reports `disclosure_budget` and `candidate_source` (`lancedb-ann` or `json-fullscan`).

`/context-request` is a different thing: it writes Markdown requests for the technology, design, quality, frontend and backend teams to `08_context_packs/requests/`. See the [workflows](03-workflows.md).

### Declarative retrieval plans

`/specs` and `/backlog` read section plans from `sentinel/retrieval_plans/specs_generation.json` and `backlog_generation.json`. Each section declares a query, filters, limit, budgets, preferred source sections and lenses. To tune retrieval for a section, edit the plan JSON in your clone and re-run the command; no Python change is needed. Story execution contracts carry the cited anchors as `execution_contract.<signal>.anchor`.

## Privacy

Sentinel is local-first.

- `privacy_mode: local-only` is the default; the index lives under the workspace.
- Semantic embeddings, when enabled, run only from local packages and local model files. Retrieval never calls an external embedding API and never downloads a model.
- Hash embeddings are deterministic and local, and remain the fallback for restricted environments.
- Do not use remote MCP servers, external vector databases or external embedding APIs for client data unless that is approved outside this framework.

See [secure environments](09-secure-environments.md).

## Next

- [Artifact reference](02-artifact-reference.md): every folder and file.
- [Workflows](03-workflows.md): what to do after a change, a gate refusal or a new source.
- [Command reference](01-command-reference.md): `/retrieve`, `/reindex`, `/trace`, `/health`.

---

## Developer notes: memory internals

None of this is needed to use Sentinel.

### Backend

Memory lives in `memory.lancedb/`. The primary store is a local LanceDB table `ba_memory` under `memory.lancedb/lance/`. When LanceDB is available, Sentinel keeps a full-text index on `text` and combines FTS ranks with vector ranks using reciprocal rank fusion; the same search also generates the candidate set that is then scored and re-ranked. `memory.json` is the JSON fallback and audit copy, and `artifact_manifest.json` is the local artifact manifest. The JSON store holds the verbatim content, and a full scan is the fallback whenever LanceDB is absent, returns nothing or yields stale ids, so `json-hybrid` behaves identically.

LanceDB is a Python dependency installed with `.[memory]`; no database server is needed. It must be installed in the same Python environment that runs `python -m sentinel`. `/doctor` checks the import and a local open/create probe and reports the active backend and any degradation cause. `/health` includes the same fields without marking a project dirty merely because LanceDB is missing.

### Chunks

Chunks are heading-aware. Each carries `section_path` and approximate `line_start` and `line_end`. Markdown tables are never split across chunks. Before indexing, a deterministic local prefix (document title, artifact type, section path, domain, iteration, requirement units) is prepended to the text that is embedded and full-text indexed; the returned `content` and the `read_plan` anchors stay verbatim. The chunking version is `heading-table:v2`; an older workspace re-chunks on its next `/reindex`.

Rows carry these fields:

```text
project_id, id, chunk_id, type, title, content, domain, iteration, status,
file_path, trace_ids, source_hash, chunking_version, section_path,
line_start, line_end, language, confidence, sensitivity, metadata,
indexed_at, embedder, embedding_version, vector
```

### Ranking

After lexical, semantic and vector signals are merged, a bounded second stage re-scores the shortlist by recency (later iteration, then later `indexed_at`) and domain coverage. Each result exposes `base_score`, `recency_score`, `coverage_score` and the final `score`. An optional neural reranker stays off.

### Embedders

Sentinel auto-detects local embedders in this order: `model2vec` with a local multilingual static model, `sentence-transformers` with a local multilingual model, then the deterministic `hash_embedding` fallback. Every chunk records `embedder` and `embedding_version`.

To enable semantic retrieval offline:

1. Install the extra in the environment that runs Sentinel: `python -m pip install -e .[memory-semantic]`.
2. Make a multilingual model available locally, by pre-seeding the cache or pointing at a folder:

   ```powershell
   $env:SENTINEL_MODEL2VEC_MODEL = "C:\models\potion-multilingual-128M"
   $env:SENTINEL_SENTENCE_TRANSFORMERS_MODEL = "C:\models\paraphrase-multilingual-MiniLM-L12-v2"
   ```

   Models load with `local_files_only` and remote (`http(s)://`) references are refused. If no local model is available, the hash fallback is used silently.
3. Run `/doctor`. The check `memory embedder: semantic local (optional)` is `PASS` with the active level when a model loaded and `WARN` when the hash fallback is active; the detail names each candidate and why it is inactive. The fallback is never an error.

### Eval harness

`tests/test_evals_retrieval.py` scores each fixture with section-level golden queries over a shared distractor corpus and writes a JSON report under `tests/evals/reports/` (newest five kept; see `SENTINEL_EVAL_KEEP_REPORTS`). It compares recall@5, MRR, cross-lingual recall and distractor discrimination by backend and by embedder. With the hash fallback, same-language recall is deliberately below 1.0 and cross-lingual recall is near zero: that gap is the target a local semantic embedder should lift.
