---
name: sentinel-command-router
description: Use when the user sends an Ignite Sentinel chat command such as /init PROJECT_ID, /ingest PROJECT_ID --source PATH, or sentinel /health PROJECT_ID, and wants the command executed from chat instead of typing in a terminal.
---

# Sentinel Command Router

Translate short chat commands into Sentinel CLI executions.

## Accepted Forms

- `/doctor`
- `/init PROJECT_ID`
- `/ingest PROJECT_ID --source PATH`
- `/maturity PROJECT_ID`
- `/sync PROJECT_ID --source PATH --note "NOTE"`
- `/retrieve PROJECT_ID --query "TEXT" --workflow WORKFLOW`
- `/reindex PROJECT_ID`
- `/specs PROJECT_ID`
- `/backlog PROJECT_ID`
- `/quality PROJECT_ID`
- `/trace PROJECT_ID`
- `/health PROJECT_ID`
- `/validate PROJECT_ID`
- `sentinel /COMMAND PROJECT_ID [OPTIONS]`
- `ignite /COMMAND PROJECT_ID [OPTIONS]`

## Execution

1. Parse the command name, project ID, and options from the user message.
2. Run from the repository root:

```powershell
python -m sentinel /COMMAND PROJECT_ID [OPTIONS]
```

For `/doctor`, omit `PROJECT_ID`.

3. If `python` is unavailable, use the configured or bundled Codex Python runtime when visible.
4. Return a concise summary of the CLI result and point to generated artifacts.

## Routing

- `/init`, `/ingest`: use `sentinel-discovery` guidance after execution.
- `/maturity`: use `sentinel-maturity`.
- `/sync`, `/retrieve`, `/reindex`: use `sentinel-sync`.
- `/specs`: use `sentinel-specs`.
- `/backlog`: use `sentinel-backlog`.
- `/quality`: use `sentinel-quality`.
- `/health`, `/trace`, `/validate`, `/doctor`: use `sentinel-health`.

## Safety

- Do not edit generated workspace artifacts by hand unless the user explicitly asks for a manual correction.
- After manual edits to workspace `.md` or `.txt` artifacts, run `/reindex PROJECT_ID` so LanceDB memory matches the versionable files.
- Before executing a task that depends on project context, prefer `/retrieve PROJECT_ID --query "TEXT" --workflow WORKFLOW --write-pack` over loading the whole workspace.
- Do not commit project workspace data unless explicitly approved.
- If a Codex UI intercepts `/init` or another slash command before it reaches the agent, tell the user to send `sentinel /init PROJECT_ID`.

## Memory

- Ignite Sentinel stores local retrieval memory in `workspaces/PROJECT_ID/memory.lancedb/`.
- LanceDB is the primary backend; source files remain the source of truth.
- `/ingest`, `/sync`, and `/reindex` keep memory available for Codex and Kilo Code workflows.
