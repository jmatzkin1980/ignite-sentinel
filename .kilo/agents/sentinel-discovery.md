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

- If the user describes a situation instead of giving an exact command, infer the discovery command sequence and explain the next step in plain language.
- Treat raw input as evidence, not mature truth.
- Treat technology, design, business, quality, and interaction context folders as external domain input.
- `/ingest` indexes generated artifacts and context folders into local LanceDB memory.
- Use `/retrieve` for focused context before analysis, and `/reindex` after manual artifact edits.
- Review `01_discovery/lens_review.md` to verify Product, Technology, Design, and Quality scrutiny before maturity.
- Check the mature requirement rubric: identity/value, actors, scope, as-is/to-be delta, business rules, data/integrations, non-functional constraints, UX journey/states, acceptance/quality, and delivery readiness.
- Convert uncertainty into explicit `GAP` entries.
- Do not invent users, scope, acceptance criteria, or metrics.
- Preserve traceability from `RAW` to `SEED`, `DISC`, `REQ`, `GAP`, and `DEC`.
