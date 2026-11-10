---
description: Regenerate the shareable Ignite Sentinel discovery gaps document, or record the BA's disposition on a gap an agentic channel raised.
agent: sentinel-discovery
---

# Ignite Gaps

Parse `PROJECT_ID` from:

```text
/gaps PROJECT_ID
/gaps PROJECT_ID --id GAP-X --disposition accepted|rejected|irrelevant [--reason TEXT]
```

Run from the repository root:

```powershell
python -m sentinel /gaps PROJECT_ID
python -m sentinel /gaps PROJECT_ID --id GAP-X --disposition rejected --reason TEXT
```

Return the generated `01_discovery/gaps.md` path and current gap counts.

With `--id` and `--disposition`, record the BA's disposition on a gap an agentic channel raised (`agent`, `challenge`, `scrutiny`, `implementability-probe`, `self-review`). `rejected` and `irrelevant` need `--reason`. `/maturity` reports the false-alarm rate per channel under `maturation_telemetry.agent_channel_dispositions`.
