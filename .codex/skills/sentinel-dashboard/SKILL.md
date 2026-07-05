---
name: sentinel-dashboard
description: "Use when generating, opening, presenting, or interpreting the Ignite Sentinel workspace dashboard; when the user asks for project status, portfolio status, pending work, workspace health, or 'show me the dashboard' without naming an exact CLI command."
---

# Sentinel Dashboard

Use this skill when the user wants a read-only portfolio view across Ignite Sentinel workspaces, especially in natural language:

- "Mostrame el estado de los proyectos."
- "What is pending across workspaces?"
- "Open the Sentinel dashboard."
- "Which workspaces need attention?"

## Workflow

1. Run from the repository root:

```powershell
python -m sentinel /dashboard
```

2. If the user explicitly asks to open it and the local environment allows browser/file opening, run:

```powershell
python -m sentinel /dashboard --open
```

3. Present the result in plain language: generated path, workspace count, workspaces scanned, and the fact that `dashboard.html` is a local rebuildable snapshot ignored by git.
4. Summarize what needs attention: blocking gaps, DIRTY health, stale backlog/domain context warnings, stories not ready, and the recommended next command shown by the dashboard model.

## Rules

- The dashboard is read-only. Do not mutate workspace files from this skill.
- The source of truth remains `workspaces/[PROJECT_ID]/`; `dashboard.html` is presentation only.
- Do not commit `dashboard.html`. It can embed local workspace markdown and is intentionally git-ignored.
- Keep operation local-first: no remote rendering, no external services, no remote embeddings, and no network calls.
- Do not run follow-up lifecycle commands just because the dashboard recommends them. Ask or confirm when the next command would mutate project artifacts.
- If the user wants implementation details for extending the dashboard, read `references/section-registry.md` before editing runtime.

## Interpretation Hints

- `CLEAN` plus mature/spec/backlog-ready signals means the workspace is structurally ready for the next governed step, not automatically approved by a human.
- `DIRTY`, blocking gaps, stale domain context, missing DoR/DoD evidence, or `[PENDING INPUT]` should be reported as pending decisions or evidence, not as failures of the framework.
- For a single workspace question, use the dashboard only when a portfolio-style visual helps; otherwise route exact lifecycle commands through `sentinel-command-router`.
