---
description: Ingest raw client, domain, or interaction evidence into an Ignite workspace.
agent: sentinel-discovery
---

# Ignite Ingest

Parse the project ID and source path from the invocation:

```text
/ingest PROJECT_ID --source PATH
```

Run from the repository root:

```powershell
python -m sentinel /ingest PROJECT_ID --source PATH
```

Then summarize generated `RAW`, `REQ`, `GAP`, and `DEC` IDs.
