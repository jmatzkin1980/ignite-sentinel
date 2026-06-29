---
description: Validate Ignite workspace structure, graph integrity, semantic quality, and cross-artifact consistency.
---

# Ignite Validate

Arguments received from the user invocation: `$ARGUMENTS`

Parse `PROJECT_ID` from:

```text
/validate PROJECT_ID
```

Run:

```powershell
python -m sentinel /validate PROJECT_ID
```

Report whether the workspace is structurally valid. Also summarize non-blocking `semantic_quality` and `cross_artifact_consistency` warnings, naming the affected layer, artifact, and suggested corrective command when present. `cross_artifact_consistency` now also checks handoff fidelity from confirmed `SPEC-U-*` statements into backlog acceptance criteria, so call out any `spec_unit->story` warning explicitly.
