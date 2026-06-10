---
description: Evaluate whether an Ignite requirement is ready for specs and backlog.
---

# Ignite Maturity

Arguments received from the user invocation: `$ARGUMENTS`

Parse `PROJECT_ID` from:

```text
/maturity PROJECT_ID
```

Run:

```powershell
python -m sentinel /maturity PROJECT_ID
```

Report whether readiness is `BLOCKED` or ready, and list blocking gaps if present.
