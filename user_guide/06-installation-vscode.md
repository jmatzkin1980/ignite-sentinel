# VS Code Portable Installation

Ignite Sentinel is designed to run from the cloned repository. This is the safest path for company laptops and client VDIs where admin rights, global installs, and marketplace access may be restricted.

This page is the onboarding checklist for a new laptop. If the framework evolves, keep this checklist and `/doctor` aligned.

## What Must Be Installed

Required:

- VS Code, if you want the editor workflow.
- Kilo Code extension, if you want repo-local slash commands and agents.
- Python 3.10 or newer available as `python`, `py`, or an approved local runtime.
- The Python package dependencies from `pyproject.toml`.

Required for LanceDB memory:

- `lancedb` installed in the same Python environment used to run `python -m sentinel`.

Optional:

- `sentence-transformers`, only if a future local semantic embedding workflow is enabled. Sentinel currently keeps a deterministic local hash fallback.

No remote MCP, external vector database, or external embedding service is required for the default local-first workflow.

## Recommended Setup

1. Clone or download the repository.

```powershell
git clone https://github.com/jmatzkin1980/ignite-sentinel.git
cd ignite-sentinel
```

If Git is unavailable, download the repository ZIP from GitHub and extract it to a writable folder.

2. Open the folder in VS Code.

```powershell
code .
```

3. Run the portable doctor.

```powershell
python -m sentinel /doctor
```

`/doctor` checks the runtime, repo structure, Kilo/Codex adapter files, write access, required dependencies, and whether LanceDB can create a local table in a temporary folder.

4. Start a workspace.

```powershell
python -m sentinel /init DEMO_PROJECT
```

## No-Install Mode

Use this mode first in securitized environments:

```powershell
python -m sentinel --help
python -m sentinel /doctor
```

No global package install is required if the laptop already has the dependencies available in the active Python environment. If `/doctor` reports `required dependency: lancedb` as `FAIL`, install the repo locally:

```powershell
python -m pip install -e .
python -m sentinel /doctor
```

## Optional Local Venv

Use only if your environment allows local virtual environments:

```powershell
.\installers\install.ps1 -CreateVenv
```

Or on Unix-like shells:

```sh
sh installers/install.sh --venv
```

The local venv path is intentionally repo-local. It avoids global Python changes and keeps client/VDI environments easier to audit.

## VS Code Extension Usage

Ignite works through repo-local files:

- Codex reads `.codex/skills/`.
- Kilo Code reads `.kilo/agents/`.
- Kilo Code slash workflows live in `.kilo/commands/`.
- Kilo Code permissions live in `kilo.jsonc`.
- The CLI works even without either extension.

## New Laptop Checklist

1. Clone or extract the repo into a writable folder.
2. Open the folder itself in VS Code, not only a subfolder.
3. Confirm Kilo Code is enabled.
4. Run `python -m sentinel /doctor`.
5. If LanceDB fails, run `python -m pip install -e .` or the approved local installer.
6. Run `python -m sentinel /init DEMO_PROJECT`.
7. In Kilo chat, try `/status DEMO_PROJECT`.
8. If slash commands are intercepted, use `/sentinel /status DEMO_PROJECT` or run the CLI in the terminal.

## Troubleshooting

### `No module named lancedb`

Install the repo dependencies in the active Python environment:

```powershell
python -m pip install -e .
```

Then rerun:

```powershell
python -m sentinel /doctor
```

### `python` Is Not Recognized

Use `py -m sentinel /doctor` if the Windows Python launcher is available, or install/expose an approved Python 3.10+ runtime.

### Kilo Does Not Run A Command

Check that the repo root is open in VS Code and that `kilo.jsonc`, `.kilo/agents/`, and `.kilo/commands/` are visible. If the command is not allowed automatically, Kilo may ask for approval because the config defaults to ask for unknown commands.

## Daily Use

```powershell
python -m sentinel /ingest PROJECT_ID --source input\client-note.md
python -m sentinel /gaps PROJECT_ID
python -m sentinel /resolve-gaps PROJECT_ID --source input\interactions\answered-gaps.md
python -m sentinel /maturity PROJECT_ID
python -m sentinel /brief PROJECT_ID
python -m sentinel /specs PROJECT_ID
python -m sentinel /backlog PROJECT_ID
python -m sentinel /quality PROJECT_ID
python -m sentinel /health PROJECT_ID
```
