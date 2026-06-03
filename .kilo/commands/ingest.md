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

This also indexes generated artifacts plus workspace context folders into local LanceDB memory.

Then summarize generated `RAW`, `REQ`, `GAP`, `DEC`, `SEED`, `DISC`, and lens review IDs. Mention that `01_discovery/lens_review.md` contains the Product, Technology, Design, and Quality scrutiny, and that focused context can be retrieved with:

```powershell
python -m sentinel /retrieve PROJECT_ID --query "topic" --workflow discovery --write-pack
```
