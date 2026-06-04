# Chat Commands

This guide explains how to invoke Ignite Sentinel from VS Code chat without manually using PowerShell for every step.

Chat commands are shortcuts over the same CLI. They do not create a second workflow or a hidden state. Whether you run `/gaps PROJECT_ID` in chat or `python -m sentinel /gaps PROJECT_ID` in PowerShell, the framework mutates the same workspace artifacts and follows the same command protocol.

## Goal

The intended user experience after cloning the repository and opening the repo root in VS Code is:

```text
/doctor
/init PROJECT_ID
/ingest PROJECT_ID --source input\client_requirement\sync-guide.md
/gaps PROJECT_ID
/maturity PROJECT_ID
```

The terminal equivalent remains available:

```powershell
python -m sentinel /doctor
python -m sentinel /init PROJECT_ID
```

If `/doctor` reports missing Python dependencies, run:

```powershell
python -m pip install -e .
python -m sentinel /doctor
```

## Kilo Code

Kilo Code supports repo-local workflows stored in:

```text
.kilo/commands/
```

Each Markdown file becomes a slash command. For example:

```text
.kilo/commands/init.md -> /init
```

Use these directly in Kilo chat:

```text
/doctor
/init PROJECT_ID
/ingest PROJECT_ID --source input\client_requirement\sync-guide.md
/maturity PROJECT_ID
/gaps PROJECT_ID
/resolve-gaps PROJECT_ID --source input\interactions\answered-gaps.md
/brief PROJECT_ID
/context-request PROJECT_ID --domain technology
/status PROJECT_ID
/export PROJECT_ID --artifact gaps --format md
/sync PROJECT_ID
/sync PROJECT_ID --source input\interactions\client-answer.md --note "client response"
/retrieve PROJECT_ID --query "dashboard access and data source" --workflow discovery
/reindex PROJECT_ID
/specs PROJECT_ID
/backlog PROJECT_ID
/quality PROJECT_ID
/trace PROJECT_ID
/health PROJECT_ID
/validate PROJECT_ID
```

Fallback:

```text
/sentinel /init PROJECT_ID
```

## Codex

Codex may reserve some native slash commands depending on the surface. For that reason, the most reliable Codex chat form is:

```text
sentinel /init PROJECT_ID
sentinel /ingest PROJECT_ID --source input\client_requirement\sync-guide.md
sentinel /maturity PROJECT_ID
sentinel /resolve-gaps PROJECT_ID --source input\interactions\answered-gaps.md
```

The repo also includes instructions in `AGENTS.md` and the `sentinel-command-router` skill so Codex can translate Ignite-style chat commands into:

```powershell
python -m sentinel /COMMAND PROJECT_ID [OPTIONS]
```

If `/init PROJECT_ID` is intercepted by Codex itself, resend:

```text
sentinel /init PROJECT_ID
```

## Recommended BA Lifecycle From Chat

This lifecycle is intentionally conservative. It keeps discovery, gap resolution, brief generation, domain requests, specs, backlog, quality, and health checks as separate moments so the team can inspect each handoff.

```text
/doctor
/init PROJECT_ID
/ingest PROJECT_ID --source input\client_requirement\sync-guide.md
/gaps PROJECT_ID
/resolve-gaps PROJECT_ID --source input\interactions\answered-gaps.md
/maturity PROJECT_ID
/brief PROJECT_ID
/context-request PROJECT_ID --domain technology
/context-request PROJECT_ID --domain design
/sync PROJECT_ID
/maturity PROJECT_ID
/status PROJECT_ID
/health PROJECT_ID
/specs PROJECT_ID
/backlog PROJECT_ID
/quality PROJECT_ID
/trace PROJECT_ID
/validate PROJECT_ID
```

For Codex, prefix each line with `sentinel` when needed.

## Practical Rule

Use chat commands for normal BA flow. Use PowerShell only when:

- the extension cannot execute commands due to environment policy;
- the chat surface reserves a slash command;
- you need to debug Python/runtime availability;
- you want to run tests or Git operations manually.
