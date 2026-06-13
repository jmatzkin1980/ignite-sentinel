# Technology Context - Stale Risk Data

Spec Unit: SPEC-U-004

When risk data is stale, the dashboard implementation must route the warning through `src/risk/StaleDataBanner.tsx` and `RiskMetricsFreshnessService`. The critical surfaces are the freshness timestamp adapter, the queue summary view model, and the stale-data warning state. Engineering must not reuse the metrics-service outage fallback for stale data because freshness is a separate state with its own audit note.

Execution commands: `npm test -- risk-dashboard` and `npm run lint -- src/risk`.
