---
name: sentinel-sync
description: Ingest stakeholder feedback, meeting notes, or client changes and generate impact analysis.
mode: primary
---

# Sentinel Sync

Run:

```powershell
python -m sentinel /sync PROJECT_ID --source PATH --note "source and intent"
python -m sentinel /retrieve PROJECT_ID --query "change topic" --workflow sync --write-pack
python -m sentinel /reindex PROJECT_ID
python -m sentinel /health PROJECT_ID
```

Rules:

- Treat new information as a `CHG` event.
- `/sync` indexes the change into local LanceDB memory and links it to impacted artifacts.
- Use `/retrieve --workflow sync --write-pack` before patching downstream artifacts.
- Run `/reindex PROJECT_ID` after manual artifact edits so memory matches source files.
- Do not silently patch downstream artifacts.
- Review impact before considering the workspace healthy.
