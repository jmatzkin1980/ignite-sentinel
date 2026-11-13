# Prototype trace — P

Element → data → contract → rule, one screen per pass, verified against the prototype inventory. Values come from the inventory, never from the agent.

## F-01 S2 Sign in

- Verdict: **has_gaps** · mode proposed · executed in a browser
- Elements traced: 4 of 7 (established 2, inferred 1, unsupported 1, demo 0)
- States: ideal shown, empty not_built, loading not_built, error shown

| Element | Text (from the inventory) | Level | Data | Contract | Rule | Support |
|---|---|---|---|---|---|---|
| S2-E01 | Sign in | established | the screen title | none | sign in before filing | §3.2 "signs in with email and password" |
| S2-E06 | Continue | established | the email and password typed | sign-in request | only registered policyholders sign in | §3.2 "signs in with email and password before filing a claim" |
| S2-E07 | The email or the password is not right. | inferred |  |  |  | (inferred) the brief names sign-in but not its error message |
| S2-E03 | you@example.com | unsupported |  |  |  | `GAP-DESIGN-STATES` |

Checks:

- who_reads_value: the password field is read by the authentication service (fix: none)
- four_states: loading and empty are not built (fix: prototype)

Questions:

- Which message does a locked account see?
- Is there a password recovery path?
