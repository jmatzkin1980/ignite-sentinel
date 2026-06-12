---
description: Rebuild Ignite local memory after artifact updates.
agent: sentinel-sync
---

# Ignite Reindex

Parse `PROJECT_ID` and optional `--full` from:

```text
/reindex PROJECT_ID
/reindex PROJECT_ID --full
```

Run:

```powershell
python -m sentinel /reindex PROJECT_ID
python -m sentinel /reindex PROJECT_ID --full
```

This refreshes local memory from versionable workspace artifacts, traceability nodes, and context folders. By default it skips unchanged artifacts by `source_hash`, embedder, and chunking version; `--full` forces re-chunking and re-embedding.

Summarize indexed, skipped, and embedded counts.
