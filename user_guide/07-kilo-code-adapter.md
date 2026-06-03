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

Kilo agents use the same local LanceDB memory layer as Codex. `/ingest`, `/sync`, and `/reindex` keep `workspaces/[PROJECT_ID]/memory.lancedb/` populated, while `/retrieve` builds focused context packs for the active workflow.

## Slash Workflows

Kilo Code supports repo-local workflows in `.kilo/commands/`. In this repo, those workflows let you type short Ignite commands directly in Kilo chat.

Examples:

```text
/doctor
/init TESORO_CIERRE_FORZADO
/ingest TESORO_CIERRE_FORZADO --source input\client_requirement\sync-guide.md
/maturity TESORO_CIERRE_FORZADO
/sync TESORO_CIERRE_FORZADO --source input\interactions\client-answer.md --note "client gap response"
/retrieve TESORO_CIERRE_FORZADO --query "client gap response" --workflow sync
/specs TESORO_CIERRE_FORZADO
/backlog TESORO_CIERRE_FORZADO
/quality TESORO_CIERRE_FORZADO
/trace TESORO_CIERRE_FORZADO
/health TESORO_CIERRE_FORZADO
/validate TESORO_CIERRE_FORZADO
```

If a command name conflicts with the chat surface, use the generic fallback:

```text
/sentinel /init TESORO_CIERRE_FORZADO
```

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
python -m sentinel /doctor
python -m sentinel /retrieve PROJECT_ID --query "topic" --workflow sync --write-pack
python -m sentinel /health PROJECT_ID
```

