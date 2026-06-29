---
description: Generate the BA-facing backlog board and rollup by epic/status.
---

# Ignite Backlog Status

Arguments received from the user invocation: `$ARGUMENTS`

Parse `PROJECT_ID` and optional `--override PATH` from:

```text
/backlog-status PROJECT_ID
/backlog-status PROJECT_ID --override PATH
```

Run:

```powershell
python -m sentinel /backlog-status PROJECT_ID
python -m sentinel /backlog-status PROJECT_ID --override PATH
```

The runtime reads governed story lifecycle state, DoR/DoD gates, and implementation readiness, writes `04_backlog/BACKLOG.md`, and returns the rollup by epic/status plus a top-level gate summary. If BA/Product intentionally proceeds despite the resulting `WARN`, `--override PATH` accepts a JSON object with cited `decisions[]` in `DEC-*` shape and records the rationale under `06_traceability/gate_overrides/` without changing the gate verdict. Summarize total stories, Ready/Done percentages, owners, blockers, the board path, and any override report/register paths.
