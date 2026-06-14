---
description: Generate traceable epics, user stories, and acceptance criteria.
---

# Ignite Backlog

Arguments received from the user invocation: `$ARGUMENTS`

Parse `PROJECT_ID` and optional `--with-task-seeds` from:

```text
/backlog PROJECT_ID
/backlog PROJECT_ID --with-task-seeds
```

Run:

```powershell
python -m sentinel /backlog PROJECT_ID
python -m sentinel /backlog PROJECT_ID --with-task-seeds
```

Default mode generates epics, stories, acceptance criteria, implementation readiness, and slice plan with no task seeds. `--with-task-seeds` is opt-in and adds a per-story Task Seed Contract: ordered implementation intentions traced to AC and critical surfaces. These are not executed, estimated, assigned, scheduled, or managed by Ignite. Summarize generated epic, story, acceptance criteria IDs, and whether task seed contracts were enabled.
