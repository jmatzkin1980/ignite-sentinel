# Kilo Code Adapter

Ignite Sentinel includes a repo-local Kilo Code adapter under:

```text
.kilo/agents/
```

These agents mirror the Codex skills and call the same portable CLI:

```powershell
python -m sentinel ...
```

## Agents

| Agent | Purpose |
| --- | --- |
| `sentinel-discovery` | Ingest raw input and create requirements, gaps, decisions |
| `sentinel-maturity` | Evaluate readiness |
| `sentinel-specs` | Generate AI-friendly specs |
| `sentinel-backlog` | Generate backlog |
| `sentinel-quality` | Generate test coverage |
| `sentinel-sync` | Process changes and impact |
| `sentinel-health` | Run health, validation, traceability checks |

## Suggested Prompt

```text
Use the sentinel-discovery agent to ingest input/client-note.md for project ACME_DASHBOARD.
```

## Permissions

The repo includes:

```text
kilo.jsonc
.kilocodeignore
```

The config is intentionally conservative:

- write access is focused on `workspaces/**`, Sentinel runtime files, guides, and adapter files;
- `.git/**`, secrets, env files, caches, and build output are denied;
- commands default to ask unless explicitly allowed.

## In Restricted Environments

If Kilo cannot execute commands, use the VS Code terminal manually:

```powershell
python -m sentinel doctor
python -m sentinel health PROJECT_ID
```

