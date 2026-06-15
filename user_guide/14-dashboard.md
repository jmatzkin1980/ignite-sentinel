# Dashboard

`/dashboard` creates a local, read-only portfolio view across every Sentinel workspace under `workspaces/`. It is meant for BA/Product review moments when you want to see phase, health, gaps, generated documents, backlog readiness, and recommended next steps without opening many Markdown files.

Run it from the repository root:

```powershell
python -m sentinel /dashboard
```

It writes:

```text
dashboard.html
```

The file is self-contained and opens offline. It is intentionally git-ignored because it can embed local workspace Markdown. Treat it as a rebuildable snapshot, not as source of truth.

## From Chat

You can ask for it in natural language:

```text
Mostrame el estado de los workspaces.
```

```text
Show me the Sentinel dashboard and summarize what needs attention.
```

The agent should run `/dashboard`, report the generated path, summarize the portfolio signals, and stop before running any mutating lifecycle command unless you explicitly ask for the next action.

Codex-safe exact form:

```text
sentinel /dashboard
```

## How To Read It

- Portfolio cards show totals and attention signals across workspaces.
- Workspace rows show phase, health, language, privacy mode, maturity, gaps, backlog rollup, warnings, and next step.
- Lifecycle stages help you see whether a workspace is still in discovery, moving through specs, or ready for backlog/implementation review.
- Gaps can be copied for client/domain follow-up.
- Documents open in the dashboard for quick review, but the canonical files still live under each workspace.

## Guardrails

- Read-only: the dashboard never mutates workspaces.
- Local-first: no remote rendering, no external services, and no network calls.
- Rebuildable: rerun `/dashboard` whenever workspace state changes.
- Governed: follow-up changes still go through lifecycle commands such as `/resolve-gaps`, `/sync`, `/story-status`, `/health`, or `/validate`.
