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
python -m sentinel doctor
```

4. Use Codex skills, Kilo agents, or the CLI.

## If Git Is Blocked

Download the repository ZIP from GitHub on an approved network, then move it into the VDI or laptop through the approved channel.

## If Python Is Missing

Ask for a portable or approved Python 3.10+ runtime. Ignite does not require admin installation, but it does require a Python interpreter.

## If Pip Is Blocked

Use no-install mode:

```powershell
python -m sentinel doctor
python -m sentinel init PROJECT_ID
```

The MVP core uses only the Python standard library.

## If Command Execution Is Restricted In Extensions

Run CLI commands manually in the VS Code terminal and use the extension only to read/edit artifacts.

## Data Handling

- Do not put credentials or secrets in workspaces.
- Do not commit client-sensitive workspaces unless approved.
- `workspaces/` is ignored by Git by default.
- Keep the source of truth in versionable artifacts only when data classification allows it.

