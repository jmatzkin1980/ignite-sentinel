---
description: Regenerate the shareable Ignite Sentinel discovery gaps document.
agent: sentinel-discovery
---

# Ignite Gaps

Parse `PROJECT_ID` from:

```text
/gaps PROJECT_ID
```

Run from the repository root:

```powershell
python -m sentinel /gaps PROJECT_ID
```

Return the generated `01_discovery/gaps.md` path and current gap counts.
