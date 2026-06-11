# Secure Environments Guide

This guide is for company laptops and client VDIs with restricted permissions.

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

The deterministic runtime is local-first, but LanceDB is a required package for the current memory check. If dependency installation is blocked, keep working from an approved Python environment that already includes the dependencies, or ask for a portable environment prepared by the team.

## If Command Execution Is Restricted In Extensions

Run CLI commands manually in the VS Code terminal and use the extension only to read/edit artifacts.

## Data Handling

- Do not put credentials or secrets in workspaces.
- Do not commit client-sensitive workspaces unless approved.
- `workspaces/` is ignored by Git by default.
- Keep the source of truth in versionable artifacts only when data classification allows it.
- Keep `main` clean so a fresh download of the repo never includes client or workflow test data.
- Use dedicated project branches for execution in laptops or VDIs, and avoid merging those branches into `main` when they contain client artifacts.

