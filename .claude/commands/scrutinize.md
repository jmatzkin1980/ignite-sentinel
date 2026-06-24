---
description: Merge systematic per-lens scrutiny findings as cited gaps (origin: scrutiny) and refresh the knowledge ledger.
---

# Ignite Scrutinize

Arguments received from the user invocation: `$ARGUMENTS`

Parse `PROJECT_ID`, optional `--lens LENS`, optional `--mode MODE`, and `--source PATH` from:

```text
/scrutinize PROJECT_ID --source PATH
/scrutinize PROJECT_ID --lens technical --source PATH
/scrutinize PROJECT_ID --mode implementability-probe --source PATH
```

The `--source` file is JSON with systematic findings by Ignite lens. Each gap has `id`, `lens`, `severity`, `finding_type`, `question`, and a verbatim `evidence` quote from the raw input or local domain context folders.

`--mode` selects the pass (default `scrutiny`):
- `scrutiny`: systematic per-lens gap finding; `finding_type` is `unstated-assumption`, `contradiction`, `mention-without-counterpart`, or `domain-conflict`; tags `origin: scrutiny`; writes `01_discovery/scrutiny_report.md`.
- `implementability-probe` (IMP-119): the pre-flight, per-Requirement-Unit mirror of `/implementation-feedback`. A coding agent declares, per RU, what it is missing to implement. Every finding additionally requires a `unit` (`RU-NNN`, IMP-115) and uses `finding_type` `missing-context`, `non-inferable-gap`, or `ambiguous-for-implementation`; tags `origin: implementability-probe`; writes `01_discovery/implementability_probe_report.md`.

Run from the repository root:

```powershell
python -m sentinel /scrutinize PROJECT_ID --source PATH
python -m sentinel /scrutinize PROJECT_ID --mode implementability-probe --source PATH
```

The runtime validates declared lens, optional lens filter, severity, finding type, RU anchor (probe mode), and citation; tags accepted gaps with the mode origin; writes the matching report; refreshes `01_discovery/knowledge_state.md/json`; and records traceability. Nothing is auto-resolved. Summarize merged/skipped gap IDs, updated gap counts, and the report path.
