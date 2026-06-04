---
description: Export a shareable Ignite Sentinel artifact.
agent: sentinel-health
---

# Ignite Export

Parse `PROJECT_ID`, `--artifact`, and optional `--format md` from:

```text
/export PROJECT_ID --artifact gaps --format md
```

Allowed artifacts: `gaps`, `brief`, `context-request`.

Run from the repository root:

```powershell
python -m sentinel /export PROJECT_ID --artifact ARTIFACT --format md
```

Return the copied artifact path under `08_context_packs/exports/`.
