---
description: Generate the PRD and AI-friendly specification when maturity allows it.
argument-hint: PROJECT_ID [--release rN]
---

# Ignite Specs

Arguments received from the user invocation: `$ARGUMENTS`

Parse `PROJECT_ID` from:

```text
/specs PROJECT_ID
```

Run:

```powershell
python -m sentinel /specs PROJECT_ID
```

If maturity is blocked, report the blocker instead of forcing generation.

`--release rN` (IMP-267b) runs this command for one release of a confirmed series: the release brief `02_requirements/rN/project-brief.md` is the input and the outputs land under `03_specs/rN/`, `04_backlog/rN/`, `06_traceability/rN/` and `08_context_packs/rN/`. The release keeps its own lifecycle; the project's state and artifacts are not touched. Without `--release` nothing changes.
