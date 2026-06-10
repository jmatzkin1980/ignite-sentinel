---
description: Rebuild Ignite local memory after artifact updates.
---

# Ignite Reindex

Arguments received from the user invocation: `$ARGUMENTS`

Parse `PROJECT_ID` from:

```text
/reindex PROJECT_ID
```

Run:

```powershell
python -m sentinel /reindex PROJECT_ID
```

This rebuilds local LanceDB memory from versionable workspace artifacts, traceability nodes, and context folders.

Summarize indexed artifacts and chunks.
