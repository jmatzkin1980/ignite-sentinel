---
description: Metabolize client responses, meetings, Slack/email content, or domain updates.
---

# Ignite Sync

Arguments received from the user invocation: `$ARGUMENTS`

Parse the project ID, optional source path, and optional note from:

```text
/sync PROJECT_ID
/sync PROJECT_ID --source PATH --note "NOTE"
```

Run:

```powershell
python -m sentinel /sync PROJECT_ID
python -m sentinel /sync PROJECT_ID --source PATH --note "NOTE"
```

Without `--source`, Sentinel scans known input and workspace context folders, detects new or modified files by hash, processes each novelty as a `CHG` event, and indexes the result into local LanceDB memory.

With `--source`, Sentinel processes only the specified file.

The command protocol records the sync anchor in `06_traceability/command_protocol_log.md` and refreshes trace views after the mutation.

Summarize the change ID, impacted artifacts, and newly detected gaps. Recommend a focused context pack before patching downstream artifacts:

```powershell
python -m sentinel /retrieve PROJECT_ID --query "change topic" --workflow sync --write-pack
```
