---
description: Create an Ignite Sentinel project workspace.
argument-hint: PROJECT_ID [--brief-version 1|2]
---

# Ignite Init

Arguments received from the user invocation: `$ARGUMENTS`

Parse `PROJECT_ID` from the chat invocation:

```text
/init PROJECT_ID
```

Run from the repository root:

```powershell
python -m sentinel /init PROJECT_ID
```

After execution, confirm the workspace path and remind the user that real project execution should stay in a project branch.

A new project compiles the brief v2 (`--brief-version 1` keeps v1). Before the first `/brief`, ask the BA to confirm profile and genesis (`/brief PROJECT_ID --profile ... --genesis ...`); until then `GAP-BRIEF-PROFILE` blocks the flow.
