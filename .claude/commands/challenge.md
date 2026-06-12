---
description: Run advanced elicitation (pre-mortem, per-lens role-play, assumption inversion) and merge findings as gaps (origin: challenge).
---

# Ignite Challenge

Arguments received from the user invocation: `$ARGUMENTS`

Parse `PROJECT_ID` and `--source PATH` from:

```text
/challenge PROJECT_ID --source PATH
```

First run advanced elicitation over the maturing requirement, per lens (invariant #1): pre-mortem ("the project failed at 6 months — what did we fail to ask?"), role-play by lens (operator, auditor, attacker...), and assumption inversion. Capture findings in a JSON `--source` file: a `gaps` array (each gap has `id`, `lens`, `severity`, `question`, a verbatim `evidence` quote from the raw input, and an optional `technique`), plus optional `premortem` and `assumptions_inverted` arrays.

Run from the repository root:

```powershell
python -m sentinel /challenge PROJECT_ID --source PATH
```

The runtime validates each finding exactly like `/annotate` (declared lens, severity range, verbatim evidence), tags them `origin: challenge`, merges them into `01_discovery/gaps.md`, and writes a traced, indexed `01_discovery/challenge_report.md`. Summarize merged and skipped gap IDs plus updated gap counts.
