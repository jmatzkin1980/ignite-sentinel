# Codex Adapter

Ignite Sentinel includes repo-local Codex skills under:

```text
.codex/skills/
```

These skills provide progressive disclosure for Codex. Each skill is short and delegates deterministic work to:

```powershell
python -m sentinel ...
```

On a fresh clone, first validate the local runtime from Codex chat:

```text
sentinel /doctor
```

Codex Desktop or VS Code terminal fallback on Windows:

```powershell
.\installers\sentinel.ps1 /doctor
```

The launcher tries `SENTINEL_PYTHON`, `.venv`, `python`, `py`, and the Codex Desktop bundled runtime when visible. This keeps the same Sentinel CLI behavior even when the laptop does not expose `python` in `PATH`.

If dependencies are missing:

```powershell
python -m pip install -e .
python -m sentinel /doctor
```

## Skills

| Skill | Purpose |
| --- | --- |
| `sentinel-discovery` | Ingest raw input and create requirements/gaps/decisions |
| `sentinel-maturity` | Evaluate maturity gates |
| `sentinel-specs` | Generate specs |
| `sentinel-backlog` | Generate backlog, retrieval plans, and implementation readiness handoff |
| `sentinel-quality` | Generate quality artifacts |
| `sentinel-sync` | Process changes |
| `sentinel-health` | Audit health, validation risks, and stale domain context |
| `sentinel-command-router` | Translate Ignite chat commands into CLI runs |
| `sentinel-gap-response` | Process answered discovery gaps |
| `sentinel-project-brief` | Generate or refresh project brief |
| `sentinel-domain-request` | Generate domain context requests |
| `sentinel-privacy-local-first` | Apply local-only privacy rules |

## Chat Command Router

Codex uses `AGENTS.md` plus the `sentinel-command-router` skill to interpret Ignite-style chat commands and run the matching CLI command.

Codex can also work from plain-language requests. The user may describe the situation, and Codex should choose the right Sentinel command sequence, run it, and summarize the outputs and next step.

Recommended Codex chat form:

```text
sentinel /init ACME_DASHBOARD
sentinel /ingest ACME_DASHBOARD --source input\client_requirement\sync-guide.md
sentinel /gaps ACME_DASHBOARD
sentinel /resolve-gaps ACME_DASHBOARD --source input\interactions\answered-gaps.md
sentinel /maturity ACME_DASHBOARD
sentinel /brief ACME_DASHBOARD
sentinel /context-request ACME_DASHBOARD --domain technology
sentinel /status ACME_DASHBOARD
sentinel /specs ACME_DASHBOARD
sentinel /backlog ACME_DASHBOARD
sentinel /quality ACME_DASHBOARD
sentinel /trace ACME_DASHBOARD
sentinel /health ACME_DASHBOARD
sentinel /validate ACME_DASHBOARD
```

The shorter form may also work if the Codex surface does not reserve that slash command:

```text
/init ACME_DASHBOARD
```

If Codex intercepts `/init` or another slash command as a native Codex command, resend it with the `sentinel` prefix.

## Suggested Prompt

```text
Use sentinel-maturity to evaluate ACME_DASHBOARD and explain what blocks specs generation.
```

More plain-language examples:

```text
I received new client input at input\client_requirement\initial-request.md.
Create project ACME_DASHBOARD, ingest it, and explain the open gaps.
```

```text
Technology and Design updated their context files for ACME_DASHBOARD.
Refresh memory, check health, and tell me whether backlog must be regenerated.
```

## Hooks

Optional hooks live in:

```text
.codex/hooks/
```

They are guardrails and reminders. The primary enforcement layer remains:

```powershell
python -m sentinel /validate PROJECT_ID
python -m sentinel /health PROJECT_ID
```

For backlog handoff, Codex should inspect:

```text
workspaces/[PROJECT_ID]/04_backlog/EPIC-001.md
workspaces/[PROJECT_ID]/08_context_packs/backlog_generation.json
workspaces/[PROJECT_ID]/08_context_packs/implementation_readiness.json
```

If domain context changed after backlog generation, run `/reindex` and `/backlog` before planning or implementing stories.

## If Codex Is Unavailable

Use Kilo Code agents or run the CLI manually from VS Code terminal. On Windows machines without a valid `python`, run the same commands through `.\installers\sentinel.ps1`.

