---
description: Generate the BA-facing backlog board and rollup by epic/status.
---

# Ignite Backlog Status

Arguments received from the user invocation: `$ARGUMENTS`

Parse `PROJECT_ID` from:

```text
/backlog-status PROJECT_ID
```

Run:

```powershell
python -m sentinel /backlog-status PROJECT_ID
```

The runtime reads governed story lifecycle state, DoR/DoD gates, and implementation readiness, writes `04_backlog/BACKLOG.md`, and returns the rollup by epic and status. Summarize total stories, Ready/Done percentages, owners, blockers, and the board path.
