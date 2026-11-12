---
description: Show only the next step, exactly as /status gives it.
argument-hint: PROJECT_ID [--release rN]
---

# Ignite Next

Arguments received from the user invocation: `$ARGUMENTS`

Parse `PROJECT_ID` from:

```text
/next PROJECT_ID
```

`--release rN` (IMP-267b) runs this command for one release of a confirmed series: the release brief `02_requirements/rN/project-brief.md` is the input and the outputs land under `03_specs/rN/`, `04_backlog/rN/`, `05_quality/rN/`, `06_traceability/rN/` and `08_context_packs/rN/`. The release keeps its own lifecycle; the project's state and artifacts are not touched. Without `--release` nothing changes.

Run from the repository root:

```powershell
python -m sentinel /next PROJECT_ID
```

It prints the next step and nothing else: `key`, `title`, `text` and the `command` to run. It is the same decision as `next_action` in `/status`, so the two never disagree. Read-only.

Say the step in one line and offer the command. For why the project is or is not ready, use `/status`.
