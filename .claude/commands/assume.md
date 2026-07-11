---
description: Register BA-owned governed assumptions with risk, uncertainty, cited basis, and ledger visibility.
---

# Ignite Assume

Arguments received from the user invocation: `$ARGUMENTS`

Parse `PROJECT_ID` and `--source PATH` from:

```text
/assume PROJECT_ID --source PATH
```

The `--source` file is JSON with `assumptions[]`. Each assumption has `id` (`ASM-*`), `lens`, `statement`, human `owner`, `risk` (`low`, `med`, or `high`) as importance/impact, `uncertainty` (`low`, `med`, or `high`, default `med` for legacy rows), `justification` as a verbatim quote from local evidence, optional `closes_gap` (`GAP-*`) for the gap it provisionally addresses, and optional `risk_category` (`value`, `usability`, `viability`, or `feasibility` - Cagan's four product risks, kept separate from `lens` and extensible via a directory override).

Run from the repository root:

```powershell
python -m sentinel /assume PROJECT_ID --source PATH
```

The runtime validates the declared lens, owner, risk, uncertainty, local citation, and optional risk category; writes `01_discovery/assumptions.md` (grouped by `risk_category` when any assumption declares one); traces and indexes the assumption register; refreshes `01_discovery/knowledge_state.md/json` with `ASSUMED` units; keeps high-risk assumptions visible in maturity/status; marks `risk=high` plus `uncertainty=high` as a non-blocking test-before-advancing signal; and reports per-category coverage in the development readiness matrix. Summarize accepted/skipped assumption IDs, risk summary, linked gaps, and the ledger path.
