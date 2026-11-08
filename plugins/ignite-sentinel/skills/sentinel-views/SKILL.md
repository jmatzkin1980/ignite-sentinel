---
name: sentinel-views
description: "Use when generating, opening, presenting, or interpreting Ignite Sentinel views: the read-only workspace dashboard (/dashboard) and the per-artifact HTML views (/view for gaps, brief, PRD, specs, backlog), with themes, reader edition and local notes; when the user asks for project or portfolio status, pending work, workspace health, 'show me the dashboard' or 'open the PRD view' without naming an exact CLI command. Not for changing artifacts: views are read-only, corrections go through /sync or /resolve-gaps."
---

# Sentinel Views

Use this skill when the user wants a read-only portfolio view across Ignite Sentinel workspaces, especially in natural language:

- "Mostrame el estado de los proyectos."
- "What is pending across workspaces?"
- "Open the Sentinel dashboard."
- "Which workspaces need attention?"

## Workflow

1. Run from the repository root:

```powershell
sh "${CLAUDE_PLUGIN_ROOT}/python.sh" "${CLAUDE_PLUGIN_ROOT}/launcher.py" /dashboard
```

2. If the user explicitly asks to open it and the local environment allows browser/file opening, run:

```powershell
sh "${CLAUDE_PLUGIN_ROOT}/python.sh" "${CLAUDE_PLUGIN_ROOT}/launcher.py" /dashboard --open
```

   To use a theme other than the built-in `neutral`, add `--theme NAME_OR_PATH` (a local theme JSON path; brand themes never live in the repo).
3. Present the result in plain language: generated path, workspace count, workspaces scanned, theme, source cut-off date, and the fact that `dashboard.html` is a local rebuildable snapshot ignored by git.
4. Summarize what needs attention: blocking gaps, DIRTY health, stale backlog/domain context warnings, stories not ready, and the recommended next command shown by the dashboard model.

## Artifact views (/view)

When the user wants one artifact as a navigable page instead of the portfolio:

```powershell
sh "${CLAUDE_PLUGIN_ROOT}/python.sh" "${CLAUDE_PLUGIN_ROOT}/launcher.py" /view PROJECT_ID --artifact prd            # gaps | brief | prd | specs | backlog
sh "${CLAUDE_PLUGIN_ROOT}/python.sh" "${CLAUDE_PLUGIN_ROOT}/launcher.py" /view PROJECT_ID --artifact prd --theme NAME_OR_PATH
```

- Report the generated path, theme and source cut-off.
- Inline provenance is hidden by default (reader edition). Tell the user about the **Show provenance** toggle when they need citations.
- Local notes survive rebuilds. The page warns when the source changed and marks orphaned notes without deleting them.
- Feedback leaves only through the page's Markdown export, routed to `/resolve-gaps` or `/sync`.

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

## Adaptive Decision Ladder (coaching posture)

When the BA asks "where do I start?" across the portfolio, present the workspaces as numbered rungs by what they need — *pick this when…* plus the *why* — not a single "do this next". The dashboard is read-only, so every rung routes to a governed command the BA runs deliberately. (Posture: the Adaptive Decision Ladder, Peters.)

1. **Unblock a `DIRTY` workspace first** — pick this when any workspace shows DIRTY health or blocking gaps. Route through `sentinel-health` / `sentinel-gap-response`. Why: downstream handoff from a dirty workspace is untrustworthy, so it caps the value of everything after it.
2. **Feed a `[PENDING INPUT]` / stale-context workspace** — pick this when a workspace is waiting on client answers or stale domain context. Why: it is idle on missing input, so unblocking it is cheap and moves it without generation work.
3. **Advance a spec/backlog-ready workspace** — pick this when a workspace is `CLEAN` and mature. Route the exact lifecycle command via `sentinel-command-router`. Why: it is ready for the next governed step, and progress here is pure forward motion.
4. **Confirm readiness with a human** — pick this when a workspace looks structurally complete. Why: `CLEAN` plus ready signals means structurally ready, not human-approved — the sign-off is a person's call, not the dashboard's.

Recommend where to start and why; do not run a mutating command just because the dashboard surfaced it.
