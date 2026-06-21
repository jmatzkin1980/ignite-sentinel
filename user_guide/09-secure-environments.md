# Secure Environments Guide

This guide is for company laptops and client VDIs with restricted permissions.

For a concise IT/security approval note and a matrix of supported execution modes, see [Portability And IT Letter](16-portability.md) or the repo-root [PORTABILITY.md](../PORTABILITY.md).

## Portability Assumptions

Ignite Sentinel assumes:

- no admin rights;
- limited or no global installs;
- limited marketplace access;
- possible network restrictions;
- VS Code as the common surface;
- Python may be available but not always configured globally.

## Recommended Use

1. Download or clone the repository into a writable folder.
2. Open it in VS Code.
3. Run:

```powershell
python -m sentinel /doctor
```

If `python` is not exposed globally, run the repo-local launcher instead:

```powershell
.\installers\sentinel.ps1 /doctor
```

4. Use Codex skills, Kilo agents, or the CLI.

## If Git Is Blocked

Download the repository ZIP from GitHub on an approved network, then move it into the VDI or laptop through the approved channel.

## If Python Is Missing

Ask for a portable or approved Python 3.10+ runtime. Ignite does not require admin installation, but it does require a Python interpreter. If the runtime is not named `python`, set `SENTINEL_PYTHON` to the approved executable path or use the Codex Desktop bundled runtime when visible.

## If Pip Is Blocked

Use no-install mode:

```powershell
python -m sentinel /doctor
python -m sentinel /init PROJECT_ID
```

Equivalent Windows launcher form:

```powershell
.\installers\sentinel.ps1 /doctor
.\installers\sentinel.ps1 /init PROJECT_ID
```

The deterministic runtime is local-first and has no mandatory third-party package for the core lifecycle. If dependency installation is blocked, keep working in fallback mode or ask for a portable environment prepared by the team.

## If Command Execution Is Restricted In Extensions

Run CLI commands manually in the VS Code terminal and use the extension only to read/edit artifacts.

## Data Handling

- Do not put credentials or secrets in workspaces.
- Do not commit client-sensitive workspaces unless approved.
- `workspaces/` is ignored by Git by default.
- Keep the source of truth in versionable artifacts only when data classification allows it.
- Keep `main` clean so a fresh download of the repo never includes client or workflow test data.
- Use dedicated project branches for execution in laptops or VDIs, and avoid merging those branches into `main` when they contain client artifacts.

Backlog handoff surfaces have an additional local guard. Commands that hand off, validate, or mutate `04_backlog/` can scan existing backlog artifacts for credential assignments, authorization headers, non-example HTTP endpoints, email addresses, and private account/client identifiers. The default `privacy_scan.mode: warn` names the file, line, and pattern without blocking; `mode: block` makes those findings fail the command; `mode: off` skips the scan. Use `block` in repositories where backlog artifacts must never contain those values, and keep original secrets in the approved system of record outside this repository.

## Degraded Memory Mode (No LanceDB)

Some corporate laptops and client VDIs do not allow installing native packages such as `lancedb`. This is a fully supported first-class scenario, not an error:

- The entire lifecycle (`/init` ... `/validate`) works without LanceDB.
- `ContextBroker` automatically runs in deterministic `json-hybrid` mode: indexing and `/retrieve` use the local JSON memory with hash embeddings.
- `/doctor` reports `memory dependency: lancedb (optional)` and `memory backend mode` as `WARN`, with the degradation cause, and the verdict stays `PASS`.
- `/health` includes `memory_backend` and `memory_backend_degradation_reason` in `health_report.json`; this alone does not make the project `DIRTY`.
- What you lose is vector-similarity quality in `/retrieve`; lexical retrieval and all traceability remain intact.
- When the environment allows it, enable the vector layer with `python -m pip install -e .[memory]` and run `/reindex PROJECT_ID` to rebuild project memory.

## Optional Semantic Embeddings

Semantic embeddings are optional and local-only. They improve paraphrase and ES/EN retrieval when the environment allows local model packages:

```powershell
python -m pip install -e .[memory-semantic]
```

Sentinel attempts local embedders in this order:

- `model2vec` with a local multilingual static model.
- `sentence-transformers` with a local multilingual model.
- deterministic `hash_embedding` fallback.

Runtime Sentinel does not download models. For air-gapped environments, prepare the Python environment and model cache on an approved machine, transfer it through the approved channel, then point Sentinel to the local model path when needed:

```powershell
$env:SENTINEL_MODEL2VEC_MODEL="C:\approved-models\model2vec-multilingual"
$env:SENTINEL_SENTENCE_TRANSFORMERS_MODEL="C:\approved-models\multilingual-e5-small"
python -m sentinel /doctor
```

If no semantic model is available, `/doctor` reports the semantic embedder as `WARN`, keeps the overall verdict `PASS`, and retrieval continues with deterministic hash fallback. Run `/reindex PROJECT_ID` after enabling a semantic embedder so existing chunks are rebuilt with the new `embedder` and `embedding_version` metadata.
