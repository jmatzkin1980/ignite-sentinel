---
description: Generate a local read-only HTML view for one Sentinel artifact.
argument-hint: PROJECT_ID --artifact backlog|brief|gaps|prd|specs [OPTIONS]
---

# Ignite View

Arguments received from the user invocation: `$ARGUMENTS`

Parse `PROJECT_ID`, `--artifact`, and optional `--open` / `--theme` from:

```text
/view PROJECT_ID --artifact prd
/view PROJECT_ID --artifact brief --open
```

Allowed artifacts: `gaps`, `brief`, `prd`, `specs`, and `backlog`.

Run from the repository root:

```powershell
python -m sentinel /view PROJECT_ID --artifact ARTIFACT
python -m sentinel /view PROJECT_ID --artifact ARTIFACT --open
python -m sentinel /view PROJECT_ID --artifact ARTIFACT --theme neutral
```

`--theme` takes a built-in theme name or the path to a local theme JSON; without it the workspace config `theme:` applies, else `neutral`.

The runtime reads the Markdown source of truth, traceability graph, and workspace state, then writes a self-contained read-only HTML snapshot under `08_context_packs/views/`. It never mutates the source artifact. The output is reproducible (source cut-off and sha256 instead of a build time), and inline provenance is hidden behind a reader toggle. Summarize the generated path, source path, theme, cut-off, section count, pending markers, citations, and trace-node count.
