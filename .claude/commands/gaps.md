---
description: Regenerate the shareable Ignite Sentinel discovery gaps document, or record the BA's disposition on a gap an agentic channel raised.
argument-hint: PROJECT_ID [--id GAP-X --disposition accepted|rejected|irrelevant [--reason TEXT]] [--change CHG-NNN [--id GAP-X --impact construccion|operativo --reason TEXT]] [--top N]
---

# Ignite Gaps

Arguments received from the user invocation: `$ARGUMENTS`

Parse `PROJECT_ID` from:

```text
/gaps PROJECT_ID
/gaps PROJECT_ID --id GAP-X --disposition accepted|rejected|irrelevant [--reason TEXT]
/gaps PROJECT_ID --change CHG-NNN
/gaps PROJECT_ID --change CHG-NNN --id GAP-X --impact construccion|operativo --reason TEXT
```

Run from the repository root:

```powershell
python -m sentinel /gaps PROJECT_ID
python -m sentinel /gaps PROJECT_ID --id GAP-X --disposition rejected --reason TEXT
python -m sentinel /gaps PROJECT_ID --change CHG-NNN
python -m sentinel /gaps PROJECT_ID --change CHG-NNN --id GAP-X --impact operativo --reason TEXT
```

Return the generated `01_discovery/gaps.md` path and current gap counts.

With `--id` and `--disposition`, record the BA's disposition on a gap an agentic channel raised (`agent`, `challenge`, `scrutiny`, `implementability-probe`, `self-review`). `rejected` and `irrelevant` need `--reason`. `/maturity` reports the false-alarm rate per channel under `maturation_telemetry.agent_channel_dispositions`.

`--top N` (IMP-257) plans the next round: at most N open gaps (5 by default), ordered scope > security and privacy > UX > technical, one decision per question, the recommended option first (an inference, never applied by itself) and "leave pending" last. It writes `01_discovery/gap_round.md`; ask the BA those questions, nothing more.

Each gap now carries its kind (`client`, `domain` deferrable, `synthesis`, `template`) and, once closed, its closure reason from a closed vocabulary. A closure needs `Evidence or reference`; `by_decision` cites a `DEC-*`, and `resolved_by_inference` cites an `ASM-*` and keeps the gap partially closed until ratified.

`--change CHG-NNN` (IMP-382) regenerates the gap file of that change, `01_discovery/CHG-NNN/gaps.md`, instead of the project's. A change is a change or new feature on an existing system; it matures with its own gap round, apart from the project.

`--change CHG-NNN --id GAP-X --impact construccion|operativo --reason TEXT` (IMP-406) classes an open, non-blocking question of the change as a deferred item: `construccion` holds back the change's build verdict (the default), `operativo` only warns. A blocking or closed question is refused; the reason is required. `/status --change` shows the change verdict with these counts.
