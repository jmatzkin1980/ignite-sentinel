---
description: Register BA-owned governed assumptions with risk, uncertainty, cited basis, and ledger visibility.
agent: sentinel-discovery
---

# Ignite Assume

Parse `PROJECT_ID` and `--source PATH` from:

```text
/assume PROJECT_ID --source PATH
```

The `--source` file is JSON with `assumptions[]`. Each assumption has `id` (`ASM-*`), `lens`, `statement`, human `owner`, `risk` (`low`, `med`, or `high`) as importance/impact, `uncertainty` (`low`, `med`, or `high`, default `med` for legacy rows), `justification` as a verbatim quote from local evidence, and optional `closes_gap` (`GAP-*`) for the gap it provisionally addresses.

Run from the repository root:

```powershell
python -m sentinel /assume PROJECT_ID --source PATH
```

The runtime validates the declared lens, owner, risk, uncertainty, and local citation; writes `01_discovery/assumptions.md`; traces and indexes the assumption register; refreshes `01_discovery/knowledge_state.md/json` with `ASSUMED` units; and keeps high-risk assumptions visible in maturity/status, and marks `risk=high` plus `uncertainty=high` as a non-blocking test-before-advancing signal. Summarize accepted/skipped assumption IDs, risk summary, linked gaps, and the ledger path.
