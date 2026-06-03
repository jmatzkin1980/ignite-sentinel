---
description: Retrieve a focused context pack for an Ignite workflow.
agent: sentinel-sync
---

# Ignite Retrieve

Parse project ID, query, workflow, and optional filters from:

```text
/retrieve PROJECT_ID --query "TEXT" --workflow WORKFLOW
```

Run:

```powershell
python -m sentinel /retrieve PROJECT_ID --query "TEXT" --workflow WORKFLOW --write-pack
```

If the user provided `--limit`, `--artifact-type`, `--domain`, or `--trace-id`, preserve those options.
