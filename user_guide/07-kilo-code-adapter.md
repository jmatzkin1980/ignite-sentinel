# Kilo Code Adapter

Ignite Sentinel includes a repo-local Kilo Code adapter under:

```text
.kilo/agents/
```

These agents mirror the Codex skills and call the same portable CLI:

```powershell
python -m sentinel ...
```

Before relying on Kilo chat commands in a freshly cloned repository, run the setup check from Kilo chat:

```text
/doctor
```

If LanceDB or another dependency is missing:

```powershell
python -m pip install -e .
python -m sentinel /doctor
```

## Agents

| Agent | Purpose |
| --- | --- |
| `sentinel-discovery` | Ingest raw input and create requirements, gaps, decisions |
| `sentinel-maturity` | Evaluate readiness |
| `sentinel-specs` | Generate AI-friendly specs |
| `sentinel-backlog` | Generate epics, stories, acceptance criteria, retrieval plans, and implementation readiness pack |
| `sentinel-quality` | Generate test coverage |
| `sentinel-sync` | Process changes and impact |
| `sentinel-health` | Run health, validation, traceability checks, including stale domain context detection |

Kilo agents use the same local LanceDB memory layer as Codex. `/ingest`, `/sync`, and `/reindex` keep `workspaces/[PROJECT_ID]/memory.lancedb/` populated, while `/retrieve` builds focused context packs for the active workflow.

If the VS Code environment cannot resolve `python`, use the repo-local launcher from the terminal or from the generic `/sentinel` workflow when allowed:

```powershell
.\installers\sentinel.ps1 /doctor
.\installers\sentinel.ps1 /status PROJECT_ID
```

The launcher preserves the same CLI contract and only changes how the Python runtime is found.

When Kilo generates backlog, review both:

```text
workspaces/[PROJECT_ID]/08_context_packs/backlog_generation.json
workspaces/[PROJECT_ID]/08_context_packs/implementation_readiness.json
```

If `/health` reports that domain context changed after backlog generation, run `/reindex PROJECT_ID` and retrieve focused context before handing work to implementation or test agents. Rerun `/backlog PROJECT_ID` only when the change materially affects story scope, sequencing, acceptance criteria, dependencies, or execution contracts.

## Slash Workflows

Kilo Code supports repo-local workflows in `.kilo/commands/`. In this repo, those workflows let you type short Ignite commands directly in Kilo chat.

Non-technical users can also describe the situation in plain language. Kilo should use the matching Sentinel agent or command workflow and then summarize the generated artifacts and next step.

Examples:

```text
/doctor
/init ACME_DASHBOARD
/ingest ACME_DASHBOARD --source input\client_requirement\sync-guide.md
/gaps ACME_DASHBOARD
/resolve-gaps ACME_DASHBOARD --source input\interactions\answered-gaps.md
/maturity ACME_DASHBOARD
/brief ACME_DASHBOARD
/context-request ACME_DASHBOARD --domain technology
/status ACME_DASHBOARD
/sync ACME_DASHBOARD --source input\interactions\client-answer.md --note "client follow-up"
/retrieve ACME_DASHBOARD --query "client gap response" --workflow sync
/specs ACME_DASHBOARD
/backlog ACME_DASHBOARD
/quality ACME_DASHBOARD
/trace ACME_DASHBOARD
/health ACME_DASHBOARD
/validate ACME_DASHBOARD
```

If a command name conflicts with the chat surface, use the generic fallback:

```text
/sentinel /init ACME_DASHBOARD
```

## Suggested Prompt

```text
Use the sentinel-discovery agent to ingest input/client-note.md for project ACME_DASHBOARD.
```

Other plain-language examples:

```text
The client answered gaps in input\interactions\answered-gaps.md.
Process them for ACME_DASHBOARD and tell me whether discovery is ready for a brief.
```

```text
Generate backlog for ACME_DASHBOARD and tell me whether any story still needs Technology, Design, or Quality context.
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
- known Sentinel commands are allowlisted in `kilo.jsonc`;
- commands default to ask unless explicitly allowed.

If a new Sentinel command is added later, update both `.kilo/commands/` and `kilo.jsonc` so a cloned laptop gets the same chat experience.

## In Restricted Environments

If Kilo cannot execute commands, use the VS Code terminal manually:

```powershell
python -m sentinel /doctor
python -m sentinel /retrieve PROJECT_ID --query "topic" --workflow sync --write-pack
python -m sentinel /health PROJECT_ID
```

If `python` is unavailable in that terminal, use:

```powershell
.\installers\sentinel.ps1 /doctor
.\installers\sentinel.ps1 /health PROJECT_ID
```

