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

The runtime applies the governed closure matrix per gap: a substantive answer over a confirmed gap marks it `CLOSED`; a substantive answer still pending confirmation becomes `ANSWERED`; a vague or partial answer becomes `PARTIALLY_CLOSED`; an unusable answer stays `OPEN`. A vague answer never closes a gap even if it is flagged confirmed. Prefer an EARS reformulation for functional gaps as they close, and report the knowledge metabolism the closure triggers (validated assumptions, recalculated certainty, staleness). Return closed, answered, partially closed, and still-open gap IDs plus the gap resolution report path.
