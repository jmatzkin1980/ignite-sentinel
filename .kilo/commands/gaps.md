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

`--top N` (IMP-257) plans the next round: at most N open gaps (5 by default), ordered scope > security and privacy > UX > technical, one decision per question, the recommended option first (an inference, never applied by itself) and "leave pending" last. It writes `01_discovery/gap_round.md`; ask the BA those questions, nothing more.

Each gap now carries its kind (`client`, `domain` deferrable, `synthesis`, `template`) and, once closed, its closure reason from a closed vocabulary. A closure needs `Evidence or reference`; `by_decision` cites a `DEC-*`, and `resolved_by_inference` cites an `ASM-*` and keeps the gap partially closed until ratified.
