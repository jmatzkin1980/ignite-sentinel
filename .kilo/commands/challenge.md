---
description: Run advanced elicitation (pre-mortem, per-lens role-play, assumption inversion, JTBD Four Forces) and merge findings as gaps (origin: challenge).
agent: sentinel-discovery
---

# Ignite Challenge

Parse `PROJECT_ID` and `--source PATH` from:

```text
/challenge PROJECT_ID --source PATH
```

First run advanced elicitation over the maturing requirement, per lens (invariant #1). The technique registry offers seven lenses — pre-mortem, role-play, assumption-inversion, jtbd-forces (push/pull/anxiety/habit), red-blue-team, first-principles, and stakeholder-round-robin — and each finding may name the `technique` it came from. Pass an optional `respondent_profile` (`business` or `technical`) so the runtime calibrates which questions it expects. JTBD findings must cite concrete past events or local observations; hypothetical preference phrasing is only a low-severity guardrail. Capture findings in a JSON `--source` file: a `gaps` array (each gap has `id`, `lens`, `severity`, `question`, a verbatim `evidence` quote from the raw input, and an optional `technique`), plus optional `premortem` and `assumptions_inverted` arrays.

Run from the repository root:

```powershell
python -m sentinel /challenge PROJECT_ID --source PATH
```

The runtime validates each finding exactly like `/annotate` (declared lens, severity range, verbatim evidence), tags them `origin: challenge`, merges them into `01_discovery/gaps.md`, and writes a traced, indexed `01_discovery/challenge_report.md`. Summarize merged and skipped gap IDs plus updated gap counts.
