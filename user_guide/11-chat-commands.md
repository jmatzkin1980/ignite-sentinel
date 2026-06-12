# Chat Commands

This guide explains how to invoke Ignite Sentinel from VS Code chat without manually using PowerShell for every step.

Chat commands are shortcuts over the same CLI. They do not create a second workflow or a hidden state. Whether you run `/gaps PROJECT_ID` in chat or `python -m sentinel /gaps PROJECT_ID` in PowerShell, the framework mutates the same workspace artifacts and follows the same command protocol.

Users do not need to memorize every command. They can either type a command or explain the situation in plain language. The agent should translate the request into the right Sentinel command sequence and summarize what changed.

## Intent-To-Command Map

When the user describes a situation instead of typing a command, the agent should map the intent to the right lifecycle sequence. Canonical patterns:

| User intent (plain language) | Command sequence | Notes |
| --- | --- | --- |
| "I have a new client requirement in this file" | `/init` → `/ingest` → `/status` | Summarize generated gaps and evidence triggers. |
| "I read the requirement and spotted gaps the checklist missed" | `/annotate --source analysis.json` → `/status` | Agent proposes semantic gaps with verbatim citations; runtime tags them `origin: agent` and merges. |
| "Stress-test the requirement — what are we not asking?" / "run a pre-mortem" | `/challenge --source findings.json` → `/status` | Agent runs pre-mortem, per-lens role-play, and assumption inversion; runtime validates and merges findings as `origin: challenge` plus a `challenge_report.md`. |
| "The client answered the gaps document" | `/resolve-gaps` → `/maturity` → `/status` | Report closed / answered / partially-closed with notes; for functional prose answers, mention any `EARS-eligible, not normalized` count and propose a BA-confirmed EARS rewrite. |
| "Is this requirement ready to move forward?" | `/maturity` → `/status` | Quote `maturity_score` and `trend_vs_previous_run`. |
| "Generate the brief / crystallize discovery" | `/brief` → `/status` | Only meaningful after blocking gaps are resolved. |
| "Technology/Design/Quality updated their context" | `/sync` → `/reindex` → `/health` | If backlog exists, expect a staleness warning naming the domain. |
| "I received meeting notes / an email with changes" | `/sync --source PATH --note "..."` → `/health` | Check `07_changes/04_regeneration/` after regenerating. |
| "Ask Technology/Design for their input" | `/context-request --domain DOMAIN` | One request file per domain under `08_context_packs/requests/`. |
| "Generate PRD and specs" | `/specs` → `/validate` | Report `semantic_quality` classification per artifact. |
| "Prepare the backlog for implementation handoff" | `/backlog` → `/quality` → `/trace` → `/health` → `/validate` | Only when gates allow; report `readiness_score` summary. |
| "What changed since the backlog was generated?" | `/health` | Staleness finding names the changed domains. |
| "Is the framework healthy on this machine?" | `/doctor` | LanceDB missing is WARN (degraded mode), not failure. |

Rules for any agent surface: respect gates (never force a blocked command — explain why and recommend the prior step), mutate artifacts only through the CLI, and end every interaction with generated artifacts, gap/health state, and the recommended next step.

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

If the machine does not expose a valid `python`, use the repo-local launcher:

```powershell
.\installers\sentinel.ps1 /doctor
.\installers\sentinel.ps1 /init PROJECT_ID
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

Plain-language Kilo examples:

```text
I have a new client requirement in input\client_requirement\initial-request.md.
Create PROJECT_ID, ingest the file, and tell me what gaps were found.
```

```text
The client answered gaps in input\interactions\answered-gaps.md.
Process the answers, check maturity, and tell me whether we can generate the brief.
```

For functional gaps, if `/status` reports `ears_eligible_not_normalized_total`, propose EARS statements separately and wait for BA confirmation before treating them as normalized requirements.

```text
Technology updated context files for PROJECT_ID.
Refresh memory and check whether the backlog is stale.
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

When `python` is unavailable in Codex Desktop or VS Code, the router may use:

```powershell
.\installers\sentinel.ps1 /COMMAND PROJECT_ID [OPTIONS]
```

If `/init PROJECT_ID` is intercepted by Codex itself, resend:

```text
sentinel /init PROJECT_ID
```

Plain-language Codex examples:

```text
Use Ignite Sentinel to create PROJECT_ID from input\client_requirement\initial-request.md.
Run the needed commands and summarize the resulting status.
```

```text
For PROJECT_ID, generate the PRD/specs if maturity allows it.
If something blocks the workflow, explain the blocker and the next action.
```

```text
For PROJECT_ID, generate backlog and implementation readiness.
Then tell me which stories still need domain context.
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

Plain-language equivalent:

```text
Guide PROJECT_ID through the normal Sentinel lifecycle.
Start with discovery and gaps, stop at each maturity or health gate, and summarize the next recommended action after each step.
```

## Practical Rule

Use chat commands for normal BA flow. Use PowerShell only when:

- the extension cannot execute commands due to environment policy;
- the chat surface reserves a slash command;
- you need to debug Python/runtime availability;
- you want to run tests or Git operations manually.
