---
description: Show the ready-to-build verdict, gap counts, gate matrix, maturity score and next step.
agent: sentinel-health
---

# Ignite Status

Parse `PROJECT_ID` from:

```text
/status PROJECT_ID [--full]
```

Run from the repository root:

```powershell
python -m sentinel /status PROJECT_ID
```

The default output is the summary: the counts-based ready-to-build `verdict` (`READY`, `READY_WITH_WARNINGS` or `NOT_READY`) with its blockers, warnings and the checks that could not run (`partial_coverage`), the gap counts, the gate matrix, the maturity score and the next step. `--full` adds the detailed maturity and development-readiness metrics.

Report the verdict first and what blocks it, then the next step exactly as `next_action` gives it. Never call a workspace ready when the verdict is not `READY`, and never hide a `partial_coverage` entry.
