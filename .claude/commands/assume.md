---
description: Register BA-owned governed assumptions with risk, cited basis, and ledger visibility.
---

# Ignite Assume

Arguments received from the user invocation: `$ARGUMENTS`

Parse `PROJECT_ID` and `--source PATH` from:

```text
/assume PROJECT_ID --source PATH
```

The `--source` file is JSON with `assumptions[]`. Each assumption has `id` (`ASM-*`), `lens`, `statement`, human `owner`, `risk` (`low`, `med`, or `high`), `justification` as a verbatim quote from local evidence, and optional `closes_gap` (`GAP-*`) for the gap it provisionally addresses.

Run from the repository root:

```powershell
python -m sentinel /assume PROJECT_ID --source PATH
```

The runtime validates the declared lens, owner, risk, and local citation; writes `01_discovery/assumptions.md`; traces and indexes the assumption register; refreshes `01_discovery/knowledge_state.md/json` with `ASSUMED` units; and keeps high-risk assumptions visible in maturity/status. Summarize accepted/skipped assumption IDs, risk summary, linked gaps, and the ledger path.
