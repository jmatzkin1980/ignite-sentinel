---
description: Register BA-owned governed assumptions with risk, uncertainty, cited basis, and ledger visibility.
agent: sentinel-discovery
---

# Ignite Assume

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

`--change CHG-NNN` (IMP-412) registers the assumptions of a change in `01_discovery/CHG-nnn/assumptions.md`: each `closes_gap` must be an open question of that change, and the assumption closes it (`CLOSED`, closure `assumed`, counted apart in `gap_counts`) until it is validated or invalidated. An item may add `validate_with` (who validates it; default its owner). `/assume PROJECT_ID --change CHG-NNN --id ASM-ID --validate --reason TEXT` keeps the closure as an answer; `--invalidate --reason TEXT` opens the question again. An assumption is never a decision: it does not preload later questions nor enter conflicts. The file is all or nothing.
