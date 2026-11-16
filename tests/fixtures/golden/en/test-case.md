# Test Case Set - US-001

- Project: `[PROJECT_ID]`
- Source story: `US-001`
- Status: `draft`

## Coverage Matrix

| Test Step | Acceptance Criterion |
| --- | --- |
| TC step AC-001-01 [fail-to-pass] | AC-001-01 [fail-to-pass]: Given `SPEC-U-001` is confirmed and its sources are available, When queue metrics are available, the system shall display open risk queues., Then the system produces the observable result the unit states and keeps the trace to its evidence. |
| TC step AC-001-02 [fail-to-pass] | AC-001-02 [fail-to-pass]: Given a precondition, data item or rule that `SPEC-U-001` requires is not met, When the user or the system tries to complete the slice, Then the risky step is blocked or left recoverable, and no false success is recorded. |
| TC step AC-001-03 [fail-to-pass] | AC-001-03 [fail-to-pass]: Given a dependency, data item, permission or external state the unit cites is not available, When the system tries to complete the slice, Then the failure is visible, partial information is not shown as final, and auditability is preserved. |
| TC step AC-001-04 [pass-to-pass] | AC-001-04 [pass-to-pass]: Given existing behavior, contracts or related tests are in place before this story is built, When the increment is validated together with the regression defined by Quality or the repository, Then existing capabilities keep passing with no side effects outside the declared blast radius. |
| TC step AC-001-05 [evidence] | AC-001-05 [evidence]: Given Quality reviews the story for acceptance or automation, When it reads the criteria, scope, dependencies and traces, Then it finds SPEC-U-001, REQ-EARS-001, REQ-001, PRD-001, SPEC-001 and the criteria in a verifiable form. |

## Automation Notes

- Prepare valid input data for the happy path.
- Prepare missing and invalid input data for validation paths.
- Separate fail-to-pass checks, pass-to-pass regression checks, and evidence checks when classifications are present.
- Assert trace IDs remain visible in the artifact chain.
