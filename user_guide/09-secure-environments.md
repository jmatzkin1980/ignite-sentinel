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
- `/doctor` reports `memory dependency: lancedb (optional)`, `LanceDB local open/create` and `memory backend mode` as `WARN`, marks them as a healthy state, and the verdict stays `PASS`. The other optional pieces you did not install (the semantic embedder, `sentence_transformers`, `mcp`) are `WARN` too.
- `/health` records `memory_backend` and the reason in `health_report.json`; this alone does not make a project `DIRTY`.
- You lose vector-similarity ranking in `/retrieve`. Traceability is untouched.

To enable the vector layer later: install the `memory` extra, then run `/reindex PROJECT_ID` to rebuild the index.

## Offline extras

Each optional extra has a lock file with pinned versions and hashes in `constraints/` (`memory.txt`, `memory-semantic.txt`, `embeddings.txt`, `mcp.txt`; `embeddings` installs the same packages as `memory-semantic`). The usual install commands (on the [install page](06-installation-vscode.md#optional-extras)) download from PyPI, so on a machine without internet they fail. Download the files on a connected machine instead, and install from them on the target.

**1. On a machine with internet**, with the same operating system and the same Python version as the target (the lock picks different files per platform and Python version), from the clone:

```powershell
python -m pip download --require-hashes -r constraints/memory.txt -d offline-wheels
python -m pip download "setuptools>=68" wheel -d offline-wheels
```

The first command downloads every pinned package and checks each file against its hash. The second downloads the build tool that `pip install -e .` needs to install the clone itself (`pyproject.toml` declares `setuptools>=68`). It is not in the lock, so it is not hash-checked.

**2. Copy** the `offline-wheels` folder to the target machine through the approved channel, next to the clone.

**3. On the target machine**, from the clone, install with no index, only from the copied folder:

```powershell
python -m pip install --no-index --find-links offline-wheels --require-hashes -r constraints/memory.txt
python -m pip install --no-index --find-links offline-wheels --no-deps -e .
```

pip builds the clone in an isolated environment and fetches `setuptools` for it from the same folder. If `setuptools` 68 or newer is already installed in that Python, you can skip it in step 1 and add `--no-build-isolation` to the last command instead.

Swap `memory.txt` for the lock of the extra you need.

### Semantic embeddings

Semantic embeddings (better paraphrase and Spanish/English retrieval) are optional and local. Sentinel never downloads, except /setup --semantic-memory, which you run yourself and which checks every file's sha256 before using it. On a machine with no access to the model host, `/setup --semantic-memory --offline-from FOLDER` installs from a folder you prepared on an approved machine, with the same sha256 and size checks. `/setup` never pip-installs `model2vec`: if it is missing it stops before downloading and prints the pip command (with `constraints/memory-semantic.txt`), which goes through your organization's own index or proxy. Retrieval tries, in order: `model2vec` with a local multilingual model, `sentence-transformers` with a local model, then the deterministic hash fallback. Install the `memory-semantic` extra as in [offline extras](#offline-extras), with `constraints/memory-semantic.txt`. Or prepare the model yourself on an approved machine, move it in, and point Sentinel at it (these variables override the model `/setup` installed):

```powershell
$env:SENTINEL_MODEL2VEC_MODEL="C:\approved-models\model2vec-multilingual"
$env:SENTINEL_SENTENCE_TRANSFORMERS_MODEL="C:\approved-models\multilingual-e5-small"
python -m sentinel /doctor
```

With no model available, `/doctor` shows the embedder as `WARN`, the verdict stays `PASS`, and retrieval uses the fallback. After enabling an embedder, run `/reindex PROJECT_ID` so existing chunks carry the new embedder metadata.

## Handling client data

- Never put credentials or secrets in a workspace. `/ingest`, `/sync`, `/resolve-gaps` and `/harvest` replace detected secrets with `<SECRETO:type>`, and so do the commands that take an agent or BA payload (`/annotate`, `/challenge`, `/scrutinize`, `/self-review`, `/compose`, `/assume`, `/refine-backlog`, `/implementation-feedback`, and `--override` on `/validate`, `/quality` and `/backlog-status`). Each one is logged in `01_discovery/secret_alerts.md` (type, line, fingerprint, never the value). What it detects and what it cannot is in the [threat model](19-threat-model.md#t3--secret-leakage).
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
