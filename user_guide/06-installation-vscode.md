# VS Code Portable Installation

Ignite Sentinel is designed to run from the cloned repository. This is the safest path for company laptops and client VDIs where admin rights, global installs, and marketplace access may be restricted.

This page is the onboarding checklist for a new laptop. If the framework evolves, keep this checklist and `/doctor` aligned.

## What Must Be Installed

Required:

- VS Code, if you want the editor workflow.
- Kilo Code extension, if you want repo-local slash commands and agents.
- Python 3.10 or newer available as `python`, `py`, `.venv`, `SENTINEL_PYTHON`, the Codex Desktop bundled runtime, or another approved local runtime.
- The Python package dependencies from `pyproject.toml`.

Required for LanceDB memory:

- `lancedb` installed in the same Python environment used to run `python -m sentinel`.

Optional:

- `sentence-transformers`, only if a future local semantic embedding workflow is enabled. Sentinel currently keeps a deterministic local hash fallback.

No remote MCP, external vector database, or external embedding service is required for the default local-first workflow.

## Recommended Setup

1. Clone or download the repository.

```powershell
git clone <REPO_URL>
cd ignite-sentinel
```

If Git is unavailable, download the repository ZIP from GitHub and extract it to a writable folder.

2. Open the folder in VS Code.

```powershell
code .
```

3. Open Kilo Code chat, Codex in VS Code, or Codex Desktop and run the portable doctor.

Kilo Code:

```text
/doctor
```

Codex:

```text
sentinel /doctor
```

Plain-language option:

```text
Check whether Ignite Sentinel is ready to use on this machine.
```

Terminal fallback:

```powershell
python -m sentinel /doctor
```

Windows portable launcher:

```powershell
.\installers\sentinel.ps1 /doctor
```

Unix-like portable launcher:

```sh
sh installers/sentinel.sh /doctor
```

`/doctor` checks the runtime, repo structure, `AGENTS.md`, Codex skills and hooks, Kilo agents and slash commands, portable launchers, write access, required dependencies, and whether LanceDB can create a local table in a temporary folder.

4. Start a workspace from chat.

Kilo Code:

```text
/init DEMO_PROJECT
```

Codex:

```text
sentinel /init DEMO_PROJECT
```

Plain-language option:

```text
Create a demo Sentinel project called DEMO_PROJECT.
```

Terminal fallback:

```powershell
python -m sentinel /init DEMO_PROJECT
```

Portable launcher fallback:

```powershell
.\installers\sentinel.ps1 /init DEMO_PROJECT
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

If `python` resolves to the Windows Microsoft Store alias instead of a real interpreter, prefer:

```powershell
.\installers\sentinel.ps1 /doctor
```

That launcher validates candidates before using them and skips invalid aliases.

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
3. Open Kilo Code chat, Codex in VS Code, or Codex Desktop.
4. Run `/doctor` in Kilo or `sentinel /doctor` in Codex.
5. If LanceDB fails, ask a technical teammate to run `python -m pip install -e .` or use the approved local installer.
6. Run `/init DEMO_PROJECT` in Kilo or `sentinel /init DEMO_PROJECT` in Codex.
7. Try `/status DEMO_PROJECT` in Kilo or `sentinel /status DEMO_PROJECT` in Codex.
8. If slash commands are intercepted, use `sentinel /status DEMO_PROJECT`, `.\installers\sentinel.ps1 /status DEMO_PROJECT`, or the terminal fallback.

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

Use `py -m sentinel /doctor` if the Windows Python launcher is available, run `.\installers\sentinel.ps1 /doctor`, set `SENTINEL_PYTHON` to an approved runtime, or install/expose Python 3.10+.

### Kilo Does Not Run A Command

Check that the repo root is open in VS Code and that `kilo.jsonc`, `.kilo/agents/`, and `.kilo/commands/` are visible. If the command is not allowed automatically, Kilo may ask for approval because the config defaults to ask for unknown commands.

## Daily Use

Use chat commands for everyday work:

```text
/ingest PROJECT_ID --source input\client-note.md
/gaps PROJECT_ID
/resolve-gaps PROJECT_ID --source input\interactions\answered-gaps.md
/maturity PROJECT_ID
/brief PROJECT_ID
/specs PROJECT_ID
/backlog PROJECT_ID
/quality PROJECT_ID
/health PROJECT_ID
```

For Codex, prefix each command with `sentinel` if needed.

Plain-language daily use also works:

```text
I received new client notes at input\client-note.md.
Ingest them for PROJECT_ID, regenerate gaps, and tell me the next recommended step.
```
