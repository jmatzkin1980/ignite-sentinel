---
name: sentinel-health
description: Audit health, traceability, missing artifacts, unbacked metrics, and local memory indexing.
mode: primary
---

# Sentinel Health

Run:

```powershell
python -m sentinel health PROJECT_ID
python -m sentinel validate PROJECT_ID
python -m sentinel trace PROJECT_ID
```

Rules:

- Use health and validation before handoff.
- Source workspace files are authoritative.
- Memory indexes never override versionable artifacts.
