---
description: Validate that Ignite Sentinel is ready in this VS Code workspace.
agent: sentinel-health
---

# Ignite Doctor

Run this command from the repository root:

```powershell
python -m sentinel /doctor
```

Summarize the verdict, failures, and warnings. If `python` is unavailable, tell the user to run the same command with their approved Python runtime.
