---
description: Metabolize client responses, meetings, Slack/email content, or domain updates.
agent: sentinel-sync
---

# Ignite Sync

Parse the project ID, source path, and optional note from:

```text
/sync PROJECT_ID --source PATH --note "NOTE"
```

Run:

```powershell
python -m sentinel /sync PROJECT_ID --source PATH --note "NOTE"
```

This indexes the change into local LanceDB memory.

Summarize the change ID, impacted artifacts, and newly detected gaps. Recommend a focused context pack before patching downstream artifacts:

```powershell
python -m sentinel /retrieve PROJECT_ID --query "change topic" --workflow sync --write-pack
```
