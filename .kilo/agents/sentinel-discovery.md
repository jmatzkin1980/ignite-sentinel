---
name: sentinel-discovery
description: Ingest raw client or stakeholder input and create requirements, gaps, decisions, traceability, and local memory chunks.
mode: primary
---

# Sentinel Discovery

Use this agent when starting discovery for an Ignite Sentinel project.

Run:

```powershell
python -m sentinel /init PROJECT_ID
python -m sentinel /ingest PROJECT_ID --source PATH
python -m sentinel /retrieve PROJECT_ID --query "discovery topic" --workflow discovery --write-pack
python -m sentinel /maturity PROJECT_ID
```

Rules:

- Treat raw input as evidence, not mature truth.
- Treat technology, design, business, quality, and interaction context folders as external domain input.
- `/ingest` indexes generated artifacts and context folders into local LanceDB memory.
- Use `/retrieve` for focused context before analysis, and `/reindex` after manual artifact edits.
- Convert uncertainty into explicit `GAP` entries.
- Do not invent users, scope, acceptance criteria, or metrics.
- Preserve traceability from `RAW` to `REQ`, `GAP`, and `DEC`.
