---
description: Show only the next step, exactly as /status gives it.
agent: sentinel-health
---

# Ignite Next

Parse `PROJECT_ID` from:

```text
/next PROJECT_ID
```

Run from the repository root:

```powershell
python -m sentinel /next PROJECT_ID
```

It prints the next step and nothing else: `key`, `title`, `text` and the `command` to run. It is the same decision as `next_action` in `/status`, so the two never disagree. Read-only.

Say the step in one line and offer the command. For why the project is or is not ready, use `/status`.
