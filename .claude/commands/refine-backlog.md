---
description: Merge validated agent-authored backlog refinement proposals with verbatim local citations.
---

# Ignite Refine Backlog

Arguments received from the user invocation: `$ARGUMENTS`

Parse `PROJECT_ID` and `--source PATH` from:

```text
/refine-backlog PROJECT_ID --source PATH
```

The `--source` file is JSON with `proposals[]`. Each proposal declares a kind (`reslice`, `split-story`, `merge-stories`, `missing-story`, or `enabler-candidate`), target stories or source units as applicable, a recommendation, rationale, and verbatim `citations[]` from local source-of-truth evidence.

Run from the repository root:

```powershell
python -m sentinel /refine-backlog PROJECT_ID --source PATH
```

The runtime validates story/unit existence, rejects pending units, checks every citation verbatim, archives the source under `04_backlog/refinements/`, merges valid proposals with `origin: agent`, renders a governed refinement section in the backlog, and reports rejected proposals with reasons. Summarize accepted/rejected proposal IDs and the refinement report path.
