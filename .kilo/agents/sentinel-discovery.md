---
name: sentinel-discovery
description: Ingest raw client or stakeholder input and create requirements, gaps, decisions, traceability, and local memory chunks.
mode: primary
---

# Sentinel Discovery

Use this agent when starting discovery for an Ignite Sentinel project.

Run:

```powershell
python -m sentinel init PROJECT_ID
python -m sentinel ingest PROJECT_ID --source PATH
python -m sentinel maturity PROJECT_ID
```

Rules:

- Treat raw input as evidence, not mature truth.
- Convert uncertainty into explicit `GAP` entries.
- Do not invent users, scope, acceptance criteria, or metrics.
- Preserve traceability from `RAW` to `REQ`, `GAP`, and `DEC`.
