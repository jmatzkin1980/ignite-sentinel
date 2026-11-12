---
description: Generate or refresh the Ignite traceability matrix and graph.
argument-hint: PROJECT_ID [--release rN]
---

# Ignite Trace

Arguments received from the user invocation: `$ARGUMENTS`

Parse `PROJECT_ID` from:

```text
/trace PROJECT_ID
```

Run:

```powershell
python -m sentinel /trace PROJECT_ID
```

Summarize graph and matrix locations.

`--release rN` (IMP-267b) runs this command for one release of a confirmed series: the release brief `02_requirements/rN/project-brief.md` is the input and the outputs land under `03_specs/rN/`, `04_backlog/rN/`, `06_traceability/rN/` and `08_context_packs/rN/`. The release keeps its own lifecycle; the project's state and artifacts are not touched. Without `--release` nothing changes.
