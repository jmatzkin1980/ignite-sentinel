---
description: Evaluate whether an Ignite requirement is ready for specs and backlog.
agent: sentinel-maturity
---

# Ignite Maturity

Parse `PROJECT_ID` from:

```text
/maturity PROJECT_ID
```

Run:

```powershell
python -m sentinel /maturity PROJECT_ID
```

Report whether readiness is `BLOCKED` or ready, and list blocking gaps if present.

A workspace that only holds changes (IMP-431) has no project brief to measure: the command refuses, writes no report and leaves phase, health and metrics untouched; report the refusal and run `/status PROJECT_ID --change CHG-NNN` or `/next PROJECT_ID --change CHG-NNN` instead.
