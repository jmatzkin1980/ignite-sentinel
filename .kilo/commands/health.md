---
description: Audit Ignite workspace health, gaps, traceability, and readiness.
agent: sentinel-health
---

# Ignite Health

Parse `PROJECT_ID` from:

```text
/health PROJECT_ID
```

Run:

```powershell
python -m sentinel /health PROJECT_ID
```

Report the verdict and highest-priority findings. `/health` covers blocking gaps, unbacked metrics, orphan trace nodes, missing memory indexing, and knowledge staleness. A checksum mismatch against the governed `artifact_hashes` snapshot means an artifact was changed outside the CLI: recommend regenerating it through its owning command, never re-saving it by hand. On a soft `needs_context` gate, recommend a focus pack (`/retrieve --write-pack`) before deep analysis.
