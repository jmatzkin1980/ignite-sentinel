# Quality Context - Dashboard Access Audit

Spec Unit: SPEC-U-006

Where audit logging is enabled, the quality evidence must prove that dashboard access creates an audit record with actor, timestamp, and dashboard scope. The regression surface is `RiskDashboardAuditTrailTest`, and the evidence bundle should include an access-log assertion plus a trace link to the acceptance criterion for SPEC-U-006.
