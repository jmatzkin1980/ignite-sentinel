---
description: Generate a local read-only HTML view for one Sentinel artifact.
---

# Ignite View

Arguments received from the user invocation: `$ARGUMENTS`

Parse `PROJECT_ID`, `--artifact`, and optional `--open` from:

```text
/view PROJECT_ID --artifact prd
/view PROJECT_ID --artifact brief --open
```

Allowed artifacts: `gaps`, `brief`, `prd`, `specs`, and `backlog`.

Run from the repository root:

```powershell
python -m sentinel /view PROJECT_ID --artifact ARTIFACT
python -m sentinel /view PROJECT_ID --artifact ARTIFACT --open
```

The runtime reads the Markdown source of truth, traceability graph, and workspace state, then writes a self-contained read-only HTML snapshot under `08_context_packs/views/`. It never mutates the source artifact. Summarize the generated path, source path, section count, pending markers, citations, and trace-node count.
