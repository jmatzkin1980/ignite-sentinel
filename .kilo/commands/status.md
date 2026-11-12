---
description: Show the ready-to-build verdict, gap counts, gate matrix, maturity score and next step.
agent: sentinel-health
---

# Ignite Status

Parse `PROJECT_ID` from:

```text
/status PROJECT_ID [--full]
```

`--release rN` (IMP-267b) runs this command for one release of a confirmed series: the release brief `02_requirements/rN/project-brief.md` is the input and the outputs land under `03_specs/rN/`, `04_backlog/rN/`, `06_traceability/rN/` and `08_context_packs/rN/`. The release keeps its own lifecycle; the project's state and artifacts are not touched. Without `--release` nothing changes.

Run from the repository root:

```powershell
python -m sentinel /status PROJECT_ID
```

The default output is the summary: the counts-based ready-to-build `verdict` (`READY`, `READY_WITH_WARNINGS` or `NOT_READY`) with its blockers, warnings and the checks that could not run (`partial_coverage`), the gap counts, the gate matrix, the maturity score and the next step. `--full` adds the detailed maturity and development-readiness metrics.

Report the verdict first and what blocks it, then the next step exactly as `next_action` gives it. Never call a workspace ready when the verdict is not `READY`, and never hide a `partial_coverage` entry.
