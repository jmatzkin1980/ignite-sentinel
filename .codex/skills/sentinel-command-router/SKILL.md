---
name: sentinel-command-router
description: "Use when the user sends an Ignite Sentinel chat command such as /init PROJECT_ID, /dashboard, /ingest PROJECT_ID --source PATH, or sentinel /health PROJECT_ID, and wants the command executed from chat instead of typing in a terminal."
---

# Sentinel Command Router

Translate short chat commands into Sentinel CLI executions.

## Accepted Forms

- `/doctor`
- `/dashboard`
- `/init PROJECT_ID`
- `/ingest PROJECT_ID --source PATH`
- `/maturity PROJECT_ID`
- `/gaps PROJECT_ID`
- `/annotate PROJECT_ID --source ANALYSIS.json`
- `/challenge PROJECT_ID --source ANALYSIS.json`
- `/scrutinize PROJECT_ID --source ANALYSIS.json [--lens LENS] [--mode implementability-probe]`
- `/assume PROJECT_ID --source ASSUMPTIONS.json`
- `/resolve-gaps PROJECT_ID --source PATH`
- `/brief PROJECT_ID`
- `/context-request PROJECT_ID --domain technology|design|quality|frontend|backend`
- `/status PROJECT_ID`
- `/export PROJECT_ID --artifact gaps|brief|context-request|prd --format md`
- `/export PROJECT_ID --artifact prd --format mdx`
- `/export PROJECT_ID --artifact gaps --format interview`
- `/export PROJECT_ID --artifact gaps --format faq`
- `/view PROJECT_ID --artifact gaps|brief|prd|specs|backlog [--open]`
- `/sync PROJECT_ID`
- `/sync PROJECT_ID --source PATH --note "NOTE"`
- `/retrieve PROJECT_ID --query "TEXT" --workflow WORKFLOW`
- `/reindex PROJECT_ID`
- `/specs PROJECT_ID`
- `/self-review PROJECT_ID --source FINDINGS.json`
- `/compose PROJECT_ID --source PATH`
- `/backlog PROJECT_ID`
- `/backlog PROJECT_ID --with-task-seeds`
- `/backlog-status PROJECT_ID`
- `/story-status PROJECT_ID --story US-NNN --set STATE [--owner "NAME"] [--evidence PATH]`
- `/refine-backlog PROJECT_ID --source PROPOSALS.json`
- `/implementation-feedback PROJECT_ID --source PATH`
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

For `/doctor` and `/dashboard`, omit `PROJECT_ID`. `/dashboard` accepts `--root PATH` and `--open`. `/view` requires `PROJECT_ID` and writes a derived read-only HTML snapshot under `08_context_packs/views/`.

3. If `python` is unavailable, use the configured or bundled Codex Python runtime when visible, or the repo-local launcher:

```powershell
.\installers\sentinel.ps1 /COMMAND PROJECT_ID [OPTIONS]
```

4. Return a concise summary of the CLI result and point to generated artifacts.

The CLI applies the Sentinel vNext command protocol automatically: preflight guard, command execution, trace refresh for mutating commands, and a command anchor in `workspaces/PROJECT_ID/06_traceability/command_protocol_log.md`.

## Routing

- `/init`, `/ingest`, `/gaps`: use `sentinel-discovery` guidance after execution.
- `/annotate`: use `sentinel-annotate` to author the analysis JSON before executing.
- `/challenge`: use `sentinel-challenge` to author the findings JSON before executing.
- `/scrutinize` (both modes): use `sentinel-scrutiny` to author the findings JSON before executing.
- `/assume`: use `sentinel-assume` to author the assumptions JSON before executing.
- `/resolve-gaps`: use `sentinel-gap-response`.
- `/maturity`: use `sentinel-maturity`.
- `/brief`: use `sentinel-project-brief`.
- `/context-request`: use `sentinel-domain-request`.
- `/sync`, `/retrieve`, `/reindex`: use `sentinel-sync`.
- `/dashboard`: use `sentinel-dashboard`.
- `/specs`: use `sentinel-specs`.
- `/self-review`: use `sentinel-self-review` to author the cited findings/decisions JSON before executing.
- `/compose`: use `sentinel-compose`.
- `/backlog`, `/backlog-status`, `/story-status`: use `sentinel-backlog` (lifecycle and board rules live there).
- `/refine-backlog`: use `sentinel-backlog-refine`; proposals land as cited agent-origin overlays, never direct rewrites.
- `/implementation-feedback`: use `sentinel-implementation-feedback`; accepted findings are traced feedback, not direct backlog rewrites.
- `/quality`: use `sentinel-quality`.
- `/health`, `/trace`, `/validate`, `/view`, `/doctor`: use `sentinel-health`.
- `/status`, `/export`: summarize the CLI result and generated artifact path.

## Safety

- Never edit generated workspace artifacts by hand; mutation flows only through Sentinel commands. If the user insists on a manual correction, warn that `/health` will flag the out-of-CLI edit and recommend the owning command instead.
- Do not close gaps manually when a structured client response can be processed with `/resolve-gaps`.
- After source inputs change (files under `00_raw/` context folders or new client material), run `/reindex PROJECT_ID` so memory matches the versionable files.
- Before executing a task that depends on project context, prefer `/retrieve PROJECT_ID --query "TEXT" --workflow WORKFLOW --write-pack` over loading the whole workspace.
- Do not commit project workspace data unless explicitly approved.
- If a Codex UI intercepts `/init` or another slash command before it reaches the agent, tell the user to send `sentinel /init PROJECT_ID`.

## Memory

- Ignite Sentinel stores local retrieval memory in `workspaces/PROJECT_ID/memory.lancedb/`.
- LanceDB is the primary backend; source files remain the source of truth.
- `/ingest`, `/sync`, and `/reindex` keep memory available for Codex and Kilo Code workflows.
- Privacy mode is local-only: do not route client code or project data through remote MCP or external embedding services.

## Intent Mapping

When the user describes a situation instead of a command, use the Intent-To-Command Map in `user_guide/11-chat-commands.md`: new input → init/ingest/status; answered gaps → resolve-gaps/maturity/status; domain updates → sync/reindex/health; downstream handoff → specs/backlog/quality/trace/health/validate when gates allow. Always close with artifacts generated, gap/health state, and next step.
