---
description: Process a client or domain response to discovery gaps.
agent: sentinel-discovery
---

# Ignite Resolve Gaps

Parse `PROJECT_ID` and `--source PATH` from:

```text
/resolve-gaps PROJECT_ID --source PATH
```

Run from the repository root:

```powershell
python -m sentinel /resolve-gaps PROJECT_ID --source PATH
```

Return closed, partially closed, and still-open gap IDs plus the gap resolution report path.
