---
description: Merge systematic per-lens scrutiny findings as cited gaps (origin: scrutiny) and refresh the knowledge ledger.
agent: sentinel-discovery
---

# Ignite Scrutinize

Parse `PROJECT_ID`, optional `--lens LENS`, and `--source PATH` from:

```text
/scrutinize PROJECT_ID --source PATH
/scrutinize PROJECT_ID --lens technical --source PATH
```

The `--source` file is JSON with systematic findings by Ignite lens. Each gap has `id`, `lens`, `severity`, `finding_type` (`unstated-assumption`, `contradiction`, `mention-without-counterpart`, or `domain-conflict`), `question`, and a verbatim `evidence` quote from the raw input or local domain context folders.

Run from the repository root:

```powershell
python -m sentinel /scrutinize PROJECT_ID --source PATH
```

The runtime validates declared lens, optional lens filter, severity, finding type, and citation; tags accepted gaps `origin: scrutiny`; writes `01_discovery/scrutiny_report.md`; refreshes `01_discovery/knowledge_state.md/json`; and records traceability. Summarize merged/skipped gap IDs, updated gap counts, and the ledger path.
