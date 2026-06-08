# Codex Adapter

Ignite Sentinel includes repo-local Codex skills under:

```text
.codex/skills/
```

These skills provide progressive disclosure for Codex. Each skill is short and delegates deterministic work to:

```powershell
python -m sentinel ...
```

On a fresh clone, first validate the local runtime from the VS Code terminal:

```powershell
python -m sentinel /doctor
```

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
| `sentinel-backlog` | Generate backlog |
| `sentinel-quality` | Generate quality artifacts |
| `sentinel-sync` | Process changes |
| `sentinel-health` | Audit health |
| `sentinel-command-router` | Translate Ignite chat commands into CLI runs |
| `sentinel-gap-response` | Process answered discovery gaps |
| `sentinel-project-brief` | Generate or refresh project brief |
| `sentinel-domain-request` | Generate domain context requests |
| `sentinel-privacy-local-first` | Apply local-only privacy rules |

## Chat Command Router

Codex uses `AGENTS.md` plus the `sentinel-command-router` skill to interpret Ignite-style chat commands and run the matching CLI command.

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

## If Codex Is Unavailable

Use Kilo Code agents or run the CLI manually from VS Code terminal.

