---
name: sentinel-health
description: Audit health, traceability, missing artifacts, unbacked metrics, and local memory indexing.
mode: primary
---

# Sentinel Health

Run:

```powershell
python -m sentinel /health PROJECT_ID
python -m sentinel /validate PROJECT_ID
python -m sentinel /trace PROJECT_ID
```

Rules:

- Use health and validation before handoff.
- Source workspace files are authoritative.
- Memory indexes never override versionable artifacts.
- If domain context changed after backlog generation, treat the backlog as stale and run `/reindex PROJECT_ID` plus `/backlog PROJECT_ID` before implementation handoff.
- `/health` should catch blocking gaps, unbacked metrics, orphan trace nodes, missing memory indexing, stale domain context, and story/epic linkage issues.
- `/validate` should confirm required semantic artifacts exist, including specs context packs, backlog readiness audit, story execution contracts, retrieval plans, and implementation readiness pack.
