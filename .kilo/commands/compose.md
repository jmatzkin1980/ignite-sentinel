---
description: Merge validated agent-authored PRD narrative blocks with verbatim local citations.
agent: sentinel-specs
---

# Ignite Compose

Parse `PROJECT_ID` and `--source PATH` from:

```text
/compose PROJECT_ID --source PATH
```

The `--source` file is JSON with `blocks[]`; each block targets an existing PRD section and each paragraph declares verbatim `citations[]` from local source-of-truth evidence.

Run from the repository root:

```powershell
python -m sentinel /compose PROJECT_ID --source PATH
```

The runtime validates section existence, rejects narrative over pending PRD sections, checks every citation verbatim against local evidence, archives the source under `03_specs/compositions/`, merges valid blocks with `origin: agent`, and reports rejected blocks with reasons. Summarize accepted/rejected block IDs and the composition report path.
