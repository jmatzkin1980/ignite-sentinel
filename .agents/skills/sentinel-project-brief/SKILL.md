---
name: sentinel-project-brief
description: Use when Codex needs to generate or refresh the Ignite Sentinel mature project brief after discovery gaps and seeds are stable enough.
---

# Sentinel Project Brief

Use this skill to produce the mature discovery handoff.

## Workflow

1. Check current state:

```powershell
python -m sentinel /status PROJECT_ID
python -m sentinel /maturity PROJECT_ID
```

2. Generate or refresh:

```powershell
python -m sentinel /brief PROJECT_ID
```

3. Review `workspaces/PROJECT_ID/02_requirements/project-brief.md`.
4. If domain teams need deeper analysis, create context requests with `sentinel-domain-request`.

## Readiness Check

- The brief should be complete enough to guide PRD, specs, backlog, and acceptance strategy.
- It should not attempt to replace domain packs. Technology can deepen architecture/contracts later; Design can deepen flows/prototypes later; Quality can deepen test cases later.
- Critical/high gaps that are `OPEN`, `ANSWERED`, or `PARTIALLY_CLOSED` should be treated as blockers before downstream specs/backlog.
