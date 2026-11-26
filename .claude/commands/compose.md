---
description: Merge validated agent-authored PRD narrative blocks with verbatim local citations.
argument-hint: PROJECT_ID --source PATH [--change CHG-NNN]
---

# Ignite Compose

Arguments received from the user invocation: `$ARGUMENTS`

Parse `PROJECT_ID` and `--source PATH` from:

```text
/compose PROJECT_ID --source PATH
/compose PROJECT_ID --source PATH --change CHG-NNN
```

The `--source` file is JSON with `blocks[]`; each block targets an existing PRD section and each paragraph declares verbatim `citations[]` from local source-of-truth evidence.

Run from the repository root:

```powershell
python -m sentinel /compose PROJECT_ID --source PATH
python -m sentinel /compose PROJECT_ID --source PATH --change CHG-NNN
```

The runtime validates section existence, rejects narrative over pending PRD sections, checks every citation verbatim against local evidence, archives the source under `03_specs/compositions/`, merges valid blocks with `origin: agent`, and reports rejected blocks with reasons. Summarize accepted/rejected block IDs and the composition report path.

`--change CHG-NNN` (IMP-433) composes onto the PRD of that change, `03_specs/CHG-NNN/prd.md`, which `/specs PROJECT_ID --change CHG-NNN` must have written first (otherwise the command refuses and names `/specs`). Citations are verbatim lines of the change's own text (request, brief, specs, units). The source and the accepted blocks are kept under `03_specs/CHG-NNN/compositions/`, and `/specs --change` writes them back into the PRD each time it regenerates it, listing any block it had to drop in `regeneration_report.md`. `/compose PROJECT_ID` without `--change` does not touch the PRD of a change; a workspace that only has changes refuses the project form. `--release` is not accepted.
