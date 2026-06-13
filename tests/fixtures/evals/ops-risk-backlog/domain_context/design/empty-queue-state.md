# Design Context - Empty Queue State

Spec Unit: SPEC-U-003

When a queue has no open cases, the read-only dashboard uses the `RiskQueueEmptyState` component and hides risk indicators for that queue row. The design surface is the empty state in `RiskQueueTable`, including neutral copy, no high-risk badge, and no attention color. This state is separate from stale data and service unavailable.
