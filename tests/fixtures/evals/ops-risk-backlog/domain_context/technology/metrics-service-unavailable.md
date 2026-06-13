# Technology Context - Metrics Service Unavailable

Spec Unit: SPEC-U-005

If the metrics service is unavailable, the dashboard implementation must route the unknown status through `src/risk/MetricsGateway.ts` and `RiskStatusFallback`. The critical surfaces are the metrics gateway timeout branch, the unknown-risk status presenter, and the service-health adapter. Engineering must not show stale data copy for this state because the service outage means current risk metrics cannot be read.

Execution commands: `npm test -- metrics-gateway` and `npm run lint -- src/risk`.
