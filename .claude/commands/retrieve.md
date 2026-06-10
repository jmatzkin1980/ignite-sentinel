---
description: Retrieve a focused context pack for an Ignite workflow.
---

# Ignite Retrieve

Arguments received from the user invocation: `$ARGUMENTS`

Parse project ID, query, workflow, and optional filters from:

```text
/retrieve PROJECT_ID --query "TEXT" --workflow WORKFLOW
```

Run:

```powershell
python -m sentinel /retrieve PROJECT_ID --query "TEXT" --workflow WORKFLOW --write-pack
```

If the user provided `--limit`, `--artifact-type`, `--domain`, or `--trace-id`, preserve those options.

Retrieval uses local LanceDB memory when available. Source files remain the authority; if results look stale, run `/reindex PROJECT_ID`.
