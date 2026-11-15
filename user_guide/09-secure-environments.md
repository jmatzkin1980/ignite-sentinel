# Secure environments: offline, locked-down and VDI use

This page is for people who run Ignite Sentinel on a company laptop or a client VDI (a virtual desktop) with restricted rights: no admin, little or no internet, blocked installs. It says what still works, what to do when something is blocked, and how client data is kept local. For the modes matrix and the note you can send to IT, see [Portability and the IT note](16-portability.md).

## What Sentinel assumes

- It needs **Python 3.10+** and a **writable folder**. Nothing else is mandatory: the core uses only the Python standard library.
- It makes **no network calls**. Client content never leaves the machine; the only network use belongs to the tools around it (your agent, GitHub, VS Code), which have their own approvals.
- Everything it produces is plain text under `workspaces/<PROJECT_ID>/`.

Pick your install on the [install page](06-installation-vscode.md); the rest of this page covers what to do when a piece is blocked.

## When something is blocked

| Blocked | What to do |
|---------|------------|
| **git** | Download the repository ZIP (or a [release](18-claude-plugin.md#without-git-the-release-archive) file) on an approved network and move it in through the approved channel. |
| **Python missing** | Ask for an approved Python 3.10+ (a portable one needs no admin rights). If it is not called `python`, set `SENTINEL_PYTHON` to its full path. |
| **pip** | Use the no-install mode below. |
| **Command execution in the agent** | Run the commands in the VS Code terminal and use the agent only to read and edit sources. |
| **PowerShell scripts** | Skip the launcher and call Python directly: `C:\approved\python.exe -m sentinel /doctor`. |
| **Internet** | Nothing in Sentinel needs it. Install extras on an approved machine and transfer them (see [offline extras](#offline-extras)). |

### No-install mode

Run from a clone or the extracted ZIP, with no `pip` at all:

```powershell
python -m sentinel /doctor
python -m sentinel /init ACME_PORTAL
python -m sentinel /ingest ACME_PORTAL --source input\client_requirement\request.md
```

On Windows, if `python` is the Microsoft Store alias, `.\installers\sentinel.ps1 /doctor` finds a real interpreter.

## Degraded memory mode (no LanceDB)

Many VDIs cannot install native packages such as LanceDB. This is a supported mode, not an error.

- The whole lifecycle, from `/init` to `/validate`, works.
- Retrieval runs in `json-hybrid` mode: lexical search over a local JSON index with a deterministic hash embedding.
- `/doctor` reports `memory dependency: lancedb (optional)` and `memory backend mode` as `WARN`, marks them as a healthy state, and the verdict stays `PASS`.
- `/health` records `memory_backend` and the reason in `health_report.json`; this alone does not make a project `DIRTY`.
- You lose vector-similarity ranking in `/retrieve`. Traceability is untouched.

To enable the vector layer later: install the `memory` extra, then run `/reindex PROJECT_ID` to rebuild the index.

## Offline extras

Each optional extra has a lock file with pinned versions and hashes in `constraints/` (`memory.txt`, `memory-semantic.txt`, `mcp.txt`). On a machine that has internet, download and verify; on the target machine, install from the copied files:

```powershell
python -m pip install --require-hashes -r constraints/memory.txt
python -m pip install --no-deps -e .
```

### Semantic embeddings

Semantic embeddings (better paraphrase and Spanish/English retrieval) are optional and local. Sentinel **never downloads a model**. It tries, in order: `model2vec` with a local multilingual model, `sentence-transformers` with a local model, then the deterministic hash fallback. Prepare the model on an approved machine, move it in, and point Sentinel at it:

```powershell
python -m pip install --require-hashes -r constraints/memory-semantic.txt
$env:SENTINEL_MODEL2VEC_MODEL="C:\approved-models\model2vec-multilingual"
$env:SENTINEL_SENTENCE_TRANSFORMERS_MODEL="C:\approved-models\multilingual-e5-small"
python -m sentinel /doctor
```

With no model available, `/doctor` shows the embedder as `WARN`, the verdict stays `PASS`, and retrieval uses the fallback. After enabling an embedder, run `/reindex PROJECT_ID` so existing chunks carry the new embedder metadata.

## Handling client data

- Never put credentials or secrets in a workspace. `/ingest` and `/sync` replace detected secrets with `<SECRETO:type>` and log each one in `01_discovery/secret_alerts.md` (type, line, fingerprint, never the value). What it detects and what it cannot is in the [threat model](19-threat-model.md#t3--secret-leakage).
- In the framework repository `workspaces/` is ignored by git, so a project never ends up in a public copy by accident. If you version your own project, see [Versioning your workspaces](10-repo-and-branching-strategy.md).
- Keep the framework's `main` branch free of client data; work on your own copy.
- **Backlog privacy scan.** Commands that hand off, validate or change `04_backlog/` scan existing backlog artifacts for credential assignments, authorization headers, non-example HTTP endpoints, email addresses and private account or client identifiers. The setting is `privacy_scan.mode` in `workspaces/<PROJECT_ID>/sentinel.config.yaml`:

  | Mode | Effect |
  |------|--------|
  | `warn` (default) | Names the file, line and pattern; does not block. |
  | `block` | Findings make the command fail. Use it where backlog files must never hold those values. |
  | `off` | Skips the scan. |

  Keep original secrets in your approved system of record, outside this repository.

## Next

- [Portability modes and the IT note](16-portability.md)
- [Install: choose your path](06-installation-vscode.md)
- [Threat model](19-threat-model.md) and [admin guide](20-admin-guide.md)
